import asyncio
import logging

logger = logging.getLogger(__name__)


async def run_with_retry(coro_factory, *, retry_delay: float = 5.0) -> None:
    while True:
        try:
            await coro_factory()
        except Exception:
            logger.exception("Source connection failed, retrying in %.1fs", retry_delay)
            await asyncio.sleep(retry_delay)
