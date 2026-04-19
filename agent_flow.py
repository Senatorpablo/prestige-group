"""
Prestige Group - Multi-Agent Collaboration Framework
=====================================================
Defines the workflow between Tony (Hermes) and Jarvis for the
Prestige Group website cloning pipeline.

Agent Roles:
  - JARVIS (glm-5.1:cloud): Head of agents, strategic decisions,
    quality reviews, client communication strategy
  - TONY (Hermes/this agent): Builder, executor, scraper, cloner,
    pipeline runner, handles the technical heavy lifting

Communication Protocol:
  - Agents share a shared workspace: /Users/senator/prestige-group/
  - Task handoffs are tracked in agent_handoffs.json
  - Each agent logs activity to agent_log.json
  - Status files indicate what's ready for the other agent to pick up

Workflow Stages:
  1. LEAD_GEN    → Tony: Run maps_scraper, produce leads CSV
  2. LEAD_REVIEW → Jarvis: Review leads, prioritize, select targets
  3. CLONE_BUILD → Tony: Clone selected websites, generate new sites
  4. QUALITY_REVIEW → Jarvis: Review cloned sites, approve or request changes
  5. OUTREACH    → Tony: Generate pitch emails for approved clones
  6. OUTREACH_REVIEW → Jarvis: Review pitch emails, refine messaging
  7. SEND        → Tony: Send approved emails
"""

import json
import os
import datetime
from pathlib import Path

WORKSPACE = Path("/Users/senator/prestige-group")
HANDOFFS_FILE = WORKSPACE / "agent_handoffs.json"
LOG_FILE = WORKSPACE / "agent_log.json"
STATUS_DIR = WORKSPACE / "status"

# Agent identifiers
TONY = "tony"
JARVIS = "jarvis"

# Workflow stages in order
STAGES = [
    "LEAD_GEN",         # Tony
    "LEAD_REVIEW",      # Jarvis
    "CLONE_BUILD",      # Tony
    "QUALITY_REVIEW",   # Jarvis
    "OUTREACH",         # Tony
    "OUTREACH_REVIEW",  # Jarvis
    "SEND",             # Tony
]

# Stage ownership
STAGE_OWNER = {
    "LEAD_GEN": TONY,
    "LEAD_REVIEW": JARVIS,
    "CLONE_BUILD": TONY,
    "QUALITY_REVIEW": JARVIS,
    "OUTREACH": TONY,
    "OUTREACH_REVIEW": JARVIS,
    "SEND": TONY,
}

# Status signals (files that indicate state)
STATUS_FILES = {
    "leads_ready": STATUS_DIR / "leads_ready.flag",
    "leads_reviewed": STATUS_DIR / "leads_reviewed.flag",
    "clones_ready": STATUS_DIR / "clones_ready.flag",
    "clones_approved": STATUS_DIR / "clones_approved.flag",
    "emails_ready": STATUS_DIR / "emails_ready.flag",
    "emails_approved": STATUS_DIR / "emails_approved.flag",
    "emails_sent": STATUS_DIR / "emails_sent.flag",
}


def _ensure_dirs():
    """Create status directory if it doesn't exist."""
    STATUS_DIR.mkdir(parents=True, exist_ok=True)


def log_activity(agent: str, action: str, details: str = ""):
    """Log an agent activity to the shared log."""
    _ensure_dirs()
    log = []
    if LOG_FILE.exists():
        log = json.loads(LOG_FILE.read_text())

    log.append({
        "timestamp": datetime.datetime.now().isoformat(),
        "agent": agent,
        "action": action,
        "details": details,
    })

    LOG_FILE.write_text(json.dumps(log, indent=2))


def create_handoff(from_agent: str, to_agent: str, stage: str, notes: str = ""):
    """Create a handoff entry — 'from_agent' completed a stage, 'to_agent' should pick up."""
    _ensure_dirs()
    handoffs = []
    if HANDOFFS_FILE.exists():
        handoffs = json.loads(HANDOFFS_FILE.read_text())

    handoffs.append({
        "timestamp": datetime.datetime.now().isoformat(),
        "from": from_agent,
        "to": to_agent,
        "stage": stage,
        "notes": notes,
        "status": "pending",
    })

    HANDOFFS_FILE.write_text(json.dumps(handoffs, indent=2))
    log_activity(from_agent, f"HANDOFF → {to_agent}", f"Stage: {stage}. Notes: {notes}")


