import json
from collections.abc import AsyncIterator

import httpx

from app.infra_ai.chat.base import ChatChunk, ChatClient, ChatMessage, ChatRequest, ChatResponse
from app.infra_ai.model_target import ModelTarget


class OpenAIStyleChatClient(ChatClient):
    def __init__(self, target: ModelTarget, timeout: float = 60.0) -> None:
        self.target = target
        self.timeout = timeout

    async def complete(self, request: ChatRequest) -> ChatResponse:
        payload = self._build_payload(request, stream=False)
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                self._chat_url(),
                headers=self._headers(),
                json=payload,
            )
            response.raise_for_status()
            body = response.json()

        choice = body.get("choices", [{}])[0]
        message = choice.get("message", {})
        return ChatResponse(
            content=message.get("content", ""),
            model=body.get("model", request.model),
            raw=body,
        )

    async def stream(self, request: ChatRequest) -> AsyncIterator[ChatChunk]:
        payload = self._build_payload(request, stream=True)
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream(
                "POST",
                self._chat_url(),
                headers=self._headers(),
                json=payload,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    chunk = self._parse_stream_line(line)
                    if chunk is not None:
                        yield chunk

    def _build_payload(self, request: ChatRequest, stream: bool) -> dict:
        payload = {
            "model": request.model,
            "messages": [self._message_to_dict(message) for message in request.messages],
            "temperature": request.temperature,
            "stream": stream,
        }
        payload.update(self.target.extra_body)
        if request.extra_body:
            payload.update(request.extra_body)
        return payload

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json", **self.target.extra_headers}
        if self.target.api_key:
            headers["Authorization"] = f"Bearer {self.target.api_key}"
        return headers

    def _chat_url(self) -> str:
        return f"{self.target.base_url.rstrip('/')}/{self.target.chat_path.lstrip('/')}"

    @staticmethod
    def _message_to_dict(message: ChatMessage) -> dict[str, str]:
        return {"role": message.role, "content": message.content}

    @staticmethod
    def _parse_stream_line(line: str) -> ChatChunk | None:
        if not line.startswith("data:"):
            return None

        data = line.removeprefix("data:").strip()
        if not data or data == "[DONE]":
            return None

        body = json.loads(data)
        choice = body.get("choices", [{}])[0]
        delta = choice.get("delta", {})
        return ChatChunk(
            delta=delta.get("content", ""),
            finish_reason=choice.get("finish_reason"),
            raw=body,
        )
