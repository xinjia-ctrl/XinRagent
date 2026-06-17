import httpx

from app.infra_ai.model_target import ModelTarget
from app.infra_ai.rerank.base import RerankClient, RerankDocument, RerankRequest, RerankResponse


class BaiLianRerankClient(RerankClient):
    def __init__(self, target: ModelTarget, timeout: float = 60.0) -> None:
        self.target = target
        self.timeout = timeout

    async def rerank(self, request: RerankRequest) -> RerankResponse:
        documents = self._deduplicate(list(request.documents))
        top_n = request.top_n or len(documents)
        if not documents or top_n <= 0:
            return RerankResponse(documents=[], model=request.model)
        if len(documents) <= top_n:
            return RerankResponse(documents=documents, model=request.model)

        payload = {
            "model": request.model,
            "input": {
                "query": request.query,
                "documents": [document.content or "" for document in documents],
            },
            "parameters": {
                "top_n": top_n,
                "return_documents": True,
            },
        }
        payload.update(self.target.extra_body)
        if request.extra_body:
            payload.update(request.extra_body)

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(self._rerank_url(), headers=self._headers(), json=payload)
            response.raise_for_status()
            body = response.json()

        return RerankResponse(
            documents=self._map_results(body, documents, top_n),
            model=body.get("model", request.model),
            raw=body,
        )

    def _rerank_url(self) -> str:
        return f"{self.target.base_url.rstrip('/')}/{self.target.rerank_path.lstrip('/')}"

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json", **self.target.extra_headers}
        if self.target.api_key:
            headers["Authorization"] = f"Bearer {self.target.api_key}"
        return headers

    @staticmethod
    def _deduplicate(documents: list[RerankDocument]) -> list[RerankDocument]:
        seen = set()
        deduplicated = []
        for document in documents:
            if document.id in seen:
                continue
            seen.add(document.id)
            deduplicated.append(document)
        return deduplicated

    @staticmethod
    def _map_results(body: dict, documents: list[RerankDocument], top_n: int) -> list[RerankDocument]:
        results = ((body.get("output") or {}).get("results") or [])
        ranked = []
        added_ids = set()
        for item in results:
            index = item.get("index") if isinstance(item, dict) else None
            if not isinstance(index, int) or index < 0 or index >= len(documents):
                continue
            source = documents[index]
            score = item.get("relevance_score", source.score)
            ranked.append(
                RerankDocument(
                    id=source.id,
                    content=source.content,
                    score=float(score),
                    metadata=source.metadata,
                ),
            )
            added_ids.add(source.id)
            if len(ranked) >= top_n:
                return ranked

        for document in documents:
            if document.id in added_ids:
                continue
            ranked.append(document)
            if len(ranked) >= top_n:
                break
        return ranked
