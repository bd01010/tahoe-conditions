"""Generic HTML adapter that looks for common patterns."""

import logging
import re
from typing import Optional

from bs4 import BeautifulSoup

from tahoe_conditions.adapters.base import BaseAdapter, ParseResult
from tahoe_conditions.models import Operations, Snow

logger = logging.getLogger(__name__)


class GenericHTMLAdapter(BaseAdapter):
    """
    Generic adapter that searches for common patterns in HTML.

    This works for some simpler resort pages but may miss data
    on JS-heavy sites.
    """

    def parse(self, html: str) -> ParseResult:
        """Parse HTML looking for common condition patterns."""
        result = ParseResult()
        ops = Operations()
        snow = Snow()

        try:
            soup = BeautifulSoup(html, "lxml")

            # Remove script/style elements
            for tag in soup(["script", "style", "noscript"]):
                tag.decompose()

            text = soup.get_text(separator=" ")
            text_lower = text.lower()

            # Look for lift counts
            lifts = self._find_lift_counts(text, soup)
            if lifts:
                ops.lifts_open, ops.lifts_total = lifts

            # Look for trail counts
            trails = self._find_trail_counts(text, soup)
            if trails:
                ops.trails_open, ops.trails_total = trails

            # Look for open/closed status
            ops.open_flag = self._find_open_status(text_lower, ops)

            # Look for snow data
            snow.new_snow_24h_in = self._find_new_snow(text, "24")
            snow.new_snow_48h_in = self._find_new_snow(text, "48")
            snow.base_depth_in = self._find_base_depth(text)
            snow.season_total_in = self._find_season_total(text)
            snow.surface = self._find_surface(text)

            result.ops = ops
            result.snow = snow

            # Consider it a success if we got at least some data
            if ops.lifts_open is not None or snow.new_snow_24h_in is not None:
                result.success = True
            else:
                result.error = "Could not extract meaningful data"

        except Exception as e:
            logger.exception("Generic parser error")
            result.error = str(e)

        return result

    def _find_lift_counts(self, text: str, soup: BeautifulSoup) -> Optional[tuple[int, int]]:
        """Find lift open/total counts."""
        patterns = [
            r"(\d+)\s*/\s*(\d+)\s*lifts?",
            r"lifts?\s*[:\s]*(\d+)\s*/\s*(\d+)",
            r"(\d+)\s+of\s+(\d+)\s+lifts?",
            r"lifts?\s+open[:\s]*(\d+)\s*/\s*(\d+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return int(match.group(1)), int(match.group(2))

        return None

    def _find_trail_counts(self, text: str, soup: BeautifulSoup) -> Optional[tuple[int, int]]:
        """Find trail open/total counts."""
        patterns = [
            r"(\d+)\s*/\s*(\d+)\s*(?:trails?|runs?)",
            r"(?:trails?|runs?)\s*[:\s]*(\d+)\s*/\s*(\d+)",
            r"(\d+)\s+of\s+(\d+)\s+(?:trails?|runs?)",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return int(match.group(1)), int(match.group(2))

        return None

    def _find_open_status(self, text_lower: str, ops: Operations) -> Optional[bool]:
        """Determine if resort is open."""
        # Check explicit markers
        if "resort closed" in text_lower or "mountain closed" in text_lower:
            return False
        if "resort open" in text_lower or "mountain open" in text_lower:
            return True

        # Infer from lift counts
        if ops.lifts_open is not None:
            return ops.lifts_open > 0

        return None

    def _find_new_snow(self, text: str, hours: str) -> Optional[float]:
        """Find new snow for given hour period."""
        patterns = [
            rf"(\d+(?:\.\d+)?)[\"″]\s*(?:in\s+)?(?:last\s+)?{hours}\s*(?:hr|hour)",
            rf"{hours}\s*(?:hr|hour)[s]?\s*[:\s]*(\d+(?:\.\d+)?)[\"″]?",
            rf"new\s+snow\s*\(?{hours}[h]?\)?\s*[:\s]*(\d+(?:\.\d+)?)",
            rf"(\d+(?:\.\d+)?)\s*(?:in|inches?|\")\s*(?:in\s+)?{hours}\s*(?:hr|hour)",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return float(match.group(1))

        return None

    def _find_base_depth(self, text: str) -> Optional[float]:
        """Find base depth."""
        patterns = [
            r"base\s*(?:depth)?[:\s]*(\d+(?:\.\d+)?)\s*[-–]\s*(\d+(?:\.\d+)?)",
            r"base\s*(?:depth)?[:\s]*(\d+(?:\.\d+)?)[\"″]?\s*(?:in|inches?)?",
            r"(\d+(?:\.\d+)?)[\"″]?\s*base",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                if match.lastindex == 2:
                    # Range - return average
                    return (float(match.group(1)) + float(match.group(2))) / 2
                return float(match.group(1))

        return None

    def _find_season_total(self, text: str) -> Optional[float]:
        """Find season total snowfall."""
        patterns = [
            r"season\s*total[:\s]*(\d+(?:\.\d+)?)[\"″]?\s*(?:in|inches?)?",
            r"ytd[:\s]*(\d+(?:\.\d+)?)[\"″]?",
            r"(\d+(?:\.\d+)?)[\"″]?\s*(?:in|inches?)?\s*season",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return float(match.group(1))

        return None

    def _find_surface(self, text: str) -> Optional[str]:
        """Find surface conditions description."""
        patterns = [
            r"surface[:\s]+([A-Za-z\s,]+?)(?:\.|$|\n)",
            r"conditions?[:\s]+([A-Za-z\s,]+?)(?:\.|$|\n)",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                surface = self.clean_text(match.group(1))
                if len(surface) < 50:  # Reasonable length
                    return surface

        return None
