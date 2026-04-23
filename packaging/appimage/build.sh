#!/usr/bin/env bash
# Build OpenEmail AppImage
# Requires: python3, pip, appimagetool (from https://github.com/AppImage/AppImageKit)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
BUILD_DIR="${PROJECT_ROOT}/build/appimage"
APPDIR="${BUILD_DIR}/AppDir"

VERSION="$(python3 -c "import sys; sys.path.insert(0, '${PROJECT_ROOT}/src'); import openemail; print(openemail.__version__)")"
COMMIT="$(git -C "${PROJECT_ROOT}" rev-parse --short HEAD 2>/dev/null || echo 'unknown')"

APPIMAGE_NAME="OpenEmail-${VERSION}-${COMMIT}-x86_64.AppImage"

echo "Building OpenEmail AppImage v${VERSION} (commit ${COMMIT})..."

# Clean and create AppDir
rm -rf "${APPDIR}"
mkdir -p "${APPDIR}/usr/share/openemail"

# Copy source
cp -r "${PROJECT_ROOT}/src/openemail" "${APPDIR}/usr/share/openemail/"
cp "${PROJECT_ROOT}/openemail.desktop" "${APPDIR}/"
cp "${PROJECT_ROOT}/README.md" "${APPDIR}/usr/share/openemail/"

# Install dependencies into AppDir
cp -r "${PROJECT_ROOT}/.venv" "${APPDIR}/usr/share/openemail/.venv" 2>/dev/null || true

# Create AppRun
cat > "${APPDIR}/AppRun" << 'EOF'
#!/bin/sh
SELF=$(readlink -f "$0")
HERE=${SELF%/*}
export PATH="${HERE}/usr/bin:${PATH}"
export PYTHONPATH="${HERE}/usr/share/openemail:${PYTHONPATH}"
exec python3 "${HERE}/usr/share/openemail/openemail/main.py" "$@"
EOF
chmod +x "${APPDIR}/AppRun"

# Symlink desktop file
ln -sf "${APPDIR}/openemail.desktop" "${APPDIR}/usr/share/applications/openemail.desktop"

# Check for appimagetool
if command -v appimagetool >/dev/null 2>&1; then
    appimagetool "${APPDIR}" "${BUILD_DIR}/${APPIMAGE_NAME}"
    echo "AppImage built: ${BUILD_DIR}/${APPIMAGE_NAME}"
elif [ -f "${SCRIPT_DIR}/appimagetool-x86_64.AppImage" ]; then
    "${SCRIPT_DIR}/appimagetool-x86_64.AppImage" "${APPDIR}" "${BUILD_DIR}/${APPIMAGE_NAME}"
    echo "AppImage built: ${BUILD_DIR}/${APPIMAGE_NAME}"
else
    echo "WARNING: appimagetool not found. AppDir created at ${APPDIR}"
    echo "Download appimagetool from: https://github.com/AppImage/AppImageKit/releases"
    exit 1
fi
