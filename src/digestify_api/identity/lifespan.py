from contextlib import asynccontextmanager
from typing import AsyncIterator

import httpx
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from digestify_api.identity.dependencies import Context
from digestify_api.identity.email_delivery import ResendEmailSender
from digestify_api.identity.sign_in_code import SignInCode
from digestify_api.identity.token_generation import TokenGenerator
from digestify_api.identity.token_verification import TokenVerifier
from digestify_api.identity.user import User
from digestify_api.infrastructure.couchdb import CouchDBRepository, ensure_database

DATABASE = "identity"


class CouchDBSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        env_prefix="COUCHDB_",
    )

    url: str = Field(default="http://localhost:5984")
    user: str = Field(default="admin")
    password: SecretStr = Field(default=SecretStr("password"))


@asynccontextmanager
async def lifespan() -> AsyncIterator[Context]:
    token_generator = TokenGenerator()
    token_verifier = TokenVerifier()
    settings = CouchDBSettings()

    async with (
        httpx.AsyncClient(
            base_url=settings.url,
            auth=(settings.user, settings.password.get_secret_value()),
        ) as couch_client,
        httpx.AsyncClient() as email_client,
    ):
        await ensure_database(couch_client, DATABASE)

        users = CouchDBRepository(couch_client, DATABASE, User)
        sign_in_codes = CouchDBRepository(couch_client, DATABASE, SignInCode)

        context = Context(
            users=users,
            sign_in_codes=sign_in_codes,
            email_sender=ResendEmailSender(email_client),
            token_generator=token_generator,
            token_verifier=token_verifier,
        )

        yield context
