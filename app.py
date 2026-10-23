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
 12. Live data layer: real per-street traffic (HERE / TomTom / Yandex Router, whichever has a
     key; otherwise a per-street simulation), an OpenStreetMap POI inventory with opening hours,
     optional BestTime live busyness. Admin diagnostics at /api/admin/data-sources.
 13. Keeps a Render free-tier service awake: /healthz plus a self-ping thread (KEEPALIVE=off to disable).

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
import threading
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

_rl_calls = 0


def _prune_rate_limits(now: float) -> None:
    """Forget visitors who have been quiet for a while, so the table can't grow without bound
    (someone sending made-up addresses would otherwise fill the server's memory)."""
    for k in [k for k, v in _rate_limit_store.items() if not v or v[-1] < now - 900]:
        _rate_limit_store.pop(k, None)
    if len(_rate_limit_store) > 20000:                       # still huge: keep only the busiest half
        keep = sorted(_rate_limit_store.items(), key=lambda kv: len(kv[1]), reverse=True)[:10000]
        _rate_limit_store.clear()
        _rate_limit_store.update(keep)


def _check_rate_limit(key: str, max_requests: int, window_seconds: float) -> bool:
    """Returns True if the request is allowed, False if the caller has exceeded
    max_requests within window_seconds. Records the request if allowed."""
    global _rl_calls
    now = time.time()
    _rl_calls += 1
    if _rl_calls % 200 == 0 or len(_rate_limit_store) > 5000:
        _prune_rate_limits(now)
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
    # The LEFT end of X-Forwarded-For is whatever the visitor chose to send, so it can be forged to dodge limits.
    # Each trusted proxy appends the address it saw on the RIGHT, so count in from the right.
    #   TRUSTED_PROXY_HOPS = how many proxies sit in front of this app (see your host's docs/logs).
    # Unset keeps the old behaviour; the admin login also has an overall cap that does not depend on this.
    fwd = request.headers.get("X-Forwarded-For", "")
    if fwd:
        parts = [p.strip() for p in fwd.split(",") if p.strip()]
        try:
            hops = int(os.environ.get("TRUSTED_PROXY_HOPS", "0") or 0)
        except ValueError:
            hops = 0
        if parts and hops > 0 and len(parts) >= hops:
            return parts[-hops]
        if parts:
            return parts[0]
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
    if request.path == "/traffic-map":
        # Yandex's JS API needs 'unsafe-eval' and a few Yandex origins (from Yandex's CSP guide). That is
        # confined to this one page, which the app embeds as a same-origin iframe.
        # Rules copied from Yandex's "Enabling the API when using CSP" for JS API 2.1 (the version loaded here):
        #   script-src also needs *.maps.yandex.net (the 2.1 traffic layer fetches its data from there) and yandex.ru
        #   style-src needs blob:,  img-src/connect-src need yandex.ru,  frame-src/child-src need api-maps.yandex.ru
        ya = "https://api-maps.yandex.ru https://*.api-maps.yandex.ru https://suggest-maps.yandex.ru https://*.maps.yandex.net https://yandex.ru https://yastatic.net"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            f"script-src 'self' 'unsafe-inline' 'unsafe-eval' {ya}; "
            "style-src 'self' 'unsafe-inline' blob: https://api-maps.yandex.ru https://*.api-maps.yandex.ru https://yastatic.net; "
            f"connect-src 'self' {ya}; "
            "img-src 'self' data: blob: https://*.maps.yandex.net https://api-maps.yandex.ru https://*.api-maps.yandex.ru https://yandex.ru https://yastatic.net; "
            "frame-src https://api-maps.yandex.ru; "
            "child-src https://api-maps.yandex.ru; "
            "worker-src 'self' data: blob:; "
            "font-src 'self' https://yastatic.net; "
            "object-src 'none'; "
            "frame-ancestors 'self'"
        )
        if os.environ.get("RENDER"):
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response
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


class LiveData(db.Model):
    """Shared cache for live-data results (traffic readings, POI inventory, quotas), one row per key,
    so every worker process reads and writes the same data."""
    __tablename__ = 'live_data'

    key = db.Column(db.String(80), primary_key=True)
    payload = db.Column(db.Text)
    updated_at = db.Column(db.Float, default=0.0)
    claimed_at = db.Column(db.Float, default=0.0)   # compare-and-set lock for "who refreshes this key"

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

_BUSYNESS_CACHE: dict = {}

# ==========================================================================
# LIVE DATA LAYER
#
#   street traffic  - real per-street readings (HERE / TomTom / Yandex Router),
#                     or a per-street simulation when no key is configured
#   POI busyness    - a real POI inventory (OpenStreetMap, incl. opening hours)
#                     plus live signals (traffic pressure, optional BestTime)
#
# Design rules:
#   * nothing here may ever make a request fail: every external call is wrapped,
#     time-boxed, budgeted, and falls back to the simulation
#   * external calls never run inside a user request: they run in a background
#     thread, one worker at a time (a DB row is the lock), and requests read the
#     cached result (stale-while-revalidate)
#   * nothing is polled while nobody is using the app, so quotas aren't burned
# ==========================================================================

# ---- environment ----------------------------------------------------------
#   TRAFFIC_PROVIDER      auto (default) | here | tomtom | yandex | simulated
#   HERE_API_KEY          HERE Traffic API v7   (free plan: ~250k requests/month)
#   TOMTOM_API_KEY        TomTom Traffic Flow   (free plan: 2,500 requests/day)
#   YANDEX_ROUTING_API_KEY  Yandex Router API   (already used by this app). NOTE: Yandex lists "no free
#                         version" for its HTTP Router API, so this only works with a paid key.
#   COVERAGE (checked against the providers' own tables, Oct 2026): HERE's Traffic API v7 and
#   TomTom's Traffic API do NOT list Armenia, so for Yerevan they return nothing and the app falls
#   back to the simulation. They are kept for use in other cities. Use /api/admin/data-sources?probe=1.
#   HERE_MONTHLY_BUDGET / TOMTOM_DAILY_BUDGET / YANDEX_DAILY_BUDGET   hard caps
#   TRAFFIC_TTL_S         how long a reading is considered fresh (default 180 HERE, 900 others)
#   POI_SOURCE            auto (default) | curated    (curated = built-in list only)
#   OVERPASS_URL          override the OpenStreetMap Overpass endpoint
#   BESTTIME_API_KEY      optional: live "busier than usual" for landmarks (paid after trial)
#   BESTTIME_MONTHLY_BUDGET   cap on BestTime calls (default 60)
_UA = "parkaway/1.0 (parking recommender)"


def _provider_keys() -> dict:
    yandex = os.environ.get("YANDEX_ROUTING_API_KEY", "").strip()
    return {
        "here": os.environ.get("HERE_API_KEY", "").strip(),
        "tomtom": os.environ.get("TOMTOM_API_KEY", "").strip(),
        "yandex": yandex,
    }


def _active_traffic_provider():
    """The provider to use: the one forced by TRAFFIC_PROVIDER, else the first configured."""
    pref = os.environ.get("TRAFFIC_PROVIDER", "auto").strip().lower()
    keys = _provider_keys()
    if pref == "simulated":
        return None
    if pref in keys:
        return pref if keys[pref] else None
    for name in ("here", "tomtom", "yandex"):
        if keys[name]:
            return name
    return None


def _redact(text) -> str:
    """Error text safe to log: API keys never reach the logs."""
    s = str(text)
    for k in list(_provider_keys().values()) + [os.environ.get("BESTTIME_API_KEY", "").strip()]:
        if k:
            s = s.replace(k, "***")
    return s


def _http_json(url, timeout=7.0, method="GET", data=None, headers=None):
    hdrs = {"User-Agent": _UA, "Accept": "application/json"}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, data=data, method=method, headers=hdrs)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


# ---- shared cache (one DB row per key, so every worker sees the same data) ----
def _ld_get(key):
    row = LiveData.query.get(key)
    if row is None or not row.payload:
        return None, 0.0
    try:
        return json.loads(row.payload), float(row.updated_at or 0.0)
    except Exception:
        return None, 0.0


def _ld_put(key, obj):
    row = LiveData.query.get(key)
    if row is None:
        row = LiveData(key=key, claimed_at=0.0)
        db.session.add(row)
    row.payload = json.dumps(obj, separators=(",", ":"))
    row.updated_at = time.time()
    db.session.commit()


def _ld_claim(key, hold_s):
    """
    Atomically takes the right to refresh `key`: returns True for exactly one caller
    per hold window, across every worker process (a compare-and-set on the row).
    """
    now = time.time()
    try:
        if LiveData.query.get(key) is None:
            try:
                db.session.add(LiveData(key=key, payload=None, updated_at=0.0, claimed_at=0.0))
                db.session.commit()
            except Exception:
                db.session.rollback()
        n = (LiveData.query
             .filter(LiveData.key == key, LiveData.claimed_at < now - hold_s)
             .update({"claimed_at": now}, synchronize_session=False))
        db.session.commit()
        return n == 1
    except Exception:
        db.session.rollback()
        return False


def _budget_limit(provider):
    env_names = {"here": ("HERE_MONTHLY_BUDGET", 100000, "%Y%m"),
                 "tomtom": ("TOMTOM_DAILY_BUDGET", 2400, "%Y%m%d"),
                 "yandex": ("YANDEX_DAILY_BUDGET", 800, "%Y%m%d"),
                 "besttime": ("BESTTIME_MONTHLY_BUDGET", 60, "%Y%m")}
    name, default, fmt = env_names[provider]
    try:
        limit = int(os.environ.get(name, default))
    except ValueError:
        limit = default
    return limit, fmt


