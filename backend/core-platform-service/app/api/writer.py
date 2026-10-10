import time
from typing import Optional
from fastapi import APIRouter
from pydantic import BaseModel
from app.agents.base import AgentContext
from app.agents.writing_agent import WritingRequest, writing_agent
from app.utils.response import success_response, error_response

router = APIRouter(
    prefix="/writer",
    tags=["AI Writer"],
)


class WriterRequest(BaseModel):
    type: str  # "email", "rewrite", "reply"
    instruction: Optional[str] = ""
    text: Optional[str] = ""
    email: Optional[str] = ""


@router.post("/generate")
def generate_writer_content(request: WriterRequest):
    start_time = time.time()
    try:
        req_type = request.type.lower()
        kind = req_type if req_type in ("email", "rewrite", "reply") else "generate"

        agent_result = writing_agent.run(
            AgentContext(owner_id="anonymous"),
            WritingRequest(
                kind=kind,
                instruction=request.instruction,
                text=request.text,
                email=request.email,
            ),
        )
        result = agent_result.output.body

        return success_response(
            data={"result": result, "type": req_type},
            message=f"Writer {req_type} generated successfully",
            start_time=start_time,
        )
    except Exception as e:
        return error_response(
            message="Request failed",
            exc=e,
            start_time=start_time,
            status_code=500,
        )