def claim_handoff(agent: str) -> dict | None:
    """Claim the next pending handoff for this agent."""
    _ensure_dirs()
    if not HANDOFFS_FILE.exists():
        return None

    handoffs = json.loads(HANDOFFS_FILE.read_text())
    for h in handoffs:
        if h["to"] == agent and h["status"] == "pending":
            h["status"] = "claimed"
            h["claimed_at"] = datetime.datetime.now().isoformat()
            HANDOFFS_FILE.write_text(json.dumps(handoffs, indent=2))
            log_activity(agent, f"CLAIMED handoff from {h['from']}", f"Stage: {h['stage']}")
            return h
    return None


def complete_handoff(agent: str, stage: str, result: str = ""):
    """Mark a handoff as completed after the agent finishes their work."""
    _ensure_dirs()
    if not HANDOFFS_FILE.exists():
        return

    handoffs = json.loads(HANDOFFS_FILE.read_text())
    for h in reversed(handoffs):
        if h["to"] == agent and h["stage"] == stage and h["status"] == "claimed":
            h["status"] = "completed"
            h["completed_at"] = datetime.datetime.now().isoformat()
            h["result"] = result
            HANDOFFS_FILE.write_text(json.dumps(handoffs, indent=2))
            log_activity(agent, f"COMPLETED stage {stage}", result)
            break


def set_status(flag_name: str):
    """Set a status flag file to signal other agents."""
    _ensure_dirs()
    STATUS_FILES[flag_name].write_text(datetime.datetime.now().isoformat())


def check_status(flag_name: str) -> bool:
    """Check if a status flag is set."""
    return STATUS_FILES.get(flag_name, Path("/nonexistent")).exists()


def clear_status(flag_name: str):
    """Clear a status flag."""
    f = STATUS_FILES.get(flag_name)
    if f and f.exists():
        f.unlink()


def get_pipeline_status() -> dict:
    """Get the current state of the full pipeline."""
    return {
        "leads_ready": check_status("leads_ready"),
        "leads_reviewed": check_status("leads_reviewed"),
        "clones_ready": check_status("clones_ready"),
        "clones_approved": check_status("clones_approved"),
        "emails_ready": check_status("emails_ready"),
        "emails_approved": check_status("emails_approved"),
        "emails_sent": check_status("emails_sent"),
    }


def current_stage() -> str | None:
    """Determine which stage the pipeline is currently at."""
    status = get_pipeline_status()
    if not status["leads_ready"]:
        return "LEAD_GEN"
    elif not status["leads_reviewed"]:
        return "LEAD_REVIEW"
    elif not status["clones_ready"]:
        return "CLONE_BUILD"
    elif not status["clones_approved"]:
        return "QUALITY_REVIEW"
    elif not status["emails_ready"]:
        return "OUTREACH"
    elif not status["emails_approved"]:
        return "OUTREACH_REVIEW"
    elif not status["emails_sent"]:
        return "SEND"
    else:
        return "COMPLETE"


# ── Tony's actions (this agent) ──────────────────────────────────

def tony_run_lead_gen(query: str = "restaurants", location: str = "London, UK", max_results: int = 50):
    """Tony: Run the Google Maps scraper to generate leads."""
    log_activity(TONY, "RUN_LEAD_GEN", f"Query: {query}, Location: {location}, Max: {max_results}")
    # In production, this calls maps_scraper.main()
    # For now, set the flag so Jarvis knows leads are ready
    set_status("leads_ready")
    create_handoff(TONY, JARVIS, "LEAD_REVIEW",
                    f"Leads generated for '{query}' in '{location}'. Review and prioritize.")


def tony_run_clone_build():
    """Tony: Clone the websites for reviewed leads."""
    log_activity(TONY, "RUN_CLONE_BUILD", "Building cloned websites for reviewed leads")
    set_status("clones_ready")
    create_handoff(TONY, JARVIS, "QUALITY_REVIEW",
                    "Cloned websites ready for quality review.")


