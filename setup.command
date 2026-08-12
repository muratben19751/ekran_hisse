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
echo "[ 1/6 ] Python kontrol ediliyor..."
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

# ── 2. Kaynağı bundle'a senkronla ────────────────────────────────────────
# Launcher, kodu bundle'ın Contents/Resources kopyalarından çalıştırır. Kaynak
# tek yerdedir (proje kökü); güncellemelerin/güvenlik düzeltmelerinin çalışan
# koda yansıması için kopyaları HER kurulumda kaynaktan yenilemeliyiz. Aksi
# halde bundle kaynaktan geride kalır (drift) ve kullanıcı eski kodu çalıştırır.
echo ""
echo "[ 2/6 ] Uygulama dosyaları bundle'a senkronlanıyor..."
RES_DIR="$APP_PATH/Contents/Resources"
mkdir -p "$RES_DIR"
for f in main.py overlay.py logic.py data_fetcher.py config.py paths.py \
         notes_api_client.py twitter_client.py applog.py symbols.py symbols.json; do
    if [ -f "$PROJ_DIR/$f" ]; then
        cp "$PROJ_DIR/$f" "$RES_DIR/$f"
    fi
done
echo "  ✓ Bundle kaynakla senkron"

# ── 3. Bağımlılıklar ────────────────────────────────────────────────────
echo ""
echo "[ 3/6 ] Bağımlılıklar kuruluyor..."
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

# ── 4. Yapılandırma dosyası ──────────────────────────────────────────────
echo ""
echo "[ 4/6 ] Yapılandırma kontrol ediliyor..."
# Sırlar (GIST_ID, GITHUB_TOKEN, TWITTER_BEARER_TOKEN, TV_SESSION_ID) macOS
# Keychain'de güvenli tutulur. Düz metin dosya artık üretilmez.
#
# ÖNEMLİ: config sabitleri uygulama import edilirken BİR KEZ okunur (snapshot);
# uygulama sırlar eklenmeden başlatılırsa, sonradan Keychain'e sır eklense bile
# süreç yeniden başlatılana kadar görülmez. Bu yüzden sır yoksa uygulamayı
# OTOMATİK başlatmayız — kullanıcı sırları ekledikten sonra başlatırız.
KC_SERVICE="ekranhisse"
if security find-generic-password -s "$KC_SERVICE" -a GITHUB_TOKEN -w >/dev/null 2>&1; then
    echo "  ✓ Sırlar Keychain'de mevcut ($KC_SERVICE)"
else
    echo "  ⚠  Sırlar Keychain'de bulunamadı. Notlar/Twitter/RSI özellikleri için"
    echo "     aşağıdaki komutları ŞİMDİ (başka bir Terminal sekmesinde) çalıştırın:"
    echo "       security add-generic-password -U -s $KC_SERVICE -a GIST_ID -w '<gist-id>'"
    echo "       security add-generic-password -U -s $KC_SERVICE -a GITHUB_TOKEN -w '<ghp_token>'"
    echo "       security add-generic-password -U -s $KC_SERVICE -a TWITTER_BEARER_TOKEN -w '<bearer>'"
    echo "       security add-generic-password -U -s $KC_SERVICE -a TV_SESSION_ID -w '<tv-session>'"
    echo ""
    echo "     Sırları eklemeden devam ederseniz uygulama sırsız (yalnızca fiyat)"
    echo "     başlar; sır eklemek için sonradan uygulamayı yeniden başlatmanız gerekir."
    read -p "  Sırları ekledikten sonra Enter'a basın (veya sırsız devam için de Enter)... "
    # Yeniden kontrol et: kullanıcı bu arada eklediyse otomatik başlatmayı sürdür.
    if security find-generic-password -s "$KC_SERVICE" -a GITHUB_TOKEN -w >/dev/null 2>&1; then
        echo "  ✓ Sırlar artık Keychain'de mevcut"
    else
        echo "  ⚠  Sırlar hâlâ yok — uygulama sırsız başlatılacak (fiyat çalışır)."
    fi
fi

# ── 5. Login'de otomatik başlatma ───────────────────────────────────────
echo ""
echo "[ 5/6 ] Login'de otomatik başlatma ayarlanıyor..."

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

# ── 6. Uygulamayı başlat ────────────────────────────────────────────────
echo ""
echo "[ 6/6 ] Uygulama başlatılıyor..."

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