def _budget_take(provider, cost=1) -> bool:
    """Counts a request against the provider's quota BEFORE making it. False = over budget."""
    limit, fmt = _budget_limit(provider)
    key = f"budget:{provider}:{datetime.utcnow().strftime(fmt)}"
    used, _ = _ld_get(key)
    used = int(used or 0)
    if used + cost > limit:
        return False
    _ld_put(key, used + cost)
    return True


def _run_in_background(fn, *args):
    def runner():
        with app.app_context():
            try:
                fn(*args)
            except Exception as exc:
                print(f"[live] background task {getattr(fn, '__name__', 'fn')} failed ({_redact(exc)})")
            finally:
                db.session.remove()
    if os.environ.get("LIVE_DATA_SYNC") == "1":      # tests / debugging: run inline
        fn(*args)
        return
    threading.Thread(target=runner, daemon=True).start()


# ---- geometry ----------------------------------------------------------------
def _flatten_points(coords):
    out = []

    def rec(x):
        if isinstance(x, (list, tuple)) and len(x) >= 2 and isinstance(x[0], (int, float)) and isinstance(x[1], (int, float)):
            out.append((float(x[0]), float(x[1])))
        elif isinstance(x, (list, tuple)):
            for y in x:
                rec(y)
    rec(coords)
    # features are stored [lon, lat] (GeoJSON) but older rows can be [lat, lon]
    return [(a, b) if (38.0 <= a <= 42.0 and 43.0 <= b <= 47.0) else (b, a) for a, b in out]


def _xy(lat, lon, lat0):
    return lon * 111320.0 * math.cos(math.radians(lat0)), lat * 110540.0


def _dist_to_polyline_m(lat, lon, pts):
    if not pts:
        return float("inf")
    px, py = _xy(lat, lon, lat)
    if len(pts) == 1:
        qx, qy = _xy(pts[0][0], pts[0][1], lat)
        return math.hypot(px - qx, py - qy)
    best = float("inf")
    ax, ay = _xy(pts[0][0], pts[0][1], lat)
    for i in range(1, len(pts)):
        bx, by = _xy(pts[i][0], pts[i][1], lat)
        dx, dy = bx - ax, by - ay
        seg2 = dx * dx + dy * dy
        t = 0.0 if seg2 == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / seg2))
        best = min(best, math.hypot(px - (ax + t * dx), py - (ay + t * dy)))
        ax, ay = bx, by
    return best


_SEG_INDEX = {"ts": 0.0, "by_id": {}}


def _segment_index():
    """id -> {id, name, type, lat, lon, points}; refreshed from the DB at most once a minute."""
    now = time.time()
    if now - _SEG_INDEX["ts"] < 60 and _SEG_INDEX["by_id"]:
        return _SEG_INDEX
    try:
        feats = _get_live_features()
    except Exception:
        feats = PARKING_FEATURES
    by_id = {}
    for f in feats:
        try:
            lat, lon = _extract_lat_lon(f)
            by_id[f["id"]] = {
                "id": f["id"],
                "name": (f.get("name") or "Unnamed segment"),
                "type": f.get("parking_type", "unspecified"),
                "geom": f.get("geometry_type"),
                "lat": lat, "lon": lon,
                "points": _flatten_points(f.get("coordinates")),
            }
        except Exception:
            continue
    _SEG_INDEX["by_id"] = by_id
    _SEG_INDEX["ts"] = now
    return _SEG_INDEX


# --------------------------------------------------------------------------
# Street traffic: simulation (used when no live data is available)
#
# The old simulator ran every street off ONE hourly curve (+/-9 random), so all
# streets rose and fell together. Here every street has its own personality
# (road class, commute direction, lunch/dinner pull, drifting noise, the odd
# incident), so at any moment some streets are heavy while others are free.
# --------------------------------------------------------------------------
_PROFILES: dict = {}
_GENERIC_NAME_WORDS = {"street", "st", "avenue", "ave", "str", "lane", "road", "rd", "blvd", "boulevard",
                       "parking", "lot", "complex", "the", "of", "and", "south", "north", "east", "west", "(south)", "(north)"}


def _name_tokens(name: str) -> set:
    return {w for w in re.split(r"[^a-z0-9]+", (name or "").lower()) if len(w) > 2 and w not in _GENERIC_NAME_WORDS}


def _street_profile(name: str) -> dict:
    p = _PROFILES.get(name)
    if p:
        return p
    n = (name or "").lower()
    rnd = random.Random("profile|" + n)
    if any(w in n for w in ("avenue", " ave", "highway", "prospekt", "boulevard", "bridge")):
        size = 0.98
    elif any(w in n for w in ("street", " st", "road")):
        size = 0.74
    else:
        size = 0.60
    p = {
        "size": max(0.35, min(1.05, size + rnd.uniform(-0.12, 0.10))),
        "am_bias": rnd.uniform(-1.0, 1.0),        # >0: heavier toward the city in the morning, <0: out in the evening
        "phase_min": rnd.uniform(-35, 35),        # this street peaks a bit earlier/later than the city curve
        "rush": rnd.uniform(0.65, 1.35),          # how hard the commute peaks hit this street
        "midday": rnd.uniform(0.6, 1.4),          # shops, offices, lunch
        "nightlife": rnd.uniform(0.0, 1.0),       # dining / bar streets
        "periods": (rnd.uniform(26, 52), rnd.uniform(70, 130)),
        "phases": (rnd.random(), rnd.random()),
    }
    _PROFILES[name] = p
    return p


def _bump(t_min: float, mu_min: float, sigma_min: float) -> float:
    d = abs(t_min - mu_min)
    d = min(d, 1440.0 - d)
    return math.exp(-0.5 * (d / sigma_min) ** 2)


def _curve_at(minutes: float, weekend: bool) -> float:
    h = (minutes / 60.0) % 24.0
    lo = int(h)
    frac = h - lo
    a = _hour_congestion_curve(lo, weekend)
    b = _hour_congestion_curve((lo + 1) % 24, weekend)
    return a + (b - a) * frac


