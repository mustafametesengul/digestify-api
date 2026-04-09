import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from pymongo import AsyncMongoClient
from pymongo.errors import OperationFailure

from digestify_api.identity.dependencies import Context
from digestify_api.identity.token_generation import TokenGenerator
from digestify_api.identity.token_verification import TokenVerifier
from digestify_api.identity.user import UserRepository

from digestify_api.infrastructure import create_message_broker


@asynccontextmanager
async def lifespan() -> AsyncIterator[Context]:
    mongo_url = "mongodb://localhost:27017/db?directConnection=true"
    async with (
        AsyncMongoClient(mongo_url, uuidRepresentation="standard") as mongo_client,
        create_message_broker() as message_broker,
    ):
        try:
            await mongo_client.admin.command(
                "replSetInitiate",
                {"_id": "rs0", "members": [{"_id": 0, "host": "db:27017"}]},
            )
            logging.info("Replica set initialized.")
        except OperationFailure as e:
            if e.code == 23:  # AlreadyInitialized
                logging.info("Replica set already initialized.")
            else:
                logging.warning(f"Replica set initialization failed: {e}")

        token_generator = TokenGenerator()
        token_verifier = TokenVerifier()

        db = mongo_client["identity"]
        collection = db["users"]

        user_repository = UserRepository(collection)

        context = Context(
            user_repository=user_repository,
            token_generator=token_generator,
            token_verifier=token_verifier,
            message_broker=message_broker,
        )

        yield context
