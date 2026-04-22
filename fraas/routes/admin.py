from datetime import date

from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user

from .. import db
from ..models import Student, Attendance
from ..services.reports import get_daily_summary
from ..ai.face_capture import capture_faces_for_student
from ..ai.face_trainer import train_model

admin_bp = Blueprint("admin", __name__)


@admin_bp.route("/")
@login_required
def dashboard():
    today = date.today()
    total_students = Student.query.count()
    today_present = Attendance.query.filter_by(date=today, status="Present").count()
    summary = get_daily_summary(today)
    return render_template(
        "dashboard.html",
        total_students=total_students,
        today_present=today_present,
        today_absent=total_students - today_present,
        summary=summary,
    )


@admin_bp.route("/students")
@login_required
def students_list():
    if not current_user.is_admin:
        flash("Access Denied: Admin only.", "danger")
        return redirect(url_for("admin.dashboard"))
    import os
    from flask import current_app
    
    students = Student.query.order_by(Student.class_name, Student.section, Student.roll_number).all()
    cfg = current_app.config
    
    for s in students:
        student_dir = os.path.join(cfg["FACE_DATA_DIR"], str(s.id))
        s.is_captured = False
        s.capture_count = 0
        if os.path.exists(student_dir):
            images = [f for f in os.listdir(student_dir) if f.endswith(('.png', '.jpg', '.jpeg'))]
            if images:
                s.is_captured = True
                s.capture_count = len(images)
                
    return render_template("students.html", students=students)


@admin_bp.route("/students/add", methods=["POST"])
@login_required
def students_add():
    if not current_user.is_admin:
        return redirect(url_for("admin.dashboard"))
    roll_number = request.form.get("roll_number", "").strip()
    name = request.form.get("name", "").strip()
    class_name = request.form.get("class_name", "").strip()
    section = request.form.get("section", "").strip()

    if not roll_number or not name or not class_name:
        flash("Roll number, name and class are required.", "danger")
        return redirect(url_for("admin.students_list"))

    if Student.query.filter_by(roll_number=roll_number).first():
        flash("Student with this roll number already exists.", "danger")
        return redirect(url_for("admin.students_list"))

    student = Student(
        roll_number=roll_number,
        name=name,
        class_name=class_name,
        section=section or None,
    )
    db.session.add(student)
    db.session.commit()
    flash("Student added. Please capture face samples.", "success")
    return redirect(url_for("admin.students_list"))


