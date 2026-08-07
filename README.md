# Yerevan Smart Parking Recommender

A Flask + Leaflet.js web app that turns your original Folium/OSMnx script into
a live, interactive parking dashboard for Kentron, Yerevan.

## What's inside

```
yerevan-smart-parking/
├── app.py                  # Flask backend: data loading, simulation, API
├── requirements.txt
├── templates/
│   └── index.html          # Leaflet dashboard (sidebar + map, single file)
└── data/
    └── parking_cache.geojson   # created automatically on first run
```

## How it works

- **Data source** (`app.py`): on startup, the app tries to pull live curb/lot
  parking geometry for "Kentron, Yerevan, Armenia" via `osmnx.features_from_place`,
  using the same tag set and red/green/blue/grey classification logic as your
  original script. A successful pull is cached to `data/parking_cache.geojson`
  so future restarts are instant. If OSMnx/Overpass isn't reachable (no
  network, rate-limited, etc.), the app automatically falls back to a curated
  offline dataset covering well-known Kentron corridors (Northern Avenue,
  Mashtots Avenue, Republic Square, the Opera lot, and more), so the app is
  always demoable.
- **Simulated real-time layer**: `simulate_segment_state()` models congestion
  as a function of hour-of-day and weekday/weekend, with morning (08:00–10:00)
  and evening (17:00–20:00) rush-hour peaks in Kentron and low congestion at
  night, plus a small deterministic per-street "personality" offset. This
  drives `availability_pct`, `occupancy_status`, and `traffic_level` for every
  segment, refreshed every minute.
- **Recommendation engine** (`/api/recommend`): given a destination
  lat/lon, it finds every parking segment within `radius` (default 500 m),
  scores it as `type_weight - traffic_penalty - distance_penalty`
  (free > lot > paid > unspecified, penalized by live congestion and
  distance), and returns the top 3.

## Install & run

```bash
cd yerevan-smart-parking
python3 -m venv venv && source venv/bin/activate   # optional but recommended
pip install -r requirements.txt
python app.py
```

Then open **http://127.0.0.1:5000** in your browser.

The first launch will try to fetch live OSM data (can take 10–30s); if that
fails for any reason, you'll see a console log and the app seamlessly starts
with the offline dataset instead — no action needed.

## Using the dashboard

- **Click anywhere on the map** (or pick a landmark preset — Republic Square,
  Opera House, Cascade, Vernissage) to drop a destination pin.
- The **"Top 3 Recommended Spots"** panel updates instantly, each card showing
  a live availability gauge, walking distance/time, and score.
- The **"Live Traffic"** panel lists every street ranked by current simulated
  congestion, refreshing every 15 seconds along with the map layer.
- Click any street or lot on the map for a popup with its live status.

## API reference

| Endpoint | Method | Params | Returns |
|---|---|---|---|
| `/api/parking` | GET | – | GeoJSON `FeatureCollection` of all segments with live `parking_type`, `occupancy_status`, `availability_pct`, `congestion_score`, `traffic_level` |
| `/api/recommend` | GET | `lat`, `lon`, `radius` (m, default 500) | Top 3 scored parking recommendations near a destination |
| `/api/traffic` | GET | – | Street-by-street congestion snapshot + overall Kentron traffic level |
| `/api/refresh` | POST | – | Forces a fresh OSMnx pull (falls back to cache/offline data on failure) |

## Notes for production use

- Swap the simulated availability model for a real feed (municipal sensors,
  a partner API, or crowdsourced check-ins) by replacing the body of
  `simulate_segment_state()` — the rest of the app (API contract, frontend)
  doesn't need to change.
- For heavier traffic, put `PARKING_FEATURES` behind a proper cache
  (Redis) instead of the in-memory list, and move the OSMnx refresh to a
  scheduled background job rather than a request-triggered one.
