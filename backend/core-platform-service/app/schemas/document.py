from pydantic import BaseModel


class DocumentSummaryRequest(BaseModel):

    file_id: str


class DocumentQuestionRequest(BaseModel):

    file_id: str

    question: str


class DocumentExtractionRequest(BaseModel):

    file_id: str

    fields: list[str]


class DocumentCompareRequest(BaseModel):

    first_file_id: str

    second_file_id: str