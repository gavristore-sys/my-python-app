import hmac

import pandas as pd
import streamlit as st
from crm_data import kunci_nama, label_bayar, ringkas_customer, ringkas_grup
from sheets_io import edit_kolom, tambah_pelanggan
from auth import (PERAN, ada_admin_aktif, baca, cek_kekuatan, ganti_sandi, ganti_sandi_sendiri,
                  masuk, tambah_pengguna, ws_pengguna)

STATUS = ["", "Aktif", "Prospek", "Tidak aktif"]  # ubah sesuai kebutuhan

st.set_page_config(page_title="CRM Pelanggan", layout="wide")


def rp(x):
    return "Rp " + f"{int(x):,}".replace(",", ".")


def rapikan(df):
    df = df.copy()
    df["plafon"] = pd.to_numeric(df["plafon"], errors="coerce").fillna(0).astype("int64")
    df["jt_tempo"] = pd.to_numeric(df["jt_tempo"], errors="coerce").fillna(0).astype(int)
    for c in df.columns.difference(["plafon", "jt_tempo"]):
        df[c] = df[c].fillna("").astype(str)
    df["cara_bayar"] = df["tk"].map(label_bayar)
    cari = ["id", "nama_customer", "nama_jobsite", "alamat", "kontak", "telp"]
    df["_teks"] = df[cari].agg(" ".join, axis=1).str.lower()
    return df


@st.cache_resource
def buka_sheet():
    """File Google Sheet, atau None (mode lokal)."""
    if "gcp_service_account" not in st.secrets:
        return None
    import gspread
    gc = gspread.service_account_from_dict(dict(st.secrets["gcp_service_account"]))
    return gc.open_by_key(st.secrets["sheet_id"])


@st.cache_resource
def sambung():
    """Tab 'Pelanggan', atau None (mode lokal)."""
    sh = buka_sheet()
    return None if sh is None else sh.worksheet("Pelanggan")


@st.cache_resource
def sambung_pengguna():
    """Tab 'Pengguna' (dibuat otomatis jika belum ada)."""
    return ws_pengguna(buka_sheet())


@st.cache_data(ttl=300)  # baca ulang dari Sheets paling cepat tiap 5 menit (hemat kuota API)
def muat():
    ws = sambung()
    if ws is not None:
        return rapikan(pd.DataFrame(ws.get_all_records(numericise_ignore=["all"])))
    # mode lokal (tanpa Google): pakai file hasil `python crm_data.py cust.xls`
    return rapikan(pd.read_excel("pelanggan_bersih.xlsx", dtype=str))


def pengaturan_awal(ws_p):
    st.subheader("Pengaturan awal: buat admin")
    kode = str(st.secrets.get("kode_setup", ""))
    if len(kode) < 12:
        st.info('Tambahkan baris `kode_setup = "teks-acak-minimal-12-karakter"` di Secrets '
                '(di atas baris [gcp_service_account]), lalu reboot aplikasi.')
        return
    with st.form("awal"):
        k = st.text_input("Kode setup", type="password")
        u = st.text_input("Username admin")
        n = st.text_input("Nama")
        s1 = st.text_input("Kata sandi", type="password")
        s2 = st.text_input("Ulangi kata sandi", type="password")
        if st.form_submit_button("Buat admin"):
            if not hmac.compare_digest(k.encode(), kode.encode()):
                st.error("Kode setup salah.")
            elif s1 != s2:
                st.error("Kata sandi tidak sama.")
            else:
                try:
                    tambah_pengguna(ws_p, u, n, "admin", s1)
                except ValueError as e:
                    st.error(str(e))
                except Exception as e:
                    st.error(f"Gagal menyimpan: {e}")
                else:
                    st.session_state["pesan"] = "Admin dibuat. Silakan masuk."
                    st.rerun()


def halaman_masuk(ws_p):
    st.title("CRM Pelanggan")
    if "pesan" in st.session_state:
        st.success(st.session_state.pop("pesan"))
    if not ada_admin_aktif(baca(ws_p)):
        pengaturan_awal(ws_p)
        st.stop()
    with st.form("masuk"):
        u = st.text_input("Username")
        s = st.text_input("Kata sandi", type="password")
        kirim = st.form_submit_button("Masuk")
    if kirim:
        try:
            p, pesan = masuk(ws_p, u, s)
        except Exception as e:
            st.error(f"Gagal memeriksa login: {e}")
        else:
            if p:
                st.session_state["pengguna"] = {"username": p["username"],
                                                "nama": p["nama"] or p["username"], "peran": p["peran"]}
                st.rerun()
            st.error(pesan)
    st.stop()


