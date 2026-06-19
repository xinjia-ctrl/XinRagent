import re
from typing import Any

STOP_WORDS = {
    "and",
    "the",
    "for",
    "with",
    "this",
    "that",
    "from",
    "into",
    "about",
    "一个",
    "我们",
    "可以",
    "以及",
    "通过",
    "进行",
    "支持",
}

TOKEN_PATTERN = re.compile(r"[\u4e00-\u9fff]{2,}|[A-Za-z][A-Za-z0-9_+-]{2,}|\d{2,}")


def extract_keywords(text: str, limit: int = 8) -> list[str]:
    counts: dict[str, int] = {}
    for raw_token in TOKEN_PATTERN.findall(text):
        token = raw_token.lower() if raw_token.isascii() else raw_token
        if token in STOP_WORDS:
            continue
        counts[token] = counts.get(token, 0) + 1
    return [token for token, _ in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:limit]]


def first_heading_or_line(text: str, fallback: str = "") -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        return stripped.lstrip("#").strip()[:120]
    return fallback


def summarize_text(text: str, max_length: int = 200) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= max_length:
        return normalized
    return normalized[: max_length - 3].rstrip() + "..."


def json_safe_metadata(value: Any) -> Any:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, list):
        return [json_safe_metadata(item) for item in value]
    if isinstance(value, dict):
        return {str(key): json_safe_metadata(item) for key, item in value.items()}
    return str(value)


def scalar_document_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in metadata.items():
        if key in {"credentials"}:
            continue
        if isinstance(value, str | int | float | bool) or value is None:
            result[key] = value
        elif isinstance(value, list) and all(isinstance(item, str | int | float | bool) for item in value):
            result[key] = value
    return result
