#!/bin/bash
set -e

APP_PATH="/Users/i034216/Documents/myAI_projects/ekran_hisse/EkranHisse.app"
LAUNCH_AGENTS="$HOME/Library/LaunchAgents"
PLIST="$LAUNCH_AGENTS/com.local.ekranhisse.plist"

echo "=== EkranHisse Kurulum ==="

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

echo "✓ Her login'de otomatik başlayacak"
echo ""
echo "Şimdi çift tıklayarak aç:"
echo "  $APP_PATH"
echo ""
echo "Kaldırmak için:"
echo "  launchctl unload $PLIST && rm $PLIST"
