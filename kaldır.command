#!/bin/bash
# EkranHisse Kaldır
PLIST="$HOME/Library/LaunchAgents/com.local.ekranhisse.plist"

clear
echo "╔══════════════════════════════════════╗"
echo "║       EkranHisse Kaldırılıyor        ║"
echo "╚══════════════════════════════════════╝"
echo ""

pkill -f "ekran_hisse.*main.py" 2>/dev/null && echo "  ✓ Uygulama durduruldu" || echo "  — Uygulama zaten çalışmıyordu"

if [ -f "$PLIST" ]; then
    launchctl unload "$PLIST" 2>/dev/null || true
    rm "$PLIST"
    echo "  ✓ Otomatik başlatma kaldırıldı"
else
    echo "  — Otomatik başlatma zaten kurulu değildi"
fi

echo ""
echo "  EkranHisse kaldırıldı."
echo "  (Proje dosyaları silinmedi — manuel olarak silebilirsin)"
echo ""
read -p "  Kapatmak için Enter'a basın..."
