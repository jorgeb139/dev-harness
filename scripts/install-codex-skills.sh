#!/bin/bash
# Instala las skills de dev-harness para Codex mediante symlink idempotente.
# No requiere dependencias externas.
set -u

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TARGET_DIR="${HOME}/.agents/skills"
LINK="${TARGET_DIR}/dev-harness"

mkdir -p "$TARGET_DIR"

if [ -L "$LINK" ]; then
  current="$(readlink "$LINK")"
  if [ "$current" = "$ROOT/skills" ]; then
    echo "dev-harness ya esta enlazado en $LINK"
    exit 0
  fi
  echo "FAIL: $LINK ya apunta a $current" >&2
  echo "Eliminalo o renombralo antes de instalar dev-harness." >&2
  exit 1
fi

if [ -e "$LINK" ]; then
  echo "FAIL: $LINK ya existe y no es symlink" >&2
  echo "Eliminalo o renombralo antes de instalar dev-harness." >&2
  exit 1
fi

ln -s "$ROOT/skills" "$LINK"
echo "dev-harness enlazado en $LINK"
echo "Abre una tarea nueva en Codex para que descubra las skills."
