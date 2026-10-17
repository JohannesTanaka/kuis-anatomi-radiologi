import csv
import re
import unicodedata
from datetime import datetime
from pathlib import Path

import streamlit as st
from PIL import Image

BASE = Path(__file__).parent
IMAGE_PATH = BASE / "gambar_tengkorak.png"
KEY_PATH = BASE / "kunci_jawaban.csv"
RESULTS_PATH = BASE / "hasil_kuis_lokal.csv"

st.set_page_config(page_title="Kuis Anatomi Radiologi", page_icon="🩻", layout="wide")

# Sticky image panel: remains visible while the participant scrolls through answers.
st.markdown("""
<style>
/* Keep the reference image fixed in the viewport while the answer form scrolls. */
.st-key-image_panel {
    position: fixed !important;
    top: 6.2rem !important;
    left: 7vw !important;
    width: min(34vw, 500px) !important;
    max-height: calc(100vh - 7.2rem) !important;
    overflow-y: auto !important;
    z-index: 1000 !important;
    background: var(--background-color, white);
    padding: 0.35rem 0.5rem 0.5rem 0.35rem;
    border-radius: 0.5rem;
}
.st-key-image_panel img {
    max-height: calc(100vh - 13rem) !important;
    width: 100% !important;
    object-fit: contain !important;
}
div[data-testid="stTextInput"] input {
    min-height: 2.2rem;
}
/* On narrow screens, return to a normal stacked layout to avoid covering answers. */
@media (max-width: 900px) {
    .st-key-image_panel {
        position: static !important;
        width: 100% !important;
        max-height: none !important;
        overflow: visible !important;
    }
    .st-key-image_panel img {
        max-height: 60vh !important;
    }
}
</style>
""", unsafe_allow_html=True)

def normalize(text):
    text = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode("ascii")
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()

