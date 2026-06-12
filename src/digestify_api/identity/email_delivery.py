from typing import Protocol

import httpx
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class EmailDeliveryError(Exception):
    pass


class EmailSender(Protocol):
    async def send(self, to: str, subject: str, text: str) -> None: ...


class ResendSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        env_prefix="RESEND_",
    )

    api_key: SecretStr = Field(default=...)
    from_address: str = Field(default="Digestify <onboarding@resend.dev>")


class ResendEmailSender:
    def __init__(
        self,
        client: httpx.AsyncClient,
        settings: ResendSettings | None = None,
    ) -> None:
        self._client = client
        self._settings = settings or ResendSettings()

    async def send(self, to: str, subject: str, text: str) -> None:
        try:
            response = await self._client.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": (
                        f"Bearer {self._settings.api_key.get_secret_value()}"
                    ),
                },
                json={
                    "from": self._settings.from_address,
                    "to": [to],
                    "subject": subject,
                    "text": text,
                },
            )
        except httpx.HTTPError as e:
            raise EmailDeliveryError("Failed to reach Resend") from e
        if response.is_error:
            raise EmailDeliveryError(
                f"Resend returned {response.status_code}: {response.text}"
            )
