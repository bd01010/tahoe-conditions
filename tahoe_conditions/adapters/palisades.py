"""Adapter for Palisades Tahoe (formerly Squaw Valley / Alpine Meadows)."""

import json
import logging
import re

from bs4 import BeautifulSoup

from tahoe_conditions.adapters.base import BaseAdapter, ParseResult
from tahoe_conditions.models import Operations, Snow

logger = logging.getLogger(__name__)


class PalisadesAdapter(BaseAdapter):
    """
    Parser for Palisades Tahoe conditions.

    The site uses mtnfeed.com React app for conditions data.
    After JS rendering, look for:
    - Lift status in data attributes or rendered text
    - Snow data in various formats
    """

    def parse(self, html: str) -> ParseResult:
        result = ParseResult()
        ops = Operations()
        snow = Snow()

        try:
            soup = BeautifulSoup(html, "lxml")

            # === LIFTS ===
            # mtnfeed widget pattern: Lifts</h3>...<strong>26/39</strong>...<span> Open</span>
            lift_match = re.search(
                r"Lifts</h3>.*?<strong>(\d+)/(\d+)</strong>.*?Open",
                html, re.IGNORECASE | re.DOTALL
            )
            if lift_match:
                ops.lifts_open = int(lift_match.group(1))
                ops.lifts_total = int(lift_match.group(2))

            # === TRAILS ===
            # mtnfeed widget pattern: Trails</h3>...<strong>97/296</strong>...<span> Open</span>
            trail_match = re.search(
                r"Trails</h3>.*?<strong>(\d+)/(\d+)</strong>.*?Open",
                html, re.IGNORECASE | re.DOTALL
            )
            if trail_match:
                ops.trails_open = int(trail_match.group(1))
                ops.trails_total = int(trail_match.group(2))

            # Fallback to text-based patterns if HTML parsing didn't work
            if ops.lifts_open is None:
                text = soup.get_text(separator=" ")
                text = re.sub(r"\s+", " ", text)

                lift_patterns = [
                    r"(\d+)\s*(?:of|/)\s*(\d+)\s*lifts?\s*(?:open|running)",
                    r"lifts?\s*(?:open|running)[:\s]*(\d+)\s*(?:of|/)\s*(\d+)",
                ]
                for pattern in lift_patterns:
                    match = re.search(pattern, text, re.IGNORECASE)
                    if match:
                        ops.lifts_open = int(match.group(1))
                        ops.lifts_total = int(match.group(2))
                        break

            if ops.trails_open is None:
                text = soup.get_text(separator=" ") if 'text' not in dir() else text
                text = re.sub(r"\s+", " ", text)

                trail_patterns = [
                    r"(\d+)\s*(?:of|/)\s*(\d+)\s*(?:trails?|runs?)\s*(?:open|groomed)",
                    r"(?:trails?|runs?)\s*(?:open|groomed)[:\s]*(\d+)\s*(?:of|/)\s*(\d+)",
                ]
                for pattern in trail_patterns:
                    match = re.search(pattern, text, re.IGNORECASE)
                    if match:
                        ops.trails_open = int(match.group(1))
                        ops.trails_total = int(match.group(2))
                        break

            # === SNOW DATA ===
            text = soup.get_text(separator=" ")
            text = re.sub(r"\s+", " ", text)

            # mtnfeed format: '0" - --" New Snow' (24hr - 48hr)
            new_snow_match = re.search(
                r'(\d+)"\s*-\s*(?:(\d+)|--)".*?New\s*Snow',
                text, re.IGNORECASE
            )
            if new_snow_match:
                snow.new_snow_24h_in = float(new_snow_match.group(1))
                if new_snow_match.group(2):
                    snow.new_snow_48h_in = float(new_snow_match.group(2))

            # Base depth - look for pattern like 'Base 102"' in WeatherCard
            base_match = re.search(
                r'Base.*?(\d{2,3})"',
                text, re.IGNORECASE
            )
            if base_match:
                snow.base_depth_in = float(base_match.group(1))

            # Season total - look for 'Season Total' or 'YTD'
            season_match = re.search(
                r'(?:Season\s*Total|YTD|Season).*?(\d{2,3})"',
                text, re.IGNORECASE
            )
            if season_match:
                snow.season_total_in = float(season_match.group(1))

            # === Try to find JSON data embedded in page ===
            # mtnfeed often has window.__INITIAL_STATE__ or similar
            script_tags = soup.find_all("script")
            for script in script_tags:
                if script.string and "__INITIAL_STATE__" in script.string:
                    # Try to extract JSON
                    json_match = re.search(
                        r"__INITIAL_STATE__\s*=\s*({.+?});",
                        script.string, re.DOTALL
                    )
                    if json_match:
                        try:
                            data = json.loads(json_match.group(1))
                            self._parse_mtnfeed_json(data, ops, snow)
                        except json.JSONDecodeError:
                            pass

            # === OPEN STATUS ===
            if ops.lifts_open is not None:
                ops.open_flag = ops.lifts_open > 0
            elif ops.trails_open is not None:
                ops.open_flag = ops.trails_open > 0
            else:
                ops.open_flag = None

            result.ops = ops
            result.snow = snow
            result.success = (ops.lifts_open is not None or ops.trails_open is not None)

            if not result.success:
                result.error = "Could not extract lift/trail data from rendered page"

        except Exception as e:
            logger.exception("Palisades parser error")
            result.error = str(e)

        return result

    def _parse_mtnfeed_json(self, data: dict, ops: Operations, snow: Snow) -> None:
        """Try to extract data from mtnfeed JSON structure."""
        try:
            # mtnfeed structures vary, but look for common patterns
            if "lifts" in data:
                lifts = data["lifts"]
                if isinstance(lifts, dict):
                    ops.lifts_open = lifts.get("open", ops.lifts_open)
                    ops.lifts_total = lifts.get("total", ops.lifts_total)

            if "trails" in data or "runs" in data:
                trails = data.get("trails") or data.get("runs", {})
                if isinstance(trails, dict):
                    ops.trails_open = trails.get("open", ops.trails_open)
                    ops.trails_total = trails.get("total", ops.trails_total)

            if "snow" in data:
                snow_data = data["snow"]
                if isinstance(snow_data, dict):
                    if "24hr" in snow_data:
                        snow.new_snow_24h_in = float(snow_data["24hr"])
                    if "base" in snow_data:
                        snow.base_depth_in = float(snow_data["base"])
                    if "season" in snow_data:
                        snow.season_total_in = float(snow_data["season"])

        except Exception as e:
            logger.debug(f"Error parsing mtnfeed JSON: {e}")
