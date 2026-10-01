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

# --- Homebrew ---
if ! command -v brew >/dev/null 2>&1; then
  info "No tienes Homebrew instalado (es el instalador de programas que vamos a usar). Instalándolo..."
  info "Te va a pedir tu contraseña de Mac - es normal, escríbela y da Enter (no se ve mientras escribes)."
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  if [[ -x /opt/homebrew/bin/brew ]]; then
    eval "$(/opt/homebrew/bin/brew shellenv)"
  elif [[ -x /usr/local/bin/brew ]]; then
    eval "$(/usr/local/bin/brew shellenv)"
  fi
  if ! command -v brew >/dev/null 2>&1; then
    err "Homebrew no quedó instalado correctamente. Cierra esta ventana, abre una Terminal nueva y vuelve a hacer doble clic en este archivo."
    read -n 1 -s -r -p "Presiona cualquier tecla para cerrar..."
    exit 1
  fi
else
  ok "Homebrew ya está instalado."
fi

# --- Python 3.13 ---
if ! brew list python@3.13 >/dev/null 2>&1; then
  info "Instalando Python 3.13..."
  brew install python@3.13
else
  ok "Python 3.13 ya está instalado."
fi
PYTHON_BIN="$(brew --prefix python@3.13)/bin/python3.13"
if [[ ! -x "$PYTHON_BIN" ]]; then
  err "No se encontró Python 3.13 después de instalarlo. Avísale a quien te compartió la app."
  read -n 1 -s -r -p "Presiona cualquier tecla para cerrar..."
  exit 1
fi

# --- Entorno virtual + dependencias ---
if [[ ! -d "venv" ]]; then
  info "Creando el entorno de la app..."
  "$PYTHON_BIN" -m venv venv
  ok "Entorno creado."
fi

info "Instalando los componentes necesarios (esto puede tardar un par de minutos)..."
venv/bin/pip install -q --upgrade pip
venv/bin/pip install -q -r requirements.txt
ok "Componentes instalados."
echo ""

# --- credentials.json (lo único que cada persona debe hacer por su cuenta) ---
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
  echo "Cuando tengas el archivo credentials.json, colócalo en esta"
  echo "misma carpeta (junto a este instalador) y vuelve a hacer"
  echo "doble clic en Instalar.command para terminar."
  echo ""
  read -n 1 -s -r -p "Presiona cualquier tecla para cerrar..."
  exit 0
fi
ok "credentials.json encontrado."
echo ""

# --- Symlink de finance-app al PATH ---
BREW_BIN="$(brew --prefix)/bin"
if [[ ! -L "$BREW_BIN/finance-app" || "$(readlink "$BREW_BIN/finance-app")" != "$DIR/finance-app" ]]; then
  chmod +x "$DIR/finance-app"
  ln -sf "$DIR/finance-app" "$BREW_BIN/finance-app"
  ok "Comando 'finance-app' instalado."
else
  ok "Comando 'finance-app' ya estaba instalado."
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
"$DIR/finance-app"

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
echo "Revisa la GUIA_DE_USO.md para el detalle de cada paso."
echo ""
read -n 1 -s -r -p "Presiona cualquier tecla para cerrar..."
