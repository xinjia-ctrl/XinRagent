"""检索后处理模块。"""

from app.rag.retrieve.postprocessors.base import RetrievalPostProcessor
from app.rag.retrieve.postprocessors.deduplication import DeduplicationPostProcessor

__all__ = ["DeduplicationPostProcessor", "RetrievalPostProcessor"]
