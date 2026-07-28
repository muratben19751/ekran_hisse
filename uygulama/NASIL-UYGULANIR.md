# 1b (macOS Native) tasarımını klasöre uygulama

## Kurulum
1. Mevcut `overlay.py`'yi yedekle:
   ```
   cd /path/to/ekran_hisse
   cp overlay.py overlay_eski.py
   ```
2. Bu klasördeki `overlay.py`'yi ekran_hisse klasörüne kopyala (üzerine yaz).
3. Çalışan uygulamayı kapat (sekmeye sağ tık → Uygulamayı Kapat), sonra tekrar başlat.

`main.py`, `data_fetcher.py`, `notes_api_client.py`, `notes_api.php` ve `stocks.json`
**değişmedi** — dosya biçimi (symbol / entry / exit, `---:AD:sayı` ayırıcıları) aynı,
mevcut listen olduğu gibi açılır.

## Ne değişti

**Geometri**
- Panel 285 → **320px**, köşe yarıçapı 8 → 12, sekmeler 44 → 56px yükseklik, sekme arası 6px.
- Animasyon 200 → 220ms (OutCubic aynı).

**Görünüm**
- Panel arkaplanı `rgba(30,30,32,236)`, kenarlık `rgba(255,255,255,30)`.
- Satırlar artık **gruplanmış kart** içinde: kart `rgba(255,255,255,18)`, yarıçap 10,
  satır aralarında 12px soldan girintili hairline.
- Menlo/Arial yerine **macOS sistem yazı tipi**: başlık 15pt DemiBold, sembol 13pt DemiBold,
  fiyat 13pt, meta 11pt.
- Yüzde değişim artık **dolgulu pill**: yeşil `#30d158` / kırmızı `#ff453a`.
- Fiyat TR biçiminde: `₺12.847,52`.
- Yeşil ayırıcı bar yerine **büyük harf bölüm başlığı** + chevron + adet sayacı (tıkla → katla).
- Giriş/çıkış barı: 4px yuvarlak track + yeşil dolgu; hedef aşılınca sarı `#ffd60a` +
  satırda **"Hedef"** rozeti.
- Sekmeler: aktif olan mavi `#0a84ff`, ikonlar ◧ (portföy) ve ✎ (notlar).

**Etkileşim**
- **Arama alanı** (panel başında): yazarken liste filtrelenir; 3+ harfte mavi "Ekle"
  düğmesi çıkar, Enter da ekler.
- **Sürükle-bırak sıralama**: satırı tut ve sürükle; bırakma yeri mavi çizgiyle gösterilir.
  ▲▼ düğmeleri kalktı (bölümler için sağ tık → Yukarı/Aşağı taşı).
- Satıra **tek tık** → giriş ve çıkış hedefini tek sheet'te açar (eskiden iki ayrı dialog).
  Sheet panelin soluna yapışır; Temizle / İptal / Kaydet.
- Sağ tık → Hedef belirle… / Hedefi temizle / Listeden kaldır. Satırdaki `×` kalktı.
- Notlar: kart görünümlü liste (seçili satır mavi), yuvarlak köşeli editör,
  "+ Not" / "Sil" / "↻" pill düğmeleri, durum metni Kaydedildi / Değişiklik var / Kaydediliyor…

## Not
Qt penceresi macOS vibrancy (arka plan bulanıklığı) veremez; tasarımdaki blur yerine
panel opaklığı 236'ya çekildi. Gerçek vibrancy istersen `main.py` içindeki objc
köprüsüyle `NSVisualEffectView` eklenebilir — istersen onu da yazayım.
