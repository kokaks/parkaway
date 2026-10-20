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
  6. Serves a rolled-up live traffic snapshot (/api/traffic), including a 0-10
     `overall_traffic_score` for the circular traffic badge.
  7. Serves an administrative curation API (/api/admin/feature).
  8. Serves an ML feedback recording API (/api/admin/ml_feedback).
  9. Serves a live search/autocomplete geocoding engine (/api/search). Each result
     carries a `kind` (landmark | street | address) and a `distance_m` from the
     caller (or the map centre) so the UI can render Yandex-style result rows.
 10. Detects parking automatically: devices stream location pings to
     /api/trip/ping while driving and the backend decides when the car has
     stopped for good (replaces the old manual "I Parked Here" endpoint).
 11. Serves the brand logo as vector icons (/icon.svg, /icon-maskable.svg) used
     by the tab icon, the PWA manifest and the iOS home-screen icon.

Run:
    pip install -r requirements.txt
    python app.py
Then open http://127.0.0.1:5000
"""

from __future__ import annotations

from flask_sqlalchemy import SQLAlchemy
import hashlib
import hmac
import json
import math
import os
import random
import re
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path

from flask import Flask, jsonify, render_template, request, make_response, session

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

# Max distance (meters) between a logged GPS parking spot and a recommended
# candidate location for that spot to be considered a "match" against the
# recommendation engine's output.
RECOMMENDATION_MATCH_RADIUS_M = 40.0

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
def _resolve_database_url() -> str:
    """
    Normalises DATABASE_URL and matches its driver to what is actually installed.
    Render hands out postgres:// or postgresql:// URLs; SQLAlchemy then defaults to
    psycopg2, while a postgresql+psycopg:// URL needs psycopg (v3). Whichever one
    the URL asks for, fall back to the other if only that one is installed, so a
    mismatch between the URL and requirements.txt can't crash the deploy.
    """
    import importlib.util
    url = os.environ.get('DATABASE_URL', 'sqlite:///local_parking.db')
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if not url.startswith("postgresql"):
        return url

    scheme, rest = url.split("://", 1)
    wanted = scheme.split("+", 1)[1] if "+" in scheme else None
    have_v3 = importlib.util.find_spec("psycopg") is not None
    have_v2 = importlib.util.find_spec("psycopg2") is not None

    # Always name the driver explicitly. Newer SQLAlchemy releases changed what a bare
    # postgresql:// URL means (psycopg2 -> psycopg v3), so relying on the default breaks
    # whenever the installed SQLAlchemy and the installed driver disagree.
    driver = wanted
    if wanted in (None, "psycopg2") and have_v2:
        driver = "psycopg2"
    elif wanted in (None, "psycopg2") and have_v3:
        driver = "psycopg"
    elif wanted == "psycopg" and not have_v3 and have_v2:
        driver = "psycopg2"
    print(f"[db] PostgreSQL drivers installed: psycopg2={have_v2}, psycopg={have_v3}; "
          f"URL asked for '{wanted or 'default'}', using '{driver or 'psycopg2 (SQLAlchemy default)'}'.")
    if not (have_v2 or have_v3):
        raise RuntimeError(
            "DATABASE_URL points at PostgreSQL but no PostgreSQL driver is installed in this build. "
            "Add 'psycopg2-binary' to requirements.txt (repo root), push, and check the Render build log "
            "shows it being installed.")
    return f"postgresql+{driver}://{rest}" if driver else f"postgresql://{rest}"


app.config['SQLALCHEMY_DATABASE_URI'] = _resolve_database_url()
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --------------------------------------------------------------------------
# Security Configuration
# --------------------------------------------------------------------------
# SECRET_KEY signs the admin login session cookie. If it's not set via
# environment variable, we fall back to a random one generated at process
# startup - which means every admin session gets invalidated whenever the
# process restarts (Render free-tier services restart often: on every
# deploy, and after idle spin-down). Set SECRET_KEY in Render's environment
# variables (Settings -> Environment) to a long random string so your login
# persists normally. Generate one with: python -c "import secrets; print(secrets.token_hex(32))"
_env_secret = os.environ.get("SECRET_KEY")
if not _env_secret:
    print("[WARNING] SECRET_KEY not set - using a random key for this process only. "
          "Admin logins will be lost on every restart until you set SECRET_KEY in your environment.")
app.secret_key = _env_secret or secrets.token_hex(32)

# ADMIN_PASSWORD gates access to Admin/Curation Mode (adding, editing, and
# deleting parking segments). This must be set via environment variable -
# there is no hardcoded default, and if it's missing, admin mode is fully
# disabled (fails closed, not open) rather than silently accessible to
# anyone. Set it in Render's environment variables (Settings -> Environment).
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")
if not ADMIN_PASSWORD:
    print("[WARNING] ADMIN_PASSWORD not set - Admin/Curation Mode is disabled until you set it "
          "in your environment variables.")

app.config.update(
    SESSION_COOKIE_HTTPONLY=True,      # JS can't read the session cookie (mitigates XSS cookie theft)
    SESSION_COOKIE_SAMESITE="Lax",     # basic CSRF mitigation for the login/admin endpoints
    SESSION_COOKIE_SECURE=os.environ.get("RENDER") is not None,  # only require HTTPS in real deployment; allow local http dev
    PERMANENT_SESSION_LIFETIME=timedelta(hours=float(os.environ.get("ADMIN_SESSION_HOURS", "2"))),
    MAX_CONTENT_LENGTH=1 * 1024 * 1024,  # reject request bodies over 1MB (basic DoS/abuse guard)
)

# Google Analytics 4 measurement ID, injected into the page template only if
# set. Leave GA4_MEASUREMENT_ID unset locally/for testing so analytics never
# fires outside of the real production deployment.
GA4_MEASUREMENT_ID = os.environ.get("GA4_MEASUREMENT_ID", "")


# --------------------------------------------------------------------------
# Lightweight in-memory rate limiting
# --------------------------------------------------------------------------
# NOTE: this is per-process, in-memory rate limiting. It's a pragmatic,
# dependency-free guard against casual abuse/spam for a small public app - it
# is NOT a substitute for a real distributed limiter (e.g. Redis-backed) if
# this app ever runs with multiple gunicorn workers or scales to multiple
# instances, since each process keeps its own counts. For this app's scale
# (a single small Render web service), it's a meaningful, cheap improvement.
_rate_limit_store: dict[str, list[float]] = defaultdict(list)

def _check_rate_limit(key: str, max_requests: int, window_seconds: float) -> bool:
    """Returns True if the request is allowed, False if the caller has exceeded
    max_requests within window_seconds. Records the request if allowed."""
    now = time.time()
    bucket = _rate_limit_store[key]
    cutoff = now - window_seconds
    while bucket and bucket[0] < cutoff:
        bucket.pop(0)
    if len(bucket) >= max_requests:
        return False
    bucket.append(now)
    return True


def _client_ip() -> str:
    # Render sits behind a proxy; the real client IP is in X-Forwarded-For.
    fwd = request.headers.get("X-Forwarded-For", "")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.remote_addr or "unknown"


@app.before_request
def _global_rate_limit():
    if not request.path.startswith("/api/"):
        return None
    # Generous general ceiling per IP across all API endpoints, mainly to
    # protect the database (and its free-tier compute-hour budget) from a
    # runaway script or bot rather than to constrain normal human usage.
    if not _check_rate_limit(f"global:{_client_ip()}", max_requests=120, window_seconds=60):
        return jsonify({"error": "Too many requests. Please slow down and try again shortly."}), 429
    return None


def require_admin(view_func):
    """Decorator: blocks a route unless the caller has an authenticated admin session."""
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not session.get("is_admin"):
            return jsonify({"error": "Admin login required."}), 401
        return view_func(*args, **kwargs)
    return wrapped


@app.after_request
def _set_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    # Fairly permissive script/style-src (the app relies on inline <script>
    # and inline styles) but still meaningfully restricts which origins can
    # be loaded from, blocks the app from being framed by another site
    # (clickjacking), and blocks plugin/object embeds entirely.
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com https://unpkg.com https://www.googletagmanager.com; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdnjs.cloudflare.com https://unpkg.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data: https:; "
        "connect-src 'self' https:; "
        "object-src 'none'; "
        "frame-ancestors 'none'"
    )
    if os.environ.get("RENDER"):
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

# --------------------------------------------------------------------------
# Machine Learning Feedback & Admin Data Models (PostgreSQL)
# --------------------------------------------------------------------------
class MLFeedback(db.Model):
    __tablename__ = 'ml_feedback'

    id = db.Column(db.Integer, primary_key=True)
    
    # Core Spatial Data
    lat = db.Column(db.Float, nullable=False)
    lon = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    # Temporal Derivations (Zero-Friction ML Features)
    hour = db.Column(db.Integer, nullable=False)
    day_of_week = db.Column(db.Integer, nullable=False)  # 0 = Monday, 6 = Sunday
    is_weekend = db.Column(db.Boolean, nullable=False)

    # Spatial Context & Segment Matching
    matched_segment_id = db.Column(db.String(64), nullable=True, index=True)
    parking_type = db.Column(db.String(32), nullable=True)
    distance_to_segment_m = db.Column(db.Float, nullable=True)

    # Real-Time Contextual Factors
    destination_busyness = db.Column(db.Float, nullable=True)
    traffic_multiplier = db.Column(db.Float, nullable=True)
    weather_condition = db.Column(db.String(32), nullable=True)
    weather_factor = db.Column(db.Float, nullable=True)
    temp_c = db.Column(db.Float, nullable=True)

    # System Simulation Baseline (At logging instant)
    simulated_availability_pct = db.Column(db.Float, nullable=True)
    simulated_congestion_score = db.Column(db.Float, nullable=True)

    # Destination Context (the point the user was navigating to, if any)
    dest_lat = db.Column(db.Float, nullable=True)
    dest_lon = db.Column(db.Float, nullable=True)
    distance_parking_to_destination_m = db.Column(db.Float, nullable=True)

    # Recommendation-Match Ground Truth
    parked_at_recommended_spot = db.Column(db.Boolean, nullable=True)
    recommended_rank_matched = db.Column(db.Integer, nullable=True)
    distance_to_nearest_recommendation_m = db.Column(db.Float, nullable=True)

class ParkingSegment(db.Model):
    __tablename__ = 'parking_segments'

    id = db.Column(db.String(64), primary_key=True)
    name = db.Column(db.String(128))
    parking_type = db.Column(db.String(32))
    geometry_type = db.Column(db.String(32))
    coordinates = db.Column(db.JSON, nullable=False)
    centroid_lat = db.Column(db.Float)
    centroid_lon = db.Column(db.Float)


class TripSession(db.Model):
    """Short-lived state for one drive, used to decide when the car was parked.
    Holds a few anchor points (never the route) and is deleted within hours."""
    __tablename__ = 'trip_sessions'

    id = db.Column(db.String(64), primary_key=True)          # random id generated by the device
    created_at = db.Column(db.Float, nullable=False)          # unix seconds
    updated_at = db.Column(db.Float, nullable=False, index=True)
    state = db.Column(db.String(16), nullable=False, default='tracking', index=True)  # tracking|driving|stopped|parked|discarded
    dest_lat = db.Column(db.Float, nullable=True)
    dest_lon = db.Column(db.Float, nullable=True)
    last_lat = db.Column(db.Float, nullable=True)
    last_lon = db.Column(db.Float, nullable=True)
    last_speed = db.Column(db.Float, nullable=True)
    last_ts = db.Column(db.Float, nullable=True)
    drive_lat = db.Column(db.Float, nullable=True)            # where the car last moved at vehicle speed
    drive_lon = db.Column(db.Float, nullable=True)
    drive_ts = db.Column(db.Float, nullable=True)
    drive_seconds = db.Column(db.Float, default=0.0)
    drive_distance_m = db.Column(db.Float, default=0.0)
    max_speed = db.Column(db.Float, default=0.0)
    last_charging = db.Column(db.Boolean, nullable=True)
    power_lost_ts = db.Column(db.Float, nullable=True)        # phone unplugged from a charger after driving
    log_id = db.Column(db.Integer, nullable=True)             # MLFeedback row written when parked
    announced = db.Column(db.Boolean, default=False)          # client has been told about the parking event


class ParkingDetection(db.Model):
    """How an MLFeedback row came to exist automatically (kept apart so ml_feedback keeps its schema)."""
    __tablename__ = 'parking_detections'

    id = db.Column(db.Integer, primary_key=True)
    ml_feedback_id = db.Column(db.Integer, index=True)
    source = db.Column(db.String(24))        # auto_dwell | auto_destination | auto_charger | auto_signal_loss
    confidence = db.Column(db.Float)
    dwell_seconds = db.Column(db.Float)
    drive_seconds = db.Column(db.Float)
    drive_distance_m = db.Column(db.Float)
    near_destination = db.Column(db.Boolean)
    charger_unplugged = db.Column(db.Boolean)
    segment_name = db.Column(db.String(128))
    undo_token = db.Column(db.String(32))
    undone = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

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
            parking_type = _classify_segment(row_dict)
            if parking_type == "lot":
                parking_type = "unspecified"

            if geom.geom_type == "LineString":
                coords = [(lat, lon) for lon, lat in geom.coords]
                centroid = _linestring_midpoint(coords)
                features.append({
                    "id": seg_id,
                    "geometry_type": "LineString",
                    "coordinates": [[lon, lat] for lat, lon in coords],
                    "centroid": [centroid[1], centroid[0]],
                    "name": street_name,
                    "parking_type": parking_type,
                })
            else:
                # IMPORTANT: a MultiLineString is a set of *disconnected* road
                # pieces (e.g. a street split by an intersection). They must
                # NOT be concatenated into one flat coordinate list, or the
                # renderer will draw a spurious straight line connecting the
                # end of one piece to the start of the next, unrelated piece
                # (the "spiderweb" artifact). Keep each piece as its own
                # nested line so the geometry stays a true MultiLineString.
                lines = [[(lat, lon) for lon, lat in line.coords] for line in geom.geoms]
                centroid = _linestring_midpoint(lines[0]) if lines else (MAP_CENTER[0], MAP_CENTER[1])
                features.append({
                    "id": seg_id,
                    "geometry_type": "MultiLineString",
                    "coordinates": [[[lon, lat] for lat, lon in line] for line in lines],
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
            [40.1785, 44.5183], [40.1774, 44.5162], [40.1763, 44.5141], [40.1752, 44.5120],
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
    # NOTE: the while loop above already unwraps Polygon/MultiLineString rings
    # down to a flat list of [lon, lat] points. Do NOT unwrap again here -
    # doing so used to strip off a normal 2+ point LineString down to just
    # its first point, which made the averaging below throw and silently
    # fall back to MAP_CENTER. That meant every segment added through Admin
    # Mode got mislocated to the exact center of Kentron for distance-based
    # recommendation purposes (even though it still drew correctly on the
    # map, since the map uses the raw coordinates, not this centroid).

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

    seg_id = str(f.get("id") or props.get("id") or "unk").strip()[:64]
    raw_name = props.get("name") or f.get("name") or "Parking Segment"
    clean_name = raw_name if isinstance(raw_name, str) else "Unnamed Segment"
    clean_name = clean_name.strip()[:120] or "Parking Segment"  # matches db.String(128) column with margin

    parking_type = props.get("parking_type") or f.get("parking_type") or "free"
    if parking_type not in TYPE_BASE_WEIGHT:
        parking_type = "unspecified"
    geom_type = geom.get("type") or f.get("geometry_type") or "LineString"
    if geom_type not in ("LineString", "Polygon", "MultiLineString"):
        geom_type = "LineString"
    
    coords = geom.get("coordinates") or f.get("coordinates") or []
    
    # Force parse stringified JSON coordinates
    if isinstance(coords, str):
        try:
            coords = json.loads(coords)
            if isinstance(f.get("geometry"), dict):
                f["geometry"]["coordinates"] = coords
            else:
                f["coordinates"] = coords
        except Exception:
            pass

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

# Set global store for caching, hydrated below inside app context
PARKING_FEATURES: list[dict] = []

with app.app_context():
    db.create_all()
    
    # Load parking segments from DB; seed if empty.
    segments = ParkingSegment.query.all()
    if not segments:
        print("[data] PostgreSQL 'parking_segments' table is empty. Seeding initial data...")
        initial_features = load_parking_features(force_refresh=True)
        for f in initial_features:
            lat, lon = _extract_lat_lon(f)
            seg = ParkingSegment(
                id=f["id"],
                name=f["name"],
                parking_type=f["parking_type"],
                geometry_type=f["geometry_type"],
                coordinates=f["coordinates"],
                centroid_lat=lat,
                centroid_lon=lon
            )
            db.session.add(seg)
        db.session.commit()
        PARKING_FEATURES = initial_features
        print(f"[data] Successfully seeded {len(PARKING_FEATURES)} segments into PostgreSQL.")
    else:
        print(f"[data] Loaded {len(segments)} segments from PostgreSQL database.")
        for s in segments:
            coords = s.coordinates
            
            # Ensure coordinates are a parsed list, not a string
            if isinstance(coords, str):
                try:
                    coords = json.loads(coords)
                except Exception:
                    pass
            
            c_lat = s.centroid_lat
            c_lon = s.centroid_lon
            
            # Self-heal corrupted centroids that defaulted to MAP_CENTER due to previous errors
            if c_lat == MAP_CENTER[0] and c_lon == MAP_CENTER[1] and coords:
                c_lat, c_lon = _extract_lat_lon({"coordinates": coords})
                
            PARKING_FEATURES.append({
                "id": s.id,
                "name": s.name,
                "parking_type": s.parking_type,
                "geometry_type": s.geometry_type,
                "coordinates": coords,
                "centroid": [c_lon, c_lat]
            })

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
        ga4_id=GA4_MEASUREMENT_ID,
    )

_LOGO_BG_PATH = "M73 0H251C290 0 324 34 324 73V251C324 290 290 324 251 324H73C34 324 0 290 0 251V73C0 34 34 0 73 0Z"
_LOGO_GLYPH_PATHS = (
    "M56.5 77.5 L101.5 122.5 L56.5 122.5 L56.5 152.5 L152.5 152.5 L152.5 56.5 L122.5 56.5 L122.5 101.5 L77.5 56.5Z",
    "M267.5 77.5 L222.5 122.5 L267.5 122.5 L267.5 152.5 L171.5 152.5 L171.5 56.5 L201.5 56.5 L201.5 101.5 L246.5 56.5Z",
    "M56.5 246.5 L101.5 201.5 L56.5 201.5 L56.5 171.5 L152.5 171.5 L152.5 267.5 L122.5 267.5 L122.5 222.5 L77.5 267.5Z",
    "M267.5 246.5 L222.5 201.5 L267.5 201.5 L267.5 171.5 L171.5 171.5 L171.5 267.5 L201.5 267.5 L201.5 222.5 L246.5 267.5Z",
)


def _logo_svg(maskable: bool = False) -> str:
    """The parkaway logo as pure vector geometry (traced from the brand artwork).
    maskable=True gives the full-bleed square with the mark inside the safe zone,
    for Android adaptive icons and the iOS home screen (both round the corners themselves)."""
    glyph = "".join(f"<path d='{d}'/>" for d in _LOGO_GLYPH_PATHS)
    if maskable:
        body = (f"<rect width='324' height='324' fill='#E9BB95'/>"
                f"<g fill='#252121' transform='translate(162 162) scale(.78) translate(-162 -162)'>{glyph}</g>")
    else:
        body = f"<path fill='#E9BB95' d='{_LOGO_BG_PATH}'/><g fill='#252121'>{glyph}</g>"
    return f"<svg xmlns='http://www.w3.org/2000/svg' width='324' height='324' viewBox='0 0 324 324'>{body}</svg>"


def _svg_response(svg: str):
    resp = make_response(svg)
    resp.headers["Content-Type"] = "image/svg+xml; charset=utf-8"
    resp.headers["Cache-Control"] = "public, max-age=86400"
    return resp


@app.route("/icon.svg")
def icon_svg():
    return _svg_response(_logo_svg())


@app.route("/icon-maskable.svg")
def icon_maskable_svg():
    return _svg_response(_logo_svg(maskable=True))


@app.route("/manifest.json")
def pwa_manifest():
    manifest_data = {
        "name": "parkaway – Yerevan Smart Parking",
        "short_name": "parkaway",
        "categories": ["navigation", "travel"],
        "description": "Live-simulated curb & lot availability across central Yerevan.",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#E9BB95",
        "theme_color": "#14151a",
        "icons": [
            {"src": "/icon.svg", "sizes": "any", "type": "image/svg+xml", "purpose": "any"},
            {"src": "/icon-maskable.svg", "sizes": "any", "type": "image/svg+xml", "purpose": "maskable"}
        ]
    }
    return jsonify(manifest_data)

@app.route("/sw.js")
def service_worker():
    js = """
    // Bump this on every deploy that changes app behavior. Changing the name
    // makes old caches orphaned so they get cleaned up in 'activate' below.
    const CACHE_NAME = 'yerevan-parking-v5';
    const STATIC_ASSETS = [
        'https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=Inter:wght@400;500;600;700&display=swap',
        'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css',
        'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js',
        'https://unpkg.com/@geoman-io/leaflet-geoman-free@latest/dist/leaflet-geoman.css',
        'https://unpkg.com/@geoman-io/leaflet-geoman-free@latest/dist/leaflet-geoman.js'
    ];

    self.addEventListener('install', event => {
        // Take over immediately instead of waiting for every open tab to close.
        self.skipWaiting();
        event.waitUntil(
            caches.open(CACHE_NAME).then(cache => cache.addAll(STATIC_ASSETS))
        );
    });

    self.addEventListener('activate', event => {
        event.waitUntil(
            caches.keys().then(names =>
                Promise.all(names.filter(n => n !== CACHE_NAME).map(n => caches.delete(n)))
            ).then(() => self.clients.claim())
        );
    });

    self.addEventListener('fetch', event => {
        const url = new URL(event.request.url);
        const isApi = url.pathname.startsWith('/api/');
        const isAppShell = event.request.mode === 'navigate' || url.pathname === '/';

        // API calls and the app shell (index.html/JS) must always be
        // network-first: they change frequently (live parking data, and
        // your own app updates) and must never be served from a stale cache.
        // Only the static CDN libraries above (Leaflet, fonts, etc., which
        // are version-pinned and never change) are served cache-first.
        if (isApi || isAppShell) {
            event.respondWith(
                fetch(event.request).catch(() => caches.match(event.request))
            );
            return;
        }

        event.respondWith(
            caches.match(event.request).then(response => response || fetch(event.request))
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

    # Optional caller position (the front-end sends its live GPS fix when it has
    # one). Used only to attach a "distance from you" to each result, like the
    # result rows in Yandex Maps. Falls back to the map centre when missing or
    # when the caller is nowhere near Yerevan.
    try:
        origin_lat = float(request.args.get("lat", MAP_CENTER[0]))
        origin_lon = float(request.args.get("lon", MAP_CENTER[1]))
        if not (MAP_BOUNDS["lat_min"] <= origin_lat <= MAP_BOUNDS["lat_max"] and
                MAP_BOUNDS["lon_min"] <= origin_lon <= MAP_BOUNDS["lon_max"]):
            raise ValueError("origin outside Yerevan area")
    except (TypeError, ValueError):
        origin_lat, origin_lon = MAP_CENTER

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
                    "kind": "landmark",
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
                        "kind": "street",
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
                            "kind": "address",
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
                            "kind": "address",
                            "lat": lat,
                            "lon": lon,
                        })
        except Exception as exc:
            print(f"[search] Nominatim API call skipped/failed ({exc})")

    results = results[:8]
    for r in results:
        r["distance_m"] = int(round(haversine_m(origin_lat, origin_lon, r["lat"], r["lon"])))
    return jsonify(results)

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

    for f in _get_live_features():
        state = simulate_segment_state(f["id"], f["parking_type"], now)

        geometry = {"type": f["geometry_type"], "coordinates": f["coordinates"]}
        centroid_lat, centroid_lon = _extract_lat_lon(f)

        geojson_features.append({
            "type": "Feature",
            "geometry": geometry,
            "properties": {
                "id": f["id"],
                "name": f["name"],
                "parking_type": f["parking_type"],
                "color": TYPE_COLORS.get(f["parking_type"], "#7f8c8d"),
                "centroid_lat": round(centroid_lat, 6),
                "centroid_lon": round(centroid_lon, 6),
                **state,
            },
        })

    resp = jsonify({
        "type": "FeatureCollection",
        "generated_at": now.isoformat(),
        "features": geojson_features,
    })
    resp.headers["Cache-Control"] = "no-store"
    return resp

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
        "overall_traffic_score": max(0, min(10, int(round(overall_avg / 10)))),
        "streets": rows,
    })

