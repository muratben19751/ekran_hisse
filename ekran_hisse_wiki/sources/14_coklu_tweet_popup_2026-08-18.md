---
source: oturum notu
retrieved: 2026-08-18
type: session_note
immutable: true
---

# Çoklu Monitör Sheet Konumlandırması & Çoklu Tweet Pop-up Kartları — 2026-08-18

## Ne değişti

### 1. Çoklu Monitör Sheet Konumlandırması (`_SheetDialog._place`)
- `TargetSheet`, `StockPickerSheet` ve `TextSheet` pencerelerinin ikincil ekranlara taşındığında ana pencereden ayrışması engellendi.
- `parent.screen()` ve `QApplication.primaryScreen()` ekran algılaması eklenerek aktif ekran sınırları içinde (`availableGeometry`) yerleşim sağlandı.
- `_main_screen()` null guard'ı eklendi.

### 2. Bağımsız Kayan Pop-up Kartları (`TweetPopupCard`)
- Eski pencere içi gömülü toast (`_show_tweet_toast`) yerine, ekran üzerinde bağımsız yüzen `Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint` tabanlı `TweetPopupCard` geliştirildi.
- `showEvent` içinde macOS Cocoa seviyesi `level=1003` ve `_COLLECTION_BEHAVIOR` atanarak tüm masaüstlerinde ve tam ekran uygulamalarda en üstte kalması sağlandı.
- Otomatik zamanlayıcı kaldırıldı; kartlar kullanıcı kapatana (`✕`) veya tıklayana kadar ekranda kalıcı oldu.
- Tıklanıldığında EkranHisse ana penceresini öne getirip 𝕏 sekmesini açar.

### 3. Çoklu Tweet Yığın Yöneticisi (`TweetPopupManager`)
- Birden fazla tweet geldiğinde ekranın sağ üstünden başlayarak (`start_x`, `current_y`) kartlar alt alta dizilir (`(1/3)`, `(2/3)`, `(3/3)` vb.).
- `_on_card_closed` ve `reposition_cards()`: Kullanıcı üstteki veya aradaki herhangi bir kartı kapattığında, altındaki tüm kartlar yukarı kayarak boşalan yere yerleşir.

### 4. macOS Notification Center & Test Butonu
- `_send_macos_notification("EkranHisse — 𝕏 Akışı", msg)` ile macOS Bildirim Merkezi'ne eşzamanlı sistem banner'ı gönderimi sağlandı.
- 𝕏 sekmesi başlığına `🔔 test` butonu eklendi (tıklanınca 3 örnek kartı alt alta açar ve yukarı kayma testini sunar).
- `ui_notify.json` ile bildirim tercihi kalıcı hale getirildi.

### 5. Kalite & Testler
- Sıfır lint hatası (`ruff check .` All checks passed).
- 301 testin tamamı başarıyla geçti (`pytest tests/`).
