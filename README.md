# Yerevan Smart Parking Recommender

A production-ready full-stack application providing live-simulated curb and lot parking availability across central Yerevan (Kentron). It serves a dual purpose: a real-time recommendation engine for drivers and a robust data-collection platform to train future machine learning models.

---

## 🚀 Overview

Navigating parking in Yerevan's city center can be unpredictable. This application takes a data-driven approach by mapping real-time environmental factors (traffic, weather, time-of-day, and local POI busyness) to curated parking segments. It guides users to the most optimal parking spots while continuously logging user feedback (accepted vs. rejected recommendations) into a PostgreSQL database to improve future accuracy.

---

## ✨ Comprehensive Feature Set

### 1. Context-Aware Recommendation Engine (`/api/recommend`)
The core algorithm scores and ranks nearby parking candidates dynamically. Instead of just returning the closest spot, it weighs multiple real-time factors:
*   **Proximity (35%):** Walking distance calculated using the Haversine formula.
*   **Destination Busyness (25%):** Analyzes nearby Points of Interest (POIs). Uses time-of-day and day-of-week activity profiles (e.g., cafes peak in the morning, bars at night, offices during weekdays).
*   **Parking Type (10%):** Weighs user preferences between free curbside, paid curbside, and dedicated parking lots.
*   **Live Traffic (8%):** Adjusts congestion scores dynamically using the Yandex Routing API.
*   **Live Weather (2%):** Docks availability points slightly during adverse weather (rain, snow, extreme heat) via OpenWeather API.

### 2. Live Environmental Simulation
*   **Time-of-Day Curves:** Models organic city movement by mapping congestion curves (rush hour, off-peak, night) to individual parking segments.
*   **Day Differentiation:** Maintains distinct baseline congestion models for weekdays versus weekends.

### 3. Smart Search & Autocomplete (`/api/search`)
*   **Search-As-You-Type:** A lightning-fast geocoding engine that instantly matches queries against a curated list of local Yerevan landmarks and ground-truth parking segments.
*   **Phonetic Transliteration:** Built-in synonym mapping for Armenian streets (e.g., understands "mastoc", "մաշտոց", and "Mashtots" as the exact same query).
*   **Fuzzy Fallback:** Seamlessly falls back to the Photon API and OpenStreetMap Nominatim to handle specific house numbers and fuzzy typos.

### 4. Administrative Map Curation & Editing
*   **Interactive Admin UI:** Features an active modal allowing authorized administrators to draw (Lines or Polygons), update, or delete parking boundaries directly on the Leaflet map.
*   **Geofencing:** Automatically blocks segment saves if the drawn coordinates accidentally fall outside the Kentron (city center) bounding box.

### 5. Machine Learning Feedback Loop (`/api/admin/ml_feedback`)
*   **High-Fidelity Snapshots:** Captures rich contextual data whenever a user parks. 
*   **Data Logged:** Timestamps, exact GPS coordinates, active weather conditions, destination busyness, nearest segment matching, and boolean tracking on whether the user accepted the system's recommendation.
*   **Data Storage:** Safely stored in PostgreSQL for future predictive model training.

---

## 🛠 Tech Stack & Architecture

### Backend (Python / Flask)
*   **Framework:** Flask serves API endpoints, web pages, and request routing.
*   **Database:** **PostgreSQL** (via SQLAlchemy) is utilized as the primary database for the persistent, reliable storage of curated parking map geometries and ML feedback logs.
*   **Geospatial Processing:** Uses `OSMnx` and the `math` library (Haversine formula) for fetching, parsing, and calculating distances between spatial geometries (LineStrings and Polygons).

### Frontend (HTML / CSS / JS)
*   **Map Rendering:** Powered by **Leaflet.js** for high-performance interactive mapping and **Leaflet-Geoman** for on-the-fly geometry drawing and editing.
*   **Progressive Web App (PWA):** Configured with a `manifest.json` and a Service Worker (`sw.js`) for aggressive caching of static assets, allowing faster load times.
*   **Mobile-First UI/UX:** Fully responsive, custom CSS layout featuring a bottom-sheet drag architecture specifically optimized for mobile devices and iOS safe-area adaptations.

### External APIs & Integrations
*   **Traffic:** Yandex Routing API
*   **Weather:** OpenWeather API / Open-Meteo
*   **Geocoding:** Photon API & OpenStreetMap Nominatim

---

## ⚙️ Installation & Setup

**1. Clone the Repository**
```bash
git clone [https://github.com/yourusername/yerevan-smart-parking.git](https://github.com/yourusername/yerevan-smart-parking.git)
cd yerevan-smart-parking
