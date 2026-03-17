# JobStreet Semi-Auto Apply

Dokumen ini menjelaskan cara setup, menjalankan, dan memahami output fitur semi-auto apply JobStreet.

## Tujuan Fitur

Flow ini dipakai setelah application record sudah dibuat oleh pipeline utama. Bot akan:

1. Membuka URL lowongan JobStreet yang sudah tersimpan.
2. Memakai browser profile persisten agar session login bisa dipakai ulang.
3. Upload resume dan cover letter yang sudah dibuat pipeline.
4. Mengisi field profil standar bila datanya tersedia.
5. Menanyakan screening question yang belum punya jawaban.
6. Menyimpan jawaban ke database dan file markdown audit.
7. Berhenti di halaman review secara default, bukan submit otomatis.

V1 hanya mendukung JobStreet dan memang sengaja konservatif.

## Setup

### 1. Install dependency

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
playwright install chromium
```

### 2. Siapkan config

Copy config contoh:

```bash
cp config.example.json config.json
```

Field penting:

- `automation.enabled`: mengaktifkan fitur apply semi-auto.
- `automation.mode`: default `semi_auto`.
- `automation.headless`: default `false` supaya browser terlihat.
- `automation.stop_before_submit`: default `true` supaya flow berhenti di review page.
- `paths.browser_profile_dir`: lokasi browser profile persisten.
- `paths.automation_screenshots_dir`: lokasi screenshot apply.
- `computer_use.provider`: provider classifier state halaman, saat ini `gemini`.
- `computer_use.model`: model classifier yang dipakai.
- `applicant_profile.*`: data profil pelamar untuk autofill dan fallback jawaban.

### 3. Set API key

Gunakan environment variable atau `.env`, jangan commit secret ke repo.

```env
GEMINI_API_KEY=your_key_here
```

Alternatif:

```env
JAH_COMPUTER_USE_API_KEY=your_key_here
```

Kalau key pernah terekspos, rotate dulu sebelum dipakai real.

## Applicant Profile

`applicant_profile` dipakai untuk dua hal:

- mengisi field standar seperti nama, email, phone, location
- menjawab screening question sederhana kalau pertanyaannya cocok secara heuristic

Field yang tersedia:

- `full_name`
- `email`
- `phone`
- `location`
- `years_of_experience`
- `current_salary`
- `expected_salary`
- `notice_period`
- `work_authorization`

Kalau field kosong, bot tidak akan mengarang isiannya.

## Cara Pakai

### Opsi 1: interactive menu

```bash
python main.py
```

Pilih:

- `1` untuk membuat application record baru
- `4` untuk apply semi-auto ke JobStreet dari `application_id`

### Opsi 2: CLI

```bash
python main.py --config config.json apply 1
```

`1` adalah `application_id` yang sebelumnya sudah tersimpan di database.

## Urutan Flow

Saat `apply` dijalankan, sistem akan:

1. Mengambil record aplikasi dari SQLite.
2. Validasi URL harus mengandung JobStreet.
3. Validasi file resume harus ada.
4. Buka lowongan di browser persistent context Playwright.
5. Cek apakah user sudah login.
6. Klik tombol apply jika ditemukan.
7. Upload resume.
8. Upload cover letter jika file-nya ada.
9. Isi field profil standar.
10. Scan screening questions.
11. Cari jawaban dari cache database.
12. Kalau tidak ada, coba dari `applicant_profile`.
13. Kalau tetap tidak ada, tanya user via terminal.
14. Simpan jawaban dan event apply.
15. Deteksi state halaman akhir.
16. Simpan screenshot dan audit trail.
17. Berhenti di review page atau pause untuk intervensi user.

## Status Apply

Nilai `apply_status` yang mungkin muncul:

- `not_started`: belum pernah menjalankan apply flow.
- `draft_started`: flow sudah dimulai.
- `awaiting_user_input`: perlu login, CAPTCHA, atau jawaban manual.
- `ready_for_review`: semua langkah aman selesai dan flow berhenti di review page.
- `submitted`: reserved jika nanti mode submit aktif.
- `failed`: error fatal, misalnya file penting hilang atau browser flow gagal.
- `skipped`: reserved untuk kondisi skip yang disengaja.

## Audit Trail

Setiap apply attempt menyimpan data di dua tempat.

### Database

Table/field yang relevan:

- `applications.apply_status`
- `applications.apply_portal`
- `applications.apply_attempted_at`
- `applications.apply_error_reason`
- `applications.apply_review_url`
- `applications.apply_screenshot_path`
- `applications.screening_answers_json`
- table `screening_answers`
- table `apply_events`

### File output

Di folder lowongan yang sama dengan resume dan report akan dibuat:

- `screening-answers.md`

Isi file ini mencakup:

- daftar pertanyaan screening
- jawaban yang dipakai
- sumber jawaban: `cached_answer`, `config_default`, atau `user_input`
- waktu pencatatan
- event penting sepanjang flow apply

## Sumber Jawaban Screening

Prioritas sumber jawaban:

1. cache jawaban sebelumnya untuk `application_id` yang sama
2. heuristic mapping dari `applicant_profile`
3. input manual user di terminal

V1 tidak mengarang jawaban pakai AI generatif untuk screening question.

## Login dan Browser Profile

Fitur ini memakai persistent profile di:

- `paths.browser_profile_dir`

Artinya:

- sekali login di browser itu, session bisa dipakai ulang
- kalau JobStreet logout, flow akan pause dengan status `awaiting_user_input`
- setelah login manual selesai, jalankan lagi command apply

## Screenshot dan Debugging

Screenshot disimpan ke:

- `paths.automation_screenshots_dir`

Screenshot dibuat saat:

- flow pause
- flow gagal
- flow sukses sampai review page

Gunakan screenshot itu untuk cek apakah selector portal berubah atau ada popup tak terduga.

## Keterbatasan V1

- hanya untuk JobStreet
- selector masih heuristic dan bisa berubah kalau UI portal berubah
- belum ada resume otomatis setelah pause di tengah halaman yang sama
- belum ada multi-portal abstraction
- belum ada auto-submit default
- classifier Gemini saat ini hanya dipakai untuk bantu klasifikasi state yang tidak dikenali

## Troubleshooting

### Browser tidak bisa jalan

Pastikan Playwright terinstall:

```bash
pip install playwright
playwright install chromium
```

### Selalu diminta login

- pastikan `paths.browser_profile_dir` konsisten
- login langsung di browser yang dibuka flow
- jangan hapus folder profile kalau masih ingin reuse session

### Pertanyaan screening tidak terisi

Itu expected kalau:

- tidak ada jawaban cache
- `applicant_profile` tidak punya data cocok
- pertanyaannya butuh jawaban spesifik

Bot akan pause atau prompt ke terminal, lalu menyimpan jawaban itu untuk audit.

### Apply berhenti walau semua field terlihat sudah terisi

Kemungkinan:

- halaman review tidak terdeteksi selector/teksnya
- ada modal/popup yang menutupi form
- ada CAPTCHA atau verifikasi anti-bot

Cek screenshot terakhir dan event di `screening-answers.md`.

## File yang Relevan

- `job_app_helper/modules/jobstreet_apply.py`
- `job_app_helper/providers/computer_use.py`
- `job_app_helper/storage/repository.py`
- `job_app_helper/config.py`
- `main.py`
