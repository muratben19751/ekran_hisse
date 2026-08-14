---
source: EkranHisse oturum notu — TV seri limiti / sıralı seri akışı
retrieved: 2026-08-14
type: session
immutable: true
---

# RSI/sparkline boş: TV "exceed limit of series in the session" → sıralı seri akışı (2026-08-14)

## Belirti
Uygulama açılışında log:
```
TV RSI critical_error: [cs_..., 'exceed limit of series in the session',
                        'method: create_series. args: "[sym0_15, ...]"']
TV history critical_error: [..., 'exceed limit of series in the session', ...]
```
RSI etiketleri ve sparkline boş kalıyor; tweet ile ilgisiz (TV veri katmanı).

## Teşhis (canlı probe)
`data_fetcher._fetch_tv_rsi_bulk_once` ve `fetch_tv_history` her (sembol[,interval])
için TEK chart session altında paralel `create_series` atıyordu. Canlı deneyle
gerçek kota ölçüldü:
- **1 seri** (THYAO 15m) tek başına → **BAŞARILI** (RSI 36.5).
- **2 seri** (2 sembol × 1 interval) → **HEPSİ None**, hata hep `sym1` (ikinci seride).
- 8 seri, 10 seri → yine hepsi None.

**Kök neden:** Bu TV hesabının (`sessionid`) eşzamanlı-seri kotası = **1**. Tek
session'da aynı anda birden fazla `create_series` açılamıyor; ikincisi
`exceed limit of series in the session` ile reddediliyor ve `critical_error`
tüm batch'i düşürüyor → RSI/sparkline komple boş.

## Çözüm — sıralı seri akışı (tek WS, remove_series ile)
Yeni ortak motor `data_fetcher._stream_tv_series(specs, on_closes, timeout)`:
- TEK WS bağlantısı açar (handshake+auth bir kez); seriler **sıralı** akıtılır.
- `on_open`: chart_create_session + İLK seriyi aç (resolve_symbol + create_series).
- `timescale_update`: o an açık serinin (cur_sid) close'larını toplar (NaN filtreli).
- `series_completed`/`series_error`: seriyi `remove_series` ile kapat → sonucu
  `on_closes(key, closes)` ile yay → BİR SONRAKİ seriyi aç. Herhangi bir anda
  **tek seri açık** → kota hiç aşılmaz.
- Bittiğinde `done.set()`; `timeout` (40s) güvenlik ağı.

### İki kritik ayrıntı (canlı probe'da yakalandı)
1. **Benzersiz slot/sid gerekli.** `remove_series` seriyi kaldırır ama resolve
   edilen sembol **slotu session'da kalır**; aynı slot adını (`sym0`) ikinci kez
   resolve etmek → `critical_error: duplicate id`. Çözüm: her seri idx'e bağlı
   taze isim alır (`sym{idx}` / `s{idx}`).
2. **ws.send kilit DIŞINDA.** Motor `state` (idx/closes_acc/cur_sid) için
   `threading.Lock` kullanır; ama bir soket send'i senkron işleyip on_message'ı
   AYNI thread'de yeniden çağırabilir (testte kesin böyle). Kilit içinde send
   etmek reentrant kilitlenme yapardı (Lock reentrant değil). Kilit yalnız state'i
   korur; tüm send'ler kilit bırakıldıktan sonra. `advancing` bayrağı aynı seri
   için çift sinyalde (completed+error) tek ilerleme sağlar.

## Sarmalayıcılar (public API değişmedi)
- `fetch_tv_rsi_bulk(symbols, intervals)` → specs = her (SYM, iv); `_on_closes`
  close'ları `_calc_rsi`'ye verir. Tüm sonuç None ise token invalide + 1 retry.
  Döndürür `{SYM: {iv: rsi|None}}` (aynen eski sözleşme).
- `fetch_tv_history(symbols, interval, bars)` → specs = her SYM; `_on_closes`
  son `bars` close'u sembole yazar. Döndürür `{SYM: [close...]}`.

Eski `_fetch_tv_rsi_bulk_once`/`_fetch_tv_history_once` ve kısa ömürlü
`_MAX_SERIES_PER_SESSION` batch denemesi kaldırıldı (batch'leme işe yaramaz:
kota tek session'da 1 seri, batch boyutu ne olursa olsun 2. seri patlardı).

## Doğrulama
- `pytest -q` → **299 passed** (+7: sıralı akış sıra/remove/error, RSI+history
  spec üretimi, boş-close→None, all-None retry, boş sembol no-op; +2 gerçek WS
  mock'uyla motoru süren uçtan-uca test).
- `ruff check` → temiz.
- **Canlı:** 3 sembol × 4 interval = 12 serinin hepsi doldu (9.1s); 3 sparkline
  24'er bar (2.4s). Gerçek portföyle (8 sembol): RSI 28/32 seri (VİOP vadeli
  `*Q2026` ve `---` ayracı beklendiği gibi boş), sparkline 7/8, 17.4s.
- Uygulama yeni kodla açıldı; logda `exceed limit`/`duplicate id`/`critical_error`
  = 0.

## Ödünleşim (belgeli)
Sıralı akış, kota=1 hesabın kaçınılmaz sonucu: seri başına ~0.75s, N sembol ×
4 interval seri → RSI süresi sembol sayısıyla lineer artar (8 sembol ≈ 17s).
Arka plan thread'inde çalışır (UI bloklanmaz), RSI 300sn'de bir yenilenir.
Kota daha yüksek bir TV oturumu ile paralel akışa dönülebilir (o zaman eski
tek-session çoklu-seri deseni yeniden mümkün). Bkz. [[data_fetcher]].
