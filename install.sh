#!/bin/bash
set -e

# Script'in bulunduğu dizinden otomatik path hesapla
PROJ_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_PATH="$PROJ_DIR/EkranHisse.app"
LAUNCH_AGENTS="$HOME/Library/LaunchAgents"
PLIST="$LAUNCH_AGENTS/com.local.ekranhisse.plist"

echo "=== EkranHisse Kurulum ==="
echo "Proje dizini: $PROJ_DIR"

# ── Build: kaynak dosyaları .app bundle'ına kopyala ──────────────────────────
# Bundle'daki .py kopyaları build çıktısıdır (git'te tutulmaz). Kaynak tek
# yerde (proje kökü); kurulumda bundle'a senkronlanır ki iki kopya asla
# birbirinden ayrışmasın.
echo "Uygulama dosyaları bundle'a kopyalanıyor..."
RES_DIR="$APP_PATH/Contents/Resources"
mkdir -p "$RES_DIR"
for f in main.py overlay.py logic.py data_fetcher.py config.py paths.py \
         notes_api_client.py twitter_client.py applog.py symbols.py symbols.json; do
    cp "$PROJ_DIR/$f" "$RES_DIR/$f"
done

# Bağımlılıkları kur — launcher /usr/bin/python3 kullandığı için AYNI yorumlayıcıya kur
echo "Bağımlılıklar kuruluyor..."
PY="/usr/bin/python3"; [ -x "$PY" ] || PY="$(command -v python3)"
"$PY" -m pip install -q --user -r "$PROJ_DIR/requirements.txt"

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
