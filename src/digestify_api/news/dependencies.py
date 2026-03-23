from dataclasses import dataclass

from fastapi import Request

from digestify_api.infrastructure import Database


@dataclass
class Context:
    database: Database


def get_context(request: Request) -> Context:
    return request.app.state.news_context