def _get_live_features() -> list[dict]:
    """
    Reads parking segments directly from PostgreSQL rather than the in-process
    PARKING_FEATURES cache.

    Why: PARKING_FEATURES is only populated once, at process startup. If the
    app is ever running more than one worker process (Render's default
    gunicorn setup often is), a segment saved or deleted via Admin Mode only
    updates the memory of the *one* worker that handled that request — other
    workers (which may well be the ones that end up serving a later
    /api/recommend call) keep serving stale data until they happen to
    restart. Querying the DB directly here is cheap for a table this size
    and guarantees recommendations always reflect the latest saved/deleted
    segments, no matter which process handles the request.
    """
    segments = ParkingSegment.query.all()
    features = []
    for s in segments:
        coords = s.coordinates
        if isinstance(coords, str):
            try:
                coords = json.loads(coords)
            except Exception:
                pass
        features.append({
            "id": s.id,
            "name": s.name,
            "parking_type": s.parking_type,
            "geometry_type": s.geometry_type,
            "coordinates": coords,
            "centroid": [s.centroid_lon, s.centroid_lat],
        })
    return features


def _compute_recommendations(dest_lat, dest_lon, requested_radius, now, traffic_mult, weather_info):
    """
    Core multi-factor recommendation scoring engine. Shared by /api/recommend
    (interactive UI queries) and the ML feedback logger (to determine whether
    a logged parking spot matches one of the app's recommended candidates).

    Returns (candidates, current_radius) where candidates is the full sorted
    list of scored, in-radius parking options (best first).
    """
    weather_factor = weather_info["weather_factor"]
    candidates = []
    current_radius = requested_radius
    live_features = _get_live_features()

    for current_radius in [requested_radius, 1500.0, 3000.0]:
        candidates = []
        for f in live_features:
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
    return candidates, current_radius

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

    candidates, current_radius = _compute_recommendations(
        dest_lat, dest_lon, requested_radius, now, traffic_mult, weather_info
    )
    top3 = candidates[:3]

    resp = jsonify({
        "destination": {"lat": dest_lat, "lon": dest_lon},
        "radius_m": current_radius,
        "generated_at": now.isoformat(),
        "candidates_considered": len(candidates),
        "weather": weather_info,
        "live_traffic_multiplier": traffic_mult,
        "recommendations": top3,
    })
    resp.headers["Cache-Control"] = "no-store"
    return resp


