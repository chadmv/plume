#!/usr/bin/env bash
# Memory-store health report for the retro skill's promotion step.
# Usage: store_health.sh <memory-dir> [repo-root]
# Exit status is 1 when the index is over budget, 0 otherwise.
#
# The budget and caps below are the single definition; SKILL.md refers here rather than
# restating the numbers.
INDEX_BUDGET_BYTES=20000   # MEMORY.md is injected into every session and every dispatch
HOOK_CAP_BYTES=300         # one index entry line, including the link
BODY_CAP_LINES=80          # one memory file
BODY_CAP_BYTES=4000        # project memory shows a session only each file's first 4 KB

set -u
mem=$(printf '%s' "${1:?usage: store_health.sh <memory-dir> [repo-root]}" | sed 's#\\#/#g')
repo=$(printf '%s' "${2:-.}" | sed 's#\\#/#g')
index="$mem/MEMORY.md"
[ -f "$index" ] || { echo "no index at $index"; exit 0; }

echo "budget: index <= $INDEX_BUDGET_BYTES bytes, hook <= $HOOK_CAP_BYTES bytes, body <= $BODY_CAP_LINES lines and $BODY_CAP_BYTES bytes"

bytes=$(wc -c < "$index" | tr -d ' ')
entries=$(grep -c '^- \[' "$index")
status=OK
[ "$bytes" -gt "$INDEX_BUDGET_BYTES" ] && status=OVER
echo "index: $bytes bytes, $entries entries - $status"

echo "hooks over cap:"
LC_ALL=C grep '^- \[' "$index" | LC_ALL=C awk -v cap="$HOOK_CAP_BYTES" '
  length($0) > cap {
    if (match($0, /\(([^)]+\.md)\)/)) file = substr($0, RSTART + 1, RLENGTH - 2); else file = "?"
    printf "  %dB %s\n", length($0), file
  }'

echo "bodies over cap:"
for f in "$mem"/*.md; do
  case "$f" in */MEMORY.md) continue ;; esac
  n=$(wc -l < "$f" | tr -d ' ')
  b=$(wc -c < "$f" | tr -d ' ')
  if [ "$n" -gt "$BODY_CAP_LINES" ] || [ "$b" -gt "$BODY_CAP_BYTES" ]; then
    echo "  $n lines, ${b}B $(basename "$f")"
  fi
done

if git -C "$repo" rev-parse --is-inside-work-tree > /dev/null 2>&1; then
  tracked=$(mktemp)
  git -C "$repo" ls-files > "$tracked"
  echo "dangling referents (backticked source/doc paths with no tracked file of that path or basename):"
  for f in "$mem"/*.md; do
    case "$f" in */MEMORY.md) continue ;; esac
    grep -o '`[^` ]*`' "$f" | tr -d '`' | grep -E '\.(cpp|h|md|ps1|gd|toml|cmake)$' | grep -v '[<*$]' | sort -u |
      while read -r t; do
        b=$(basename "$t")
        grep -qxF -- "$t" "$tracked" || grep -qF -- "/$b" "$tracked" || grep -qxF -- "$b" "$tracked" ||
          echo "  $(basename "$f" .md): $t"
      done
  done
  rm -f "$tracked"

  if [ -d "$repo/docs/retros" ]; then
    echo "never cited in a retro ledger since promotion (a review queue, not a delete list):"
    for f in "$mem"/*.md; do
      case "$f" in */MEMORY.md) continue ;; esac
      s=$(basename "$f" .md)
      if ! grep -lF "[[$s]]" "$repo"/docs/retros/*.md 2> /dev/null | xargs -r grep -LF "promoted to [[$s]]" | grep -q .; then
        echo "  $s"
      fi
    done
  fi
fi

[ "$status" = OVER ] && exit 1
exit 0
