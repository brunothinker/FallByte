#!/usr/bin/env bash

set -e

APP_NAME="fallbyte"
VERSION="1.0.0"
ARCH="x86_64"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

PYINSTALLER_DIR="$PROJECT_ROOT/build/pyinstaller"
RPM_STAGE_DIR="$PROJECT_ROOT/build/rpm/tree"
FINAL_RPM="$PROJECT_ROOT/build/${APP_NAME}_${VERSION}_${ARCH}.rpm"

ICON_SRC="$PROJECT_ROOT/resources/icons/fallbyte_icon.png"
SPEC_FILE="$PROJECT_ROOT/packaging/rpm/fallbyte.spec"

echo "=== [RPM] Criando pacote RPM para ${APP_NAME} ==="

if [ ! -d "$PYINSTALLER_DIR" ]; then
    echo "Erro: Pasta $PYINSTALLER_DIR não encontrada. Execute o PyInstaller primeiro."
    exit 1
fi

if ! command -v rpmbuild &> /dev/null; then
    sudo apt update && sudo apt install -y rpm
fi

# 1. Prepara ambiente temporário do rpmbuild
rm -rf "$RPM_STAGE_DIR"
mkdir -p "$RPM_STAGE_DIR"/{BUILD,RPMS,SOURCES,SPECS,SRPMS}

# 2. Copia arquivos de entrada
cp -r "$PYINSTALLER_DIR" "$RPM_STAGE_DIR/SOURCES/FallByte"
cp "$ICON_SRC" "$RPM_STAGE_DIR/SOURCES/fallbyte_icon.png"
cp "$SPEC_FILE" "$RPM_STAGE_DIR/SPECS/"

# 3. Compila o pacote RPM
rpmbuild --define "_topdir $RPM_STAGE_DIR" -bb "$RPM_STAGE_DIR/SPECS/fallbyte.spec"

# 4. Move o RPM gerado para a raiz do build com o nome padronizado
GENERATED_RPM=$(find "$RPM_STAGE_DIR/RPMS/$ARCH" -type f -name "*.rpm" | head -n 1)
mv "$GENERATED_RPM" "$FINAL_RPM"

echo "Pacote RPM gerado em: $FINAL_RPM"