# Loose bounding box around Kentron, Yerevan. Any admin-submitted point
# outside this box is almost certainly a typo (swapped lat/lon, pasted
# coordinates from the wrong place, etc.) and would otherwise get written
# straight into the shared PostgreSQL table and corrupt the map for every
# user. +/- ~0.08 deg (~8km) gives comfortable room around the city center.
MAP_BOUNDS = {
    "lat_min": MAP_CENTER[0] - 0.08, "lat_max": MAP_CENTER[0] + 0.08,
    "lon_min": MAP_CENTER[1] - 0.08, "lon_max": MAP_CENTER[1] + 0.08,
}


def _all_points(coordinates, geometry_type: str):
    """Flatten a GeoJSON coordinates array (LineString/Polygon/MultiLineString) into a flat list of [lon, lat] points."""
    pts = []
    def walk(node):
        if not isinstance(node, list):
            return
        if len(node) == 2 and all(isinstance(v, (int, float)) for v in node):
            pts.append(node)
            return
        for child in node:
            walk(child)
    walk(coordinates)
    return pts


def _validate_feature_coordinates(coordinates, geometry_type: str) -> str | None:
    """Returns an error message if any point falls outside the Kentron/Yerevan area, else None."""
    pts = _all_points(coordinates, geometry_type)
    if not pts:
        return "No coordinates supplied."
    for lon, lat in pts:
        if not (MAP_BOUNDS["lat_min"] <= lat <= MAP_BOUNDS["lat_max"] and
                MAP_BOUNDS["lon_min"] <= lon <= MAP_BOUNDS["lon_max"]):
            return (f"Point [lon={lon}, lat={lat}] is outside the expected Yerevan/Kentron area "
                    f"(lat {MAP_BOUNDS['lat_min']:.4f}..{MAP_BOUNDS['lat_max']:.4f}, "
                    f"lon {MAP_BOUNDS['lon_min']:.4f}..{MAP_BOUNDS['lon_max']:.4f}). "
                    "Check for a swapped lat/lon or a typo before saving.")
    return None