def tony_run_outreach():
    """Tony: Generate pitch emails for approved clones."""
    log_activity(TONY, "RUN_OUTREACH", "Generating pitch emails")
    set_status("emails_ready")
    create_handoff(TONY, JARVIS, "OUTREACH_REVIEW",
                    "Pitch emails generated. Review and refine messaging.")


def tony_send_emails():
    """Tony: Send the approved pitch emails."""
    log_activity(TONY, "RUN_SEND", "Sending approved pitch emails")
    set_status("emails_sent")


# ── Jarvis's actions (simulated for handoff protocol) ────────────

def jarvis_review_leads():
    """Jarvis: Review and prioritize leads from Tony's scraper."""
    log_activity(JARVIS, "REVIEW_LEADS", "Reviewing and prioritizing leads")
    set_status("leads_reviewed")
    create_handoff(JARVIS, TONY, "CLONE_BUILD",
                    "Leads reviewed. Priority targets selected. Clone these sites.")


def jarvis_review_clones():
    """Jarvis: Review cloned websites for quality."""
    log_activity(JARVIS, "REVIEW_CLONES", "Quality checking cloned websites")
    set_status("clones_approved")
    create_handoff(JARVIS, TONY, "OUTREACH",
                    "Clones approved. Generate pitch emails.")


def jarvis_review_outreach():
    """Jarvis: Review and refine pitch emails."""
    log_activity(JARVIS, "REVIEW_OUTREACH", "Reviewing pitch email messaging")
    set_status("emails_approved")
    create_handoff(JARVIS, TONY, "SEND",
                    "Emails approved. Send them out.")


# ── CLI interface ────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python agent_flow.py <command>")
        print()
        print("Commands:")
        print("  status           - Show current pipeline status")
        print("  stage            - Show current pipeline stage")
        print("  log              - Show agent activity log")
        print("  handoffs         - Show pending handoffs")
        print("  tony:leads       - Tony: Run lead generation")
        print("  tony:clone       - Tony: Clone reviewed leads")
        print("  tony:outreach    - Tony: Generate pitch emails")
        print("  tony:send        - Tony: Send approved emails")
        print("  jarvis:leads     - Jarvis: Review leads")
        print("  jarvis:clones    - Jarvis: Review cloned sites")
        print("  jarvis:outreach  - Jarvis: Review pitch emails")
        print("  reset            - Clear all status flags")
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "status":
        s = get_pipeline_status()
        print("Pipeline Status:")
        for k, v in s.items():
            print(f"  {k}: {'✅' if v else '⬜'}")

    elif cmd == "stage":
        stage = current_stage()
        owner = STAGE_OWNER.get(stage, "?")
        print(f"Current stage: {stage} (→ {owner.upper()})")

    elif cmd == "log":
        if LOG_FILE.exists():
            log = json.loads(LOG_FILE.read_text())
            for entry in log[-20:]:
                print(f"[{entry['timestamp']}] {entry['agent'].upper()}: {entry['action']}")
                if entry.get('details'):
                    print(f"  → {entry['details']}")
        else:
            print("No activity log yet.")

    elif cmd == "handoffs":
        if HANDOFFS_FILE.exists():
            handoffs = json.loads(HANDOFFS_FILE.read_text())
            pending = [h for h in handoffs if h["status"] == "pending"]
            if pending:
                for h in pending:
                    print(f"{h['from'].upper()} → {h['to'].upper()} | {h['stage']} | {h['notes']}")
            else:
                print("No pending handoffs.")
        else:
            print("No handoffs yet.")

    elif cmd == "tony:leads":
        tony_run_lead_gen()

    elif cmd == "tony:clone":
        tony_run_clone_build()

    elif cmd == "tony:outreach":
        tony_run_outreach()

    elif cmd == "tony:send":
        tony_send_emails()

    elif cmd == "jarvis:leads":
        jarvis_review_leads()

    elif cmd == "jarvis:clones":
        jarvis_review_clones()

    elif cmd == "jarvis:outreach":
        jarvis_review_outreach()

    elif cmd == "reset":
        for flag in STATUS_FILES:
            clear_status(flag)
        print("All status flags cleared. Pipeline reset.")

    else:
        print(f"Unknown command: {cmd}")