"""OverlayWindow UI/E2E smoke testleri (offscreen QApplication).

PySide6 yoksa tüm modül atlanır. Qt platformu 'offscreen' zorlanır ki başlıksız
CI'da da çalışsın. Bu testler DeepR'nin işaret ettiği kapsam boşluğunu kapatır:
apply_data → _apply_cached_prices tüketici zinciri, _prune_tw_seen invaryantı,
_twitter_set_filter görünürlük filtresi ve _sync_target yön mantığı.
"""

import os
import sys

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

pytest.importorskip("PySide6")
overlay = pytest.importorskip("overlay")

from PySide6.QtCore import QObject, Qt, Signal  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402


class _Signals(QObject):
    data_signal = Signal(list)
    notes_signal = Signal(object)
    rsi_signal = Signal(str, object)


@pytest.fixture(scope="module")
def app():
    a = QApplication.instance() or QApplication([])
    yield a


@pytest.fixture
def win(app, tmp_path, monkeypatch):
    # Kalıcılığı tmp'ye yönlendir (gerçek ~/.ekranhisse'e dokunma).
    monkeypatch.setattr(overlay, "STOCKS_FILE", str(tmp_path / "stocks.json"))
    monkeypatch.setattr(overlay, "TW_SYMBOLS_FILE", str(tmp_path / "tw.json"))
    monkeypatch.setattr(overlay, "_LEGACY_STOCKS", str(tmp_path / "ls.json"))
    monkeypatch.setattr(overlay, "_LEGACY_TW", str(tmp_path / "lt.json"))
    w = overlay.OverlayWindow(_Signals())
    yield w
    w.close()
    w.deleteLater()


# ── Floating varsayılan KAPALI (yeni kullanıcı paneli kapatabilsin) ──────────
def test_floating_default_off(win):
    assert win._floating is False
    assert win._pinned is False


# ── apply_data → _apply_cached_prices tüketici zinciri ───────────────────────
def test_apply_data_updates_row_label(win):
    win.stocks = [{"symbol": "THYAO", "entry": None, "exit": None}]
    win._rebuild_rows()
    win.apply_data([{"symbol": "THYAO", "price": 12.5, "change_pct": 1.2}])
    assert "THYAO" in win.rows
    # _tr(12.5) TR biçimi: '12,50'
    assert win.rows["THYAO"].lbl_price.text() == overlay._tr(12.5)
    assert win._fetching is False   # invaryant: fetch kilidi bırakıldı


def test_apply_data_none_price_shows_dash(win):
    win.stocks = [{"symbol": "AKBNK", "entry": None, "exit": None}]
    win._rebuild_rows()
    win.apply_data([{"symbol": "AKBNK", "price": None, "change_pct": None}])
    assert win.rows["AKBNK"].lbl_price.text() == "—"


# ── _sync_target: yön farkındalığı (long/short hedef) ────────────────────────
def test_target_reached_long(win):
    r = overlay.StockRow("X", entry=100.0, exit_price=120.0)
    r.update_data(125.0, 1.0)          # long: fiyat çıkışın üstünde
    assert r._reached is True
    r.update_data(110.0, 1.0)          # çıkışın altında → ulaşılmadı
    assert r._reached is False


def test_target_reached_short(win):
    # Short/aşağı hedef: exit < entry. Fiyat çıkışa DÜŞünce ulaşılır.
    r = overlay.StockRow("X", entry=100.0, exit_price=90.0)
    r.update_data(88.0, -1.0)          # hedefin altına indi → ulaşıldı
    assert r._reached is True
    r.update_data(105.0, 1.0)          # girişin üstü → ESKİDEN yanlış 'ulaşıldı'
    assert r._reached is False


# ── _prune_tw_seen: incoming id'lerin tamamı korunur (unread invaryantı) ─────
def test_prune_tw_seen_keeps_all_incoming(win):
    incoming = {f"in{i}" for i in range(50)}
    # 500 üstü eski id + gelenler
    win._tw_seen = {f"old{i}" for i in range(600)} | incoming
    win._prune_tw_seen(incoming)
    assert len(win._tw_seen) <= 500
    # Kritik: gelen id'lerin TAMAMI korunmalı (yoksa yanlış 'yeni' rozeti)
    assert incoming <= win._tw_seen


def test_prune_tw_seen_no_prune_under_cap(win):
    win._tw_seen = {"a", "b", "c"}
    win._prune_tw_seen({"a"})
    assert win._tw_seen == {"a", "b", "c"}