def _simulated_traffic(name: str, lat: float, lon: float, ptype: str, now: datetime) -> dict:
    """-> {c: congestion 0-100, typical: the same without noise/incidents}"""
    if ptype == "unavailable":
        return {"c": 0.0, "typical": 0.0}
    prof = _street_profile(name)
    weekend = now.weekday() >= 5
    t = now.hour * 60 + now.minute + prof["phase_min"]

    city = _curve_at(t, weekend)
    commute = 0.35 if weekend else 1.0
    am = _bump(t, 8.5 * 60, 75) * (1.0 + 0.45 * prof["am_bias"]) * commute
    pm = _bump(t, 18.0 * 60, 95) * (1.0 - 0.45 * prof["am_bias"]) * commute
    mid = _bump(t, 13.0 * 60, 120) * prof["midday"] * (1.25 if weekend else 1.0)
    eve = _bump(t, 20.5 * 60, 90) * prof["nightlife"] * (1.3 if weekend else 0.9)
    shape = 0.36 * city + 0.30 * prof["rush"] * (am + pm) + 0.14 * mid + 0.16 * eve

    dist_center = haversine_m(lat, lon, MAP_CENTER[0], MAP_CENTER[1])
    centrality = 1.12 - 0.30 * min(1.0, dist_center / 2500.0)
    typical = max(0.0, min(100.0, 100.0 * prof["size"] * shape * centrality))

    abs_min = now.timestamp() / 60.0
    p1, p2 = prof["periods"]
    f1, f2 = prof["phases"]
    noise = 8.0 * math.sin(2 * math.pi * (abs_min / p1 + f1)) + 5.0 * math.sin(2 * math.pi * (abs_min / p2 + f2))

    bucket = int(abs_min // 30)
    r = random.Random(f"incident|{name.lower()}|{bucket}")
    p_inc = 0.035 if 7 <= now.hour <= 21 else 0.012
    incident = 0.0
    if r.random() < p_inc:
        incident = r.uniform(18, 40) * math.sin(math.pi * ((abs_min % 30) / 30.0))

    c = max(0.0, min(100.0, typical + noise + incident))
    if ptype == "lot":                      # a lot is a destination, not a through street
        c, typical = c * 0.45, typical * 0.45
    return {"c": c, "typical": typical}


# --------------------------------------------------------------------------
# Street traffic: live providers
# --------------------------------------------------------------------------
def _slowdown_to_congestion(slowdown: float) -> float:
    """1 - current/free-flow speed -> 0-100. 20% slower ~ 33, 40% ~ 67, 60%+ = 100."""
    return max(0.0, min(100.0, slowdown / 0.6 * 100.0))


def _traffic_ttl(provider) -> float:
    try:
        return float(os.environ["TRAFFIC_TTL_S"])
    except (KeyError, ValueError):
        return 180.0 if provider == "here" else 900.0


def _here_readings(segs):
    """
    HERE Traffic API v7 /flow: ONE request returns every road link in a circle,
    with its geometry, current speed, free-flow speed and jamFactor (0-10).
    Each parking segment is matched to the nearest link(s) within 35 m.
    """
    key = _provider_keys()["here"]
    far = max((haversine_m(MAP_CENTER[0], MAP_CENTER[1], s["lat"], s["lon"]) for s in segs), default=0.0)
    radius = int(min(8000, max(700, far + 450)))
    url = "https://data.traffic.hereapi.com/v7/flow?" + urllib.parse.urlencode({
        "in": f"circle:{MAP_CENTER[0]},{MAP_CENTER[1]};r={radius}",
        "locationReferencing": "shape",
        "apiKey": key,
    })
    if not _budget_take("here"):
        raise RuntimeError("HERE monthly budget exhausted")
    data = _http_json(url, timeout=10)

    links = []
    for r in data.get("results", []) or []:
        cf = r.get("currentFlow") or {}
        loc = r.get("location") or {}
        speed, free, jam, conf = cf.get("speed"), cf.get("freeFlow"), cf.get("jamFactor"), cf.get("confidence")
        if conf is not None and conf < 0.25:
            continue
        for link in (loc.get("shape") or {}).get("links", []) or []:
            pts = [(p["lat"], p["lng"]) for p in link.get("points", []) if "lat" in p and "lng" in p]
            if len(pts) >= 2:
                links.append({"pts": pts, "jam": jam, "speed": speed, "free": free,
                              "tokens": _name_tokens(loc.get("description") or ""),
                              "bbox": (min(p[0] for p in pts), max(p[0] for p in pts),
                                       min(p[1] for p in pts), max(p[1] for p in pts))})

    cell = 0.003
    grid: dict = {}
    pad = 0.0006
    for i, ln in enumerate(links):
        la0, la1, lo0, lo1 = ln["bbox"]
        for ix in range(int((la0 - pad) / cell), int((la1 + pad) / cell) + 1):
            for iy in range(int((lo0 - pad) / cell), int((lo1 + pad) / cell) + 1):
                grid.setdefault((ix, iy), []).append(i)

    readings = {}
    now = time.time()
    for s in segs:
        if s["type"] == "lot" or len(s["points"]) < 2:
            continue
        pts = s["points"]
        mid = pts[len(pts) // 2] if len(pts) >= 3 else ((pts[0][0] + pts[1][0]) / 2, (pts[0][1] + pts[1][1]) / 2)
        samples = [pts[0], mid, pts[-1]]
        seg_tokens = _name_tokens(s["name"])
        cand = {}
        for (la, lo) in samples:
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for i in grid.get((int(la / cell) + dx, int(lo / cell) + dy), ()):
                        cand.setdefault(i, None)
        scored = []
        for i in cand:
            ln = links[i]
            ds = sorted(_dist_to_polyline_m(la, lo, ln["pts"]) for (la, lo) in samples)
            d = ds[1]                                   # median: a street that merely CROSSES this road touches it at one end only
            if d <= 35.0:
                rank = d - (10.0 if (seg_tokens and ln["tokens"] & seg_tokens) else 0.0)
                scored.append((rank, d, ln))
        if not scored:
            continue
        scored.sort(key=lambda x: x[0])
        best_rank = scored[0][0]
        chosen = [ln for rank, d, ln in scored if rank <= best_rank + 5.0][:4]
        cs, sp, fr = [], [], []
        for ln in chosen:
            if ln["jam"] is not None:
                cs.append(min(100.0, float(ln["jam"]) * 10.0))
            elif ln["speed"] and ln["free"]:
                cs.append(_slowdown_to_congestion(1.0 - float(ln["speed"]) / float(ln["free"])))
            if ln["speed"] is not None:
                sp.append(float(ln["speed"]) * 3.6)       # m/s -> km/h
            if ln["free"] is not None:
                fr.append(float(ln["free"]) * 3.6)
        if cs:
            readings[s["id"]] = {"c": round(sum(cs) / len(cs), 1),
                                 "s": round(sum(sp) / len(sp), 1) if sp else None,
                                 "f": round(sum(fr) / len(fr), 1) if fr else None,
                                 "ts": now}
    return readings


def _probe_tomtom(seg):
    """TomTom Flow Segment Data: the road segment nearest to a point -> current vs free-flow speed."""
    pts = seg["points"]
    la, lo = pts[len(pts) // 2] if pts else (seg["lat"], seg["lon"])
    url = ("https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json?" +
           urllib.parse.urlencode({"key": _provider_keys()["tomtom"], "point": f"{la},{lo}", "unit": "KMPH", "thickness": 1}))
    if not _budget_take("tomtom"):
        raise RuntimeError("TomTom daily budget exhausted")
    d = (_http_json(url, timeout=6).get("flowSegmentData")) or {}
    cur, free = d.get("currentSpeed"), d.get("freeFlowSpeed")
    if d.get("roadClosure"):
        return {"c": 100.0, "s": 0.0, "f": free}
    if not cur and cur != 0 or not free:
        return None
    conf = d.get("confidence")
    if conf is not None and conf < 0.3:
        return None
    return {"c": round(_slowdown_to_congestion(1.0 - float(cur) / float(free)), 1), "s": float(cur), "f": float(free)}


def _probe_yandex(seg):
    """
    Yandex Router API: route from one end of the segment to the other and compare the
    time with traffic to the time without. (Same response fields this app already read.)
    """
    pts = seg["points"]
    if len(pts) < 2:
        return None
    a, b = pts[0], pts[-1]
    if haversine_m(a[0], a[1], b[0], b[1]) < 50:
        return None                                     # too short for a meaningful ratio
    waypoints = urllib.parse.quote(f"{a[0]},{a[1]}|{b[0]},{b[1]}", safe=",|")
    url = (f"https://api.routing.yandex.net/v2/route?waypoints={waypoints}&mode=driving"
           f"&apikey={urllib.parse.quote(_provider_keys()['yandex'])}")
    if not _budget_take("yandex"):
        raise RuntimeError("Yandex daily budget exhausted")
    data = _http_json(url, timeout=6)
    legs = ((data.get("route") or {}).get("legs")) or []
    t_free = t_traffic = dist = 0.0
    for leg in legs:
        w = leg.get("weight") or {}
        tf = (w.get("time") or {}).get("value")
        tt = (w.get("time_with_traffic") or {}).get("value", tf)
        if tf:
            t_free += float(tf)
            t_traffic += float(tt if tt is not None else tf)
        dist += float((w.get("distance") or {}).get("value") or 0)
    if t_free <= 0:
        return None
    ratio = t_traffic / t_free
    return {"c": round(max(0.0, min(100.0, (ratio - 1.0) * 100.0)), 1),
            "s": round(dist / t_traffic * 3.6, 1) if (dist and t_traffic) else None, "f": None}


_PROBES = {"tomtom": _probe_tomtom, "yandex": _probe_yandex}
_MAX_PROBES_PER_CYCLE = 25


def _refresh_traffic():
    """Runs in a background thread: asks the active provider for fresh readings and stores them."""
    provider = _active_traffic_provider()
    if not provider:
        return
    status, _ = _ld_get("traffic:status")
    status = status or {}
    now = time.time()
    if now < status.get("backoff_until", 0):
        return
    segs = [s for s in _segment_index()["by_id"].values() if s["type"] != "unavailable"]
    doc, _ = _ld_get("traffic:live")
    if not doc or doc.get("provider") != provider:
        doc = {"provider": provider, "readings": {}, "fetched_at": 0.0}
    ttl = _traffic_ttl(provider)
    try:
        if provider == "here":
            doc["readings"] = _here_readings(segs)
        else:
            probe = _PROBES[provider]
            ids = {s["id"] for s in segs}
            doc["readings"] = {k: v for k, v in doc["readings"].items() if k in ids}
            due = [s for s in segs if s["type"] != "lot" and len(s["points"]) >= 2 and
                   now - doc["readings"].get(s["id"], {}).get("ts", 0.0) > ttl]
            due.sort(key=lambda s: doc["readings"].get(s["id"], {}).get("ts", 0.0))
            fails = 0
            out_of_quota = False
            for s in due[:_MAX_PROBES_PER_CYCLE]:
                try:
                    r = probe(s)
                    if r:
                        r["ts"] = time.time()
                        doc["readings"][s["id"]] = r
                    fails = 0
                except RuntimeError as exc:   # out of quota: keep what was collected, try again later
                    out_of_quota = True
                    status["last_error"] = _redact(exc)
                    break
                except Exception as exc:
                    fails += 1
                    status["last_error"] = _redact(exc)
                    if fails >= 3:
                        raise
            if out_of_quota:
                status["backoff_until"] = time.time() + 900.0
        doc["fetched_at"] = time.time()
        _ld_put("traffic:live", doc)
        status.update({"provider": provider, "last_ok": time.time(), "fail_streak": 0,
                       "backoff_until": status.get("backoff_until", 0) if provider != "here" else 0,
                       "readings": len(doc["readings"]), "segments": len(segs)})
        if not (provider != "here" and status.get("backoff_until", 0) > time.time()):
            status["last_error"] = None
    except Exception as exc:
        streak = int(status.get("fail_streak", 0)) + 1
        status.update({"provider": provider, "fail_streak": streak, "last_error": _redact(exc),
                       "backoff_until": time.time() + min(900.0, 60.0 * (2 ** min(streak, 4)))})
        print(f"[traffic] {provider} refresh failed ({_redact(exc)}); using simulated/last-known data")
    _ld_put("traffic:status", status)


_TRAFFIC_MEM = {"loaded": 0.0, "doc": None, "est": {}, "pressure": [], "provider": None}


def _traffic_view():
    """Per-process view of the stored live data, reloaded every 15 s; kicks off a background refresh when stale."""
    now = time.time()
    if now - _TRAFFIC_MEM["loaded"] < 15:
        return _TRAFFIC_MEM
    _TRAFFIC_MEM["loaded"] = now
    provider = _active_traffic_provider()
    _TRAFFIC_MEM["provider"] = provider
    if not provider:
        _TRAFFIC_MEM.update(doc=None, est={}, pressure=[])
        return _TRAFFIC_MEM
    try:
        doc, _ = _ld_get("traffic:live")
        if doc and doc.get("provider") != provider:
            doc = None
        _TRAFFIC_MEM["doc"] = doc
        ttl = _traffic_ttl(provider)
        stale_after = ttl if provider == "here" else 120.0
        if (not doc or now - doc.get("fetched_at", 0) > stale_after) and _ld_claim("traffic:refresh", 45):
            _run_in_background(_refresh_traffic)
        _rebuild_traffic_estimates()
    except Exception as exc:
        print(f"[traffic] cache read failed ({_redact(exc)})")
    return _TRAFFIC_MEM


def _fresh_reading(doc, seg_id, provider, now):
    if not doc:
        return None
    r = (doc.get("readings") or {}).get(seg_id)
    if r and now - r.get("ts", 0) <= max(3 * _traffic_ttl(provider), 1800.0):
        return r
    return None


def _rebuild_traffic_estimates():
    """Segments without a fresh reading borrow from live neighbours (inverse-distance weighted, <=450 m)."""
    now = time.time()
    doc, provider = _TRAFFIC_MEM["doc"], _TRAFFIC_MEM["provider"]
    segs = _segment_index()["by_id"]
    live = {}
    for sid, s in segs.items():
        r = _fresh_reading(doc, sid, provider, now)
        if r is not None and s["type"] != "lot":
            live[sid] = r
    est, pressure = {}, []
    for sid, s in segs.items():
        if s["type"] == "lot":
            continue
        if sid in live:
            typ = _simulated_traffic(s["name"], s["lat"], s["lon"], s["type"], datetime.now())["typical"]
            pressure.append((s["lat"], s["lon"], (live[sid]["c"] - typ) / 100.0))
            continue
        num = den = 0.0
        for oid, r in live.items():
            o = segs[oid]
            d = haversine_m(s["lat"], s["lon"], o["lat"], o["lon"])
            if d <= 450.0:
                w = 1.0 / (30.0 + d) ** 2
                num += w * r["c"]
                den += w
        if den > 0:
            est[sid] = num / den
    _TRAFFIC_MEM["est"] = est
    _TRAFFIC_MEM["pressure"] = pressure


def segment_traffic(seg_id: str, now: datetime | None = None) -> dict:
    """
    Current street traffic for one parking segment:
      congestion 0-100, source live|estimated|simulated, speed_kmh, typical (what's usual right now)
    """
    now = now or datetime.now()
    seg = _segment_index()["by_id"].get(seg_id)
    name, lat, lon, ptype = ((seg["name"], seg["lat"], seg["lon"], seg["type"]) if seg
                             else (seg_id, MAP_CENTER[0], MAP_CENTER[1], "unspecified"))
    sim = _simulated_traffic(name, lat, lon, ptype, now)
    out = {"congestion": round(sim["c"], 1), "typical": round(sim["typical"], 1), "source": "simulated",
           "speed_kmh": None, "provider": None}
    if ptype in ("lot", "unavailable"):
        return out
    view = _traffic_view()
    provider = view["provider"]
    if not provider:
        return out
    r = _fresh_reading(view["doc"], seg_id, provider, time.time())
    if r is not None:
        out.update(congestion=round(r["c"], 1), source="live", speed_kmh=r.get("s"), provider=provider)
    elif seg_id in view["est"]:
        out.update(congestion=round(view["est"][seg_id], 1), source="estimated", provider=provider)
    return out


_MULT_CACHE = {"ts": 0.0, "v": 1.0}


def fetch_live_traffic_multiplier() -> float:
    """
    City-wide "busier or quieter than usual" ratio (0.8 - 1.5): live street readings vs what the
    model expects for this hour. 1.0 when there is no live data. Logged with every parking
    event and returned by /api/recommend.
    """
    now = time.time()
    cache = _MULT_CACHE
    if now - cache["ts"] < 60:
        return cache["v"]
    ratio = 1.0
    try:
        view = _traffic_view()
        provider = view["provider"]
        if provider and view["doc"]:
            live, typ = [], []
            dt = datetime.now()
            for sid, s in _segment_index()["by_id"].items():
                r = _fresh_reading(view["doc"], sid, provider, now)
                if r is not None and s["type"] != "lot":
                    live.append(r["c"])
                    typ.append(_simulated_traffic(s["name"], s["lat"], s["lon"], s["type"], dt)["typical"])
            if len(live) >= 3:
                ratio = max(0.8, min(1.5, (sum(live) / len(live) + 15.0) / (sum(typ) / len(typ) + 15.0)))
    except Exception:
        ratio = 1.0
    cache.update(ts=now, v=round(ratio, 3))
    return cache["v"]


# --------------------------------------------------------------------------
# POI busyness: inventory (OpenStreetMap) + opening hours + live signals
# --------------------------------------------------------------------------
_DAY_IDX = {"mo": 0, "tu": 1, "we": 2, "th": 3, "fr": 4, "sa": 5, "su": 6}
_OH_DAYS_RE = re.compile(r"^((?:[a-z]{2}(?:-[a-z]{2})?)(?:,(?:[a-z]{2}(?:-[a-z]{2})?))*)(?:\s+|$)")
_OH_TIME_RE = re.compile(r"(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})")


def _expand_days(spec: str):
    days = set()
    for part in spec.split(","):
        if "-" in part:
            a, b = part.split("-")
            if a not in _DAY_IDX or b not in _DAY_IDX:
                return None
            i, j = _DAY_IDX[a], _DAY_IDX[b]
            k = i
            while True:
                days.add(k)
                if k == j:
                    break
                k = (k + 1) % 7
        elif part in _DAY_IDX:
            days.add(_DAY_IDX[part])
        else:
            return None
    return days


def parse_opening_hours(text):
    """
    OSM opening_hours (common subset) -> 7 lists of [start_min, end_min] (end > 1440 = past midnight),
    or None when the text is missing / uses syntax we don't understand (then the category curve is used).
    Supported: 24/7, "Mo-Fr 09:00-18:00; Sa 10:00-14:00; Su off", several ranges, overnight ranges.
    """
    if not text or len(text) > 400:
        return None
    t = text.strip().lower()
    if t == "24/7":
        return [[[0, 1440]] for _ in range(7)]
    sched = [None] * 7
    understood = False
    for rule in t.split(";"):
        rule = rule.strip()
        if not rule:
            continue
        days = set(range(7))
        m = _OH_DAYS_RE.match(rule)
        rest = rule
        if m:
            spec = m.group(1)
            if any(h in spec for h in ("ph", "sh")):
                continue                                  # public/school holiday rules: ignored
            days = _expand_days(spec)
            if days is None:
                return None
            rest = rule[m.end():].strip()
        elif rule.startswith(("ph", "sh")):
            continue
        if rest in ("off", "closed"):
            ranges = []
        elif rest == "24/7":
            ranges = [[0, 1440]]
        else:
            found = _OH_TIME_RE.findall(rest)
            if not found:
                return None
            ranges = []
            for h1, m1, h2, m2 in found:
                a, b = int(h1) * 60 + int(m1), int(h2) * 60 + int(m2)
                if b <= a:
                    b += 1440
                ranges.append([a, b])
        for d in days:
            sched[d] = ranges
        understood = True
    if not understood:
        return None
    return [s if s is not None else [] for s in sched]


def oh_is_open(sched, weekday: int, minute: int):
    if sched is None:
        return None
    for a, b in sched[weekday]:
        if a <= minute < b:
            return True
    for a, b in sched[(weekday - 1) % 7]:
        if b > 1440 and minute + 1440 < b:
            return True
    return False


_OSM_EXTRA_WEIGHTS = {"fast_food": 2, "clinic": 2, "library": 1.5, "venue": 4, "worship": 1.5,
                      "retail": 0.8, "fitness": 1.5}
_AMENITY_TYPES = {
    "restaurant": "restaurant", "food_court": "restaurant", "fast_food": "fast_food",
    "cafe": "cafe", "ice_cream": "cafe", "bar": "bar", "pub": "bar", "nightclub": "bar",
    "bank": "bank", "pharmacy": "pharmacy", "clinic": "clinic", "doctors": "clinic", "dentist": "clinic",
    "hospital": "hospital", "university": "university", "college": "university",
    "school": "school", "kindergarten": "school", "library": "library",
    "cinema": "venue", "theatre": "venue", "arts_centre": "venue", "events_venue": "venue",
    "conference_centre": "venue", "marketplace": "shopping_centre",
    "townhall": "government", "courthouse": "government", "police": "government", "post_office": "government",
    "place_of_worship": "worship", "bus_station": "bus_station",
}


def _osm_poi_type(t: dict):
    a, s, tr, le = t.get("amenity"), t.get("shop"), t.get("tourism"), t.get("leisure")
    if a in _AMENITY_TYPES:
        return _AMENITY_TYPES[a]
    if s:
        if s in ("mall", "department_store"):
            return "shopping_centre"
        if s == "supermarket":
            return "supermarket"
        if s in ("convenience", "greengrocer", "bakery", "butcher", "kiosk"):
            return "convenience"
        return "retail"
    if tr in ("museum", "gallery"):
        return "museum"
    if tr in ("attraction", "zoo", "theme_park"):
        return "tourist_attraction"
    if tr in ("hotel", "hostel", "guest_house"):
        return "hotel"
    if le == "park":
        return "park"
    if le in ("fitness_centre", "sports_centre", "stadium"):
        return "fitness"
    if t.get("railway") == "subway_entrance" or t.get("public_transport") == "station":
        return "metro_station"
    if t.get("office"):
        return "office"
    return None


def _poi_weight(ptype: str) -> float:
    return float(_OSM_EXTRA_WEIGHTS.get(ptype, POI_WEIGHTS.get(ptype, 2)))


def _pois_from_overpass(elements):
    pois = []
    for el in elements:
        tags = el.get("tags") or {}
        ptype = _osm_poi_type(tags)
        if not ptype:
            continue
        lat = el.get("lat", (el.get("center") or {}).get("lat"))
        lon = el.get("lon", (el.get("center") or {}).get("lon"))
        if lat is None or lon is None:
            continue
        w = _poi_weight(ptype)
        if tags.get("wikidata") or tags.get("wikipedia"):
            w *= 1.4                       # notable places draw more people
        elif tags.get("brand"):
            w *= 1.1
        pois.append({"lat": round(lat, 5), "lon": round(lon, 5), "t": ptype, "n": tags.get("name", ""),
                     "w": round(w, 2), "oh": parse_opening_hours(tags.get("opening_hours"))})
    return pois[:15000]


def _overpass_query() -> str:
    pts = [p for s in _segment_index()["by_id"].values() for p in s["points"]] or [(MAP_CENTER[0], MAP_CENTER[1])]
    south, north = min(p[0] for p in pts) - 0.006, max(p[0] for p in pts) + 0.006
    west, east = min(p[1] for p in pts) - 0.008, max(p[1] for p in pts) + 0.008
    bb = f"{south:.5f},{west:.5f},{north:.5f},{east:.5f}"
    amen = "|".join(sorted(_AMENITY_TYPES))
    return (f'[out:json][timeout:50];('
            f'nwr["amenity"~"^({amen})$"]({bb});'
            f'nwr["shop"]({bb});'
            f'nwr["tourism"~"^(museum|gallery|attraction|hotel|hostel|guest_house|zoo|theme_park)$"]({bb});'
            f'nwr["leisure"~"^(park|fitness_centre|sports_centre|stadium)$"]({bb});'
            f'nwr["railway"="subway_entrance"]({bb});nwr["public_transport"="station"]({bb});'
            f'nwr["office"]({bb});'
            f');out center tags qt;')


def _refresh_pois():
    """Downloads the POI inventory from OpenStreetMap (Overpass) and stores it for every worker."""
    urls = [u for u in (os.environ.get("OVERPASS_URL", "").strip(),
                        "https://overpass-api.de/api/interpreter",
                        "https://overpass.kumi.systems/api/interpreter") if u]
    body = urllib.parse.urlencode({"data": _overpass_query()}).encode()
    last = None
    for url in urls:
        try:
            data = _http_json(url, timeout=70, method="POST", data=body,
                              headers={"Content-Type": "application/x-www-form-urlencoded"})
            pois = _pois_from_overpass(data.get("elements", []))
            if len(pois) < 20:
                raise RuntimeError(f"only {len(pois)} usable POIs returned")
            _ld_put("poi:inventory", {"fetched_at": time.time(), "source": "osm", "pois": pois})
            print(f"[poi] stored {len(pois)} OpenStreetMap POIs ({sum(1 for p in pois if p['oh'])} with opening hours)")
            return len(pois)
        except Exception as exc:
            last = exc
            print(f"[poi] Overpass fetch failed on {url.split('/')[2]} ({_redact(exc)})")
    raise RuntimeError(f"all Overpass endpoints failed: {_redact(last)}")


_POI_MEM = {"checked": 0.0, "fetched_at": None, "pois": [], "grid": {}, "source": "curated", "ref": None}
_POI_TTL_S = 7 * 24 * 3600
_GRID_DLAT, _GRID_DLON = 0.004, 0.005          # cells >= the 350 m search radius in both axes


def _install_inventory(pois, source, fetched_at):
    grid: dict = {}
    for p in pois:
        grid.setdefault((int(p["lat"] / _GRID_DLAT), int(p["lon"] / _GRID_DLON)), []).append(p)
    _POI_MEM.update(pois=pois, grid=grid, source=source, fetched_at=fetched_at, ref=None)
    _BUSYNESS_CACHE.clear()


def _poi_state():
    now = time.time()
    st = _POI_MEM
    if st["pois"] and now - st["checked"] < 600:
        return st
    st["checked"] = now
    if os.environ.get("POI_SOURCE", "auto").strip().lower() != "curated":
        try:
            doc, _ = _ld_get("poi:inventory")
            if doc and doc.get("pois"):
                if st["fetched_at"] != doc.get("fetched_at"):
                    _install_inventory(doc["pois"], "osm", doc.get("fetched_at"))
                if now - float(doc.get("fetched_at", 0)) > _POI_TTL_S and _ld_claim("poi:refresh", 3600):
                    _run_in_background(_refresh_pois)
            elif _ld_claim("poi:refresh", 3600):
                _run_in_background(_refresh_pois)
        except Exception as exc:
            print(f"[poi] inventory read failed ({_redact(exc)})")
    if not st["pois"]:
        curated = [{"lat": p["lat"], "lon": p["lon"], "t": p["type"], "n": p["name"],
                    "w": float(POI_WEIGHTS.get(p["type"], 2)), "oh": None} for p in FALLBACK_POIS]
        _install_inventory(curated, "curated", 0)
    return st


def _poi_demand(ptype: str, hour: int, weekday: int) -> float:
    """How busy this kind of place is at this hour/weekday (0-1), before opening hours are applied."""
    weekend = weekday >= 5
    if ptype == "fast_food":
        d = 0.35 + 0.65 * get_poi_hourly_factor("restaurant", hour, weekend)
    elif ptype == "clinic":
        d = 0.9 if (weekday < 5 and 8 <= hour <= 18) else (0.5 if (weekday == 5 and 9 <= hour <= 14) else 0.04)
    elif ptype == "library":
        d = 0.75 if 10 <= hour <= 20 else 0.05
    elif ptype == "venue":
        d = 1.0 if 19 <= hour <= 22 else (0.35 if 12 <= hour <= 18 else 0.05)
        if weekday in (4, 5) and 19 <= hour <= 23:
            d = min(1.0, d * 1.2)
    elif ptype == "worship":
        d = 1.0 if (weekday == 6 and 10 <= hour <= 13) else (0.3 if 17 <= hour <= 19 else 0.12)
    elif ptype == "retail":
        if weekend:
            d = 1.0 if 12 <= hour <= 19 else (0.55 if 10 <= hour <= 21 else 0.05)
        else:
            d = 0.9 if 17 <= hour <= 19 else (0.6 if 10 <= hour <= 21 else 0.05)
    elif ptype == "fitness":
        d = 1.0 if 17 <= hour <= 21 else (0.7 if 7 <= hour <= 9 else (0.3 if 10 <= hour <= 16 else 0.03))
    else:
        d = get_poi_hourly_factor(ptype, hour, weekend)
    if ptype in ("restaurant", "bar", "cafe", "fast_food") and weekday in (4, 5) and 18 <= hour <= 23:
        d = min(1.0, d * 1.15)                           # Friday / Saturday evenings
    return d


def _raw_poi_impact(st, lat, lon, hour, weekday, minute, radius=350.0):
    ci, cj = int(lat / _GRID_DLAT), int(lon / _GRID_DLON)
    total = 0.0
    for di in (-1, 0, 1):
        for dj in (-1, 0, 1):
            for p in st["grid"].get((ci + di, cj + dj), ()):
                d = haversine_m(lat, lon, p["lat"], p["lon"])
                if d > radius:
                    continue
                demand = _poi_demand(p["t"], hour, weekday)
                if p["oh"] is not None:
                    is_open = oh_is_open(p["oh"], weekday, minute)
                    if is_open is False:
                        demand = min(demand, 0.04)       # known to be closed right now
                total += p["w"] * demand * (1.0 - d / radius)
    return total


def _poi_reference(st) -> float:
    """
    Divisor that turns raw POI impact into a 0-1 busyness. The curated list used a fixed 18.
    A full OpenStreetMap inventory has far more POIs, so the scale is calibrated from the data:
    the 85th-percentile impact over all parking segments at the weekday lunch / dinner peaks.
    """
    if st["ref"] is not None:
        return st["ref"]
    if st["source"] == "curated":
        st["ref"] = 18.0
        return st["ref"]
    vals = []
    for s in list(_segment_index()["by_id"].values())[:200]:
        for hour in (13, 19):
            vals.append(_raw_poi_impact(st, s["lat"], s["lon"], hour, 2, hour * 60))
    vals.sort()
    p85 = vals[int(0.85 * (len(vals) - 1))] if vals else 0.0
    st["ref"] = max(p85 * 1.15, 6.0)
    return st["ref"]


def _local_traffic_pressure(lat, lon):
    """Average (live - usual) congestion of live street readings within 350 m, as -1..1; None if there are none."""
    try:
        pts = _traffic_view()["pressure"]
    except Exception:
        return None
    num = den = 0.0
    for la, lo, delta in pts:
        d = haversine_m(lat, lon, la, lo)
        if d <= 350.0:
            w = 1.0 - d / 350.0
            num += w * delta
            den += w
    return (num / den) if den > 0 else None


# ---- optional: BestTime.app live busyness ("busier than usual") ---------------------
def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:48]


def _fetch_besttime(venue_name: str):
    key = os.environ.get("BESTTIME_API_KEY", "").strip()
    if not key or not _budget_take("besttime"):
        return
    url = "https://besttime.app/api/v1/forecasts/live?" + urllib.parse.urlencode({
        "api_key_private": key, "venue_name": venue_name, "venue_address": f"{venue_name}, Yerevan, Armenia"})
    data = _http_json(url, method="POST", data=b"", timeout=15)
    an = data.get("analysis") or {}
    ratio = None
    if an.get("venue_live_busyness_available"):
        live, fc = an.get("venue_live_busyness"), an.get("venue_forecasted_busyness")
        if live is not None and fc is not None:
            ratio = (float(live) + 10.0) / (float(fc) + 10.0)       # smoothed live / forecast
    _ld_put(f"bt:{_slug(venue_name)}", {"ratio": ratio, "live": an.get("venue_live_busyness"),
                                        "forecast": an.get("venue_forecasted_busyness")})


def _besttime_ratio_near(lat, lon):
    if not os.environ.get("BESTTIME_API_KEY", "").strip():
        return None
    best, best_d = None, 150.0
    for p in FALLBACK_POIS:                            # tracked venues: the curated landmarks
        if POI_WEIGHTS.get(p["type"], 2) < 4:
            continue
        d = haversine_m(lat, lon, p["lat"], p["lon"])
        if d < best_d:
            best, best_d = p, d
    if not best:
        return None
    key = f"bt:{_slug(best['name'])}"
    doc, ts = _ld_get(key)
    if time.time() - ts > 2700 and _ld_claim(key + ":claim", 1800):
        _run_in_background(_fetch_besttime, best["name"])
    if doc and doc.get("ratio") is not None and time.time() - ts < 4 * 3600:
        return float(doc["ratio"])
    return None


def calculate_destination_busyness(lat: float, lon: float, now: datetime | None = None) -> float:
    """
    How busy the area around a point is (0 = quiet, 1 = packed), from:
      1. every POI within 350 m, weighted by type and distance, scaled by how busy that kind of
         place is at this hour/weekday, and zeroed for places that are closed right now
      2. live pressure: are the surrounding streets slower than usual?  (when live traffic is on)
      3. live venue busyness vs forecast for nearby landmarks               (when BestTime is on)
    """
    now = now or datetime.now()
    key = (round(lat, 4), round(lon, 4), now.weekday(), now.hour * 6 + now.minute // 10)
    now_ts = time.time()
    hit = _BUSYNESS_CACHE.get(key)
    if hit and now_ts - hit[0] < 300:
        return hit[1]

    st = _poi_state()
    impact = _raw_poi_impact(st, lat, lon, now.hour, now.weekday(), now.hour * 60 + now.minute)
    score = min(1.0, impact / _poi_reference(st))

    pressure = _local_traffic_pressure(lat, lon)
    if pressure is not None:
        score += max(-0.15, min(0.25, 0.4 * pressure))
    ratio = _besttime_ratio_near(lat, lon)
    if ratio is not None:
        score *= max(0.6, min(1.5, ratio))

    score = round(max(0.0, min(1.0, score)), 2)
    if len(_BUSYNESS_CACHE) > 4000:
        _BUSYNESS_CACHE.clear()
    _BUSYNESS_CACHE[key] = (now_ts, score)
    return score


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

    openweather_key = os.environ.get("OPENWEATHER_API_KEY")
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
    """
    One parking segment's current state.

      congestion_score / traffic_level   how slow the STREET is: a live provider reading when
                                         available, otherwise the per-street simulation
      availability_pct / occupancy_status  how likely a free space is: driven by the demand of the
                                         POIs around THIS segment (open places only), the time of
                                         day, the street's traffic and the kind of parking

    These used to be one number (traffic = 100 - availability); they are independent now.
    """
    if parking_type == "unavailable":
        return {
            "availability_pct": 0.0,
            "congestion_score": 0.0,
            "occupancy_status": "Unavailable",
            "traffic_level": "N/A",
            "traffic_source": "n/a",
            "speed_kmh": None,
        }

    now = now or datetime.now()
    seg = _segment_index()["by_id"].get(segment_id)
    lat, lon = (seg["lat"], seg["lon"]) if seg else (MAP_CENTER[0], MAP_CENTER[1])

    traffic = segment_traffic(segment_id, now)
    congestion = traffic["congestion"]
    demand = calculate_destination_busyness(lat, lon, now)
    city = _curve_at(now.hour * 60 + now.minute, now.weekday() >= 5)

    occupancy = 0.14 + 0.46 * demand + 0.22 * city + 0.10 * (congestion / 100.0)
    occupancy += {"free": 0.06, "paid": -0.06, "lot": -0.10}.get(parking_type, 0.0)
    rnd = random.Random("avail|" + str(segment_id))          # slow, per-segment drift (no per-minute flicker)
    occupancy += 0.05 * math.sin(2 * math.pi * (now.timestamp() / 60.0 / rnd.uniform(35, 70) + rnd.random()))

    availability_pct = max(3.0, min(97.0, 100.0 * (1.0 - occupancy)))
    if availability_pct >= 60:
        occupancy_status = "Available"
    elif availability_pct >= 28:
        occupancy_status = "Filling Fast"
    else:
        occupancy_status = "Occupied"

    if congestion < 35:
        traffic_level = "Low"
    elif congestion < 65:
        traffic_level = "Medium"
    else:
        traffic_level = "Heavy"

    return {
        "availability_pct": round(availability_pct, 1),
        "congestion_score": round(congestion, 1),
        "occupancy_status": occupancy_status,
        "traffic_level": traffic_level,
        "traffic_source": traffic["source"],
        "speed_kmh": traffic["speed_kmh"],
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
        yandex_traffic=bool(_yandex_maps_key()),
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
        "id": "/",
        "start_url": "/",
        "scope": "/",
        "lang": "en",
        "orientation": "portrait",
        # Long-press the home-screen icon -> jump straight to the one thing people open the app for
        "shortcuts": [
            {"name": "Find parking", "short_name": "Where to?", "url": "/?a=search",
             "icons": [{"src": "/icon.svg", "sizes": "any", "type": "image/svg+xml"}]},
            {"name": "Live traffic", "short_name": "Traffic", "url": "/?a=traffic",
             "icons": [{"src": "/icon.svg", "sizes": "any", "type": "image/svg+xml"}]},
        ],
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
    const CACHE_NAME = 'yerevan-parking-v6';
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

def _traffic_level(score: float) -> str:
    return "Low" if score < 35 else ("Medium" if score < 65 else "Heavy")


@app.route("/api/traffic")
def api_traffic():
    now = datetime.now()
    segs = [s for s in _segment_index()["by_id"].values() if s["type"] != "unavailable"]
    streets = [s for s in segs if s["type"] != "lot"] or segs          # parking lots aren't streets
    by_street: dict[str, list[tuple[dict, dict]]] = {}
    for s in streets:
        by_street.setdefault(s["name"], []).append(
            (simulate_segment_state(s["id"], s["type"], now), segment_traffic(s["id"], now)))

    rows = []
    for name, items in by_street.items():
        cong = sum(t["congestion"] for _, t in items) / len(items)
        avail = sum(st["availability_pct"] for st, _ in items) / len(items)
        typical = sum(t["typical"] for _, t in items) / len(items)
        sources = {t["source"] for _, t in items}
        source = "live" if "live" in sources else ("estimated" if "estimated" in sources else "simulated")
        speeds = [t["speed_kmh"] for _, t in items if t["speed_kmh"] is not None]
        delta = cong - typical
        rows.append({
            "name": name,
            "traffic_level": _traffic_level(cong),
            "congestion_score": round(cong, 1),
            "availability_pct": round(avail, 1),
            "source": source,
            "speed_kmh": round(sum(speeds) / len(speeds), 1) if speeds else None,
            # "busier than usual" at street level (only meaningful with real readings)
            "vs_typical": round(delta, 1) if source != "simulated" else None,
            "usual": (None if source == "simulated" else
                      ("busier than usual" if delta >= 12 else ("quieter than usual" if delta <= -12 else "as usual"))),
        })
    rows.sort(key=lambda r: r["congestion_score"], reverse=True)

    overall_avg = sum(r["congestion_score"] for r in rows) / len(rows) if rows else 0
    live_n = sum(1 for r in rows if r["source"] == "live")
    est_n = sum(1 for r in rows if r["source"] == "estimated")
    provider = _traffic_view()["provider"]
    status, _ = _ld_get("traffic:status")
    # a provider is configured and answering, but has no data for these streets (e.g. no coverage in this city)
    no_data = bool(provider and status and status.get("last_ok") and not status.get("readings"))

    resp = jsonify({
        "generated_at": now.isoformat(),
        "overall_level": _traffic_level(overall_avg),
        "overall_congestion_score": round(overall_avg, 1),
        "overall_traffic_score": max(0, min(10, int(round(overall_avg / 10)))),
        "data_source": {
            "provider": provider,                       # None = simulated
            "mode": "live" if live_n else ("warming_up" if (provider and not no_data) else "simulated"),
            "provider_returned_no_data": no_data,
            "live_streets": live_n,
            "estimated_streets": est_n,
            "total_streets": len(rows),
        },
        "streets": rows,
    })
    resp.headers["Cache-Control"] = "private, max-age=10"
    return resp


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

            # real/estimated street readings already ARE the current traffic; only the simulation is scaled by the city ratio
            adjusted_congestion = (state["congestion_score"] if state.get("traffic_source") in ("live", "estimated")
                                   else min(100.0, state["congestion_score"] * traffic_mult))
            traffic_factor = round(adjusted_congestion / 100.0, 2)

            adjusted_avail = max(3.0, min(97.0, state["availability_pct"] - (dest_busyness * 8.0) - (weather_factor * 6.0)))

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
                "traffic_source": state.get("traffic_source"),
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

    # Overall cap on password attempts from ALL addresses together, so guessing stays slow even if someone
    # hides behind many made-up addresses. (The cost: a flood of bad attempts can briefly lock admin login.)
    if not _check_rate_limit("login:all", max_requests=30, window_seconds=3600):
        return jsonify({"error": "Too many login attempts. Please wait a while and try again."}), 429

    data = request.get_json(silent=True) or {}
    submitted = str(data.get("password", ""))[:256]

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


# --------------------------------------------------------------------------
# Home-screen data: live parking outlook per place, and "where am I" street
# --------------------------------------------------------------------------
# The home screen shows one-tap shortcut cards ("Opera Theatre - Easy parking").
# This is the same scoring engine as /api/recommend, summarised to a single
# word per place so a visitor gets value before typing anything, and has a
# reason to come back later ("is it easy to park near Cascade right now?").
_OUTLOOK_CACHE: dict = {}
_OUTLOOK_TTL_S = 30.0
_OUTLOOK_MAX_POINTS = 10


def _outlook_level(best_score: float) -> str:
    """
    Top recommendation score -> how hard parking is right now. Best-spot scores for the
    landmarks range ~45-94 over a day/week, so the cut-offs split that range into
    roughly thirds; that keeps the cards informative (they differ by place and by hour)
    instead of reading "busy" all day.
    """
    if best_score >= 75:
        return "easy"
    if best_score >= 62:
        return "moderate"
    return "tough"


def _outlook_for_point(lat, lon, now, traffic_mult, weather):
    key = (round(lat, 4), round(lon, 4))
    stamp = time.time()
    hit = _OUTLOOK_CACHE.get(key)
    if hit and stamp - hit[0] < _OUTLOOK_TTL_S:
        return hit[1]

    candidates, _ = _compute_recommendations(lat, lon, 500.0, now, traffic_mult, weather)
    if candidates:
        best = candidates[0]
        out = {
            "level": _outlook_level(best["final_score"]),
            "score": best["final_score"],
            "walk_min": best["walk_time_min"],
            "spot": best["name"],
            "availability_pct": best["availability_pct"],
            "spots": len(candidates),
        }
    else:
        out = {"level": "unknown", "score": None, "walk_min": None, "spot": None,
               "availability_pct": None, "spots": 0}

    if len(_OUTLOOK_CACHE) > 500:
        _OUTLOOK_CACHE.clear()
    _OUTLOOK_CACHE[key] = (stamp, out)
    return out


@app.route("/api/outlook")
def api_outlook():
    """?pts=lat,lon|lat,lon|...  ->  one outlook per point that lies inside the service area."""
    points = []
    for chunk in request.args.get("pts", "").split("|")[:_OUTLOOK_MAX_POINTS]:
        try:
            lat_s, lon_s = chunk.split(",")
            lat, lon = float(lat_s), float(lon_s)
        except ValueError:
            continue
        if math.isfinite(lat) and math.isfinite(lon) and _in_service_area(lat, lon):
            points.append((lat, lon))
    if not points:
        return jsonify({"places": []})

    now = datetime.now()
    traffic_mult = fetch_live_traffic_multiplier()
    weather = fetch_live_weather()
    places = []
    for lat, lon in points:
        places.append({"lat": lat, "lon": lon, **_outlook_for_point(lat, lon, now, traffic_mult, weather)})

    resp = jsonify({"generated_at": now.isoformat(), "places": places})
    resp.headers["Cache-Control"] = "private, max-age=20"
    return resp


@app.route("/api/where")
def api_where():
    """Nearest named street to a point (for the 'Your location' chip and dropped pins)."""
    lat, lon = _opt_float(request.args.get("lat")), _opt_float(request.args.get("lon"))
    if lat is None or lon is None:
        return jsonify({"error": "lat and lon are required."}), 400

    best, best_d = None, float("inf")
    for f in _get_live_features():
        f_lat, f_lon = _extract_lat_lon(f)
        d = haversine_m(lat, lon, f_lat, f_lon)
        if d < best_d:
            best, best_d = f, d
    name = best.get("name") if best else None
    street = name if isinstance(name, str) and name.strip() and best_d <= 150 else None

    resp = jsonify({
        "street": street,
        "distance_m": round(best_d) if best else None,
        "in_service_area": _in_service_area(lat, lon),
    })
    resp.headers["Cache-Control"] = "private, max-age=30"
    return resp


@app.route("/api/admin/data-sources")
@require_admin
def api_admin_data_sources():
    """
    Admin-only health check for the live-data layer. ?probe=1 makes one real request to the
    active traffic provider and reports exactly what came back (use it right after setting a
    key: it answers "does this provider actually cover Yerevan?"). ?refresh_pois=1 re-downloads
    the OpenStreetMap POI inventory in the background.
    """
    keys = _provider_keys()
    provider = _active_traffic_provider()
    status, _ = _ld_get("traffic:status")
    doc, doc_ts = _ld_get("traffic:live")
    segs = [s for s in _segment_index()["by_id"].values() if s["type"] not in ("unavailable", "lot")]
    out = {
        "traffic": {
            "configured": {k: bool(v) for k, v in keys.items()},
            "preference": os.environ.get("TRAFFIC_PROVIDER", "auto"),
            "active_provider": provider,
            "status": status or {},
            "readings": len((doc or {}).get("readings", {})) if doc else 0,
            "segments": len(segs),
            "last_fetch_age_s": round(time.time() - doc_ts) if doc_ts else None,
            "budgets": {p: {"limit": _budget_limit(p)[0],
                            "used": int(_ld_get(f"budget:{p}:{datetime.utcnow().strftime(_budget_limit(p)[1])}")[0] or 0)}
                        for p in ("here", "tomtom", "yandex", "besttime")},
        },
    }

    if request.args.get("probe") == "1":
        probe = {"provider": provider}
        if not provider:
            probe["error"] = "No traffic provider is configured (set HERE_API_KEY, TOMTOM_API_KEY or YANDEX_ROUTING_API_KEY)."
        else:
            t0 = time.time()
            try:
                if provider == "here":
                    r = _here_readings(segs)
                    probe["matched_segments"] = len(r)
                    probe["sample"] = dict(list(r.items())[:3])
                else:
                    seg = min(segs, key=lambda s: haversine_m(MAP_CENTER[0], MAP_CENTER[1], s["lat"], s["lon"]))
                    probe["segment"] = seg["name"]
                    probe["sample"] = _PROBES[provider](seg)
                probe["ok"] = bool(probe.get("sample"))
                if not probe["ok"]:
                    probe["note"] = ("The call worked but returned no usable traffic for this area. "
                                     + ("HERE and TomTom do not list Armenia in their official traffic coverage, so this is expected for Yerevan."
                                        if provider in ("here", "tomtom") else "No coverage here, or the road was too short."))
            except Exception as exc:
                probe["ok"] = False
                probe["error"] = _redact(exc)
            probe["latency_ms"] = round((time.time() - t0) * 1000)
        out["probe"] = probe

    if request.args.get("refresh_pois") == "1":
        _run_in_background(_refresh_pois)
        out["poi_refresh"] = "started"
    st = _poi_state()
    by_type: dict = {}
    for p in st["pois"]:
        by_type[p["t"]] = by_type.get(p["t"], 0) + 1
    out["poi"] = {
        "source": st["source"],
        "count": len(st["pois"]),
        "with_opening_hours": sum(1 for p in st["pois"] if p.get("oh")),
        "age_h": round((time.time() - st["fetched_at"]) / 3600, 1) if st["fetched_at"] else None,
        "by_type": dict(sorted(by_type.items(), key=lambda kv: -kv[1])[:12]),
        "besttime_configured": bool(os.environ.get("BESTTIME_API_KEY", "").strip()),
    }
    out["yandex_map_view"] = _yandex_maps_status()
    return jsonify(out)


# --------------------------------------------------------------------------
# Keep-alive (Render's free tier stops a web service after ~15 min without inbound traffic)
# --------------------------------------------------------------------------
# While the service is running, a background thread requests the service's own PUBLIC url
# every KEEPALIVE_INTERVAL_S (default 10 min). That request goes out and back in through
# Render's edge, so it counts as real inbound traffic and the instance doesn't idle out.
#
# It only does this during Yerevan daytime, 08:00 - 24:00 (Armenia is UTC+4 all year, no
# daylight saving). Overnight the pings stop, so Render winds the service down after ~15 idle
# minutes and the free instance hours aren't spent while nobody is parking. A visitor at night
# simply wakes it (a ~30 s cold start) and it winds down again 15 minutes after the last request.
#   KEEPALIVE=off                  disable entirely
#   KEEPALIVE_START_HOUR / KEEPALIVE_END_HOUR   Yerevan hours (default 8 and 24)
#   KEEPALIVE_URL                  ping a different address (custom domain)
#   KEEPALIVE_INTERVAL_S           2-14 min, default 10
# /healthz is deliberately tiny and never touches the database, so pinging it doesn't keep a
# serverless Postgres (Neon) awake. A sleeping service can't ping itself: to be awake at 08:00
# sharp, point a free scheduler (cron-job.org) at /healthz for those hours (see the README note).
_KEEPALIVE = {"started": False}


@app.route("/healthz")
def healthz():
    resp = make_response("ok")
    resp.headers["Content-Type"] = "text/plain; charset=utf-8"
    resp.headers["Cache-Control"] = "no-store"
    return resp


_YEREVAN_UTC_OFFSET_H = 4        # Armenia has been UTC+4 year-round since 2012


def _yerevan_now() -> datetime:
    return datetime.utcnow() + timedelta(hours=_YEREVAN_UTC_OFFSET_H)


def _keepalive_hours() -> tuple[int, int]:
    def hour(name, default):
        try:
            return max(0, min(24, int(os.environ.get(name, default))))
        except ValueError:
            return default
    return hour("KEEPALIVE_START_HOUR", 8), hour("KEEPALIVE_END_HOUR", 24)


def _keepalive_active(local: datetime) -> bool:
    start, end = _keepalive_hours()
    return start <= local.hour < end if start < end else (local.hour >= start or local.hour < end)


def _seconds_until_window(local: datetime) -> float:
    start, _ = _keepalive_hours()
    target = local.replace(hour=start % 24, minute=0, second=0, microsecond=0)
    if target <= local:
        target += timedelta(days=1)
    return (target - local).total_seconds()


def _keepalive_loop(url: str, interval: float, now_fn=None):
    now_fn = now_fn or _yerevan_now
    time.sleep(min(60.0, interval))                       # let the server finish booting first
    while True:
        local = now_fn()
        if _keepalive_active(local):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": _UA + " keepalive"})
                with urllib.request.urlopen(req, timeout=25) as r:
                    r.read(8)
            except Exception as exc:
                print(f"[keepalive] ping failed ({_redact(exc)}); will retry")
            time.sleep(interval + random.uniform(0, 20))  # jitter so several workers don't ping in lockstep
        else:
            # night: say nothing, let Render wind the service down; wake exactly when the window opens
            time.sleep(min(interval, _seconds_until_window(local) + 5.0))


def _start_keepalive():
    if _KEEPALIVE["started"] or os.environ.get("KEEPALIVE", "on").strip().lower() == "off":
        return
    base = (os.environ.get("KEEPALIVE_URL") or os.environ.get("RENDER_EXTERNAL_URL") or "").strip().rstrip("/")
    if not base:
        return
    try:
        interval = max(120.0, min(840.0, float(os.environ.get("KEEPALIVE_INTERVAL_S", "600"))))
    except ValueError:
        interval = 600.0
    _KEEPALIVE["started"] = True
    url = base if base.endswith("/healthz") else base + "/healthz"
    threading.Thread(target=_keepalive_loop, args=(url, interval), daemon=True, name="keepalive").start()
    s, e = _keepalive_hours()
    print(f"[keepalive] pinging {url} every {int(interval)}s between {s:02d}:00 and {e:02d}:00 Yerevan time; winding down outside those hours")


@app.before_request
def _ensure_keepalive():
    # also covers servers that import the app once and then fork workers (the thread must start in the worker)
    if not _KEEPALIVE["started"]:
        _start_keepalive()


_start_keepalive()


# --------------------------------------------------------------------------
# Yandex live-traffic map (a viewer, not a data source)
# --------------------------------------------------------------------------
# Yandex's FREE Maps API terms say everything received through the API (explicitly "including
# information about traffic") must be shown on a Yandex map, so its traffic can't be drawn on the
# Leaflet map and can't be fed into this app's numbers. What the free tier does allow is a Yandex
# map with Yandex's own live-traffic layer, shown to the user. That is this page: it is embedded in
# the app (an iframe) when the user flips "Live traffic map" in the menu.
#
# It lives on its own URL so that the permissions Yandex's script needs ('unsafe-eval' plus a few
# Yandex origins) apply to this one page only, and the main app keeps its strict policy.
#   YANDEX_MAPS_API_KEY   (or YANDEX_API_KEY)  a free "JavaScript API" key from the Yandex Developer Dashboard
#                         (restrict it to your domain there). Without it the feature is off.
_YANDEX_KEY_RE = re.compile(r"^[A-Za-z0-9\-]{8,64}$")


def _yandex_maps_status() -> dict:
    """For the admin diagnostics page: is the key found, and does it look right? Never returns the key itself."""
    found = {n: bool(os.environ.get(n, "").strip()) for n in ("YANDEX_MAPS_API_KEY", "YANDEX_API_KEY")}
    raw = (os.environ.get("YANDEX_MAPS_API_KEY") or os.environ.get("YANDEX_API_KEY") or "").strip()
    return {
        "variables_present": found,
        "key_found": bool(raw),
        "looks_valid": bool(_YANDEX_KEY_RE.match(raw)),
        "length": len(raw),
        "hint": (raw[:4] + "…" + raw[-2:]) if len(raw) >= 10 else "",
        "toggle_enabled": bool(_yandex_maps_key()),
        "note": ("Not set: add YANDEX_MAPS_API_KEY in Render > Environment and redeploy." if not raw else
                 "The value has characters a Yandex key never has (quotes, spaces, a pasted label?). Paste only the key itself." if not _YANDEX_KEY_RE.match(raw) else
                 "Key found. If the traffic view still fails, open it and read the 'Reason' line."),
    }


def _yandex_maps_key() -> str:
    # read only from the environment (Render > Environment); no key is ever written in this file
    key = (os.environ.get("YANDEX_MAPS_API_KEY") or os.environ.get("YANDEX_API_KEY") or "").strip()
    return key if _YANDEX_KEY_RE.match(key) else ""


_YTRAFFIC_PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Live traffic</title>
<style>
  html, body, #map { margin: 0; padding: 0; width: 100%; height: 100%; overflow: hidden; background: #e9e7e2; }
  #err { position: absolute; inset: 0; display: none; align-items: center; justify-content: center; text-align: center;
         padding: 28px; font: 500 15px/1.5 -apple-system, system-ui, sans-serif; color: #eef0f4; background: #1b1d24; }
</style>
<script>
  function post(m) { try { parent.postMessage(Object.assign({ type: 'ytraffic' }, m), location.origin); } catch (e) {} }
  // the browser tells us when our own security policy blocks something Yandex needs: pass that on, it names the culprit
  document.addEventListener('securitypolicyviolation', function (e) {
    post({ event: 'csp', directive: e.violatedDirective, blocked: String(e.blockedURI || '').slice(0, 120) });
  });
  function fail(why) {
    var e = document.getElementById('err');
    if (e) { e.style.display = 'flex'; e.textContent = 'Yandex traffic could not be loaded here.'; }
    post({ event: 'error', why: why });
  }
</script>
<script src="https://api-maps.yandex.ru/2.1/?apikey=__KEY__&lang=en_US&csp=true" onerror="fail('script')"></script>
</head><body>
<div id="map"></div><div id="err"></div>
<script>
(function () {
  if (typeof ymaps === 'undefined') { fail('script'); return; }
  var q = new URLSearchParams(location.search);
  function num(k, d) { var v = parseFloat(q.get(k)); return isFinite(v) ? v : d; }
  ymaps.ready(function () {
    var map = new ymaps.Map('map', {
      center: [num('lat', 40.1792), num('lon', 44.5152)],
      zoom: Math.max(3, Math.min(19, Math.round(num('z', 15)))),
      controls: []
    });
    // zoom buttons on the right, clear of the app's own bar at the top-left
    map.controls.add(new ymaps.control.ZoomControl({ options: { position: { right: 12, top: 140 } } }));

    // The live traffic layer itself (infoLayerShown adds Yandex's own incident points + speed balloons).
    var traffic = new ymaps.traffic.provider.Actual({}, { infoLayerShown: true });
    traffic.setMap(map);
    function reportLevel() {
      try { var lv = traffic.state.get('level'); if (typeof lv === 'number') post({ event: 'level', level: lv }); } catch (e) {}
    }
    try { traffic.state.events.add('change', reportLevel); } catch (e) {}
    setTimeout(reportLevel, 2500);

    // context: where you are, where you are going, and the recommended spots
    var ulat = num('ulat', NaN), ulon = num('ulon', NaN);
    if (isFinite(ulat) && isFinite(ulon)) map.geoObjects.add(new ymaps.Placemark([ulat, ulon], { hintContent: 'You' }, { preset: 'islands#blueCircleDotIcon' }));
    var dlat = num('dlat', NaN), dlon = num('dlon', NaN);
    if (isFinite(dlat) && isFinite(dlon)) map.geoObjects.add(new ymaps.Placemark([dlat, dlon], { hintContent: q.get('dl') || 'Destination' }, { preset: 'islands#redDotIcon' }));
    (q.get('r') || '').split('|').slice(0, 3).forEach(function (p, i) {
      var c = p.split(',').map(parseFloat);
      if (c.length === 2 && isFinite(c[0]) && isFinite(c[1]))
        map.geoObjects.add(new ymaps.Placemark(c, { iconContent: String(i + 1), hintContent: 'Parking spot ' + (i + 1) }, { preset: 'islands#orangeCircleIcon' }));
    });

    // tell the app where the user ended up so its own map can follow when this view closes
    function view() { try { var c = map.getCenter(); post({ event: 'view', center: [c[0], c[1]], zoom: map.getZoom() }); } catch (e) {} }
    try { map.events.add('actionend', view); } catch (e) {}
    post({ event: 'ready' });
  }, function (err) { fail('init: ' + String((err && (err.message || err)) || 'unknown').slice(0, 100)); });
})();
</script></body></html>"""


@app.route("/traffic-map")
def traffic_map():
    key = _yandex_maps_key()
    if not key:
        return ("Not available", 404)
    resp = make_response(_YTRAFFIC_PAGE.replace("__KEY__", key))
    resp.headers["Content-Type"] = "text/html; charset=utf-8"
    resp.headers["Cache-Control"] = "no-store"
    return resp


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
