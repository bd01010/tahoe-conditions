"""Adapter for Sugar Bowl ski resort."""

import logging
import re

from bs4 import BeautifulSoup

from tahoe_conditions.adapters.base import BaseAdapter, ParseResult
from tahoe_conditions.models import Operations, Snow

logger = logging.getLogger(__name__)


class SugarBowlAdapter(BaseAdapter):
    """
    Parser for Sugar Bowl's conditions page.

    Key patterns:
    - "X / Y Lifts Open" - lift counts
    - "X / Y Trails Open" - trail counts
    - "X" 24 Hr Snowfall" - new snow
    - "X" Year to Date" - season total
    """

    def parse(self, html: str) -> ParseResult:
        result = ParseResult()
        ops = Operations()
        snow = Snow()

        try:
            soup = BeautifulSoup(html, "lxml")
            text = soup.get_text(separator=" ")
            # Normalize whitespace
            text = re.sub(r"\s+", " ", text)

            # === LIFTS ===
            # Count individual lift statuses for scheduled info
            lift_counts = self._count_lift_statuses(soup)
            if lift_counts["total"] > 0:
                ops.lifts_open = lift_counts["open"]
                ops.lifts_scheduled = lift_counts["scheduled"]
                ops.lifts_total = lift_counts["total"]
            else:
                # Fallback: Pattern "X / Y Lifts Open"
                lift_match = re.search(
                    r"(\d+)\s*/\s*(\d+)\s*Lifts?\s*Open",
                    text, re.IGNORECASE
                )
                if lift_match:
                    ops.lifts_open = int(lift_match.group(1))
                    ops.lifts_total = int(lift_match.group(2))

            # === TRAILS ===
            # Pattern: "X / Y Trails Open"
            trails_match = re.search(
                r"(\d+)\s*/\s*(\d+)\s*Trails?\s*Open",
                text, re.IGNORECASE
            )
            if trails_match:
                ops.trails_open = int(trails_match.group(1))
                ops.trails_total = int(trails_match.group(2))

            # === SNOW DATA ===
            # Pattern: X" 24 Hr Snowfall or 24 Hr: X"
            snow_24_patterns = [
                r"(\d+(?:\.\d+)?)\s*[\"″]\s*24\s*[Hh]r",
                r"24\s*[Hh]r\s*(?:Snowfall)?[:\s]*(\d+(?:\.\d+)?)",
            ]
            for pattern in snow_24_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    snow.new_snow_24h_in = float(match.group(1))
                    break

            # Pattern: X" Year to Date or YTD: X"
            ytd_patterns = [
                r"(\d+(?:\.\d+)?)\s*[\"″]\s*(?:Year\s*to\s*Date|YTD)",
                r"(?:Year\s*to\s*Date|YTD)[:\s]*(\d+(?:\.\d+)?)",
            ]
            for pattern in ytd_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    snow.season_total_in = float(match.group(1))
                    break

            # 7-day total as 48h proxy
            day7_match = re.search(r"(\d+(?:\.\d+)?)\s*[\"″]\s*7\s*[Dd]ay", text, re.IGNORECASE)
            if day7_match:
                snow.new_snow_48h_in = float(day7_match.group(1))

            # Base depth - Summit or Base
            base_patterns = [
                r"(?:Summit|Base)[:\s]*(\d+(?:\.\d+)?)\s*[\"″]",
                r"(\d+(?:\.\d+)?)\s*[\"″]\s*(?:at\s+)?(?:Summit|Base)",
            ]
            for pattern in base_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    snow.base_depth_in = float(match.group(1))
                    break

            # === OPEN STATUS ===
            # Check for "Mountain Status Open" or similar
            # Also consider scheduled lifts as "open for today"
            lifts_active = (ops.lifts_open or 0) + (ops.lifts_scheduled or 0)
            if "mountain status open" in text.lower():
                ops.open_flag = True
            elif lifts_active > 0:
                ops.open_flag = True
            elif ops.lifts_open is not None or ops.lifts_scheduled is not None:
                ops.open_flag = False
            else:
                ops.open_flag = None

            result.ops = ops
            result.snow = snow
            result.success = True

        except Exception as e:
            logger.exception("SugarBowl parser error")
            result.error = str(e)

        return result

    def _count_lift_statuses(self, soup: BeautifulSoup) -> dict:
        """Count lifts by status from individual lift entries."""
        counts = {"open": 0, "scheduled": 0, "closed": 0, "total": 0}

        # Look for status text patterns in the page
        text = soup.get_text(separator="\n")

        # Known lift names at Sugar Bowl
        lift_names = [
            "Mt. Judah Express", "Jerome Hill Express", "Mt. Lincoln Express",
            "Christmas Tree Express", "Mt. Disney Express", "Nob Hill",
            "White Pine", "Summit Chair", "Gondola", "Flume Carpet", "Crow's Peak"
        ]

        for lift_name in lift_names:
            # Look for lift name followed by status
            pattern = rf"{re.escape(lift_name)}[^\n]*\n[^\n]*(Open|Scheduled|Closed)"
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                counts["total"] += 1
                status = match.group(1).lower()
                if status == "open":
                    counts["open"] += 1
                elif status == "scheduled":
                    counts["scheduled"] += 1
                else:
                    counts["closed"] += 1

        # If no matches found, try a simpler approach - count status occurrences
        if counts["total"] == 0:
            # Count standalone status words that likely refer to lifts
            # This is less accurate but better than nothing
            open_count = len(re.findall(r"(?:lift|chair|express)\s+open", text, re.IGNORECASE))
            sched_count = len(re.findall(r"(?:lift|chair|express)\s+scheduled", text, re.IGNORECASE))

            # Also check for icon references
            if "icon_lift_scheduled" in str(soup):
                sched_count = max(sched_count, text.lower().count("scheduled"))
            if "icon_lift_open" in str(soup):
                open_count = max(open_count, 1)

        return counts