# ── _twitter_set_filter: widget yeniden kurmadan görünürlük filtresi ─────────
def test_twitter_filter_toggles_visibility_not_rebuild(win):
    win._tw_symbols = ["THYAO", "AKBNK"]
    win._tw_tweets = [
        {"id": "1", "text": "THYAO harika", "author_id": "u1"},
        {"id": "2", "text": "AKBNK yükseldi", "author_id": "u2"},
        {"id": "3", "text": "genel piyasa", "author_id": "u3"},
    ]
    win._tw_users = {}
    win._tw_hl = set()
    win._twitter_render()
    rows_before = win._tw_rows
    assert len(rows_before) == 3
    # _tw_rows artık (syms_list, row) tutar — çok sembollü tweet için liste.
    # THYAO filtrele — aynı row nesneleri kalmalı (rebuild yok), sadece görünürlük.
    # Pencere show() edilmediğinden isVisible() False döner; isVisibleTo(ebeveyn)
    # ile mantıksal görünürlük bayrağını doğrula.
    win._twitter_set_filter("THYAO")
    assert win._tw_rows is rows_before   # AYNI liste — yeniden kurulmadı
    visible = [("THYAO" in syms, r.isVisibleTo(r.parentWidget()))
               for syms, r in win._tw_rows]
    assert visible == [(True, True), (False, False), (False, False)]
    # Tümü'ye dön — hepsi görünür
    win._twitter_set_filter(None)
    assert all(r.isVisibleTo(r.parentWidget()) for _, r in win._tw_rows)
    assert win._tw_rows is rows_before


# ── Çok sembollü tweet her ilgili sembol filtresinde görünür/sayılır (#29) ────
def test_twitter_multi_symbol_tweet_counts_and_visible_in_both(win):
    win._tw_symbols = ["THYAO", "AKBNK"]
    win._tw_tweets = [
        {"id": "1", "text": "THYAO ve AKBNK ikisi de uçtu", "author_id": "u1"},
        {"id": "2", "text": "sadece THYAO", "author_id": "u2"},
    ]
    win._tw_users = {}
    win._tw_hl = set()
    win._twitter_render()
    # Çok sembollü tweet HER İKİ sembolün satır-listesinde olmalı.
    rows_by_id = {}
    for syms, row in win._tw_rows:
        rows_by_id[tuple(sorted(syms))] = syms
    # tweet 1 iki sembol, tweet 2 tek sembol
    all_syms = [syms for syms, _ in win._tw_rows]
    assert ["THYAO", "AKBNK"] in all_syms   # verilen 'symbols' sırasında
    assert ["THYAO"] in all_syms
    # AKBNK filtresi → çok sembollü tweet AKBNK'de de görünür (eskiden görünmezdi)
    win._twitter_set_filter("AKBNK")
    vis = {tuple(syms): r.isVisibleTo(r.parentWidget()) for syms, r in win._tw_rows}
    assert vis[("THYAO", "AKBNK")] is True   # çok sembollü tweet AKBNK'de görünür
    assert vis[("THYAO",)] is False          # yalnız-THYAO tweet'i gizli
    # Chip sayaçları: AKBNK chip'i 0 DEĞİL (çok sembollü tweet ona da sayıldı)
    akbnk_chip = next(c for s, c in win._tw_chip_widgets if s == "AKBNK")
    # Chip metninde sayı 1 olmalı (yalnızca çok sembollü tweet AKBNK içeriyor)
    assert "1" in akbnk_chip._chip_cnt.text()


# ── StockRow.update_rsi: eşik renk mantığı + NaN savunması (#38) ─────────────
def test_update_rsi_threshold_colors(win):
    r = overlay.StockRow("X")
    # anchor >= 70 → yeşil
    r.update_rsi({5: 75.0, 15: 60.0, 30: 50.0, 60: 40.0})
    assert overlay.C_GREEN in r.lbl_rsi.styleSheet()
    assert r.lbl_rsi.isVisibleTo(r)
    # anchor <= 30 → kırmızı
    r.update_rsi({5: 25.0, 15: 40.0, 30: 50.0, 60: 60.0})
    assert overlay.C_RED in r.lbl_rsi.styleSheet()
    # 30 < anchor < 70 → nötr (yeşil/kırmızı değil)
    r.update_rsi({5: 50.0, 15: 55.0, 30: 45.0, 60: 60.0})
    ss = r.lbl_rsi.styleSheet()
    assert overlay.C_GREEN not in ss and overlay.C_RED not in ss


