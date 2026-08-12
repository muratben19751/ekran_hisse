---
title: paths
type: entity
summary: EkranHisse'nin veri-dizini yol politikasının tek kaynağı — ~/.ekranhisse için DATA_DIR, ensure_data_dir() ve data_file(); OSError'da ~'a fallback.
sources:
  - sources/03_deepr_review_round2_2026-08-12.md
related:
  - wiki/synthesis/architecture_overview.md
last_updated: 2026-08-12
---

# paths

`~/.ekranhisse` veri dizini yol politikasının **tek kaynağı**. DeepR 3. turda
(bulgu G43) eklendi: daha önce `main.py`, `config.py` ve `overlay.py` bu yolu
bağımsız hardcode ediyordu ve `ensure_data_dir` mantığı iki yerde farklı
davranıyordu.

## API
- `DATA_DIR` — modül-seviyesi mutable string; varsayılan `~/.ekranhisse`.
- `ensure_data_dir() -> str` — dizini `makedirs(exist_ok=True)` ile oluşturur;
  `OSError`'da `DATA_DIR`'i `~`'a düşürür (log.warning) ve döndürür.
- `data_file(name) -> str` — `os.path.join(DATA_DIR, name)`.

## Kullanım deseni ve uyarı
`main.py` `ensure_data_dir()`'i overlay/config importundan **önce** çağırır.
Bu kritik: `STOCKS_FILE = paths.data_file("stocks.json")` gibi modül-seviyesi
sabitler import anında `DATA_DIR`'in o anki değerini **yakalar**; fallback
importlardan önce tetiklenmezse sabitler bayat kalırdı. Mevcut sıra bunu doğru
yapar (bkz. [[architecture_overview]] "Kalıcılık ve yol politikası").

Kalıcı dosyalar: `stocks.json`, `tw_symbols.json`, `notes_config.env`,
`.ekranhisse.lock` — hepsi `data_file()` üzerinden.

## İlgili
- [[architecture_overview]]
- [[overlay_window]]

<!-- BACKLINKS:BEGIN -->
## Referenced by

- [[architecture_overview]]
<!-- BACKLINKS:END -->
