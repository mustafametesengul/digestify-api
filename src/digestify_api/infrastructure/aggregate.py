from typing import Callable, Generic, TypeVar

from pydantic import BaseModel, TypeAdapter


class OptimisticConcurrencyError(Exception):
    pass


T = TypeVar("T", bound=BaseModel)
E = TypeVar("E", bound=BaseModel)


class Aggregate(Generic[T]):
    def __init__(self, id: str) -> None:
        self._id = id
        self._state: T | None = None
        self._pending_events: list[BaseModel] = []
        self._mutators: dict[type[BaseModel], Callable[..., None]] = {}

    def _add_mutator(self, event_type: type[E], mutator: Callable[[E], None]) -> None:
        self._mutators[event_type] = mutator

    def apply(self, event: BaseModel) -> None:
        """Route the event to the registered mutator."""
        event_type = type(event)
        if event_type not in self._mutators:
            raise ValueError(f"No mutator registered for event type {event_type}.")
        mutator_func = self._mutators[event_type]
        mutator_func(self, event)

    def apply_json(self, event_json: str) -> None:
        """Apply an event from its JSON representation."""
        for event_type, mutator_func in self._mutators.items():
            try:
                event = TypeAdapter(event_type).validate_json(event_json)
                mutator_func(self, event)
                return
            except Exception:
                continue
        raise ValueError("No matching event type found for the provided JSON.")

    def _publish(self, event: BaseModel) -> None:
        self._pending_events.append(event)
        self.apply(event)

    def _get_state(self) -> T:
        if self._state is None:
            raise ValueError("Aggregate state is not initialized.")
        return self._state.model_copy()

    def _set_state(self, state: T) -> None:
        if self._state is not None:
            raise ValueError("Aggregate state is already initialized.")
        self._state = state
