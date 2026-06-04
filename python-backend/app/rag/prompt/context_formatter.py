from app.rag.retrieve import RetrievedChunk
from app.mcp import MCPResponse


class ContextFormatter:
    def format_chunks(self, chunks: list[RetrievedChunk]) -> str:
        if not chunks:
            return ""

        sections = []
        for index, chunk in enumerate(chunks, start=1):
            source = chunk.metadata.get("docName") or chunk.metadata.get("docId") or chunk.id
            sections.append(
                f"[{index}] 来源: {source}\n"
                f"相关度: {chunk.score:.4f}\n"
                f"内容: {chunk.content}",
            )
        return "\n\n".join(sections)

    def format_mcp_context(self, responses: list[MCPResponse]) -> str:
        if not responses:
            return ""

        sections = []
        for index, response in enumerate(responses, start=1):
            if response.success and response.content:
                sections.append(f"[工具结果 {index}] {response.tool_id}\n{response.content}")
                continue
            sections.append(f"[工具结果 {index}] {response.tool_id}\n调用失败: {response.error_message}")
        return "\n\n".join(sections)
