#!/usr/bin/env python3
"""gate-preflight.py – Checks gate artefacts upfront and creates a checklist.

Usage: ~/.claude/scripts/gate-preflight.py <phase> [projectdirectory]
Output: docs/.gate-preflight-<phase>.md
"""

import sys
import os
from datetime import datetime

# Add lib to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "lib"))

from gate_checklists import run_gate_check, check_content_patterns, CONTENT_PATTERNS

# Command suggestions per phase for missing artefacts
MISSING_COMMANDS = {
    "p0": {
        "docs/discovery/DISCOVERY.md": "/p0-problem (creates the index implicitly)",
        "docs/discovery/PROBLEM.md": "/p0-problem",
        "docs/discovery/MARKET.md": "/p0-market",
        "docs/discovery/REGULATORY.md": "/p0-regulatory",
    },
    "p1": {
        "docs/concept/CONCEPT.md": "/p1-journeys (creates the index implicitly)",
        "docs/concept/USER_JOURNEYS.md": "/p1-journeys",
        "docs/concept/FEATURES.md": "/p1-features",
        "docs/concept/BUSINESS_MODEL.md": "/p1-business-model",
        "docs/concept/FINANCIAL_PLAN.md": "/p1-financial-plan",
        "docs/concept/DSGVO_INITIAL_ASSESSMENT.md": "/p1-privacy",
    },
    "p3": {
        # Phase index
        "docs/architecture/ARCHITECTURE.md": "/p3-architecture (creates the index implicitly)",
        # Direct detail files
        "docs/architecture/COMPONENTS.md": "/p3-arch-components",
        "docs/architecture/TECH_STACK.md": "/p3-arch-techstack",
        "docs/architecture/NFR.md": "/p3-arch-nfa",
        "docs/architecture/DATA_MODEL.md": "/p3-data-model",
        "docs/architecture/API_SPEC.md": "/p3-data-model",
        "docs/architecture/COST_ESTIMATION.md": "/p3-cost",
        "docs/architecture/ADR/": "/p3-arch-adr",
        # Security sub-index + detail files
        "docs/architecture/SECURITY.md": "/p3-security (sub-index, created implicitly)",
        "docs/architecture/THREATS.md": "/p3-sec-threats",
        "docs/architecture/AUTH.md": "/p3-sec-auth",
        "docs/architecture/DATA_SECURITY.md": "/p3-sec-data",
        "docs/architecture/API_SECURITY.md": "/p3-sec-api",
        "docs/architecture/CHECKLIST.md": "/p3-sec-checklist",
        # UX sub-index + detail files
        "docs/architecture/UX_CONCEPT.md": "/p3-ux (sub-index, created implicitly)",
        "docs/architecture/NAVIGATION.md": "/p3-ux-navigation",
        "docs/architecture/WIREFRAMES.md": "/p3-ux-wireframes",
        "docs/architecture/DARKMODE.md": "/p3-ux-darkmode",
        "docs/architecture/A11Y.md": "/p3-ux-a11y",
        # Infra sub-index + detail files
        "docs/architecture/INFRA.md": "/p3-infra (sub-index, created implicitly)",
        "docs/architecture/HOSTING.md": "/p3-infra-hosting",
        "docs/architecture/CICD.md": "/p3-infra-cicd",
        "docs/architecture/MONITORING.md": "/p3-infra-monitoring",
        "docs/architecture/TESTSTRATEGY.md": "/p3-infra-teststrategy",
    },
    "p2": {
        "docs/validation/VALIDATION.md": "/p2-assumptions (creates the index implicitly)",
        "docs/validation/ASSUMPTIONS.md": "/p2-assumptions",
        "docs/validation/MARKET_VALIDATION.md": "/p2-market-validation",
        "docs/validation/POC.md": "/p2-poc",
        "docs/validation/REGULATORY_CHECK.md": "/p2-regulatory-check",
    },
    "p4": {
        "docs/planning/PROJECT_PLAN.md": "/p4-backlog (creates the index implicitly)",
        "docs/planning/BACKLOG.md": "/p4-backlog",
        "docs/planning/SPRINT.md": "/p4-sprint",
        "docs/planning/RISKS.md": "/p4-sprint",
        "docs/planning/SETUP.md": "/p4-setup",
        "docs/planning/DOCS.md": "/p4-docs",
        "README.md": "/p4-docs",
        "CONTRIBUTING.md": "/p4-docs",
    },
    "p5": {
        "docs/planning/SPRINT.md": "/p4-sprint",
        "src/": "/p5-implement",
        "tests/": "/p5-implement",
    },
    "p6": {
        # Phase index
        "docs/quality/QA.md": "/p6-functional or /p6-a11y (creates the index implicitly)",
        # Direct detail files
        "docs/quality/EXPLORATORY.md": "/p6-exploratory",
        "docs/quality/BUGFIX.md": "/p6-bugfix",
        # A11Y sub-index + detail files
        "docs/quality/A11Y.md": "/p6-a11y (sub-index, created implicitly)",
        "docs/quality/a11y_keyboard.md": "/p6-a11y-keyboard",
        "docs/quality/a11y_screenreader.md": "/p6-a11y-screenreader",
        "docs/quality/a11y_visual.md": "/p6-a11y-visual",
        # AUDIT sub-index + detail files
        "docs/quality/AUDIT.md": "/p6-audit (sub-index, created implicitly)",
        "docs/quality/audit_auth.md": "/p6-audit-auth",
        "docs/quality/audit_config.md": "/p6-audit-config",
        "docs/quality/audit_deps.md": "/p6-audit-deps",
        "docs/quality/audit_dsgvo.md": "/p6-audit-dsgvo",
        "docs/quality/audit_sast.md": "/p6-audit-sast",
        # FUNCTIONAL sub-index + detail files
        "docs/quality/FUNCTIONAL.md": "/p6-functional (sub-index, created implicitly)",
        "docs/quality/func_e2e.md": "/p6-func-e2e",
        "docs/quality/func_integration.md": "/p6-func-integration",
        "docs/quality/func_regression.md": "/p6-func-regression",
        # PENTEST sub-index + detail files
        "docs/quality/PENTEST.md": "/p6-pentest (sub-index, created implicitly)",
        "docs/quality/pentest_recon.md": "/p6-pentest-recon",
        "docs/quality/pentest_auth.md": "/p6-pentest-auth",
        "docs/quality/pentest_authz.md": "/p6-pentest-authz",
        "docs/quality/pentest_injection.md": "/p6-pentest-injection",
        "docs/quality/pentest_logic.md": "/p6-pentest-logic",
    },
    "p7": {
        "docs/launch/LAUNCH.md": "/p7-prepare (creates the index implicitly)",
        "docs/launch/PREPARE.md": "/p7-prepare",
        "docs/launch/DEPLOYMENT.md": "/p7-deploy",
        "docs/launch/MONITORING.md": "/p7-monitoring",
        "docs/launch/RELEASE_DOCS.md": "/p7-release-docs",
        "docs/launch/GTM.md": "/p7-gtm",
        "docs/quality/": "/p6-functional (complete Phase 6 first)",
    },
}


