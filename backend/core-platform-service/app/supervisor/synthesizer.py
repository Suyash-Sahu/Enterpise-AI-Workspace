import json
import logging
from sqlalchemy.orm import Session

from app.supervisor.context import SupervisorContext
from app.services.execution_manager import execution_manager
from app.schemas.execution import ExecutionRequest

logger = logging.getLogger(__name__)


class ResponseSynthesizer:

    def synthesize(
        self,
        db: Session,
        context: SupervisorContext,
        aggregated_data: dict,
        sources: list,
    ) -> tuple[str, str]:
        """
        Synthesizes grounded user answer via P5 Execution Manager text_generation (purpose="synthesis").
        Returns tuple of (answer_text, synthesis_execution_id).
        """
        # If single-step capability already produced a clean answer/summary, present it cleanly
        for step_id, data in aggregated_data.items():
            output = data.get("output", {})
            if isinstance(output, dict):
                if "answer" in output and output["answer"]:
                    return output["answer"], ""
                if "summary" in output and output["summary"]:
                    return output["summary"], ""
                if "generated_text" in output and output["generated_text"]:
                    return output["generated_text"], ""
                if "rows" in output and "explanation" in output:
                    rows = output.get("rows", [])
                    explanation = output.get("explanation", "")
                    return f"{explanation}\n\nQuery returned {len(rows)} matching record(s).", ""

        # Multi-step synthesis via P5 ➔ P6
        try:
            synthesis_prompt = (
                "You are an enterprise AI assistant synthesizing an answer for the user based strictly on completed step results.\n\n"
                f"User Question: {context.question}\n\n"
                f"Aggregated Step Context:\n{json.dumps(aggregated_data, indent=2, default=str)}\n\n"
                "Provide a clear, professional, and grounded final answer."
            )

            req = ExecutionRequest(
                task_type="text_generation",
                input={
                    "prompt": synthesis_prompt,
                    "purpose": "synthesis",
                },
                execution_mode=context.execution_mode,
                request_id=f"{context.request_id}_synth",
            )

            exec_res = execution_manager.execute(db=db, request=req, owner_id=context.owner_id)
            synth_exec_id = exec_res.execution_id

            if exec_res.result and "generated_text" in exec_res.result:
                return exec_res.result["generated_text"], synth_exec_id
        except Exception as e:
            logger.warning(f"Synthesis fallback trigger: {e}")

        return "Completed task execution successfully. See details below.", ""


response_synthesizer = ResponseSynthesizer()
