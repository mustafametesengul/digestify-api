from dataclasses import dataclass

from fastapi import Request

from digestify_api.identity import TokenVerifier
from digestify_api.infrastructure import Database


@dataclass
class Context:
    database: Database
    token_verifier: TokenVerifier


def get_context(request: Request) -> Context:
    return request.app.state.news_context
