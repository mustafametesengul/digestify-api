from typing import Literal

from digestify_api.infrastructure.couchdb import Document


class ProjectionCheckpoint(Document):
    """Resume token for a `_changes` consumer.

    Stores the opaque CouchDB update sequence (`last_seq`) of the most recently
    *processed* change. On restart the consumer resumes from here, so a crash
    costs at most a re-processing of already-applied changes (which the
    projection makes idempotent) — never a skipped one.
    """

    type: Literal["projection_checkpoint"] = "projection_checkpoint"
    last_seq: str

    @classmethod
    def start(cls, id: str) -> "ProjectionCheckpoint":
        # "0" means "replay from the beginning", which backfills every existing
        # identity user the first time the consumer runs.
        return cls(id=id, last_seq="0")