def test_update_rsi_anchor_is_shortest_valid_interval(win):
    # 5m NaN → anchor 15m (75) olmalı → yeşil; 5m atlanır ama parts'ta 15m var.
    nan = float("nan")
    r = overlay.StockRow("X")
    r.update_rsi({5: nan, 15: 75.0, 30: 50.0, 60: 40.0})
    assert overlay.C_GREEN in r.lbl_rsi.styleSheet()
    assert "15m:75" in r.lbl_rsi.text()
    assert not r.lbl_rsi.text().startswith("5m:")   # NaN 5m interval gösterilmez


def test_update_rsi_nan_never_crashes_and_hides_when_all_invalid(win):
    nan = float("nan")
    r = overlay.StockRow("X")
    # Tüm interval NaN/None → int(round(nan)) ValueError ATMAMALI, etiket gizli
    r.update_rsi({5: nan, 15: None, 30: nan, 60: None})
    assert r.lbl_rsi.isVisibleTo(r) is False
    # Karışık: NaN atlanır, geçerli olan gösterilir (çökme yok)
    r.update_rsi({5: nan, 15: 55.0, 30: None, 60: nan})
    assert "15m:55" in r.lbl_rsi.text()


# ── _add_from_search: bilinmeyen/boş/tekrar sembol koruması (#39) ─────────────
def test_add_from_search_rejects_unknown_symbol(win):
    win.stocks = []
    win.search.setText("ZZZZZ")     # is_known False
    win._add_from_search()
    assert win.stocks == []          # geçersiz sembol stocks'a SIZMAMALI
    assert "Bilinmeyen sembol" in win.lbl_stock_status.text()


def test_add_from_search_empty_input_noop(win):
    win.stocks = []
    win.search.setText("   ")
    win._add_from_search()
    assert win.stocks == []


def test_add_from_search_accepts_known_and_dedupes(win):
    win.stocks = []
    win.search.setText("thyao")      # küçük harf → upper + is_known True
    win._add_from_search()
    assert any(s["symbol"] == "THYAO" for s in win.stocks)
    n = len(win.stocks)
    # Aynı sembolü tekrar ekle → çift kayıt olmamalı
    win.search.setText("THYAO")
    win._add_from_search()
    assert len(win.stocks) == n


# ── apply_rsi → _rsi_cache → _rebuild_rows sonrası RSI restore (#40) ──────────
def test_apply_rsi_caches_and_restores_after_rebuild(win):
    win.stocks = [{"symbol": "THYAO", "entry": None, "exit": None}]
    win._rebuild_rows()
    win.apply_rsi("THYAO", {5: 72.0, 15: 60.0, 30: 50.0, 60: 40.0})
    assert win._rsi_cache["THYAO"][5] == 72.0
    assert win.rows["THYAO"].lbl_rsi.isVisibleTo(win.rows["THYAO"])
    # Rebuild sonrası (sekme/panel değişimi simülasyonu) RSI korunmalı
    win._rebuild_rows()
    assert "5m:72" in win.rows["THYAO"].lbl_rsi.text()   # cache'ten geri uygulandı


# ── Sheet açıkken panel kapanmamalı: _modal_open guard (#41) ──────────────────
def test_modal_open_guards_outside_click_close(win, monkeypatch):
    # Panel açık, floating/pinned kapalı — normalde dışarı tıklama kapatır.
    win._mode = 1
    win._pinned = False
    win._floating = False
    closed = []
    monkeypatch.setattr(win, "_toggle", lambda m: closed.append(m))
    # Modal (sheet) açık gibi davran → _modal_open True → panel KAPANMAMALI
    monkeypatch.setattr(win, "_modal_open", lambda: True)
    from PySide6.QtCore import QEvent, QPointF
    from PySide6.QtGui import QMouseEvent

    def _press():
        # global konumu panel dışında bir MouseButtonPress olayı üret
        return QMouseEvent(QEvent.MouseButtonPress, QPointF(-9999, -9999),
                           QPointF(-9999, -9999), Qt.LeftButton, Qt.LeftButton,
                           Qt.NoModifier)

    win.eventFilter(win, _press())
    assert closed == []   # modal açıkken kapanmadı
    # Modal kapalıyken (sheet yok) aynı dış tıklama paneli kapatmalı
    monkeypatch.setattr(win, "_modal_open", lambda: False)
    win.eventFilter(win, _press())
    assert closed == [1]   # modal yokken kapandı
