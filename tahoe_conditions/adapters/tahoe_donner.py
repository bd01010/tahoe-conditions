"""Adapter for Tahoe Donner ski resort."""

import logging
import re

from bs4 import BeautifulSoup

from tahoe_conditions.adapters.base import BaseAdapter, ParseResult
from tahoe_conditions.models import Operations, Snow

logger = logging.getLogger(__name__)


class TahoeDonnerAdapter(BaseAdapter):
    """
    Parser for Tahoe Donner ski resort conditions.

    Tahoe Donner is a smaller private resort. The conditions page
    uses HTML tables but status cells require JS to populate.
    After rendering, look for:
    - Lift status table rows
    - Snow conditions in various formats
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
            # Try table-based extraction first
            lifts_open = 0
            lifts_total = 0

            # Look for lift status tables
            tables = soup.find_all("table")
            for table in tables:
                rows = table.find_all("tr")
                for row in rows:
                    cells = row.find_all(["td", "th"])
                    row_text = " ".join(c.get_text(strip=True).lower() for c in cells)

                    # Check if this looks like a lift row
                    if any(lift in row_text for lift in ["chair", "lift", "carpet"]):
                        lifts_total += 1
                        if "open" in row_text or "yes" in row_text:
                            lifts_open += 1

            if lifts_total > 0:
                ops.lifts_open = lifts_open
                ops.lifts_total = lifts_total

            # Fallback to text patterns if table parsing didn't work
            if ops.lifts_open is None:
                lift_patterns = [
                    r"(\d+)\s*(?:of|/)\s*(\d+)\s*lifts?\s*(?:open|running)",
                    r"lifts?\s*(?:open)?[:\s]*(\d+)\s*(?:of|/)\s*(\d+)",
                    r"(\d+)\s*/\s*(\d+)\s*lifts?",
                ]
                for pattern in lift_patterns:
                    match = re.search(pattern, text, re.IGNORECASE)
                    if match:
                        ops.lifts_open = int(match.group(1))
                        ops.lifts_total = int(match.group(2))
                        break

            # === TRAILS ===
            # Try table-based extraction
            trails_open = 0
            trails_total = 0

            for table in tables:
                rows = table.find_all("tr")
                for row in rows:
                    cells = row.find_all(["td", "th"])
                    row_text = " ".join(c.get_text(strip=True).lower() for c in cells)

                    # Check if this looks like a trail row (by difficulty or name)
                    if any(diff in row_text for diff in ["green", "blue", "black", "diamond", "run", "trail"]):
                        # Skip header rows
                        if "name" in row_text and "status" in row_text:
                            continue
                        trails_total += 1
                        if "open" in row_text or "groomed" in row_text:
                            trails_open += 1

            if trails_total > 0:
                ops.trails_open = trails_open
                ops.trails_total = trails_total

            # Fallback to text patterns
            if ops.trails_open is None:
                trail_patterns = [
                    r"(\d+)\s*(?:of|/)\s*(\d+)\s*(?:trails?|runs?)\s*(?:open|groomed)",
                    r"(?:trails?|runs?)\s*(?:open)?[:\s]*(\d+)\s*(?:of|/)\s*(\d+)",
                ]
                for pattern in trail_patterns:
                    match = re.search(pattern, text, re.IGNORECASE)
                    if match:
                        ops.trails_open = int(match.group(1))
                        ops.trails_total = int(match.group(2))
                        break

            # === SNOW DATA ===
            # New snow
            new_snow_match = re.search(
                r"(?:24\s*(?:hr|hour)|new\s*snow|overnight|fresh)[:\s]*(\d+(?:\.\d+)?)\s*(?:in|\")",
                text, re.IGNORECASE
            )
            if new_snow_match:
                snow.new_snow_24h_in = float(new_snow_match.group(1))

            # Base depth
            base_match = re.search(
                r"(?:base|snow\s*depth)[:\s]*(\d+(?:\.\d+)?)\s*(?:in|\")",
                text, re.IGNORECASE
            )
            if base_match:
                snow.base_depth_in = float(base_match.group(1))

            # Season total
            season_match = re.search(
                r"(?:season|ytd)[:\s]*(\d+(?:\.\d+)?)\s*(?:in|\")",
                text, re.IGNORECASE
            )
            if season_match:
                snow.season_total_in = float(season_match.group(1))

            # === OPEN STATUS ===
            if "closed" in text.lower() and "season" in text.lower():
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
            logger.exception("Tahoe Donner parser error")
            result.error = str(e)

        return result
