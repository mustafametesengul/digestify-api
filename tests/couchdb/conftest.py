from collections.abc import AsyncIterator

import httpx
import pytest

from digestify_api.couchdb import Database


class FakeServer:
    """Replays queued responses in order and records every request."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self._responses: list[httpx.Response] = []

    def enqueue(self, response: httpx.Response) -> None:
        self._responses.append(response)

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        assert self._responses, f"unexpected request: {request.method} {request.url}"
        return self._responses.pop(0)

    @property
    def request(self) -> httpx.Request:
        assert len(self.requests) == 1, f"expected one request, saw {self.requests}"
        return self.requests[0]


@pytest.fixture
def server() -> FakeServer:
    return FakeServer()


@pytest.fixture
async def database(server: FakeServer) -> AsyncIterator[Database]:
    async with httpx.AsyncClient(
        base_url="http://couch",
        transport=httpx.MockTransport(server),
    ) as client:
        yield Database(client, "things")
