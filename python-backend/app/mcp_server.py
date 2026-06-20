import uvicorn

from app.core.config import settings
from app.mcp.server import create_mcp_app

mcp_app = create_mcp_app()


def main() -> None:
    uvicorn.run(
        "app.mcp_server:mcp_app",
        host=settings.mcp_host,
        port=settings.mcp_port,
        reload=False,
        factory=False,
    )


if __name__ == "__main__":
    main()
