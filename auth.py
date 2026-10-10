"""Login berbasis tab 'Pengguna' di Google Sheet yang sama (tanpa Streamlit di sini, agar mudah diuji).
Kata sandi tidak pernah disimpan polos: hanya hash PBKDF2-SHA256 dengan garam acak."""
import hashlib
import hmac
import re
import secrets
from datetime import datetime, timedelta, timezone

import gspread
from sheets_io import edit_kolom

KOLOM = ["username", "nama", "peran", "password_hash", "aktif", "gagal", "terkunci_hingga", "dibuat"]
PERAN = ["admin", "staf", "lihat"]  # admin: semua + kelola pengguna | staf: lihat & ubah | lihat: baca saja
MAKS_GAGAL = 5      # salah sandi berturut-turut sebelum akun dikunci
KUNCI_MENIT = 15
ITERASI = 600_000
MIN_SANDI = 8


def _sekarang():
    return datetime.now(timezone.utc)


def _waktu(teks):
    try:
        t = datetime.fromisoformat(str(teks))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def _int(x):
    try:
        return int(str(x).strip() or 0)
    except ValueError:
        return 0


def hash_sandi(sandi, iterasi=ITERASI):
    garam = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", sandi.encode(), bytes.fromhex(garam), iterasi).hex()
    return f"pbkdf2${iterasi}${garam}${h}"


def cek_sandi(sandi, tersimpan):
    try:
        _, iterasi, garam, h = str(tersimpan).split("$")
        baru = hashlib.pbkdf2_hmac("sha256", sandi.encode(), bytes.fromhex(garam), int(iterasi)).hex()
    except ValueError:
        return False
    return hmac.compare_digest(baru, h)


_PALSU = hash_sandi("palsu")  # agar waktu respons sama untuk username yang tidak ada


def ws_pengguna(sh):
    """Tab 'Pengguna'; dibuat otomatis (hanya header) jika belum ada."""
    try:
        return sh.worksheet("Pengguna")
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet("Pengguna", rows=100, cols=len(KOLOM))
        ws.update(range_name="A1", values=[KOLOM], value_input_option="RAW")
        return ws


def baca(ws):
    return ws.get_all_records(numericise_ignore=["all"])


def ada_admin_aktif(data):
    return any(str(u["peran"]) == "admin" and str(u["aktif"]).strip().lower() == "ya" for u in data)


def cek_kekuatan(sandi):
    if len(sandi) < MIN_SANDI:
        raise ValueError(f"Kata sandi minimal {MIN_SANDI} karakter.")


def masuk(ws, username, sandi):
    """(pengguna, None) jika berhasil; (None, pesan) jika gagal."""
    username = username.strip().lower()
    p = next((u for u in baca(ws) if str(u["username"]).strip().lower() == username), None)
    if p is None or str(p["aktif"]).strip().lower() != "ya":
        cek_sandi(sandi, _PALSU)
        return None, "Username atau kata sandi salah."
    kunci = _waktu(p["terkunci_hingga"])
    if kunci and kunci > _sekarang():
        sisa = int((kunci - _sekarang()).total_seconds() // 60) + 1
        return None, f"Akun terkunci karena terlalu banyak percobaan. Coba lagi dalam {sisa} menit."
    if cek_sandi(sandi, p["password_hash"]):
        if _int(p["gagal"]) or p["terkunci_hingga"]:
            edit_kolom(ws, [p["username"]], {"gagal": 0, "terkunci_hingga": ""}, kolom_kunci="username")
        return p, None
    gagal = _int(p["gagal"]) + 1
    if gagal >= MAKS_GAGAL:
        isi = {"gagal": 0, "terkunci_hingga":
               (_sekarang() + timedelta(minutes=KUNCI_MENIT)).isoformat(timespec="seconds")}
    else:
        isi = {"gagal": gagal}
    edit_kolom(ws, [p["username"]], isi, kolom_kunci="username")
    return None, "Username atau kata sandi salah."


def tambah_pengguna(ws, username, nama, peran, sandi):
    username = username.strip().lower()
    if not re.fullmatch(r"[a-z0-9._-]{3,30}", username):
        raise ValueError("Username 3-30 karakter: huruf kecil, angka, titik, garis bawah, atau strip.")
    if peran not in PERAN:
        raise ValueError("Peran tidak valid.")
    cek_kekuatan(sandi)
    if username in [str(u).strip().lower() for u in ws.col_values(1)[1:]]:
        raise ValueError("Username sudah dipakai.")
    ws.append_row([username, nama.strip(), peran, hash_sandi(sandi), "ya", 0, "",
                   _sekarang().isoformat(timespec="seconds")], value_input_option="RAW")


def ganti_sandi(ws, username, sandi_baru):
    cek_kekuatan(sandi_baru)
    edit_kolom(ws, [username], {"password_hash": hash_sandi(sandi_baru), "gagal": 0,
                                "terkunci_hingga": ""}, kolom_kunci="username")


def ganti_sandi_sendiri(ws, username, lama, baru):
    p, _ = masuk(ws, username, lama)
    if p is None:
        raise ValueError("Kata sandi lama salah.")
    ganti_sandi(ws, username, baru)
