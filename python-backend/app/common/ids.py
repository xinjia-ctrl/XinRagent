from uuid import uuid4


def generate_id() -> str:
    return uuid4().hex[:20]
