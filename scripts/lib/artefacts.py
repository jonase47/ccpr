#!/usr/bin/env python3
"""Phase-to-artefacts mapping for the Claude Code agent system.

Defines expected files per phase and checks their existence.
"""

import os
from pathlib import Path

# Expected artefacts per phase (path relative to project root)
PHASE_ARTEFACTS = {
    "p0": {
        "docs/discovery/DISCOVERY.md": "Discovery Phase Index",
        "docs/discovery/PROBLEM.md": "Problem Definition (P0)",
        "docs/discovery/MARKET.md": "Market Assessment (P0)",
        "docs/discovery/REGULATORY.md": "Regulatory Assessment (P0)",
    },
    "p1": {
        "docs/concept/CONCEPT.md": "Conception Phase Index",
        "docs/concept/USER_JOURNEYS.md": "Personas & User Journeys (P1)",
        "docs/concept/FEATURES.md": "Feature Definition incl. MVP Scope (P1)",
        "docs/concept/BUSINESS_MODEL.md": "Business Model (P1)",
        "docs/concept/FINANCIAL_PLAN.md": "Financial Plan (P1)",
        "docs/concept/DSGVO_INITIAL_ASSESSMENT.md": "DSGVO Initial Assessment (P1)",
    },
    "p2": {
        "docs/validation/VALIDATION.md": "Validation Phase Index",
        "docs/validation/ASSUMPTIONS.md": "Assumptions Register (P2)",
        "docs/validation/MARKET_VALIDATION.md": "Market Validation (P2)",
        "docs/validation/POC.md": "Proof of Concept (P2)",
        "docs/validation/REGULATORY_CHECK.md": "Regulatory Validation (P2)",
    },
    "p3": {
        # Phase index
        "docs/architecture/ARCHITECTURE.md": "Architecture Phase Index",
        # Direct detail files
        "docs/architecture/COMPONENTS.md": "Component Diagram & Data Flows (P3)",
        "docs/architecture/TECH_STACK.md": "Tech Stack Decision (P3)",
        "docs/architecture/NFR.md": "Non-Functional Requirements (P3)",
        "docs/architecture/DATA_MODEL.md": "Data Model (P3)",
        "docs/architecture/API_SPEC.md": "API Specification (P3)",
        "docs/architecture/COST_ESTIMATION.md": "Operating Costs (P3)",
        "docs/architecture/ADR/": "Architecture Decision Records",
        # Security sub-index + detail files
        "docs/architecture/SECURITY.md": "Security Sub-Index (P3)",
        "docs/architecture/THREATS.md": "STRIDE Threat Model (P3)",
        "docs/architecture/AUTH.md": "Auth & Authorization Concept (P3)",
        "docs/architecture/DATA_SECURITY.md": "Data Security (P3)",
        "docs/architecture/API_SECURITY.md": "API Security (P3)",
        "docs/architecture/CHECKLIST.md": "Developer Security Checklist (P3)",
        # UX sub-index + detail files
        "docs/architecture/UX_CONCEPT.md": "UX Sub-Index (P3)",
        "docs/architecture/NAVIGATION.md": "Sitemap & Information Architecture (P3)",
        "docs/architecture/WIREFRAMES.md": "Wireframes (P3)",
        "docs/architecture/DARKMODE.md": "Dark Mode Color Strategy (P3)",
        "docs/architecture/A11Y.md": "Accessibility Concept (P3)",
        # Infra sub-index + detail files
        "docs/architecture/INFRA.md": "Infrastructure Sub-Index (P3)",
        "docs/architecture/HOSTING.md": "Hosting & Deployment Strategy (P3)",
        "docs/architecture/CICD.md": "CI/CD Pipeline (P3)",
        "docs/architecture/MONITORING.md": "Monitoring & Observability (P3)",
        "docs/architecture/TESTSTRATEGY.md": "Test Strategy (P3)",
    },
    "p4": {
        "docs/planning/PROJECT_PLAN.md": "Planning Phase Index",
        "docs/planning/BACKLOG.md": "Product Backlog (P4, living)",
        "docs/planning/SPRINT.md": "Sprint Plan (P4, living)",
        "docs/planning/RISKS.md": "Risk Register (P4, living)",
        "docs/planning/SETUP.md": "Repo & CI/CD Setup Status (P4)",
        "docs/planning/DOCS.md": "README/CONTRIBUTING Summary (P4)",
        "README.md": "Project README",
        "CONTRIBUTING.md": "Contributing Guide",
    },
    "p5": {
        "src/": "Source Code Directory",
        "tests/": "Test Directory",
        "docs/planning/SPRINT.md": "Current Sprint",
    },
    "p6": {
        # Phase index
        "docs/quality/QA.md": "Quality Phase Index",
        # Direct detail files
        "docs/quality/EXPLORATORY.md": "Exploratory Test Protocol (P6)",
        "docs/quality/BUGFIX.md": "P6 Bugfix Log",
        # A11Y sub-index + detail files
        "docs/quality/A11Y.md": "Accessibility Sub-Index (P6)",
        "docs/quality/a11y_keyboard.md": "Keyboard A11y Findings (P6)",
        "docs/quality/a11y_screenreader.md": "Screen-Reader A11y Findings (P6)",
        "docs/quality/a11y_visual.md": "Visual A11y Findings (P6)",
        # AUDIT sub-index + detail files
        "docs/quality/AUDIT.md": "Security Audit Sub-Index (P6)",
        "docs/quality/audit_auth.md": "Auth Audit Findings (P6)",
        "docs/quality/audit_config.md": "Configuration Audit Findings (P6)",
        "docs/quality/audit_deps.md": "Dependency Audit Findings (P6)",
        "docs/quality/audit_dsgvo.md": "DSGVO Compliance Findings (P6)",
        "docs/quality/audit_sast.md": "SAST Findings (P6)",
        # FUNCTIONAL sub-index + detail files
        "docs/quality/FUNCTIONAL.md": "Functional Test Sub-Index (P6)",
        "docs/quality/func_e2e.md": "E2E Test Results (P6)",
        "docs/quality/func_integration.md": "Integration Test Results (P6)",
        "docs/quality/func_regression.md": "Regression Test Results (P6)",
        # PENTEST sub-index + detail files
        "docs/quality/PENTEST.md": "Pentest Sub-Index (P6)",
        "docs/quality/pentest_recon.md": "Pentest Recon Findings (P6)",
        "docs/quality/pentest_auth.md": "Pentest Auth Findings (P6)",
        "docs/quality/pentest_authz.md": "Pentest Authz Findings (P6)",
        "docs/quality/pentest_injection.md": "Pentest Injection Findings (P6)",
        "docs/quality/pentest_logic.md": "Pentest Logic Findings (P6)",
    },
    "p7": {
        "docs/launch/LAUNCH.md": "Launch Phase Index",
        "docs/launch/PREPARE.md": "Pre-Launch Checklist (P7)",
        "docs/launch/DEPLOYMENT.md": "Deployment Log (P7)",
        "docs/launch/MONITORING.md": "Monitoring & Runbook (P7)",
        "docs/launch/RELEASE_DOCS.md": "Release Docs Summary (P7)",
        "docs/launch/GTM.md": "Go-to-Market & KPI (P7)",
    },
    "p8": {
        "docs/operations/OPS.md": "Operations Phase Index",
        "docs/operations/BUSINESS.md": "Business KPI Report (P8, living)",
        "docs/operations/ITERATION.md": "Iteration Plan (P8, living)",
        "docs/operations/OPS_REVIEW.md": "Operations Review (P8, living)",
        "docs/operations/SECURITY.md": "Ongoing Security Updates (P8, living)",
    },
}