@admin_bp.route("/students/upload_csv", methods=["POST"])
@login_required
def students_upload_csv():
    if not current_user.is_admin:
        return redirect(url_for("admin.dashboard"))
    import pandas as pd
    import json
    
    if 'csv_file' not in request.files:
        flash("No file uploaded", "danger")
        return redirect(url_for("admin.students_list"))
        
    file = request.files['csv_file']
    if file.filename == '':
        flash("No file selected", "danger")
        return redirect(url_for("admin.students_list"))
        
    if not (file.filename.endswith('.csv') or file.filename.endswith('.xlsx')):
        flash("Only CSV and Excel (.xlsx) files are allowed.", "danger")
        return redirect(url_for("admin.students_list"))
        
    try:
        # Load with pandas for bulletproof CSV and Excel parsing
        if file.filename.endswith('.csv'):
            df = pd.read_csv(file, dtype=str)
        else:
            df = pd.read_excel(file, dtype=str)
            
        if df.empty:
            flash("The uploaded file is empty.", "warning")
            return redirect(url_for("admin.students_list"))
            
        # Strip string columns to avoid whitespace issues
        df = df.apply(lambda x: x.str.strip() if x.dtype == "object" else x)
        
        # Replace NaN with empty string
        df = df.fillna("")
            
        success_count = 0
        skipped_count = 0
        
        # Match expected headers dynamically
        columns = df.columns.tolist()
        name_col = next((c for c in columns if c and 'name' in c.lower()), None)
        roll_col = next((c for c in columns if c and 'roll' in c.lower()), None)
        class_col = next((c for c in columns if c and 'class' in c.lower()), None)
        sec_col = next((c for c in columns if c and 'section' in c.lower()), None)
        email_col = next((c for c in columns if c and 'email' in c.lower()), None)
        phone_col = next((c for c in columns if c and 'phone' in c.lower() or c and 'contact' in c.lower() or c and 'mobile' in c.lower()), None)
        
        if not name_col or not roll_col:
            flash("File must contain at least 'Name' and 'Roll' columns.", "danger")
            return redirect(url_for("admin.students_list"))
            
        # Discover completely extra columns to drop into JSON tracking
        known_cols = {name_col, roll_col, class_col, sec_col, email_col, phone_col}
        extra_cols = [c for c in columns if c not in known_cols]
        
        for _, row in df.iterrows():
            name = str(row[name_col]).strip() if name_col and row[name_col] else ""
            roll_number = str(row[roll_col]).strip() if roll_col and row[roll_col] else ""
            class_name = str(row[class_col]).strip() if class_col and row[class_col] else "Standard"
            section = str(row[sec_col]).strip() if sec_col and row[sec_col] else None
            email = str(row[email_col]).strip() if email_col and row[email_col] else None
            phone = str(row[phone_col]).strip() if phone_col and row[phone_col] else None
            
            if not name or not roll_number:
                skipped_count += 1
                continue
                
            if Student.query.filter_by(roll_number=roll_number).first():
                skipped_count += 1
                continue
                
            # Bundle any dynamic extra columns into JSON string tracking layer
            extra_data_dict = {}
            for ec in extra_cols:
                val = str(row[ec]).strip()
                if val:
                    extra_data_dict[ec] = val
            extra_data_str = json.dumps(extra_data_dict) if extra_data_dict else None
                
            student = Student(
                roll_number=roll_number,
                name=name,
                class_name=class_name,
                section=section,
                email=email,
                phone=phone,
                extra_data=extra_data_str
            )
            db.session.add(student)
            success_count += 1
            
        db.session.commit()
        if success_count > 0:
            flash(f"Students imported successfully! ({success_count} added, {skipped_count} skipped). Please capture their faces.", "success")
        else:
            flash(f"No new students were added. (Skipped: {skipped_count} records due to blanks or duplicates).", "warning")
            
    except Exception as e:
        flash(f"Error processing File: {str(e)}", "danger")
        
    return redirect(url_for("admin.students_list"))


@admin_bp.route("/students/<int:student_id>/delete", methods=["POST"])
@login_required
def students_delete(student_id: int):
    if not current_user.is_admin:
        return redirect(url_for("admin.dashboard"))
    import shutil
    import os
    from flask import current_app
    student = Student.query.get_or_404(student_id)
    
    cfg = current_app.config
    student_dir = os.path.join(cfg["FACE_DATA_DIR"], str(student.id))
    if os.path.exists(student_dir):
        shutil.rmtree(student_dir)
        
    db.session.delete(student)
    db.session.commit()
    
    # Try retraining to remove deleted student from active model
    train_model()
    
    flash("Student completely deleted and neural network updated.", "info")
    return redirect(url_for("admin.students_list"))


@admin_bp.route("/students/<int:student_id>/edit", methods=["POST"])
@login_required
def students_edit(student_id: int):
    if not current_user.is_admin:
        return redirect(url_for("admin.dashboard"))
    student = Student.query.get_or_404(student_id)
    
    roll_number = request.form.get("roll_number", "").strip()
    name = request.form.get("name", "").strip()
    class_name = request.form.get("class_name", "").strip()
    section = request.form.get("section", "").strip()
    email = request.form.get("email", "").strip()
    phone = request.form.get("phone", "").strip()
    
    if not roll_number or not name or not class_name:
        flash("Roll number, name and class are required.", "danger")
        return redirect(url_for("admin.students_list"))
        
    if roll_number != student.roll_number:
        if Student.query.filter_by(roll_number=roll_number).first():
            flash("Roll number already exists for another student.", "danger")
            return redirect(url_for("admin.students_list"))
            
    student.roll_number = roll_number
    student.name = name
    student.class_name = class_name
    student.section = section or None
    student.email = email or None
    student.phone = phone or None
    
    db.session.commit()
    flash(f"Student {name} updated successfully.", "success")
    return redirect(url_for("admin.students_list"))


