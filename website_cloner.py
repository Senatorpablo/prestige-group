#!/usr/bin/env python3
"""
Website Cloner — Prestige Group
Clones a business website's content/structure and generates a clean, modern,
responsive HTML replacement site.

Usage:
    python website_cloner.py <URL>
    python website_cloner.py https://example.com
    python website_cloner.py https://example.com --output /custom/path
"""

import argparse
import json
import os
import re
import sys
import textwrap
import unicodedata
import urllib.parse
from pathlib import Path

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("Missing dependencies. Install with:\n  pip install requests beautifulsoup4")
    sys.exit(1)

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
REQUEST_TIMEOUT = 20  # seconds
MAX_IMAGE_DOWNLOADS = 15
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

# Regex helpers
PHONE_RE = re.compile(
    r'(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', re.VERBOSE
)
EMAIL_RE = re.compile(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+')
HEX_COLOR_RE = re.compile(r'#[0-9a-fA-F]{3,8}\b')
RGB_COLOR_RE = re.compile(r'rgb\(\s*\d{1,3}\s*,\s*\d{1,3}\s*,\s*\d{1,3}\s*\)')


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def slugify(text: str) -> str:
    """Convert text to a filesystem-safe slug."""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r'[^\w\s-]', '', text).strip().lower()
    return re.sub(r'[-\s]+', '-', text) or "unknown-business"


def clean_text(text: str) -> str:
    """Collapse whitespace and strip."""
    return re.sub(r'\s+', ' ', text).strip()


def resolve_url(base: str, href: str) -> str:
    """Resolve a possibly-relative URL against a base."""
    if not href:
        return ""
    return urllib.parse.urljoin(base, href)


def is_reasonable_image_url(url: str) -> bool:
    """Heuristic: skip tiny icons, tracking pixels, data-URIs, SVG sprites."""
    if not url or url.startswith("data:"):
        return False
    lower = url.lower()
    skip_patterns = [
        "pixel", "spacer", "blank", "transparent", "1x1",
        "favicon", "icon", "bullet", "arrow", "dot",
        ".svg", "tracking", "analytics", "gravatar",
    ]
    return not any(p in lower for p in skip_patterns)


def rgb_to_hex(rgb_match: str) -> str:
    """Convert an rgb() string to #rrggbb."""
    nums = re.findall(r'\d{1,3}', rgb_match)
    if len(nums) >= 3:
        return '#' + ''.join(f'{int(n):02x}' for n in nums[:3])
    return rgb_match


def luminance(hex_c: str) -> float:
    """Compute relative luminance of a hex color (0–1)."""
    h = hex_c.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    try:
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    except (ValueError, IndexError):
        return 0.5
    return (0.299 * r + 0.587 * g + 0.114 * b) / 255


# ---------------------------------------------------------------------------
# Fetching
# ---------------------------------------------------------------------------

def fetch_html(url: str) -> tuple:
    """Fetch the page HTML. Returns (html, final_url)."""
    headers = {"User-Agent": USER_AGENT}
    try:
        resp = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT,
                            allow_redirects=True)
        resp.raise_for_status()
        if not resp.encoding or resp.encoding.lower() == "iso-8859-1":
            resp.encoding = resp.apparent_encoding or "utf-8"
        return resp.text, resp.url
    except requests.exceptions.SSLError:
        try:
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                resp = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT,
                                    allow_redirects=True, verify=False)
                resp.raise_for_status()
                if not resp.encoding or resp.encoding.lower() == "iso-8859-1":
                    resp.encoding = resp.apparent_encoding or "utf-8"
                return resp.text, resp.url
        except Exception as e2:
            raise ConnectionError(f"SSL error and fallback failed: {e2}")
    except requests.exceptions.ConnectionError as e:
        raise ConnectionError(f"Could not connect to {url}: {e}")
    except requests.exceptions.Timeout:
        raise ConnectionError(f"Timeout fetching {url}")
    except requests.exceptions.HTTPError as e:
        raise ConnectionError(
            f"HTTP error {e.response.status_code} for {url}")
    except Exception as e:
        raise ConnectionError(f"Error fetching {url}: {e}")


# ---------------------------------------------------------------------------
# Screenshot / thumbnail
# ---------------------------------------------------------------------------

def save_screenshot(url: str, output_path: str) -> bool:
    """Attempt to save a screenshot of the URL. Returns True on success."""
    # Try Playwright first
    try:
        from playwright.sync_api import sync_playwright  # noqa
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1280, "height": 800})
            page.goto(url, timeout=REQUEST_TIMEOUT * 1000,
                      wait_until="domcontentloaded")
            page.wait_for_timeout(2000)
            page.screenshot(path=output_path, full_page=False)
            browser.close()
        return True
    except ImportError:
        pass
    except Exception as e:
        print(f"  [warn] Playwright screenshot failed: {e}")

    # Try Selenium
    try:
        from selenium import webdriver  # noqa
        from selenium.webdriver.chrome.options import Options  # noqa
        opts = Options()
        opts.add_argument("--headless=new")
        opts.add_argument("--disable-gpu")
        opts.add_argument("--window-size=1280,800")
        opts.add_argument(f"--user-agent={USER_AGENT}")
        driver = webdriver.Chrome(options=opts)
        driver.get(url)
        driver.save_screenshot(output_path)
        driver.quit()
        return True
    except ImportError:
        pass
    except Exception as e:
        print(f"  [warn] Selenium screenshot failed: {e}")

    print("  [info] No screenshot tool available "
          "(install playwright: pip install playwright && playwright install chromium)")
    return False


