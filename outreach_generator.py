#!/usr/bin/env python3
"""
Outreach / Pitch Email Generator — Prestige Group

Takes business info (name, category, location, website status) and generates
a professional cold-pitch email offering to rebuild their website.

Usage:
    from outreach_generator import generate_email, save_email
    email_text = generate_email(business)
    path = save_email(business, email_text, output_dir="outreach")
"""

import logging
import re
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
# CONFIGURATION — Pricing & branding
# ──────────────────────────────────────────────────────────────

BRAND = {
    "company": "Prestige Group",
    "tagline": "We Build Websites That Build Businesses",
    "email": "hello@prestige-group.com",
    "phone": "(512) 555-0199",
    "website": "https://prestige-group.com",
}

PRICING = {
    "starter": {
        "label": "Starter",
        "one_time": 499,
        "monthly": 49,
        "description": "5-page responsive website with contact form, mobile-first design, and basic SEO setup.",
    },
    "professional": {
        "label": "Professional",
        "one_time": 999,
        "monthly": 89,
        "description": "10-page website with online booking, gallery, testimonials, advanced SEO, and Google Business integration.",
    },
    "premium": {
        "label": "Premium",
        "one_time": 1999,
        "monthly": 149,
        "description": "Full custom build with e-commerce, CRM integration, content management system, and priority support.",
    },
}

# ──────────────────────────────────────────────────────────────
# EMAIL TEMPLATE BUILDER
# ──────────────────────────────────────────────────────────────

def _slugify(text: str) -> str:
    """Convert text to a filesystem-safe slug."""
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"[\s-]+", "-", text)
    return text.strip("-")


def _website_state_phrase(business: dict) -> str:
    """Return a natural-language description of the business's current website state."""
    has = business.get("has_website", False)
    poor = business.get("poor_website", False)
    reason = business.get("website_reason", "")

    if not has:
        return (
            "I noticed you don't currently have a website. "
            "In today's market, that means countless potential customers are searching "
            "for your services online and finding your competitors instead."
        )

    if poor and "social" in (business.get("website_status") or ""):
        return (
            f"I came across your business online and noticed your web presence is limited "
            f"to a social media page. While social profiles are great for engagement, "
            f"they don't give you the credibility, control, or discoverability that a "
            f"dedicated website provides."
        )

    if poor:
        return (
            f"I visited your current website and noticed it may not be giving your "
            f"business the strong online presence it deserves. "
            f"A professional, high-performing website is often the first impression "
            f"potential customers have of your business — and first impressions count."
        )

    return ""


def _build_subject(business: dict) -> str:
    """Generate a compelling subject line."""
    name = business.get("name", "your business")
    return f"A better website for {name} — free preview inside"


def _build_pricing_section() -> str:
    """Build the pricing-tier block for the email."""
    lines = []
    for tier_key in ("starter", "professional", "premium"):
        tier = PRICING[tier_key]
        lines.append(
            f"  **{tier['label']}** — ${tier['one_time']:,} one-time setup\n"
            f"    {tier['description']}\n"
            f"    Optional ongoing plan: ${tier['monthly']}/mo (hosting, updates, analytics, support)"
        )
    return "\n\n".join(lines)


def _build_email(business: dict) -> str:
    """
    Build the full pitch email body.

    Expected business dict keys:
        name, category, address (or location), has_website, poor_website,
        website_status, website_reason, phone, website
    """
    name = business.get("name", "Business Owner")
    category = business.get("category", "your industry")
    location = business.get("address", business.get("location", "your area"))
    owner_first = name.split()[0] if name else "there"

    state_phrase = _website_state_phrase(business)
    subject = _build_subject(business)
    pricing_block = _build_pricing_section()

    email = f"""Subject: {subject}

Hi {owner_first},

{state_phrase}

My name is the team at {BRAND['company']}, and we specialize in building
high-converting websites for {category} businesses in {location} and beyond.

**Here's the good news — we've already prepared a preview.**

We took the liberty of putting together a demo of what a modern, professional
website for {name} could look like. It's fast, mobile-friendly, and designed
to turn visitors into paying customers. You can review the preview at no cost
and with zero obligation.

**Investment Options:**

{pricing_block}

All plans include:
  ✓ Custom design tailored to your brand
  ✓ Mobile-responsive layout (looks great on every device)
  ✓ Fast load times & modern design standards
  ✓ No long-term contracts — cancel anytime on the monthly plan

The one-time setup gets your site live quickly. The optional monthly plan
keeps it running smoothly with hosting, security updates, content tweaks,
and performance analytics — so you never have to think about it.

**Next steps:** Simply reply to this email or call us at {BRAND['phone']}
and we'll share the live preview link. If you like what you see, we can
have your new site fully launched within 5–7 business days.

No pressure, no hard sell — just a better website that works as hard as
you do.

Looking forward to hearing from you,

— {BRAND['company']}
{BRAND['tagline']}
{BRAND['email']}  |  {BRAND['phone']}
{BRAND['website']}
"""
    return email


# ──────────────────────────────────────────────────────────────
# PUBLIC API
# ──────────────────────────────────────────────────────────────

def generate_email(business: dict) -> str:
    """
    Generate a cold-pitch email for the given business.

    Args:
        business: Dict with keys like name, category, address/location,
                  has_website, poor_website, website_status, website_reason.

    Returns:
        The full email text including subject line.
    """
    if not business.get("name"):
        log.warning("Business dict missing 'name' — email will use a generic greeting.")

    email_text = _build_email(business)
    log.info("Generated pitch email for '%s'", business.get("name", "unknown"))
    return email_text


def save_email(business: dict, email_text: str, output_dir: str = "outreach") -> Path:
    """
    Save the generated email to a file inside output_dir.

    File naming: outreach/<slugified_name>_pitch_<timestamp>.txt
    Returns the Path of the saved file.
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    slug = _slugify(business.get("name", "unknown_business"))
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{slug}_pitch_{timestamp}.txt"
    path = out / filename

    path.write_text(email_text, encoding="utf-8")
    log.info("Saved pitch email → %s", path)
    return path


# ──────────────────────────────────────────────────────────────
# CLI ENTRY POINT — useful for quick testing
# ──────────────────────────────────────────────────────────────

def main():
    """Quick demo: generate a sample email for a fake business."""
    sample_business = {
        "name": "Austin Premier Plumbing",
        "category": "plumbing",
        "address": "Austin, TX",
        "has_website": True,
        "poor_website": True,
        "website_status": "social",
        "website_reason": "social/directory only (facebook.com)",
        "phone": "(512) 555-1234",
        "website": "https://facebook.com/austinpremierplumbing",
    }
    email = generate_email(sample_business)
    path = save_email(sample_business, email)
    print(f"\nSample email saved to: {path}\n")
    print(email)


if __name__ == "__main__":
    main()