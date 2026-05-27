"""BrowserManager: manages Playwright browser lifecycle."""
from typing import Optional


class BrowserManager:
    """Manages a Playwright browser instance. Lazy start, close on workflow end."""

    def __init__(self, headless: bool = False, browser_type: str = "chromium",
                 user_data_dir: Optional[str] = None):
        self.headless = headless
        self.browser_type = browser_type  # chromium / firefox / webkit
        self.user_data_dir = user_data_dir
        self._playwright = None
        self._browser = None
        self._context = None  # BrowserContext
        self._page = None     # current active Page

    def ensure_started(self):
        """Lazy start: first call launches browser, subsequent calls are no-ops."""
        if self._browser is not None:
            return
        from playwright.sync_api import sync_playwright
        self._playwright = sync_playwright().start()
        launcher = getattr(self._playwright, self.browser_type)
        launch_args = {"headless": self.headless}
        if self.user_data_dir:
            self._context = launcher.launch_persistent_context(
                self.user_data_dir, **launch_args
            )
            if self._context.pages:
                self._page = self._context.pages[0]
        else:
            self._browser = launcher.launch(**launch_args)
            self._context = self._browser.new_context()

    @property
    def page(self):
        """Get the current active page; creates one if none exists."""
        self.ensure_started()
        if self._page is None or self._page.is_closed():
            if self._context and self._context.pages:
                self._page = self._context.pages[0]
            else:
                self._page = self._context.new_page()
        return self._page

    def new_page(self):
        """Create a new tab and switch to it."""
        self.ensure_started()
        self._page = self._context.new_page()
        return self._page

    def close(self):
        """Close browser and playwright."""
        try:
            if self._context:
                self._context.close()
        except Exception:
            pass
        try:
            if self._browser:
                self._browser.close()
        except Exception:
            pass
        try:
            if self._playwright:
                self._playwright.stop()
        except Exception:
            pass
        self._page = None
        self._context = None
        self._browser = None
        self._playwright = None