def generate_placeholder_thumbnail(output_path: str, business_name: str):
    """Create a simple SVG placeholder thumbnail."""
    safe_name = business_name[:40].replace("&", "&amp;").replace("<", "&lt;")
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="800"'
        ' viewBox="0 0 1280 800">'
        '<rect width="1280" height="800" fill="#6366f1"/>'
        f'<text x="640" y="380" text-anchor="middle" fill="#fff"'
        f' font-family="Arial,Helvetica,sans-serif" font-size="48"'
        f' font-weight="bold">{safe_name}</text>'
        f'<text x="640" y="430" text-anchor="middle" fill="#c7d2fe"'
        f' font-family="Arial,Helvetica,sans-serif" font-size="20">'
        'Original site screenshot unavailable</text>'
        '</svg>'
    )
    svg_path = output_path.rsplit(".", 1)[0] + ".svg"
    Path(svg_path).write_text(svg, encoding="utf-8")


# ---------------------------------------------------------------------------
# Content extraction
# ---------------------------------------------------------------------------

def extract_colors(soup: BeautifulSoup, html: str) -> dict:
    """Extract dominant color scheme from CSS and inline styles."""
    colors: dict = {}

    # From inline styles
    for tag in soup.find_all(style=True):
        style = tag.get("style", "")
        for m in HEX_COLOR_RE.finditer(style):
            c = m.group().lower()
            colors[c] = colors.get(c, 0) + 1
        for m in RGB_COLOR_RE.finditer(style):
            c = rgb_to_hex(m.group()).lower()
            colors[c] = colors.get(c, 0) + 1

    # From <style> blocks
    for style_tag in soup.find_all("style"):
        css = style_tag.get_text()
        for m in HEX_COLOR_RE.finditer(css):
            c = m.group().lower()
            colors[c] = colors.get(c, 0) + 1
        for m in RGB_COLOR_RE.finditer(css):
            c = rgb_to_hex(m.group()).lower()
            colors[c] = colors.get(c, 0) + 1

    # Filter out white/black/generic
    generic = {"#fff", "#ffffff", "#000", "#000000", "#none"}
    filtered = {c: n for c, n in colors.items()
                if c not in generic and len(c) >= 4 and not c.startswith("#none")}

    # Sort by frequency
    sorted_colors = sorted(filtered.items(), key=lambda x: -x[1])

    # Pick primary from dark-enough colors (visible on white)
    dark_candidates = [(c, n) for c, n in sorted_colors if luminance(c) < 0.65]
    if dark_candidates:
        primary = dark_candidates[0][0]
    else:
        primary = "#4f46e5"

    secondary = dark_candidates[1][0] if len(dark_candidates) > 1 else "#7c3aed"
    # Accent: use a warm/vivid color — prefer non-blue/purple, must be visible on white
    vivid_candidates = [
        (c, n) for c, n in sorted_colors
        if 0.25 <= luminance(c) <= 0.75
        and c not in (primary, secondary)
    ]
    accent = vivid_candidates[0][0] if vivid_candidates else "#f59e0b"

    text_on_primary = "#ffffff" if luminance(primary) < 0.45 else "#1f2937"

    return {
        "primary": primary,
        "secondary": secondary,
        "accent": accent,
        "text_on_primary": text_on_primary,
        "bg": "#ffffff",
        "text": "#1f2937",
        "text_secondary": "#6b7280",
        "border": "#e5e7eb",
    }


def extract_logo(soup: BeautifulSoup, base_url: str) -> str:
    """Heuristic logo extraction."""
    candidates = []

    # 1. <img> with logo-related class/id/src/alt
    for img in soup.find_all("img"):
        cl = img.get("class", [])
        if isinstance(cl, list):
            cl = " ".join(cl)
        attrs_str = " ".join([
            cl,
            str(img.get("id", "")),
            img.get("src", ""),
            img.get("alt", ""),
        ]).lower()
        if any(k in attrs_str for k in ["logo", "brand"]):
            src = resolve_url(base_url, img.get("src", ""))
            candidates.append((src, 10))

    # 2. First image in <header> or <nav>
    for container in soup.find_all(["header", "nav"]):
        img = container.find("img")
        if img:
            src = resolve_url(base_url, img.get("src", ""))
            candidates.append((src, 6))

    # 3. Link with homepage href containing an image
    parsed_base = urllib.parse.urlparse(base_url)
    for a in soup.find_all("a", href=True):
        href = a.get("href", "").rstrip("/")
        home_like = href in [
            "/", "",
            parsed_base.path.rstrip("/") or "/",
            f"{parsed_base.scheme}://{parsed_base.netloc}",
            f"{parsed_base.scheme}://{parsed_base.netloc}/",
        ]
        if home_like:
            img = a.find("img")
            if img:
                src = resolve_url(base_url, img.get("src", ""))
                candidates.append((src, 5))

    if candidates:
        candidates.sort(key=lambda x: -x[1])
        return candidates[0][0]
    return ""


