from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

DATE_FMT = "%Y-%m-%d %H:%M"


class HMSValidationError(ValueError):
    """Raised for validation problems that should be shown to the user."""


def _require_non_empty(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise HMSValidationError(f"{field_name} must be a non-empty string.")
    return value.strip()


def _require_int(value: str, field_name: str, min_value: int = 0, max_value: int = 150) -> int:
    try:
        v = int(value)
    except Exception as e:
        raise HMSValidationError(f"{field_name} must be an integer.") from e
    if v < min_value or v > max_value:
        raise HMSValidationError(f"{field_name} must be between {min_value} and {max_value}.")
    return v


def _parse_datetime(dt_str: str) -> datetime:
    dt_str = _require_non_empty(dt_str, "Date/time")
    try:
        return datetime.strptime(dt_str, DATE_FMT)
    except Exception as e:
        raise HMSValidationError(f"Invalid date/time. Use format: YYYY-MM-DD HH:MM (e.g., 2026-02-22 14:30)") from e


def _yes_no(value: str, field_name: str = "Availability") -> bool:
    value = _require_non_empty(value, field_name).lower()
    if value in {"y", "yes", "true", "1"}:
        return True
    if value in {"n", "no", "false", "0"}:
        return False
    raise HMSValidationError(f"{field_name} must be yes/no (y/n).")


def _pipe_escape(text: str) -> str:
    return text.replace("|", "/")  # simple: prevent delimiter breaking the file


@dataclass
class Patient:
    patient_id: str
    name: str
    age: int
    gender: str
    disease: str
    visit_history: List[str] = field(default_factory=list)

    def validate(self) -> None:
        self.patient_id = _require_non_empty(self.patient_id, "Patient ID")
        self.name = _require_non_empty(self.name, "Name")
        if not isinstance(self.age, int) or self.age < 0 or self.age > 150:
            raise HMSValidationError("Age must be between 0 and 150.")
        self.gender = _require_non_empty(self.gender, "Gender")
        self.disease = _require_non_empty(self.disease, "Disease")

    def to_row(self) -> str:
        history = ";".join(_pipe_escape(x) for x in self.visit_history)
        return "|".join([
            _pipe_escape(self.patient_id),
            _pipe_escape(self.name),
            str(self.age),
            _pipe_escape(self.gender),
            _pipe_escape(self.disease),
            history
        ])

    @staticmethod
    def from_row(row: str) -> "Patient":
        parts = row.rstrip("\n").split("|")
        # patient_id|name|age|gender|disease|visit_history
        if len(parts) < 5:
            raise HMSValidationError("Corrupted patients.txt row.")
        patient_id, name, age_s, gender, disease = parts[:5]
        history = parts[5] if len(parts) > 5 else ""
        visit_history = [x for x in history.split(";") if x] if history else []
        return Patient(patient_id=patient_id, name=name, age=int(age_s), gender=gender, disease=disease, visit_history=visit_history)


@dataclass
class Doctor:
    doctor_id: str
    name: str
    age: int
    gender: str
    specialty: str
    availability: bool = True

    def validate(self) -> None:
        self.doctor_id = _require_non_empty(self.doctor_id, "Doctor ID")
        self.name = _require_non_empty(self.name, "Name")
        if not isinstance(self.age, int) or self.age < 18 or self.age > 100:
            raise HMSValidationError("Doctor age must be between 18 and 100.")
        self.gender = _require_non_empty(self.gender, "Gender")
        self.specialty = _require_non_empty(self.specialty, "Specialty")
        if not isinstance(self.availability, bool):
            raise HMSValidationError("Availability must be True/False.")

    def to_row(self) -> str:
        return "|".join([
            _pipe_escape(self.doctor_id),
            _pipe_escape(self.name),
            str(self.age),
            _pipe_escape(self.gender),
            _pipe_escape(self.specialty),
            "1" if self.availability else "0",
        ])

    @staticmethod
    def from_row(row: str) -> "Doctor":
        parts = row.rstrip("\n").split("|")
        # doctor_id|name|age|gender|specialty|availability
        if len(parts) < 6:
            raise HMSValidationError("Corrupted doctors.txt row.")
        doctor_id, name, age_s, gender, specialty, avail_s = parts[:6]
        availability = avail_s.strip() == "1"
        return Doctor(doctor_id=doctor_id, name=name, age=int(age_s), gender=gender, specialty=specialty, availability=availability)


@dataclass
class Appointment:
    appointment_id: str
    patient_id: str
    doctor_id: str
    appointment_dt: datetime

    def validate(self) -> None:
        self.appointment_id = _require_non_empty(self.appointment_id, "Appointment ID")
        self.patient_id = _require_non_empty(self.patient_id, "Patient ID")
        self.doctor_id = _require_non_empty(self.doctor_id, "Doctor ID")
        if not isinstance(self.appointment_dt, datetime):
            raise HMSValidationError("Appointment date/time is invalid.")

    def to_row(self) -> str:
        return "|".join([
            _pipe_escape(self.appointment_id),
            _pipe_escape(self.patient_id),
            _pipe_escape(self.doctor_id),
            self.appointment_dt.strftime(DATE_FMT),
        ])

    @staticmethod
    def from_row(row: str) -> "Appointment":
        parts = row.rstrip("\n").split("|")
        # appointment_id|patient_id|doctor_id|appointment_dt
        if len(parts) < 4:
            raise HMSValidationError("Corrupted appointments.txt row.")
        appt_id, patient_id, doctor_id, dt_s = parts[:4]
        return Appointment(appointment_id=appt_id, patient_id=patient_id, doctor_id=doctor_id, appointment_dt=datetime.strptime(dt_s, DATE_FMT))


class HospitalSystem:
    def __init__(self) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)

        self.patients: Dict[str, Patient] = {}
        self.doctors: Dict[str, Doctor] = {}
        self.appointments: Dict[str, Appointment] = {}

        self._patients_file = DATA_DIR / "patients.txt"
        self._doctors_file = DATA_DIR / "doctors.txt"
        self._appointments_file = DATA_DIR / "appointments.txt"

        self.load_all()

    # ------------------------ Persistence ------------------------
    def load_all(self) -> None:
        self.patients = self._load_patients()
        self.doctors = self._load_doctors()
        self.appointments = self._load_appointments()

    def save_all(self) -> None:
        self._save_patients()
        self._save_doctors()
        self._save_appointments()

    def _load_lines(self, path: Path) -> List[str]:
        if not path.exists():
            return []
        return [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip() and not ln.startswith("#")]

    def _write_lines(self, path: Path, header: str, lines: List[str]) -> None:
        content = [f"# {header}", f"# delimiter: |", ""]
        content.extend(lines)
        path.write_text("\n".join(content) + "\n", encoding="utf-8")

    def _load_patients(self) -> Dict[str, Patient]:
        items: Dict[str, Patient] = {}
        for ln in self._load_lines(self._patients_file):
            p = Patient.from_row(ln)
            items[p.patient_id] = p
        return items

    def _save_patients(self) -> None:
        lines = [p.to_row() for p in self.patients.values()]
        self._write_lines(self._patients_file, "patients.txt: patient_id|name|age|gender|disease|visit_history(; separated)", lines)

    def _load_doctors(self) -> Dict[str, Doctor]:
        items: Dict[str, Doctor] = {}
        for ln in self._load_lines(self._doctors_file):
            d = Doctor.from_row(ln)
            items[d.doctor_id] = d
        return items

    def _save_doctors(self) -> None:
        lines = [d.to_row() for d in self.doctors.values()]
        self._write_lines(self._doctors_file, "doctors.txt: doctor_id|name|age|gender|specialty|availability(1/0)", lines)

    def _load_appointments(self) -> Dict[str, Appointment]:
        items: Dict[str, Appointment] = {}
        for ln in self._load_lines(self._appointments_file):
            a = Appointment.from_row(ln)
            items[a.appointment_id] = a
        return items

    def _save_appointments(self) -> None:
        lines = [a.to_row() for a in self.appointments.values()]
        self._write_lines(self._appointments_file, "appointments.txt: appointment_id|patient_id|doctor_id|appointment_dt(YYYY-MM-DD HH:MM)", lines)

    # ------------------------ Helpers ------------------------
    def _print_header(self, title: str) -> None:
        print("\n" + "=" * 60)
        print(title)
        print("=" * 60)

    def _prompt(self, msg: str) -> str:
        return input(msg).strip()

    def _pause(self) -> None:
        input("\nPress Enter to continue...")

    def _print_kv(self, pairs: List[Tuple[str, str]]) -> None:
        for k, v in pairs:
            print(f"- {k}: {v}")

    def _require_unique_id(self, _id: str, existing: Dict[str, object], label: str) -> None:
        if _id in existing:
            raise HMSValidationError(f"{label} '{_id}' already exists.")

    # ------------------------ Patient Ops ------------------------
    def add_patient(self) -> None:
        self._print_header("Add Patient")
        pid = _require_non_empty(self._prompt("Patient ID: "), "Patient ID")
        self._require_unique_id(pid, self.patients, "Patient ID")
        name = _require_non_empty(self._prompt("Name: "), "Name")
        age = _require_int(self._prompt("Age: "), "Age", 0, 150)
        gender = _require_non_empty(self._prompt("Gender: "), "Gender")
        disease = _require_non_empty(self._prompt("Disease: "), "Disease")
        p = Patient(patient_id=pid, name=name, age=age, gender=gender, disease=disease)
        p.validate()
        self.patients[pid] = p
        self._save_patients()
        print("✅ Patient added.")

    def list_patients(self) -> None:
        self._print_header("Patients")
        if not self.patients:
            print("No patients found.")
            return
        for p in self.patients.values():
            print(f"- {p.patient_id}: {p.name} ({p.age}, {p.gender}) | Disease: {p.disease}")

    def view_patient(self) -> None:
        self._print_header("View Patient")
        pid = _require_non_empty(self._prompt("Patient ID: "), "Patient ID")
        p = self.patients.get(pid)
        if not p:
            print("❌ Patient not found.")
            return
        self._print_kv([
            ("Patient ID", p.patient_id),
            ("Name", p.name),
            ("Age", str(p.age)),
            ("Gender", p.gender),
            ("Disease", p.disease),
            ("Visit history", ", ".join(p.visit_history) if p.visit_history else "(none)"),
        ])

    def update_patient(self) -> None:
        self._print_header("Update Patient")
        pid = _require_non_empty(self._prompt("Patient ID: "), "Patient ID")
        p = self.patients.get(pid)
        if not p:
            print("❌ Patient not found.")
            return
        print("Leave blank to keep the current value.")
        name = self._prompt(f"Name [{p.name}]: ") or p.name
        age_s = self._prompt(f"Age [{p.age}]: ")
        age = p.age if not age_s else _require_int(age_s, "Age", 0, 150)
        gender = self._prompt(f"Gender [{p.gender}]: ") or p.gender
        disease = self._prompt(f"Disease [{p.disease}]: ") or p.disease
        p.name, p.age, p.gender, p.disease = name, age, gender, disease
        p.validate()
        self._save_patients()
        print("✅ Patient updated.")

    def delete_patient(self) -> None:
        self._print_header("Delete Patient")
        pid = _require_non_empty(self._prompt("Patient ID: "), "Patient ID")
        if pid not in self.patients:
            print("❌ Patient not found.")
            return
        # Also remove appointments for this patient
        removed_appts = [aid for aid, a in self.appointments.items() if a.patient_id == pid]
        for aid in removed_appts:
            del self.appointments[aid]
        del self.patients[pid]
        self._save_patients()
        self._save_appointments()
        print(f"✅ Patient deleted. Removed {len(removed_appts)} related appointment(s).")

    # ------------------------ Doctor Ops ------------------------
    def add_doctor(self) -> None:
        self._print_header("Add Doctor")
        did = _require_non_empty(self._prompt("Doctor ID: "), "Doctor ID")
        self._require_unique_id(did, self.doctors, "Doctor ID")
        name = _require_non_empty(self._prompt("Name: "), "Name")
        age = _require_int(self._prompt("Age: "), "Age", 18, 100)
        gender = _require_non_empty(self._prompt("Gender: "), "Gender")
        specialty = _require_non_empty(self._prompt("Specialty: "), "Specialty")
        availability = _yes_no(self._prompt("Available now? (y/n): "), "Availability")
        d = Doctor(doctor_id=did, name=name, age=age, gender=gender, specialty=specialty, availability=availability)
        d.validate()
        self.doctors[did] = d
        self._save_doctors()
        print("✅ Doctor added.")

    def list_doctors(self) -> None:
        self._print_header("Doctors")
        if not self.doctors:
            print("No doctors found.")
            return
        for d in self.doctors.values():
            avail = "Available" if d.availability else "Not available"
            print(f"- {d.doctor_id}: Dr. {d.name} | {d.specialty} | {avail}")

    def view_doctor(self) -> None:
        self._print_header("View Doctor")
        did = _require_non_empty(self._prompt("Doctor ID: "), "Doctor ID")
        d = self.doctors.get(did)
        if not d:
            print("❌ Doctor not found.")
            return
        self._print_kv([
            ("Doctor ID", d.doctor_id),
            ("Name", d.name),
            ("Age", str(d.age)),
            ("Gender", d.gender),
            ("Specialty", d.specialty),
            ("Availability", "Yes" if d.availability else "No"),
        ])

    def update_doctor(self) -> None:
        self._print_header("Update Doctor")
        did = _require_non_empty(self._prompt("Doctor ID: "), "Doctor ID")
        d = self.doctors.get(did)
        if not d:
            print("❌ Doctor not found.")
            return
        print("Leave blank to keep the current value.")
        name = self._prompt(f"Name [{d.name}]: ") or d.name
        age_s = self._prompt(f"Age [{d.age}]: ")
        age = d.age if not age_s else _require_int(age_s, "Age", 18, 100)
        gender = self._prompt(f"Gender [{d.gender}]: ") or d.gender
        specialty = self._prompt(f"Specialty [{d.specialty}]: ") or d.specialty
        avail_s = self._prompt(f"Available? (y/n) [{'y' if d.availability else 'n'}]: ")
        availability = d.availability if not avail_s else _yes_no(avail_s, "Availability")
        d.name, d.age, d.gender, d.specialty, d.availability = name, age, gender, specialty, availability
        d.validate()
        self._save_doctors()
        print("✅ Doctor updated.")

    def delete_doctor(self) -> None:
        self._print_header("Delete Doctor")
        did = _require_non_empty(self._prompt("Doctor ID: "), "Doctor ID")
        if did not in self.doctors:
            print("❌ Doctor not found.")
            return
        # Remove appointments for this doctor
        removed_appts = [aid for aid, a in self.appointments.items() if a.doctor_id == did]
        for aid in removed_appts:
            del self.appointments[aid]
        del self.doctors[did]
        self._save_doctors()
        self._save_appointments()
        print(f"✅ Doctor deleted. Removed {len(removed_appts)} related appointment(s).")

    # ------------------------ Appointment Ops ------------------------
    def _doctor_has_conflict(self, doctor_id: str, when: datetime, ignore_appt_id: Optional[str] = None) -> bool:
        for aid, a in self.appointments.items():
            if ignore_appt_id and aid == ignore_appt_id:
                continue
            if a.doctor_id == doctor_id and a.appointment_dt == when:
                return True
        return False

    def book_appointment(self) -> None:
        self._print_header("Book Appointment")
        appt_id = _require_non_empty(self._prompt("Appointment ID: "), "Appointment ID")
        self._require_unique_id(appt_id, self.appointments, "Appointment ID")

        pid = _require_non_empty(self._prompt("Patient ID: "), "Patient ID")
        if pid not in self.patients:
            raise HMSValidationError("Patient does not exist. Add the patient first.")

        did = _require_non_empty(self._prompt("Doctor ID: "), "Doctor ID")
        doc = self.doctors.get(did)
        if not doc:
            raise HMSValidationError("Doctor does not exist. Add the doctor first.")
        if not doc.availability:
            raise HMSValidationError("Doctor is marked as not available.")

        when = _parse_datetime(self._prompt("Appointment date/time (YYYY-MM-DD HH:MM): "))
        if self._doctor_has_conflict(did, when):
            raise HMSValidationError("Scheduling conflict: this doctor already has an appointment at that time.")

        a = Appointment(appointment_id=appt_id, patient_id=pid, doctor_id=did, appointment_dt=when)
        a.validate()
        self.appointments[appt_id] = a

        # Add a small note to visit history
        self.patients[pid].visit_history.append(f"Appointment {appt_id} with Dr.{doc.name} @ {when.strftime(DATE_FMT)}")
        self._save_appointments()
        self._save_patients()
        print("✅ Appointment booked.")

    def list_appointments(self) -> None:
        self._print_header("Appointments")
        if not self.appointments:
            print("No appointments found.")
            return
        # Sort by datetime
        appts = sorted(self.appointments.values(), key=lambda x: x.appointment_dt)
        for a in appts:
            p = self.patients.get(a.patient_id)
            d = self.doctors.get(a.doctor_id)
            p_name = p.name if p else a.patient_id
            d_name = d.name if d else a.doctor_id
            print(f"- {a.appointment_id}: {a.appointment_dt.strftime(DATE_FMT)} | Patient: {p_name} | Doctor: Dr. {d_name}")

    def cancel_appointment(self) -> None:
        self._print_header("Cancel Appointment")
        appt_id = _require_non_empty(self._prompt("Appointment ID: "), "Appointment ID")
        a = self.appointments.get(appt_id)
        if not a:
            print("❌ Appointment not found.")
            return
        del self.appointments[appt_id]
        self._save_appointments()
        print("✅ Appointment canceled.")

    # ------------------------ Menus ------------------------
    def run(self) -> None:
        while True:
            try:
                self._print_header("🏥 Hospital Management System (Simple)")
                print("1) Patients")
                print("2) Doctors")
                print("3) Appointments")
                print("4) Save & Exit")
                choice = self._prompt("\nSelect: ")

                if choice == "1":
                    self._patients_menu()
                elif choice == "2":
                    self._doctors_menu()
                elif choice == "3":
                    self._appointments_menu()
                elif choice == "4":
                    self.save_all()
                    print("👋 Goodbye!")
                    return
                else:
                    print("Invalid choice.")
                    self._pause()

            except HMSValidationError as e:
                print(f"❌ {e}")
                self._pause()
            except KeyboardInterrupt:
                print("\n\n👋 Exiting...")
                self.save_all()
                return
            except Exception as e:
                # Keep the system from crashing unexpectedly
                print(f"⚠️ Unexpected error: {e}")
                self._pause()

    def _patients_menu(self) -> None:
        while True:
            self._print_header("Patients Menu")
            print("1) Add patient")
            print("2) List patients")
            print("3) View patient")
            print("4) Update patient")
            print("5) Delete patient")
            print("6) Back")
            c = self._prompt("\nSelect: ")
            try:
                if c == "1":
                    self.add_patient(); self._pause()
                elif c == "2":
                    self.list_patients(); self._pause()
                elif c == "3":
                    self.view_patient(); self._pause()
                elif c == "4":
                    self.update_patient(); self._pause()
                elif c == "5":
                    self.delete_patient(); self._pause()
                elif c == "6":
                    return
                else:
                    print("Invalid choice."); self._pause()
            except HMSValidationError as e:
                print(f"❌ {e}"); self._pause()

    def _doctors_menu(self) -> None:
        while True:
            self._print_header("Doctors Menu")
            print("1) Add doctor")
            print("2) List doctors")
            print("3) View doctor")
            print("4) Update doctor")
            print("5) Delete doctor")
            print("6) Back")
            c = self._prompt("\nSelect: ")
            try:
                if c == "1":
                    self.add_doctor(); self._pause()
                elif c == "2":
                    self.list_doctors(); self._pause()
                elif c == "3":
                    self.view_doctor(); self._pause()
                elif c == "4":
                    self.update_doctor(); self._pause()
                elif c == "5":
                    self.delete_doctor(); self._pause()
                elif c == "6":
                    return
                else:
                    print("Invalid choice."); self._pause()
            except HMSValidationError as e:
                print(f"❌ {e}"); self._pause()

    def _appointments_menu(self) -> None:
        while True:
            self._print_header("Appointments Menu")
            print("1) Book appointment")
            print("2) List appointments")
            print("3) Cancel appointment")
            print("4) Back")
            c = self._prompt("\nSelect: ")
            try:
                if c == "1":
                    self.book_appointment(); self._pause()
                elif c == "2":
                    self.list_appointments(); self._pause()
                elif c == "3":
                    self.cancel_appointment(); self._pause()
                elif c == "4":
                    return
                else:
                    print("Invalid choice."); self._pause()
            except HMSValidationError as e:
                print(f"❌ {e}"); self._pause()