# --------------------------------------------------------------------------
# Admin Authentication
# --------------------------------------------------------------------------
@app.route("/api/admin/login", methods=["POST"])
def api_admin_login():
    if not ADMIN_PASSWORD:
        return jsonify({"error": "Admin mode is not configured on this server."}), 503

    # Strict per-IP limit to slow down password guessing, independent of
    # (and in addition to) the general API rate limit above.
    if not _check_rate_limit(f"login:{_client_ip()}", max_requests=5, window_seconds=300):
        return jsonify({"error": "Too many login attempts. Please wait a few minutes and try again."}), 429

    data = request.get_json(silent=True) or {}
    submitted = str(data.get("password", ""))

    # Constant-time comparison so response timing can't leak how many
    # leading characters of the password guess were correct.
    if not hmac.compare_digest(submitted, ADMIN_PASSWORD):
        return jsonify({"error": "Incorrect password."}), 401

    session.permanent = True
    session["is_admin"] = True
    session["admin_login_at"] = time.time()
    return jsonify({"status": "ok", "session_seconds": app.config["PERMANENT_SESSION_LIFETIME"].total_seconds()})


@app.route("/api/admin/logout", methods=["POST"])
def api_admin_logout():
    session.pop("is_admin", None)
    session.pop("admin_login_at", None)
    return jsonify({"status": "ok"})


