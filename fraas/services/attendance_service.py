from datetime import date, datetime
from typing import Optional

from flask import current_app

from .. import db
from ..models import Attendance, Student
from .confirmation_service import get_confirmation_service


def mark_attendance_for_recognition(student_id: int, confidence: float, on_date: date) -> Optional[dict]:
    """
    Handle attendance marking for a recognized student.

    - If not yet marked today: create a new attendance record.
    - If already marked today: do NOT create a new record.

    Returns a dict describing the outcome or None if the student does not exist.
    Dict structure:
      {
        "student_id": int,
        "student_name": str,
        "roll_number": str,
        "class_name": str,
        "section": str | None,
        "confidence": float,
        "status": "marked" | "already_marked"
      }
    """
    if student_id == -1:
        confirmation_service = get_confirmation_service()
        confirmation_service.add_confirmation(-1, "Unknown", "N/A", on_date, status="unknown")
        return {
            "student_id": -1,
            "student_name": "Unknown",
            "roll_number": "N/A",
            "class_name": "N/A",
            "section": "N/A",
            "confidence": confidence,
            "status": "unknown"
        }

    student = Student.query.get(student_id)
    if not student:
        return None

    already_marked = Attendance.has_attendance_for(student_id, on_date)

    if not already_marked:
        import zoneinfo
        tz = zoneinfo.ZoneInfo("Asia/Kolkata")
        
        # Create a new attendance record
        now_dt = datetime.now(tz)
        rec = Attendance(
            student_id=student_id,
            date=on_date,
            time=now_dt.time(),
            status="Present",
            confidence=confidence,
            synced=False,
        )
        db.session.add(rec)
        db.session.commit()
        status = "marked"
        
        # Trigger SMS Notification safely
        try:
            from .sms_service import send_attendance_sms
            phone = student.phone if student.phone else ""
            if phone:
                now_str = now_dt.strftime("%I:%M %p")
                date_str = on_date.strftime("%B %d, %Y")
                import threading
                threading.Thread(
                    target=send_attendance_sms, 
                    args=(student.name, student.class_name, now_str, date_str, phone)
                ).start()
        except Exception as e:
            current_app.logger.error(f"Failed to initiate SMS thread: {e}")
            
        # Trigger Email Notification safely
        try:
            from .email_service import send_attendance_email
            email_address = student.email if student.email else ""
            if email_address:
                now_str = now_dt.strftime("%I:%M %p")
                import threading
                threading.Thread(
                    target=send_attendance_email, 
                    args=(student.name, now_str, email_address)
                ).start()
        except Exception as e:
            current_app.logger.error(f"Failed to initiate Email thread: {e}")
            
    else:
        # Do not create a new record; just signal that it already exists
        status = "already_marked"

    # Add confirmation for frontend feedback (subject to cooldown)
    confirmation_service = get_confirmation_service()
    confirmation_service.add_confirmation(
        student_id, student.name, student.roll_number, on_date, status=status, phone=student.phone or "", class_name=student.class_name or ""
    )

    return {
        "student_id": student_id,
        "student_name": student.name,
        "roll_number": student.roll_number,
        "class_name": student.class_name,
        "section": student.section,
        "confidence": confidence,
        "status": status,
    }


