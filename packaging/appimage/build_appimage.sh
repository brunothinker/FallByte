#!/usr/bin/env bash

set -e

APP_NAME="fallbyte"
APP_TITLE="FallByte"
VERSION="1.0.0"
ARCH="x86_64"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

PYINSTALLER_DIR="$PROJECT_ROOT/build/pyinstaller/FallByte"
APPDIR="$PROJECT_ROOT/build/appimage/FallByte.AppDir"
FINAL_APPIMAGE="$PROJECT_ROOT/build/${APP_NAME}_${VERSION}_${ARCH}.AppImage"

ICON_SRC="$PROJECT_ROOT/resources/icons/fallbyte_icon.png"

echo "=== [AppImage] Criando arquivo executável portátil para ${APP_TITLE} ==="

if [ ! -d "$PYINSTALLER_DIR" ]; then
    echo "Erro: Pasta $PYINSTALLER_DIR não encontrada. Execute o PyInstaller primeiro."
    exit 1
fi

# 1. Obter appimagetool confiável
APPIMAGETOOL="$PROJECT_ROOT/build/appimagetool"
if ! command -v appimagetool &> /dev/null; then
    if [ -f "$APPIMAGETOOL" ] && [ $(stat -c%s "$APPIMAGETOOL") -lt 1000000 ]; then
        rm -f "$APPIMAGETOOL"
    fi

    if [ ! -f "$APPIMAGETOOL" ]; then
        echo "[1/4] Baixando appimagetool..."
        APPIMAGETOOL_URL="https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage"
        curl -sL "$APPIMAGETOOL_URL" -o "$APPIMAGETOOL"
        chmod +x "$APPIMAGETOOL"
    fi
else
    APPIMAGETOOL="appimagetool"
fi

# 2. Prepara o diretório de staging (AppDir)
echo "[2/4] Montando a estrutura AppDir em build/appimage/..."
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin"
mkdir -p "$APPDIR/usr/share/icons/hicolor/256x256/apps"

# Copia os binários do PyInstaller
cp -r "$PYINSTALLER_DIR"/* "$APPDIR/usr/bin/"

# Copia os ícones
cp "$ICON_SRC" "$APPDIR/fallbyte.png"
cp "$ICON_SRC" "$APPDIR/.DirIcon"
cp "$ICON_SRC" "$APPDIR/usr/share/icons/hicolor/256x256/apps/fallbyte.png"

# 3. Cria o arquivo .desktop e AppRun
echo "[3/4] Gerando arquivos de entrada AppRun e .desktop..."
cat <<EOF > "$APPDIR/fallbyte.desktop"
[Desktop Entry]
Name=${APP_TITLE}
Comment=Ferramenta de conversão e compressão de mídias
Exec=FallByte
Icon=fallbyte
Terminal=false
Type=Application
Categories=Utility;AudioVideo;Video;Graphics;
EOF

cat <<'EOF' > "$APPDIR/AppRun"
#!/bin/sh
HERE="$(dirname "$(readlink -f "${0}")")"
export PATH="${HERE}/usr/bin:${PATH}"
export LD_LIBRARY_PATH="${HERE}/usr/bin:_internal:${LD_LIBRARY_PATH}"
exec "${HERE}/usr/bin/FallByte" "$@"
EOF

chmod +x "$APPDIR/AppRun"

# 4. Empacota em .AppImage (com APPIMAGE_EXTRACT_AND_RUN=1 para dispensar FUSE)
echo "[4/4] Empacotando em .AppImage..."
ARCH=x86_64 APPIMAGE_EXTRACT_AND_RUN=1 "$APPIMAGETOOL" "$APPDIR" "$FINAL_APPIMAGE"

echo ""
echo "=================================================================="
echo " AppImage gerado com sucesso!"
echo " Arquivo: $FINAL_APPIMAGE"
echo "=================================================================="