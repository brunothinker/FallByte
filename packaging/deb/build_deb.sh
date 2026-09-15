#!/usr/bin/env bash

set -e

APP_NAME="fallbyte"
APP_TITLE="FallByte"
VERSION="1.0.0"
ARCH="amd64"
MAINTAINER="Bruno Henrique <seu.email@exemplo.com>"
DESCRIPTION="Ferramenta de conversão e compressão de mídias (imagens e vídeos)."

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

PYINSTALLER_DIR="$PROJECT_ROOT/build/pyinstaller"
DEB_STAGE_DIR="$PROJECT_ROOT/build/deb/tree"
FINAL_DEB="$PROJECT_ROOT/build/${APP_NAME}_${VERSION}_${ARCH}.deb"

ICON_JPEG="$PROJECT_ROOT/resources/icons/fallbyte_icon.jpeg"
ICON_PNG="$PROJECT_ROOT/resources/icons/fallbyte_icon.png"

echo "=== [DEB] Criando pacote Debian para ${APP_TITLE} ==="

if [ ! -d "$PYINSTALLER_DIR" ]; then
    echo "Erro: Pasta $PYINSTALLER_DIR não encontrada. Execute o PyInstaller primeiro."
    exit 1
fi

# 1. Prepara ambiente temporário
rm -rf "$DEB_STAGE_DIR"
mkdir -p "$DEB_STAGE_DIR/DEBIAN"
mkdir -p "$DEB_STAGE_DIR/usr/bin"
mkdir -p "$DEB_STAGE_DIR/usr/share/applications"
mkdir -p "$DEB_STAGE_DIR/usr/share/icons/hicolor/256x256/apps"
mkdir -p "$DEB_STAGE_DIR/usr/share/$APP_NAME"

# 2. Processa ícone
if [ ! -f "$ICON_PNG" ] && [ -f "$ICON_JPEG" ]; then
    ffmpeg -y -i "$ICON_JPEG" "$ICON_PNG" >/dev/null 2>&1 || true
fi

if [ -f "$ICON_PNG" ]; then
    cp "$ICON_PNG" "$DEB_STAGE_DIR/usr/share/icons/hicolor/256x256/apps/${APP_NAME}.png"
fi

# 3. Copia binários do PyInstaller
cp -r "$PYINSTALLER_DIR/"* "$DEB_STAGE_DIR/usr/share/$APP_NAME/"

# 4. Gera .desktop e links
cat <<EOF > "$DEB_STAGE_DIR/usr/share/applications/${APP_NAME}.desktop"
[Desktop Entry]
Name=${APP_TITLE}
Comment=${DESCRIPTION}
Exec=/usr/bin/${APP_NAME}
Icon=${APP_NAME}
Terminal=false
Type=Application
Categories=Utility;AudioVideo;Video;Graphics;
EOF

ln -s "/usr/share/$APP_NAME/FallByte" "$DEB_STAGE_DIR/usr/bin/$APP_NAME"

# 5. Gera arquivo control
cat <<EOF > "$DEB_STAGE_DIR/DEBIAN/control"
Package: ${APP_NAME}
Version: ${VERSION}
Architecture: ${ARCH}
Maintainer: ${MAINTAINER}
Section: utils
Priority: optional
Description: ${DESCRIPTION}
 FallByte permite converter e comprimir arquivos de imagem e vídeo de forma
 rápida, integrando utilitários nativos e interface gráfica moderna.
EOF

chmod -R 755 "$DEB_STAGE_DIR"
chmod 755 "$DEB_STAGE_DIR/DEBIAN/control"

# 6. Compila o .deb final
dpkg-deb --root-owner-group --build "$DEB_STAGE_DIR" "$FINAL_DEB"

echo "Pacote DEB gerado em: $FINAL_DEB"