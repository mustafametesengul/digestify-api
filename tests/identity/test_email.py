import httpx
import pytest
from pydantic import SecretStr

from digestify_api.identity.email import (
    EmailClient,
    EmailClientSettings,
    EmailDeliveryError,
)


async def test_email_client_uses_finite_timeout() -> None:
    settings = EmailClientSettings(api_key=SecretStr("test-only"))
    async with EmailClient.create(settings) as email:
        assert email._client.timeout.read == 10.0


async def test_email_timeout_becomes_delivery_error() -> None:
    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("simulated timeout", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(timeout)) as client:
        email = EmailClient(client, EmailClientSettings(api_key=SecretStr("test-only")))
        with pytest.raises(EmailDeliveryError) as caught:
            await email.send("alice@example.com", "Sign in", "Test")
        assert isinstance(caught.value.__cause__, httpx.ReadTimeout)
