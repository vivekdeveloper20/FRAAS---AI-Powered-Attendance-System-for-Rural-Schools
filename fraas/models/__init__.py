from datetime import datetime, date

from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from .. import db


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), default="Teacher")

    @property
    def is_admin(self):
        return self.role == "Admin"

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class Student(db.Model):
    __tablename__ = "students"

    id = db.Column(db.Integer, primary_key=True)
    roll_number = db.Column(db.String(32), unique=True, nullable=False)
    name = db.Column(db.String(128), nullable=False)
    class_name = db.Column(db.String(64), nullable=False)
    section = db.Column(db.String(16), nullable=True)
    email = db.Column(db.String(128), nullable=True)
    phone = db.Column(db.String(32), nullable=True)
    extra_data = db.Column(db.Text, nullable=True) # JSON string for unknown columns
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def full_class(self) -> str:
        return f"{self.class_name}{('-' + self.section) if self.section else ''}"


class Attendance(db.Model):
    __tablename__ = "attendance"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False)
    date = db.Column(db.Date, default=date.today, index=True)
    time = db.Column(db.Time, default=datetime.utcnow().time)
    status = db.Column(db.String(16), default="Present")
    confidence = db.Column(db.Float, nullable=True)
    synced = db.Column(db.Boolean, default=False, index=True)

    student = db.relationship("Student", backref=db.backref("attendance_records", lazy=True, cascade="all, delete-orphan"))

    @staticmethod
    def has_attendance_for(student_id: int, on_date: date) -> bool:
        return (
            Attendance.query.filter_by(student_id=student_id, date=on_date)
            .filter(Attendance.status == "Present")
            .first()
            is not None
        )


