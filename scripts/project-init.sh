#!/usr/bin/env bash
# project-init.sh – Creates project structure without Claude tokens.
# Usage: ~/.claude/scripts/project-init.sh <projectname> [template]
# Templates: default, webapp, api, library

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATES_DIR="${HOME}/.claude/templates"
WORKSPACE="${HOME}/Workspace"

if [ $# -lt 1 ]; then
    echo "Usage: project-init.sh <projectname> [template]"
    echo "  template: default, webapp, api, library"
    exit 1
fi

PROJECT_NAME="$1"
TEMPLATE="${2:-default}"
PROJECT_DIR="${WORKSPACE}/${PROJECT_NAME}"

# Check if project already exists
if [ -d "${PROJECT_DIR}" ]; then
    echo "ERROR: Project '${PROJECT_NAME}' already exists at ${PROJECT_DIR}"
    exit 1
fi

echo "Creating project: ${PROJECT_NAME} (Template: ${TEMPLATE})"

# Create directory structure
mkdir -p "${PROJECT_DIR}"/{docs/{discovery,concept,validation,architecture/ADR,planning,quality,launch,operations},src,tests,.claude}

# Copy templates
if [ -f "${TEMPLATES_DIR}/HANDOVER_TEMPLATE.md" ]; then
    cp "${TEMPLATES_DIR}/HANDOVER_TEMPLATE.md" "${PROJECT_DIR}/docs/HANDOVER.md"
fi

if [ -f "${TEMPLATES_DIR}/PROJECT_CLAUDE_TEMPLATE.md" ]; then
    # Copy and replace project name placeholder
    sed "s/{{PROJECT_NAME}}/${PROJECT_NAME}/g" "${TEMPLATES_DIR}/PROJECT_CLAUDE_TEMPLATE.md" > "${PROJECT_DIR}/.claude/CLAUDE.md"
fi

# Generate empty P0 phase index (Document Splitting Convention).
# Subskill commands (/p0-problem etc.) write detail files into this directory
# and refresh the index; gate-p0 reads the index first.
TODAY=$(date +%d.%m.%Y)
cat > "${PROJECT_DIR}/docs/discovery/DISCOVERY.md" <<EOF
# Discovery (P0) – Index

**Status:** Not started
**Last Updated:** ${TODAY}

## Key Decisions
<!-- One-liners lifted by /p0-* subskills (link to detail file). -->
- _none yet_

## Open Risks / Open Questions
<!-- Critical items surfaced by /p0-* subskills. -->
- _none yet_

## Detail Files
| Subskill | File | Status |
|---|---|---|
| Problem Definition | [PROBLEM.md](PROBLEM.md) | _missing_ |
| Market Assessment | [MARKET.md](MARKET.md) | _missing_ |
| Regulatory | [REGULATORY.md](REGULATORY.md) | _missing_ |

## Gate Notes
<!-- Filled by /gate-p0 with verdict and any Conditional-Go conditions. -->
EOF

# Create .gitignore
cat > "${PROJECT_DIR}/.gitignore" << 'EOF'
# OS
.DS_Store
Thumbs.db

# IDE
.idea/
.vscode/
*.swp
*.swo

# Dependencies (language-specific, add as needed)
node_modules/
__pycache__/
*.pyc
.venv/
venv/
target/

# Environment
.env
.env.local
.env.*.local

# Claude session files (generated, do not commit)
docs/.session-context.md
docs/.gate-preflight-*.md
docs/.quality-scan-report.json

# Build output
dist/
build/
*.egg-info/
EOF

# Template-specific additions
case "${TEMPLATE}" in
    webapp)
        mkdir -p "${PROJECT_DIR}/src"/{components,pages,styles,utils,hooks}
        mkdir -p "${PROJECT_DIR}/public"
        echo "# ${PROJECT_NAME} – Web Application" > "${PROJECT_DIR}/src/.gitkeep"
        ;;
    api)
        mkdir -p "${PROJECT_DIR}/src"/{routes,middleware,models,services,utils}
        mkdir -p "${PROJECT_DIR}/config"
        echo "# ${PROJECT_NAME} – API" > "${PROJECT_DIR}/src/.gitkeep"
        ;;
    library)
        mkdir -p "${PROJECT_DIR}/src/lib"
        mkdir -p "${PROJECT_DIR}/examples"
        echo "# ${PROJECT_NAME} – Library" > "${PROJECT_DIR}/src/.gitkeep"
        ;;
    default)
        echo "# ${PROJECT_NAME}" > "${PROJECT_DIR}/src/.gitkeep"
        ;;
    *)
        echo "Unknown template: ${TEMPLATE}. Using 'default'."
        echo "# ${PROJECT_NAME}" > "${PROJECT_DIR}/src/.gitkeep"
        ;;
esac

# Initialize git
cd "${PROJECT_DIR}"
git init -q
git add -A
git commit -q -m "project: initialize project structure (template: ${TEMPLATE})"

echo ""
echo "Project created: ${PROJECT_DIR}"
echo ""
echo "Next steps:"
echo "  cd ${PROJECT_DIR} && claude"
echo "  Then: /project-init or /p0-problem"
echo ""
echo "Directory structure:"
find "${PROJECT_DIR}" -maxdepth 3 -not -path '*/.git/*' -not -path '*/.git' | sort | head -40 | sed "s|${WORKSPACE}/||"
