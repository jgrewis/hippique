#!/usr/bin/env bash
# Persist data/ between GitHub Actions runs as assets of a "data" release.
# Keeping the binary database out of Git history avoids an ever-growing repo.
#
#   scripts/data_store.sh restore         # download the latest database and model
#   scripts/data_store.sh save            # upload them back
#   scripts/data_store.sh backup [keep]   # add a dated snapshot, keep the N most recent (default 6)
# Requires the gh CLI and GH_TOKEN.
set -euo pipefail
cd "$(dirname "$0")/.."

TAG=data
FILES=(turf.db.gz model.json backtest.json)

ensure_release() {
  gh release view "$TAG" >/dev/null 2>&1 || gh release create "$TAG" \
    --title "Données" --notes "Base SQLite et modèle, mis à jour automatiquement. Ne pas supprimer." --latest=false
}

case "${1:-}" in
  restore)
    mkdir -p data
    if gh release view "$TAG" >/dev/null 2>&1; then
      for f in "${FILES[@]}"; do
        gh release download "$TAG" --pattern "$f" --dir data --clobber 2>/dev/null || echo "Absent : $f"
      done
      if [ -f data/turf.db.gz ]; then gunzip -f data/turf.db.gz; fi
    else
      echo "Aucune donnée publiée : démarrage avec une base vide."
    fi
    ;;
  save)
    ensure_release
    gzip -kf9 data/turf.db
    uploads=(data/turf.db.gz)
    [ -f data/model.json ] && uploads+=(data/model.json)
    [ -f data/backtest.json ] && uploads+=(data/backtest.json)
    gh release upload "$TAG" "${uploads[@]}" --clobber
    ;;
  backup)
    ensure_release
    keep="${2:-6}"
    snapshot="data/turf-$(date -u +%Y-%m-%d).db.gz"
    gzip -c9 data/turf.db > "$snapshot"
    gh release upload "$TAG" "$snapshot" --clobber
    gh release view "$TAG" --json assets -q '.assets[].name' \
      | grep -E '^turf-[0-9]{4}-[0-9]{2}-[0-9]{2}\.db\.gz$' | sort -r | tail -n +"$((keep + 1))" \
      | while read -r old; do gh release delete-asset "$TAG" "$old" -y; done
    ;;
  *)
    echo "Usage: $0 restore|save|backup [keep]" >&2
    exit 2
    ;;
esac
