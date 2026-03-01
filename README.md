# Hospital Management System (Simple) — Python CLI

A small, beginner-friendly **Hospital Management System** implemented with **OOP** and **TXT file persistence**.

## Features
- Manage **Patients** (add/list/view/update/delete)
- Manage **Doctors** (add/list/view/update/delete)
- Manage **Appointments** (book/list/cancel)
- Validations:
  - IDs must be unique
  - Date/time format: `YYYY-MM-DD HH:MM`
  - Prevents double-booking the **same doctor** at the **same date/time**
  - Requires patient + doctor to exist before booking

## Run
```bash
python main.py
```

## Data files
Stored in `data/` as plain text (pipe-delimited):
- `patients.txt`
- `doctors.txt`
- `appointments.txt`

You can delete these files to reset the system.

## Notes
- This project is intentionally small and readable for learning.
- You can extend it by adding search, billing, rooms, etc.
