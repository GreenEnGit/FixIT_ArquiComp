#!/usr/bin/env bash
# Genera static/tailwind.css (minificado) a partir de las clases usadas en las
# plantillas. Ejecutar despues de agregar o cambiar clases de Tailwind.
set -euo pipefail
cd "$(dirname "$0")/../.."
npx --yes tailwindcss@3.4.17 -c tailwind.config.js -i static/src/tailwind.input.css -o static/tailwind.css --minify
echo "[OK] static/tailwind.css generado ($(du -h static/tailwind.css | cut -f1))"
