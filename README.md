# Prestige Group — Website Cloning & Outreach Pipeline

Automated pipeline for finding businesses with poor/no websites, cloning and rebuilding them, and pitching the improved version.

**Company:** Prestige Group  
**Owner:** Senator  

## 🏗️ Architecture

```
Google Maps Scraper  →  Website Cloner  →  Outreach Generator
      (Tony)              (Tony)              (Tony)
         ↓                    ↓                    ↓
    LEAD_REVIEW          QUALITY_REVIEW      OUTREACH_REVIEW
      (Jarvis)             (Jarvis)            (Jarvis)
```

**Multi-Agent Flow:**
- **Tony (Hermes)** — Builder/Executor: Runs scrapers, builds clones, generates emails, sends outreach
- **Jarvis (glm-5.1:cloud)** — Head of Agents: Reviews leads, quality-checks clones, refines messaging, makes strategic decisions

Handoffs are tracked in `agent_handoffs.json`. Activity is logged in `agent_log.json`.

## 📁 Files

| File | Purpose |
|------|---------|
| `maps_scraper.py` | Google Maps Places API scraper — finds businesses with poor/no websites |
| `website_cloner.py` | Clones a website URL and generates a clean modern replacement |
| `outreach_generator.py` | Generates professional pitch emails for businesses |
| `pipeline.py` | Orchestrator — runs the full pipeline end to end |
| `agent_flow.py` | Multi-agent collaboration framework (Tony ↔ Jarvis handoffs) |
| `requirements.txt` | Python dependencies |

## 🚀 Quick Start

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Get a Google Maps API Key
You need a Google Cloud project with the **Places API** enabled.
Get a key at: https://console.cloud.google.com/google/maps-apis

### 3. Run the full pipeline
```bash
python pipeline.py --query "plumbers" --location "Austin, TX" --max 40
```

### 4. Or run individual steps

**Scrape for leads:**
```bash
# Edit CONFIG in maps_scraper.py first (add your API key)
python maps_scraper.py
```

**Clone a website:**
```bash
python website_cloner.py https://example.com
```

**Generate pitch email:**
```bash
python outreach_generator.py
```

### 5. Multi-agent workflow
```bash
# Check pipeline status
python agent_flow.py status

# Tony's actions
python agent_flow.py tony:leads
python agent_flow.py tony:clone
python agent_flow.py tony:outreach
python agent_flow.py tony:send

# Jarvis's reviews
python agent_flow.py jarvis:leads
python agent_flow.py jarvis:clones
python agent_flow.py jarvis:outreach
```

## 💰 Pricing Tiers (in pitch emails)

| Tier | One-time | Monthly |
|------|----------|---------|
| Starter | $499 | $49/mo |
| Professional | $999 | $89/mo |
| Premium | $1,999 | $149/mo |

## 📊 Output Structure

```
prestige-group/
├── leads/              # CSV files from Google Maps scraper
├── cloned_sites/       # Cloned website HTML + assets
├── outreach/           # Generated pitch emails
├── output/             # Individual clone output folders
├── status/             # Agent handoff status flags
├── agent_handoffs.json  # Handoff tracking
└── agent_log.json       # Activity log
```

## 🤝 Agent Roles

### Tony (Hermes) — 2nd in Command
- Runs the technical pipeline (scraping, cloning, generating)
- Executes on Jarvis's strategic decisions
- Handles the heavy lifting

### Jarvis — Head of Agents
- Reviews and prioritizes leads
- Quality-checks cloned websites
- Refines outreach messaging
- Makes go/no-go decisions on sending

## 🔧 Configuration

Edit the `CONFIG` dict at the top of `maps_scraper.py`:
- `api_key`: Your Google Maps Places API key
- `search_query`: Business category (e.g., "restaurants", "plumbers")
- `location`: City/area to search
- `radius`: Search radius in meters
- `max_results`: Maximum number of businesses to return

## 📋 Requirements

- Python 3.10+
- Google Maps Places API key
- Internet connection

## ⚠️ Notes

- Always respect robots.txt and rate limits when scraping
- The website cloner uses multiple fallback methods (wget → curl → Python requests)
- Pitch emails are generated but **not auto-sent** — review them in the `outreach/` folder first