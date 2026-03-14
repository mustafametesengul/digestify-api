from fastapi import APIRouter

from digestify_api import infrastructure
from digestify_api.identity.user import create_tables
from digestify_api.infrastructure import Channel

router = APIRouter()


events = Channel()


migrations = infrastructure.migrations + [create_tables]
