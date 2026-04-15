from abc import ABC
from typing import Callable, Generic, TypeVar, get_type_hints, Any
from uuid import UUID, uuid4

from pydantic import BaseModel, TypeAdapter


class OptimisticConcurrencyError(Exception):
    pass


T = TypeVar("T", bound=BaseModel)


class Aggregate(ABC, Generic[T]):
    _mutators: dict[type[BaseModel], Callable] = {}

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        cls._mutators = getattr(cls, "_mutators", {}).copy()
        for name, method in cls.__dict__.items():
            if getattr(method, "__is_mutator__", False):
                hints = get_type_hints(method)
                for hint in hints.values():
                    # Find the parameter mapped to the Event (must subclass BaseModel)
                    if isinstance(hint, type) and issubclass(hint, BaseModel):
                        cls._mutators[hint] = method
                        break

    def __init__(self, id: int | UUID | str | None = None) -> None:
        self._id = id or uuid4()
        self._state_: T | None = None
        self._pending_events: list[BaseModel] = []

    def apply(self, event: BaseModel) -> None:
        """Route the event to the registered mutator."""
        mutator_func = self._mutators.get(type(event))
        if not mutator_func:
            raise NotImplementedError(
                f"No mutator registered for event type: {type(event).__name__}"
            )
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
        if self._state_ is None:
            raise ValueError("Aggregate state is not initialized.")
        return self._state_

    def _set_state(self, state: T) -> None:
        if self._state_ is not None:
            raise ValueError("Aggregate state is already initialized.")
        self._state_ = state


def mutator(func: Callable[[Any, Any], None]) -> Callable[[Any, Any], None]:
    setattr(func, "__is_mutator__", True)
    return func
