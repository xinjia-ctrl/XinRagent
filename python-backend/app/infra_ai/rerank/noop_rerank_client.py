from app.infra_ai.rerank.base import RerankClient, RerankRequest, RerankResponse


class NoopRerankClient(RerankClient):
    async def rerank(self, request: RerankRequest) -> RerankResponse:
        documents = list(request.documents)
        if request.top_n is not None:
            documents = documents[: request.top_n]
        return RerankResponse(documents=documents, model=request.model)
