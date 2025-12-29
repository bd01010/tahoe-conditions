"""Base adapter interface for resort condition parsers."""

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from tahoe_conditions.models import Operations, Snow


@dataclass
class ParseResult:
    """Result of parsing resort conditions page."""
    success: bool = False
    ops: Operations = field(default_factory=Operations)
    snow: Snow = field(default_factory=Snow)
    error: Optional[str] = None
    needs_headless: bool = False


class BaseAdapter(ABC):
    """Base class for resort condition adapters."""

    @abstractmethod
    def parse(self, html: str) -> ParseResult:
        """
        Parse HTML content and extract conditions.

        Args:
            html: Raw HTML content from resort conditions page

        Returns:
            ParseResult with extracted data
        """
        pass

    # ========== Utility Methods ==========

    @staticmethod
    def parse_fraction(text: str) -> tuple[Optional[int], Optional[int]]:
        """
        Parse fraction like "5/10" or "5 / 10" or "5 of 10".

        Returns:
            Tuple of (numerator, denominator) or (None, None) if parsing fails
        """
        if not text:
            return None, None

        # Clean the text
        text = text.strip()

        # Try various patterns
        patterns = [
            r"(\d+)\s*/\s*(\d+)",      # 5/10 or 5 / 10
            r"(\d+)\s+of\s+(\d+)",     # 5 of 10
            r"(\d+)\s+out\s+of\s+(\d+)",  # 5 out of 10
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return int(match.group(1)), int(match.group(2))

        return None, None

    @staticmethod
    def parse_inches(text: str) -> Optional[float]:
        """
        Parse inch measurement like '6"', "6 in", "6 inches", "6-8"".

        Returns:
            Float inches or None if parsing fails
        """
        if not text:
            return None

        text = text.strip().lower()

        # Handle range like "6-8"" - take the average
        range_match = re.search(r"(\d+(?:\.\d+)?)\s*[-–]\s*(\d+(?:\.\d+)?)", text)
        if range_match:
            low = float(range_match.group(1))
            high = float(range_match.group(2))
            return (low + high) / 2

        # Single value
        match = re.search(r"(\d+(?:\.\d+)?)\s*(?:\"|in|inches?)?", text)
        if match:
            return float(match.group(1))

        return None

    @staticmethod
    def parse_bool_status(text: str) -> Optional[bool]:
        """Parse open/closed status text."""
        if not text:
            return None

        text = text.strip().lower()

        # Check negative phrases first (order matters)
        if any(phrase in text for phrase in ["not operating", "closed", "not open"]):
            return False
        if any(word in text for word in ["open", "yes", "operating"]):
            return True

        return None

    @staticmethod
    def clean_text(text: Optional[str]) -> str:
        """Clean whitespace from text."""
        if not text:
            return ""
        return " ".join(text.split())
