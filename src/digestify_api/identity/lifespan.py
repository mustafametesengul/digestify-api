from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from digestify_api.identity.models import SignInCode, User
from digestify_api.identity.service import Accounts
from digestify_api.identity.token import TokenGenerator, TokenVerifier
from digestify_api.infrastructure.database import create_client
from digestify_api.infrastructure.email_delivery import create_email_client

DATABASE = "identity"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    token_generator = TokenGenerator()
    token_verifier = TokenVerifier()

    async with create_client() as client, create_email_client() as email_client:
        await client.ensure_database(DATABASE)
        database = client.get_database(DATABASE, User, SignInCode)

        service = Accounts(
            database=database,
            email_sender=email_client,
            token_generator=token_generator,
            token_verifier=token_verifier,
        )

        app.state.identity_service = service
        app.state.token_verifier = token_verifier
        yield
