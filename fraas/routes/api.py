from datetime import datetime
import io

import pandas as pd
from flask import Blueprint, jsonify, request, send_file
from flask_login import login_required

from .. import db
from ..models import Attendance, Student
from ..services.sync_service import get_unsynced_attendance, mark_synced

api_bp = Blueprint("api", __name__)


@api_bp.route("/attendance/unsynced")
@login_required
def api_unsynced_attendance():
    records = get_unsynced_attendance()
    return jsonify(records)


@api_bp.route("/attendance/mark-synced", methods=["POST"])
@login_required
def api_mark_synced():
    ids = request.json.get("ids", [])
    mark_synced(ids)
    return jsonify({"status": "ok", "count": len(ids)})


@api_bp.route("/reports/export")
@login_required
def export_report():
    """Export date-wise or class-wise attendance as CSV, Excel, or PDF."""
    date_str = request.args.get("date")
    class_name = request.args.get("class")
    fmt = request.args.get("format", "csv")

    query = Attendance.query.join(Student)

    if date_str:
        query = query.filter(Attendance.date == datetime.strptime(date_str, "%Y-%m-%d").date())
    if class_name:
        query = query.filter(Student.class_name == class_name)

    rows = []
    for rec in query.all():
        rows.append(
            {
                "Name": rec.student.name,
                "Roll Number": rec.student.roll_number,
                "Date": rec.date.isoformat(),
                "Time": rec.time.strftime("%H:%M:%S"),
                "Status": rec.status,
            }
        )
    df = pd.DataFrame(rows)
    
    if df.empty:
        df = pd.DataFrame(columns=["Name", "Roll Number", "Date", "Time", "Status"])
        
    file_name_base = f"attendance_{date_str or 'all'}"

    if fmt == "excel":
        buf = io.BytesIO()
        df.to_excel(buf, index=False)
        buf.seek(0)
        return send_file(
            buf,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name=f"{file_name_base}.xlsx"
        )
    elif fmt == "pdf":
        try:
            from fpdf import FPDF
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Arial", size=12)
            pdf.cell(200, 10, txt=f"Attendance Report - {date_str or 'All Dates'}", ln=1, align="C")
            pdf.ln(10)
            
            pdf.set_font("Arial", "B", 10)
            pdf.cell(50, 10, "Name", border=1)
            pdf.cell(30, 10, "Roll Number", border=1)
            pdf.cell(30, 10, "Date", border=1)
            pdf.cell(30, 10, "Time", border=1)
            pdf.cell(30, 10, "Status", border=1)
            pdf.ln()
            
            pdf.set_font("Arial", "", 10)
            for idx, row in df.iterrows():
                pdf.cell(50, 10, str(row['Name'])[:25], border=1)
                pdf.cell(30, 10, str(row['Roll Number'])[:10], border=1)
                pdf.cell(30, 10, str(row['Date']), border=1)
                pdf.cell(30, 10, str(row['Time']), border=1)
                pdf.cell(30, 10, str(row['Status']), border=1)
                pdf.ln()
                
            pdf_out = pdf.output(dest='S').encode('latin-1')
            buf = io.BytesIO(pdf_out)
        except ImportError:
            buf = io.BytesIO(b"PDF export not available. Please install fpdf2.")
            
        return send_file(
            buf,
            mimetype="application/pdf",
            as_attachment=True,
            download_name=f"{file_name_base}.pdf"
        )
    else:
        # Default CSV
        csv_data = df.to_csv(index=False)
        buf = io.BytesIO(csv_data.encode('utf-8'))
        return send_file(
            buf,
            mimetype="text/csv",
            as_attachment=True,
            download_name=f"{file_name_base}.csv",
        )

@api_bp.route("/dashboard/stats")
@login_required
def dashboard_stats():
    from datetime import date, timedelta
    today = date.today()
    
    total_students = Student.query.count()
    present_today = Attendance.query.filter_by(date=today, status="Present").count()
    absent_today = max(total_students - present_today, 0)
    
    # Calculate avg accuracy safely
    present_records = Attendance.query.filter_by(date=today, status="Present").all()
    total_conf = sum(r.confidence for r in present_records if r.confidence is not None)
    if present_records and len(present_records) > 0:
        accuracy = min(100.0, max(0.0, 100 - (total_conf / len(present_records))))
    else:
        accuracy = 100.0
        
    recent_logs = Attendance.query.order_by(Attendance.time.desc()).limit(15).all()
    logs_data = []
    for l in recent_logs:
        logs_data.append({
            "name": l.student.name,
            "status": "known" if l.status == "Present" else "unknown",
            "time_str": l.time.strftime("%I:%M:%S %p"),
            "msg": "marked present" if l.status == "Present" else "detected"
        })
        
    # Real Monthly trend (last 7 days of attendance)
    # Get last 7 days ending today
    date_list = [today - timedelta(days=x) for x in range(6, -1, -1)]
    monthly_labels = [d.strftime("%b %d") for d in date_list]
    monthly_data = []
    for d in date_list:
        monthly_data.append(Attendance.query.filter_by(date=d, status="Present").count())
        
    # Real Class-wise Performance
    # calculate total students per class
    classes = db.session.query(Student.class_name, db.func.count(Student.id)).group_by(Student.class_name).all()
    class_labels = []
    class_data = []
    for cls, total in classes:
        # present today
        present_in_cls = Attendance.query.join(Student).filter(
            Attendance.date == today,
            Attendance.status == "Present",
            Student.class_name == cls
        ).count()
        class_labels.append(f"Class {cls}")
        class_data.append(int(present_in_cls * 100 / total) if total > 0 else 0)
        
    return jsonify({
        "total_students": total_students,
        "present_today": present_today,
        "absent_today": absent_today,
        "accuracy": round(accuracy, 1),
        "recent_logs": logs_data,
        "monthly_labels": monthly_labels,
        "monthly_data": monthly_data,
        "class_labels": class_labels,
        "class_data": class_data
    })


