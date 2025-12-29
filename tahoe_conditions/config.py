"""Configuration settings for the pipeline."""

from pathlib import Path

# Contact info for User-Agent (required by NWS API)
CONTACT_EMAIL = "tahoe-conditions-bot@example.com"  # Replace with real email

# User-Agent header
USER_AGENT = f"TahoeConditionsBot/0.1 ({CONTACT_EMAIL})"

# HTTP settings
REQUEST_TIMEOUT = 15  # seconds
RATE_LIMIT_DELAY = 1.5  # seconds between requests to same host
MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 2  # exponential backoff multiplier

# Cache settings
CACHE_DIR = Path(".cache")
CONDITIONS_CACHE_TTL = 900  # 15 minutes for resort conditions
NWS_CACHE_TTL = 3600  # 60 minutes for NWS data

# Output directories
OUTPUT_DIR = Path("public/data")
RESORTS_OUTPUT_DIR = OUTPUT_DIR / "resorts"

# Registry
RESORTS_YAML = Path("resorts.yaml")