@admin_bp.route("/students/<int:student_id>/capture-faces", methods=["POST"])
@login_required
def students_capture_faces(student_id: int):
    if not current_user.is_admin:
        return redirect(url_for("admin.dashboard"))
    student = Student.query.get_or_404(student_id)
    samples = capture_faces_for_student(student.id, num_samples=20)
    if samples == 0:
        flash("Could not access camera for face capture.", "danger")
    else:
        if train_model():
            flash(f"Captured {samples} face images and updated recognition model.", "success")
        else:
            flash(f"Captured {samples} images but training failed (insufficient data?).", "warning")
    return redirect(url_for("admin.students_list"))


@admin_bp.route("/reports")
@login_required
def reports():
    logs = Attendance.query.order_by(Attendance.date.desc(), Attendance.time.desc()).limit(100).all()
    return render_template("reports.html", logs=logs)

@admin_bp.route("/api/students/<int:student_id>/upload_faces", methods=["POST"])
@login_required
def api_students_upload_faces(student_id: int):
    if not current_user.is_admin:
        return jsonify({"success": False, "error": "Admin only"}), 403
    import base64
    import os
    from flask import current_app, jsonify
    
    student = Student.query.get_or_404(student_id)
    data = request.json
    if not data or "images" not in data:
        return jsonify({"success": False, "error": "No images provided"}), 400
        
    images = data["images"]
    if len(images) == 0:
        return jsonify({"success": False, "error": "Empty images list"}), 400
        
    cfg = current_app.config
    student_dir = os.path.join(cfg["FACE_DATA_DIR"], str(student.id))
    os.makedirs(student_dir, exist_ok=True)
    
    for i, b64_str in enumerate(images):
        if "," in b64_str:
            b64_str = b64_str.split(",")[1]
            
        img_data = base64.b64decode(b64_str)
        filepath = os.path.join(student_dir, f"capture_{i}.jpg")
        with open(filepath, "wb") as f:
            f.write(img_data)
            
    success = train_model()
    return jsonify({"success": success, "message": f"Saved {len(images)} images and trained model."})


@admin_bp.route("/students/bulk_delete", methods=["POST"])
@login_required
def students_bulk_delete():
    if not current_user.is_admin:
        return redirect(url_for("admin.dashboard"))
    import pandas as pd
    import shutil
    import os
    from flask import current_app
    
    if 'csv_file' not in request.files:
        flash("No file uploaded", "danger")
        return redirect(url_for("admin.students_list"))
        
    file = request.files['csv_file']
    if file.filename == '':
        flash("No file selected", "danger")
        return redirect(url_for("admin.students_list"))
        
    if not (file.filename.endswith('.csv') or file.filename.endswith('.xlsx')):
        flash("Only CSV and Excel (.xlsx) files are allowed.", "danger")
        return redirect(url_for("admin.students_list"))
        
    try:
        if file.filename.endswith('.csv'):
            df = pd.read_csv(file, dtype=str)
        else:
            df = pd.read_excel(file, dtype=str)
            
        if df.empty:
            flash("The uploaded file is empty.", "warning")
            return redirect(url_for("admin.students_list"))
            
        columns = df.columns.tolist()
        roll_col = next((c for c in columns if c and 'roll' in c.lower()), None)
        
        if not roll_col:
            flash("File must contain at least a 'Roll' column.", "danger")
            return redirect(url_for("admin.students_list"))
            
        success_count = 0
        skipped_count = 0
        cfg = current_app.config
        
        for _, row in df.iterrows():
            roll_number = str(row[roll_col]).strip() if pd.notna(row[roll_col]) else ""
            if not roll_number or roll_number.lower() == "nan":
                continue
                
            student = Student.query.filter_by(roll_number=roll_number).first()
            if not student:
                skipped_count += 1
                continue
                
            student_dir = os.path.join(cfg["FACE_DATA_DIR"], str(student.id))
            if os.path.exists(student_dir):
                shutil.rmtree(student_dir)
                
            db.session.delete(student)
            success_count += 1
            
        db.session.commit()
        if success_count > 0:
            train_model()
            flash(f"Successfully deleted {success_count} students and refreshed AI. ({skipped_count} not found).", "success")
        else:
            flash(f"No matching students were found. (Skipped: {skipped_count})", "warning")
            
    except Exception as e:
        flash(f"Error processing File: {str(e)}", "danger")
        
    return redirect(url_for("admin.students_list"))


