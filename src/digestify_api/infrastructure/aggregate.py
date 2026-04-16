from typing import Any, Callable, Generic, TypeVar

from pydantic import BaseModel, TypeAdapter


class OptimisticConcurrencyError(Exception):
    pass


S = TypeVar("S", bound=BaseModel)
E = TypeVar("E", bound=BaseModel)


class Aggregate(Generic[S]):
    def __init__(self, id: str) -> None:
        self._id = id
        self._state: S | None = None
        self._pending_events: list[BaseModel] = []
        self._mutators: dict[type[BaseModel], Callable[[Any], None]] = {}

    def _add_mutator(self, event_type: type[E], mutator: Callable[[E], None]) -> None:
        self._mutators[event_type] = mutator

    def apply(self, event: BaseModel) -> None:
        """Route the event to the registered mutator."""
        event_type = type(event)
        if event_type not in self._mutators:
            raise ValueError(f"No mutator registered for event type {event_type}.")
        mutator_func = self._mutators[event_type]
        mutator_func(event)

    def apply_json(self, event_json: str) -> None:
        """Apply an event from its JSON representation."""
        for event_type, mutator_func in self._mutators.items():
            try:
                event = TypeAdapter(event_type).validate_json(event_json)
                mutator_func(event)
                return
            except Exception:
                continue
        raise ValueError("No matching event type found for the provided JSON.")

    def _publish(self, event: BaseModel) -> None:
        self._pending_events.append(event)
        self.apply(event)