@app.route("/api/admin/status")
def api_admin_status():
    if not session.get("is_admin"):
        return jsonify({"is_admin": False})

    # Explicit, authoritative remaining-time check (in addition to Flask's
    # own signed-cookie expiry) so the frontend can proactively log the
    # device out and show a clear message the moment the session's time is
    # up, rather than only discovering it on the next failed save/delete.
    login_at = session.get("admin_login_at")
    lifetime_s = app.config["PERMANENT_SESSION_LIFETIME"].total_seconds()
    if login_at is not None:
        remaining = lifetime_s - (time.time() - login_at)
        if remaining <= 0:
            session.pop("is_admin", None)
            session.pop("admin_login_at", None)
            return jsonify({"is_admin": False, "reason": "expired"})
        return jsonify({"is_admin": True, "seconds_remaining": round(remaining)})

    return jsonify({"is_admin": True, "seconds_remaining": round(lifetime_s)})


@app.route("/api/admin/feature", methods=["POST"])
@require_admin
def api_admin_save_feature():
    global PARKING_FEATURES
    data = request.json
    if not data:
        return jsonify({"error": "Invalid or empty payload."}), 400

    normalized = _normalize_feature(data)

    # Automatically generate an ID if the frontend passes an un-saved segment
    if not normalized["id"] or normalized["id"] == "unk":
        normalized["id"] = hashlib.md5(str(time.time()).encode()).hexdigest()[:10]

    # Reject out-of-area coordinates before they ever touch the shared DB.
    validation_error = _validate_feature_coordinates(normalized["coordinates"], normalized["geometry_type"])
    if validation_error:
        return jsonify({"error": validation_error}), 400

    lat, lon = _extract_lat_lon(normalized)

    # --- Database Persistence (Prevents ephemeral loss on server reload) ---
    segment = ParkingSegment.query.get(normalized["id"])
    if segment:
        segment.name = normalized["name"]
        segment.parking_type = normalized["parking_type"]
        segment.geometry_type = normalized["geometry_type"]
        segment.coordinates = normalized["coordinates"]
        segment.centroid_lat = lat
        segment.centroid_lon = lon
        updated = True
    else:
        segment = ParkingSegment(
            id=normalized["id"],
            name=normalized["name"],
            parking_type=normalized["parking_type"],
            geometry_type=normalized["geometry_type"],
            coordinates=normalized["coordinates"],
            centroid_lat=lat,
            centroid_lon=lon
        )
        db.session.add(segment)
        updated = False

    db.session.commit()

    # --- In-memory Update ---
    for i, f in enumerate(PARKING_FEATURES):
        if f["id"] == normalized["id"]:
            PARKING_FEATURES[i] = normalized
            break
    else:
        PARKING_FEATURES.append(normalized)

    return jsonify({
        "status": "ok",
        "action": "updated" if updated else "created",
        "id": normalized["id"],
        "total_segments": len(PARKING_FEATURES),
        "parking_type_saved": normalized["parking_type"]
    })


