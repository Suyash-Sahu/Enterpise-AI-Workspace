import logging
import requests
from openai import OpenAI
from app.core.config import settings

logger = logging.getLogger(__name__)


class EmbeddingServiceError(Exception):
    pass


class EmbeddingService:

    def __init__(self):
        self.dim = settings.EMBEDDING_DIM
        self.provider = settings.EMBEDDING_PROVIDER
        self.model = settings.EMBEDDING_MODEL
        self.openrouter_key = settings.OPENROUTER_API_KEY
        self.ollama_base = settings.OLLAMA_BASE_URL
        
        self.client = None
        if self.provider in ["openai", "openrouter"] and self.openrouter_key and not self.openrouter_key.startswith("your_"):
            try:
                self.client = OpenAI(
                    api_key=self.openrouter_key,
                    base_url="https://openrouter.ai/api/v1",
                )
            except Exception:
                self.client = None

    def generate_embedding(self, text: str) -> list[float]:
        if not text:
            return [0.0] * self.dim

        # 1. Try OpenAI / OpenRouter embedding API
        if self.provider in ["openai", "openrouter"] and self.client:
            try:
                res = self.client.embeddings.create(
                    model=self.model if "embedding" in self.model else "text-embedding-3-small",
                    input=text,
                )
                emb = res.data[0].embedding
                if len(emb) == self.dim:
                    return emb
                elif len(emb) > 0:
                    raise EmbeddingServiceError(
                        f"Embedding dimension mismatch: API returned {len(emb)} dims, expected {self.dim} dims."
                    )
            except Exception as e:
                logger.warning(f"OpenAI/OpenRouter embedding API failed: {e}")

        # 2. Try Ollama embedding API
        if self.provider == "ollama" or not self.client:
            try:
                res = requests.post(
                    f"{self.ollama_base}/api/embeddings",
                    json={"model": self.model, "prompt": text},
                    timeout=15,
                )
                if res.status_code == 200:
                    data = res.json()
                    emb = data.get("embedding", [])
                    if len(emb) == self.dim:
                        return emb
                    elif len(emb) > 0:
                        raise EmbeddingServiceError(
                            f"Ollama embedding dimension mismatch: returned {len(emb)} dims, expected {self.dim} dims."
                        )
            except Exception as e:
                logger.warning(f"Ollama embedding API failed: {e}")

        raise EmbeddingServiceError(
            "Embedding provider unavailable. Please check OPENROUTER_API_KEY or local Ollama server connectivity."
        )

    def generate_embeddings_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.generate_embedding(t) for t in texts]


embedding_service = EmbeddingService()