@admin_bp.route("/students/delete_all", methods=["POST"])
@login_required
def students_delete_all():
    if not current_user.is_admin:
        return redirect(url_for("admin.dashboard"))
    import shutil
    import os
    from flask import current_app
    
    cfg = current_app.config
    all_students = Student.query.all()
    count = 0
    for student in all_students:
        student_dir = os.path.join(cfg["FACE_DATA_DIR"], str(student.id))
        if os.path.exists(student_dir):
            shutil.rmtree(student_dir)
        db.session.delete(student)
        count += 1
        
    db.session.commit()
    if count > 0:
        train_model()
    flash(f"Complete Wipe: Successfully deleted {count} students and scrubbed neural network.", "info")
    return redirect(url_for("admin.students_list"))


@admin_bp.route("/api/search")
@login_required
def api_search():
    from flask import jsonify
    query = request.args.get("q", "").strip().lower()
    if not query:
        return jsonify({"success": True, "results": []})
        
    students = Student.query.all()
    results = []
    
    for s in students:
        if (query in s.name.lower() or 
            query in s.roll_number.lower() or 
            query in s.class_name.lower()):
            results.append({
                "id": s.id,
                "name": s.name,
                "roll_number": s.roll_number,
                "class_name": s.class_name,
                "section": s.section or ""
            })
            
    return jsonify({"success": True, "results": results[:20]})


@admin_bp.route("/api/student/<int:student_id>")
@login_required
def api_student_details(student_id: int):
    import os
    from flask import current_app, jsonify
    
    student = Student.query.get_or_404(student_id)
    cfg = current_app.config
    
    # Face capture status
    is_captured = False
    capture_count = 0
    student_dir = os.path.join(cfg["FACE_DATA_DIR"], str(student.id))
    if os.path.exists(student_dir):
        images = [f for f in os.listdir(student_dir) if f.endswith(('.png', '.jpg', '.jpeg'))]
        if images:
            is_captured = True
            capture_count = len(images)
            
    # Attendance stats
    attendance_records = Attendance.query.filter_by(student_id=student.id).order_by(Attendance.date.desc(), Attendance.time.desc()).all()
    
    total_days = len(set([a.date for a in attendance_records]))
    present_count = len([a for a in attendance_records if a.status == "Present"])
    absent_count = len([a for a in attendance_records if a.status == "Absent"])
    
    last_attendance = attendance_records[0] if attendance_records else None
    
    attendance_percentage = round((present_count / total_days * 100), 1) if total_days > 0 else 0.0
    
    data = {
        "id": student.id,
        "name": student.name,
        "roll_number": student.roll_number,
        "class_name": student.class_name,
        "section": student.section,
        "email": student.email,
        "phone": student.phone,
        "extra_data": student.extra_data,
        "is_captured": is_captured,
        "capture_count": capture_count,
        "total_days": total_days,
        "present_count": present_count,
        "absent_count": absent_count,
        "attendance_percentage": attendance_percentage,
        "last_date": last_attendance.date.strftime('%B %d, %Y') if last_attendance else "N/A",
        "last_time": last_attendance.time.strftime('%I:%M %p') if last_attendance else ""
    }
    
    return jsonify({"success": True, "student": data})