# ---- gerbang login: semua data di bawah baris ini hanya untuk pengguna yang sudah masuk ----
ws_p = sambung_pengguna() if sambung() is not None else None
if ws_p is None:  # mode lokal (tanpa Google Sheets): tanpa login
    pengguna = {"username": "lokal", "nama": "Mode lokal", "peran": "admin"}
else:
    pengguna = st.session_state.get("pengguna")
    if pengguna is None:
        halaman_masuk(ws_p)
bisa_ubah = pengguna["peran"] in ("admin", "staf")

with st.sidebar:
    st.markdown(f"**{pengguna['nama']}**  \n{pengguna['peran']}")
    if ws_p is not None:
        with st.expander("Ganti kata sandi"):
            with st.form("form_ganti_sandi"):
                lama = st.text_input("Kata sandi lama", type="password")
                baru = st.text_input("Kata sandi baru", type="password")
                ulang = st.text_input("Ulangi kata sandi baru", type="password")
                if st.form_submit_button("Simpan"):
                    if baru != ulang:
                        st.error("Kata sandi baru tidak sama.")
                    else:
                        try:
                            ganti_sandi_sendiri(ws_p, pengguna["username"], lama, baru)
                        except ValueError as e:
                            st.error(str(e))
                        except Exception as e:
                            st.error(f"Gagal menyimpan: {e}")
                        else:
                            st.success("Kata sandi diganti.")
        if st.button("Keluar"):
            st.session_state.clear()
            st.rerun()

df = muat()
cust = ringkas_customer(df)
grup = ringkas_grup(cust)
PLAFON = {"plafon": st.column_config.NumberColumn("Plafon", format="Rp %d")}

st.title("CRM Pelanggan")
if "pesan" in st.session_state:
    st.success(st.session_state.pop("pesan"))
a, b, c, d = st.columns(4)
a.metric("Customer", len(cust))
b.metric("Jobsite / cabang", len(df))
c.metric("Grup", len(grup))
d.metric("Total plafon", rp(cust["plafon"].sum()))

nama_tab = ["Pelanggan", "Grup", "Tambah pelanggan"] + (["Pengguna"] if pengguna["peran"] == "admin" else [])
tabs = st.tabs(nama_tab)
tab1, tab2, tab3 = tabs[:3]

with tab1:
    k1, k2, k3, k5, k4 = st.columns([3, 2, 2, 2, 1])
    cari = k1.text_input("Cari nama, alamat, kontak, telepon, kode")
    wil = k2.multiselect("Wilayah", sorted(x for x in df["wilayah"].unique() if x))
    kota = k3.multiselect("Kota", sorted(x for x in df["kota"].unique() if x))
    cb = k5.multiselect("Cara bayar", ["Tunai", "Kredit"])
    ada = k4.checkbox("Punya plafon")

    f = df
    if cari:
        f = f[f["_teks"].str.contains(cari.lower(), regex=False)]
    if wil:
        f = f[f["wilayah"].isin(wil)]
    if kota:
        f = f[f["kota"].isin(kota)]
    if cb:
        f = f[f["cara_bayar"].isin(cb)]
    if ada:
        f = f[f["plafon"] > 0]
    f = f.reset_index(drop=True)

    st.caption(f"{len(f)} dari {len(df)} baris. Klik satu baris untuk melihat detail.")
    sel = st.dataframe(
        f[["id", "nama_customer", "nama_jobsite", "kota", "cara_bayar", "plafon", "jt_tempo", "kd_group"]],
        hide_index=True, width="stretch", on_select="rerun",
        selection_mode="single-row", column_config=PLAFON)

    if sel.selection.rows:
        r = f.iloc[sel.selection.rows[0]]
        st.divider()
        st.subheader(r["nama_customer"])
        st.caption(r["nama_jobsite"])
        x, y = st.columns(2)
        x.markdown(f"**Alamat:** {r['alamat'] or '-'}\n\n"
                   f"**Kota / wilayah:** {r['kota'] or '-'} / {r['wilayah'] or '-'}\n\n"
                   f"**Jobsite:** {r['jobsite'] or '-'}")
        y.markdown(f"**Kontak:** {r['kontak'] or '-'}  ·  **Telp:** {r['telp'] or '-'}\n\n"
                   f"**NPWP:** {r['npwp'] or '-'}\n\n"
                   f"**Cara bayar:** {r['cara_bayar']}  ·  **Jatuh tempo:** {r['jt_tempo']} hari\n\n"
                   f"**Plafon kredit (per customer):** {rp(r['plafon'])}")
        anggota = cust[cust["kd_group"] == r["kd_group"]]
        if len(anggota) > 1:
            st.markdown(f"**Satu grup (kode {r['kd_group']}):** {len(anggota)} customer, "
                        f"total plafon {rp(anggota['plafon'].sum())}")
            st.dataframe(anggota[["nama_customer", "cara_bayar", "jumlah_jobsite", "plafon"]],
                         hide_index=True, width="stretch", column_config=PLAFON)
        else:
            st.caption(f"Tidak ada customer lain dalam grup {r['kd_group']}.")

        with st.expander("Ubah status / catatan"):
            ws = sambung()
            if not bisa_ubah:
                st.info("Peran Anda hanya dapat melihat data.")
            elif ws is None:
                st.info("Mode lokal: pengeditan aktif setelah aplikasi terhubung ke Google Sheets.")
            else:
                serumpun = df[df["nama_customer"].map(kunci_nama) == kunci_nama(r["nama_customer"])]["id"].tolist()
                opsi = STATUS + ([r["status"]] if r["status"] not in STATUS else [])
                tgl0 = pd.to_datetime(r["terakhir_dihubungi"], errors="coerce")
                with st.form(f"edit_{r['id']}"):
                    status = st.selectbox("Status", opsi, index=opsi.index(r["status"]))
                    tgl = st.date_input("Terakhir dihubungi", value=None if pd.isna(tgl0) else tgl0.date())
                    catatan = st.text_area("Catatan", value=r["catatan"])
                    semua = st.checkbox(f"Terapkan ke semua jobsite customer ini ({len(serumpun)} baris)")
                    if st.form_submit_button("Simpan"):
                        ids = serumpun if semua else [r["id"]]
                        try:
                            edit_kolom(ws, ids, {"status": status, "catatan": catatan,
                                                 "terakhir_dihubungi": tgl.isoformat() if tgl else ""})
                        except Exception as e:
                            st.error(f"Gagal menyimpan: {e}")
                        else:
                            muat.clear()
                            st.session_state["pesan"] = f"Tersimpan untuk {len(ids)} baris."
                            st.rerun()

