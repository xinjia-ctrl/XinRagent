from pathlib import Path
from urllib.parse import unquote, urlparse

import httpx

from app.core.exceptions import RagentException
from app.ingestion.context import IngestionContext
from app.ingestion.nodes.base import NodeConfig, NodeResult


class FetcherNode:
    node_type = "fetcher"

    def __init__(self, max_bytes: int = 50 * 1024 * 1024, timeout_seconds: float = 30.0) -> None:
        self.max_bytes = max_bytes
        self.timeout_seconds = timeout_seconds

    async def execute(self, context: IngestionContext, config: NodeConfig) -> NodeResult:
        options = config.options or {}
        source_type = self._normalize_source_type(
            str(options.get("sourceType") or context.source_type or context.metadata.get("sourceType") or "file"),
        )
        source_location = str(
            options.get("sourceLocation")
            or context.source_location
            or context.metadata.get("sourceLocation")
            or context.file_path,
        )
        context.source_type = source_type
        context.source_location = source_location

        if source_type == "url" or self._is_http_url(source_location):
            await self._fetch_url(context, source_location)
        elif source_type in {"file", "local"}:
            self._resolve_local_file(context, source_location)
        else:
            raise RagentException(message=f"不支持的数据源类型: {source_type}", code="INGESTION_SOURCE_UNSUPPORTED")

        self._hydrate_metadata(context)
        return NodeResult(
            node_type=self.node_type,
            success=True,
            message="fetched",
            output={
                "sourceType": context.source_type,
                "sourceLocation": context.source_location,
                "fileName": context.file_name,
                "fileType": context.file_type,
                "fileSize": context.metadata.get("fileSize"),
            },
        )

    async def _fetch_url(self, context: IngestionContext, source_location: str) -> None:
        parsed = urlparse(source_location)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise RagentException(message="URL 数据源地址无效", code="INGESTION_SOURCE_URL_INVALID")

        async with httpx.AsyncClient(timeout=self.timeout_seconds, follow_redirects=True) as client:
            response = await client.get(source_location)
        response.raise_for_status()
        content = response.content
        if len(content) > self.max_bytes:
            raise RagentException(message="URL 数据源文件超过大小限制", code="INGESTION_SOURCE_TOO_LARGE")

        suffix = self._infer_suffix(source_location, response.headers.get("content-type"))
        if suffix and context.file_path.suffix.lower() != suffix:
            context.file_path = context.file_path.with_suffix(suffix)
        if suffix and not Path(context.file_name).suffix:
            context.file_name = f"{context.file_name}{suffix}"
        context.file_path.parent.mkdir(parents=True, exist_ok=True)
        context.file_path.write_bytes(content)
        context.file_type = context.file_path.suffix.removeprefix(".").lower() or "txt"

    def _resolve_local_file(self, context: IngestionContext, source_location: str) -> None:
        if not context.file_path.exists() and source_location:
            candidate = Path(source_location)
            if candidate.exists():
                context.file_path = candidate
        if not context.file_path.exists():
            raise RagentException(message="入库源文件不存在", code="INGESTION_SOURCE_NOT_FOUND")
        if not context.file_type:
            context.file_type = context.file_path.suffix.removeprefix(".").lower()

    def _hydrate_metadata(self, context: IngestionContext) -> None:
        file_size = context.file_path.stat().st_size if context.file_path.exists() else 0
        context.metadata.update(
            {
                "sourceType": context.source_type,
                "sourceLocation": context.source_location or str(context.file_path),
                "fileName": context.file_name,
                "fileType": context.file_type,
                "fileSize": file_size,
            },
        )

    @staticmethod
    def _normalize_source_type(source_type: str) -> str:
        normalized = source_type.lower().strip()
        if normalized in {"http", "https"}:
            return "url"
        return normalized

    @staticmethod
    def _is_http_url(value: str) -> bool:
        parsed = urlparse(value)
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)

    @staticmethod
    def _infer_suffix(source_location: str, content_type: str | None) -> str:
        parsed_name = Path(unquote(urlparse(source_location).path)).name
        suffix = Path(parsed_name).suffix.lower()
        if suffix:
            return suffix

        normalized_type = (content_type or "").split(";")[0].strip().lower()
        return {
            "application/pdf": ".pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
            "text/markdown": ".md",
            "text/plain": ".txt",
            "text/html": ".txt",
        }.get(normalized_type, ".txt")
