from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from digestify_api.news.topic import TopicDetails


def test_daily_schedule_uses_local_timezone():
    details = TopicDetails.model_validate(
        {
            "name": " Science ",
            "description": "New discoveries",
            "language": "en-US",
            "schedule": {"time": "09:00", "timezone": "Europe/Istanbul"},
        }
    )
    now = datetime(2026, 9, 13, tzinfo=UTC)
    assert details.name == "Science"
    assert details.schedule.next_after(now, now) == now.replace(hour=6)


@pytest.mark.parametrize(
    "change",
    [
        {"name": " "},
        {"description": ""},
        {"schedule": {"time": "09:00", "timezone": "Invalid/Zone"}},
        {"schedule": {"time": "09:00+03:00", "timezone": "UTC"}},
        {"user_id": "client-controlled"},
    ],
)
def test_rejects_invalid_details(change):
    with pytest.raises(ValidationError):
        TopicDetails.model_validate(
            {
                "name": "Science",
                "description": "New discoveries",
                "language": "en-US",
                "schedule": {"time": "09:00", "timezone": "UTC"},
                **change,
            }
        )
