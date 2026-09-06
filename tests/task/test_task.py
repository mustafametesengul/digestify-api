from datetime import UTC, datetime, time, timedelta

import pytest
from pydantic import ValidationError

from digestify_api.tasks.task import DailySchedule, IntervalSchedule, LostLease, Task

NOW = datetime(2026, 1, 1, tzinfo=UTC)
LEASE = timedelta(minutes=1)


def make_task(**overrides) -> Task:
    return Task.model_validate(
        {
            "id": "task:example",
            "kind": "example",
            "partition_key": "user:1",
            "bucket": 0,
            "scheduled_at": NOW,
            "available_at": NOW,
            "created_at": NOW,
            "updated_at": NOW,
            **overrides,
        }
    )


def test_stale_worker_cannot_finish_or_renew_reclaimed_task() -> None:
    task = make_task()
    assert task.claim("first", NOW, LEASE)
    first_token = task.claim_token
    assert first_token is not None
    key = task.idempotency_key
    assert not task.claim("second", NOW, LEASE)
    assert task.claim("second", NOW + LEASE, LEASE)
    assert task.idempotency_key == key
    assert task.claim_token != first_token
    with pytest.raises(LostLease):
        task.finish(first_token, NOW + LEASE)
    with pytest.raises(LostLease):
        task.renew(first_token, NOW + LEASE, LEASE)


def test_one_time_success_is_terminal() -> None:
    task = make_task()
    assert task.claim("worker", NOW, LEASE)
    assert task.claim_token is not None
    task.finish(task.claim_token, NOW, result={"sent": True})
    assert task.status == "succeeded"
    assert task.last_result == {"sent": True}
    assert task.succeeded_runs == 1
    assert not task.claim("worker", NOW + LEASE, LEASE)


def test_retry_keeps_occurrence_and_stops_at_limit() -> None:
    task = make_task(max_attempts=2)
    key = task.idempotency_key
    for attempt in range(2):
        now = NOW + attempt * task.retry_delay
        assert task.claim("worker", now, LEASE)
        assert task.claim_token is not None
        task.finish(task.claim_token, now, error="unavailable")
        assert task.idempotency_key == key
    assert task.status == "failed"
    assert task.failed_runs == 1
    assert task.attempts == 2


def test_crashed_final_attempt_is_not_run_again() -> None:
    task = make_task(max_attempts=1)
    assert task.claim("worker", NOW, LEASE)
    assert not task.claim("replacement", NOW + LEASE, LEASE)
    assert task.status == "failed"


def test_cancellation_invalidates_claim() -> None:
    task = make_task()
    task.claim("worker", NOW, LEASE)
    token = task.claim_token
    assert token is not None
    task.cancel(NOW)
    with pytest.raises(LostLease):
        task.finish(token, NOW)
    assert not task.claim("worker", NOW + LEASE, LEASE)


def test_recurring_task_skips_missed_slots_without_drifting() -> None:
    task = make_task(schedule=IntervalSchedule(every=timedelta(minutes=10)))
    now = NOW + timedelta(minutes=35)
    task.claim("worker", now, LEASE)
    assert task.claim_token is not None
    task.finish(task.claim_token, now)
    assert task.status == "pending"
    assert task.scheduled_at == NOW + timedelta(minutes=40)
    assert task.occurrence == 2
    assert task.attempts == 0


def test_failed_recurring_occurrence_advances() -> None:
    task = make_task(max_attempts=1, schedule=IntervalSchedule(every=LEASE))
    task.claim("worker", NOW, LEASE)
    assert task.claim_token is not None
    task.finish(task.claim_token, NOW, error="failed")
    assert task.status == "pending"
    assert task.failed_runs == 1
    assert task.occurrence == 2


def test_future_task_and_retry_are_not_claimable() -> None:
    task = make_task(available_at=NOW + LEASE)
    assert not task.claim("worker", NOW, LEASE)


@pytest.mark.parametrize("field", ["scheduled_at", "available_at", "created_at"])
def test_naive_timestamps_rejected(field: str) -> None:
    with pytest.raises(ValidationError):
        make_task(**{field: datetime(2026, 1, 1)})


@pytest.mark.parametrize("every", [timedelta(0), timedelta(seconds=-1)])
def test_invalid_interval_rejected(every: timedelta) -> None:
    with pytest.raises(ValidationError):
        IntervalSchedule(every=every)


def test_daily_dst_gap_moves_forward() -> None:
    schedule = DailySchedule(time=time(2, 30), timezone="America/New_York")
    now = datetime(2026, 3, 8, 5, tzinfo=UTC)
    assert schedule.next_after(now, now) == datetime(2026, 3, 8, 7, 30, tzinfo=UTC)


def test_daily_dst_fold_runs_only_first_occurrence() -> None:
    schedule = DailySchedule(time=time(1, 30), timezone="America/New_York")
    now = datetime(2026, 11, 1, 5, 30, tzinfo=UTC)
    assert schedule.next_after(now, now) == datetime(2026, 11, 2, 6, 30, tzinfo=UTC)


def test_daily_schedule_uses_local_date() -> None:
    schedule = DailySchedule(time=time(23), timezone="America/Los_Angeles")
    now = datetime(2026, 1, 2, 3, tzinfo=UTC)
    assert schedule.next_after(now, now) == datetime(2026, 1, 2, 7, tzinfo=UTC)


@pytest.mark.parametrize(
    "values",
    [
        {"time": "12:00+01:00", "timezone": "UTC"},
        {"time": "12:00", "timezone": "unknown"},
    ],
)
def test_invalid_daily_schedule_rejected(values) -> None:
    with pytest.raises(ValidationError):
        DailySchedule.model_validate(values)
