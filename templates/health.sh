#!/bin/bash
# Health-check del proyecto. Personalizar por proyecto tras /dev-harness:init.
# Contrato: exit 0 = proyecto sano; exit != 0 = roto (stdout/stderr explica qué).
# Debe terminar en < 60 segundos. Ejemplos a descomentar según el stack:

# flutter analyze --no-fatal-infos || exit 1
# flutter test || exit 1
# npm test || exit 1

echo "health.sh sin personalizar: agregar chequeos de build/tests del proyecto"
exit 0
