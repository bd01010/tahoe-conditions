"""Adapter for Diamond Peak ski resort."""

import logging
import re
from typing import Optional

from bs4 import BeautifulSoup

from tahoe_conditions.adapters.base import BaseAdapter, ParseResult
from tahoe_conditions.models import Operations, Snow

logger = logging.getLogger(__name__)


class DiamondPeakAdapter(BaseAdapter):
    """
    Parser for Diamond Peak's conditions page.

    The page uses structured HTML with CSS classes:
    - conditions__row--header = lift rows
    - conditions__row--open, conditions__row--groomed = open trails
    - conditions__row--closed = closed items
    - conditions__status = status text
    """

    def parse(self, html: str) -> ParseResult:
        result = ParseResult()
        ops = Operations()
        snow = Snow()

        try:
            soup = BeautifulSoup(html, "lxml")
            text = soup.get_text(separator=" ")

            # === LIFTS ===
            # Lifts are in rows with class "conditions__row--header" containing "Lift" or "Chair"
            header_rows = soup.find_all(class_="conditions__row--header")
            lifts_open = 0
            lifts_total = 0

            for row in header_rows:
                label = row.find(class_="conditions__label")
                status = row.find(class_="conditions__status")
                if label and status:
                    label_text = label.get_text().strip()
                    status_text = status.get_text().strip().lower()
                    # Check if this is a lift (contains "Lift", "Chair", or "Powerline")
                    if any(word in label_text for word in ["Lift", "Chair", "Powerline", "Express"]):
                        lifts_total += 1
                        if status_text in ["open", "groomed"]:
                            lifts_open += 1

            if lifts_total > 0:
                ops.lifts_open = lifts_open
                ops.lifts_total = lifts_total

            # === TRAILS ===
            # Trails are in non-header rows with open/groomed/closed classes
            # Count rows that are NOT headers and NOT terrain parks
            trail_rows = soup.find_all(class_=re.compile(r"conditions__row--(?:open|groomed|closed)"))
            trails_open = 0
            trails_total = 0

            for row in trail_rows:
                classes = row.get("class", [])
                # Skip if this is a header row (lift)
                if "conditions__row--header" in classes:
                    continue
                # Skip terrain parks
                label = row.find(class_="conditions__label")
                if label and "Village" in label.get_text():
                    continue  # Skip terrain park items

                trails_total += 1
                if "conditions__row--open" in classes or "conditions__row--groomed" in classes:
                    trails_open += 1

            if trails_total > 0:
                ops.trails_open = trails_open
                ops.trails_total = trails_total

            # === SNOW DATA ===
            # Look for patterns in the page text
            snow.new_snow_24h_in = self._extract_snow_value(text,
                r"(\d+)\s*(?:Inches?|\")\s*24\s*H",
                r"24\s*[Hh](?:our)?[s]?[:\s]*(\d+)")

            # Try overnight as 24h fallback
            if snow.new_snow_24h_in is None:
                overnight = self._extract_snow_value(text,
                    r"(\d+)\s*(?:Inches?|\")\s*overnight",
                    r"overnight[:\s]*(\d+)")
                if overnight is not None:
                    snow.new_snow_24h_in = overnight

            # Base depth
            base_match = re.search(r"base[:\s]*(\d+)\s*(?:Inches?|\")", text, re.IGNORECASE)
            if base_match:
                snow.base_depth_in = float(base_match.group(1))

            # Also check for "Peak: X Inches" pattern
            peak_match = re.search(r"peak[:\s]*(\d+)\s*(?:Inches?|\")", text, re.IGNORECASE)
            if peak_match and snow.base_depth_in is None:
                snow.base_depth_in = float(peak_match.group(1))

            # Season total
            season_match = re.search(r"season[:\s]*(\d+)\s*(?:Inches?|\")", text, re.IGNORECASE)
            if season_match:
                snow.season_total_in = float(season_match.group(1))

            # Storm total as 48h proxy
            storm_patterns = [
                r"storm\s*(?:total)?[:\s]*(\d+)\s*(?:Inches?|\")",
                r"(\d+)\s*(?:Inches?|\")\s*storm\s*(?:total)?",
            ]
            for pattern in storm_patterns:
                storm_match = re.search(pattern, text, re.IGNORECASE)
                if storm_match:
                    snow.new_snow_48h_in = float(storm_match.group(1))
                    break

            # Open status
            if ops.lifts_open is not None:
                ops.open_flag = ops.lifts_open > 0
            elif "mountain closed" in text.lower() or "closed for season" in text.lower():
                ops.open_flag = False
            elif "open" in text.lower():
                ops.open_flag = True

            result.ops = ops
            result.snow = snow
            result.success = True

        except Exception as e:
            logger.exception("DiamondPeak parser error")
            result.error = str(e)

        return result

    def _extract_snow_value(self, text: str, *patterns: str) -> Optional[float]:
        """Try multiple patterns to extract a snow value."""
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    return float(match.group(1))
                except (ValueError, IndexError):
                    continue
        return None