@app.route("/api/admin/feature/<segment_id>", methods=["DELETE"])
@require_admin
def api_admin_delete_feature(segment_id):
    global PARKING_FEATURES

    segment = ParkingSegment.query.get(segment_id)
    if not segment:
        return jsonify({"error": f"No segment found with id '{segment_id}'."}), 404

    # --- Database Persistence (removes it from the shared table for good) ---
    db.session.delete(segment)
    db.session.commit()

    # --- In-memory Update (so it disappears immediately for this instance too) ---
    PARKING_FEATURES = [f for f in PARKING_FEATURES if f["id"] != segment_id]

    return jsonify({
        "status": "ok",
        "action": "deleted",
        "id": segment_id,
        "total_segments": len(PARKING_FEATURES),
    })

# --------------------------------------------------------------------------
# Parking event logging (shared by automatic detection)
# --------------------------------------------------------------------------
def _in_service_area(lat: float, lon: float) -> bool:
    return (MAP_BOUNDS["lat_min"] <= lat <= MAP_BOUNDS["lat_max"] and
            MAP_BOUNDS["lon_min"] <= lon <= MAP_BOUNDS["lon_max"])


def _log_parking_event(user_lat, user_lon, dest_lat, dest_lon, when_ts):
    """
    Builds and stages (flush, no commit) one MLFeedback row for a car that was
    parked at (user_lat, user_lon) at unix time `when_ts`. This is the same
    feature snapshot the old manual "I Parked Here" endpoint recorded; the
    temporal features describe the moment the car actually stopped, not the
    moment the backend noticed. Returns (entry, info).
    """
    # 1. Temporal context of the moment the car stopped
    utc_now = datetime.utcfromtimestamp(when_ts)
    local_now = datetime.fromtimestamp(when_ts)
    hour = local_now.hour
    day_of_week = local_now.weekday()
    is_weekend = day_of_week >= 5

    # 2. Nearest parking segment (reads live from the DB, like /api/parking)
    closest_segment = None
    min_distance_m = float('inf')
    for f in _get_live_features():
        f_lat, f_lon = _extract_lat_lon(f)
        dist = haversine_m(user_lat, user_lon, f_lat, f_lon)
        if dist < min_distance_m:
            min_distance_m = dist
            closest_segment = f

    matched_seg_id = closest_segment.get("id") if closest_segment else None
    matched_seg_name = closest_segment.get("name") if closest_segment else None
    matched_parking_type = closest_segment.get("parking_type", "unspecified") if closest_segment else "unspecified"

    # 3. Environment snapshot
    busyness_score = calculate_destination_busyness(user_lat, user_lon, local_now)
    traffic_mult = fetch_live_traffic_multiplier()
    weather = fetch_live_weather()

    # 4. Simulated baseline for the matched segment
    simulated_avail = None
    simulated_cong = None
    if matched_seg_id:
        sim_state = simulate_segment_state(matched_seg_id, matched_parking_type, local_now)
        simulated_avail = sim_state.get("availability_pct")
        simulated_cong = sim_state.get("congestion_score")

    # 5. Did they park where the app would have recommended?
    distance_parking_to_destination_m = None
    parked_at_recommended = None
    recommended_rank_matched = None
    distance_to_nearest_recommendation_m = None

    if dest_lat is not None and dest_lon is not None:
        distance_parking_to_destination_m = round(haversine_m(user_lat, user_lon, dest_lat, dest_lon), 2)

        rec_candidates, _ = _compute_recommendations(dest_lat, dest_lon, 500.0, local_now, traffic_mult, weather)
        top3 = rec_candidates[:3]

        if top3:
            parked_at_recommended = False
            best_distance = float('inf')
            for rank, cand in enumerate(top3, start=1):
                cand_dist = haversine_m(user_lat, user_lon, cand["location"]["lat"], cand["location"]["lon"])
                if cand_dist < best_distance:
                    best_distance = cand_dist
                is_match = cand_dist <= RECOMMENDATION_MATCH_RADIUS_M or cand["id"] == matched_seg_id
                if is_match and not parked_at_recommended:
                    parked_at_recommended = True
                    recommended_rank_matched = rank
            distance_to_nearest_recommendation_m = round(best_distance, 2)

    entry = MLFeedback(
        lat=user_lat,
        lon=user_lon,
        timestamp=utc_now,
        hour=hour,
        day_of_week=day_of_week,
        is_weekend=is_weekend,
        matched_segment_id=matched_seg_id,
        parking_type=matched_parking_type,
        distance_to_segment_m=round(min_distance_m, 2) if min_distance_m != float('inf') else None,
        destination_busyness=busyness_score,
        traffic_multiplier=traffic_mult,
        weather_condition=weather.get("condition"),
        weather_factor=weather.get("weather_factor"),
        temp_c=weather.get("temp_c"),
        simulated_availability_pct=simulated_avail,
        simulated_congestion_score=simulated_cong,
        dest_lat=dest_lat,
        dest_lon=dest_lon,
        distance_parking_to_destination_m=distance_parking_to_destination_m,
        parked_at_recommended_spot=parked_at_recommended,
        recommended_rank_matched=recommended_rank_matched,
        distance_to_nearest_recommendation_m=distance_to_nearest_recommendation_m,
    )
    db.session.add(entry)
    db.session.flush()  # assigns entry.id; the caller commits

    return entry, {
        "matched_segment_id": matched_seg_id,
        "matched_segment_name": matched_seg_name,
        "matched_parking_type": matched_parking_type,
        "parked_at_recommended_spot": parked_at_recommended,
        "recommended_rank_matched": recommended_rank_matched,
        "distance_to_nearest_recommendation_m": distance_to_nearest_recommendation_m,
    }


# --------------------------------------------------------------------------
# Automatic parking detection: the trip state machine
# --------------------------------------------------------------------------
# The device sends a location ping every few seconds while a drive is in
# progress (/api/trip/ping). The backend decides when that drive has ended:
#
#   tracking -> driving   a sample moves at vehicle speed
#   driving  -> stopped   speed drops below vehicle speed after a real drive
#   stopped  -> parked    the stop has lasted long enough. "Long enough" is
#                         shortened when the stop is near the destination the
#                         user set, when the phone has walked away from the
#                         car, or when the phone was unplugged from a charger
#                         (a good proxy for "turned the car off").
#   stopped/driving -> parked  also when pings simply stop (app backgrounded
#                         or phone locked after parking) near the destination
#                         or after a stop - settled lazily on the next request.
#
# The parked spot is where the car STOPPED MOVING (last vehicle-speed sample),
# not where the phone is by the time the decision is made. Only that spot is
# kept; trip rows hold a few anchor points, never the route, and are deleted
# within hours.
TRIP_CFG = {
    "VEHICLE_SPEED_MS": 4.0,        # ~14 km/h. Walking ~1.4 m/s, jogging ~3 m/s
    "MIN_DRIVE_SECONDS": 45.0,      # vehicle-speed motion needed before a stop can count as "parking"
    "MIN_DRIVE_DISTANCE_M": 300.0,
    "MIN_PEAK_SPEED_MS": 5.0,
    "DWELL_DEFAULT_S": 150.0,       # stopped this long with no other context (outlasts traffic lights)
    "DWELL_NEAR_DEST_S": 45.0,      # ...when the stop is at the destination ("approximately reached")
    "DWELL_WALKING_AWAY_S": 90.0,   # ...when the phone has walked away from the car
    "DWELL_CHARGER_S": 20.0,        # ...when the phone was unplugged from the car charger
    "NEAR_DEST_M": 200.0,
    "WALKED_AWAY_M": 25.0,
    "MAX_ACCURACY_M": 100.0,        # ignore poorer fixes
    "MAX_PLAUSIBLE_SPEED_MS": 70.0, # ~250 km/h; anything faster is a GPS glitch
    "SILENCE_S": 240.0,             # no pings for this long after a drive => settle it
    "SILENCE_NEAR_DEST_M": 300.0,
    "DISCARD_AFTER_S": 1200.0,      # silent mid-drive and not near anything: drop it
    "KEEP_FINISHED_S": 3600.0,
    "KEEP_ANY_S": 86400.0,
}
_TRIP_ID_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")
_last_trip_sweep = 0.0


