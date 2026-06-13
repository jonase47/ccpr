#!/usr/bin/env python3
"""Gate checklists for the Claude Code agent system.

Defines required artefacts and mandatory sections per gate.
"""

import os
import re

# Gate checklists: artefact -> list of required sections (case-insensitive search)
# None means only existence check (e.g. for directories)
GATE_CHECKLISTS = {
    "p0": {
        "docs/discovery/DISCOVERY.md": ["Status", "Detail Files"],
        "docs/discovery/PROBLEM.md": ["Problem Statement", "Target Audience"],
        "docs/discovery/MARKET.md": ["Market Size", "Competition"],
        "docs/discovery/REGULATORY.md": ["DSGVO", "Knock-Out", "Assessment"],
    },
    "p1": {
        "docs/concept/CONCEPT.md": ["Status", "Detail Files"],
        "docs/concept/USER_JOURNEYS.md": ["Persona", "Journey", "Pain Point"],
        "docs/concept/FEATURES.md": ["Priorit", "MVP Scope Boundary"],
        "docs/concept/BUSINESS_MODEL.md": ["Value Proposition", "Pricing"],
        "docs/concept/FINANCIAL_PLAN.md": ["Cost Structure", "Revenue Forecast", "Break-Even", "Assumptions"],
        "docs/concept/DSGVO_INITIAL_ASSESSMENT.md": ["Data Classification", "Legal Bases"],
    },
    "p2": {
        "docs/validation/VALIDATION.md": ["Status", "Detail Files"],
        "docs/validation/ASSUMPTIONS.md": ["Assumptions Register", "Top-3"],
        "docs/validation/MARKET_VALIDATION.md": ["Findings", "Recommendation"],
        "docs/validation/POC.md": ["Feasibility"],
        "docs/validation/REGULATORY_CHECK.md": ["Findings"],
    },
    "p3": {
        # Phase index
        "docs/architecture/ARCHITECTURE.md": ["Status", "Detail Files"],
        # Direct detail files
        "docs/architecture/COMPONENTS.md": ["Component Diagram", "Data Flows"],
        "docs/architecture/TECH_STACK.md": ["Stack Overview"],
        "docs/architecture/NFR.md": ["Non-Functional"],
        "docs/architecture/DATA_MODEL.md": ["ER Diagram", "Entities", "DSGVO"],
        "docs/architecture/API_SPEC.md": ["API Style", "Endpoints", "Auth"],
        "docs/architecture/COST_ESTIMATION.md": ["Cost Table", "Scaling"],
        "docs/architecture/ADR/": None,
        # Security sub-index + detail files
        "docs/architecture/SECURITY.md": ["Status", "Detail Files"],
        "docs/architecture/THREATS.md": ["STRIDE"],
        "docs/architecture/AUTH.md": ["Auth Method", "Roles"],
        "docs/architecture/DATA_SECURITY.md": ["Encryption", "Secrets"],
        "docs/architecture/API_SECURITY.md": ["Input Validation", "Rate Limiting"],
        "docs/architecture/CHECKLIST.md": ["Forbidden Practices"],
        # UX sub-index + detail files
        "docs/architecture/UX_CONCEPT.md": ["Status", "Detail Files"],
        "docs/architecture/NAVIGATION.md": ["Sitemap", "Critical Flows"],
        "docs/architecture/WIREFRAMES.md": ["Screen"],
        "docs/architecture/DARKMODE.md": ["Semantic Colors", "Toggle"],
        "docs/architecture/A11Y.md": ["WCAG", "Color Blindness"],
        # Infra sub-index + detail files
        "docs/architecture/INFRA.md": ["Status", "Detail Files"],
        "docs/architecture/HOSTING.md": ["Hosting Platform", "Environments"],
        "docs/architecture/CICD.md": ["Pipeline", "Branch Strategy"],
        "docs/architecture/MONITORING.md": ["Logging", "Metrics", "Alerting"],
        "docs/architecture/TESTSTRATEGY.md": ["Test Levels", "Coverage"],
    },
    "p4": {
        "docs/planning/PROJECT_PLAN.md": ["Status", "Detail Files", "Milestones"],
        "docs/planning/BACKLOG.md": ["Epic", "Stor"],
        "docs/planning/SPRINT.md": ["Sprint Goal", "Stor"],
        "docs/planning/RISKS.md": ["Risk Register"],
        "docs/planning/SETUP.md": ["Repository Structure", "CI/CD"],
        "docs/planning/DOCS.md": ["README"],
        "README.md": ["Quick Start", "Prerequisites"],
    },
    "p5": {
        "docs/planning/SPRINT.md": ["Sprint Goal", "Status"],
        "src/": None,
        "tests/": None,
    },
    "p6": {
        # Phase index
        "docs/quality/QA.md": ["Status", "Detail Files"],
        # Direct detail files
        "docs/quality/EXPLORATORY.md": ["Findings"],
        "docs/quality/BUGFIX.md": ["Fix Log"],
        # A11Y sub-index + detail files
        "docs/quality/A11Y.md": ["Status", "Detail Files"],
        "docs/quality/a11y_keyboard.md": ["Findings"],
        "docs/quality/a11y_screenreader.md": ["Findings"],
        "docs/quality/a11y_visual.md": ["Contrast", "Dark Mode"],
        # AUDIT sub-index + detail files
        "docs/quality/AUDIT.md": ["Status", "Detail Files"],
        "docs/quality/audit_auth.md": ["Findings"],
        "docs/quality/audit_config.md": ["Findings"],
        "docs/quality/audit_deps.md": ["Findings"],
        "docs/quality/audit_dsgvo.md": ["Findings"],
        "docs/quality/audit_sast.md": ["Findings"],
        # FUNCTIONAL sub-index + detail files
        "docs/quality/FUNCTIONAL.md": ["Status", "Detail Files"],
        "docs/quality/func_e2e.md": ["Test Results"],
        "docs/quality/func_integration.md": ["Test Results"],
        "docs/quality/func_regression.md": ["Test Results"],
        # PENTEST sub-index + detail files
        "docs/quality/PENTEST.md": ["Status", "Detail Files"],
        "docs/quality/pentest_recon.md": ["Findings"],
        "docs/quality/pentest_auth.md": ["Findings"],
        "docs/quality/pentest_authz.md": ["Findings"],
        "docs/quality/pentest_injection.md": ["Findings"],
        "docs/quality/pentest_logic.md": ["Findings"],
        "src/": None,
        "tests/": None,
    },
    "p7": {
        "docs/launch/LAUNCH.md": ["Status", "Detail Files"],
        "docs/launch/PREPARE.md": ["Pre-Launch Checklist", "Rollback Plan"],
        "docs/launch/DEPLOYMENT.md": ["Deployment Steps", "Smoke Test"],
        "docs/launch/MONITORING.md": ["Alerting Rules", "Incident Response"],
        "docs/launch/RELEASE_DOCS.md": ["Release Notes Summary"],
        "docs/launch/GTM.md": ["KPI"],
        "docs/quality/": None,
    },
}


