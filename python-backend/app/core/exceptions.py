from fastapi import HTTPException, status


class RagentException(Exception):
    def __init__(self, message: str, code: str = "500") -> None:
        self.message = message
        self.code = code
        super().__init__(message)


def bad_request(message: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)