def _trip_has_drive_evidence(trip) -> bool:
    c = TRIP_CFG
    return (trip.drive_ts is not None
            and (trip.drive_seconds or 0.0) >= c["MIN_DRIVE_SECONDS"]
            and (trip.drive_distance_m or 0.0) >= c["MIN_DRIVE_DISTANCE_M"]
            and (trip.max_speed or 0.0) >= c["MIN_PEAK_SPEED_MS"])


def _dwell_conclusion(trip, lat, lon, now):
    """The car has been below vehicle speed since trip.drive_ts: has it been long enough?"""
    c = TRIP_CFG
    dwell = now - trip.drive_ts
    near_dest = (trip.dest_lat is not None and trip.dest_lon is not None and
                 haversine_m(trip.drive_lat, trip.drive_lon, trip.dest_lat, trip.dest_lon) <= c["NEAR_DEST_M"])
    walked_away = haversine_m(trip.drive_lat, trip.drive_lon, lat, lon) >= c["WALKED_AWAY_M"]
    unplugged = trip.power_lost_ts is not None and trip.power_lost_ts >= trip.drive_ts

    needed = c["DWELL_NEAR_DEST_S"] if near_dest else c["DWELL_DEFAULT_S"]
    if walked_away:
        needed = min(needed, c["DWELL_WALKING_AWAY_S"])
    if unplugged:
        needed = min(needed, c["DWELL_CHARGER_S"])
    if dwell < needed:
        return None

    confidence = 0.55 + (0.20 if near_dest else 0.0) + (0.10 if walked_away else 0.0) + (0.15 if unplugged else 0.0)
    return {
        "source": "auto_charger" if unplugged else ("auto_destination" if near_dest else "auto_dwell"),
        "confidence": round(min(0.95, confidence), 2),
        "dwell_seconds": round(dwell, 1),
        "near_destination": near_dest,
        "charger_unplugged": unplugged,
    }


def _silence_conclusion(trip, now):
    """
    Pings stopped after a real drive (the page was backgrounded / the phone
    locked). If the last sample was a slow one, or was near the destination,
    the drive most likely ended there. Otherwise it was probably a tunnel or
    a dead zone, so wait; after DISCARD_AFTER_S give up.
    """
    c = TRIP_CFG
    if trip.state not in ("driving", "stopped") or trip.updated_at is None or not _trip_has_drive_evidence(trip):
        return None
    gap = now - trip.updated_at
    if gap < c["SILENCE_S"]:
        return None
    near_dest = (trip.dest_lat is not None and trip.last_lat is not None and
                 haversine_m(trip.last_lat, trip.last_lon, trip.dest_lat, trip.dest_lon) <= c["SILENCE_NEAR_DEST_M"])
    was_slow = trip.last_speed is not None and trip.last_speed < c["VEHICLE_SPEED_MS"]
    if was_slow or near_dest:
        return {
            "source": "auto_signal_loss",
            "confidence": round(0.45 + (0.20 if near_dest else 0.0) + (0.10 if was_slow else 0.0), 2),
            "dwell_seconds": round(gap, 1),
            "near_destination": near_dest,
            "charger_unplugged": False,
        }
    if gap >= c["DISCARD_AFTER_S"]:
        trip.state = "discarded"
    return None


def _advance_trip(trip, lat, lon, accuracy, reported_speed, charging, now):
    """Feeds one location sample into the trip. Returns a conclusion dict if the car is now judged parked."""
    c = TRIP_CFG

    # The page may have been away for a while: settle any drive that already ended.
    silent = _silence_conclusion(trip, now)
    if silent:
        return silent
    if trip.state not in ("tracking", "driving", "stopped"):
        return None

    trip.updated_at = now
    if accuracy is not None and accuracy > c["MAX_ACCURACY_M"]:
        return None  # too imprecise to learn anything from

    dt = (now - trip.last_ts) if trip.last_ts else None
    if reported_speed is not None:
        speed = reported_speed
    elif dt and 0.5 <= dt <= 60 and trip.last_lat is not None:
        speed = haversine_m(trip.last_lat, trip.last_lon, lat, lon) / dt
    else:
        speed = 0.0
    if speed > c["MAX_PLAUSIBLE_SPEED_MS"]:
        return None

    # Charger: plugged in -> unplugged after driving began is a strong "engine off" hint.
    if charging is not None:
        if trip.last_charging and not charging and trip.drive_ts is not None:
            trip.power_lost_ts = now
        trip.last_charging = bool(charging)

    outcome = None
    if speed >= c["VEHICLE_SPEED_MS"]:
        if trip.state == "driving" and trip.drive_ts is not None and dt and dt <= 60:
            trip.drive_seconds = (trip.drive_seconds or 0.0) + dt
            trip.drive_distance_m = (trip.drive_distance_m or 0.0) + haversine_m(trip.drive_lat, trip.drive_lon, lat, lon)
        trip.drive_lat, trip.drive_lon, trip.drive_ts = lat, lon, now
        trip.max_speed = max(trip.max_speed or 0.0, speed)
        trip.power_lost_ts = None
        trip.state = "driving"
    elif _trip_has_drive_evidence(trip):
        trip.state = "stopped"
        outcome = _dwell_conclusion(trip, lat, lon, now)

    trip.last_lat, trip.last_lon, trip.last_speed, trip.last_ts = lat, lon, speed, now
    return outcome