# Content patterns for deeper mechanical checks per gate
CONTENT_PATTERNS = {
    "p0": {
        "docs/discovery/PROBLEM.md": [
            ("has_problem_statement", r"(?i)(Problem.*Statement|Problem.*defined|Who.*What.*Consequence)"),
            ("has_target_group", r"(?i)(Target Audience|Non-Target|Segment)"),
        ],
        "docs/discovery/MARKET.md": [
            ("has_competitors", r"(?i)(Competition|Competitor|Alternative)"),
            ("has_economic_assessment", r"(?i)(Economic Assessment|TAM|SAM|willingness.*pay)"),
        ],
        "docs/discovery/REGULATORY.md": [
            ("has_feasibility", r"(?i)(Feasibility|Showstopper|Knock.?Out|K\.O\.|economic)"),
            ("has_traffic_light", r"(🟢|🟡|🔴)"),
        ],
    },
    "p1": {
        "docs/concept/USER_JOURNEYS.md": [
            ("has_personas", r"(?i)(Persona|Frustration|Pain.?Point)"),
            ("has_journeys", r"(?i)(Journey|Scenario|Step.*[0-9])"),
        ],
        "docs/concept/FEATURES.md": [
            ("has_prioritization", r"(?i)(Must|Should|Nice|MoSCoW|Priorit)"),
            ("has_scope", r"(?i)(Scope|Scope Boundary|excluded|not included)"),
        ],
        "docs/concept/BUSINESS_MODEL.md": [
            ("has_canvas", r"(?i)(Canvas|Revenue|Value Proposition)"),
            ("has_pricing", r"(?i)(Pricing|Price|Free|Freemium|Subscription)"),
        ],
        "docs/concept/FINANCIAL_PLAN.md": [
            ("has_break_even", r"(?i)(Break.Even|Revenue Forecast|Cost Structure)"),
            ("has_assumptions_marked", r"(?i)(Assumption|assumed|estimated)"),
        ],
        "docs/concept/DSGVO_INITIAL_ASSESSMENT.md": [
            ("has_data_categories", r"(?i)(Data Category|personal data|Legal Basis)"),
        ],
    },
    "p2": {
        "docs/validation/ASSUMPTIONS.md": [
            ("has_risk_levels", r"(?i)(K\.O\.|Critical|High|Low|Consequence)"),
            ("has_validation_status", r"(?i)(validated|disproved|open|confirmed)"),
        ],
        "docs/validation/MARKET_VALIDATION.md": [
            ("has_results", r"(?i)(Result|Recommendation|Conclusion|Finding)"),
        ],
        "docs/validation/POC.md": [
            ("has_poc_reference", r"(?i)(PoC|Proof of Concept|Prototype|Feasibility)"),
        ],
        "docs/validation/REGULATORY_CHECK.md": [
            ("has_results", r"(?i)(Finding|Recommendation|Mandatory)"),
        ],
    },
    "p3": {
        "docs/architecture/COMPONENTS.md": [
            ("has_diagram", r"(?i)(```|mermaid|graph|flowchart|Component)"),
            ("has_dataflow", r"(?i)(Data Fl|Data Flow|Request.*Response)"),
        ],
        "docs/architecture/TECH_STACK.md": [
            ("has_tradeoffs", r"(?i)(Trade.off|Alternative|Rationale|Pro.*Con)"),
        ],
        "docs/architecture/DATA_MODEL.md": [
            ("has_erd", r"(?i)(ERD|Entit|Relation|1:n|n:m|Relation)"),
            ("has_dsgvo_fields", r"(?i)(DSGVO|personal data|Soft.Delete|Audit)"),
        ],
        "docs/architecture/API_SPEC.md": [
            ("has_endpoints", r"(?i)(GET|POST|PUT|DELETE|/api/)"),
            ("has_auth_concept", r"(?i)(Auth|Bearer|JWT|Session|Token)"),
        ],
        "docs/architecture/THREATS.md": [
            ("has_stride", r"(?i)(STRIDE|Spoofing|Tampering|Repudiation)"),
            ("has_critical_threats", r"(?i)(Critical|Countermeasure|Mitigation)"),
        ],
        "docs/architecture/AUTH.md": [
            ("has_auth_method", r"(?i)(JWT|Session|OAuth|Bearer|Token|Password)"),
            ("has_roles", r"(?i)(Role|Permission|Access)"),
        ],
        "docs/architecture/DATA_SECURITY.md": [
            ("has_encryption", r"(?i)(TLS|HSTS|Encryption|At Rest|In Transit)"),
            ("has_secrets", r"(?i)(Secret|Vault|Rotation|KMS)"),
        ],
        "docs/architecture/HOSTING.md": [
            ("has_hosting_platform", r"(?i)(Hetzner|AWS|Vercel|Netlify|self-host|VPS)"),
            ("has_environments", r"(?i)(prod|staging|dev|environment)"),
        ],
        "docs/architecture/CICD.md": [
            ("has_cicd", r"(?i)(CI/CD|Pipeline|Deploy|Stage)"),
            ("has_branch_strategy", r"(?i)(trunk|gitflow|branch|main|feature)"),
        ],
        "docs/architecture/MONITORING.md": [
            ("has_monitoring", r"(?i)(Monitor|Alert|Logging|Observ)"),
        ],
        "docs/architecture/TESTSTRATEGY.md": [
            ("has_coverage", r"(?i)(Coverage|Unit|Integration|E2E)"),
        ],
        "docs/architecture/A11Y.md": [
            ("has_wcag", r"(?i)(WCAG|AA|AAA|Contrast)"),
        ],
    },
    "p4": {
        "docs/planning/BACKLOG.md": [
            ("has_estimates", r"(?i)(Story Points?|SP[\s:]|Effort|[XSML]{1,2}\b)"),
            ("has_acceptance", r"(?i)(Acceptance Criteria|Acceptance|Given.*When.*Then)"),
            ("has_dependencies", r"(?i)(Dependenc|blocked)"),
        ],
        "docs/planning/SPRINT.md": [
            ("has_sprint_goal", r"(?i)(Sprint.Goal|Sprint Goal)"),
            ("has_dod", r"(?i)(Definition of Done|DoD)"),
        ],
        "docs/planning/PROJECT_PLAN.md": [
            ("has_milestones", r"(?i)(Milestone)"),
            ("has_criteria", r"(?i)(Success Criteria|Success Criterion|Criterion|Definition)"),
        ],
        "docs/planning/RISKS.md": [
            ("has_countermeasures", r"(?i)(Countermeasure|Mitigation|Fallback)"),
        ],
    },
    "p5": {
        "docs/planning/SPRINT.md": [
            ("has_story_status", r"(?i)(Done|In Progress|Deferred|Status)"),
            ("has_sprint_goal", r"(?i)(Sprint.Goal|Sprint Goal)"),
        ],
    },
}


