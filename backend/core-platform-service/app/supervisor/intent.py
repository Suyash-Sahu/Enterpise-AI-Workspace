import json
import logging
from typing import Optional
from sqlalchemy.orm import Session

from app.schemas.supervisor import IntentResult
from app.supervisor.context import SupervisorContext
from app.services.execution_manager import execution_manager
from app.schemas.execution import ExecutionRequest

logger = logging.getLogger(__name__)


class IntentAnalyzer:

    def analyze(self, db: Session, context: SupervisorContext) -> tuple[IntentResult, Optional[str]]:
        """
        Classifies user query into structured IntentResult.
        Returns tuple of (IntentResult, intent_execution_id).
        """
        q = context.question.lower().strip()

        # Rule-based heuristics for deterministic queries
        if any(kw in q for kw in ["how many", "count of", "total documents", "list tables", "database", "sql"]):
            return IntentResult(
                capability="database_query",
                confidence=0.95,
                reason="Query contains database/SQL counting keywords",
            ), None

        if any(kw in q for kw in ["write", "create a", "draft an email", "generate code", "compose"]):
            return IntentResult(
                capability="text_generation",
                confidence=0.94,
                reason="Query requests text or email composition",
            ), None

        if any(kw in q for kw in ["how does", "explain", "what is", "according to documents"]):
            return IntentResult(
                capability="rag_answer",
                confidence=0.90,
                reason="Query requests grounded document explanation",
            ), None

        if any(kw in q for kw in ["search", "find documents", "lookup", "rag search"]):
            return IntentResult(
                capability="rag_search",
                confidence=0.92,
                reason="Query requests document search retrieval",
            ), None

        if any(kw in q for kw in ["summarize", "summary of", "bullet points"]):
            return IntentResult(
                capability="document_summary",
                confidence=0.91,
                reason="Query requests document summary",
            ), None

        # LLM Classification via P5 Execution Manager (purpose="intent_classification")
        try:
            intent_prompt = (
                "You are an AI intent classifier for an enterprise workspace. Classify the user query into exactly ONE of these capabilities:\n"
                "- rag_search: Search/retrieve raw document passages\n"
                "- rag_answer: Answer question grounded in document context\n"
                "- database_query: Query database counts or structured data\n"
                "- text_generation: Generate new text/code or write emails\n"
                "- document_summary: Summarize document content\n\n"
                "Return JSON ONLY in this format:\n"
                '{"capability": "rag_answer", "confidence": 0.88, "reason": "Explanation"}\n\n'
                f"User Query: {context.question}"
            )

            req = ExecutionRequest(
                task_type="text_generation",
                input={
                    "prompt": intent_prompt,
                    "purpose": "intent_classification",
                },
                execution_mode=context.execution_mode,
                request_id=f"{context.request_id}_intent",
            )

            exec_res = execution_manager.execute(db=db, request=req, owner_id=context.owner_id)
            intent_exec_id = exec_res.execution_id

            if exec_res.result and "generated_text" in exec_res.result:
                raw_text = exec_res.result["generated_text"]
                # Parse JSON output
                clean_json = raw_text.strip()
                if "```json" in clean_json:
                    clean_json = clean_json.split("```json")[1].split("```")[0].strip()
                elif "```" in clean_json:
                    clean_json = clean_json.split("```")[1].split("```")[0].strip()

                parsed = json.loads(clean_json)
                cap = parsed.get("capability", "text_generation")
                conf = float(parsed.get("confidence", 0.80))
                reason = parsed.get("reason", "LLM Intent Classifier")

                if cap in ("rag_search", "rag_answer", "database_query", "text_generation", "document_summary"):
                    return IntentResult(capability=cap, confidence=conf, reason=reason), intent_exec_id

        except Exception as e:
            logger.warning(f"LLM intent classification fallback trigger: {e}")

        # Default fallback intent
        return IntentResult(
            capability="text_generation",
            confidence=0.85,
            reason="Default general text generation fallback",
        ), None


intent_analyzer = IntentAnalyzer()
