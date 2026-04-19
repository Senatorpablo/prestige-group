#!/usr/bin/env python3
"""
Pipeline Orchestrator — Prestige Group

End-to-end pipeline that automates the lead → clone → pitch flow:

  Step 1) Scrape Google Maps for businesses with poor/no websites
  Step 2) For each lead with a poor website, clone the site
  Step 3) Generate a personalized pitch email
  Step 4) Save everything in organized folders

Directory structure produced:
    <base_dir>/
    ├── leads/           ← CSV output from maps scraper
    ├── cloned_sites/    ← Mirrored sites per business
    └── outreach/        ← Generated pitch emails

Usage:
    python pipeline.py                                           # defaults
    python pipeline.py --query "plumbers" --location "Austin, TX"
    python pipeline.py --query "dentists" --location "Denver, CO" --max 40
    python pipeline.py --leads-file leads/maps_plumbers_20260419.csv  # skip scraping
"""

import argparse
import csv
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

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
# DEFAULT CONFIGURATION
# ──────────────────────────────────────────────────────────────

DEFAULTS = {
    "query": "plumbers",
    "location": "Austin, TX",
    "radius": 20000,
    "max_results": 60,
    "api_key": "",
    "base_dir": ".",
    "clone_timeout": 60,
}


def _setup_directories(base_dir: str) -> dict[str, Path]:
    """Create and return the output directory structure."""
    base = Path(base_dir)
    dirs = {
        "base": base,
        "leads": base / "leads",
        "cloned_sites": base / "cloned_sites",
        "outreach": base / "outreach",
    }
    for d in dirs.values():
        d.mkdir(parents=True, exist_ok=True)
    log.info("Output directories ready under %s", base.resolve())
    return dirs


# ──────────────────────────────────────────────────────────────
# STEP 1 — SCRAPE GOOGLE MAPS
# ──────────────────────────────────────────────────────────────

def step_scrape(config: dict, leads_dir: Path) -> Path | None:
    """
    Run the Google Maps scraper and return the path to the output CSV.

    Returns None if scraping fails.
    """
    log.info("=" * 60)
    log.info("STEP 1: Scraping Google Maps for leads")
    log.info("=" * 60)

    try:
        import maps_scraper
    except ImportError:
        log.error("Cannot import maps_scraper.py — make sure it's in the same directory.")
        return None

    # Patch the scraper config with our values
    maps_scraper.CONFIG["search_query"] = config["query"]
    maps_scraper.CONFIG["location"] = config["location"]
    maps_scraper.CONFIG["radius"] = config["radius"]
    maps_scraper.CONFIG["max_results"] = config["max_results"]
    maps_scraper.CONFIG["api_key"] = config.get("api_key", "")
    maps_scraper.CONFIG["output_dir"] = str(leads_dir)

    try:
        csv_path = maps_scraper.run()
    except Exception as exc:
        log.error("Maps scraper failed: %s", exc)
        return None

    if csv_path is None:
        log.error("Maps scraper returned no output.")
        return None

    log.info("Leads CSV saved → %s", csv_path)
    return csv_path


# ──────────────────────────────────────────────────────────────
# STEP 2 — CLONE WEBSITES
# ──────────────────────────────────────────────────────────────

def step_clone(businesses: list[dict], cloned_dir: Path, timeout: int) -> list[dict]:
    """
    For each business with a poor website, clone (or snapshot) the site.

    Adds a 'clone_path' key to each business dict.
    """
    log.info("=" * 60)
    log.info("STEP 2: Cloning websites for %d businesses", len(businesses))
    log.info("=" * 60)

    try:
        from website_cloner import clone_website
    except ImportError:
        log.error("Cannot import website_cloner.py — make sure it's in the same directory.")
        return businesses

    for biz in businesses:
        url = biz.get("website", "")
        name = biz.get("name", "unknown")
        log.info("Cloning '%s' (%s)", name, url or "no URL")

        result = clone_website(
            url=url,
            name=name,
            output_dir=str(cloned_dir),
            timeout=timeout,
        )
        biz["clone_path"] = result["path"]
        biz["clone_method"] = result["method"]
        biz["clone_success"] = result["success"]

        if not result["success"]:
            log.warning("Clone failed for '%s': %s", name, result.get("error", "unknown"))

    log.info("Cloning step complete for %d businesses", len(businesses))
    return businesses