# Cumulative: phases also require artefacts from previous phases
CUMULATIVE_PHASES = True


def get_expected_artefacts(phase: str, cumulative: bool = True) -> dict:
    """Return expected artefacts for a phase.

    Args:
        phase: Phase like "p3"
        cumulative: If True, include artefacts from all previous phases

    Returns:
        Dict mapping file path to description
    """
    if not cumulative:
        return PHASE_ARTEFACTS.get(phase, {})

    result = {}
    phase_num = int(phase[1]) if phase else 0

    for p in range(phase_num + 1):
        p_key = f"p{p}"
        if p_key in PHASE_ARTEFACTS:
            result.update(PHASE_ARTEFACTS[p_key])

    return result


def check_artefacts(project_dir: str, phase: str, cumulative: bool = False) -> list:
    """Check which artefacts exist for a given phase.

    Returns list of dicts with keys: path, description, exists, lines
    """
    expected = get_expected_artefacts(phase, cumulative)
    results = []

    for rel_path, description in expected.items():
        full_path = os.path.join(project_dir, rel_path)
        is_dir = rel_path.endswith("/")

        entry = {
            "path": rel_path,
            "description": description,
            "exists": False,
            "lines": 0,
            "is_dir": is_dir,
        }

        if is_dir:
            if os.path.isdir(full_path):
                entry["exists"] = True
                # Count files in directory
                entry["lines"] = len([
                    f for f in os.listdir(full_path)
                    if os.path.isfile(os.path.join(full_path, f))
                ])
        else:
            if os.path.isfile(full_path):
                entry["exists"] = True
                with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                    entry["lines"] = sum(1 for _ in f)

        results.append(entry)

    return results


def main():
    """CLI interface for artefacts module."""
    import sys
    import json

    phase = sys.argv[1] if len(sys.argv) > 1 else "p0"
    project_dir = sys.argv[2] if len(sys.argv) > 2 else os.getcwd()
    cumulative = "--cumulative" in sys.argv

    results = check_artefacts(project_dir, phase, cumulative)

    existing = sum(1 for r in results if r["exists"])
    total = len(results)

    output = {
        "phase": phase,
        "summary": f"{existing}/{total} Artifacts present",
        "artefacts": results,
    }

    print(json.dumps(output, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
