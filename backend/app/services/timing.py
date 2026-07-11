import time
from typing import Awaitable, TypeVar

T = TypeVar("T")


async def timed(coro: Awaitable[T]) -> tuple[T, int]:
    start = time.perf_counter()
    result = await coro
    elapsed_ms = round((time.perf_counter() - start) * 1000)
    return result, elapsed_ms
