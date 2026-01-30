from digestify_api.core import DBManager, DBSettings

_db: DBManager | None = None


def init_db(settings: DBSettings) -> DBManager:
    global _db
    _db = DBManager(settings)
    return _db


def get_db() -> DBManager:
    global _db
    if _db is None:
        raise RuntimeError("Database service is not initialized.")
    return _db
