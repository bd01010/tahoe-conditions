# Tahoe Conditions

A free, repeatable pipeline that fetches current conditions for Lake Tahoe ski resorts, normalizes the data into a consistent schema, and outputs static JSON files.

## Features

- **No paid APIs** - Scrapes resort websites directly + NWS weather API
- **Resilient** - Individual failures don't break the pipeline; last-known-good fallback
- **Normalized schema** - Consistent data format across all resorts
- **Static JSON output** - Ready for website integration
- **NWS weather** - Fetches real-time weather from National Weather Service

## Quick Start

```bash
# Install dependencies
pip install -e .

# Run update
python -m tahoe_conditions update

# Output files are in public/data/
```

## Output Files

- `public/data/latest.json` - All resorts in a single file
- `public/data/resorts/<slug>.json` - Individual resort files
- `public/data/summary.json` - Homepage highlights and blurbs

## Data Schema

Each resort record includes:

```json
{
  "slug": "diamond-peak",
  "name": "Diamond Peak",
  "fetched_at_utc": "2025-12-29T13:32:55.686875Z",
  "stale": false,
  "sources": {
    "ops_url": "https://...",
    "weather_points_url": "https://api.weather.gov/points/...",
    "weather_forecast_url": "https://api.weather.gov/gridpoints/.../forecast"
  },
  "ops": {
    "open_flag": true,
    "lifts_open": 5,
    "lifts_total": 10,
    "trails_open": 20,
    "trails_total": 40
  },
  "snow": {
    "new_snow_24h_in": 6.0,
    "new_snow_48h_in": 12.0,
    "base_depth_in": 48.0,
    "season_total_in": 150.0
  },
  "weather": {
    "temp_f": 28.0,
    "wind_mph": 15.0,
    "short_forecast": "Mostly Cloudy",
    "forecast_period_name": "Tonight"
  }
}
```

## Enabled Resorts

| Resort | Status |
|--------|--------|
| Diamond Peak | ✅ Works |
| Mt Rose | ✅ Works |
| Sierra-at-Tahoe | ✅ Works |
| Sugar Bowl | ✅ Works |
| Heavenly | ⚠️ Partial (needs improvement) |
| Northstar | ⚠️ Partial (needs improvement) |
| Kirkwood | ⚠️ Partial (needs improvement) |

## Adding a New Resort

1. **Add to registry** - Edit `resorts.yaml`:

```yaml
- slug: new-resort
  name: New Resort Name
  kind: generic  # or create a new adapter
  source_url: https://example.com/conditions
  lat: 39.0
  lon: -120.0
  enabled: true
```

2. **Test parsing** - Run `python -m tahoe_conditions update` and check output

3. **Create custom adapter** (if needed):
   - Add `tahoe_conditions/adapters/new_resort.py`
   - Register in `tahoe_conditions/adapters/registry.py`
   - Use `generic` adapter as a template

## Adapter Types

| Type | Description |
|------|-------------|
| `generic` | Pattern matching for common HTML layouts |
| `diamond_peak` | Diamond Peak specific parser |
| `mt_rose` | Mt Rose specific parser |
| `sierra_at_tahoe` | Sierra-at-Tahoe specific parser |
| `sugar_bowl` | Sugar Bowl specific parser |
| `vail_resorts` | Vail/EpicMix sites (extracts JSON from script tags) |
| `placeholder_headless` | Marks resort as needing JavaScript rendering |

## GitHub Actions

The included workflow (`.github/workflows/update.yml`) runs every 30 minutes:
- Fetches latest conditions
- Commits updated JSON files to repo
- Skips commit if no changes

## Website Integration

Fetch the JSON from your static site:

```javascript
// Fetch all resorts
const response = await fetch('/data/latest.json');
const data = await response.json();

// Fetch summary for homepage
const summary = await fetch('/data/summary.json');
const { highlights, blurbs, counts } = await summary.json();
```

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tahoe_conditions/tests/ -v

# Run with verbose logging
python -m tahoe_conditions update -v
```

## Configuration

Edit `tahoe_conditions/config.py`:

- `CONTACT_EMAIL` - Required for NWS API User-Agent
- `CONDITIONS_CACHE_TTL` - Cache duration for resort pages (default: 15 min)
- `NWS_CACHE_TTL` - Cache duration for weather (default: 60 min)

## Next Steps

1. **Improve Vail adapters** - The Vail/EpicMix sites need better JSON extraction
2. **Add Palisades Tahoe** - Requires headless browser (Playwright)
3. **Add Boreal** - Requires headless browser (Gatsby SPA)
4. **Historical data** - Track conditions over time
5. **Alerts** - Notify on significant snow events

## License

MIT
