from fastapi import HTTPException, status


class Unauthenticated(HTTPException):
    def __init__(self, detail: str = "Could not validate credentials") -> None:
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )


class Unauthorized(HTTPException):
    def __init__(
        self,
        detail: str = "You do not have permission to perform this action",
    ) -> None:
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
        )


class AccountNotFound(HTTPException):
    def __init__(
        self,
        detail: str = "The specified account does not exist",
    ) -> None:
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=detail,
        )
