from app.infra_ai.chat import ChatMessage
from app.rag.prompt.context_formatter import ContextFormatter
from app.rag.retrieve import RetrievedChunk


class PromptService:
    def __init__(self, formatter: ContextFormatter | None = None) -> None:
        self.formatter = formatter or ContextFormatter()

    def build_messages(self, question: str, chunks: list[RetrievedChunk]) -> list[ChatMessage]:
        system_prompt = "你是 Ragent Python 后端的 AI 助手。"
        context = self.formatter.format_chunks(chunks)
        if context:
            system_prompt += (
                "\n请优先基于以下知识库上下文回答；如果上下文不足，明确说明无法从知识库确认。\n\n"
                f"{context}"
            )

        return [
            ChatMessage(role="system", content=system_prompt),
            ChatMessage(role="user", content=question),
        ]
