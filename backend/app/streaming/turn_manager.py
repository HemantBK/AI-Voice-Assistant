"""Per-connection turn orchestration. Ensures at most one in-flight turn
per WS and makes barge-in (B.5) a single `cancel()` call."""
from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Optional

logger = logging.getLogger(__name__)


class TurnManager:
    def __init__(self):
        self._task: Optional[asyncio.Task] = None
        self._cancelled = False

    def is_busy(self) -> bool:
        return self._task is not None and not self._task.done()

    async def start(self, coro: Awaitable[None]) -> None:
        """Start a new turn. If a previous turn is still running, cancel it
        first and wait for it to unwind before starting the new one."""
        await self.cancel()
        self._cancelled = False
        self._task = asyncio.create_task(self._wrap(coro))

    async def cancel(self) -> None:
        if self._task is None or self._task.done():
            return
        self._cancelled = True
        self._task.cancel()
        try:
            await self._task
        except (asyncio.CancelledError, Exception):
            pass
        self._task = None

    def cancelled(self) -> bool:
        return self._cancelled

    async def _wrap(self, coro: Awaitable[None]) -> None:
        try:
            await coro
        except asyncio.CancelledError:
            logger.info("turn cancelled")
            raise
        except Exception as e:
            logger.exception("turn failed: %s", e)

    async def join(self) -> None:
        if self._task is not None:
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
