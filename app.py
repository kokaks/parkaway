"""
Yerevan Smart Parking Recommender
==================================
Production-ready Flask backend that:
  1. Loads curbside + lot parking geometry for Kentron, Yerevan (via ground-truth,
     OSMnx cache, or fallback dataset).
  2. Simulates real-time traffic congestion / space availability using a
     time-of-day model (rush hour vs. off-peak vs. night).
  3. Integrates Contextual Factors:
     - Destination POI Busyness (25% weight) using hourly activity profiles.
     - Real-Time Live Traffic adjustment (8% weight) with simulated fallback.
     - Real-Time Live Weather integration (2% weight) with neutral fallback.
     - Proximity / Distance weighting highly prioritized (35% weight).
  4. Serves the parking network as GeoJSON (/api/parking).
  5. Serves a multi-factor destination recommendation engine (/api/recommend).
  6. Serves a rolled-up live traffic snapshot (/api/traffic).
  7. Serves an administrative curation API (/api/admin/feature).
  8. Serves an ML feedback recording API (/api/admin/ml_feedback).
  9. Serves a live search/autocomplete geocoding engine (/api/search).

Run:
    pip install -r requirements.txt
    python app.py
Then open http://127.0.0.1:5000
"""

from __future__ import annotations

from flask_sqlalchemy import SQLAlchemy
import hashlib
import json
import math
import os
import random
import time
import urllib.error
import urllib.parse
import urllib.request
import ssl
ssl._create_default_https_context = ssl._create_unverified_context
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, render_template, request, make_response

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------

PLACE_NAME = "Kentron, Yerevan, Armenia"
MAP_CENTER = (40.1792, 44.5152)

DATA_DIR = Path(__file__).parent / "data"
CACHE_FILE = DATA_DIR / "parking_cache.geojson"
GROUND_TRUTH_FILE = DATA_DIR / "ground_truth.geojson"
ML_DATA_FILE = DATA_DIR / "ml_training_data.json"
DATA_DIR.mkdir(exist_ok=True)

PARKING_TAGS = {
    "parking:lane": True,
    "parking:left": True,
    "parking:right": True,
    "parking:both": True,
    "amenity": "parking",
}

TYPE_COLORS = {
    "paid": "#e74c3c",         # Red lines
    "free": "#2ecc71",         # Green curbside lanes
    "lot": "#3498db",          # Dedicated lots (polygons)
    "unavailable": "#f39c12",  # Orange / No-parking zones
    "unspecified": "#7f8c8d",  # Grey / general
}

TYPE_BASE_WEIGHT = {
    "free": 100,
    "lot": 85,
    "paid": 70,
    "unspecified": 45,
    "unavailable": 0,
}

