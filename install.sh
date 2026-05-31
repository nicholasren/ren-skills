#!/usr/bin/env bash
# Install the skills in this repo into ~/.agents/skills.
#
# Usage:
#   ./install.sh                          # install all skills
#   ./install.sh aws-permission-evaluator # install one skill
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
TARGET="$HOME/.agents/skills"
mkdir -p "$TARGET"

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
echo "Done."
