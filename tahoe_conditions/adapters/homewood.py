"""Adapter for Homewood Mountain Resort."""

import logging
import re

from bs4 import BeautifulSoup

from tahoe_conditions.adapters.base import BaseAdapter, ParseResult
from tahoe_conditions.models import Operations, Snow

logger = logging.getLogger(__name__)


class HomewoodAdapter(BaseAdapter):
    """
    Parser for Homewood Mountain Resort's snow report page.

    Key patterns:
    - "Open Lifts" followed by "X/Y"
    - "Open Runs" followed by "X/Y"
    - Snow depths with base/summit values
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
            # Pattern: "Open Lifts" ... "X/Y"
            lift_match = re.search(
                r"Open\s+Lifts[^0-9]*(\d+)\s*/\s*(\d+)",
                text, re.IGNORECASE
            )
            if lift_match:
                ops.lifts_open = int(lift_match.group(1))
                ops.lifts_total = int(lift_match.group(2))

            # === TRAILS ===
            # Pattern: "Open Runs" ... "X/Y"
            trails_match = re.search(
                r"Open\s+Runs[^0-9]*(\d+)\s*/\s*(\d+)",
                text, re.IGNORECASE
            )
            if trails_match:
                ops.trails_open = int(trails_match.group(1))
                ops.trails_total = int(trails_match.group(2))

            # === SNOW DATA ===
            # Base depth - look for "Base: X.X in" or similar
            base_match = re.search(
                r"(?:Base|Summit)[:\s]*(\d+(?:\.\d+)?)\s*(?:in|\")",
                text, re.IGNORECASE
            )
            if base_match:
                snow.base_depth_in = float(base_match.group(1))

            # Season total
            season_match = re.search(
                r"Season\s*(?:Total)?[:\s]*(\d+(?:\.\d+)?)\s*(?:in|\")",
                text, re.IGNORECASE
            )
            if season_match:
                snow.season_total_in = float(season_match.group(1))

            # 24h/12h snow
            new_snow_match = re.search(
                r"(?:24\s*(?:hr|hour)|overnight)[:\s]*(\d+(?:\.\d+)?)\s*(?:in|\")",
                text, re.IGNORECASE
            )
            if new_snow_match:
                snow.new_snow_24h_in = float(new_snow_match.group(1))

            # === OPEN STATUS ===
            if ops.lifts_open is not None:
                ops.open_flag = ops.lifts_open > 0
            elif ops.trails_open is not None:
                ops.open_flag = ops.trails_open > 0
            else:
                ops.open_flag = None

            result.ops = ops
            result.snow = snow
            result.success = True

        except Exception as e:
            logger.exception("Homewood parser error")
            result.error = str(e)

        return result
