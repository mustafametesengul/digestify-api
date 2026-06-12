from contextlib import asynccontextmanager
from typing import AsyncIterator

import httpx
import nats
from nats.js.api import StreamConfig
from nats.js.client import JetStreamContext
from nats.js.errors import BadRequestError
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from rillo.nats import NATSRepository

from digestify_api.identity.dependencies import Context
from digestify_api.identity.email_delivery import ResendEmailSender
from digestify_api.identity.sign_in_code import SignInCode
from digestify_api.identity.token_generation import TokenGenerator
from digestify_api.identity.token_verification import TokenVerifier
from digestify_api.identity.user import User


class DSNSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        env_prefix="NATS_",
    )

    host: str = Field(default="localhost")
    port: int = Field(default=4222)


async def _ensure_stream(js: JetStreamContext) -> None:
    config = StreamConfig(
        name="identity",
        subjects=["users.*", "sign-in-codes.*"],
    )
    try:
        await js.add_stream(config)
    except BadRequestError:
        await js.update_stream(config)


@asynccontextmanager
async def lifespan() -> AsyncIterator[Context]:
    token_generator = TokenGenerator()
    token_verifier = TokenVerifier()
    settings = DSNSettings()

    nc = await nats.connect(f"nats://{settings.host}:{settings.port}")
    try:
        async with httpx.AsyncClient() as http_client:
            js = nc.jetstream()
            await _ensure_stream(js)

            users = NATSRepository[User](
                js,
                "identity",
                "users",
            )

            sign_in_codes = NATSRepository[SignInCode](
                js,
                "identity",
                "sign-in-codes",
            )

            context = Context(
                users=users,
                sign_in_codes=sign_in_codes,
                email_sender=ResendEmailSender(http_client),
                token_generator=token_generator,
                token_verifier=token_verifier,
            )

            yield context
    finally:
        await nc.close()
