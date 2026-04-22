from typing import List, Dict

from ..models import Attendance
from .. import db


def get_unsynced_attendance() -> List[Dict]:
    rows = Attendance.query.filter_by(synced=False).all()
    result = []
    for r in rows:
        result.append(
            {
                "id": r.id,
                "student_id": r.student_id,
                "date": r.date.isoformat(),
                "time": r.time.strftime("%H:%M:%S"),
                "status": r.status,
                "confidence": r.confidence,
            }
        )
    return result


def mark_synced(ids: List[int]) -> None:
    if not ids:
        return
    Attendance.query.filter(Attendance.id.in_(ids)).update({"synced": True}, synchronize_session=False)
    db.session.commit()


