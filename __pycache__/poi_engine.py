"""
poi_engine.py
=============
Nearby point-of-interest (POI) demand modeling for the Yerevan Smart Parking
Recommender.

Why this exists
----------------
Google's Places API does not expose "busier than usual" / Popular Times
data through any officially supported field — it's rendered client-side in
the Google Maps UI only, and scraping it breaks Google's Terms of Service.
So rather than faking a Google integration, this module builds an
OSM-grounded stand-in that plugs into the same place in the pipeline:

  1. Pull nearby points of interest (restaurants, cafes, universities,
     malls/markets, theatres & museums, hospitals) from OpenStreetMap
     around Kentron.
  2. Give each POI category a base "draw" weight — how much parking
     pressure that kind of place typically creates — and a time-of-day /
     day-of-week busyness curve (a university fills nearby curbs during
     class hours; a restaurant strip peaks at lunch and dinner; a market
     spikes on weekends).
  3. For every parking segment, precompute which POIs sit within a short
     walk (default 250 m) and combine their weighted, time-varying
     busyness into a single `poi_demand_index` in [0, 1].

That index feeds into both the live congestion simulation and the
recommendation score, and the nearest POI names are surfaced in the API so
the UI can explain *why* a spot is scored the way it is ("busy — 90 m from
Republic Square").

Swapping in a real feed later
------------------------------
`_time_busyness()` is the single seam meant for a licensed replacement
(e.g. a paid Google Places "popular times" partner feed, or a municipal
foot-traffic API): keep the same (category, hour, is_weekend) -> [0,1]
signature and everything downstream — demand index, recommendation score,
API payloads — keeps working unchanged.
"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
POI_CACHE_FILE = DATA_DIR / "poi_cache.geojson"
DATA_DIR.mkdir(exist_ok=True)

PLACE_NAME = "Kentron, Yerevan, Armenia"

# OSM tags worth pulling in as "demand generators" near a parking spot.
POI_TAGS = {
    "amenity": ["restaurant", "cafe", "fast_food", "bar", "university",
                "theatre", "cinema", "hospital", "marketplace", "college"],
    "shop": ["mall", "supermarket", "department_store"],
    "tourism": ["museum", "attraction", "gallery"],
}

# How much baseline parking pressure a category creates, before any
# time-of-day adjustment. Calibrated relative to each other, not absolute.
CATEGORY_WEIGHT = {
    "university": 0.90,
    "college": 0.80,
    "hospital": 0.75,
    "mall": 0.85,
    "department_store": 0.75,
    "supermarket": 0.55,
    "marketplace": 0.80,
    "theatre": 0.60,
    "cinema": 0.60,
    "museum": 0.50,
    "gallery": 0.35,
    "attraction": 0.55,
    "restaurant": 0.55,
    "bar": 0.45,
    "cafe": 0.40,
    "fast_food": 0.35,
}

DEFAULT_RADIUS_M = 250.0
EARTH_RADIUS_M = 6_371_000


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = EARTH_RADIUS_M
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


# --------------------------------------------------------------------------
# Time-of-day busyness curves per category (0..1). Everything not listed
# falls back to a mild flat-ish "shop hours" curve.
# --------------------------------------------------------------------------

def _bell(hour: float, center: float, width: float, height: float) -> float:
    return height * math.exp(-((hour - center) ** 2) / (2 * width ** 2))


def _time_busyness(category: str, now: datetime) -> float:
    """
    Returns a 0..1 busyness factor for a POI category at the given moment.
    This is the seam to replace with a real "popular times" feed later —
    see module docstring.
    """
    hour = now.hour + now.minute / 60.0
    is_weekend = now.weekday() >= 5

    if category in ("university", "college"):
        if is_weekend:
            return max(0.05, _bell(hour, 13, 3.5, 0.25))
        return max(0.08, _bell(hour, 11.5, 3.2, 0.85))

    if category in ("restaurant", "bar", "cafe", "fast_food"):
        lunch = _bell(hour, 13.0, 1.3, 0.7)
        dinner = _bell(hour, 20.0, 1.8, 0.9 if is_weekend else 0.75)
        return max(0.08, min(1.0, lunch + dinner))

    if category in ("mall", "department_store", "supermarket", "marketplace"):
        base = _bell(hour, 17.5, 4.0, 0.75 if is_weekend else 0.55)
        return max(0.05, base)

    if category in ("theatre", "cinema"):
        return max(0.03, _bell(hour, 19.5, 1.6, 0.8))

    if category in ("museum", "gallery", "attraction"):
        return max(0.05, _bell(hour, 13.5, 3.0, 0.55 if is_weekend else 0.4))

    if category == "hospital":
        # Hospitals draw steady parking pressure around the clock, with a
        # daytime visiting-hours bump.
        return max(0.35, _bell(hour, 14.0, 5.0, 0.55))

    # Generic fallback: mild daytime bump.
    return max(0.1, _bell(hour, 14.0, 4.5, 0.45))


# --------------------------------------------------------------------------
# Loading POIs: live OSM fetch (cached) with a curated offline fallback.
# --------------------------------------------------------------------------

def _classify_poi(row_dict: dict) -> str | None:
    for key in ("amenity", "shop", "tourism"):
        val = row_dict.get(key)
        if isinstance(val, str) and val in CATEGORY_WEIGHT:
            return val
    return None


def _fetch_from_osmnx() -> list[dict]:
    import osmnx as ox  # lazy import, optional dependency

    gdf = ox.features_from_place(PLACE_NAME, tags=POI_TAGS)
    pois = []
    for idx, row in gdf.iterrows():
        geom = row.geometry
        if geom is None:
            continue
        row_dict = row.to_dict()
        category = _classify_poi(row_dict)
        if category is None:
            continue
        point = geom.centroid if geom.geom_type != "Point" else geom
        name = row_dict.get("name") or category.replace("_", " ").title()
        poi_id = hashlib.md5(f"{name}-{point.x}-{point.y}".encode()).hexdigest()[:10]
        pois.append({
            "id": poi_id,
            "name": name,
            "category": category,
            "weight": CATEGORY_WEIGHT[category],
            "lat": point.y,
            "lon": point.x,
        })

    if not pois:
        raise RuntimeError("OSMnx returned no usable POIs.")
    return pois


def _fallback_pois() -> list[dict]:
    """Well-known Kentron landmarks, used whenever Overpass isn't reachable."""
    raw = [
        ("Republic Square", "attraction", 40.1772, 44.5152),
        ("Cascade Complex", "attraction", 40.1897, 44.5133),
        ("Yerevan Opera Theatre", "theatre", 40.1846, 44.5122),
        ("Yerevan State University", "university", 40.1878, 44.5064),
        ("American University of Armenia", "university", 40.1846, 44.5170),
        ("GUM Market", "marketplace", 40.1902, 44.5065),
        ("Vernissage Market", "marketplace", 40.1815, 44.5175),
        ("Northern Avenue Shops", "mall", 40.1794, 44.5134),
        ("Moscow Cinema", "cinema", 40.1832, 44.5147),
        ("Saint Gregory the Illuminator Cathedral", "attraction", 40.1888, 44.5197),
        ("Yerevan City Hospital No.1", "hospital", 40.1926, 44.5087),
        ("Dalma Food Court", "restaurant", 40.1783, 44.5121),
        ("Komitas Cafe Row", "cafe", 40.1830, 44.5105),
        ("Tashir Pizza Amiryan", "fast_food", 40.1808, 44.5140),
    ]
    pois = []
    for name, category, lat, lon in raw:
        poi_id = hashlib.md5(name.encode()).hexdigest()[:10]
        pois.append({
            "id": poi_id,
            "name": name,
            "category": category,
            "weight": CATEGORY_WEIGHT.get(category, 0.4),
            "lat": lat,
            "lon": lon,
        })
    return pois


