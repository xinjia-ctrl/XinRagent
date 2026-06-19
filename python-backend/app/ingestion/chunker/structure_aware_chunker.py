import re


class StructureAwareChunker:
    def __init__(
        self,
        target_chars: int = 1400,
        max_chars: int = 1800,
        min_chars: int = 600,
        overlap_chars: int = 0,
        separator: str = "\n\n",
    ) -> None:
        self.target_chars = target_chars
        self.max_chars = max_chars
        self.min_chars = min_chars
        self.overlap_chars = overlap_chars
        self.separator = separator or "\n\n"

    def split(self, text: str) -> list[str]:
        normalized = text.strip()
        if not normalized:
            return []

        blocks = self._split_blocks(normalized)
        chunks: list[str] = []
        current = ""
        for block in blocks:
            for piece in self._split_large_block(block):
                candidate = self._join(current, piece)
                if current and len(candidate) > self.max_chars and len(current) >= self.min_chars:
                    chunks.append(current.strip())
                    current = self._overlap_prefix(current)
                    candidate = self._join(current, piece)
                current = candidate

        if current.strip():
            chunks.append(current.strip())
        return chunks

    def _split_blocks(self, text: str) -> list[str]:
        custom_separator = self.separator.strip()
        if custom_separator and custom_separator in text:
            return [block.strip() for block in text.split(custom_separator) if block.strip()]

        blocks: list[str] = []
        current: list[str] = []
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                if current:
                    blocks.append("\n".join(current).strip())
                    current = []
                continue
            if self._is_heading(stripped) and current:
                blocks.append("\n".join(current).strip())
                current = []
            current.append(line)
        if current:
            blocks.append("\n".join(current).strip())
        return blocks or [text]

    def _split_large_block(self, block: str) -> list[str]:
        if len(block) <= self.max_chars:
            return [block]

        sentences = [item.strip() for item in re.split(r"(?<=[。！？.!?])\s+", block) if item.strip()]
        if len(sentences) <= 1:
            return self._fixed_split(block)

        pieces: list[str] = []
        current = ""
        for sentence in sentences:
            candidate = self._join(current, sentence, separator=" ")
            if current and len(candidate) > self.max_chars:
                pieces.append(current)
                current = sentence
                continue
            current = candidate
        if current:
            pieces.append(current)
        return pieces

    def _fixed_split(self, text: str) -> list[str]:
        step = max(self.max_chars - self.overlap_chars, 1)
        return [text[index : index + self.max_chars].strip() for index in range(0, len(text), step)]

    def _overlap_prefix(self, chunk: str) -> str:
        if self.overlap_chars <= 0:
            return ""
        return chunk[-self.overlap_chars :].strip()

    def _join(self, left: str, right: str, separator: str | None = None) -> str:
        if not left:
            return right.strip()
        if not right:
            return left.strip()
        return f"{left.strip()}{separator or self.separator}{right.strip()}"

    @staticmethod
    def _is_heading(line: str) -> bool:
        return bool(re.match(r"^#{1,6}\s+\S+", line))