@admin_bp.route("/api/student/<int:student_id>/photo")
def api_student_photo(student_id: int):
    import os
    from flask import current_app, send_file, Response
    
    student = Student.query.get_or_404(student_id)
    cfg = current_app.config
    student_dir = os.path.join(cfg["FACE_DATA_DIR"], str(student.id))
    
    if os.path.exists(student_dir):
        images = [f for f in os.listdir(student_dir) if f.endswith(('.png', '.jpg', '.jpeg'))]
        if images:
            filepath = os.path.join(student_dir, images[0])
            return send_file(filepath, mimetype='image/jpeg')
            
    # Fallback default SVG Initial Avatar
    svg_data = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
        <rect width="100%" height="100%" fill="#e2e8f0"/>
        <text x="50%" y="50%" text-anchor="middle" dy=".3em" font-family="Arial" font-weight="bold" font-size="45" fill="#94a3b8">{student.name[0].upper()}</text>
    </svg>'''
    return Response(svg_data, mimetype='image/svg+xml')

@admin_bp.route("/unknown-faces")
@login_required
def unknown_faces():
    if not current_user.is_admin:
        flash("Access Denied: Admin only.", "danger")
        return redirect(url_for("admin.dashboard"))
    import os
    from flask import current_app
    
    cfg = current_app.config
    unknown_dir = os.path.join(cfg["INSTANCE_DIR"], "unknown_faces")
    faces = []
    
    if os.path.exists(unknown_dir):
        files = [f for f in os.listdir(unknown_dir) if f.endswith(('.jpg', '.jpeg', '.png'))]
        # Sort by newest first
        files.sort(key=lambda x: os.path.getmtime(os.path.join(unknown_dir, x)), reverse=True)
        for f in files:
            mtime = os.path.getmtime(os.path.join(unknown_dir, f))
            from datetime import datetime
            import zoneinfo
            tz = zoneinfo.ZoneInfo("Asia/Kolkata")
            dt = datetime.fromtimestamp(mtime, tz)
            faces.append({
                "filename": f,
                "date": dt.strftime("%B %d, %Y"),
                "time": dt.strftime("%I:%M:%S %p"),
                "timestamp": mtime
            })
            
    # Also pass students for the mapping modal
    students = Student.query.order_by(Student.name).all()
    return render_template("unknown_faces.html", faces=faces, students=students)


@admin_bp.route("/unknown-faces/image/<filename>")
@login_required
def unknown_faces_image(filename):
    if not current_user.is_admin:
        return "Access Denied", 403
    import os
    from flask import current_app, send_file
    cfg = current_app.config
    unknown_dir = os.path.join(cfg["INSTANCE_DIR"], "unknown_faces")
    filepath = os.path.join(unknown_dir, filename)
    if os.path.exists(filepath):
        return send_file(filepath, mimetype='image/jpeg')
    return "Not found", 404


@admin_bp.route("/unknown-faces/assign", methods=["POST"])
@login_required
def unknown_faces_assign():
    if not current_user.is_admin:
        return redirect(url_for("admin.dashboard"))
    import os
    import shutil
    import uuid
    from flask import current_app
    
    filename = request.form.get("filename")
    student_id = request.form.get("student_id")
    
    if not filename or not student_id:
        flash("Invalid assignment request.", "danger")
        return redirect(url_for("admin.unknown_faces"))
        
    student = Student.query.get(student_id)
    if not student:
        flash("Student not found.", "danger")
        return redirect(url_for("admin.unknown_faces"))
        
    cfg = current_app.config
    unknown_dir = os.path.join(cfg["INSTANCE_DIR"], "unknown_faces")
    src_path = os.path.join(unknown_dir, filename)
    
    if not os.path.exists(src_path):
        flash("Image no longer exists.", "warning")
        return redirect(url_for("admin.unknown_faces"))
        
    student_dir = os.path.join(cfg["FACE_DATA_DIR"], str(student.id))
    os.makedirs(student_dir, exist_ok=True)
    
    dest_path = os.path.join(student_dir, f"assigned_{uuid.uuid4().hex[:6]}.jpg")
    shutil.move(src_path, dest_path)
    
    # Retrain model
    from ..ai.face_trainer import train_model
    train_model()
    
    flash(f"Image successfully assigned to {student.name} and Neural Network updated.", "success")
    return redirect(url_for("admin.unknown_faces"))


@admin_bp.route("/unknown-faces/delete", methods=["POST"])
@login_required
def unknown_faces_delete():
    if not current_user.is_admin:
        return redirect(url_for("admin.dashboard"))
    import os
    from flask import current_app
    
    filename = request.form.get("filename")
    if not filename:
        return redirect(url_for("admin.unknown_faces"))
        
    cfg = current_app.config
    unknown_dir = os.path.join(cfg["INSTANCE_DIR"], "unknown_faces")
    src_path = os.path.join(unknown_dir, filename)
    
    if os.path.exists(src_path):
        os.remove(src_path)
        flash("Face Image deleted successfully.", "info")
        
    return redirect(url_for("admin.unknown_faces"))


@admin_bp.route("/unknown-faces/clear", methods=["POST"])
@login_required
def unknown_faces_clear():
    if not current_user.is_admin:
        return redirect(url_for("admin.dashboard"))
    import os
    from flask import current_app
    
    cfg = current_app.config
    unknown_dir = os.path.join(cfg["INSTANCE_DIR"], "unknown_faces")
    count = 0
    if os.path.exists(unknown_dir):
        for f in os.listdir(unknown_dir):
            if f.endswith(('.jpg', '.jpeg', '.png')):
                os.remove(os.path.join(unknown_dir, f))
                count += 1
                
    flash(f"Cleared {count} unknown faces.", "success")
    return redirect(url_for("admin.unknown_faces"))


@admin_bp.route("/users")
@login_required
def users_manage():
    if not current_user.is_admin:
        flash("Access Denied: Admin only.", "danger")
        return redirect(url_for("admin.dashboard"))
    from ..models import User
    users = User.query.all()
    return render_template("users.html", users=users)


@admin_bp.route("/users/add", methods=["POST"])
@login_required
def users_add():
    if not current_user.is_admin:
        return redirect(url_for("admin.dashboard"))
    from ..models import User
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    role = request.form.get("role", "Teacher")
    
    if not username or not password:
        flash("Username and password are required.", "danger")
        return redirect(url_for("admin.users_manage"))
        
    if User.query.filter_by(username=username).first():
        flash("Username already exists.", "danger")
        return redirect(url_for("admin.users_manage"))
        
    new_user = User(username=username, role=role)
    new_user.set_password(password)
    db.session.add(new_user)
    db.session.commit()
    flash(f"User {username} created successfully as {role}.", "success")
    return redirect(url_for("admin.users_manage"))


@admin_bp.route("/users/<int:user_id>/delete", methods=["POST"])
@login_required
def users_delete(user_id):
    if not current_user.is_admin:
        return redirect(url_for("admin.dashboard"))
    from ..models import User
    if user_id == current_user.id:
        flash("You cannot delete yourself.", "danger")
        return redirect(url_for("admin.users_manage"))
        
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    flash(f"User {user.username} deleted.", "info")
    return redirect(url_for("admin.users_manage"))