# ──────────────────────────────────────────────────────────────
# STEP 3 — GENERATE OUTREACH EMAILS
# ──────────────────────────────────────────────────────────────

def step_outreach(businesses: list[dict], outreach_dir: Path) -> list[dict]:
    """
    For each business with a poor website, generate a pitch email.

    Adds an 'email_path' key to each business dict.
    """
    log.info("=" * 60)
    log.info("STEP 3: Generating outreach emails for %d businesses", len(businesses))
    log.info("=" * 60)

    try:
        from outreach_generator import generate_email, save_email
    except ImportError:
        log.error("Cannot import outreach_generator.py — make sure it's in the same directory.")
        return businesses

    count = 0
    for biz in businesses:
        name = biz.get("name", "unknown")
        email_text = generate_email(biz)
        email_path = save_email(biz, email_text, output_dir=str(outreach_dir))
        biz["email_path"] = str(email_path)
        count += 1
        log.info("Email generated for '%s' → %s", name, email_path)

    log.info("Generated %d pitch emails", count)
    return businesses


# ──────────────────────────────────────────────────────────────
# CSV LOADING (when using --leads-file)
# ──────────────────────────────────────────────────────────────

def load_leads_csv(csv_path: str) -> list[dict]:
    """Load businesses from an existing leads CSV."""
    path = Path(csv_path)
    if not path.exists():
        log.error("Leads file not found: %s", csv_path)
        return []

    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    log.info("Loaded %d leads from %s", len(rows), csv_path)
    return rows


# ──────────────────────────────────────────────────────────────
# PIPELINE RUNNER
# ──────────────────────────────────────────────────────────────

def run_pipeline(config: dict) -> dict:
    """
    Execute the full pipeline: scrape → clone → outreach.

    Returns a summary dict with counts and file paths.
    """
    start = datetime.now()
    summary = {
        "started_at": start.isoformat(),
        "config": config,
        "steps_completed": [],
        "errors": [],
        "leads_total": 0,
        "poor_website_count": 0,
        "cloned_count": 0,
        "emails_generated": 0,
    }

    # ── Setup directories ────────────────────────────────────
    dirs = _setup_directories(config["base_dir"])

    # ── Step 1: Scrape or load leads ────────────────────────
    leads_csv = config.get("leads_file")

    if leads_csv:
        # Skip scraping — use existing CSV
        all_businesses = load_leads_csv(leads_csv)
    else:
        csv_path = step_scrape(config, dirs["leads"])
        if csv_path is None:
            summary["errors"].append("Maps scraper failed — cannot continue pipeline")
            return summary
        all_businesses = load_leads_csv(str(csv_path))

    summary["leads_total"] = len(all_businesses)
    summary["steps_completed"].append("scrape")

    if not all_businesses:
        log.warning("No leads found. Pipeline complete (nothing to do).")
        return summary

    # ── Filter: only businesses with poor / no website ───────
    poor_leads = [b for b in all_businesses if _is_poor_website(b)]
    summary["poor_website_count"] = len(poor_leads)

    log.info("Total leads: %d  |  Poor/no website: %d", len(all_businesses), len(poor_leads))

    if not poor_leads:
        log.info("No businesses with poor websites found. Pipeline complete.")
        return summary

    # ── Step 2: Clone websites ───────────────────────────────
    poor_leads = step_clone(poor_leads, dirs["cloned_sites"], config.get("clone_timeout", 60))
    cloned_ok = sum(1 for b in poor_leads if b.get("clone_success"))
    summary["cloned_count"] = cloned_ok
    summary["steps_completed"].append("clone")

    # ── Step 3: Generate outreach emails ─────────────────────
    poor_leads = step_outreach(poor_leads, dirs["outreach"])
    summary["emails_generated"] = sum(1 for b in poor_leads if b.get("email_path"))
    summary["steps_completed"].append("outreach")

    # ── Save pipeline manifest ───────────────────────────────
    _save_manifest(poor_leads, dirs, summary, config)

    # ── Done ─────────────────────────────────────────────────
    elapsed = (datetime.now() - start).total_seconds()
    summary["elapsed_seconds"] = round(elapsed, 1)
    _print_summary(summary, dirs)

    return summary


