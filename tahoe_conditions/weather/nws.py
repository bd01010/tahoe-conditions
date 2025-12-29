"""NWS (National Weather Service) API integration."""

import logging
import re
from typing import Optional

from tahoe_conditions.config import NWS_CACHE_TTL
from tahoe_conditions.http import fetch_json, FetchError
from tahoe_conditions.models import Weather

logger = logging.getLogger(__name__)

NWS_POINTS_URL = "https://api.weather.gov/points/{lat},{lon}"


def _parse_wind(wind_str: Optional[str]) -> tuple[Optional[float], Optional[float]]:
    """
    Parse wind string like "10 mph" or "10 to 20 mph" or "10 mph gusting to 25 mph".

    Returns:
        Tuple of (wind_mph, wind_gust_mph)
    """
    if not wind_str:
        return None, None

    wind_mph = None
    wind_gust_mph = None

    # Match patterns like "10 mph" or "10 to 20 mph"
    speed_match = re.search(r"(\d+)\s*(?:to\s*(\d+))?\s*mph", wind_str, re.IGNORECASE)
    if speed_match:
        wind_mph = float(speed_match.group(1))
        if speed_match.group(2):
            # "10 to 20 mph" - use higher value as base
            wind_mph = float(speed_match.group(2))

    # Match gust pattern
    gust_match = re.search(r"gust(?:ing|s)?\s*(?:to\s*)?(\d+)\s*mph", wind_str, re.IGNORECASE)
    if gust_match:
        wind_gust_mph = float(gust_match.group(1))

    return wind_mph, wind_gust_mph


def fetch_weather(lat: float, lon: float) -> tuple[Weather, Optional[str], Optional[str]]:
    """
    Fetch current weather from NWS for given coordinates.

    Args:
        lat: Latitude
        lon: Longitude

    Returns:
        Tuple of (Weather object, points_url, forecast_url)
    """
    points_url = NWS_POINTS_URL.format(lat=lat, lon=lon)
    forecast_url = None
    weather = Weather()

    try:
        # Step 1: Get the forecast URL from points endpoint
        logger.debug(f"Fetching NWS points: {points_url}")
        points_data = fetch_json(points_url, ttl_seconds=NWS_CACHE_TTL)

        properties = points_data.get("properties", {})
        forecast_url = properties.get("forecast")

        if not forecast_url:
            logger.warning(f"No forecast URL in NWS points response for {lat},{lon}")
            return weather, points_url, None

        # Step 2: Fetch the forecast
        logger.debug(f"Fetching NWS forecast: {forecast_url}")
        forecast_data = fetch_json(forecast_url, ttl_seconds=NWS_CACHE_TTL)

        periods = forecast_data.get("properties", {}).get("periods", [])
        if not periods:
            logger.warning(f"No forecast periods for {lat},{lon}")
            return weather, points_url, forecast_url

        # Take the first (current) period
        current = periods[0]

        # Extract temperature
        temp = current.get("temperature")
        temp_unit = current.get("temperatureUnit", "F")
        if temp is not None:
            if temp_unit == "C":
                temp = temp * 9 / 5 + 32  # Convert to F
            weather.temp_f = float(temp)

        # Extract wind
        wind_speed = current.get("windSpeed")
        wind_mph, wind_gust_mph = _parse_wind(wind_speed)
        weather.wind_mph = wind_mph
        weather.wind_gust_mph = wind_gust_mph

        # Extract short forecast and period name
        weather.short_forecast = current.get("shortForecast")
        weather.forecast_period_name = current.get("name")

        logger.info(f"NWS weather fetched: {weather.temp_f}F, {weather.wind_mph} mph")

    except FetchError as e:
        logger.warning(f"Failed to fetch NWS weather: {e}")

    return weather, points_url, forecast_url
