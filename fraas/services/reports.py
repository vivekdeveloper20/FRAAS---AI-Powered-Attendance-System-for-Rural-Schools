from datetime import date
from typing import Dict

from ..models import Attendance, Student


def get_daily_summary(on_date: date) -> Dict[str, int]:
    total_students = Student.query.count()
    present = Attendance.query.filter_by(date=on_date, status="Present").count()
    absent = max(total_students - present, 0)
    return {"total": total_students, "present": present, "absent": absent}


