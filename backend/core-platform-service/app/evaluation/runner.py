import os
import json
import uuid
import logging
from typing import List, Optional
from sqlalchemy.orm import Session

from app.evaluation.schemas import (
    EvaluationConfigSchema,
    EvaluationRunResponseSchema,
    EvaluationResultItemSchema,
)
from app.evaluation.dataset_loader import DatasetLoader
from app.evaluation.reproducibility import ReproducibilityManager
from app.evaluation.recorder import EvaluationRecorder
from app.evaluation.executor import TaskExecutor
from app.evaluation.metrics import MetricsEngine
from app.evaluation.baselines import BaselineRunner
from app.evaluation.ablation import AblationRunner
from app.evaluation.exporters import EvaluationExporter

from app.utils.timeutils import utcnow_naive

logger = logging.getLogger(__name__)


class EvaluationRunner:
    """
    Orchestrates the entire evaluation lifecycle: dataset loading, task execution, metric calculation, baseline & ablation runs, artifact generation.
    """

    ARTIFACTS_DIR = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "evaluation",
        "artifacts",
    )

    @classmethod
    def start_run(
        cls,
        db: Session,
        dataset_version: str = "amof_eval_v1",
        config: Optional[EvaluationConfigSchema] = None,
        run_baselines: bool = True,
        run_ablations: bool = True,
        existing_run_id: Optional[str] = None,
    ) -> EvaluationRunResponseSchema:
        if config is None:
            config = EvaluationConfigSchema(dataset_version=dataset_version)

        run_uuid = existing_run_id if existing_run_id else f"run_{uuid.uuid4().hex[:12]}"
        
        # Load real dataset
        metadata, items = DatasetLoader.load_dataset(dataset_version)
        config_dict = config.model_dump()
        repro_metadata = ReproducibilityManager.build_run_metadata(metadata.dataset_hash, config_dict)

        # Merge configuration metadata
        full_config = {**config_dict, **repro_metadata}

        # 1. Create or retrieve DB run record
        db_run = None
        if existing_run_id:
            from app.models.evaluation import EvaluationRun
            db_run = db.query(EvaluationRun).filter(EvaluationRun.run_id == existing_run_id).first()
            if db_run:
                db_run.status = "running"
                db_run.started_at = utcnow_naive()
                db.commit()
                db.refresh(db_run)
        
        if not db_run:
            db_run = EvaluationRecorder.create_run(
                db=db,
                run_id=run_uuid,
                dataset_version=dataset_version,
                dataset_hash=metadata.dataset_hash,
                config_dict=full_config,
                config_hash=repro_metadata.get("configuration_hash"),
                git_commit=repro_metadata["git_commit"],
            )

        # 2. Save tasks
        tasks_dicts = [item.model_dump() for item in items]
        EvaluationRecorder.save_tasks(db=db, run_id=run_uuid, tasks=tasks_dicts)

        completed_count = 0
        failed_count = 0
        executed_results: List[EvaluationResultItemSchema] = []

        # 3. Execute tasks
        for item in items:
            try:
                res_item = TaskExecutor.execute_task(db=db, task=item, config=config)
                EvaluationRecorder.save_result(db=db, run_id=run_uuid, item=res_item)
                executed_results.append(res_item)

                if res_item.completion_success:
                    completed_count += 1
                else:
                    failed_count += 1
            except Exception as e:
                logger.error(f"[EvaluationRunner] Task {item.task_id} failed: {str(e)}")
                failed_count += 1

        # 4. Calculate metrics
        metrics = MetricsEngine.calculate_metrics(executed_results)
        EvaluationRecorder.save_metrics(db=db, run_id=run_uuid, metrics=metrics)

        # 5. Run Baselines if enabled
        baseline_metrics = []
        if run_baselines:
            try:
                baseline_metrics = BaselineRunner.run_baselines(db=db, tasks=items, config=config)
            except Exception as e:
                logger.error(f"[EvaluationRunner] Baseline execution failed: {str(e)}")

        # 6. Run Ablations if enabled
        ablation_metrics = []
        if run_ablations:
            try:
                ablation_metrics = AblationRunner.run_ablations(db=db, tasks=items, base_config=config)
            except Exception as e:
                logger.error(f"[EvaluationRunner] Ablation execution failed: {str(e)}")

        # 7. Update run status in DB
        final_status = "completed" if completed_count > 0 else "failed"
        db_run = EvaluationRecorder.update_run_status(
            db=db,
            run_id=run_uuid,
            status=final_status,
            task_count=len(items),
            completed_count=completed_count,
            failed_count=failed_count,
        )

        # Store baselines & ablations in configuration_json metadata.
        #
        # This must REPLACE the dict, not mutate it in place. `configuration_json`
        # is a plain Column(JSON), not MutableDict.as_mutable(JSON), so
        # SQLAlchemy's change detection never sees in-place key assignment and
        # the commit silently writes nothing. That is why every historical run
        # artifact recorded "baselines": null despite the baseline runner having
        # executed: the results were computed and then dropped.
        db_run.configuration_json = {
            **(db_run.configuration_json or {}),
            "baselines": [b.model_dump() for b in baseline_metrics],
            "ablations": [a.model_dump() for a in ablation_metrics],
        }
        db.commit()

        # 8. Generate filesystem artifacts
        #
        # A failure here used to be logged (str(e), no traceback) and
        # otherwise swallowed entirely: the run still reported "completed"
        # with no trace that evaluation_run.json/evaluation_results.csv were
        # missing or incomplete. That is exactly how the privacy_confidence
        # AttributeError bug went unnoticed -- evaluation_results.csv was
        # never generated for any run since that field was added, and
        # nothing said so (smoke-eval audit, 2026-09-20). artifact_error is
        # now persisted on the run and returned in the response so a failure
        # here is impossible to miss without deliberately ignoring both.
        artifact_error: Optional[str] = None
        try:
            cls.save_artifacts(db=db, run_id=run_uuid)
        except Exception as e:
            logger.exception(f"[EvaluationRunner] Artifact generation error for run {run_uuid}")
            artifact_error = str(e)
            db_run.artifact_error = artifact_error
            db.commit()

        return EvaluationRunResponseSchema(
            run_id=run_uuid,
            status=final_status,
            dataset_version=dataset_version,
            dataset_hash=metadata.dataset_hash,
            started_at=db_run.started_at,
            completed_at=db_run.completed_at,
            task_count=len(items),
            completed_count=completed_count,
            failed_count=failed_count,
            configuration_json=db_run.configuration_json,
            git_commit=db_run.git_commit,
            created_at=db_run.created_at,
            metrics=metrics,
            baselines=baseline_metrics,
            ablations=ablation_metrics,
            artifact_error=artifact_error,
        )

    @classmethod
    def save_artifacts(cls, db: Session, run_id: str) -> str:
        run_dir = os.path.join(cls.ARTIFACTS_DIR, run_id)
        os.makedirs(run_dir, exist_ok=True)

        json_data = EvaluationExporter.export_json(db=db, run_id=run_id)
        with open(os.path.join(run_dir, "evaluation_run.json"), "w", encoding="utf-8") as f:
            json.dump(json_data, f, indent=2)

        csv_data = EvaluationExporter.export_csv(db=db, run_id=run_id)
        with open(os.path.join(run_dir, "evaluation_results.csv"), "w", encoding="utf-8") as f:
            f.write(csv_data)

        # Charts (Phase 14) live in their own subdirectory, kept separate
        # from the raw JSON/CSV siblings above. A chart-generation failure
        # (e.g. matplotlib misconfigured) must not mask successful raw
        # artifact generation, which is why this is a soft failure logged on
        # the run rather than re-raised into the caller's try/except, which
        # would incorrectly report artifact_error even though the raw
        # artifacts above saved fine.
        try:
            charts_dir = os.path.join(run_dir, "charts")
            EvaluationExporter.export_charts(db=db, run_id=run_id, output_dir=charts_dir)
        except Exception:
            logger.exception(f"[EvaluationRunner] Chart generation failed for run {run_id} (raw artifacts unaffected)")

        return run_dir
