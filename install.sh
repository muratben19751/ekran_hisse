#!/bin/bash
set -e

# Script'in bulunduğu dizinden otomatik path hesapla
PROJ_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_PATH="$PROJ_DIR/EkranHisse.app"
LAUNCH_AGENTS="$HOME/Library/LaunchAgents"
PLIST="$LAUNCH_AGENTS/com.local.ekranhisse.plist"

echo "=== EkranHisse Kurulum ==="
echo "Proje dizini: $PROJ_DIR"

# Bağımlılıkları kur
echo "Bağımlılıklar kuruluyor..."
pip3 install -q PySide6 yfinance pyobjc-framework-Cocoa

mkdir -p "$LAUNCH_AGENTS"

cat > "$PLIST" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.local.ekranhisse</string>
    <key>ProgramArguments</key>
    <array>
        <string>open</string>
        <string>$APP_PATH</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <false/>
</dict>
</plist>
EOF

launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"

echo "✓ Kurulum tamamlandı"
echo "✓ Her login'de otomatik başlayacak"
echo ""
echo "Şimdi başlatmak için:"
echo "  open \"$APP_PATH\""
echo ""
echo "Kaldırmak için:"
echo "  launchctl unload \"$PLIST\" && rm \"$PLIST\""
