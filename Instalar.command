#!/usr/bin/env bash
# Instalador de Budget Tracker para macOS.
# Se puede ejecutar con doble clic desde Finder, o desde Terminal.
# Es seguro ejecutarlo varias veces: si un paso ya está hecho, lo salta.
set -u

# --- Ubicarnos en la carpeta del proyecto, sin importar desde dónde se abrió ---
SOURCE="${BASH_SOURCE[0]}"
while [ -L "$SOURCE" ]; do
  TARGET="$(readlink "$SOURCE")"
  if [[ "$TARGET" = /* ]]; then SOURCE="$TARGET"; else SOURCE="$(dirname "$SOURCE")/$TARGET"; fi
done
DIR="$(cd "$(dirname "$SOURCE")" && pwd)"
cd "$DIR"

ok()   { echo "✓ $1"; }
info() { echo "→ $1"; }
err()  { echo "✗ $1"; }

echo "========================================"
echo " Budget Tracker - Instalador"
echo "========================================"
echo ""

# --- Solo macOS ---
if [[ "$(uname -s)" != "Darwin" ]]; then
  err "Esta app solo está preparada para Mac. Si estás en Windows, avísale a quien te la compartió."
  echo ""
  read -n 1 -s -r -p "Presiona cualquier tecla para cerrar..."
  exit 1
fi

# --- Quitar la marca de "descargado de internet" ---
# macOS marca todo lo que baja de internet (zip, AirDrop) y bloquea doble clic
# en los .command. Como este script ya está corriendo, limpiamos la carpeta
# para que Abrir.command y el resto funcionen sin avisos. No requiere sudo.
xattr -dr com.apple.quarantine "$DIR" 2>/dev/null || true
chmod +x "$DIR/Abrir.command" "$DIR/finance-app" 2>/dev/null || true

# --- uv (instala Python por nosotros; sin Homebrew, sin Xcode, sin sudo) ---
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
if ! command -v uv >/dev/null 2>&1; then
  info "Instalando 'uv' (un instalador de Python liviano, no necesita contraseña ni Xcode)..."
  if ! curl -LsSf https://astral.sh/uv/install.sh | sh; then
    err "No se pudo descargar uv. Revisa tu conexión a internet y vuelve a intentar."
    read -n 1 -s -r -p "Presiona cualquier tecla para cerrar..."
    exit 1
  fi
  export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
  if ! command -v uv >/dev/null 2>&1; then
    err "uv no quedó instalado correctamente. Avísale a quien te compartió la app."
    read -n 1 -s -r -p "Presiona cualquier tecla para cerrar..."
    exit 1
  fi
else
  ok "uv ya está instalado."
fi

# --- Entorno virtual (Python 3.13 descargado por uv) + dependencias ---
if [[ ! -x "venv/bin/python" ]]; then
  info "Creando el entorno de la app (descarga Python la primera vez)..."
  if ! uv venv --python 3.13 venv; then
    err "No se pudo crear el entorno. Avísale a quien te compartió la app."
    read -n 1 -s -r -p "Presiona cualquier tecla para cerrar..."
    exit 1
  fi
  ok "Entorno creado."
fi

info "Instalando los componentes necesarios (esto puede tardar un par de minutos)..."
if ! uv pip install -q --python venv/bin/python -r requirements.txt; then
  err "Falló la instalación de componentes. Avísale a quien te compartió la app."
  read -n 1 -s -r -p "Presiona cualquier tecla para cerrar..."
  exit 1
fi
ok "Componentes instalados."
echo ""

# --- credentials.json (lo único que cada persona debe hacer por su cuenta) ---
# Si bajaste el archivo de Google con su nombre original (client_secret_....json)
# y lo pusiste en esta carpeta, lo renombra a credentials.json automáticamente.
venv/bin/python -c "from backend.gmail_client import adopt_credentials; adopt_credentials()" 2>/dev/null
if [[ ! -f "credentials.json" ]]; then
  echo "========================================"
  err "Falta el archivo credentials.json"
  echo "========================================"
  echo ""
  echo "Este es el único paso que tienes que hacer tú mismo/a:"
  echo "crear tu propio proyecto de Google Cloud para que la app"
  echo "pueda leer tus correos del banco desde TU Gmail."
  echo ""
  echo "Sigue la sección 'Configura tu proyecto de Google' de la"
  echo "GUIA_DE_USO.md que viene junto a este archivo."
  echo ""
  echo "Cuando tengas el archivo que descargaste de Google (.json), colócalo"
  echo "en esta misma carpeta (junto a este instalador, no importa su"
  echo "nombre) y vuelve a hacer"
  echo "doble clic en Instalar.command para terminar."
  echo ""
  read -n 1 -s -r -p "Presiona cualquier tecla para cerrar..."
  exit 0
fi
ok "credentials.json encontrado."
echo ""

# --- Comando 'finance-app' (opcional, para quien use Terminal) ---
BIN_DIR="$HOME/.local/bin"
mkdir -p "$BIN_DIR"
ln -sf "$DIR/finance-app" "$BIN_DIR/finance-app"
if ! grep -qs '\.local/bin' "$HOME/.zprofile" 2>/dev/null; then
  echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.zprofile"
fi
ok "Comando 'finance-app' instalado (disponible en Terminales nuevas)."

# --- Acceso directo en el Escritorio (para abrir la app con doble clic) ---
LAUNCHER="$HOME/Desktop/Budget Tracker.command"
if printf '#!/usr/bin/env bash\nexec "%s/Abrir.command"\n' "$DIR" > "$LAUNCHER" 2>/dev/null; then
  chmod +x "$LAUNCHER"
  ok "Acceso directo creado en el Escritorio: 'Budget Tracker'."
else
  info "No se pudo crear el acceso directo en el Escritorio; usa Abrir.command en la carpeta de la app."
fi
echo ""

# --- Categorías + correos de BAC/Promerica (automático, sin preguntas) ---
echo "========================================"
echo " Configuración inicial"
echo "========================================"
echo ""
venv/bin/python backend/init_db.py --seed-only
echo ""

# --- Abrir el panel para que agregues tus tarjetas desde ahí ---
info "Abriendo el panel de la app en tu navegador..."
"$DIR/venv/bin/python" "$DIR/backend/manage.py" open

echo ""
echo "========================================"
ok "¡Instalación lista!"
echo "========================================"
echo ""
echo "Te falta un último paso, pero ya lo haces ahí mismo en el navegador,"
echo "sin usar más la Terminal:"
echo ""
echo "  1. En la pestaña 'Cards', agrega cada una de tus tarjetas"
echo "     (+ Add Card)."
echo "  2. ¿Bancos distintos a BAC/Promerica? Agrégalos en 'Settings' ->"
echo "     '+ Add Email Source' (BAC y Promerica ya quedaron listos)."
echo "  3. Clic en 'Sync Now' (está en la pestaña 'Settings') para traer"
echo "     tus transacciones de Gmail por primera vez."
echo ""
echo "La próxima vez, abre la app con doble clic en 'Budget Tracker'"
echo "(en tu Escritorio) o en Abrir.command. No necesitas la Terminal."
echo ""
echo "Revisa la GUIA_DE_USO.md para el detalle de cada paso."
echo ""
read -n 1 -s -r -p "Presiona cualquier tecla para cerrar..."
