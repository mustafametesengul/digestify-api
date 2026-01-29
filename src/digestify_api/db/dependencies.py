from digestify_api.db.service import DatabaseManager
from digestify_api.db.settings import DBSettings

_db: DatabaseManager | None = None


def init_db(settings: DBSettings) -> DatabaseManager:
    global _db
    _db = DatabaseManager(settings)
    return _db


def get_db() -> DatabaseManager:
    global _db
    if _db is None:
        raise RuntimeError("Database service is not initialized.")
    return _db
