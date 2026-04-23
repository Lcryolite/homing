# Packaging

## AppImage (Recommended)

Requires: `python3`, `pip`, `appimagetool`

```bash
cd packaging/appimage
./build.sh
```

Output: `build/appimage/OpenEmail-<version>-<commit>-x86_64.AppImage`

## Flatpak (Planned)

Manifest and build instructions will be added in a future release.

## Manual Install

```bash
pip install -e .
cp openemail.desktop ~/.local/share/applications/
```
