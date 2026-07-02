from __future__ import annotations

import asyncio
import logging
import random

from playwright.async_api import Browser, BrowserContext, Page, Playwright, async_playwright

logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36 Edg/123.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (iPad; CPU OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
]


def random_user_agent() -> str:
    return random.choice(USER_AGENTS)


class BrowserPool:
    """Manages a pool of reusable Playwright browser instances."""

    def __init__(self, pool_size: int = 2, headless: bool = True):
        self.pool_size = pool_size
        self.headless = headless
        self._playwright: Playwright | None = None
        self._browsers: list[Browser] = []
        self._available: asyncio.Queue[Browser] = asyncio.Queue()
        self._started = False
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        async with self._lock:
            if self._started:
                return
            self._playwright = await async_playwright().start()
            for _ in range(self.pool_size):
                browser = await self._playwright.chromium.launch(headless=self.headless)
                self._browsers.append(browser)
                await self._available.put(browser)
            self._started = True
            logger.info("Browser pool started with %d instances", self.pool_size)

    async def stop(self) -> None:
        async with self._lock:
            for browser in self._browsers:
                await browser.close()
            self._browsers.clear()
            if self._playwright:
                await self._playwright.stop()
                self._playwright = None
            self._started = False
            logger.info("Browser pool stopped")

    async def acquire(self) -> Browser:
        if not self._started:
            await self.start()
        return await self._available.get()

    async def release(self, browser: Browser) -> None:
        await self._available.put(browser)

    async def new_context(self, user_agent: str | None = None) -> tuple[Browser, BrowserContext]:
        browser = await self.acquire()
        context = await browser.new_context(user_agent=user_agent or random_user_agent())
        return browser, context

    async def new_page(self, user_agent: str | None = None) -> tuple[Browser, BrowserContext, Page]:
        browser, context = await self.new_context(user_agent=user_agent)
        page = await context.new_page()
        return browser, context, page

    async def release_context(self, browser: Browser, context: BrowserContext) -> None:
        await context.close()
        await self.release(browser)

    async def __aenter__(self) -> "BrowserPool":
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.stop()
