"""Rule-based summarization for resort conditions."""

import logging
from datetime import datetime, timezone
from typing import Optional

from tahoe_conditions.models import ResortConditions, Summary, SummaryCounts

logger = logging.getLogger(__name__)


def generate_blurb(resort: ResortConditions) -> str:
    """
    Generate a short summary blurb for a resort.

    Args:
        resort: ResortConditions object

    Returns:
        Human-readable summary sentence
    """
    if resort.stale:
        return (
            f"Latest update unavailable; showing last known conditions "
            f"from {resort.fetched_at_utc.strftime('%Y-%m-%d %H:%M')} UTC."
        )

    parts = [f"{resort.name}:"]

    # Lift/trail status
    # Count scheduled as open for display purposes
    ops = resort.ops
    lifts_available = (ops.lifts_open or 0) + (ops.lifts_scheduled or 0)
    trails_available = (ops.trails_open or 0) + (ops.trails_scheduled or 0)

    if ops.lifts_total is not None:
        parts.append(f"{lifts_available}/{ops.lifts_total} lifts")
    if ops.trails_total is not None:
        parts.append(f"{trails_available}/{ops.trails_total} trails.")
    elif ops.lifts_total is not None:
        parts[-1] += "."

    # Snow
    snow = resort.snow
    if snow.new_snow_24h_in is not None:
        parts.append(f"New snow (24h): {snow.new_snow_24h_in:.0f}\".")
    elif snow.base_depth_in is not None:
        parts.append(f"Base: {snow.base_depth_in:.0f}\".")

    # Weather
    weather = resort.weather
    weather_parts = []
    if weather.short_forecast:
        weather_parts.append(weather.short_forecast)
    if weather.temp_f is not None:
        weather_parts.append(f"{weather.temp_f:.0f}°F")
    if weather.wind_mph is not None:
        weather_parts.append(f"wind {weather.wind_mph:.0f} mph")

    if weather_parts:
        parts.append("Forecast: " + ", ".join(weather_parts) + ".")

    return " ".join(parts)


def compute_highlights(resorts: list[ResortConditions]) -> list[str]:
    """
    Compute highlight statements for the summary.

    Args:
        resorts: List of resort conditions

    Returns:
        List of highlight strings
    """
    highlights = []

    # Filter to non-stale, open resorts
    active = [r for r in resorts if not r.stale and r.ops.open_flag]

    if not active:
        return ["All resorts are currently closed or unavailable."]

    # Most open terrain (highest trails_open ratio)
    with_trails = [r for r in active if r.ops.trails_open and r.ops.trails_total]
    if with_trails:
        best_terrain = max(with_trails, key=lambda r: r.ops.trails_open / r.ops.trails_total)
        pct = (best_terrain.ops.trails_open / best_terrain.ops.trails_total) * 100
        highlights.append(
            f"Most open terrain: {best_terrain.name} "
            f"({best_terrain.ops.trails_open}/{best_terrain.ops.trails_total} trails, {pct:.0f}%)"
        )

    # Most new snow (24h)
    with_snow = [r for r in active if r.snow.new_snow_24h_in is not None and r.snow.new_snow_24h_in > 0]
    if with_snow:
        most_snow = max(with_snow, key=lambda r: r.snow.new_snow_24h_in)
        highlights.append(
            f"Most new snow: {most_snow.name} ({most_snow.snow.new_snow_24h_in:.0f}\" in 24h)"
        )

    # Windiest
    with_wind = [r for r in active if r.weather.wind_mph is not None]
    if with_wind:
        windiest = max(with_wind, key=lambda r: r.weather.wind_mph)
        if windiest.weather.wind_mph >= 15:  # Only highlight if notably windy
            highlights.append(
                f"Windiest: {windiest.name} ({windiest.weather.wind_mph:.0f} mph)"
            )

    # Coldest
    with_temp = [r for r in active if r.weather.temp_f is not None]
    if with_temp:
        coldest = min(with_temp, key=lambda r: r.weather.temp_f)
        if coldest.weather.temp_f <= 32:  # Only highlight if notably cold
            highlights.append(
                f"Coldest: {coldest.name} ({coldest.weather.temp_f:.0f}°F)"
            )

    return highlights


def generate_summary(resorts: list[ResortConditions]) -> Summary:
    """
    Generate a complete summary from resort conditions.

    Args:
        resorts: List of all resort conditions

    Returns:
        Summary object
    """
    counts = SummaryCounts()
    blurbs = {}

    for resort in resorts:
        # Generate blurb
        blurbs[resort.slug] = generate_blurb(resort)

        # Count status
        if resort.stale:
            counts.stale_resorts += 1
        elif resort.ops.open_flag:
            counts.open_resorts += 1
        else:
            counts.closed_resorts += 1

    highlights = compute_highlights(resorts)

    return Summary(
        last_updated_utc=datetime.now(timezone.utc),
        counts=counts,
        highlights=highlights,
        blurbs=blurbs,
    )
