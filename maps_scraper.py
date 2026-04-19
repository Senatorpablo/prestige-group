#!/usr/bin/env python3
"""
Google Maps Business Scraper — Prestige Group
Finds businesses with poor or no websites in a given niche and area.
Uses Google Maps Places API (New) to search, then flags businesses
that lack a proper website.

Output: CSV file with all collected data + a "poor_website" flag.
"""

import csv
import time
import logging
import re
import urllib.parse
from datetime import datetime
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ──────────────────────────────────────────────────────────────
# CONFIGURATION — Edit these values before running
# ──────────────────────────────────────────────────────────────

CONFIG = {
    "api_key": "",                     # Google Maps Places API key
    "search_query": "plumbers",        # Business category / niche to search
    "location": "Austin, TX",          # City, State or "lat,lng" string
    "radius": 20000,                   # Search radius in metres (max 50000)
    "max_results": 60,                 # Cap on total businesses returned
    "output_dir": ".",                 # Directory for the output CSV
    # Website-quality heuristics
    "social_media_domains": [
        "facebook.com", "fb.com", "instagram.com", "youtu.be", "youtube.com",
        "tiktok.com", "twitter.com", "x.com", "linkedin.com", "yelp.com",
        "tripadvisor.com", "google.com", "goo.gl", "bit.ly", "t.co",
        "manta.com", "yellowpages.com", "yp.com", "bbb.org", "foursquare.com",
        "thumbtack.com", "angieslist.com", "homeadvisor.com", "porch.com",
    ],
    "request_timeout": 10,             # Seconds for website reachability check
    "requests_delay": 0.3,            # Delay between API calls (seconds)
}

# ──────────────────────────────────────────────────────────────
# LOGGING
# ──────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────
# HTTP SESSION (retries + connection pooling)
# ──────────────────────────────────────────────────────────────

