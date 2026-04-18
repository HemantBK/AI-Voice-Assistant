import asyncio

import pytest

from app.streaming.turn_manager import TurnManager


@pytest.mark.asyncio
async def test_cancel_before_complete():
    tm = TurnManager()
    hit = {"done": False}

    async def work():
        try:
            await asyncio.sleep(1.0)
            hit["done"] = True
        except asyncio.CancelledError:
            raise

    await tm.start(work())
    await asyncio.sleep(0.01)
    assert tm.is_busy()
    await tm.cancel()
    assert not tm.is_busy()
    assert hit["done"] is False


@pytest.mark.asyncio
async def test_start_replaces_prior_turn():
    tm = TurnManager()
    seen = []

    async def first():
        try:
            await asyncio.sleep(1.0)
            seen.append("first-done")
        except asyncio.CancelledError:
            seen.append("first-cancelled")
            raise

    async def second():
        seen.append("second-start")

    await tm.start(first())
    await asyncio.sleep(0.01)
    await tm.start(second())
    await tm.join()
    assert "first-cancelled" in seen
    assert "second-start" in seen
    assert "first-done" not in seen
