from app.infra_ai.chat import ChatMessage
from app.mcp import MCPResponse
from app.rag.intent import IntentMatch
from app.rag.prompt.context_formatter import ContextFormatter
from app.rag.retrieve import RetrievedChunk


class PromptService:
    def __init__(self, formatter: ContextFormatter | None = None) -> None:
        self.formatter = formatter or ContextFormatter()

    def build_messages(
        self,
        question: str,
        chunks: list[RetrievedChunk],
        history: list[ChatMessage] | None = None,
        rewritten_question: str | None = None,
        sub_questions: list[str] | None = None,
        intents: list[IntentMatch] | None = None,
        mcp_responses: list[MCPResponse] | None = None,
    ) -> list[ChatMessage]:
        system_prompt = "你是 Ragent Python 后端的 AI 助手。"
        if rewritten_question and rewritten_question != question:
            system_prompt += f"\n用户问题已重写为：{rewritten_question}"
        if sub_questions and len(sub_questions) > 1:
            system_prompt += "\n问题拆分：" + "；".join(sub_questions)
        if intents:
            system_prompt += "\n命中意图：" + "、".join(
                f"{intent.name}({intent.confidence:.2f})" for intent in intents
            )

        context = self.formatter.format_chunks(chunks)
        if context:
            system_prompt += (
                "\n请优先基于以下知识库上下文回答；如果上下文不足，明确说明无法从知识库确认。\n\n"
                f"{context}"
            )
        mcp_context = self.formatter.format_mcp_context(mcp_responses or [])
        if mcp_context:
            system_prompt += (
                "\n\n以下是 MCP 工具调用结果，请和知识库上下文一起综合回答。\n\n"
                f"{mcp_context}"
            )

        messages = [ChatMessage(role="system", content=system_prompt)]
        messages.extend(history or [])
        messages.append(ChatMessage(role="user", content=rewritten_question or question))
        return messages
