"""Adapter registry - maps adapter kinds to implementations."""

import logging
from typing import Type

from tahoe_conditions.adapters.base import BaseAdapter
from tahoe_conditions.adapters.boreal import BorealAdapter
from tahoe_conditions.adapters.diamond_peak import DiamondPeakAdapter
from tahoe_conditions.adapters.generic_html import GenericHTMLAdapter
from tahoe_conditions.adapters.homewood import HomewoodAdapter
from tahoe_conditions.adapters.mt_rose import MtRoseAdapter
from tahoe_conditions.adapters.palisades import PalisadesAdapter
from tahoe_conditions.adapters.placeholder_headless import PlaceholderHeadlessAdapter
from tahoe_conditions.adapters.sierra_at_tahoe import SierraAtTahoeAdapter
from tahoe_conditions.adapters.sugar_bowl import SugarBowlAdapter
from tahoe_conditions.adapters.tahoe_donner import TahoeDonnerAdapter
from tahoe_conditions.adapters.vail_resorts import VailResortsAdapter

logger = logging.getLogger(__name__)

# Map adapter "kind" names to adapter classes
ADAPTER_REGISTRY: dict[str, Type[BaseAdapter]] = {
    "generic": GenericHTMLAdapter,
    "boreal": BorealAdapter,
    "diamond_peak": DiamondPeakAdapter,
    "homewood": HomewoodAdapter,
    "mt_rose": MtRoseAdapter,
    "palisades": PalisadesAdapter,
    "sierra_at_tahoe": SierraAtTahoeAdapter,
    "sugar_bowl": SugarBowlAdapter,
    "tahoe_donner": TahoeDonnerAdapter,
    "vail_resorts": VailResortsAdapter,
    "placeholder_headless": PlaceholderHeadlessAdapter,
}

# Adapters that require JavaScript rendering (Playwright headless browser)
HEADLESS_ADAPTERS: set[str] = {
    "boreal",
    "palisades",
    "tahoe_donner",
    "placeholder_headless",
}


def get_adapter(kind: str) -> BaseAdapter:
    """
    Get an adapter instance by kind name.

    Args:
        kind: Adapter type from resorts.yaml

    Returns:
        Adapter instance

    Falls back to generic adapter if kind not found.
    """
    adapter_class = ADAPTER_REGISTRY.get(kind)

    if adapter_class is None:
        logger.warning(f"Unknown adapter kind '{kind}', using generic")
        adapter_class = GenericHTMLAdapter

    return adapter_class()


def requires_headless(kind: str) -> bool:
    """Check if an adapter kind requires headless browser."""
    return kind in HEADLESS_ADAPTERS