def check_ollama_available() -> bool:
    """Check if Ollama is running."""
    import subprocess
    try:
        r = subprocess.run(
            ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", "http://localhost:11434/api/tags"],
            capture_output=True, text=True, timeout=3,
        )
        return r.stdout.strip() == "200"
    except Exception:
        return False


def get_ollama_summary(file_path: str) -> str:
    """Get a summary of a file via Ollama's summarize.sh."""
    import subprocess
    summarize_script = os.path.join(os.path.dirname(__file__), "local-llm", "summarize.sh")
    if not os.path.isfile(summarize_script):
        return ""
    try:
        r = subprocess.run(
            [summarize_script, file_path],
            capture_output=True, text=True, timeout=90,
        )
        return r.stdout.strip() if r.returncode == 0 else ""
    except Exception:
        return ""


def format_content_patterns(phase: str, project_dir: str) -> list:
    """Run content pattern checks and return markdown lines."""
    patterns = CONTENT_PATTERNS.get(phase, {})
    if not patterns:
        return []

    lines = ["## Content Check (mechanical)", "",
             "| Criterion | File | Found |",
             "|-----------|------|-------|"]

    PATTERN_LABELS = {
        # P0
        "has_problem_statement": "Problem statement",
        "has_target_group": "Target audience",
        "has_competitors": "Competitors",
        "has_economic_assessment": "Economic assessment",
        "has_feasibility": "Feasibility",
        "has_traffic_light": "Regulatory verdict (🟢/🟡/🔴)",
        # P1
        "has_personas": "Personas",
        "has_journeys": "User journeys",
        "has_prioritization": "Prioritization (MoSCoW)",
        "has_scope": "MVP scope/delimitation",
        "has_canvas": "Business Model Canvas",
        "has_pricing": "Pricing approach",
        "has_break_even": "Break-even/revenue forecast",
        "has_assumptions_marked": "Assumptions marked",
        "has_data_categories": "Data categories/DSGVO (GDPR)",
        # P2
        "has_risk_levels": "Risk assessments",
        "has_validation_status": "Validation status",
        "has_results": "Results/recommendations",
        "has_poc_reference": "PoC reference",
        # P3
        "has_diagram": "Architecture diagram",
        "has_dataflow": "Data flows",
        "has_tradeoffs": "Trade-offs/rationale",
        "has_erd": "ERD/entities",
        "has_dsgvo_fields": "DSGVO (GDPR) fields",
        "has_endpoints": "API endpoints",
        "has_auth_concept": "Auth concept",
        "has_stride": "STRIDE analysis",
        "has_critical_threats": "Critical threats",
        "has_auth_method": "Auth method",
        "has_roles": "Roles & permissions",
        "has_encryption": "Encryption (transit/rest)",
        "has_secrets": "Secrets management",
        "has_hosting_platform": "Hosting platform",
        "has_environments": "Environments",
        "has_cicd": "CI/CD pipeline",
        "has_branch_strategy": "Branch strategy",
        "has_monitoring": "Monitoring/alerting",
        "has_coverage": "Test coverage",
        "has_wcag": "WCAG target",
        # P4
        "has_estimates": "Effort estimates",
        "has_acceptance": "Acceptance criteria",
        "has_dependencies": "Dependencies",
        "has_sprint_goal": "Sprint goal",
        "has_dod": "Definition of Done",
        "has_milestones": "Milestones",
        "has_criteria": "Success criteria",
        "has_countermeasures": "Countermeasures",
        # P5
        "has_story_status": "Story status",
    }

    for rel_path, file_patterns in patterns.items():
        full_path = os.path.join(project_dir, rel_path)
        results = check_content_patterns(full_path, file_patterns)
        filename = os.path.basename(rel_path)
        for r in results:
            label = PATTERN_LABELS.get(r["name"], r["name"])
            marker = "[+]" if r["found"] else "[-]"
            lines.append(f"| {label} | {filename} | {marker} |")

    lines.append("")
    return lines


