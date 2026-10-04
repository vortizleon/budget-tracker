#!/usr/bin/env bash
# Abre Budget Tracker (doble clic). No necesita la Terminal ni el comando finance-app.
# Inicia el servidor si no está corriendo y abre el panel en tu navegador.
set -u

SOURCE="${BASH_SOURCE[0]}"
while [ -L "$SOURCE" ]; do
  TARGET="$(readlink "$SOURCE")"
  if [[ "$TARGET" = /* ]]; then SOURCE="$TARGET"; else SOURCE="$(dirname "$SOURCE")/$TARGET"; fi
done
DIR="$(cd "$(dirname "$SOURCE")" && pwd)"
cd "$DIR"

if [[ ! -x "venv/bin/python" ]]; then
  echo "✗ La app todavía no está instalada. Haz doble clic en Instalar.command primero."
  read -n 1 -s -r -p "Presiona cualquier tecla para cerrar..."
  exit 1
fi

venv/bin/python backend/manage.py open
echo ""
echo "Listo. Puedes cerrar esta ventana; la app sigue corriendo en segundo plano."
exit 0
