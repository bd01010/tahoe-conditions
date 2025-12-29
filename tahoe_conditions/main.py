"""CLI entry point for Tahoe Conditions pipeline."""

import argparse
import logging
import sys
from datetime import datetime, timezone

from tahoe_conditions.adapters import get_adapter, requires_headless
from tahoe_conditions.http import fetch, fetch_headless, FetchError, HAS_PLAYWRIGHT
from tahoe_conditions.models import ResortConditions, Sources, Operations, Snow
from tahoe_conditions.output import (
    load_existing_resort,
    write_all_outputs,
)
from tahoe_conditions.registry import get_enabled_resorts
from tahoe_conditions.summarize import generate_summary
from tahoe_conditions.weather import fetch_weather

logger = logging.getLogger(__name__)


def setup_logging(verbose: bool = False) -> None:
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    # Quiet noisy libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)


def process_resort(resort_config) -> ResortConditions:
    """
    Process a single resort: fetch, parse, add weather.

    Args:
        resort_config: ResortConfig from registry

    Returns:
        ResortConditions object
    """
    slug = resort_config.slug
    logger.info(f"Processing {slug}...")

    now = datetime.now(timezone.utc)
    stale = False
    ops = Operations()
    snow = Snow()

    # Fetch and parse conditions
    try:
        # Use headless browser for JS-rendered sites
        if requires_headless(resort_config.kind):
            if not HAS_PLAYWRIGHT:
                logger.warning(f"  {slug}: requires Playwright (not installed), skipping")
                stale = True
                html = None
            else:
                html = fetch_headless(resort_config.source_url)
        else:
            html = fetch(resort_config.source_url)

        if html is None:
            result = None
        else:
            adapter = get_adapter(resort_config.kind)
            result = adapter.parse(html)

        if result and result.success:
            ops = result.ops
            snow = result.snow
            # Count scheduled as open for logging
            lifts_avail = (ops.lifts_open or 0) + (ops.lifts_scheduled or 0)
            logger.info(f"  {slug}: parsed OK - lifts={lifts_avail}/{ops.lifts_total}")
        elif result:
            logger.warning(f"  {slug}: parse failed - {result.error}")
            stale = True

            # Load last-known-good
            existing = load_existing_resort(slug)
            if existing:
                ops = existing.ops
                snow = existing.snow
                logger.info(f"  {slug}: using last-known-good from {existing.fetched_at_utc}")
        # else: html was None (Playwright not available), already marked stale

    except FetchError as e:
        logger.warning(f"  {slug}: fetch failed - {e}")
        stale = True

        # Load last-known-good
        existing = load_existing_resort(slug)
        if existing:
            ops = existing.ops
            snow = existing.snow

    # Fetch weather from NWS
    weather, points_url, forecast_url = fetch_weather(
        resort_config.lat,
        resort_config.lon
    )

    # Build sources
    sources = Sources(
        ops_url=resort_config.source_url,
        weather_points_url=points_url,
        weather_forecast_url=forecast_url,
    )

    return ResortConditions(
        slug=slug,
        name=resort_config.name,
        fetched_at_utc=now,
        stale=stale,
        sources=sources,
        ops=ops,
        snow=snow,
        weather=weather,
    )


def update_command(args) -> int:
    """Run the update pipeline."""
    setup_logging(args.verbose)

    logger.info("Starting Tahoe Conditions update...")

    # Load enabled resorts
    resorts_config = get_enabled_resorts()
    if not resorts_config:
        logger.error("No enabled resorts found in registry")
        return 1

    # Process each resort
    results = []
    for config in resorts_config:
        try:
            conditions = process_resort(config)
            results.append(conditions)
        except Exception as e:
            logger.exception(f"Unexpected error processing {config.slug}: {e}")
            # Create a stale entry
            results.append(ResortConditions(
                slug=config.slug,
                name=config.name,
                fetched_at_utc=datetime.now(timezone.utc),
                stale=True,
                sources=Sources(ops_url=config.source_url),
            ))

    # Generate summary
    summary = generate_summary(results)

    # Write outputs
    write_all_outputs(results, summary)

    # Log summary
    logger.info(f"Update complete: {summary.counts.open_resorts} open, "
                f"{summary.counts.closed_resorts} closed, "
                f"{summary.counts.stale_resorts} stale")

    return 0


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="tahoe-conditions",
        description="Lake Tahoe ski resort conditions aggregator"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Update command
    update_parser = subparsers.add_parser(
        "update",
        help="Fetch and update all resort conditions"
    )
    update_parser.set_defaults(func=update_command)

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 1

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
