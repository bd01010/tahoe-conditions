"""Placeholder adapter for sites that require headless browser."""

import logging

from tahoe_conditions.adapters.base import BaseAdapter, ParseResult

logger = logging.getLogger(__name__)


class PlaceholderHeadlessAdapter(BaseAdapter):
    """
    Placeholder for resorts that require JavaScript rendering.

    This adapter always returns needs_headless=True and no data,
    signaling that future implementation with Playwright is needed.
    """

    def parse(self, html: str) -> ParseResult:
        """Return placeholder result indicating headless browser needed."""
        logger.info("Placeholder adapter: this resort requires headless browser")
        return ParseResult(
            success=False,
            needs_headless=True,
            error="This resort requires JavaScript rendering (headless browser)"
        )
