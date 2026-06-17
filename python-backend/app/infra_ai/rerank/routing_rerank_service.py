from collections.abc import Callable, Sequence

from app.infra_ai.model_target import ModelTarget
from app.infra_ai.rerank.base import RerankClient, RerankRequest, RerankResponse
from app.infra_ai.rerank.bailian_rerank_client import BaiLianRerankClient
from app.infra_ai.rerank.noop_rerank_client import NoopRerankClient
from app.infra_ai.routing_executor import ModelRoutingExecutor

RerankClientFactory = Callable[[ModelTarget], RerankClient]


class RoutingRerankService:
    def __init__(
        self,
        targets: Sequence[ModelTarget],
        executor: ModelRoutingExecutor | None = None,
        client_factory: RerankClientFactory | None = None,
    ) -> None:
        self.targets = list(targets)
        self.executor = executor or ModelRoutingExecutor()
        self.client_factory = client_factory or self._default_client

    async def rerank(self, request: RerankRequest) -> RerankResponse:
        async def operation(target: ModelTarget) -> RerankResponse:
            client = self.client_factory(target)
            routed_request = RerankRequest(
                query=request.query,
                documents=request.documents,
                model=target.model or request.model,
                top_n=request.top_n,
                extra_body=request.extra_body,
            )
            return await client.rerank(routed_request)

        return await self.executor.execute(self.targets, operation)

    @staticmethod
    def _default_client(target: ModelTarget) -> RerankClient:
        if target.provider == "bailian":
            return BaiLianRerankClient(target)
        return NoopRerankClient()