def _is_poor_website(biz: dict) -> bool:
    """Determine if a business qualifies as having a poor website."""
    has = biz.get("has_website", "")
    poor = biz.get("poor_website", "")

    # Handle string representations from CSV
    if isinstance(has, str):
        has = has.lower().strip() == "true"
    if isinstance(poor, str):
        poor = poor.lower().strip() == "true"

    # Qualify if no website at all, or flagged as poor
    return (not has) or poor


def _save_manifest(businesses: list[dict], dirs: dict, summary: dict, config: dict):
    """Save a pipeline manifest JSON with all results."""
    manifest = {
        "pipeline_run": datetime.now().isoformat(),
        "config": config,
        "summary": {
            "leads_total": summary["leads_total"],
            "poor_website_count": summary["poor_website_count"],
            "cloned_count": summary["cloned_count"],
            "emails_generated": summary["emails_generated"],
        },
        "businesses": [],
    }

    for biz in businesses:
        entry = {
            "name": biz.get("name", ""),
            "address": biz.get("address", biz.get("formatted_address", "")),
            "phone": biz.get("phone", biz.get("formatted_phone_number", "")),
            "website": biz.get("website", ""),
            "has_website": biz.get("has_website", False),
            "poor_website": biz.get("poor_website", True),
            "website_reason": biz.get("website_reason", ""),
            "clone_path": biz.get("clone_path", ""),
            "clone_method": biz.get("clone_method", ""),
            "email_path": biz.get("email_path", ""),
        }
        manifest["businesses"].append(entry)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    slug = config.get("query", "leads").replace(" ", "_").lower()
    manifest_path = dirs["base"] / f"pipeline_{slug}_{timestamp}.json"

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, default=str)

    log.info("Pipeline manifest saved → %s", manifest_path)


def _print_summary(summary: dict, dirs: dict):
    """Print a nice summary to the console."""
    log.info("=" * 60)
    log.info("PIPELINE COMPLETE")
    log.info("=" * 60)
    log.info("Steps completed:  %s", " → ".join(summary["steps_completed"]))
    log.info("Total leads:      %d", summary["leads_total"])
    log.info("Poor/no website:  %d", summary["poor_website_count"])
    log.info("Sites cloned:     %d", summary["cloned_count"])
    log.info("Emails generated: %d", summary["emails_generated"])
    log.info("Elapsed:          %.1fs", summary.get("elapsed_seconds", 0))
    log.info("")
    log.info("Output directories:")
    for label, path in dirs.items():
        log.info("  %-15s %s", label, path.resolve())
    if summary.get("errors"):
        log.info("")
        log.info("Errors:")
        for err in summary["errors"]:
            log.info("  ✗ %s", err)
    log.info("=" * 60)


# ──────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Prestige Group — Full Pipeline: Scrape → Clone → Pitch",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python pipeline.py --query "plumbers" --location "Austin, TX"
  python pipeline.py --query "dentists" --location "Denver, CO" --max 40
  python pipeline.py --leads-file leads/maps_plumbers_20260419.csv  # skip scraping
        """,
    )
    parser.add_argument("--query", default=DEFAULTS["query"],
                        help="Business category to search (default: plumbers)")
    parser.add_argument("--location", default=DEFAULTS["location"],
                        help='City, State or "lat,lng" (default: "Austin, TX")')
    parser.add_argument("--radius", type=int, default=DEFAULTS["radius"],
                        help="Search radius in metres (default: 20000)")
    parser.add_argument("--max", type=int, default=DEFAULTS["max_results"],
                        help="Max businesses to scrape (default: 60)")
    parser.add_argument("--api-key", default=DEFAULTS["api_key"],
                        help="Google Maps Places API key")
    parser.add_argument("--base-dir", default=DEFAULTS["base_dir"],
                        help="Base directory for all output (default: current dir)")
    parser.add_argument("--leads-file", default=None,
                        help="Path to existing leads CSV (skip scraping step)")
    parser.add_argument("--clone-timeout", type=int, default=DEFAULTS["clone_timeout"],
                        help="Seconds before a clone operation times out (default: 60)")

    args = parser.parse_args()

    config = {
        "query": args.query,
        "location": args.location,
        "radius": args.radius,
        "max_results": args.max,
        "api_key": args.api_key,
        "base_dir": args.base_dir,
        "clone_timeout": args.clone_timeout,
    }
    if args.leads_file:
        config["leads_file"] = args.leads_file

    run_pipeline(config)


if __name__ == "__main__":
    main()