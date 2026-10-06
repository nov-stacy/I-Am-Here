#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
APP="$PWD/build/IamHere.app"
mkdir -p "$APP/Contents/MacOS" "$PWD/build/module-cache"
for ARCH in arm64 x86_64; do
  xcrun swiftc Sources/main.swift -O -framework AppKit -framework CoreGraphics \
    -target "$ARCH-apple-macosx12.0" \
    -module-cache-path "$PWD/build/module-cache" -o "$PWD/build/IamHere-$ARCH"
done
xcrun lipo -create "$PWD/build/IamHere-arm64" "$PWD/build/IamHere-x86_64" \
  -output "$APP/Contents/MacOS/IamHere"
cp Info.plist "$APP/Contents/Info.plist"
codesign --force --sign - "$APP"
ditto -c -k --sequesterRsrc --keepParent "$APP" "$PWD/build/IamHere.zip"
printf 'Готово: %s\n' "$APP"
