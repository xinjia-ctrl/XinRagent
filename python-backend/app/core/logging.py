import logging

from app.core.context import get_request_id


class RequestContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id()
        return True


def configure_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(
        level=level,
        format="%(levelname)s [%(name)s] [request_id=%(request_id)s] %(message)s",
    )
    logging.getLogger().addFilter(RequestContextFilter())
