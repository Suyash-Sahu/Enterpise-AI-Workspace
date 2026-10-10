import json
import logging
import time
import uuid
from fastapi import APIRouter, Depends, HTTPException, Response, BackgroundTasks, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_db, get_current_user
from app.models.user import User
from app.models.evaluation import EvaluationRun, EvaluationResult, EvaluationMetric, EvaluationTask
from app.evaluation.schemas import (
    EvaluationRunCreateSchema,
)
from app.evaluation.runner import EvaluationRunner
from app.evaluation.exporters import EvaluationExporter
from app.evaluation.dataset_loader import DatasetLoader
from app.utils.response import success_response, error_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/evaluation", tags=["AMOF Research Evaluation & Benchmarking"])


@router.get("/health")
def evaluation_health(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Health/status check endpoint for P10 Evaluation Benchmarking System.
    Distinguishes 'healthy' vs 'dataset_required' based on dataset availability.
    """
    start_time = time.time()
    try:
        dataset_available = False
        dataset_hash = None
        task_count = 0
        dataset_ver = "amof_eval_v1"

        try:
            meta, items = DatasetLoader.load_dataset(dataset_ver)
            dataset_available = True
            dataset_hash = meta.dataset_hash
            task_count = meta.task_count
        except Exception:
            pass

        run_count = db.query(EvaluationRun).count()
        health_status = "healthy" if dataset_available else "dataset_required"

        return success_response(
            data={
                "status": health_status,
                "module": "P10 Research Evaluation & Benchmarking System",
                "database": True,
                "dataset": {
                    "available": dataset_available,
                    "version": dataset_ver if dataset_available else "DATASET_REQUIRED",
                    "hash": dataset_hash,
                    "task_count": task_count,
                },
                "evaluation_engine": True,
                "total_evaluation_runs": run_count,
            },
            message="Evaluation benchmarking system health status retrieved",
            start_time=start_time,
        )
    except Exception as e:
        return error_response(
            message="Evaluation health check failed",
            exc=e,
            start_time=start_time,
            status_code=500,
        )


def _run_evaluation_background(
    run_id: str,
    dataset_version: str,
    config_dict: dict,
    run_baselines: bool,
    run_ablations: bool,
):
    """
    Background worker thread function executing evaluation tasks without blocking HTTP request.
    """
    from app.db.session import SessionLocal
    db = SessionLocal()
    try:
        from app.evaluation.schemas import EvaluationConfigSchema
        config = EvaluationConfigSchema(**config_dict) if config_dict else None
        EvaluationRunner.start_run(
            db=db,
            dataset_version=dataset_version,
            config=config,
            run_baselines=run_baselines,
            run_ablations=run_ablations,
            existing_run_id=run_id,
        )
    except Exception as e:
        # Background task: nothing is awaiting this, so the traceback would be
        # lost entirely if it were not logged here.
        logger.error("Evaluation run %s failed", run_id, exc_info=e)
        run = db.query(EvaluationRun).filter(EvaluationRun.run_id == run_id).first()
        if run:
            run.status = "failed"
            db.commit()
    finally:
        db.close()


@router.post("/runs", response_model=dict, status_code=status.HTTP_202_ACCEPTED)
def create_evaluation_run(
    payload: EvaluationRunCreateSchema,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Asynchronously initiate a real evaluation run.
    Enforces EVALUATION_MAX_CONCURRENT_RUNS = 1 (returns HTTP 409 if a run is active).
    Returns HTTP 202 Accepted with run_id and status 'pending'.
    """
    start_time = time.time()
    
    # 1. Check concurrency control
    active_run = db.query(EvaluationRun).filter(
        EvaluationRun.status.in_(["running", "pending"])
    ).first()
    if active_run:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Evaluation run '{active_run.run_id}' is currently in progress. Concurrent evaluation runs are restricted.",
        )

    # 2. Check dataset presence
    dataset_ver = payload.dataset_version
    try:
        meta, items = DatasetLoader.load_dataset(dataset_ver)
    except Exception as e:
        # The dataset version is caller-supplied and safe to echo; the loader's
        # exception text is not — it carries filesystem paths.
        logger.warning(
            "Evaluation dataset load failed for %r", dataset_ver, exc_info=e
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Required evaluation dataset '{dataset_ver}' is missing or invalid",
        )

    # 3. Create initial pending EvaluationRun record
    run_uuid = f"run_{uuid.uuid4().hex[:12]}"
    config_dict = payload.config.model_dump() if payload.config else {}
    
    from app.evaluation.reproducibility import ReproducibilityManager
    config_hash = ReproducibilityManager.calculate_config_hash(config_dict)
    git_commit = ReproducibilityManager.get_git_commit()

    run_record = EvaluationRun(
        run_id=run_uuid,
        status="pending",
        dataset_version=meta.dataset_version,
        dataset_hash=meta.dataset_hash,
        configuration_hash=config_hash,
        task_count=meta.task_count,
        completed_count=0,
        failed_count=0,
        configuration_json=config_dict,
        git_commit=git_commit,
    )
    db.add(run_record)
    db.commit()
    db.refresh(run_record)

    # 4. Dispatch background task
    background_tasks.add_task(
        _run_evaluation_background,
        run_id=run_uuid,
        dataset_version=payload.dataset_version,
        config_dict=config_dict,
        run_baselines=payload.run_baselines,
        run_ablations=payload.run_ablations,
    )

    return success_response(
        data={
            "run_id": run_uuid,
            "status": "pending",
            "dataset_version": meta.dataset_version,
            "dataset_hash": meta.dataset_hash,
            "configuration_hash": config_hash,
            "task_count": meta.task_count,
            "git_commit": git_commit,
            "created_at": run_record.created_at.isoformat(),
        },
        message="Evaluation run initiated asynchronously",
        start_time=start_time,
        status_code=202,
    )


