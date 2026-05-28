from collections.abc import Callable, Sequence

from app.infra_ai.embedding.base import EmbeddingClient, EmbeddingRequest, EmbeddingResponse
from app.infra_ai.embedding.openai_style_embedding_client import OpenAIStyleEmbeddingClient
from app.infra_ai.model_target import ModelTarget
from app.infra_ai.routing_executor import ModelRoutingExecutor

EmbeddingClientFactory = Callable[[ModelTarget], EmbeddingClient]


class RoutingEmbeddingService:
    def __init__(
        self,
        targets: Sequence[ModelTarget],
        executor: ModelRoutingExecutor | None = None,
        client_factory: EmbeddingClientFactory = OpenAIStyleEmbeddingClient,
    ) -> None:
        self.targets = list(targets)
        self.executor = executor or ModelRoutingExecutor()
        self.client_factory = client_factory

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        async def operation(target: ModelTarget) -> EmbeddingResponse:
            client = self.client_factory(target)
            routed_request = EmbeddingRequest(
                texts=request.texts,
                model=target.model or request.model,
                extra_body=request.extra_body,
            )
            return await client.embed(routed_request)

        return await self.executor.execute(self.targets, operation)
