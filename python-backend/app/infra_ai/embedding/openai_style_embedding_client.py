import httpx

from app.infra_ai.embedding.base import EmbeddingClient, EmbeddingRequest, EmbeddingResponse
from app.infra_ai.model_target import ModelTarget


class OpenAIStyleEmbeddingClient(EmbeddingClient):
    def __init__(self, target: ModelTarget, timeout: float = 60.0) -> None:
        self.target = target
        self.timeout = timeout

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        payload = {
            "model": request.model,
            "input": list(request.texts),
        }
        if request.extra_body:
            payload.update(request.extra_body)

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                self._embedding_url(),
                headers=self._headers(),
                json=payload,
            )
            response.raise_for_status()
            body = response.json()

        vectors = [item.get("embedding", []) for item in body.get("data", [])]
        return EmbeddingResponse(
            vectors=vectors,
            model=body.get("model", request.model),
            raw=body,
        )

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json", **self.target.extra_headers}
        if self.target.api_key:
            headers["Authorization"] = f"Bearer {self.target.api_key}"
        return headers

    def _embedding_url(self) -> str:
        return f"{self.target.base_url.rstrip('/')}/v1/embeddings"
