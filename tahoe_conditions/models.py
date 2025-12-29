"""Pydantic models for resort conditions data contract."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class Sources(BaseModel):
    """URLs used to fetch data."""
    ops_url: str
    weather_points_url: Optional[str] = None
    weather_forecast_url: Optional[str] = None


class Operations(BaseModel):
    """Lift and trail operations status."""
    open_flag: Optional[bool] = None
    lifts_open: Optional[int] = None
    lifts_scheduled: Optional[int] = None  # Lifts planned to open today
    lifts_total: Optional[int] = None
    trails_open: Optional[int] = None
    trails_scheduled: Optional[int] = None  # Trails planned to open today
    trails_total: Optional[int] = None


class Snow(BaseModel):
    """Snow conditions."""
    new_snow_24h_in: Optional[float] = None
    new_snow_48h_in: Optional[float] = None
    base_depth_in: Optional[float] = None
    season_total_in: Optional[float] = None
    surface: Optional[str] = None
    report_updated_at: Optional[datetime] = None


class Weather(BaseModel):
    """Current weather from NWS."""
    temp_f: Optional[float] = None
    wind_mph: Optional[float] = None
    wind_gust_mph: Optional[float] = None
    short_forecast: Optional[str] = None
    forecast_period_name: Optional[str] = None


class ResortConditions(BaseModel):
    """Complete resort conditions record."""
    slug: str
    name: str
    fetched_at_utc: datetime
    stale: bool = False
    sources: Sources
    ops: Operations = Field(default_factory=Operations)
    snow: Snow = Field(default_factory=Snow)
    weather: Weather = Field(default_factory=Weather)


class SummaryCounts(BaseModel):
    """Counts for summary."""
    open_resorts: int = 0
    closed_resorts: int = 0
    stale_resorts: int = 0


class Summary(BaseModel):
    """Homepage summary with highlights and blurbs."""
    last_updated_utc: datetime
    counts: SummaryCounts = Field(default_factory=SummaryCounts)
    highlights: list[str] = Field(default_factory=list)
    blurbs: dict[str, str] = Field(default_factory=dict)


class ResortConfig(BaseModel):
    """Configuration for a single resort from resorts.yaml."""
    slug: str
    name: str
    kind: str  # adapter type
    source_url: str
    lat: float
    lon: float
    enabled: bool = True
    note: Optional[str] = None