def load_pois(force_refresh: bool = False) -> list[dict]:
    if not force_refresh and POI_CACHE_FILE.exists():
        try:
            data = json.loads(POI_CACHE_FILE.read_text())
            return data["pois"]
        except Exception:
            pass

    try:
        pois = _fetch_from_osmnx()
        POI_CACHE_FILE.write_text(json.dumps({"pois": pois}, ensure_ascii=False))
        print(f"[poi_engine] Loaded {len(pois)} POIs live from OSMnx and cached them.")
        return pois
    except Exception as exc:
        print(f"[poi_engine] OSMnx POI fetch unavailable ({exc}); using curated offline POIs.")
        pois = _fallback_pois()
        POI_CACHE_FILE.write_text(json.dumps({"pois": pois, "source": "fallback"}, ensure_ascii=False))
        return pois


# --------------------------------------------------------------------------
# Per-segment static proximity + per-request dynamic demand
# --------------------------------------------------------------------------

def nearby_pois_for_point(lat: float, lon: float, pois: list[dict],
                           radius_m: float = DEFAULT_RADIUS_M, limit: int = 4) -> list[dict]:
    """Static (time-independent) step: which POIs are within walking
    distance of this point, closest first. Safe to precompute once per
    parking segment and cache alongside its geometry."""
    found = []
    for poi in pois:
        dist = haversine_m(lat, lon, poi["lat"], poi["lon"])
        if dist <= radius_m:
            found.append({**poi, "distance_m": round(dist, 1)})
    found.sort(key=lambda p: p["distance_m"])
    return found[:limit]


def current_busyness(category: str, now: datetime | None = None) -> float:
    """Public wrapper around _time_busyness(), for callers (e.g. a debug
    endpoint) that want a single category's busyness without a full
    nearby-POI list."""
    return _time_busyness(category, now or datetime.now())


def demand_index(nearby: list[dict], now: datetime | None = None,
                  radius_m: float = DEFAULT_RADIUS_M) -> float:
    """Dynamic (time-of-day) step: combine a precomputed nearby-POI list
    into a single 0..1 demand pressure score for right now."""
    if not nearby:
        return 0.0
    now = now or datetime.now()

    total = 0.0
    for poi in nearby:
        busyness = _time_busyness(poi["category"], now)
        distance_decay = max(0.0, 1.0 - poi["distance_m"] / radius_m)
        total += poi["weight"] * busyness * distance_decay

    # Saturating curve so 1-2 nearby hotspots don't already max the score,
    # but a genuine cluster of busy venues does.
    return round(1.0 - math.exp(-total * 1.6), 3)
