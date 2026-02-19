import asyncio

import bcrypt


async def verify_password(plain_password: str, hashed_password: str) -> bool:
    return await asyncio.to_thread(
        bcrypt.checkpw,
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8"),
    )


async def hash_password(password: str) -> str:
    hashed_bytes = await asyncio.to_thread(
        bcrypt.hashpw,
        password.encode("utf-8"),
        bcrypt.gensalt(),
    )
    return hashed_bytes.decode("utf-8")