with tab2:
    cg = st.text_input("Cari grup", key="cg")
    g = grup[grup["nama_grup"].str.contains(cg, case=False, regex=False)] if cg else grup
    st.dataframe(g, hide_index=True, width="stretch",
                 column_config={"total_plafon": st.column_config.NumberColumn(
                     "Total plafon", format="Rp %d")})
    if len(g):
        nama = g.set_index("kd_group")["nama_grup"]
        pilih = st.selectbox("Lihat anggota grup", g["kd_group"],
                             format_func=lambda k: f"{k} — {nama[k]}")
        st.dataframe(cust[cust["kd_group"] == pilih][["nama_customer", "cara_bayar", "jumlah_jobsite", "plafon"]],
                     hide_index=True, width="stretch", column_config=PLAFON)

with tab3:
    ws = sambung()
    if not bisa_ubah:
        st.info("Peran Anda hanya dapat melihat data.")
    elif ws is None:
        st.info("Mode lokal: penambahan pelanggan aktif setelah aplikasi terhubung ke Google Sheets.")
    else:
        # key berubah setelah sukses supaya isian form kosong lagi
        with st.form(f"tambah_{st.session_state.get('n_tambah', 0)}"):
            c1, c2 = st.columns(2)
            nama = c1.text_input("Nama customer *")
            jobsite = c2.text_input("Jobsite / cabang (opsional)")
            alamat = st.text_input("Alamat")
            c3, c4, c5 = st.columns(3)
            wilayah = c3.text_input("Wilayah")
            kota = c4.text_input("Kota")
            grup_in = c5.text_input("Kode grup (kosong = grup sendiri)")
            c6, c7, c8 = st.columns(3)
            telp = c6.text_input("Telepon")
            kontak = c7.text_input("Kontak")
            npwp = c8.text_input("NPWP")
            c9, c10, c11 = st.columns(3)
            cb = c9.selectbox("Cara bayar", ["Tunai", "Kredit"])
            jt = c10.number_input("Jatuh tempo (hari)", min_value=0, step=1)
            plafon = c11.number_input("Plafon kredit (Rp)", min_value=0, step=1_000_000)
            c12, c13 = st.columns([1, 2])
            status = c12.selectbox("Status", STATUS)
            kode = c13.text_input("Kode customer (kosong = dibuat otomatis, CRM-0001 dst.)")
            catatan = st.text_area("Catatan")

            if st.form_submit_button("Tambah"):
                nama = nama.strip()
                ada = df[df["nama_customer"].map(kunci_nama) == kunci_nama(nama)]
                if not nama:
                    st.error("Nama customer wajib diisi.")
                elif cb == "Tunai" and plafon > 0:
                    st.error("Plafon hanya untuk pembayaran kredit.")
                elif cb == "Kredit" and not ada.empty and ada["plafon"].max() not in (0, plafon):
                    st.error(f"Customer ini sudah ada dengan plafon {rp(ada['plafon'].max())}. "
                             "Plafon berlaku per nama customer, samakan angkanya.")
                else:
                    j = jobsite.strip()
                    rec = {"id": kode.strip(), "nama_customer": nama,
                           "nama_jobsite": f"{nama} - {j}" if j else nama,
                           "alamat": alamat.strip(), "wilayah": wilayah.strip(), "kota": kota.strip(),
                           "jobsite": j, "telp": telp.strip(), "kontak": kontak.strip(),
                           "npwp": npwp.strip(), "tk": "T" if cb == "Tunai" else "K",
                           "jt_tempo": int(jt), "plafon": int(plafon), "kd_group": grup_in.strip(),
                           "status": status, "catatan": catatan.strip(), "terakhir_dihubungi": ""}
                    try:
                        kode_baru = tambah_pelanggan(ws, rec)
                    except Exception as e:
                        st.error(f"Gagal menyimpan: {e}")
                    else:
                        muat.clear()
                        st.session_state["n_tambah"] = st.session_state.get("n_tambah", 0) + 1
                        st.session_state["pesan"] = f"Pelanggan ditambahkan (kode {kode_baru})."
                        st.rerun()

