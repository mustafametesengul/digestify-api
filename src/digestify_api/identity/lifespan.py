from contextlib import asynccontextmanager
from typing import AsyncIterator

from pymongo import AsyncMongoClient

from digestify_api.identity.dependencies import Context
from digestify_api.identity.token_generation import TokenGenerator
from digestify_api.identity.token_verification import TokenVerifier
from digestify_api.identity.user import User, UserRepository

from digestify_api.infrastructure import create_message_broker


@asynccontextmanager
async def lifespan() -> AsyncIterator[Context]:
    mongo_url = "mongodb://localhost:27017/db?directConnection=true"
    async with (
        AsyncMongoClient(mongo_url, uuidRepresentation="standard") as mongo_client,
        create_message_broker() as message_broker,
    ):
        token_generator = TokenGenerator()
        token_verifier = TokenVerifier()

        db = mongo_client["identity"]
        users_collection = db["users"]

        user_repository = UserRepository(
            User,
            users_collection,
            message_broker,
        )

        context = Context(
            user_repository=user_repository,
            token_generator=token_generator,
            token_verifier=token_verifier,
            message_broker=message_broker,
        )

        yield context