def extract_business_name(soup: BeautifulSoup) -> str:
    """Extract the business / site name."""
    # <title> tag
    title_tag = soup.find("title")
    if title_tag:
        title = clean_text(title_tag.get_text())
        for suffix in [" - Home", " | Home", " — Home", " - Homepage",
                        " | Welcome", " - Welcome", " | Official Site",
                        " - Official Site", " | Official Website"]:
            if title.endswith(suffix):
                title = title[:-len(suffix)].strip()
        for sep in [" | ", " - ", " — ", " · ", " » "]:
            if sep in title:
                parts = title.split(sep)
                title = min(parts, key=len).strip()
                break
        if title:
            return title

    # <meta property="og:site_name">
    meta = soup.find("meta", attrs={"property": "og:site_name"})
    if meta and meta.get("content"):
        return clean_text(meta["content"])

    # <meta name="application-name">
    meta = soup.find("meta", attrs={"name": "application-name"})
    if meta and meta.get("content"):
        return clean_text(meta["content"])

    # Heading h1
    h1 = soup.find("h1")
    if h1:
        return clean_text(h1.get_text())

    return "Business"


def extract_tagline(soup: BeautifulSoup) -> str:
    """Extract a tagline / slogan."""
    meta = soup.find("meta", attrs={"property": "og:description"})
    if meta and meta.get("content"):
        t = clean_text(meta["content"])
        if len(t) < 200:
            return t

    meta = soup.find("meta", attrs={"name": "description"})
    if meta and meta.get("content"):
        t = clean_text(meta["content"])
        if len(t) < 200:
            return t

    for sel in ["header h2", "header p", ".hero h2", ".hero p",
                "#hero h2", "#hero p", ".banner h2", ".banner p",
                "h2.subtitle", "p.subtitle", "p.tagline"]:
        try:
            el = soup.select_one(sel)
            if el:
                t = clean_text(el.get_text())
                if 10 < len(t) < 200:
                    return t
        except Exception:
            continue

    return ""


def extract_about(soup: BeautifulSoup) -> str:
    """Extract 'about' text."""
    for sel in ["#about", ".about", "#about-us", ".about-us",
                "#about-us-section", ".about-section",
                "section.about", "div.about"]:
        el = soup.select_one(sel)
        if el:
            paras = el.find_all("p")
            if paras:
                best = max(paras, key=lambda p: len(p.get_text()))
                t = clean_text(best.get_text())
                if len(t) > 30:
                    return t
            t = clean_text(el.get_text())
            if len(t) > 30:
                return t[:800]

    meta = soup.find("meta", attrs={"name": "description"})
    if meta and meta.get("content"):
        t = clean_text(meta["content"])
        if len(t) > 30:
            return t

    paras = soup.find_all("p")
    if paras:
        best = max(paras, key=lambda p: len(p.get_text()))
        t = clean_text(best.get_text())
        if len(t) > 30:
            return t[:800]

    return ""


def extract_services(soup: BeautifulSoup) -> list:
    """Extract a list of services."""
    services = []

    for sel in ["#services", ".services", "#service", ".service",
                "#what-we-do", ".what-we-do",
                "section.services", "div.services"]:
        el = soup.select_one(sel)
        if el:
            for li in el.find_all("li"):
                t = clean_text(li.get_text())
                if 2 < len(t) < 150:
                    services.append(t)
            if not services:
                for heading in el.find_all(["h3", "h4", "h5"]):
                    t = clean_text(heading.get_text())
                    if 2 < len(t) < 80:
                        services.append(t)
            if not services:
                for card in el.find_all(["div", "article"]):
                    heading = card.find(["h3", "h4", "h5", "strong"])
                    if heading:
                        t = clean_text(heading.get_text())
                        if 2 < len(t) < 80:
                            services.append(t)
            if services:
                break

    # Deduplicate
    seen = set()
    unique = []
    for s in services:
        sl = s.lower()
        if sl not in seen:
            seen.add(sl)
            unique.append(s)

    return unique[:20]