def _finalize_trip(trip, conclusion):
    """Writes the parking record for a concluded trip. Caller commits. Returns the payload for the client."""
    lat, lon = trip.drive_lat, trip.drive_lon
    if lat is None or lon is None or not _in_service_area(lat, lon):
        trip.state = "discarded"
        return None

    entry, info = _log_parking_event(lat, lon, trip.dest_lat, trip.dest_lon, trip.drive_ts)
    detection = ParkingDetection(
        ml_feedback_id=entry.id,
        source=conclusion["source"],
        confidence=conclusion["confidence"],
        dwell_seconds=conclusion["dwell_seconds"],
        drive_seconds=round(trip.drive_seconds or 0.0, 1),
        drive_distance_m=round(trip.drive_distance_m or 0.0, 1),
        near_destination=conclusion["near_destination"],
        charger_unplugged=conclusion["charger_unplugged"],
        segment_name=(info["matched_segment_name"] or "")[:128] or None,
        undo_token=secrets.token_urlsafe(16),
    )
    db.session.add(detection)
    trip.state = "parked"
    trip.log_id = entry.id
    return _detection_payload(detection, lat, lon)


def _detection_payload(detection, lat, lon):
    return {
        "log_id": detection.ml_feedback_id,
        "undo_token": detection.undo_token,
        "segment_name": detection.segment_name,
        "source": detection.source,
        "confidence": detection.confidence,
        "lat": lat,
        "lon": lon,
    }


def _sweep_trips(now):
    """
    There is no background scheduler, so drives whose pings stopped are settled
    lazily: at most every 30s, on whichever ping arrives next. Also deletes old
    trip rows so no location state lingers.
    """
    global _last_trip_sweep
    if now - _last_trip_sweep < 30:
        return
    _last_trip_sweep = now
    try:
        stale = (TripSession.query
                 .filter(TripSession.state.in_(("driving", "stopped")),
                         TripSession.updated_at < now - TRIP_CFG["SILENCE_S"])
                 .limit(25).all())
        for t in stale:
            concl = _silence_conclusion(t, now)
            if concl:
                _finalize_trip(t, concl)
        TripSession.query.filter(
            TripSession.state.in_(("tracking", "parked", "discarded")),
            TripSession.updated_at < now - TRIP_CFG["KEEP_FINISHED_S"]).delete(synchronize_session=False)
        TripSession.query.filter(TripSession.updated_at < now - TRIP_CFG["KEEP_ANY_S"]).delete(synchronize_session=False)
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        print(f"[trip] sweep failed ({exc})")


def _opt_float(value):
    try:
        v = float(value)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


@app.route("/api/trip/ping", methods=["POST"])
def api_trip_ping():
    """
    One location sample from a device that is (probably) driving. Replaces the
    old manual "I Parked Here" button: when the sample completes a stop, the
    parking event is recorded here and returned once so the UI can offer Undo.
    """
    if not _check_rate_limit(f"trip:{_client_ip()}", max_requests=30, window_seconds=60):
        return jsonify({"error": "Too many location updates.", "state": "throttled", "keep_tracking": True}), 429

    data = request.get_json(silent=True, force=True) or {}
    trip_id = str(data.get("trip_id", ""))
    lat, lon = _opt_float(data.get("lat")), _opt_float(data.get("lon"))
    if not _TRIP_ID_RE.match(trip_id) or lat is None or lon is None:
        return jsonify({"error": "trip_id, lat and lon are required."}), 400
    if not _in_service_area(lat, lon):
        # Not in Yerevan: nothing to detect. Tell the client to back off.
        return jsonify({"state": "out_of_area", "keep_tracking": False, "parked": None})

    accuracy = _opt_float(data.get("accuracy"))
    speed = _opt_float(data.get("speed"))
    if speed is not None and speed < 0:
        speed = None
    charging = data.get("charging")
    charging = charging if isinstance(charging, bool) else None
    dest_lat, dest_lon = _opt_float(data.get("dest_lat")), _opt_float(data.get("dest_lon"))
    if dest_lat is None or dest_lon is None or not _in_service_area(dest_lat, dest_lon):
        dest_lat = dest_lon = None

    now = time.time()
    try:
        _sweep_trips(now)

        # Row lock so two workers can't both conclude the same trip.
        trip = TripSession.query.filter_by(id=trip_id).with_for_update().first()
        if trip is None:
            trip = TripSession(id=trip_id, created_at=now, updated_at=now, state="tracking",
                               drive_seconds=0.0, drive_distance_m=0.0, max_speed=0.0, announced=False)
            db.session.add(trip)
        if dest_lat is not None:
            trip.dest_lat, trip.dest_lon = dest_lat, dest_lon

        parked = None
        if trip.state == "parked":
            # Settled while the page was away (e.g. phone locked after parking): announce it once.
            if not trip.announced:
                det = ParkingDetection.query.filter_by(ml_feedback_id=trip.log_id).first()
                if det:
                    parked = _detection_payload(det, trip.drive_lat, trip.drive_lon)
                trip.announced = True
        else:
            concl = _advance_trip(trip, lat, lon, accuracy, speed, charging, now)
            if concl:
                parked = _finalize_trip(trip, concl)
                trip.announced = True

        db.session.commit()
        return jsonify({"state": trip.state, "keep_tracking": True, "parked": parked})
    except Exception as exc:
        db.session.rollback()
        print(f"[trip] ping failed ({exc})")
        return jsonify({"error": "Could not process location update.", "state": "error", "keep_tracking": True}), 500


@app.route("/api/trip/undo", methods=["POST"])
def api_trip_undo():
    """'That wasn't a parking spot': removes the automatically logged entry again."""
    if not _check_rate_limit(f"tripundo:{_client_ip()}", max_requests=10, window_seconds=60):
        return jsonify({"error": "Too many requests."}), 429
    data = request.get_json(silent=True, force=True) or {}
    try:
        log_id = int(data.get("log_id"))
    except (TypeError, ValueError):
        return jsonify({"error": "log_id is required."}), 400
    token = str(data.get("undo_token", ""))

    det = ParkingDetection.query.filter_by(ml_feedback_id=log_id).first()
    if det is None or not hmac.compare_digest(det.undo_token or "", token):
        return jsonify({"error": "Nothing to undo."}), 404
    if not det.undone:
        entry = MLFeedback.query.get(log_id)
        if entry is not None:
            db.session.delete(entry)
        det.undone = True
        db.session.commit()
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    # debug=True enables Werkzeug's interactive debugger, which lets anyone
    # who can trigger an unhandled exception run arbitrary Python on the
    # server - completely unacceptable for a public deployment. It's now
    # opt-in via FLASK_DEBUG=true for local development only, and off by
    # default. Host/port also now respect Render's environment (it injects
    # PORT and expects the app to bind 0.0.0.0) while still defaulting to
    # 127.0.0.1:5000 for a plain local `python app.py` run.
    debug_mode = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    port = int(os.environ.get("PORT", 5000))
    host = "0.0.0.0" if os.environ.get("PORT") or os.environ.get("RENDER") else "127.0.0.1"
    print(f"[server] Starting Yerevan Smart Parking Recommender server on {host}:{port} (debug={debug_mode})")
    app.run(host=host, port=port, debug=debug_mode)
