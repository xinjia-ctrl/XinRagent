import logging

from app.core.context import RequestContext, set_request_context, reset_request_context
from app.core.logging import RequestContextFilter


def test_request_context_filter_adds_request_id() -> None:
    token = set_request_context(RequestContext(request_id="log-request-id"))
    record = logging.LogRecord("test", logging.INFO, __file__, 1, "message", (), None)

    try:
        assert RequestContextFilter().filter(record) is True
        assert record.request_id == "log-request-id"
    finally:
        reset_request_context(token)