def check_content_patterns(file_path: str, patterns: list) -> list:
    """Check content patterns (regex) in a file.

    Args:
        file_path: Absolute path to the file
        patterns: List of (name, regex_pattern) tuples

    Returns list of dicts with keys: name, pattern, found
    """
    if not patterns or not os.path.isfile(file_path):
        return []

    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    results = []
    for name, pattern in patterns:
        found = bool(re.search(pattern, content))
        results.append({"name": name, "pattern": pattern, "found": found})

    return results


def check_sections(file_path: str, required_sections: list) -> list:
    """Check which required sections exist in a file.

    Returns list of dicts with keys: section, found
    """
    if not required_sections or not os.path.isfile(file_path):
        return []

    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read().lower()

    results = []
    for section in required_sections:
        found = section.lower() in content
        results.append({"section": section, "found": found})

    return results


# Directory aliases for run_gate_check: when a checklist directory key (e.g.
# "src/") is missing, try these generic alternatives before falling back to
# language-specific heuristics. Order matters — first hit wins.
DIRECTORY_ALTERNATIVES = {
    "src/": ["Sources/", "lib/", "app/", "App/"],
    "tests/": ["Tests/", "test/", "__tests__/", "spec/"],
}


def _resolve_directory_path(project_dir: str, rel_path: str):
    """Resolve a directory path with common alternatives + iOS heuristic.

    1. Direct match (e.g. project actually has src/).
    2. Generic alternatives via DIRECTORY_ALTERNATIVES.
    3. iOS heuristic:
       - "src/"  -> top-level dir containing .swift files, NOT ending in
         "Tests"/"UITests"/".xcodeproj"/".xcworkspace" (Xcode app targets
         live in <ProjectName>/).
       - "tests/" -> top-level dir whose name ends in "Tests" or "UITests"
         (Xcode test-target convention, e.g. ExampleAppTests/).

    Returns the relative path that exists (with trailing slash for dirs)
    or None if nothing matched. Why: the generic gate-preflight checklist
    uses POSIX-style "src/"/"tests/", but iOS projects don't follow that
    naming. Without this resolver, /gate-p5 reports false-negatives on
    every Xcode-based project.
    """
    if os.path.isdir(os.path.join(project_dir, rel_path)):
        return rel_path
    for alt in DIRECTORY_ALTERNATIVES.get(rel_path, []):
        if os.path.isdir(os.path.join(project_dir, alt)):
            return alt
    try:
        entries = sorted(os.listdir(project_dir))
    except OSError:
        return None
    xcodeproj_name = next(
        (e[: -len(".xcodeproj")] for e in entries if e.endswith(".xcodeproj")),
        None,
    )
    if rel_path == "src/":
        if xcodeproj_name:
            candidate = os.path.join(project_dir, xcodeproj_name)
            if os.path.isdir(candidate):
                try:
                    if any(f.endswith(".swift") for f in os.listdir(candidate)):
                        return xcodeproj_name + "/"
                except OSError:
                    pass
        for entry in entries:
            entry_path = os.path.join(project_dir, entry)
            if (not os.path.isdir(entry_path)
                    or entry.startswith(".")
                    or entry.endswith("Tests")
                    or entry.endswith("UITests")
                    or entry.endswith(".xcodeproj")
                    or entry.endswith(".xcworkspace")):
                continue
            try:
                contents = os.listdir(entry_path)
            except OSError:
                continue
            if any(f.endswith(".swift") for f in contents):
                return entry + "/"
    elif rel_path == "tests/":
        if xcodeproj_name:
            for suffix in ("Tests", "UITests"):
                candidate_name = xcodeproj_name + suffix
                if os.path.isdir(os.path.join(project_dir, candidate_name)):
                    return candidate_name + "/"
        for entry in entries:
            entry_path = os.path.join(project_dir, entry)
            if (os.path.isdir(entry_path)
                    and not entry.startswith(".")
                    and (entry.endswith("Tests") or entry.endswith("UITests"))):
                return entry + "/"
    return None


