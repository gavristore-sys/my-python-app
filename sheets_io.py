"""Tulis ke tab 'Pelanggan' di Google Sheets (ws = objek worksheet gspread).
Posisi kolom dibaca dari baris header, jadi urutan kolom di sheet boleh berubah."""


def _huruf(n):  # 1 -> A, 27 -> AA
    s = ""
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def edit_kolom(ws, ids, nilai, kolom_kunci="id"):
    """Isi kolom-kolom di `nilai` ({kolom: isi}) pada semua baris dengan id di `ids`.
    Satu kali baca + satu kali tulis, jadi hemat kuota API."""
    header = ws.row_values(1)
    posisi = {v: i + 1 for i, v in enumerate(ws.col_values(header.index(kolom_kunci) + 1))}
    hilang = [i for i in ids if i not in posisi]
    if hilang:
        raise KeyError(f"id tidak ditemukan di sheet: {', '.join(hilang)}")
    data = [{"range": f"{_huruf(header.index(k) + 1)}{posisi[i]}", "values": [[v]]}
            for i in ids for k, v in nilai.items()]
    ws.batch_update(data, value_input_option="RAW")


def id_baru(ids):
    """Kode otomatis CRM-0001, CRM-0002, ... untuk pelanggan yang belum punya kode."""
    n = [int(i[4:]) for i in ids if i.startswith("CRM-") and i[4:].isdigit()]
    return f"CRM-{max(n, default=0) + 1:04d}"


def tambah_pelanggan(ws, rec):
    """Tambah satu baris. Kode kosong -> dibuat otomatis; kd_group kosong -> sama dengan kode."""
    header = ws.row_values(1)
    ids = ws.col_values(header.index("id") + 1)[1:]
    if not rec.get("id"):
        rec["id"] = id_baru(ids)
    elif rec["id"] in ids:
        raise ValueError(f"kode {rec['id']} sudah ada")
    if not rec.get("kd_group"):
        rec["kd_group"] = rec["id"]
    ws.append_row([rec.get(k, "") for k in header], value_input_option="RAW")
    return rec["id"]