def extract_contact(soup: BeautifulSoup, html: str, base_url: str) -> dict:
    """Extract contact information."""
    contact = {
        "phone": "",
        "email": "",
        "address": "",
        "social": {},
    }

    # Phone
    phones = PHONE_RE.findall(html)
    if phones:
        contact["phone"] = phones[0]

    # Email
    emails = EMAIL_RE.findall(html)
    for e in emails:
        lower = e.lower()
        if not any(k in lower for k in ["example.com", "test.com", "domain.com",
                                          "sentry", "noreply", "no-reply",
                                          "mailchimp", "webpack"]):
            contact["email"] = e
            break

    # Look for contact section or footer
    for sel in ["#contact", ".contact", "#contact-us", ".contact-us",
                "section.contact", "div.contact", "footer"]:
        el = soup.select_one(sel)
        if el:
            text = el.get_text(" ", strip=True)
            addr_match = re.search(
                r'\d+\s+[A-Za-z\s.,]+(?:St|Street|Ave|Avenue|Blvd|Boulevard|'
                r'Rd|Road|Dr|Drive|Ln|Lane|Way|Ct|Court|Pl|Place|Pkwy|Parkway)\.?',
                text
            )
            if addr_match:
                start = max(0, addr_match.start() - 5)
                end = min(len(text), addr_match.end() + 80)
                contact["address"] = clean_text(text[start:end])

            if not contact["phone"]:
                p = PHONE_RE.search(text)
                if p:
                    contact["phone"] = p.group()

            if not contact["email"]:
                e = EMAIL_RE.search(text)
                if e:
                    contact["email"] = e.group()
            break

    # Social links
    for a in soup.find_all("a", href=True):
        href = a["href"].lower()
        if "facebook.com" in href:
            contact["social"]["facebook"] = a["href"]
        elif "twitter.com" in href or "x.com" in href:
            contact["social"]["twitter"] = a["href"]
        elif "instagram.com" in href:
            contact["social"]["instagram"] = a["href"]
        elif "linkedin.com" in href:
            contact["social"]["linkedin"] = a["href"]
        elif "youtube.com" in href:
            contact["social"]["youtube"] = a["href"]
        elif "yelp.com" in href:
            contact["social"]["yelp"] = a["href"]
        elif "tiktok.com" in href:
            contact["social"]["tiktok"] = a["href"]

    return contact


def extract_images(soup: BeautifulSoup, base_url: str) -> list:
    """Extract notable images from the page."""
    images = []

    for img in soup.find_all("img"):
        src = (img.get("src") or img.get("data-src")
               or img.get("data-lazy-src") or "")
        src = resolve_url(base_url, src)
        if not is_reasonable_image_url(src):
            continue
        try:
            w = int(img.get("width", 0) or 0)
            h = int(img.get("height", 0) or 0)
            if 0 < w < 50 or 0 < h < 50:
                continue
        except (ValueError, TypeError):
            pass
        if src not in images:
            images.append(src)
        if len(images) >= MAX_IMAGE_DOWNLOADS:
            break

    return images


# ---------------------------------------------------------------------------
# HTML generation
# ---------------------------------------------------------------------------