# Phonetic / transliteration synonyms for fuzzy matching Yerevan streets
YEREVAN_STREET_SYNONYMS = {
    "mastoc": "Mashtots",
    "mashtoc": "Mashtots",
    "mashtos": "Mashtots",
    "մաշտոց": "Mashtots",
    "abovian": "Abovyan",
    "աբովյան": "Abovyan",
    "toumanian": "Tumanyan",
    "thoumanian": "Tumanyan",
    "թումանյան": "Tumanyan",
    "saryan": "Saryan",
    "սարյան": "Saryan",
    "sayat": "Sayat-Nova",
    "սայաթ": "Sayat-Nova",
    "bagramyan": "Baghramyan",
    "bagramian": "Baghramyan",
    "բաղրամյան": "Baghramyan",
    "amirian": "Amiryan",
    "ամիրյան": "Amiryan",
    "terian": "Teryan",
    "տերյան": "Teryan",
    "pushkin": "Pushkin",
    "պուշկին": "Pushkin",
    "northern": "Northern Avenue",
    "republic": "Republic Square",
}

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///local_parking.db').replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Define the Database Model for your ML Data
class MLFeedback(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lat = db.Column(db.Float, nullable=False)
    lon = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

# Create the tables automatically
with app.app_context():
    db.create_all()

# --------------------------------------------------------------------------
# Contextual Factor 1: Destination POI Busyness Model & Data
# --------------------------------------------------------------------------

POI_WEIGHTS = {
    "restaurant": 3,
    "cafe": 2,
    "coffee_shop": 2,
    "bar": 3,
    "university": 5,
    "school": 3,
    "office": 4,
    "bank": 2,
    "hospital": 5,
    "pharmacy": 1,
    "shopping_centre": 5,
    "supermarket": 3,
    "convenience": 2,
    "museum": 2,
    "hotel": 2,
    "metro_station": 4,
    "bus_station": 3,
    "government": 4,
    "park": 1,
    "tourist_attraction": 3,
}

FALLBACK_POIS = [
    {"name": "Dolmama Restaurant", "type": "restaurant", "lat": 40.1812, "lon": 44.5140},
    {"name": "Lavash Restaurant", "type": "restaurant", "lat": 40.1835, "lon": 44.5125},
    {"name": "Sherep Restaurant", "type": "restaurant", "lat": 40.1778, "lon": 44.5138},
    {"name": "Jazzve Cafe Opera", "type": "cafe", "lat": 40.1848, "lon": 44.5142},
    {"name": "Cascade Cafe Cluster", "type": "cafe", "lat": 40.1910, "lon": 44.5135},
    {"name": "Green Bean Coffee", "type": "coffee_shop", "lat": 40.1852, "lon": 44.5150},
    {"name": "Coffeeshop Company", "type": "coffee_shop", "lat": 40.1805, "lon": 44.5130},
    {"name": "Saryan Wine Bars", "type": "bar", "lat": 40.1840, "lon": 44.5075},
    {"name": "Yerevan State University", "type": "university", "lat": 40.1815, "lon": 44.5260},
    {"name": "Polytechnic University", "type": "university", "lat": 40.1882, "lon": 44.5230},
    {"name": "State University of Economics", "type": "university", "lat": 40.1830, "lon": 44.5245},
    {"name": "Medical University", "type": "university", "lat": 40.1880, "lon": 44.5280},
    {"name": "Chekhov School No. 55", "type": "school", "lat": 40.1830, "lon": 44.5085},
    {"name": "Government House", "type": "government", "lat": 40.1775, "lon": 44.5128},
    {"name": "Ministry of Foreign Affairs", "type": "government", "lat": 40.1762, "lon": 44.5140},
    {"name": "Yerevan City Hall", "type": "government", "lat": 40.1742, "lon": 44.5078},
    {"name": "Central Bank of Armenia", "type": "bank", "lat": 40.1745, "lon": 44.5112},
    {"name": "Ameriabank HQ", "type": "bank", "lat": 40.1785, "lon": 44.5132},
    {"name": "Ardshinbank HQ", "type": "bank", "lat": 40.1810, "lon": 44.5115},
    {"name": "Synergy Business Center", "type": "office", "lat": 40.1890, "lon": 44.5180},
    {"name": "Nairi Medical Center", "type": "hospital", "lat": 40.1875, "lon": 44.5102},
    {"name": "Heratsi Hospital Complex", "type": "hospital", "lat": 40.1865, "lon": 44.5270},
    {"name": "Alfa-Pharm Central", "type": "pharmacy", "lat": 40.1825, "lon": 44.5135},
    {"name": "Tashir Street Shopping Gallery", "type": "shopping_centre", "lat": 40.1800, "lon": 44.5130},
    {"name": "Vernissage Souvenir Market", "type": "shopping_centre", "lat": 40.1808, "lon": 44.5175},
    {"name": "Carrefour Metronome", "type": "shopping_centre", "lat": 40.1818, "lon": 44.5162},
    {"name": "Yerevan City Supermarket", "type": "supermarket", "lat": 40.1822, "lon": 44.5098},
    {"name": "GUM Market", "type": "supermarket", "lat": 40.1905, "lon": 44.5065},
    {"name": "SAS Supermarket Abovyan", "type": "supermarket", "lat": 40.1842, "lon": 44.5145},
    {"name": "History Museum of Armenia", "type": "museum", "lat": 40.1786, "lon": 44.5138},
    {"name": "National Gallery of Armenia", "type": "museum", "lat": 40.1788, "lon": 44.5142},
    {"name": "Cafesjian Center for the Arts", "type": "museum", "lat": 40.1915, "lon": 44.5132},
    {"name": "Matenadaran", "type": "museum", "lat": 40.1920, "lon": 44.5210},
    {"name": "Marriott Hotel Yerevan", "type": "hotel", "lat": 40.1778, "lon": 44.5122},
    {"name": "Grand Hotel Yerevan", "type": "hotel", "lat": 40.1815, "lon": 44.5148},
    {"name": "Ani Plaza Hotel", "type": "hotel", "lat": 40.1838, "lon": 44.5180},
    {"name": "Republic Square Metro Station", "type": "metro_station", "lat": 40.1782, "lon": 44.5152},
    {"name": "Yeritasardakan Metro Station", "type": "metro_station", "lat": 40.1865, "lon": 44.5212},
    {"name": "Zoravar Andranik Metro Station", "type": "metro_station", "lat": 40.1712, "lon": 44.5128},
    {"name": "France Square Bus Stop", "type": "bus_station", "lat": 40.1860, "lon": 44.5150},
    {"name": "English Park", "type": "park", "lat": 40.1748, "lon": 44.5095},
    {"name": "Lovers' Park", "type": "park", "lat": 40.1895, "lon": 44.5070},
    {"name": "Circular Park", "type": "park", "lat": 40.1830, "lon": 44.5215},
    {"name": "Opera & Ballet Theatre", "type": "tourist_attraction", "lat": 40.1848, "lon": 44.5158},
]


def get_poi_hourly_factor(poi_type: str, hour: int, is_weekend: bool) -> float:
    if poi_type == "restaurant":
        if 12 <= hour <= 14:
            return 0.95
        if 18 <= hour <= 22:
            return 1.00
        if 11 <= hour <= 17:
            return 0.50
        return 0.15
    elif poi_type in ("cafe", "coffee_shop"):
        if 8 <= hour <= 11:
            return 1.00
        if 12 <= hour <= 18:
            return 0.70
        if 19 <= hour <= 22:
            return 0.40
        return 0.10
    elif poi_type == "bar":
        if 20 <= hour <= 23 or 0 <= hour <= 1:
            return 1.00
        if 17 <= hour <= 19:
            return 0.50
        return 0.05
    elif poi_type in ("university", "school", "office", "bank", "government"):
        if is_weekend:
            return 0.10
        if 9 <= hour <= 17:
            return 1.00
        if hour == 8 or hour == 18:
            return 0.50
        return 0.05
    elif poi_type in ("shopping_centre", "supermarket", "convenience"):
        if 12 <= hour <= 20:
            return 1.00
        if 9 <= hour <= 11 or 21 <= hour <= 22:
            return 0.55
        return 0.15
    elif poi_type in ("hospital", "pharmacy"):
        return 0.85 if 8 <= hour <= 20 else 0.50
    elif poi_type in ("museum", "tourist_attraction"):
        if 10 <= hour <= 18:
            return 1.00
        if 19 <= hour <= 21:
            return 0.35
        return 0.05
    elif poi_type in ("metro_station", "bus_station"):
        if (8 <= hour <= 10) or (17 <= hour <= 19):
            return 1.00
        if 10 <= hour <= 16:
            return 0.60
        if 20 <= hour <= 23:
            return 0.30
        return 0.10
    elif poi_type == "park":
        if is_weekend and (11 <= hour <= 20):
            return 1.00
        if 17 <= hour <= 21:
            return 0.80
        if 11 <= hour <= 16:
            return 0.45
        return 0.10
    elif poi_type == "hotel":
        if (7 <= hour <= 10) or (16 <= hour <= 21):
            return 0.90
        return 0.50
    return 0.40


_BUSYNESS_CACHE: dict[str, tuple[float, float]] = {}


def calculate_destination_busyness(lat: float, lon: float, now: datetime | None = None) -> float:
    now = now or datetime.now()
    hour = now.hour
    is_weekend = now.weekday() >= 5

    cache_key = f"{round(lat, 4)}:{round(lon, 4)}:{hour}:{is_weekend}"
    now_ts = time.time()

    if cache_key in _BUSYNESS_CACHE:
        ts, cached_score = _BUSYNESS_CACHE[cache_key]
        if now_ts - ts < 300:
            return cached_score

    total_raw_impact = 0.0
    search_radius_m = 350.0

    for poi in FALLBACK_POIS:
        dist = haversine_m(lat, lon, poi["lat"], poi["lon"])
        if dist <= search_radius_m:
            decay = max(0.0, 1.0 - (dist / search_radius_m))
            weight = POI_WEIGHTS.get(poi["type"], 2)
            hourly_factor = get_poi_hourly_factor(poi["type"], hour, is_weekend)
            total_raw_impact += weight * hourly_factor * decay

    normalized_score = min(1.0, round(total_raw_impact / 18.0, 2))
    _BUSYNESS_CACHE[cache_key] = (now_ts, normalized_score)
    return normalized_score


# --------------------------------------------------------------------------
# Contextual Factor 2: Real-Time Traffic Integration
# --------------------------------------------------------------------------

_TRAFFIC_CACHE = {"timestamp": 0.0, "multiplier": 1.0}


def fetch_live_traffic_multiplier() -> float:
    now_ts = time.time()
    global _TRAFFIC_CACHE
    if "_TRAFFIC_CACHE" not in globals():
        _TRAFFIC_CACHE = {"timestamp": 0, "multiplier": 1.0}

    if now_ts - _TRAFFIC_CACHE["timestamp"] < 180:
        return _TRAFFIC_CACHE["multiplier"]

    yandex_routing_key = os.environ.get("YANDEX_ROUTING_API_KEY", "a3c71f9f-d1d6-4319-a690-e1866877ac8e")
    multiplier = 1.0

    try:
        if yandex_routing_key and yandex_routing_key != "a3c71f9f-d1d6-4319-a690-e1866877ac8e":
            origin = f"{MAP_CENTER[0]},{MAP_CENTER[1]}"
            destination = f"{MAP_CENTER[0] + 0.01},{MAP_CENTER[1] + 0.01}"
            url = f"https://api.routing.yandex.net/v2/route?waypoints={origin}|{destination}&apikey={yandex_routing_key}"
            
            req = urllib.request.Request(url, headers={"User-Agent": "YerevanParkingApp/1.0"})
            with urllib.request.urlopen(req, timeout=4) as resp:
                data = json.loads(resp.read().decode())
                if "route" in data and "legs" in data["route"] and len(data["route"]["legs"]) > 0:
                    weight_data = data["route"]["legs"][0].get("weight", {})
                    time_normal = weight_data.get("time", {}).get("value", 1)
                    time_traffic = weight_data.get("time_with_traffic", {}).get("value", time_normal)
                    if time_normal > 0:
                        ratio = time_traffic / time_normal
                        multiplier = max(0.8, min(1.5, ratio))
    except Exception as exc:
        print(f"[traffic] Yandex Routing API call skipped/failed ({exc}); using simulated traffic multiplier 1.0.")
        multiplier = 1.0

    _TRAFFIC_CACHE["multiplier"] = multiplier
    _TRAFFIC_CACHE["timestamp"] = now_ts
    return multiplier


# --------------------------------------------------------------------------
# Contextual Factor 3: Real-Time Weather Integration
# --------------------------------------------------------------------------

_WEATHER_CACHE = {
    "timestamp": 0.0,
    "data": {
        "temp_c": 22.0,
        "condition": "Clear",
        "weather_factor": 0.0,
        "summary": "22°C, Clear",
    },
}


def fetch_live_weather() -> dict:
    now_ts = time.time()
    if now_ts - _WEATHER_CACHE["timestamp"] < 600:
        return _WEATHER_CACHE["data"]

    openweather_key = os.environ.get("944c65db587556cae940016ce322f6d3")
    weather_info = {
        "temp_c": 22.0,
        "condition": "Clear",
        "weather_factor": 0.0,
        "summary": "22°C, Clear",
    }

    try:
        if openweather_key:
            url = f"https://api.openweathermap.org/data/2.5/weather?lat={MAP_CENTER[0]}&lon={MAP_CENTER[1]}&appid={openweather_key}&units=metric"
            req = urllib.request.Request(url, headers={"User-Agent": "YerevanParkingApp/1.0"})
            with urllib.request.urlopen(req, timeout=3) as resp:
                res = json.loads(resp.read().decode())
                temp = float(res["main"]["temp"])
                main_cond = res["weather"][0]["main"] if res.get("weather") else "Clear"

                w_factor = 0.0
                if "rain" in main_cond.lower() or "drizzle" in main_cond.lower():
                    w_factor = 0.6
                elif "snow" in main_cond.lower():
                    w_factor = 0.8
                elif temp > 35 or temp < 0:
                    w_factor = 0.4

                weather_info = {
                    "temp_c": round(temp, 1),
                    "condition": main_cond,
                    "weather_factor": round(w_factor, 2),
                    "summary": f"{round(temp)}°C, {main_cond}",
                }
        else:
            url = f"https://api.open-meteo.com/v1/forecast?latitude={MAP_CENTER[0]}&longitude={MAP_CENTER[1]}&current_weather=true"
            req = urllib.request.Request(url, headers={"User-Agent": "YerevanParkingApp/1.0"})
            with urllib.request.urlopen(req, timeout=3) as resp:
                res = json.loads(resp.read().decode())
                cw = res.get("current_weather", {})
                temp = float(cw.get("temperature", 22.0))
                wcode = int(cw.get("weathercode", 0))

                w_factor = 0.0
                cond = "Clear"
                if wcode in (1, 2, 3):
                    cond = "Cloudy"
                    w_factor = 0.1
                elif wcode in range(51, 68) or wcode in range(80, 83):
                    cond = "Rain"
                    w_factor = 0.6
                elif wcode in range(71, 78) or wcode in range(85, 87):
                    cond = "Snow"
                    w_factor = 0.8
                elif wcode >= 95:
                    cond = "Storm"
                    w_factor = 0.9
                elif temp > 35 or temp < 0:
                    w_factor = 0.4

                weather_info = {
                    "temp_c": round(temp, 1),
                    "condition": cond,
                    "weather_factor": round(w_factor, 2),
                    "summary": f"{round(temp)}°C, {cond}",
                }
    except Exception as exc:
        print(f"[weather] Live weather API call skipped/failed ({exc}); using neutral weather fallback.")

    _WEATHER_CACHE["timestamp"] = now_ts
    _WEATHER_CACHE["data"] = weather_info
    return weather_info


# --------------------------------------------------------------------------
# Data loading: Ground Truth > OSMnx Cache > OSMnx Fetch > Curated Fallback
# --------------------------------------------------------------------------

def _classify_segment(row: dict) -> str:
    has_fee = any(
        row.get(f"parking:{side}:fee") == "yes"
        for side in ["left", "right", "both", "lane"]
    )
    is_ticket = row.get("parking:condition") == "ticket"
    if row.get("amenity") == "parking":
        return "lot"
    if has_fee or is_ticket:
        return "paid"
    if any(row.get(f"parking:{side}") == "lane" for side in ["left", "right", "both"]):
        return "free"
    return "unspecified"


def _linestring_midpoint(coords: list[tuple[float, float]]) -> tuple[float, float]:
    mid = coords[len(coords) // 2]
    return mid


def _fetch_from_osmnx() -> list[dict]:
    import osmnx as ox

    gdf = ox.features_from_place(PLACE_NAME, tags=PARKING_TAGS)
    features = []

    for idx, row in gdf.iterrows():
        geom = row.geometry
        if geom is None:
            continue

        row_dict = row.to_dict()
        street_name = row_dict.get("name") or row_dict.get("addr:street") or "Unnamed segment"
        seg_id = hashlib.md5(str(idx).encode()).hexdigest()[:10]

        if geom.geom_type in ("LineString", "MultiLineString"):
            if geom.geom_type == "LineString":
                coords = [(lat, lon) for lon, lat in geom.coords]
            else:
                coords = []
                for line in geom.geoms:
                    coords.extend([(lat, lon) for lon, lat in line.coords])
            parking_type = _classify_segment(row_dict)
            if parking_type == "lot":
                parking_type = "unspecified"
            centroid = _linestring_midpoint(coords)
            features.append({
                "id": seg_id,
                "geometry_type": "LineString",
                "coordinates": [[lon, lat] for lat, lon in coords],
                "centroid": [centroid[1], centroid[0]],
                "name": street_name,
                "parking_type": parking_type,
            })

        elif geom.geom_type in ("Polygon", "MultiPolygon") and row_dict.get("amenity") == "parking":
            if geom.geom_type == "Polygon":
                coords = [(lat, lon) for lon, lat in geom.exterior.coords]
                rings = [[[lon, lat] for lat, lon in coords]]
            else:
                rings = []
                for poly in geom.geoms:
                    ring = [(lat, lon) for lon, lat in poly.exterior.coords]
                    rings.append([[lon, lat] for lat, lon in ring])
            centroid_point = geom.centroid
            features.append({
                "id": seg_id,
                "geometry_type": "Polygon",
                "coordinates": rings,
                "centroid": [centroid_point.x, centroid_point.y],
                "name": street_name,
                "parking_type": "lot",
            })

    if not features:
        raise RuntimeError("OSMnx returned no usable parking geometry.")
    return features


def _fallback_dataset() -> list[dict]:
    raw = [
        ("Northern Avenue", "paid", [
            [40.1808, 44.5122], [40.1795, 44.5133], [40.1783, 44.5144], [40.1772, 44.5155],
        ]),
        ("Abovyan Street", "paid", [
            [40.1839, 44.5138], [40.1820, 44.5128], [40.1800, 44.5119], [40.1781, 44.5110],
        ]),
        ("Mashtots Avenue", "free", [
            [40.1862, 44.5079], [40.1830, 44.5101], [40.1798, 44.5124], [40.1766, 44.5147],
        ]),
        ("Tumanyan Street", "paid", [
            [40.1858, 44.5057], [40.1841, 44.5093], [40.1824, 44.5129], [40.1807, 44.5165],
        ]),
        ("Sayat-Nova Avenue", "free", [
            [40.1861, 44.5169], [40.1838, 44.5150], [40.1815, 44.5131], [40.1792, 44.5112],
        ]),
        ("Komitas Avenue (south)", "unspecified", [
            [40.1915, 44.4990], [40.1888, 44.5015], [40.1861, 44.5040],
        ]),
        ("Baghramyan Avenue", "free", [
            [40.1868, 44.5028], [40.1846, 44.5065], [40.1824, 44.5102], [40.1802, 44.5139],
        ]),
        ("Isahakyan Street", "paid", [
            [40.1855, 44.5095], [40.1828, 44.5108], [40.1801, 44.5121], [40.1774, 44.5134],
        ]),
        ("Pushkin Street", "free", [
            [40.1830, 44.5065], [40.1812, 44.5097], [40.1794, 44.5129], [40.1776, 44.5161],
        ]),
        ("Amiryan Street", "paid", [
            [40.1835, 44.5147], [40.1812, 44.5138], [40.1789, 44.5129], [40.1766, 44.5120],
        ]),
        ("Vazgen Sargsyan Street", "unspecified", [
            [40.1801, 44.5175], [40.1783, 44.5157], [40.1765, 44.5139], [40.1747, 44.5121],
        ]),
        ("Khanjyan Street", "free", [
            [40.1849, 44.5117], [40.1826, 44.5109], [40.1803, 44.5101], [40.1780, 44.5093],
        ]),
        ("Grigor Lusavorich Street", "paid", [
            [40.1785, 44.5183], [40.1798, 44.5162], [40.1711, 44.5141], [40.1824, 44.5120],
        ]),
        ("Teryan Street", "unspecified", [
            [40.1826, 44.5062], [40.1808, 44.5090], [40.1790, 44.5118], [40.1772, 44.5146],
        ]),
        ("Moskovyan Street", "free", [
            [40.1845, 44.5079], [40.1822, 44.5106], [40.1799, 44.5133], [40.1776, 44.5160],
        ]),
    ]

    lots = [
        ("Republic Square Parking Lot", [
            [40.1780, 44.5140], [40.1786, 44.5150], [40.1778, 44.5158], [40.1772, 44.5148], [40.1780, 44.5140],
        ]),
        ("Opera Complex Parking Lot", [
            [40.1848, 44.5148], [40.1855, 44.5158], [40.1847, 44.5165], [40.1840, 44.5155], [40.1848, 44.5148],
        ]),
        ("Northern Avenue Underground Lot", [
            [40.1798, 44.5128], [40.1804, 44.5136], [40.1797, 44.5142], [40.1791, 44.5134], [40.1798, 44.5128],
        ]),
        ("GUM Market Parking Lot", [
            [40.1902, 44.5062], [40.1909, 44.5072], [40.1901, 44.5079], [40.1894, 44.5069], [40.1902, 44.5062],
        ]),
    ]

    features = []
    for name, ptype, latlon_coords in raw:
        seg_id = hashlib.md5(name.encode()).hexdigest()[:10]
        mid = latlon_coords[len(latlon_coords) // 2]
        features.append({
            "id": seg_id,
            "geometry_type": "LineString",
            "coordinates": [[lon, lat] for lat, lon in latlon_coords],
            "centroid": [mid[1], mid[0]],
            "name": name,
            "parking_type": ptype,
        })

    for name, ring in lots:
        seg_id = hashlib.md5(name.encode()).hexdigest()[:10]
        lats = [p[0] for p in ring]
        lons = [p[1] for p in ring]
        centroid = [sum(lons) / len(lons), sum(lats) / len(lats)]
        features.append({
            "id": seg_id,
            "geometry_type": "Polygon",
            "coordinates": [[[lon, lat] for lat, lon in ring]],
            "centroid": centroid,
            "name": name,
            "parking_type": "lot",
        })

    return features


def _extract_lat_lon(feature: dict) -> tuple[float, float]:
    if "centroid" in feature and feature["centroid"]:
        c0, c1 = feature["centroid"]
        if 38.0 <= c0 <= 42.0 and 43.0 <= c1 <= 47.0:
            return float(c0), float(c1)
        elif 38.0 <= c1 <= 42.0 and 43.0 <= c0 <= 47.0:
            return float(c1), float(c0)

    geom = feature.get("geometry", {}) if "geometry" in feature else feature
    props = feature.get("properties", {}) if "properties" in feature else feature
    
    if "centroid" in props and props["centroid"]:
        c0, c1 = props["centroid"]
        if 38.0 <= c0 <= 42.0 and 43.0 <= c1 <= 47.0:
            return float(c0), float(c1)
        elif 38.0 <= c1 <= 42.0 and 43.0 <= c0 <= 47.0:
            return float(c1), float(c0)

    coords = geom.get("coordinates", [])
    if not coords:
        return MAP_CENTER[0], MAP_CENTER[1]

    pts = coords
    while isinstance(pts, list) and len(pts) > 0 and isinstance(pts[0], list) and len(pts[0]) > 0 and isinstance(pts[0][0], list):
        pts = pts[0]
    if isinstance(pts, list) and len(pts) > 0 and isinstance(pts[0], list):
        pts = pts[0]

    try:
        avg_0 = sum(p[0] for p in pts) / len(pts)
        avg_1 = sum(p[1] for p in pts) / len(pts)
        if 38.0 <= avg_0 <= 42.0:
            return float(avg_0), float(avg_1)
        return float(avg_1), float(avg_0)
    except Exception:
        return MAP_CENTER[0], MAP_CENTER[1]


def _normalize_feature(f: dict) -> dict:
    props = f.get("properties", {}) if isinstance(f.get("properties"), dict) else f
    geom = f.get("geometry", {}) if isinstance(f.get("geometry"), dict) else f

    seg_id = str(f.get("id") or props.get("id") or "unk")
    raw_name = props.get("name") or f.get("name") or "Parking Segment"
    clean_name = raw_name if isinstance(raw_name, str) else "Unnamed Segment"

    parking_type = props.get("parking_type") or f.get("parking_type") or "free"
    geom_type = geom.get("type") or f.get("geometry_type") or "LineString"
    coords = geom.get("coordinates") or f.get("coordinates") or []

    lat, lon = _extract_lat_lon(f)

    return {
        "id": seg_id,
        "geometry_type": geom_type,
        "coordinates": coords,
        "centroid": [lon, lat],
        "name": clean_name,
        "parking_type": parking_type,
    }

def load_parking_features(force_refresh: bool = False) -> list[dict]:
    if not force_refresh and GROUND_TRUTH_FILE.exists():
        try:
            raw_features = json.loads(GROUND_TRUTH_FILE.read_text())["features"]
            features = [_normalize_feature(f) for f in raw_features]
            print(f"[data] Loaded {len(features)} ground-truth curated segments.")
            return features
        except Exception as exc:
            print(f"[data] Failed to load ground-truth dataset ({exc}). Falling back.")

    if not force_refresh and CACHE_FILE.exists():
        try:
            raw_features = json.loads(CACHE_FILE.read_text())["features"]
            return [_normalize_feature(f) for f in raw_features]
        except Exception:
            pass

    try:
        features = _fetch_from_osmnx()
        normalized = [_normalize_feature(f) for f in features]
        CACHE_FILE.write_text(json.dumps({"features": normalized}, ensure_ascii=False))
        print(f"[data] Loaded {len(normalized)} segments live from OSMnx and cached them.")
        return normalized
    except Exception as exc:
        print(f"[data] OSMnx fetch unavailable ({exc}); using curated offline dataset.")
        features = _fallback_dataset()
        normalized = [_normalize_feature(f) for f in features]
        CACHE_FILE.write_text(json.dumps({"features": normalized, "source": "fallback"}, ensure_ascii=False))
        return normalized

PARKING_FEATURES: list[dict] = load_parking_features()


def _save_ground_truth():
    GROUND_TRUTH_FILE.write_text(json.dumps({"features": PARKING_FEATURES}, ensure_ascii=False))


# --------------------------------------------------------------------------
# Base Simulated Real-Time Traffic / Availability Engine
# --------------------------------------------------------------------------

def _hour_congestion_curve(hour: int, is_weekend: bool) -> float:
    if is_weekend:
        curve = {
            0: .10, 1: .05, 2: .05, 3: .05, 4: .05, 5: .08, 6: .12, 7: .18,
            8: .25, 9: .35, 10: .45, 11: .55, 12: .60, 13: .60, 14: .58,
            15: .55, 16: .55, 17: .60, 18: .68, 19: .72, 20: .68, 21: .55,
            22: .35, 23: .18,
        }
    else:
        curve = {
            0: .08, 1: .05, 2: .04, 3: .04, 4: .04, 5: .06, 6: .15, 7: .40,
            8: .78, 9: .85, 10: .55, 11: .48, 12: .50, 13: .52, 14: .48,
            15: .50, 16: .58, 17: .80, 18: .90, 19: .82, 20: .60, 21: .38,
            22: .22, 23: .12,
        }
    return curve.get(hour, 0.3)


def simulate_segment_state(segment_id: str, parking_type: str, now: datetime | None = None) -> dict:
    if parking_type == "unavailable":
        return {
            "availability_pct": 0.0,
            "congestion_score": 0.0,
            "occupancy_status": "Unavailable",
            "traffic_level": "N/A",
        }

    now = now or datetime.now()
    is_weekend = now.weekday() >= 5
    base = _hour_congestion_curve(now.hour, is_weekend)
    next_hour_base = _hour_congestion_curve((now.hour + 1) % 24, is_weekend)
    frac = now.minute / 60.0
    congestion_factor = base + (next_hour_base - base) * frac

    seed_key = f"{segment_id}-{now.strftime('%Y%m%d%H%M')}"
    rng = random.Random(seed_key)
    jitter = rng.uniform(-9, 9)

    availability_pct = 100 - (congestion_factor * 100) + jitter

    type_adjust = {"free": -6, "paid": 6, "lot": 12, "unspecified": -2}
    availability_pct += type_adjust.get(parking_type, 0)
    availability_pct = max(3.0, min(97.0, availability_pct))

    congestion_score = round(100 - availability_pct, 1)

    if availability_pct >= 60:
        occupancy_status = "Available"
    elif availability_pct >= 28:
        occupancy_status = "Filling Fast"
    else:
        occupancy_status = "Occupied"

    if congestion_score < 35:
        traffic_level = "Low"
    elif congestion_score < 65:
        traffic_level = "Medium"
    else:
        traffic_level = "Heavy"

    return {
        "availability_pct": round(availability_pct, 1),
        "congestion_score": congestion_score,
        "occupancy_status": occupancy_status,
        "traffic_level": traffic_level,
    }


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


# --------------------------------------------------------------------------
# Routes: pages & PWA
# --------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template(
        "index.html",
        center_lat=MAP_CENTER[0],
        center_lon=MAP_CENTER[1],
        type_colors=TYPE_COLORS,
    )


@app.route("/manifest.json")
def pwa_manifest():
    manifest_data = {
        "name": "Yerevan Smart Parking Recommender",
        "short_name": "SmartParking",
        "description": "Live-simulated curb & lot availability across central Yerevan.",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#14151a",
        "theme_color": "#14151a",
        "icons": [
            {
                "src": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/ca/MUTCD_D4-1.svg/192px-MUTCD_D4-1.svg.png",
                "sizes": "192x192",
                "type": "image/png"
            },
            {
                "src": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/ca/MUTCD_D4-1.svg/512px-MUTCD_D4-1.svg.png",
                "sizes": "512x512",
                "type": "image/png"
            }
        ]
    }
    return jsonify(manifest_data)


@app.route("/sw.js")
def service_worker():
    js = """
    const CACHE_NAME = 'yerevan-parking-v1';
    const urlsToCache = [
        '/',
        'https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=Inter:wght@400;500;600;700&display=swap',
        'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css',
        'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js',
        'https://unpkg.com/@geoman-io/leaflet-geoman-free@latest/dist/leaflet-geoman.css',
        'https://unpkg.com/@geoman-io/leaflet-geoman-free@latest/dist/leaflet-geoman.js'
    ];

    self.addEventListener('install', event => {
        event.waitUntil(
            caches.open(CACHE_NAME).then(cache => cache.addAll(urlsToCache))
        );
    });

    self.addEventListener('fetch', event => {
        event.respondWith(
            caches.match(event.request).then(response => {
                if (response) {
                    return response;
                }
                return fetch(event.request);
            })
        );
    });
    """
    response = make_response(js)
    response.headers['Content-Type'] = 'application/javascript'
    return response


# --------------------------------------------------------------------------
# Routes: Search & Geocoding Autocomplete API
# --------------------------------------------------------------------------

@app.route("/api/search")
def api_search():
    """
    Search-as-you-type endpoint for addresses & POIs in Yerevan.
    Handles typos, fuzzy matching, and exact house numbers (e.g. Mashtots 23/6).
    Returns [] if no address matches exist.
    """
    query = request.args.get("q", "").strip()
    if not query or len(query) < 2:
        return jsonify([])

    # Apply synonym/transliteration normalization for common street names
    normalized_q = query.lower()
    for syn, target in YEREVAN_STREET_SYNONYMS.items():
        if syn in normalized_q:
            normalized_q = normalized_q.replace(syn, target.lower())

    results = []
    seen_keys = set()

    # 1. Local POIs & Ground-Truth Segments Fuzzy Match
    for poi in FALLBACK_POIS:
        p_name = poi["name"]
        if normalized_q in p_name.lower() or query.lower() in p_name.lower():
            key = p_name.lower()
            if key not in seen_keys:
                seen_keys.add(key)
                results.append({
                    "title": p_name,
                    "subtitle": f"Landmark ({poi['type'].replace('_', ' ').title()}) • Kentron, Yerevan",
                    "lat": poi["lat"],
                    "lon": poi["lon"],
                })

    for f in PARKING_FEATURES:
        f_name = f.get("name", "")
        if f_name and f_name != "Unnamed Segment":
            if normalized_q in f_name.lower() or query.lower() in f_name.lower():
                key = f_name.lower()
                if key not in seen_keys:
                    seen_keys.add(key)
                    lat, lon = _extract_lat_lon(f)
                    results.append({
                        "title": f_name,
                        "subtitle": "Street / Parking Segment • Yerevan",
                        "lat": lat,
                        "lon": lon,
                    })

    # 2. Photon API for fast search-as-you-type and typo tolerance
    try:
        search_term = urllib.parse.quote(normalized_q)
        photon_url = f"https://photon.komoot.io/api/?q={search_term}&lat=40.1792&lon=44.5152&zoom=14&limit=8&bbox=44.40,40.10,44.60,40.25"
        req = urllib.request.Request(photon_url, headers={"User-Agent": "YerevanParkingApp/1.0"})
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            data = json.loads(resp.read().decode())
            for feat in data.get("features", []):
                props = feat.get("properties", {})
                coords = feat.get("geometry", {}).get("coordinates", [])
                if len(coords) == 2:
                    lon, lat = coords[0], coords[1]
                    housenumber = props.get("housenumber", "")
                    street = props.get("street") or props.get("name") or ""
                    city = props.get("city") or props.get("town") or "Yerevan"

                    if street:
                        title = f"{street} {housenumber}".strip() if housenumber else street
                    else:
                        title = props.get("name", "")

                    if not title:
                        continue

                    sub_parts = [p for p in [props.get("district"), city, "Armenia"] if p]
                    subtitle = ", ".join(sub_parts)

                    key = f"{title.lower()}:{round(lat, 4)}:{round(lon, 4)}"
                    if key not in seen_keys and title.lower() not in seen_keys:
                        seen_keys.add(key)
                        seen_keys.add(title.lower())
                        results.append({
                            "title": title,
                            "subtitle": subtitle,
                            "lat": lat,
                            "lon": lon,
                        })
    except Exception as exc:
        print(f"[search] Photon API call skipped/failed ({exc})")

    # 3. OpenStreetMap Nominatim for exact address/building numbers (e.g., "Mashtots 23/6")
    if len(results) < 4 or "/" in query or any(char.isdigit() for char in query):
        try:
            nom_q = urllib.parse.quote(f"{normalized_q}, Yerevan, Armenia")
            nom_url = f"https://nominatim.openstreetmap.org/search?q={nom_q}&format=json&limit=5&bounded=0&viewbox=44.40,40.22,44.60,40.12"
            req = urllib.request.Request(nom_url, headers={"User-Agent": "YerevanParkingApp/1.0"})
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                data = json.loads(resp.read().decode())
                for item in data:
                    lat = float(item["lat"])
                    lon = float(item["lon"])
                    display_name = item.get("display_name", "")
                    parts = [p.strip() for p in display_name.split(",")]
                    title = ", ".join(parts[:2]) if len(parts) >= 2 else parts[0]
                    subtitle = ", ".join(parts[2:4]) if len(parts) >= 4 else "Yerevan, Armenia"

                    key = f"{title.lower()}:{round(lat, 4)}:{round(lon, 4)}"
                    if key not in seen_keys and title.lower() not in seen_keys:
                        seen_keys.add(key)
                        seen_keys.add(title.lower())
                        results.append({
                            "title": title,
                            "subtitle": subtitle,
                            "lat": lat,
                            "lon": lon,
                        })
        except Exception as exc:
            print(f"[search] Nominatim API call skipped/failed ({exc})")

    return jsonify(results[:8])


# --------------------------------------------------------------------------
# Routes: System APIs
# --------------------------------------------------------------------------

@app.route("/api/weather")
def api_weather():
    return jsonify(fetch_live_weather())


@app.route("/api/parking")
def api_parking():
    now = datetime.now()
    geojson_features = []

    for f in PARKING_FEATURES:
        state = simulate_segment_state(f["id"], f["parking_type"], now)

        if f["geometry_type"] == "LineString":
            geometry = {"type": "LineString", "coordinates": f["coordinates"]}
        else:
            geometry = {"type": "Polygon", "coordinates": f["coordinates"]}

        geojson_features.append({
            "type": "Feature",
            "geometry": geometry,
            "properties": {
                "id": f["id"],
                "name": f["name"],
                "parking_type": f["parking_type"],
                "color": TYPE_COLORS.get(f["parking_type"], "#7f8c8d"),
                **state,
            },
        })

    return jsonify({
        "type": "FeatureCollection",
        "generated_at": now.isoformat(),
        "features": geojson_features,
    })


@app.route("/api/traffic")
def api_traffic():
    now = datetime.now()
    by_street: dict[str, list[dict]] = {}

    for f in PARKING_FEATURES:
        if f["parking_type"] == "unavailable":
            continue
        state = simulate_segment_state(f["id"], f["parking_type"], now)
        by_street.setdefault(f["name"], []).append(state)

    rows = []
    for name, states in by_street.items():
        avg_congestion = sum(s["congestion_score"] for s in states) / len(states)
        avg_availability = sum(s["availability_pct"] for s in states) / len(states)
        if avg_congestion < 35:
            level = "Low"
        elif avg_congestion < 65:
            level = "Medium"
        else:
            level = "Heavy"
        rows.append({
            "name": name,
            "traffic_level": level,
            "congestion_score": round(avg_congestion, 1),
            "availability_pct": round(avg_availability, 1),
        })

    rows.sort(key=lambda r: r["congestion_score"], reverse=True)

    overall_avg = sum(r["congestion_score"] for r in rows) / len(rows) if rows else 0
    overall_level = "Low" if overall_avg < 35 else ("Medium" if overall_avg < 65 else "Heavy")

    return jsonify({
        "generated_at": now.isoformat(),
        "overall_level": overall_level,
        "overall_congestion_score": round(overall_avg, 1),
        "streets": rows,
    })


@app.route("/api/recommend")
def api_recommend():
    try:
        dest_lat = float(request.args.get("lat"))
        dest_lon = float(request.args.get("lon"))
    except (TypeError, ValueError):
        return jsonify({"error": "Query params 'lat' and 'lon' are required and must be numeric."}), 400

    requested_radius = float(request.args.get("radius", 500))
    now = datetime.now()

    traffic_mult = fetch_live_traffic_multiplier()
    weather_info = fetch_live_weather()
    weather_factor = weather_info["weather_factor"]

    for current_radius in [requested_radius, 1500.0, 3000.0]:
        candidates = []
        for f in PARKING_FEATURES:
            if f.get("parking_type") == "unavailable":
                continue

            lat, lon = _extract_lat_lon(f)
            distance_m = haversine_m(dest_lat, dest_lon, lat, lon)
            if distance_m > current_radius:
                continue

            segment_id = f.get("id", f.get("properties", {}).get("id", "unk"))
            parking_type = f.get("parking_type", f.get("properties", {}).get("parking_type", "curbside"))
            
            state = simulate_segment_state(segment_id, parking_type, now)
            dest_busyness = calculate_destination_busyness(lat, lon, now)

            adjusted_congestion = min(100.0, state["congestion_score"] * traffic_mult)
            traffic_factor = round(adjusted_congestion / 100.0, 2)

            adjusted_avail = max(3.0, min(97.0, state["availability_pct"] - (dest_busyness * 20.0) - (weather_factor * 6.0)))

            busyness_component = (1.0 - dest_busyness) * 25.0
            avail_component = (adjusted_avail / 100.0) * 20.0
            type_weight = TYPE_BASE_WEIGHT.get(parking_type, 45)
            type_component = (type_weight / 100.0) * 10.0
            traffic_component = (1.0 - traffic_factor) * 8.0
            distance_component = max(0.0, 1.0 - (distance_m / current_radius)) * 35.0
            weather_component = (1.0 - weather_factor) * 2.0

            final_score = round(
                busyness_component + avail_component + type_component + traffic_component + distance_component + weather_component,
                1,
            )

            busyness_level = "High" if dest_busyness >= 0.65 else ("Moderate" if dest_busyness >= 0.35 else "Low")
            traffic_level_label = "High" if traffic_factor >= 0.65 else ("Moderate" if traffic_factor >= 0.35 else "Low")
            weather_level_label = "High" if weather_factor >= 0.6 else ("Moderate" if weather_factor >= 0.3 else "Low")

            occ_status = "Available" if adjusted_avail >= 60 else ("Filling Fast" if adjusted_avail >= 28 else "Occupied")

            raw_name = f.get("name", f.get("properties", {}).get("name", "Parking Segment"))
            clean_name = raw_name if isinstance(raw_name, str) else "Unnamed Segment"

            candidates.append({
                "id": segment_id,
                "name": clean_name,
                "parking_type": parking_type,
                "color": TYPE_COLORS.get(parking_type, "#7f8c8d"),
                "location": {"lat": lat, "lon": lon},
                "distance_m": round(distance_m, 1),
                "walk_time_min": max(1, round(distance_m / 80)),
                "score": final_score,
                "final_score": final_score,
                "availability_pct": round(adjusted_avail, 1),
                "congestion_score": round(adjusted_congestion, 1),
                "occupancy_status": occ_status,
                "traffic_level": state["traffic_level"],
                "destination_busyness": dest_busyness,
                "destination_busyness_level": busyness_level,
                "traffic_factor": traffic_factor,
                "traffic_impact_level": traffic_level_label,
                "weather_factor": weather_factor,
                "weather_impact_level": weather_level_label,
                "weather_summary": weather_info["summary"],
            })

        if candidates:
            break

    candidates.sort(key=lambda c: c["final_score"], reverse=True)
    top3 = candidates[:3]

    return jsonify({
        "destination": {"lat": dest_lat, "lon": dest_lon},
        "radius_m": current_radius,
        "generated_at": now.isoformat(),
        "candidates_considered": len(candidates),
        "weather": weather_info,
        "live_traffic_multiplier": traffic_mult,
        "recommendations": top3,
    })


@app.route("/api/admin/feature", methods=["POST"])
def api_admin_save_feature():
    global PARKING_FEATURES
    data = request.json
    if not data:
        return jsonify({"error": "Invalid or empty payload."}), 400

    normalized = _normalize_feature(data)

    if not normalized["id"] or normalized["id"] == "unk":
        return jsonify({"error": "Segment missing a valid ID."}), 400

    updated = False
    for i, f in enumerate(PARKING_FEATURES):
        if f["id"] == normalized["id"]:
            PARKING_FEATURES[i] = normalized
            updated = True
            break

    if not updated:
        PARKING_FEATURES.append(normalized)

    _save_ground_truth()

    return jsonify({
        "status": "ok",
        "action": "updated" if updated else "created",
        "id": normalized["id"],
        "total_segments": len(PARKING_FEATURES),
    })


@app.route('/api/admin/ml_feedback', methods=['POST'])
def log_ml_feedback():
    data = request.get_json()
    
    # Validate data
    if not data or 'lat' not in data or 'lon' not in data:
        return jsonify({"error": "Missing location data"}), 400
    
    # Save globally to the SQL database
    new_entry = MLFeedback(lat=data['lat'], lon=data['lon'])
    db.session.add(new_entry)
    db.session.commit()
    
    return jsonify({"status": "success"})


if __name__ == "__main__":
    print("[server] Starting Yerevan Smart Parking Recommender server on http://127.0.0.1:5000")
    app.run(host="127.0.0.1", port=5000, debug=True)
