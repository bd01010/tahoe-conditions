"""Adapter for Vail Resorts (Heavenly, Northstar, Kirkwood)."""

import json
import logging
import re
from typing import Optional

from bs4 import BeautifulSoup

from tahoe_conditions.adapters.base import BaseAdapter, ParseResult
from tahoe_conditions.models import Operations, Snow

logger = logging.getLogger(__name__)


class VailResortsAdapter(BaseAdapter):
    """
    Parser for Vail Resorts terrain status pages.

    The terrain-and-lift-status.aspx pages show:
    - "X / Y Lifts" pattern
    - "X / Y Trails" or "X / Y Runs" pattern
    - Snow data in FR.snowReportData JSON (if available)
    """

    def parse(self, html: str) -> ParseResult:
        result = ParseResult()
        ops = Operations()
        snow = Snow()

        try:
            soup = BeautifulSoup(html, "lxml")
            text = soup.get_text(separator=" ")
            text = re.sub(r"\s+", " ", text)

            # === LIFTS - Try JSON first ===
            terrain_data = self._extract_terrain_status_json(html)
            if terrain_data and "Lifts" in terrain_data:
                counts = self._count_lift_statuses(terrain_data["Lifts"])
                ops.lifts_open = counts.get("open", 0)
                ops.lifts_scheduled = counts.get("scheduled", 0)
                ops.lifts_total = counts.get("total", 0)
            else:
                # Fallback: Pattern "X / Y Lifts"
                lift_match = re.search(
                    r"(\d+)\s*/\s*(\d+)\s*Lifts?(?:\s*Open)?",
                    text, re.IGNORECASE
                )
                if lift_match:
                    ops.lifts_open = int(lift_match.group(1))
                    ops.lifts_total = int(lift_match.group(2))

            # === TRAILS - Try JSON first ===
            # Trails are inside GroomingAreas, not at top level
            if terrain_data and "GroomingAreas" in terrain_data:
                all_trails = []
                for area in terrain_data["GroomingAreas"]:
                    all_trails.extend(area.get("Trails", []))
                if all_trails:
                    counts = self._count_trail_statuses(all_trails)
                    ops.trails_open = counts.get("open", 0)
                    ops.trails_scheduled = counts.get("scheduled", 0)
                    ops.trails_total = counts.get("total", 0)
            if ops.trails_total is None:
                # Fallback: Pattern "X / Y Trails" or "X / Y Runs"
                trails_matches = re.findall(
                    r"(\d+)\s*/\s*(\d+)\s*(?:Trails?|Runs?)(?:\s*Open)?",
                    text, re.IGNORECASE
                )
                if trails_matches:
                    ops.trails_open = int(trails_matches[0][0])
                    ops.trails_total = int(trails_matches[0][1])

            # === SNOW DATA ===
            # Try to extract FR.snowReportData JSON if present
            json_data = self._extract_snow_report_json(html)
            if json_data:
                snow = self._parse_json_data(json_data)
            else:
                # Fallback to HTML text parsing
                snow = self._parse_html_fallback(text)

            # === OPEN STATUS ===
            # Resort is "open" if any lifts are running OR scheduled to open
            lifts_active = (ops.lifts_open or 0) + (ops.lifts_scheduled or 0)
            trails_active = (ops.trails_open or 0) + (ops.trails_scheduled or 0)

            if lifts_active > 0:
                ops.open_flag = True
            elif trails_active > 0:
                ops.open_flag = True
            elif ops.lifts_open is not None or ops.lifts_scheduled is not None:
                ops.open_flag = False
            else:
                ops.open_flag = None

            result.ops = ops
            result.snow = snow
            result.success = True

        except Exception as e:
            logger.exception("VailResorts parser error")
            result.error = str(e)

        return result

    def _extract_snow_report_json(self, html: str) -> Optional[dict]:
        """Extract FR.snowReportData JSON from script tags."""
        pattern = r"FR\.snowReportData\s*=\s*(\{[^;]+\});"
        match = re.search(pattern, html, re.DOTALL)

        if match:
            try:
                json_str = match.group(1)
                # Remove trailing commas before } or ]
                json_str = re.sub(r",\s*([}\]])", r"\1", json_str)
                return json.loads(json_str)
            except json.JSONDecodeError as e:
                logger.debug(f"Failed to parse FR.snowReportData: {e}")

        return None

    def _parse_json_data(self, data: dict) -> Snow:
        """Parse the FR.snowReportData structure."""
        snow = Snow()

        def extract_inches(value) -> Optional[float]:
            """Extract inches from various formats."""
            if not value:
                return None
            # Handle dict format: {"Inches": "5", "Centimeters": "12"}
            if isinstance(value, dict):
                inches_str = value.get("Inches", "")
                if inches_str and inches_str != "0":
                    try:
                        return float(inches_str)
                    except ValueError:
                        pass
                return 0.0 if inches_str == "0" else None
            # Handle string format: "5 inches / 12 cm"
            if isinstance(value, str):
                match = re.search(r"(\d+(?:\.\d+)?)\s*inch", value, re.IGNORECASE)
                if match:
                    return float(match.group(1))
            return None

        # Extract snow values
        snow.new_snow_24h_in = extract_inches(data.get("TwentyFourHourSnowfall"))
        if snow.new_snow_24h_in is None:
            snow.new_snow_24h_in = extract_inches(data.get("OvernightSnowfall"))
        snow.new_snow_48h_in = extract_inches(data.get("FortyEightHourSnowfall"))
        snow.base_depth_in = extract_inches(data.get("BaseDepth"))
        snow.season_total_in = extract_inches(data.get("CurrentSeason"))

        return snow

    def _parse_html_fallback(self, text: str) -> Snow:
        """Fallback HTML text parsing for snow data."""
        snow = Snow()

        # 24-hour snow
        match = re.search(r"24\s*(?:hr|hour)[s]?[:\s]*(\d+(?:\.\d+)?)", text, re.IGNORECASE)
        if match:
            snow.new_snow_24h_in = float(match.group(1))

        # 48-hour snow
        match = re.search(r"48\s*(?:hr|hour)[s]?[:\s]*(\d+(?:\.\d+)?)", text, re.IGNORECASE)
        if match:
            snow.new_snow_48h_in = float(match.group(1))

        # Base depth
        match = re.search(r"base[:\s]*(\d+(?:\.\d+)?)\s*(?:in|\")", text, re.IGNORECASE)
        if match:
            snow.base_depth_in = float(match.group(1))

        # Season total
        match = re.search(r"season[:\s]*(\d+(?:\.\d+)?)", text, re.IGNORECASE)
        if match:
            snow.season_total_in = float(match.group(1))

        return snow

    def _extract_terrain_status_json(self, html: str) -> Optional[dict]:
        """Extract FR.TerrainStatusFeed JSON from script tags."""
        pattern = r"FR\.TerrainStatusFeed\s*=\s*(\{[^;]+\});"
        match = re.search(pattern, html, re.DOTALL)

        if match:
            try:
                json_str = match.group(1)
                # Remove trailing commas before } or ]
                json_str = re.sub(r",\s*([}\]])", r"\1", json_str)
                return json.loads(json_str)
            except json.JSONDecodeError as e:
                logger.debug(f"Failed to parse FR.TerrainStatusFeed: {e}")

        return None

    def _count_lift_statuses(self, lifts: list) -> dict:
        """Count lifts by status.

        Status values can be numeric or string:
        - 0 or "Closed" = Closed
        - 1 or "Open" = Open
        - 2 or "On-Hold" = On Hold
        - 3 or "Scheduled" = Scheduled
        """
        counts = {"open": 0, "scheduled": 0, "closed": 0, "hold": 0, "total": 0}

        for lift in lifts:
            status = lift.get("Status", 0)
            counts["total"] += 1

            # Handle both numeric and string status
            if isinstance(status, int):
                if status == 1:
                    counts["open"] += 1
                elif status == 3:
                    counts["scheduled"] += 1
                elif status == 2:
                    counts["hold"] += 1
                else:  # 0 or other
                    counts["closed"] += 1
            else:
                status_str = str(status).lower()
                if status_str == "open":
                    counts["open"] += 1
                elif status_str == "scheduled":
                    counts["scheduled"] += 1
                elif status_str in ("on-hold", "on hold", "hold"):
                    counts["hold"] += 1
                else:
                    counts["closed"] += 1

        return counts

    def _count_trail_statuses(self, trails: list) -> dict:
        """Count trails by status (uses IsOpen boolean)."""
        counts = {"open": 0, "scheduled": 0, "closed": 0, "total": 0}

        for trail in trails:
            counts["total"] += 1
            # Trails use IsOpen boolean instead of Status
            if trail.get("IsOpen", False):
                counts["open"] += 1
            else:
                counts["closed"] += 1

        return counts
