import pytest
from unittest.mock import patch, MagicMock
from app.rag.embeddings import EmbeddingService, EmbeddingServiceError
from app.core.config import settings


def test_embedding_service_provider_ollama():
    """Verify that when EMBEDDING_PROVIDER is ollama, EmbeddingService uses settings.EMBEDDING_MODEL and does not initialize OpenAI client."""
    with patch("app.rag.embeddings.settings") as mock_settings:
        mock_settings.EMBEDDING_PROVIDER = "ollama"
        mock_settings.EMBEDDING_MODEL = "nomic-embed-text"
        mock_settings.EMBEDDING_DIM = 768
        mock_settings.OPENROUTER_API_KEY = "sk-or-v1-dummykey"
        mock_settings.OLLAMA_BASE_URL = "http://localhost:11434"

        service = EmbeddingService()
        assert service.provider == "ollama"
        assert service.model == "nomic-embed-text"
        assert service.client is None


def test_embedding_service_ollama_embedding_generation():
    """Verify generate_embedding calls Ollama endpoint with correct model when provider is ollama."""
    with patch("app.rag.embeddings.settings") as mock_settings, \
         patch("app.rag.embeddings.requests.post") as mock_post:
        
        mock_settings.EMBEDDING_PROVIDER = "ollama"
        mock_settings.EMBEDDING_MODEL = "nomic-embed-text"
        mock_settings.EMBEDDING_DIM = 768
        mock_settings.OPENROUTER_API_KEY = "sk-or-v1-dummykey"
        mock_settings.OLLAMA_BASE_URL = "http://localhost:11434"

        fake_vector = [0.1] * 768
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"embedding": fake_vector}
        mock_post.return_value = mock_response

        service = EmbeddingService()
        result = service.generate_embedding("Test prompt")

        assert len(result) == 768
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args.kwargs
        assert call_kwargs["json"]["model"] == "nomic-embed-text"
        assert call_kwargs["json"]["prompt"] == "Test prompt"
