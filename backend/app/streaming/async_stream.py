"""Bridge a blocking sync generator (Ollama/Groq streaming SDKs) into the
asyncio event loop without buffering the whole stream first."""
from __future__ import annotations

import asyncio
from typing import AsyncIterator, Callable, Iterator, TypeVar

T = TypeVar("T")


async def async_iter_sync(gen_factory: Callable[[], Iterator[T]]) -> AsyncIterator[T]:
    """Run `gen_factory()` in a thread; yield each produced item to the caller.

    Items cross the thread/loop boundary via an unbounded `asyncio.Queue` fed
    by `loop.call_soon_threadsafe`. Exceptions inside the generator are
    re-raised in the consumer.

    Caveat: if the async consumer is cancelled mid-stream, the producer
    thread continues until the underlying generator returns or its I/O is
    torn down. Phase B.5 adds explicit cancellation via `gen.close()`.
    """
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()

    def produce() -> None:
        try:
            for item in gen_factory():
                loop.call_soon_threadsafe(queue.put_nowait, ("item", item))
        except Exception as e:
            loop.call_soon_threadsafe(queue.put_nowait, ("error", e))
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, ("done", None))

    future = loop.run_in_executor(None, produce)
    try:
        while True:
            kind, val = await queue.get()
            if kind == "done":
                break
            if kind == "error":
                raise val
            yield val
    finally:
        if not future.done():
            try:
                await asyncio.wait_for(asyncio.shield(future), timeout=5.0)
            except (asyncio.TimeoutError, Exception):
                pass
