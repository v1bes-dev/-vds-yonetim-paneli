# db.py — destek talepleri (destek.db) icin tek veri erisim katmani.
# Tum sorgular parametreli (?) — SQL injection riski yok. Okuma baglantisi
# PRAGMA query_only ile salt-okunur acilir (listeleme sirasinda yanlislikla
# yazma yapilamaz).
import sqlite3
import datetime
from pathlib import Path
from contextlib import contextmanager

DB_PATH = Path(__file__).parent.resolve() / "destek.db"


def init_db() -> None:
    with _write_conn() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS talepler (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            musteri TEXT, sorun TEXT, tarih TEXT, durum TEXT
        )""")


@contextmanager
def _read_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA query_only = ON")
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def _write_conn():
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _sadelestir(metin: str) -> str:
    donusum = str.maketrans("çÇıİğĞüÜöÖşŞ", "cCiIgGuUoOsS")
    return metin.translate(donusum).lower()


def talep_olustur(musteri: str, sorun: str) -> int:
    tarih = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")
    with _write_conn() as conn:
        imlec = conn.execute(
            "INSERT INTO talepler (musteri, sorun, tarih, durum) VALUES (?, ?, ?, ?)",
            (musteri, sorun, tarih, "açık"),
        )
        return imlec.lastrowid


def talepleri_listele(durum: str | None = None) -> list[tuple]:
    with _read_conn() as conn:
        satirlar = conn.execute("SELECT id, musteri, sorun, tarih, durum FROM talepler").fetchall()
    if durum:
        hedef = _sadelestir(durum)
        satirlar = [s for s in satirlar if _sadelestir(s[4]) == hedef]
    return satirlar


def talep_durumu_guncelle(talep_id: int, yeni_durum: str) -> bool:
    with _write_conn() as conn:
        conn.execute("UPDATE talepler SET durum = ? WHERE id = ?", (yeni_durum, talep_id))
        return conn.total_changes > 0
