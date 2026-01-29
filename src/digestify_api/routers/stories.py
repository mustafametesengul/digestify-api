from fastapi import APIRouter

stories_router = APIRouter(
    prefix="/stories",
    tags=["stories"],
)
