"""Tests for parsing utilities and adapters."""

import pytest

from tahoe_conditions.adapters.base import BaseAdapter


class TestParsingUtilities:
    """Test number parsing utility functions."""

    def test_parse_fraction_slash(self):
        """Test parsing fractions with slash."""
        assert BaseAdapter.parse_fraction("5/10") == (5, 10)
        assert BaseAdapter.parse_fraction("5 / 10") == (5, 10)
        assert BaseAdapter.parse_fraction("  5  /  10  ") == (5, 10)

    def test_parse_fraction_of(self):
        """Test parsing fractions with 'of'."""
        assert BaseAdapter.parse_fraction("5 of 10") == (5, 10)
        assert BaseAdapter.parse_fraction("5 out of 10") == (5, 10)

    def test_parse_fraction_invalid(self):
        """Test parsing invalid fractions."""
        assert BaseAdapter.parse_fraction("") == (None, None)
        assert BaseAdapter.parse_fraction("five") == (None, None)
        assert BaseAdapter.parse_fraction(None) == (None, None)

    def test_parse_inches_simple(self):
        """Test parsing simple inch values."""
        assert BaseAdapter.parse_inches('6"') == 6.0
        assert BaseAdapter.parse_inches("6 in") == 6.0
        assert BaseAdapter.parse_inches("6 inches") == 6.0
        assert BaseAdapter.parse_inches("12.5 inches") == 12.5

    def test_parse_inches_range(self):
        """Test parsing inch ranges."""
        assert BaseAdapter.parse_inches('6-8"') == 7.0
        assert BaseAdapter.parse_inches("6 - 8 inches") == 7.0
        assert BaseAdapter.parse_inches("10–15") == 12.5  # en-dash

    def test_parse_inches_invalid(self):
        """Test parsing invalid inch values."""
        assert BaseAdapter.parse_inches("") is None
        assert BaseAdapter.parse_inches("none") is None
        assert BaseAdapter.parse_inches(None) is None

    def test_parse_bool_status(self):
        """Test parsing open/closed status."""
        assert BaseAdapter.parse_bool_status("Open") is True
        assert BaseAdapter.parse_bool_status("OPEN") is True
        assert BaseAdapter.parse_bool_status("operating") is True
        assert BaseAdapter.parse_bool_status("Closed") is False
        assert BaseAdapter.parse_bool_status("CLOSED") is False
        assert BaseAdapter.parse_bool_status("Not Operating") is False
        assert BaseAdapter.parse_bool_status("unknown") is None
        assert BaseAdapter.parse_bool_status("") is None

    def test_clean_text(self):
        """Test text cleaning."""
        assert BaseAdapter.clean_text("  hello   world  ") == "hello world"
        assert BaseAdapter.clean_text("multi\nline\ntext") == "multi line text"
        assert BaseAdapter.clean_text(None) == ""
        assert BaseAdapter.clean_text("") == ""


class TestGenericAdapter:
    """Test the generic HTML adapter."""

    def test_parse_simple_conditions(self):
        """Test parsing simple conditions HTML."""
        from tahoe_conditions.adapters.generic_html import GenericHTMLAdapter

        html = """
        <html>
        <body>
            <div>5/10 Lifts Open</div>
            <div>20/50 Trails Open</div>
            <div>6" in last 24 hours</div>
            <div>Base: 48"</div>
        </body>
        </html>
        """

        adapter = GenericHTMLAdapter()
        result = adapter.parse(html)

        assert result.success
        assert result.ops.lifts_open == 5
        assert result.ops.lifts_total == 10
        assert result.ops.trails_open == 20
        assert result.ops.trails_total == 50
        assert result.snow.new_snow_24h_in == 6.0
        assert result.snow.base_depth_in == 48.0


class TestDiamondPeakAdapter:
    """Test Diamond Peak adapter."""

    def test_parse_conditions(self):
        """Test parsing Diamond Peak style HTML."""
        from tahoe_conditions.adapters.diamond_peak import DiamondPeakAdapter

        html = """
        <html>
        <body>
            <strong>0</strong> Inches overnight
            <strong>5</strong> Inches 24 hour
            <strong>34</strong> Inches storm total
            Base: <strong>16</strong> Inches
            Season: <strong>66</strong> Inches
            3/6 lifts open
            25/30 trails
        </body>
        </html>
        """

        adapter = DiamondPeakAdapter()
        result = adapter.parse(html)

        assert result.success
        # Note: adapter prioritizes 24 hour value over overnight
        assert result.snow.new_snow_24h_in == 5.0  # 24 hour value
        assert result.snow.new_snow_48h_in == 34.0  # storm total
        assert result.snow.base_depth_in == 16.0
        assert result.snow.season_total_in == 66.0


class TestSugarBowlAdapter:
    """Test Sugar Bowl adapter."""

    def test_parse_conditions(self):
        """Test parsing Sugar Bowl style HTML."""
        from tahoe_conditions.adapters.sugar_bowl import SugarBowlAdapter

        html = """
        <html>
        <body>
            <div>5 / 9 Lifts Open</div>
            <div>93 / 105 Trails Open</div>
            <div>0" 24 Hr</div>
            <div>66" 7 Day</div>
            <div>99" Year to Date</div>
            <div>Summit: 47"</div>
            <div>Mountain Status Open</div>
        </body>
        </html>
        """

        adapter = SugarBowlAdapter()
        result = adapter.parse(html)

        assert result.success
        assert result.ops.lifts_open == 5
        assert result.ops.lifts_total == 9
        assert result.ops.trails_open == 93
        assert result.ops.trails_total == 105
        assert result.snow.new_snow_24h_in == 0.0
        assert result.snow.new_snow_48h_in == 66.0  # 7-day as proxy
        assert result.snow.season_total_in == 99.0
        assert result.snow.base_depth_in == 47.0