if len(tabs) > 3:  # tab khusus admin
    with tabs[3]:
        if ws_p is None:
            st.info("Manajemen pengguna aktif setelah aplikasi terhubung ke Google Sheets.")
        else:
            users = pd.DataFrame(baca(ws_p))
            st.dataframe(users[["username", "nama", "peran", "aktif", "gagal", "terkunci_hingga", "dibuat"]],
                         hide_index=True, width="stretch")

            st.markdown("**Tambah pengguna**")
            with st.form(f"user_baru_{st.session_state.get('n_user', 0)}"):
                c1, c2, c3 = st.columns(3)
                u = c1.text_input("Username")
                n = c2.text_input("Nama")
                r = c3.selectbox("Peran", PERAN, index=1)
                s = st.text_input("Kata sandi awal (minimal 8 karakter)", type="password")
                if st.form_submit_button("Tambah pengguna"):
                    try:
                        tambah_pengguna(ws_p, u, n, r, s)
                    except ValueError as e:
                        st.error(str(e))
                    except Exception as e:
                        st.error(f"Gagal menyimpan: {e}")
                    else:
                        st.session_state["n_user"] = st.session_state.get("n_user", 0) + 1
                        st.session_state["pesan"] = f"Pengguna {u.strip().lower()} ditambahkan."
                        st.rerun()

            st.markdown("**Ubah pengguna**")
            pilih = st.selectbox("Pengguna", users["username"].tolist())
            kini = users[users["username"] == pilih].iloc[0]
            with st.form(f"ubah_{pilih}"):
                peran_b = st.selectbox("Peran", PERAN,
                                       index=PERAN.index(kini["peran"]) if kini["peran"] in PERAN else 1)
                aktif_b = st.checkbox("Aktif", value=str(kini["aktif"]).strip().lower() == "ya")
                buka = st.checkbox("Buka kunci akun (hapus hitungan salah sandi)")
                sandi_b = st.text_input("Kata sandi baru (kosongkan jika tidak diganti)", type="password")
                if st.form_submit_button("Simpan perubahan"):
                    if pilih == pengguna["username"] and (peran_b != "admin" or not aktif_b):
                        st.error("Anda tidak dapat menurunkan atau menonaktifkan akun Anda sendiri.")
                    else:
                        try:
                            if sandi_b:
                                cek_kekuatan(sandi_b)
                            isi = {"peran": peran_b, "aktif": "ya" if aktif_b else "tidak"}
                            if buka:
                                isi.update({"gagal": 0, "terkunci_hingga": ""})
                            edit_kolom(ws_p, [pilih], isi, kolom_kunci="username")
                            if sandi_b:
                                ganti_sandi(ws_p, pilih, sandi_b)
                        except ValueError as e:
                            st.error(str(e))
                        except Exception as e:
                            st.error(f"Gagal menyimpan: {e}")
                        else:
                            st.session_state["pesan"] = f"Perubahan untuk {pilih} tersimpan."
                            st.rerun()