def _make_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(total=3, backoff_factor=0.5, status_forcelist=[429, 500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry, pool_maxsize=10)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update({"User-Agent": "PrestigeGroup-Scraper/1.0"})
    return session

SESSION = _make_session()

# ──────────────────────────────────────────────────────────────
# GEOCODING  (location string → lat/lng)
# ──────────────────────────────────────────────────────────────

GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"

def geocode_location(location: str, api_key: str) -> dict:
    """Convert a human-readable location to {lat, lng} using the Geocoding API."""
    params = {"address": location, "key": api_key}
    resp = SESSION.get(GEOCODE_URL, params=params, timeout=CONFIG["request_timeout"])
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") != "OK" or not data.get("results"):
        raise ValueError(f"Geocoding failed for '{location}': {data.get('status')} — {data.get('error_message', '')}")
    loc = data["results"][0]["geometry"]["location"]
    log.info("Geocoded '%s' → (%s, %s)", location, loc["lat"], loc["lng"])
    return loc

# ──────────────────────────────────────────────────────────────
# PLACES API — Nearby Search (classic) + Place Details
# ──────────────────────────────────────────────────────────────

NEARBY_URL = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"

def _nearby_search(lat: float, lng: float, query: str, radius: int, api_key: str, max_results: int) -> list[str]:
    """Return a list of place_ids using Nearby Search with keyword."""
    place_ids: list[str] = []
    params = {
        "location": f"{lat},{lng}",
        "radius": radius,
        "keyword": query,
        "key": api_key,
    }
    page = 0
    while True:
        page += 1
        log.info("Nearby search — page %d (collected %d places)", page, len(place_ids))
        resp = SESSION.get(NEARBY_URL, params=params, timeout=CONFIG["request_timeout"])
        resp.raise_for_status()
        data = resp.json()

        if data.get("status") not in ("OK", "ZERO_RESULTS"):
            log.warning("Nearby search returned status: %s — %s", data.get("status"), data.get("error_message", ""))

        for place in data.get("results", []):
            pid = place.get("place_id")
            if pid and pid not in place_ids:
                place_ids.append(pid)

        if len(place_ids) >= max_results:
            break

        token = data.get("next_page_token")
        if not token:
            break

        # Google requires a short delay before the next-page token is valid
        time.sleep(2)
        params = {"pagetoken": token, "key": api_key}

    return place_ids[:max_results]


def _place_details(place_id: str, api_key: str) -> dict:
    """Fetch detailed info for a single place."""
    params = {
        "place_id": place_id,
        "fields": "name,formatted_address,formatted_phone_number,website,rating,user_ratings_total,types,business_status",
        "key": api_key,
    }
    resp = SESSION.get(DETAILS_URL, params=params, timeout=CONFIG["request_timeout"])
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") != "OK":
        log.warning("Details for %s: %s", place_id, data.get("status"))
        return {}
    return data.get("result", {})

# ──────────────────────────────────────────────────────────────
# WEBSITE QUALITY CHECK  (heuristic)
# ──────────────────────────────────────────────────────────────

def _classify_website(url: str | None) -> dict:
    """
    Return {has_website, poor_website, website_status, website_reason}.
    Heuristics:
      - No URL at all  →  no website
      - URL domain is a known social / directory  →  poor
      - HEAD request fails or returns 4xx/5xx  →  poor (unreachable)
      - Otherwise  →  looks OK
    """
    result = {
        "has_website": False,
        "poor_website": True,
        "website_status": "",
        "website_reason": "no website listed",
    }

    if not url:
        return result

    url = url.strip()
    if not url:
        return result

    result["has_website"] = True
    result["poor_website"] = False
    result["website_reason"] = "looks ok"

    # Parse domain
    try:
        parsed = urllib.parse.urlparse(url)
        domain = (parsed.netloc or parsed.path).lower()
        # Strip "www." prefix
        domain = re.sub(r"^www\.", "", domain)
    except Exception:
        result["poor_website"] = True
        result["website_reason"] = "malformed URL"
        result["website_status"] = "invalid"
        return result

    # Check if domain is a social/directory site
    for social in CONFIG["social_media_domains"]:
        if domain == social or domain.endswith("." + social):
            result["poor_website"] = True
            result["website_reason"] = f"social/directory only ({social})"
            result["website_status"] = "social"
            return result

    # Try a HEAD request to see if the site is reachable
    try:
        head = SESSION.head(url, timeout=CONFIG["request_timeout"], allow_redirects=True)
        result["website_status"] = str(head.status_code)
        if head.status_code >= 400:
            result["poor_website"] = True
            result["website_reason"] = f"HTTP {head.status_code}"
    except requests.RequestException as exc:
        result["poor_website"] = True
        result["website_reason"] = f"unreachable ({type(exc).__name__})"
        result["website_status"] = "error"

    return result

# ──────────────────────────────────────────────────────────────
# MAIN PIPELINE
# ──────────────────────────────────────────────────────────────

CSV_FIELDS = [
    "name",
    "address",
    "phone",
    "website",
    "rating",
    "review_count",
    "category",
    "business_status",
    "has_website",
    "poor_website",
    "website_status",
    "website_reason",
    "place_id",
]


def run():
    cfg = CONFIG
    api_key = cfg["api_key"]
    if not api_key:
        log.error("No API key set in CONFIG. Add your Google Maps Places API key and re-run.")
        return

    # 1. Geocode the location
    coords = geocode_location(cfg["location"], api_key)

    # 2. Nearby search to get place IDs
    place_ids = _nearby_search(
        lat=coords["lat"],
        lng=coords["lng"],
        query=cfg["search_query"],
        radius=cfg["radius"],
        api_key=api_key,
        max_results=cfg["max_results"],
    )
    log.info("Found %d places. Fetching details …", len(place_ids))

    # 3. Fetch details for each place
    rows: list[dict] = []
    for i, pid in enumerate(place_ids, 1):
        time.sleep(cfg["requests_delay"])
        log.info("[%d/%d] Fetching details for %s", i, len(place_ids), pid)
        details = _place_details(pid, api_key)
        if not details:
            continue

        url = details.get("website") or ""
        web_info = _classify_website(url)

        # Pick the most human-readable type as "category"
        types = details.get("types", [])
        category = ", ".join(t.replace("_", " ") for t in types if t not in ("political", "locality"))

        row = {
            "name": details.get("name", ""),
            "address": details.get("formatted_address", ""),
            "phone": details.get("formatted_phone_number", ""),
            "website": url,
            "rating": details.get("rating", ""),
            "review_count": details.get("user_ratings_total", 0),
            "category": category,
            "business_status": details.get("business_status", ""),
            "has_website": web_info["has_website"],
            "poor_website": web_info["poor_website"],
            "website_status": web_info["website_status"],
            "website_reason": web_info["website_reason"],
            "place_id": pid,
        }
        rows.append(row)

        if web_info["poor_website"]:
            log.info("  ⚠  POOR WEBSITE: %s — %s", details.get("name", ""), web_info["website_reason"])

    # 4. Write CSV
    out_dir = Path(cfg["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    slug = cfg["search_query"].replace(" ", "_").lower()
    csv_path = out_dir / f"maps_{slug}_{timestamp}.csv"

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    # 5. Summary
    total = len(rows)
    poor = sum(1 for r in rows if r["poor_website"])
    no_site = sum(1 for r in rows if not r["has_website"])
    social_only = sum(1 for r in rows if r["has_website"] and r["poor_website"] and r["website_status"] == "social")
    unreachable = sum(1 for r in rows if r["has_website"] and r["poor_website"] and r["website_status"] != "social")

    log.info("=" * 55)
    log.info("DONE — %d businesses processed", total)
    log.info("  No website:        %d", no_site)
    log.info("  Social/directory:  %d", social_only)
    log.info("  Unreachable site:  %d", unreachable)
    log.info("  Total poor:        %d", poor)
    log.info("  Looks OK:          %d", total - poor)
    log.info("CSV → %s", csv_path)
    log.info("=" * 55)

    return csv_path


if __name__ == "__main__":
    run()