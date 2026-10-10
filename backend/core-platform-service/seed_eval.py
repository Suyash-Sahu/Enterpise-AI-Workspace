from app.db.session import SessionLocal
from app.evaluation.runner import EvaluationRunner
from app.evaluation.schemas import EvaluationConfigSchema

def run():
    db = SessionLocal()
    try:
        print("Executing fast evaluation run against PostgreSQL database...")
        config = EvaluationConfigSchema(dataset_version="amof_eval_v1")
        result = EvaluationRunner.start_run(
            db=db,
            dataset_version="amof_eval_v1",
            config=config,
            run_baselines=True,
            run_ablations=True,
        )
        print("Evaluation Run Completed Successfully!")
        print(f"Run ID: {result.run_id}")
        print(f"Status: {result.status}")
        print(f"Dataset Hash: {result.dataset_hash}")
        print(f"Task Count: {result.task_count}")
        print(f"Completed Tasks: {result.completed_count}")
        print(f"Metrics Count: {len(result.metrics)}")
    finally:
        db.close()

if __name__ == "__main__":
    run()