@router.get("/runs", response_model=dict)
def list_evaluation_runs(
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List actual evaluation runs.
    """
    start_time = time.time()
    try:
        runs = (
            db.query(EvaluationRun)
            .order_by(EvaluationRun.created_at.desc())
            .limit(limit)
            .all()
        )
        run_list = []
        for r in runs:
            run_list.append({
                "run_id": r.run_id,
                "status": r.status,
                "dataset_version": r.dataset_version,
                "dataset_hash": r.dataset_hash,
                "configuration_hash": r.configuration_hash,
                "started_at": r.started_at.isoformat() if r.started_at else None,
                "completed_at": r.completed_at.isoformat() if r.completed_at else None,
                "task_count": r.task_count,
                "completed_count": r.completed_count,
                "failed_count": r.failed_count,
                "git_commit": r.git_commit,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            })
        return success_response(
            data=run_list,
            message="Retrieved evaluation runs list",
            start_time=start_time,
        )
    except Exception as e:
        return error_response(
            message="Failed to list evaluation runs",
            exc=e,
            start_time=start_time,
            status_code=500,
        )


@router.get("/runs/{run_id}", response_model=dict)
def get_evaluation_run(
    run_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return evaluation run metadata.
    """
    start_time = time.time()
    run = db.query(EvaluationRun).filter(EvaluationRun.run_id == run_id).first()
    if not run:
        return error_response(
            message=f"Evaluation run '{run_id}' not found",
            start_time=start_time,
            status_code=404,
        )

    metrics = db.query(EvaluationMetric).filter(EvaluationMetric.run_id == run_id).all()
    metrics_list = [
        {
            "metric_name": m.metric_name,
            "metric_value": m.metric_value,
            "numerator": m.numerator,
            "denominator": m.denominator,
            "metric_status": m.metric_status,
            "metadata": m.metric_metadata,
        }
        for m in metrics
    ]

    config_json = run.configuration_json or {}
    baselines = config_json.get("baselines", [])
    ablations = config_json.get("ablations", [])

    data = {
        "run_id": run.run_id,
        "status": run.status,
        "dataset_version": run.dataset_version,
        "dataset_hash": run.dataset_hash,
        "configuration_hash": run.configuration_hash,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "task_count": run.task_count,
        "completed_count": run.completed_count,
        "failed_count": run.failed_count,
        "configuration_json": config_json,
        "git_commit": run.git_commit,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "metrics": metrics_list,
        "baselines": baselines,
        "ablations": ablations,
    }
    return success_response(
        data=data,
        message=f"Retrieved metadata for run {run_id}",
        start_time=start_time,
    )


@router.get("/runs/{run_id}/metrics", response_model=dict)
def get_evaluation_metrics(
    run_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return calculated metrics for a given evaluation run.
    """
    start_time = time.time()
    metrics = db.query(EvaluationMetric).filter(EvaluationMetric.run_id == run_id).all()
    metrics_list = [
        {
            "metric_name": m.metric_name,
            "metric_value": m.metric_value,
            "numerator": m.numerator,
            "denominator": m.denominator,
            "metric_status": m.metric_status,
            "metadata": m.metric_metadata,
        }
        for m in metrics
    ]
    return success_response(
        data=metrics_list,
        message=f"Retrieved metrics for run {run_id}",
        start_time=start_time,
    )


@router.get("/runs/{run_id}/paper-summary", response_model=dict)
def get_paper_summary(
    run_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return consolidated JSON summary containing measured metrics, numerators, denominators,
    metric_status, SHA-256 hashes, and git commit for research paper inclusion.
    """
    start_time = time.time()
    run = db.query(EvaluationRun).filter(EvaluationRun.run_id == run_id).first()
    if not run:
        return error_response(
            message=f"Run '{run_id}' not found",
            start_time=start_time,
            status_code=404,
        )

    metrics = db.query(EvaluationMetric).filter(EvaluationMetric.run_id == run_id).all()
    metrics_map = {
        m.metric_name: {
            "value": m.metric_value,
            "numerator": m.numerator,
            "denominator": m.denominator,
            "status": m.metric_status,
            "metadata": m.metric_metadata,
        }
        for m in metrics
    }

    paper_data = {
        "run_id": run.run_id,
        "dataset_version": run.dataset_version,
        "dataset_hash": run.dataset_hash,
        "configuration_hash": run.configuration_hash,
        "git_commit": run.git_commit,
        "status": run.status,
        "task_count": run.task_count,
        "completed_count": run.completed_count,
        "failed_count": run.failed_count,
        "measured_metrics": metrics_map,
    }

    return success_response(
        data=paper_data,
        message=f"Retrieved research paper summary for run {run_id}",
        start_time=start_time,
    )


@router.get("/runs/{run_id}/results", response_model=dict)
def get_evaluation_results(
    run_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return item-level task evaluation results for a given run.
    """
    start_time = time.time()
    results = db.query(EvaluationResult).filter(EvaluationResult.run_id == run_id).all()
    tasks_map = {
        t.task_id: t
        for t in db.query(EvaluationTask).filter(EvaluationTask.run_id == run_id).all()
    }

    res_list = []
    for r in results:
        task = tasks_map.get(r.task_id)
        res_list.append({
            "task_id": r.task_id,
            "task_text": task.task_text if task else "",
            "category": task.category if task else "",
            "complexity": task.complexity if task else "",
            "privacy_level": task.privacy_level if task else r.privacy_classification,
            "expected_capability": task.expected_capability if task else "",
            "expected_execution_mode": task.expected_execution_mode if task else "",
            "actual_capability": r.actual_capability,
            "actual_execution_mode": r.actual_execution_mode,
            "actual_model": r.actual_model,
            "routing_correct": r.routing_correct,
            "approval_required": r.approval_required,
            "approval_status": r.approval_status,
            "execution_blocked": r.execution_blocked,
            "approval_guard_triggered": r.approval_guard_triggered,
            "cache_hit": r.cache_hit,
            "verification_status": r.verification_status,
            "latency_ms": r.latency_ms,
            "input_tokens": r.input_tokens,
            "output_tokens": r.output_tokens,
            "total_tokens": r.total_tokens,
            "estimated_cost": r.estimated_cost,
            "completion_success": r.completion_success,
            "error_type": r.error_type,
            "error_message": r.error_message,
        })

    return success_response(
        data=res_list,
        message=f"Retrieved item-level results for run {run_id}",
        start_time=start_time,
    )


@router.get("/runs/{run_id}/ablation", response_model=dict)
def get_evaluation_ablation(
    run_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return component ablation results for a given run.
    """
    start_time = time.time()
    run = db.query(EvaluationRun).filter(EvaluationRun.run_id == run_id).first()
    if not run:
        return error_response(
            message=f"Run '{run_id}' not found",
            start_time=start_time,
            status_code=404,
        )

    ablations = (run.configuration_json or {}).get("ablations", [])
    return success_response(
        data=ablations,
        message=f"Retrieved ablation results for run {run_id}",
        start_time=start_time,
    )


@router.get("/runs/{run_id}/comparison", response_model=dict)
def get_evaluation_comparison(
    run_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return baseline comparison results for a given run.
    """
    start_time = time.time()
    run = db.query(EvaluationRun).filter(EvaluationRun.run_id == run_id).first()
    if not run:
        return error_response(
            message=f"Run '{run_id}' not found",
            start_time=start_time,
            status_code=404,
        )

    baselines = (run.configuration_json or {}).get("baselines", [])
    return success_response(
        data=baselines,
        message=f"Retrieved baseline comparison for run {run_id}",
        start_time=start_time,
    )


@router.get("/runs/{run_id}/export/csv")
def export_evaluation_csv(
    run_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Export actual item-level evaluation results as a downloadable CSV file.
    """
    run = db.query(EvaluationRun).filter(EvaluationRun.run_id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")

    csv_content = EvaluationExporter.export_csv(db=db, run_id=run_id)
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=evaluation_results_{run_id}.csv"},
    )


@router.get("/runs/{run_id}/export/json")
def export_evaluation_json(
    run_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Export full evaluation run artifact as a downloadable JSON file.
    """
    run = db.query(EvaluationRun).filter(EvaluationRun.run_id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")

    json_data = EvaluationExporter.export_json(db=db, run_id=run_id)
    return Response(
        content=json.dumps(json_data, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename=evaluation_artifact_{run_id}.json"},
    )

