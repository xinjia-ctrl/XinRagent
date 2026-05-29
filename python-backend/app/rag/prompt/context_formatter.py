from app.rag.retrieve import RetrievedChunk


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