def run_gate_check(phase: str, project_dir: str) -> dict:
    """Run a complete gate preflight check.

    Returns dict with artefact status, section checks, and summary.
    """
    checklist = GATE_CHECKLISTS.get(phase, {})
    artefacts = []
    total_artefacts = len(checklist)
    existing_artefacts = 0
    missing_sections = []

    for rel_path, sections in checklist.items():
        is_dir = rel_path.endswith("/")

        entry = {
            "path": rel_path,
            "exists": False,
            "lines": 0,
            "is_dir": is_dir,
            "sections": [],
        }

        if is_dir:
            resolved = _resolve_directory_path(project_dir, rel_path)
            if resolved is not None:
                full_path = os.path.join(project_dir, resolved)
                entry["exists"] = True
                entry["path"] = resolved
                entry["lines"] = len([
                    f for f in os.listdir(full_path)
                    if os.path.isfile(os.path.join(full_path, f))
                ])
                existing_artefacts += 1
        else:
            full_path = os.path.join(project_dir, rel_path)
            if os.path.isfile(full_path):
                entry["exists"] = True
                with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                    entry["lines"] = sum(1 for _ in f)
                existing_artefacts += 1

                if sections:
                    entry["sections"] = check_sections(full_path, sections)
                    for s in entry["sections"]:
                        if not s["found"]:
                            missing_sections.append(f"{rel_path}: {s['section']}")

        artefacts.append(entry)

    missing_artefacts = [a["path"] for a in artefacts if not a["exists"]]

    ready = len(missing_artefacts) == 0 and len(missing_sections) == 0
    recommendation = "Gate is ready for content review." if ready else "Gate is NOT ready."

    return {
        "phase": phase,
        "total": total_artefacts,
        "existing": existing_artefacts,
        "missing_artefacts": missing_artefacts,
        "missing_sections": missing_sections,
        "ready": ready,
        "recommendation": recommendation,
        "artefacts": artefacts,
    }


def main():
    """CLI interface."""
    import sys
    import json

    phase = sys.argv[1] if len(sys.argv) > 1 else "p0"
    project_dir = sys.argv[2] if len(sys.argv) > 2 else os.getcwd()

    result = run_gate_check(phase, project_dir)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
