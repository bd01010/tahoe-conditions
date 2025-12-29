"""Adapter for Mt Rose Ski Tahoe."""

import logging
import re
from typing import Optional

from bs4 import BeautifulSoup

from tahoe_conditions.adapters.base import BaseAdapter, ParseResult
from tahoe_conditions.models import Operations, Snow

logger = logging.getLogger(__name__)


class MtRoseAdapter(BaseAdapter):
    """
    Parser for Mt Rose Ski Tahoe's conditions page.

    Structure:
    - Lift status section lists each lift with status
    - Snow data shows ranges like "47-58""
    - Trails listed by area
    """

    # Known lifts at Mt Rose
    LIFT_NAMES = [
        "Northwest Express",
        "Zephyr Express",
        "Lakeview Express",
        "Wizard",
        "Magic",
        "Galena",
        "Chuter",
        "Blazing Zephyr",
    ]

    def parse(self, html: str) -> ParseResult:
        result = ParseResult()
        ops = Operations()
        snow = Snow()

        try:
            soup = BeautifulSoup(html, "lxml")

            # === LIFTS ===
            # Find the lift-status section
            lift_section = soup.find(class_="lift-status")
            if lift_section:
                lift_text = lift_section.get_text(separator=" ")
                lift_text = re.sub(r"\s+", " ", lift_text)
                ops.lifts_open, ops.lifts_total = self._count_lifts(lift_text)
            else:
                # Fallback to full page search
                text = soup.get_text(separator=" ")
                text = re.sub(r"\s+", " ", text)
                ops.lifts_open, ops.lifts_total = self._count_lifts(text)

            # === TRAILS ===
            # Count trails from the trail status sections
            ops.trails_open, ops.trails_total = self._count_trails(soup)

            # === SNOW DATA ===
            text = soup.get_text(separator=" ")
            text = re.sub(r"\s+", " ", text)

            # New Snow - ranges like "47-58""
            snow.new_snow_24h_in = self._parse_range(text, r"new\s*snow[:\s]*(\d+)[-–]?(\d+)?[\"″]")
            snow.base_depth_in = self._parse_range(text, r"base\s*(?:depth)?[:\s]*(\d+)[-–]?(\d+)?[\"″]")
            snow.season_total_in = self._parse_range(text, r"season\s*(?:total)?[:\s]*(\d+)[-–]?(\d+)?[\"″]")

            # Storm total as 48h proxy
            storm = self._parse_range(text, r"storm\s*(?:total)?[:\s]*(\d+)[-–]?(\d+)?[\"″]")
            if storm:
                snow.new_snow_48h_in = storm

            # === OPEN STATUS ===
            if ops.lifts_open is not None and ops.lifts_open > 0:
                ops.open_flag = True
            elif "closed" in text.lower() and "chutes" not in text.lower()[:text.lower().find("closed")+20]:
                # Check if "closed" refers to the mountain, not just chutes
                ops.open_flag = False
            else:
                ops.open_flag = ops.lifts_open is not None and ops.lifts_open > 0

            result.ops = ops
            result.snow = snow
            result.success = True

        except Exception as e:
            logger.exception("MtRose parser error")
            result.error = str(e)

        return result

    def _count_lifts(self, text: str) -> tuple[Optional[int], Optional[int]]:
        """Count open and total lifts from text."""
        lifts_open = 0
        lifts_total = 0

        for lift_name in self.LIFT_NAMES:
            # Look for the lift name followed by status
            pattern = rf"{re.escape(lift_name)}\s+(\w+(?:\s+\w+)*)"
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                lifts_total += 1
                status = match.group(1).lower()
                # "Scheduled to open" = will be open = count as open
                if "scheduled" in status or "open" in status:
                    lifts_open += 1
                # "Closed" = not open

        if lifts_total == 0:
            return None, None
        return lifts_open, lifts_total

    def _count_trails(self, soup: BeautifulSoup) -> tuple[Optional[int], Optional[int]]:
        """Count open and total trails.

        Mt Rose doesn't publish explicit trail counts - they show terrain
        percentage open instead (e.g., "90% of All Terrain Available").
        Return None since we can't get accurate counts.
        """
        # Look for "X / Y trails" or similar pattern first
        text = soup.get_text(separator=" ")
        text = re.sub(r"\s+", " ", text)

        # Try to find explicit trail counts
        match = re.search(r"(\d+)\s*/\s*(\d+)\s*(?:trails?|runs?)", text, re.IGNORECASE)
        if match:
            return int(match.group(1)), int(match.group(2))

        # Mt Rose doesn't publish explicit counts
        return None, None

    def _parse_range(self, text: str, pattern: str) -> Optional[float]:
        """Parse a value that might be a range like '47-58'."""
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            low = float(match.group(1))
            high_str = match.group(2) if match.lastindex >= 2 else None
            if high_str:
                high = float(high_str)
                return (low + high) / 2
            return low
        return None