def extract_constitution_inviolable(project_dir: str) -> tuple:
    """Extract the Inviolable section from docs/CONSTITUTION.md.

    Returns: (status, content) where status is one of:
      "ok"      — file exists and Inviolable section was found (content is bullet list)
      "no-file" — CONSTITUTION.md does not exist
      "no-section" — file exists but no Inviolable section found
      "empty"   — Inviolable section is empty
    """
    constitution_path = os.path.join(project_dir, "docs", "CONSTITUTION.md")
    if not os.path.isfile(constitution_path):
        return ("no-file", "")

    try:
        with open(constitution_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception:
        return ("no-file", "")

    # Find the Inviolable section: ## Inviolable ... (until next ## )
    import re
    match = re.search(
        r"^## Inviolable.*?\n(.*?)(?=^## |\Z)",
        content,
        flags=re.MULTILINE | re.DOTALL,
    )
    if not match:
        return ("no-section", "")

    body = match.group(1).strip()
    if not body:
        return ("empty", "")

    return ("ok", body)


def format_constitution_check(project_dir: str) -> list:
    """Generate the Constitution Inviolables block for the preflight report."""
    status, content = extract_constitution_inviolable(project_dir)

    lines = ["## Constitution Inviolables (Required Read)", ""]

    if status == "ok":
        lines.append("These Inviolable bullets from `docs/CONSTITUTION.md` must be taken into account during the gate check. Any phase decision that violates an Inviolable must be marked as 'Inviolable breach' in the gate verdict.")
        lines.append("")
        lines.append(content)
        lines.append("")
    elif status == "no-file":
        lines.append("[-] `docs/CONSTITUTION.md` not found.")
        lines.append("")
        lines.append("Full-Track projects should have a Constitution. Recommendation: run `/constitution` to create it. For Lean-Track the Constitution is optional (Constitution-Light in `docs/FRAME.md` is sufficient).")
        lines.append("")
    elif status == "no-section":
        lines.append("[-] `docs/CONSTITUTION.md` exists but section `## Inviolable` is missing.")
        lines.append("")
        lines.append("Constitution schema violated — section 'Inviolable (Non-Negotiable)' is mandatory. Recommendation: run `/constitution` to repair it.")
        lines.append("")
    elif status == "empty":
        lines.append("[!] `docs/CONSTITUTION.md` has an empty Inviolable section.")
        lines.append("")
        lines.append("When `status: active`, at least 1 Inviolable must exist. Recommendation: run `/constitution` to refine it.")
        lines.append("")

    return lines


def format_ollama_summaries(result: dict, project_dir: str) -> list:
    """Generate Ollama summaries for existing documents."""
    if not check_ollama_available():
        return []

    lines = ["## Document Summaries (via Ollama)", ""]

    for a in result["artefacts"]:
        if not a["exists"] or a["is_dir"]:
            continue
        full_path = os.path.join(project_dir, a["path"])
        summary = get_ollama_summary(full_path)
        if summary:
            filename = os.path.basename(a["path"])
            lines.append(f"### {filename}")
            lines.append(summary)
            lines.append("")

    return lines if len(lines) > 2 else []


def format_markdown(result: dict, phase: str, project_dir: str = "") -> str:
    """Format gate check result as Markdown."""
    now = datetime.now().strftime("%d.%m.%Y %H:%M")
    lines = []

    lines.append(f"# Gate {phase.upper()} Pre-Flight Check (generated: {now})")
    lines.append("")
    lines.append("## Artefact Status")
    lines.append("")
    lines.append("| Artefact | Exists | Lines | Required Sections |")
    lines.append("|----------|--------|-------|-------------------|")

    for a in result["artefacts"]:
        exists = "[+]" if a["exists"] else "[-]"

        if a["is_dir"]:
            line_info = f"{a['lines']} files" if a["exists"] else "-"
        else:
            line_info = str(a["lines"]) if a["exists"] else "-"

        if a["sections"]:
            sec_parts = []
            for s in a["sections"]:
                marker = "[+]" if s["found"] else "[-]"
                sec_parts.append(f"{s['section']} {marker}")
            sections_str = ", ".join(sec_parts)
        else:
            sections_str = "-"

        lines.append(f"| {a['path']} | {exists} | {line_info} | {sections_str} |")

    # Content pattern checks (if available for this phase)
    if project_dir:
        pattern_lines = format_content_patterns(phase, project_dir)
        if pattern_lines:
            lines.append("")
            lines.extend(pattern_lines)

        # Constitution Inviolables (mandatory pre-gate read)
        constitution_lines = format_constitution_check(project_dir)
        if constitution_lines:
            lines.extend(constitution_lines)

        # Ollama summaries (graceful fallback if unavailable)
        summary_lines = format_ollama_summaries(result, project_dir)
        if summary_lines:
            lines.extend(summary_lines)

    lines.append("")
    lines.append("## Summary")
    lines.append(f"- {result['existing']}/{result['total']} artefacts present")

    if result["missing_artefacts"]:
        lines.append(f"- {len(result['missing_artefacts'])} missing: {', '.join(result['missing_artefacts'])}")

    if result["missing_sections"]:
        lines.append(f"- {len(result['missing_sections'])} required sections missing in present artefacts:")
        for ms in result["missing_sections"]:
            lines.append(f"  - {ms}")

    lines.append("")
    lines.append("## Recommendation")

    if result["ready"]:
        lines.append(f"Gate {phase.upper()} is ready for content review by Claude.")
        lines.append("All artefacts present, all required sections found.")
    else:
        lines.append(f"Gate {phase.upper()} is NOT ready. Create missing artefacts/sections first:")
        cmds = MISSING_COMMANDS.get(phase, {})
        suggested = set()
        for missing in result["missing_artefacts"]:
            if missing in cmds and cmds[missing] not in suggested:
                lines.append(f"- {cmds[missing]} (for {missing})")
                suggested.add(cmds[missing])
        if not suggested:
            lines.append("- Create missing files manually or via phase commands")

    lines.append("")
    return "\n".join(lines)


def main():
    if len(sys.argv) < 2:
        print("Usage: gate-preflight.py <phase> [projectdirectory]")
        print("  phase: p0, p1, p2, p3, p4, p5, p6, p7")
        sys.exit(1)

    phase = sys.argv[1].lower().replace("gate-", "")
    project_dir = sys.argv[2] if len(sys.argv) > 2 else os.getcwd()

    # Ensure docs directory exists
    os.makedirs(os.path.join(project_dir, "docs"), exist_ok=True)

    result = run_gate_check(phase, project_dir)
    markdown = format_markdown(result, phase, project_dir)

    output_file = os.path.join(project_dir, "docs", f".gate-preflight-{phase}.md")
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(markdown)

    print(f"Gate pre-flight check written: {output_file}")

    # Also print summary to stdout
    if result["ready"]:
        print(f"Status: READY ({result['existing']}/{result['total']} artefacts)")
    else:
        print(f"Status: NOT READY ({result['existing']}/{result['total']} artefacts, "
              f"{len(result['missing_sections'])} missing sections)")


if __name__ == "__main__":
    main()
