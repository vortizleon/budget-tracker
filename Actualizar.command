#!/usr/bin/env bash
# Actualiza Budget Tracker a la última versión (doble clic, o `finance-app update`).
# Baja el proyecto de GitHub con el mismo curl de la instalación y copia el código
# nuevo encima. NO toca tus datos: credentials.json, token.json, la base de datos
# (*.db), .env ni el entorno (venv). Antes de actualizar guarda una copia de la
# base de datos en la carpeta backups/.
set -u

SOURCE="${BASH_SOURCE[0]}"
while [ -L "$SOURCE" ]; do
  TARGET="$(readlink "$SOURCE")"
  if [[ "$TARGET" = /* ]]; then SOURCE="$TARGET"; else SOURCE="$(dirname "$SOURCE")/$TARGET"; fi
done
DIR="$(cd "$(dirname "$SOURCE")" && pwd)"
cd "$DIR"

URL="${BUDGET_TRACKER_URL:-https://github.com/vortizleon/budget-tracker/archive/refs/heads/main.tar.gz}"

ok()   { echo "✓ $1"; }
info() { echo "→ $1"; }
err()  { echo "✗ $1"; }
pause() { [[ -t 0 ]] && read -n 1 -s -r -p "Presiona cualquier tecla para cerrar..."; echo ""; }

echo "========================================"
echo " Budget Tracker - Actualizar"
echo "========================================"
echo ""

if [[ ! -x "venv/bin/python" ]]; then
  err "La app todavía no está instalada. Haz doble clic en Instalar.command primero."
  pause
  exit 1
fi

export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
if ! command -v uv >/dev/null 2>&1; then
  err "No se encontró 'uv'. Haz doble clic en Instalar.command (es seguro repetirlo) y vuelve a intentar."
  pause
  exit 1
fi

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# --- Descargar la versión nueva ---
info "Descargando la última versión..."
if ! curl -fsSL "$URL" | tar -xz -C "$TMP"; then
  err "No se pudo descargar. Revisa tu conexión a internet y vuelve a intentar. No se cambió nada."
  pause
  exit 1
fi
NEW="$(find "$TMP" -mindepth 1 -maxdepth 1 -type d | head -n 1)"
if [[ -z "$NEW" || ! -f "$NEW/requirements.txt" ]]; then
  err "La descarga no se ve como Budget Tracker. No se cambió nada."
  pause
  exit 1
fi

# --- Copia de seguridad de la base de datos ---
if ls ./*.db >/dev/null 2>&1; then
  mkdir -p backups
  STAMP="$(date +%Y%m%d-%H%M%S)"
  for db in ./*.db; do
    cp "$db" "backups/$(basename "${db%.db}")-$STAMP.db"
  done
  ok "Copia de seguridad de tu base de datos en backups/ (se guardan las últimas 5)."
  i=0
  for f in $(ls -t backups/*.db 2>/dev/null); do
    i=$((i + 1))
    [[ $i -gt 5 ]] && rm -f "$f"
  done
fi

# --- Copiar el código nuevo (sin tocar tus datos) ---
info "Actualizando archivos..."
if ! rsync -a \
  --exclude 'venv/' \
  --exclude 'backups/' \
  --exclude '.git/' \
  --exclude '__pycache__/' \
  --exclude 'credentials.json' \
  --exclude 'client_secret*.json' \
  --exclude 'token.json*' \
  --exclude '*.db' \
  --exclude '.env' \
  --exclude '.server.log' \
  "$NEW/" "$DIR/"; then
  err "Falló la copia de archivos. Tus datos no se tocaron."
  pause
  exit 1
fi
chmod +x "$DIR"/*.command "$DIR/finance-app" 2>/dev/null || true
ok "Archivos actualizados."

# --- Componentes (por si la versión nueva trae alguno nuevo) ---
info "Revisando componentes..."
if ! uv pip install -q --python venv/bin/python -r requirements.txt; then
  err "Falló la instalación de componentes. Intenta de nuevo; si sigue igual, avísale a quien te compartió la app."
  pause
  exit 1
fi
ok "Componentes al día."

# --- Reiniciar la app si estaba abierta (así carga el código nuevo y migra la base) ---
if lsof -ti :8000 >/dev/null 2>&1; then
  info "Reiniciando la app para cargar la versión nueva..."
  venv/bin/python backend/manage.py restart
fi

echo ""
echo "========================================"
ok "¡Listo! Budget Tracker está actualizado."
echo "========================================"
echo "Tus tarjetas, transacciones y credenciales siguen igual."
echo "Ábrela como siempre con Abrir.command."
echo ""
pause
