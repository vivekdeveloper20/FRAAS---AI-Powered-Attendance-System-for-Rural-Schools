# FRAAS - Facial Recognition Automated Attendance System

FRAAS is a web-based facial recognition attendance system designed for rural schools with limited infrastructure.
It uses a lightweight Flask backend, SQLite database, and OpenCV LBPH face recognition and is optimized to run on a single low-power machine (e.g., Windows laptop) entirely offline.

## Ownership Notice

- Project author: Alok Kumar (LPU)
- Signature text used in codebase: `Developed by Alok Kumar (LPU)`
- Attribution headers: `X-Project-Signature`, `X-Project-Author`, `X-Project-Origin`
- License: MIT (see LICENSE)

The project includes UI watermark, footer attribution, browser-console signature, and server response signature headers.

## 1. Requirements

- Python 3.10+ (recommended)
- A webcam attached to the device running FRAAS
- Windows or Linux

## 1.5. Important: Face Data Setup

⚠️ **NOTE FOR NEW INSTALLATIONS**: Face recognition data and trained models are **NOT included** in the repository for privacy and performance reasons.

When you first clone this project:

- ❌ The `instance/face_data/` folder (student face images) will NOT exist
- ❌ The `instance/models/lbph_model.yml` (trained recognition model) will NOT exist

**What to do:**

1. **First run**: The system will automatically create these folders
2. **Train new faces**: Follow section "4. Basic usage workflow" → Add students → Capture faces
3. **Or restore from backup**: If you have a backup of `instance/` folder from another machine, copy it to the project root

The application will work fine; you just need to capture student faces to train the model.

## 2. Install dependencies

Open a terminal in this folder:

```bash
cd "E:/LPU SEMESTER/SEMESTER 8/Capstone Project/Capstone Project"
python -m venv venv
venv\Scripts\activate  # On Linux/macOS: source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## 2.5. Enable commit protection hook (recommended)

This repo includes a pre-commit hook that blocks commits if key ownership signatures are removed.

```bash
git config core.hooksPath .githooks
```

Or on Windows PowerShell:

```powershell
./setup-hooks.ps1
```

## 3. Initialize database and admin user

Run the Flask app:

```bash
python run.py
```

Then open a browser and visit:

- `http://localhost:5000/init-admin` (one time only) to create the default admin:
  - username: `admin`
  - password: `admin123` (change later in DB or extend UI)

After this, go to `http://localhost:5000/login` and sign in.

## 4. Basic usage workflow

1. **Add students**
   - Login as admin.
   - Go to **Students**.
   - Click **Add Student**, fill Roll No, Name, Class, Section.
2. **Capture face images & train model**
   - In **Students** list, click **Capture Faces** for each student (camera must be available).
   - System captures ~20 face samples and trains/updates the LBPH model automatically.
3. **Take attendance**
   - Click **Attendance** in the top menu.
   - The live camera view opens; ask students to stand in front of the camera one by one.
   - FRAAS automatically marks attendance once per student per day (duplicate protection).
4. **View dashboard & reports**
   - **Dashboard** shows today’s present/absent counts.
   - **Reports** lets you export CSV by date and/or class.

## 5. Offline-first behaviour & sync

- All data (students, attendance, face images, LBPH model) is stored **locally** using SQLite and the `instance/` folder.
- The system works fully offline on the local machine.
- For future integration with a central school server, FRAAS exposes APIs under `/api`:
  - `GET /api/attendance/unsynced` – list unsynced attendance.
  - `POST /api/attendance/mark-synced` – mark a list of IDs as synced.
  - A separate sync script/service can call these when internet is available.

## 6. Configuration

Main settings are in `fraas/config.py`:

- Database URI (default: local SQLite)
- Paths for face data and models
- LBPH parameters
- Recognition confidence threshold
- Minimum interval between recognitions of the same face

You can override some settings via environment variables:

- `FRAAS_SECRET_KEY`
- `FRAAS_DATABASE_URI`
- `FRAAS_SYNC_ENDPOINT`

## 7. Notes for production deployment

- In production, run FRAAS behind a proper WSGI server (gunicorn, uWSGI) or a Windows service.
- Change the default admin password immediately.
- Regularly back up the `instance/` folder (database, faces, trained models, logs).


# FRAAS