def load_keys():
    keys = {}
    if not KEY_PATH.exists():
        return keys, "File kunci_jawaban.csv tidak ditemukan."
    try:
        with open(KEY_PATH, newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                qid = str(row.get("id", "")).strip()
                if not qid or str(row.get("aktif", "true")).strip().lower() not in ("true", "1", "yes", "ya"):
                    continue
                correct = str(row.get("jawaban_benar", "")).strip()
                if not correct:
                    continue
                alternatives = [x.strip() for x in str(row.get("alternatif_jawaban", "") or "").split("|") if x.strip()]
                keys[qid] = {
                    "pertanyaan": str(row.get("pertanyaan", "")).strip(),
                    "jawaban_benar": correct,
                    "alternatif": alternatives,
                    "poin": max(1, int(float(row.get("poin") or 1))),
                }
        return keys, None
    except Exception as e:
        return {}, f"Gagal membaca kunci_jawaban.csv: {e}"

def answer_matches(response, item):
    accepted = [item["jawaban_benar"]] + item["alternatif"]
    return normalize(response) in {normalize(x) for x in accepted if normalize(x)}

def save_result(result):
    exists = RESULTS_PATH.exists()
    with open(RESULTS_PATH, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(result.keys()))
        if not exists:
            writer.writeheader()
        writer.writerow(result)

st.title("Kuis Anatomi Radiologi")
st.write("Gambar referensi tetap terlihat di sisi kiri saat kamu menggulir daftar jawaban di sisi kanan.")

keys, error = load_keys()
if error:
    st.error(error)
    st.stop()
if not IMAGE_PATH.exists():
    st.error("File gambar_tengkorak.png tidak ditemukan di folder aplikasi.")
    st.stop()

exam_key = keys.get("jenis_pemeriksaan")
anatomy_keys = {n: keys.get(f"anatomi_{n:02d}") for n in range(1, 26)}

if "started" not in st.session_state:
    st.session_state.started = False
if "submitted" not in st.session_state:
    st.session_state.submitted = False

if not st.session_state.started:
    st.subheader("Mulai kuis")
    name = st.text_input("Nama peserta")
    st.image(Image.open(IMAGE_PATH), caption="Radiografi tengkorak dengan penanda nomor 1–25", width=560)
    if st.button("Mulai menjawab", type="primary"):
        if not name.strip():
            st.error("Masukkan nama peserta terlebih dahulu.")
        else:
            st.session_state.participant = name.strip()
            st.session_state.started = True
            st.rerun()

elif not st.session_state.submitted:
    st.subheader(f"Peserta: {st.session_state.participant}")
    st.caption("Isi jawaban di panel kanan. Gambar di panel kiri dirancang tetap terlihat saat halaman digulir.")
    image_col, form_col = st.columns([1.05, 1.25], gap="large")

    with image_col:
        with st.container(key="image_panel"):
            st.image(Image.open(IMAGE_PATH), caption="Gambar referensi • Nomor 1–25", use_container_width=True)
            st.caption("Gunakan nomor pada gambar untuk menjawab kolom di sebelah kanan.")

    with form_col:
        with st.form("quiz_answers"):
            st.markdown("### A. Jenis pemeriksaan")
            st.text_input("Apa jenis pemeriksaan pada gambar ini?", key="answer_exam", placeholder="Ketik jenis pemeriksaan...")

            st.markdown("### B. Struktur anatomi")
            st.caption("Tuliskan nama struktur untuk setiap nomor.")
            for n in range(1, 26):
                st.text_input(f"{n}. Struktur anatomi", key=f"answer_{n:02d}", placeholder=f"Jawaban nomor {n}...", label_visibility="visible")

            confirm = st.checkbox("Saya sudah memeriksa jawaban saya.")
            send = st.form_submit_button("Kirim jawaban dan lihat nilai", type="primary", use_container_width=True)

    if send:
        if not confirm:
            st.error("Centang konfirmasi sebelum mengirim jawaban.")
        else:
            detail = []
            total_points = 0
            earned_points = 0
            correct_count = 0

            if exam_key:
                response = st.session_state.get("answer_exam", "").strip()
                pts = exam_key["poin"]
                total_points += pts
                ok = answer_matches(response, exam_key)
                earned_points += pts if ok else 0
                correct_count += 1 if ok else 0
                detail.append({
                    "nomor": "Jenis pemeriksaan",
                    "pertanyaan": "Apa jenis pemeriksaan pada gambar ini?",
                    "jawaban_peserta": response,
                    "jawaban_benar": exam_key["jawaban_benar"],
                    "benar": ok,
                    "poin": pts if ok else 0,
                })

            for n in range(1, 26):
                item = anatomy_keys.get(n)
                if not item:
                    continue
                response = st.session_state.get(f"answer_{n:02d}", "").strip()
                pts = item["poin"]
                total_points += pts
                ok = answer_matches(response, item)
                earned_points += pts if ok else 0
                correct_count += 1 if ok else 0
                detail.append({
                    "nomor": n,
                    "pertanyaan": item["pertanyaan"] or f"Identifikasi struktur anatomi nomor {n}.",
                    "jawaban_peserta": response,
                    "jawaban_benar": item["jawaban_benar"],
                    "benar": ok,
                    "poin": pts if ok else 0,
                })

            if total_points == 0:
                st.error("Belum ada kunci jawaban aktif. Pengelola perlu mengisi kunci_jawaban.csv terlebih dahulu.")
            else:
                score = round(earned_points / total_points * 100, 2)
                result = {
                    "waktu": datetime.now().isoformat(timespec="seconds"),
                    "nama_peserta": st.session_state.participant,
                    "jumlah_soal_dinilai": len(detail),
                    "jawaban_benar": correct_count,
                    "nilai_persen": score,
                    "detail": " | ".join(f"{d['nomor']}={d['jawaban_peserta']}" for d in detail),
                }
                save_result(result)
                st.session_state.result = result
                st.session_state.detail = detail
                st.session_state.submitted = True
                st.rerun()

else:
    result = st.session_state.result
    detail = st.session_state.detail
    st.subheader("Hasil kuis")
    a, b, c = st.columns(3)
    a.metric("Nilai", f"{result['nilai_persen']:.2f}%")
    b.metric("Jawaban benar", f"{result['jawaban_benar']} / {result['jumlah_soal_dinilai']}")
    c.metric("Peserta", result["nama_peserta"])
    st.caption("Hasil lokal ditulis ke hasil_kuis_lokal.csv. Untuk hasil lintas peserta di hosting, perlu integrasi penyimpanan bersama.")
    st.markdown("## Pembahasan")
    for d in detail:
        with st.expander(f"{d['nomor']} — {'Benar' if d['benar'] else 'Perlu diperbaiki'}"):
            st.write("Jawaban Anda:", d["jawaban_peserta"] or "(kosong)")
            st.write("Kunci jawaban:", d["jawaban_benar"])
    if st.button("Kembali ke awal / peserta berikutnya", type="primary"):
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.rerun()

st.divider()
st.caption("Pastikan seluruh kunci jawaban anatomi diverifikasi dengan atlas atau sumber pengajaran sebelum kuis digunakan.")
