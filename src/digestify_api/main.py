import uvicorn

from digestify_api.settings import get_settings, init_settings


def main() -> None:
    init_settings()
    settings = get_settings()

    uvicorn.run(
        "digestify_api.app:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
    )


if __name__ == "__main__":
    main()
