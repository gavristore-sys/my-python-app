import streamlit as st
import numpy as np
import cv2
from PIL import Image
import easyocr
import re  # Untuk pencarian teks (Regex)

st.set_page_config(page_title="AI PO Scanner", layout="wide")

st.title("📷 AI Purchase Order Scanner (Gambar & PDF)")
st.write("Unggah Scan PO (JPG/PNG/PDF) untuk mengisi formulir secara otomatis menggunakan AI.")

# Inisialisasi variabel formulir
no_po = ""
nama_customer = ""
harga = 0.0
volume = 0.0
text_data = [] # Untuk preview teks mentah

# 1. Fungsi OCR untuk Gambar (Scan)
def run_easyocr(image):
    reader = easyocr.Reader(['id', 'en']) # Membaca Bahasa Indonesia & Inggris
    result = reader.readtext(image, detail=0) # Mengembalikan hanya teksnya saja
    return result

# 2. Widget Upload File (Gambar & PDF)
uploaded_file = st.file_uploader("Unggah File PO", type=["jpg", "png", "jpeg", "pdf"])

if uploaded_file is not None:
    try:
        # Menampilkan indikator loading
        with st.spinner('Sedang memindai dan membaca dokumen...'):
            
            # Memproses jika PDF
            if uploaded_file.type == "application/pdf":
                st.warning("⚠️ Fitur OCR PDF membutuhkan library tambahan (pdfplumber + pdf2image) agar bisa berjalan penuh di Streamlit Cloud. Saat ini kita hanya mendemonstrasikan pembacaan PDF dasar via OCR.")
                
                # SEMENTARA: Kita anggap PDF adalah 1 halaman gambar utuh
                # (Untuk solusi PDF lengkap, butuh setup environment lebih lanjut di Cloud)
                
                # Baca halaman pertama PDF sebagai gambar
                from pdf2image import convert_from_bytes
                images = convert_from_bytes(uploaded_file.read(), fmt="jpeg")
                if images:
                    processed_image = images[0]
                    text_data = run_easyocr(processed_image)
                    # st.image(processed_image, caption="Halaman Pertama PDF", use_column_width=True) # Tampilkan preview
            
            # Memproses jika Gambar (JPG/PNG)
            else:
                processed_image = Image.open(uploaded_file)
                text_data = run_easyocr(processed_image)
                # st.image(processed_image, caption="Gambar yang Diunggah", use_column_width=True) # Tampilkan preview

            # --- LOGIKA PENGENALAN DATA PO ---
            full_text = " ".join(text_data) # Menggabungkan semua teks mentah

            # Contoh penggunaan Regex sederhana untuk mengekstrak data
            # (Silakan sesuaikan format Regex ini dengan pola PO kamu yang sebenarnya)
            
            # Pola No PO (misal: "PO-" diikuti angka)
            match_po = re.search(r'PO-?\d{3,}', full_text, re.IGNORECASE)
            if match_po: no_po = match_po.group(0)

            # Pola Harga (misal: mencari "Rp" diikuti angka)
            match_harga = re.search(r'(Rp\s?\d{1,3}(\.\d{3})*|\$\d{1,3}(\,\d{3})*)', full_text, re.IGNORECASE)
            if match_harga: 
                raw_harga = match_harga.group(0)
                # Bersihkan Rp/. untuk jadi float
                harga = float(re.sub(r'[^\d\.]', '', raw_harga))

            # Pola Qty (misal: angka diikuti satuan 'PCS' atau 'KG')
            match_vol = re.search(r'(\d+(\.\d{1,2})?)\s?(pcs|kg|mtr|unit)', full_text, re.IGNORECASE)
            if match_vol: 
                volume = float(match_vol.group(1))

            # Nama Customer: Pola ini biasanya paling sulit dideteksi dengan Regex sederhana
            # Coba cari nama yang ada di urutan teratas/header setelah judul
            if text_data:
                # Ambil baris teks pertama/kedua yang kemungkinan header customer
                potential_name = text_data[0:3]
                nama_customer = " / ".join(potential_name).strip()


            st.success("Teks dokumen berhasil dibaca!")
            
            # Tampilkan teks mentah hasil OCR untuk pengecekan
            with st.expander("Lihat Teks Mentah Hasil Scan"):
                for line in text_data:
                    st.write(line)

    except Exception as e:
        st.error(f"Terjadi kesalahan saat memproses file: {e}")

st.divider()

# 3. Form Input Informasi PO (Terisi Otomatis/Manual)
st.subheader("📝 Detail Informasi PO yang Dideteksi")

col1, col2 = st.columns(2)

with col1:
    po_input = st.text_input("Nomor PO", value=no_po)
    cust_input = st.text_input("Nama Customer", value=nama_customer)

with col2:
    harga_input = st.number_input("Total Harga", value=harga, format="%.2f")
    vol_input = st.number_input("Volume / Qty Utama", value=volume, format="%.2f")

# Tombol Simpan / Process
if st.button("Simpan Data PO", type="primary"):
    if po_input and cust_input:
        st.write("### Data yang Berhasil Disimpan:")
        st.json({
            "Nomor PO": po_input,
            "Nama Customer": cust_input,
            "Total Harga": harga_input,
            "Volume Utama": vol_input
        })
        st.success("Data PO telah disimpan!")
    else:
        st.error("Mohon lengkapi Nomor PO dan Nama Customer terlebih dahulu.")
