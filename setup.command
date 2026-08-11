#!/bin/bash
# EkranHisse Kurulum Sihirbazı
# Çift tıkla çalıştır — başka bir şey yapman gerekmez.

PROJ_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_PATH="$PROJ_DIR/EkranHisse.app"
PLIST="$HOME/Library/LaunchAgents/com.local.ekranhisse.plist"
LOG="$HOME/Library/Logs/EkranHisse.log"

# İnternetten/zip'ten inen dosyalara macOS "quarantine" bayrağı yapıştırır ve
# "geliştirici doğrulanamadı" hatası verir. Tüm pakete uygulanan bayrağı kaldır.
xattr -dr com.apple.quarantine "$PROJ_DIR" 2>/dev/null || true

clear
echo "╔══════════════════════════════════════╗"
echo "║       EkranHisse Kurulum             ║"
echo "║   BIST Hisse Overlay — macOS         ║"
echo "╚══════════════════════════════════════╝"
echo ""

# ── 1. Python kontrolü ──────────────────────────────────────────────────
echo "[ 1/4 ] Python kontrol ediliyor..."
if ! command -v python3 &>/dev/null; then
# ── 1. Python kontrolü ──────────────────────────────────────────────────
echo "[ 1/4 ] Python kontrol ediliyor..."
# Launcher (EkranHisse.app) özellikle /usr/bin/python3 ile başlatır; bağımlılıkları
# DA aynı yorumlayıcıya kurmalıyız yoksa "No module named 'PySide6'" alınır.
PY="/usr/bin/python3"
if [ ! -x "$PY" ]; then
    PY="$(command -v python3)"
fi
if [ -z "$PY" ]; then
    echo "  ✗ python3 bulunamadı."
    echo "    https://www.python.org adresinden Python 3 kurun."
    read -p "  Çıkmak için Enter'a basın..."
    exit 1
fi
PY_VER=$("$PY" --version 2>&1)
echo "  ✓ $PY_VER  ($PY)"

# ── 2. Bağımlılıklar ────────────────────────────────────────────────────
echo ""
echo "[ 2/5 ] Bağımlılıklar kuruluyor..."
echo "  (PySide6, yfinance, websocket-client, requests, pyobjc — ilk kurulumda birkaç dakika sürebilir)"
echo ""

"$PY" -m pip install -q --upgrade pip 2>/dev/null
"$PY" -m pip install -q --user -r "$PROJ_DIR/requirements.txt"

if [ $? -ne 0 ]; then
    echo "  ✗ Bağımlılık kurulumu başarısız."
    read -p "  Çıkmak için Enter'a basın..."
    exit 1
fi
echo "  ✓ Tüm bağımlılıklar kuruldu"

# ── 3. Yapılandırma dosyası ──────────────────────────────────────────────
echo ""
echo "[ 3/5 ] Yapılandırma kontrol ediliyor..."
CFG_DIR="$HOME/.ekranhisse"
CFG_FILE="$CFG_DIR/notes_config.env"
LOCAL_CFG="$PROJ_DIR/notes_config.env"

mkdir -p "$CFG_DIR"
if [ ! -f "$CFG_FILE" ]; then
    if [ -f "$LOCAL_CFG" ]; then
        cp "$LOCAL_CFG" "$CFG_FILE"
        echo "  ✓ notes_config.env → $CFG_FILE konumuna kopyalandı"
    else
        echo "  ⚠  notes_config.env bulunamadı."
        echo "     GIST_ID, GITHUB_TOKEN vb. değerlerinizi şuraya ekleyin:"
        echo "     $CFG_FILE"
        cat > "$CFG_FILE" << 'ENVEOF'
GIST_ID=
GITHUB_TOKEN=
TWITTER_BEARER_TOKEN=
TV_SESSION_ID=
ENVEOF
    fi
else
    echo "  ✓ Yapılandırma zaten mevcut: $CFG_FILE"
fi

# ── 4. Login'de otomatik başlatma ───────────────────────────────────────
echo ""
echo "[ 4/5 ] Login'de otomatik başlatma ayarlanıyor..."

mkdir -p "$HOME/Library/LaunchAgents"
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
launchctl load "$PLIST" 2>/dev/null || true
echo "  ✓ Her oturum açılışında otomatik başlayacak"

# ── 5. Uygulamayı başlat ────────────────────────────────────────────────
echo ""
echo "[ 5/5 ] Uygulama başlatılıyor..."

pkill -f "ekran_hisse.*main.py" 2>/dev/null || true
sleep 1
open "$APP_PATH"
sleep 5

if pgrep -f "main.py" > /dev/null; then
    echo "  ✓ EkranHisse çalışıyor"
else
    echo "  ✗ Uygulama başlatılamadı."
    echo "    Log: $LOG"
    cat "$LOG" 2>/dev/null | tail -5
fi

# ── Tamamlandı ──────────────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════╗"
echo "║         Kurulum Tamamlandı ✓         ║"
echo "╚══════════════════════════════════════╝"
echo ""
echo "  Ekranın sağ kenarında ◧ (portföy) sekmesi görünüyor olmalı."
echo "  Tıklayınca panel açılır, + ile hisse ekleyebilirsin."
echo ""
echo "  Kaldırmak için: kaldır.command dosyasını çalıştır."
echo ""
read -p "  Kapatmak için Enter'a basın..."
