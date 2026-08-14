# 1b (macOS Native) tasarımını klasöre uygulama

## Kurulum
1. Mevcut `overlay.py`'yi yedekle:
   ```
   cd /path/to/ekran_hisse
   cp overlay.py overlay_eski.py
   ```
2. Bu klasördeki `overlay.py`'yi ekran_hisse klasörüne kopyala (üzerine yaz).
3. Çalışan uygulamayı kapat (sekmeye sağ tık → Uygulamayı Kapat), sonra tekrar başlat.

`main.py`, `data_fetcher.py`, `notes_api_client.py` ve `stocks.json`
**değişmedi** — dosya biçimi (symbol / entry / exit, `---:AD:sayı` ayırıcıları) aynı,
mevcut listen olduğu gibi açılır.

## Ne değişti

**Geometri**
- Panel **300px**, köşe yarıçapı 12, sekmeler 52px yükseklik, sekme arası 6px.
- Panel aç/kapa animasyonu 120ms (OutQuart).

**Görünüm**
- Panel arkaplanı `rgba(30,30,32,236)`, kenarlık `rgba(255,255,255,30)`.
- Satırlar artık **gruplanmış kart** içinde: kart `rgba(255,255,255,18)`, yarıçap 10,
  satır aralarında 12px soldan girintili hairline.
- Menlo/Arial yerine **macOS sistem yazı tipi**: başlık 15pt DemiBold, sembol 13pt DemiBold,
  fiyat 13pt, meta 11pt.
- Yüzde değişim artık **dolgulu pill**: yeşil `#30d158` / kırmızı `#ff453a`.
- Fiyat TR biçiminde: `12.847,52` (binlik nokta, ondalık virgül). Para birimi
  simgesi gösterilmez — portföyde XAUUSD, EURUSD, XU100 gibi TL-olmayan
  semboller de bulunabildiğinden tek bir simge doğru olmazdı.
- Yeşil ayırıcı bar yerine **büyük harf bölüm başlığı** + chevron + adet sayacı (tıkla → katla).
- Giriş/çıkış hedefi belirlenince satırın başında küçük **yeşil nokta** belirir;
  hedef aşılınca nokta sarıya `#ffd60a` döner ve satır arka planı hafif sarı
  tint alır. (Ayrıca fiyat/PnL bilgisi satır tooltip'inde gösterilir.)
- Sekmeler: aktif olan mavi `#0a84ff`, ikonlar ◧ (portföy), ✎ (notlar) ve 𝕏 (tweet akışı).

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
  - **Senkron sınırı:** Notlar tek Gist'te tutulur ve son-yazan-kazanır (last-write-wins)
    mantığıyla kaydedilir. Aynı Gist'i **iki cihazdan** (ör. iş + ev Mac) eşzamanlı
    düzenlerseniz biri diğerinin değişikliğini ezebilir. Çok-cihaz güvenli birleştirme
    yoktur; tek cihazda kullanın veya cihazlar arası düzenlemeyi sıralı yapın.

## Not
Qt penceresi macOS vibrancy (arka plan bulanıklığı) veremez; tasarımdaki blur yerine
panel opaklığı 236'ya çekildi. Gerçek vibrancy istersen `main.py` içindeki objc
köprüsüyle `NSVisualEffectView` eklenebilir — istersen onu da yazayım.

## 𝕏 (Twitter) akışı — RSSHub kurulumu

𝕏 sekmesi tweet'leri **self-hosted RSSHub** üzerinden çeker. (Nitter ekosistemi
çöktüğü için eski köprü kaldırıldı.) RSSHub, X'in `auth_token` cookie'siyle gerçek
keyword araması yapar; token **RSSHub tarafında** tutulur, EkranHisse'de saklanmaz.

### 1. auth_token cookie'sini al
1. Bir tarayıcıda X/Twitter'a giriş yap (**burner/ikincil hesap önerilir** — token
   sızarsa ana hesabın etkilenmesin).
2. Geliştirici Araçları → **Application** (Chrome) / **Storage** (Firefox) → Cookies →
   `https://x.com` → `auth_token` değerini kopyala.

### 2. RSSHub'ı Docker'da başlat
```
docker run -d --name rsshub -p 1200:1200 \
  -e TWITTER_AUTH_TOKEN=<auth_token_cookie_değeri> \
  diygod/rsshub
```
Birden çok token'ı virgülle ayırıp rotasyon yapabilirsin (rate-limit'e karşı).

### 3. Doğrula
```
curl "http://localhost:1200/twitter/keyword/THYAO"
```
Geçerli bir `<rss>` XML ve güncel `pubDate` görmelisin. Bunu görüyorsan EkranHisse
𝕏 sekmesi de dolacaktır.

### 4. (Opsiyonel) Uzak RSSHub
RSSHub'ı başka bir makinede/portta çalıştırıyorsan tabanı `RSSHUB_URL` ile ver
(varsayılan `http://localhost:1200`). Sır değil; Keychain veya `~/.ekranhisse/notes_config.env`:
```
security add-generic-password -s ekranhisse -a RSSHUB_URL -w 'http://sunucu:1200'
```
Uygulama çalışırken eklersen yeniden başlatman gerekir (config import anında okunur).

> Not: RSSHub kapalıysa 𝕏 sekmesi "RSSHub kapalı" durumu gösterir; uygulama donmaz
> (istekler arka planda çalışır). Konteyneri başlatınca akış kendiliğinden dolar.
