"""Adapter for Sierra-at-Tahoe ski resort."""

import logging
import re

from bs4 import BeautifulSoup

from tahoe_conditions.adapters.base import BaseAdapter, ParseResult
from tahoe_conditions.models import Operations, Snow

logger = logging.getLogger(__name__)


class SierraAtTahoeAdapter(BaseAdapter):
    """
    Parser for Sierra-at-Tahoe's conditions page.

    Server-rendered HTML with patterns like:
    - "10/14 Lifts Open"
    - "41/50 Runs Open"
    - "60" (summit), 35" (base)" for base depth
    """

    def parse(self, html: str) -> ParseResult:
        result = ParseResult()
        ops = Operations()
        snow = Snow()

        try:
            soup = BeautifulSoup(html, "lxml")
            text = soup.get_text(separator=" ")

            # Lifts: "10/14 Lifts Open" or "Lifts Open: 10/14"
            lift_match = re.search(
                r"(\d+)\s*/\s*(\d+)\s*lifts?\s*open|lifts?\s*open[:\s]*(\d+)\s*/\s*(\d+)",
                text, re.IGNORECASE
            )
            if lift_match:
                if lift_match.group(1):
                    ops.lifts_open = int(lift_match.group(1))
                    ops.lifts_total = int(lift_match.group(2))
                else:
                    ops.lifts_open = int(lift_match.group(3))
                    ops.lifts_total = int(lift_match.group(4))

            # Runs: "41/50 Runs Open"
            runs_match = re.search(
                r"(\d+)\s*/\s*(\d+)\s*runs?\s*open|runs?\s*open[:\s]*(\d+)\s*/\s*(\d+)",
                text, re.IGNORECASE
            )
            if runs_match:
                if runs_match.group(1):
                    ops.trails_open = int(runs_match.group(1))
                    ops.trails_total = int(runs_match.group(2))
                else:
                    ops.trails_open = int(runs_match.group(3))
                    ops.trails_total = int(runs_match.group(4))

            # 24-Hour Snowfall - look for various patterns
            snow_24_patterns = [
                r"24[- ]?hour[:\s]*(\d+(?:\.\d+)?)[\"']?\s*(?:in|inches?)?",
                r"(\d+(?:\.\d+)?)[\"']\s*(?:in\s+)?24[- ]?hour",
                r"last\s*24\s*hours?[:\s]*(\d+(?:\.\d+)?)",
            ]
            for pattern in snow_24_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    snow.new_snow_24h_in = float(match.group(1))
                    break

            # Base depth - summit/base pattern or just "base depth"
            base_patterns = [
                r"base\s*depth[:\s]*(\d+(?:\.\d+)?)",
                r"(\d+)[\"']\s*\(summit\)",  # Take summit value
                r"base[:\s]*(\d+)[\"']",
            ]
            for pattern in base_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    snow.base_depth_in = float(match.group(1))
                    break

            # Season/YTD total
            ytd_match = re.search(r"ytd[:\s]*(\d+)|season\s*total[:\s]*(\d+)", text, re.IGNORECASE)
            if ytd_match:
                val = ytd_match.group(1) or ytd_match.group(2)
                snow.season_total_in = float(val)

            # Open status
            ops.open_flag = ops.lifts_open is not None and ops.lifts_open > 0

            result.ops = ops
            result.snow = snow
            result.success = True

        except Exception as e:
            logger.exception("SierraAtTahoe parser error")
            result.error = str(e)

        return result
