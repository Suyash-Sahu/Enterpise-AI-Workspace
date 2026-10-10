import json
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import relationship
from app.db.database import Base
from app.core.config import settings

try:
    from pgvector.sqlalchemy import Vector
    HAS_PGVECTOR = True
except ImportError:
    HAS_PGVECTOR = False


class IngestedDocument(Base):
    __tablename__ = "ingested_documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    file_id = Column(String(255), nullable=False)
    source = Column(String(255), nullable=False)
    owner_id = Column(String(255), index=True, nullable=False, default="1")
    chunk_count = Column(Integer, nullable=False, default=0)
    ingested_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("owner_id", "file_id", name="uq_owner_file"),
    )


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id = Column(Integer, ForeignKey("ingested_documents.id", ondelete="CASCADE"), nullable=False, index=True)
    owner_id = Column(String(255), index=True, nullable=False, default="1")
    file_id = Column(String(255), index=True, nullable=False)
    source = Column(String(255), nullable=False)
    chunk_index = Column(Integer, nullable=False, default=0)
    text = Column(Text, nullable=False)
    page = Column(Integer, nullable=True, default=1)
    metadata_json = Column(Text, nullable=True, default="{}")

    if HAS_PGVECTOR:
        embedding = Column(Vector(settings.EMBEDDING_DIM), nullable=True)
    else:
        embedding = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    document = relationship("IngestedDocument", back_populates="chunks")

    __table_args__ = (
        Index("idx_chunks_owner_file", "owner_id", "file_id"),
    )

    def set_metadata(self, meta_dict: dict):
        self.metadata_json = json.dumps(meta_dict)

    def get_metadata(self) -> dict:
        if not self.metadata_json:
            return {}
        try:
            return json.loads(self.metadata_json)
        except Exception:
            return {}

    def set_vector(self, vector_list: list[float]):
        if HAS_PGVECTOR:
            self.embedding = vector_list
        else:
            self.embedding = json.dumps(vector_list)

    def get_vector(self) -> list[float]:
        if not self.embedding:
            return []
        if isinstance(self.embedding, list):
            return self.embedding
        try:
            return json.loads(self.embedding)
        except Exception:
            return []