def generate_cloned_html(data: dict) -> str:
    """Generate a professional, modern, responsive HTML file from extracted data."""

    c = data.get("colors", {})
    name = data.get("business_name", "Business")
    tagline = data.get("tagline", "")
    about = data.get("about", "")
    services = data.get("services", [])
    contact = data.get("contact", {})
    logo = data.get("logo_url", "")
    images = data.get("images", [])

    primary = c.get("primary", "#4f46e5")
    secondary = c.get("secondary", "#7c3aed")
    accent = c.get("accent", "#f59e0b")
    text_on_primary = c.get("text_on_primary", "#ffffff")

    # Service icons (inline SVGs)
    service_icons = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>',
        '<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="7" width="20" height="14" rx="2" ry="2"/><path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/></svg>',
        '<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>',
        '<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>',
        '<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>',
        '<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>',
    ]

    social_icons = {
        "facebook": '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M18 2h-3a5 5 0 0 0-5 5v3H7v4h3v8h4v-8h3l1-4h-4V7a1 1 0 0 1 1-1h3z"/></svg>',
        "twitter": '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M23 3a10.9 10.9 0 0 1-3.14 1.53 4.48 4.48 0 0 0-7.86 3v1A10.66 10.66 0 0 1 3 4s-4 9 5 13a11.64 11.64 0 0 1-7 2c9 5 20 0 20-11.5a4.5 4.5 0 0 0-.08-.83A7.72 7.72 0 0 0 23 3z"/></svg>',
        "instagram": '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="2" width="20" height="20" rx="5" ry="5"/><path d="M16 11.37A4 4 0 1 1 12.63 8 4 4 0 0 1 16 11.37z"/><line x1="17.5" y1="6.5" x2="17.51" y2="6.5"/></svg>',
        "linkedin": '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-2-2 2 2 0 0 0-2 2v7h-4v-7a6 6 0 0 1 6-6z"/><rect x="2" y="9" width="4" height="12"/><circle cx="4" cy="4" r="2"/></svg>',
        "youtube": '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M22.54 6.42a2.78 2.78 0 0 0-1.94-2C18.88 4 12 4 12 4s-6.88 0-8.6.46a2.78 2.78 0 0 0-1.94 2A29 29 0 0 0 1 11.75a29 29 0 0 0 .46 5.33A2.78 2.78 0 0 0 3.4 19.1c1.72.46 8.6.46 8.6.46s6.88 0 8.6-.46a2.78 2.78 0 0 0 1.94-2 29 29 0 0 0 .46-5.25 29 29 0 0 0-.46-5.43z"/><polygon points="9.75 15.02 15.5 11.75 9.75 8.48 9.75 15.02" fill="#fff"/></svg>',
        "yelp": '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="12" r="10"/></svg>',
        "tiktok": '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M19.59 6.69a4.83 4.83 0 0 1-3.77-4.25V2h-3.45v13.67a2.89 2.89 0 0 1-2.88 2.5 2.89 2.89 0 0 1-2.89-2.89 2.89 2.89 0 0 1 2.89-2.89c.28 0 .54.04.79.1V9.01a6.27 6.27 0 0 0-.79-.05 6.34 6.34 0 0 0-6.34 6.34 6.34 6.34 0 0 0 6.34 6.34 6.34 6.34 0 0 0 6.34-6.34V8.75a8.18 8.18 0 0 0 4.76 1.52V6.84a4.84 4.84 0 0 1-1-.15z"/></svg>',
    }

    # Hero background
    hero_images = [i for i in images
                   if any(kw in i.lower() for kw in
                          ["hero", "banner", "slide", "background",
                           "cover", "hero-", "bg-"])][:2]
    if not hero_images and images:
        hero_images = images[:1]

    hero_style = (f"background: linear-gradient(135deg, {primary} 0%,"
                  f" {secondary} 100%);")
    if hero_images:
        hero_style = (
            f"background-image: linear-gradient(135deg,"
            f" {primary}dd 0%, {secondary}bb 100%),"
            f" url('{hero_images[0]}');"
            " background-size: cover; background-position: center;"
        )

    # Logo
    if logo and logo != "SVG_EMBEDDED":
        logo_html = (f'<img src="{logo}" alt="{name} Logo"'
                     f' style="height:40px;max-width:180px;object-fit:contain;">')
    else:
        logo_html = (f'<span style="font-size:1.5rem;font-weight:800;'
                     f'color:{primary};">{name[:30]}</span>')

    # Services HTML
    services_html = ""
    if services:
        service_cards = []
        for idx, svc in enumerate(services[:6]):
            icon = service_icons[idx % len(service_icons)]
            card = (
                '<div style="background:#ffffff;border-radius:12px;padding:2rem;'
                'text-align:center;box-shadow:0 1px 3px rgba(0,0,0,.1);'
                f'border:1px solid #e5e7eb;transition:transform .2s,box-shadow .2s;"'
                ' onmouseover="this.style.transform=\'translateY(-4px)\';'
                'this.style.boxShadow=\'0 12px 24px rgba(0,0,0,.15)\'"'
                ' onmouseout="this.style.transform=\'\';'
                'this.style.boxShadow=\'0 1px 3px rgba(0,0,0,.1)\'">'
                f'  <div style="display:inline-flex;align-items:center;'
                f'justify-content:center;width:60px;height:60px;border-radius:50%;'
                f'background:{primary}15;color:{primary};margin-bottom:1rem;">'
                f'    {icon}'
                '  </div>'
                f'  <h3 style="font-size:1.15rem;font-weight:700;'
                f'color:#1f2937;margin:0 0 .5rem;">{svc}</h3>'
                '</div>'
            )
            service_cards.append(card)
        services_html = (
            f'<section style="padding:5rem 1.5rem;background:#ffffff;">'
            '  <div style="max-width:1100px;margin:0 auto;text-align:center;">'
            f'    <h2 style="font-size:2rem;font-weight:800;color:#1f2937;'
            f'margin:0 0 .5rem;">Our Services</h2>'
            f'    <p style="color:#6b7280;max-width:600px;margin:0 auto 2.5rem;'
            f'font-size:1.05rem;line-height:1.6;">What we offer to help you succeed.</p>'
            f'    <div style="display:grid;grid-template-columns:'
            f'repeat(auto-fit,minmax(260px,1fr));gap:1.5rem;">'
            f'      {"".join(service_cards)}'
            '    </div>'
            '  </div>'
            '</section>'
        )

    # About HTML
    about_html = ""
    if about:
        other_images = [i for i in images if i not in hero_images][:2]
        about_img = ""
        if other_images:
            about_img = (
                '<div style="flex:1;min-width:280px;">'
                f'  <img src="{other_images[0]}" alt="About {name}"'
                '   style="width:100%;border-radius:12px;object-fit:cover;max-height:400px;">'
                '</div>'
            )
        about_html = (
            '<section style="padding:5rem 1.5rem;background:#ffffff;">'
            '  <div style="max-width:1100px;margin:0 auto;display:flex;'
            'gap:3rem;flex-wrap:wrap;align-items:center;">'
            '    <div style="flex:1.2;min-width:280px;">'
            f'      <h2 style="font-size:2rem;font-weight:800;color:#1f2937;'
            f'margin:0 0 1rem;">About Us</h2>'
            f'      <p style="color:#6b7280;font-size:1.05rem;line-height:1.8;'
            f'margin:0;">{about}</p>'
            '    </div>'
            f'    {about_img}'
            '  </div>'
            '</section>'
        )

    # Contact HTML
    phone_line = (f'<p style="margin:.25rem 0;">&#9742; {contact["phone"]}</p>'
                  if contact.get("phone") else "")
    email_line = (
        f'<p style="margin:.25rem 0;">&#9993;'
        f' <a href="mailto:{contact["email"]}"'
        f' style="color:{text_on_primary};text-decoration:none;">'
        f'{contact["email"]}</a></p>'
        if contact.get("email") else ""
    )
    addr_line = (
        f'<p style="margin:.25rem 0;">&#9872; {contact["address"]}</p>'
        if contact.get("address") else ""
    )

    social_links = ""
    for platform, url in contact.get("social", {}).items():
        icon_svg = social_icons.get(platform, "")
        social_links += (
            f'<a href="{url}" target="_blank" rel="noopener"'
            f' style="color:{text_on_primary};margin:0 .5rem;'
            f'text-decoration:none;display:inline-flex;align-items:center;">'
            f'{icon_svg}</a>'
        )

    contact_html = ""
    if phone_line or email_line or addr_line or social_links:
        contact_html = (
            f'<section style="padding:5rem 1.5rem;'
            f'background:linear-gradient(135deg,{primary},{secondary});'
            f'color:{text_on_primary};">'
            '  <div style="max-width:700px;margin:0 auto;text-align:center;">'
            f'    <h2 style="font-size:2rem;font-weight:800;'
            f'margin:0 0 1.5rem;">Get In Touch</h2>'
            f'    <div style="font-size:1.05rem;line-height:1.8;">'
            f'      {phone_line}{email_line}{addr_line}'
            '    </div>'
            + (f'<div style="margin-top:1.5rem;font-size:1.2rem;">'
               f'{social_links}</div>' if social_links else '')
            + '  </div>'
            '</section>'
        )

    # Gallery HTML
    gallery_images = [i for i in images if i not in hero_images][:6]
    gallery_html = ""
    if len(gallery_images) > 1:
        gallery_cards = []
        for img_url in gallery_images:
            gallery_cards.append(
                '<div style="border-radius:8px;overflow:hidden;aspect-ratio:4/3;">'
                f'<img src="{img_url}" alt="Gallery" loading="lazy"'
                ' style="width:100%;height:100%;object-fit:cover;">'
                '</div>'
            )
        gallery_html = (
            '<section style="padding:5rem 1.5rem;background:#ffffff;">'
            '  <div style="max-width:1100px;margin:0 auto;">'
            f'    <h2 style="font-size:2rem;font-weight:800;color:#1f2937;'
            f'text-align:center;margin:0 0 2rem;">Gallery</h2>'
            f'    <div style="display:grid;grid-template-columns:'
            f'repeat(auto-fit,minmax(250px,1fr));gap:1rem;">'
            f'      {"".join(gallery_cards)}'
            '    </div>'
            '  </div>'
            '</section>'
        )

    # Full page
    html = (
        '<!DOCTYPE html>\n<html lang="en">\n<head>\n'
        '  <meta charset="UTF-8">\n'
        '  <meta name="viewport" content="width=device-width,initial-scale=1.0">\n'
        f'  <title>{name}</title>\n'
        f'  <meta name="description"'
        f' content="{(tagline or about[:160] or name)}">\n'
        f'  <meta property="og:title" content="{name}">\n'
        f'  <meta property="og:description"'
        f' content="{(tagline or about[:160] or name)}">\n'
        '  <link rel="preconnect" href="https://fonts.googleapis.com">\n'
        '  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
        '  <link href="https://fonts.googleapis.com/css2?family=Inter'
        ':wght@400;500;600;700;800&display=swap" rel="stylesheet">\n'
        '  <style>\n'
        '    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }\n'
        '    html { scroll-behavior: smooth; }\n'
        "    body { font-family: 'Inter', -apple-system, BlinkMacSystemFont,"
        " 'Segoe UI', Roboto, sans-serif;\n"
        '            color: #1f2937; background: #ffffff; line-height: 1.6; }\n'
        f'    a {{ color: {primary}; text-decoration: none; transition: color .2s; }}\n'
        '    a:hover { opacity: .8; }\n'
        '    img { max-width: 100%; height: auto; display: block; }\n'
        '  </style>\n'
        '</head>\n<body>\n'
        '  <!-- Navigation -->\n'
        '  <nav style="position:fixed;top:0;left:0;right:0;z-index:1000;'
        'background:rgba(255,255,255,.95);'
        'backdrop-filter:blur(12px);border-bottom:1px solid #e5e7eb;'
        'padding:.75rem 1.5rem;">\n'
        '    <div style="max-width:1100px;margin:0 auto;display:flex;'
        'align-items:center;justify-content:space-between;">\n'
        '      <a href="#" style="text-decoration:none;display:flex;'
        'align-items:center;gap:.5rem;">\n'
        f'        {logo_html}\n'
        '      </a>\n'
        '      <div style="display:flex;gap:1.5rem;align-items:center;">\n'
        '        <a href="#about" style="color:#1f2937;font-weight:500;'
        'font-size:.95rem;text-decoration:none;">About</a>\n'
        '        <a href="#services" style="color:#1f2937;font-weight:500;'
        'font-size:.95rem;text-decoration:none;">Services</a>\n'
        '        <a href="#contact" style="color:#1f2937;font-weight:500;'
        'font-size:.95rem;text-decoration:none;">Contact</a>\n'
        '      </div>\n'
        '    </div>\n'
        '  </nav>\n\n'
        '  <!-- Hero -->\n'
        f'  <header id="hero" style="min-height:100vh;display:flex;'
        f'align-items:center;justify-content:center;text-align:center;'
        f'color:{text_on_primary};padding:6rem 1.5rem 4rem;{hero_style}">\n'
        '    <div style="max-width:800px;">\n'
        f'      <h1 style="font-size:clamp(2.2rem,5vw,3.5rem);font-weight:800;'
        f'margin:0 0 1rem;line-height:1.15;'
        f'text-shadow:0 2px 8px rgba(0,0,0,.2);">{name}</h1>\n'
        + (f'      <p style="font-size:clamp(1.1rem,2.5vw,1.35rem);'
           f'font-weight:400;margin:0 0 2rem;line-height:1.6;'
           f'opacity:.95;">{tagline}</p>\n' if tagline else '')
        + f'      <a href="#contact" style="display:inline-block;'
        f'background:{accent};color:#fff;padding:.85rem 2rem;'
        f'border-radius:8px;font-weight:600;font-size:1.05rem;'
        f'text-decoration:none;box-shadow:0 4px 14px rgba(0,0,0,.2);'
        f'transition:transform .2s,box-shadow .2s;"'
        f' onmouseover="this.style.transform=\'translateY(-2px)\';'
        f'this.style.boxShadow=\'0 8px 20px rgba(0,0,0,.25)\'"'
        f' onmouseout="this.style.transform=\'\';'
        f'this.style.boxShadow=\'0 4px 14px rgba(0,0,0,.2)\'">'
        f'Contact Us</a>\n'
        '    </div>\n'
        '  </header>\n\n'
        '  <!-- About -->\n'
        f'  <div id="about">{about_html}</div>\n\n'
        '  <!-- Services -->\n'
        f'  <div id="services">{services_html}</div>\n\n'
        '  <!-- Gallery -->\n'
        f'  {gallery_html}\n\n'
        '  <!-- Contact -->\n'
        f'  <div id="contact">{contact_html}</div>\n\n'
        '  <!-- Footer -->\n'
        '  <footer style="padding:2rem 1.5rem;background:#ffffff;'
        'border-top:1px solid #e5e7eb;text-align:center;">\n'
        f'    <p style="color:#6b7280;font-size:.875rem;margin:0;">'
        f'&copy; {name}. All rights reserved.</p>\n'
        '  </footer>\n'
        '</body>\n</html>'
    )

    return html


