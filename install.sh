#!/usr/bin/env bash
# Install ren-skills into your agent's skills directory.
#
# Usage:
#   ./install.sh                          # auto-detect target, install all skills
#   ./install.sh aws-permission-evaluator # install one skill
#   SKILLS_DIR=~/.cursor/skills ./install.sh
#   curl -fsSL https://raw.githubusercontent.com/<you>/ren-skills/main/install.sh | bash
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/<you>/ren-skills.git}"

# Source: local checkout if run from inside the repo, else clone.
SELF="${BASH_SOURCE[0]:-$0}"
SELF_DIR="$(cd "$(dirname "$SELF")" 2>/dev/null && pwd || true)"
if [ -n "$SELF_DIR" ] && [ -d "$SELF_DIR/skills" ]; then
  SRC="$SELF_DIR"
  CLONED=""
else
  SRC="$(mktemp -d)"
  echo "Fetching $REPO_URL ..."
  git clone --depth 1 "$REPO_URL" "$SRC" >/dev/null 2>&1
  CLONED="$SRC"
fi

# Target skills dir: explicit override > ~/.cursor > ~/.agents (default).
if [ -n "${SKILLS_DIR:-}" ]; then
  TARGET="$SKILLS_DIR"
elif [ -d "$HOME/.cursor" ]; then
  TARGET="$HOME/.cursor/skills"
else
  TARGET="$HOME/.agents/skills"
fi
mkdir -p "$TARGET"

# Which skills: args, else all under skills/.
if [ "$#" -gt 0 ]; then
  SKILLS=("$@")
else
  SKILLS=()
  for d in "$SRC"/skills/*/; do SKILLS+=("$(basename "$d")"); done
fi

for s in "${SKILLS[@]}"; do
  if [ -d "$SRC/skills/$s" ]; then
    rm -rf "$TARGET/$s"
    cp -R "$SRC/skills/$s" "$TARGET/$s"
    find "$TARGET/$s" -name '.DS_Store' -delete 2>/dev/null || true
    echo "Installed $s -> $TARGET/$s"
  else
    echo "Skill not found: $s" >&2
  fi
done

[ -n "$CLONED" ] && rm -rf "$CLONED"
echo "Done."
