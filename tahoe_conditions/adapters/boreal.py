"""Adapter for Boreal Mountain Resort and Soda Springs."""

import logging
import re

from bs4 import BeautifulSoup

from tahoe_conditions.adapters.base import BaseAdapter, ParseResult
from tahoe_conditions.models import Operations, Snow

logger = logging.getLogger(__name__)


class BorealAdapter(BaseAdapter):
    """
    Parser for Boreal Mountain Resort and Soda Springs.

    Both resorts use Gatsby/React SPAs. After JS rendering,
    look for lift/trail counts and snow data in rendered text.
    """

    def parse(self, html: str) -> ParseResult:
        result = ParseResult()
        ops = Operations()
        snow = Snow()

        try:
            soup = BeautifulSoup(html, "lxml")
            text = soup.get_text(separator=" ")
            text = re.sub(r"\s+", " ", text)

            # === LIFTS ===
            # Boreal typically shows "X/Y Lifts" or "Lifts Open: X of Y"
            lift_patterns = [
                r"(\d+)\s*/\s*(\d+)\s*lifts?",
                r"lifts?\s*(?:open)?[:\s]*(\d+)\s*(?:of|/)\s*(\d+)",
                r"(\d+)\s*lifts?\s*open",  # Just open count
            ]
            for pattern in lift_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    ops.lifts_open = int(match.group(1))
                    if match.lastindex >= 2:
                        ops.lifts_total = int(match.group(2))
                    break

            # === TRAILS ===
            trail_patterns = [
                r"(\d+)\s*/\s*(\d+)\s*(?:trails?|runs?|terrain)",
                r"(?:trails?|runs?|terrain)\s*(?:open)?[:\s]*(\d+)\s*(?:of|/)\s*(\d+)",
                r"(\d+)\s*(?:trails?|runs?)\s*open",
            ]
            for pattern in trail_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    ops.trails_open = int(match.group(1))
                    if match.lastindex >= 2:
                        ops.trails_total = int(match.group(2))
                    break

            # === SNOW DATA ===
            # New snow (24h, 48h, or generic "new snow")
            new_snow_patterns = [
                r"(?:24\s*(?:hr|hour)|new\s*snow|overnight|last\s*24)[:\s]*(\d+(?:\.\d+)?)\s*(?:in|\")",
                r"(\d+(?:\.\d+)?)\s*(?:in|\")?\s*(?:new|fresh)",
            ]
            for pattern in new_snow_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    snow.new_snow_24h_in = float(match.group(1))
                    break

            # 48h snow
            snow_48h_match = re.search(
                r"(?:48\s*(?:hr|hour)|last\s*48)[:\s]*(\d+(?:\.\d+)?)\s*(?:in|\")",
                text, re.IGNORECASE
            )
            if snow_48h_match:
                snow.new_snow_48h_in = float(snow_48h_match.group(1))

            # Base depth
            base_patterns = [
                r"(?:base|mid\s*mtn|summit)[:\s]*(\d+(?:\.\d+)?)\s*(?:in|\")",
                r"snow\s*(?:depth|base)[:\s]*(\d+(?:\.\d+)?)",
            ]
            for pattern in base_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    snow.base_depth_in = float(match.group(1))
                    break

            # Season total
            season_match = re.search(
                r"(?:season|ytd|year)[:\s]*(\d+(?:\.\d+)?)\s*(?:in|\")",
                text, re.IGNORECASE
            )
            if season_match:
                snow.season_total_in = float(season_match.group(1))

            # === OPEN STATUS ===
            # Check for explicit open/closed status
            if "closed for season" in text.lower() or "not operating" in text.lower():
                ops.open_flag = False
            elif ops.lifts_open is not None:
                ops.open_flag = ops.lifts_open > 0
            elif ops.trails_open is not None:
                ops.open_flag = ops.trails_open > 0
            else:
                ops.open_flag = None

            result.ops = ops
            result.snow = snow
            result.success = (
                ops.lifts_open is not None or
                ops.trails_open is not None or
                snow.base_depth_in is not None
            )

            if not result.success:
                result.error = "Could not extract conditions data from rendered page"

        except Exception as e:
            logger.exception("Boreal parser error")
            result.error = str(e)

        return result