# ---------------------------------------------------------------------------
# Image download helper
# ---------------------------------------------------------------------------

def download_images(images: list, output_dir: str) -> list:
    """Download images to a local folder. Returns list of local paths."""
    img_dir = os.path.join(output_dir, "images")
    os.makedirs(img_dir, exist_ok=True)
    local_paths = []
    for i, url in enumerate(images):
        try:
            resp = requests.get(url, headers={"User-Agent": USER_AGENT},
                                timeout=15, stream=True)
            resp.raise_for_status()
            ext = Path(urllib.parse.urlparse(url).path).suffix or ".jpg"
            if ext.lower() not in (".jpg", ".jpeg", ".png", ".webp",
                                   ".gif", ".svg", ".avif"):
                ext = ".jpg"
            fname = f"image_{i:03d}{ext}"
            fpath = os.path.join(img_dir, fname)
            with open(fpath, "wb") as f:
                for chunk in resp.iter_content(8192):
                    f.write(chunk)
            local_paths.append(f"images/{fname}")
        except Exception:
            local_paths.append(url)
    return local_paths


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def clone_website(url: str, output_base: str = None,
                  download_imgs: bool = True) -> str:
    """
    Full pipeline: fetch -> extract -> generate -> save.
    Returns the output directory path.
    """
    print(f"\n{'='*60}")
    print(f"  PRESTIGE GROUP — Website Cloner")
    print(f"{'='*60}\n")
    print(f"  Target: {url}\n")

    # 1. Fetch
    print("  [1/5] Fetching page...")
    try:
        html, final_url = fetch_html(url)
    except ConnectionError as e:
        print(f"  ✗ ERROR: {e}")
        print("  The site may be down, blocking automated requests, "
              "or the URL may be incorrect.")
        raise

    print(f"  ✓ Page fetched ({len(html):,} bytes)")

    # 2. Parse
    print("  [2/5] Extracting content...")
    soup = BeautifulSoup(html, "html.parser")

    business_name = extract_business_name(soup)
    slug = slugify(business_name)
    tagline = extract_tagline(soup)
    about = extract_about(soup)
    services = extract_services(soup)
    contact = extract_contact(soup, html, final_url)
    images = extract_images(soup, final_url)
    logo_url = extract_logo(soup, final_url)
    colors = extract_colors(soup, html)

    print(f"  ✓ Business name : {business_name}")
    tagline_display = tagline[:80] + ("…" if len(tagline) > 80 else "")
    print(f"  ✓ Tagline       : {tagline_display}")
    print(f"  ✓ About text    : {len(about)} chars")
    print(f"  ✓ Services      : {len(services)} found")
    print(f"  ✓ Images        : {len(images)} found")
    print(f"  ✓ Logo          : {'Found' if logo_url else 'Not detected'}")
    print(f"  ✓ Phone         : {contact['phone'] or 'Not found'}")
    print(f"  ✓ Email         : {contact['email'] or 'Not found'}")
    print(f"  ✓ Social links  : {len(contact.get('social', {}))}")
    print(f"  ✓ Color scheme  : primary={colors['primary']}")

    # 3. Setup output directory
    if not output_base:
        output_base = os.path.join(os.getcwd(), "output")
    output_dir = os.path.join(output_base, slug)
    os.makedirs(output_dir, exist_ok=True)

    # 4. Screenshot
    print("  [3/5] Saving screenshot...")
    screenshot_path = os.path.join(output_dir, "original_screenshot.png")
    screenshot_saved = save_screenshot(url, screenshot_path)
    if not screenshot_saved:
        generate_placeholder_thumbnail(screenshot_path, business_name)
        print("  ✓ Placeholder thumbnail saved")
    else:
        print("  ✓ Screenshot saved")

    # 5. Download images (optional)
    local_images = images
    if download_imgs and images:
        print("  [4/5] Downloading images...")
        local_images = download_images(images, output_dir)
        print(f"  ✓ {len(local_images)} images processed")
    else:
        print("  [4/5] Skipping image download (using remote URLs)")

    # 6. Generate cloned HTML
    print("  [5/5] Generating cloned website...")
    data = {
        "business_name": business_name,
        "tagline": tagline,
        "about": about,
        "services": services,
        "contact": contact,
        "logo_url": logo_url,
        "images": local_images,
        "colors": colors,
    }

    cloned_html = generate_cloned_html(data)

    # Save metadata JSON
    meta = dict(data)
    meta["source_url"] = url
    meta_path = os.path.join(output_dir, "extraction_data.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

    # Save index.html
    index_path = os.path.join(output_dir, "index.html")
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(cloned_html)

    print(f"\n  {'='*60}")
    print(f"  ✓ CLONE COMPLETE")
    print(f"  {'='*60}")
    print(f"  Output directory : {os.path.abspath(output_dir)}")
    print(f"  index.html       : {os.path.abspath(index_path)}")
    print(f"  Metadata         : {os.path.abspath(meta_path)}")
    print(f"  Screenshot       : {os.path.abspath(screenshot_path)}")
    print(f"\n  Open the cloned site with:")
    print(f"    open {os.path.abspath(index_path)}")
    print(f"    # or")
    print(f"    python -m http.server 8080"
           f" --dir {os.path.abspath(output_dir)}")
    print()

    return output_dir


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Prestige Group — Website Cloner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""
            Examples:
              python website_cloner.py https://example.com
              python website_cloner.py https://example.com --output ./clones
              python website_cloner.py https://example.com --no-download-images
        """),
    )
    parser.add_argument("url", help="URL of the business website to clone")
    parser.add_argument("--output", "-o", default=None,
                        help="Base output directory (default: ./output)")
    parser.add_argument("--no-download-images", action="store_true",
                        help="Don't download images locally (use remote URLs)")
    args = parser.parse_args()

    # Basic URL validation
    parsed = urllib.parse.urlparse(args.url)
    if not parsed.scheme or not parsed.netloc:
        print(f"Error: Invalid URL '{args.url}'. "
              "Please include the scheme (e.g., https://).")
        sys.exit(1)

    clone_website(
        url=args.url,
        output_base=args.output,
        download_imgs=not args.no_download_images,
    )


if __name__ == "__main__":
    main()