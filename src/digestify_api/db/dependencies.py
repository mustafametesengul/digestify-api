from digestify_api.db.service import DBService
from digestify_api.db.settings import DBSettings

_db: DBService | None = None


def init_db(settings: DBSettings) -> DBService:
    global _db
    _db = DBService(settings)
    return _db


def get_db() -> DBService:
    global _db
    if _db is None:
        raise RuntimeError("Database service is not initialized.")
    return _db
