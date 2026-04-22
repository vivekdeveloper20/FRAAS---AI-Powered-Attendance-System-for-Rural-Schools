from datetime import date
import time

from flask import Blueprint, render_template, Response, jsonify, current_app, request
from flask_login import login_required

from ..services.camera_manager import get_camera
from ..services.attendance_service import mark_attendance_for_recognition
from ..services.confirmation_service import get_confirmation_service

attendance_bp = Blueprint("attendance", __name__, url_prefix="/attendance")


@attendance_bp.route("/")
@login_required
def attendance_page():
    return render_template("attendance_live.html")


def _gen_frames(app):
    """
    Generator that continuously yields JPEG frames for MJPEG streaming.
    It keeps the connection open and skips invalid frames instead of stopping.
    Wrapped in Flask application context to allow database operations.
    
    Args:
        app: Flask application instance for maintaining app context
    """
    # Push application context for the entire generator lifecycle
    with app.app_context():
        import logging
        app.logger.setLevel(logging.DEBUG)
        
        camera = get_camera()
        print("[DEBUG] Started Camera Streaming in _gen_frames")
        
        import zoneinfo
        from datetime import datetime
        tz = zoneinfo.ZoneInfo("Asia/Kolkata")
        
        while True:
            # If camera stops, break the stream so HTTP response ends cleanly
            if not camera.is_active:
                print("[DEBUG] Camera inactive, breaking _gen_frames loop")
                break
                
            frame, recognized = camera.get_frame_with_recognition()

            # Mark attendance in the background when a face is recognized
            # This requires Flask app context for database operations
            if recognized is not None:
                print(f"[DEBUG] Face recognized with student_id: {recognized.student_id}, confidence: {recognized.confidence}")
                try:
                    today_kolkata = datetime.now(tz).date()
                    result = mark_attendance_for_recognition(
                        recognized.student_id, recognized.confidence, today_kolkata
                    )
                    print(f"[DEBUG] DB mark_attendance_for_recognition result: {result}")
                    if result:
                        if result.get("status") == "marked":
                            camera.recognizer.show_marked_success()
                        # Log outcome (marked or already_marked)
                        app.logger.info(
                            "Attendance recognition: %s (%s)",
                            result.get("student_name"),
                            result.get("status"),
                        )
                except Exception as e:
                    import traceback
                    print(f"[ERROR] Exception during mark_attendance_for_recognition: {e}")
                    traceback.print_exc()
                    app.logger.error(f"Error marking attendance: {e}")

            # If we don't have a valid frame, wait briefly and retry instead of closing the stream
            if frame is None:
                time.sleep(0.1)
                continue

            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
            )


@attendance_bp.route("/video_feed")
@login_required
def video_feed():
    # Get the actual Flask app instance from current_app proxy
    # This ensures the generator has proper application context for database operations
    app = current_app._get_current_object()
    return Response(
        _gen_frames(app),
        mimetype="multipart/x-mixed-replace; boundary=frame",
    )


@attendance_bp.route("/status")
@login_required
def status():
    camera = get_camera()
    return jsonify({"camera_active": camera.is_active})

@attendance_bp.route("/start_camera", methods=["POST"])
@login_required
def start_camera():
    camera = get_camera()

    payload = request.get_json(silent=True) or {}
    raw_index = payload.get("camera_index", request.form.get("camera_index", 0))
    try:
        camera_index = int(raw_index)
        if camera_index < 0:
            camera_index = 0
    except (TypeError, ValueError):
        camera_index = 0

    success = camera.start(camera_index=camera_index)
    if success:
        get_confirmation_service().reset_session_stats()
    return jsonify({"success": success, "camera_index": camera_index})

@attendance_bp.route("/stop_camera", methods=["POST"])
@login_required
def stop_camera():
    camera = get_camera()
    camera.stop()
    return jsonify({"success": True})


@attendance_bp.route("/confirmations")
@login_required
def get_confirmations():
    """
    Get recent attendance confirmations since the last check.
    Used by frontend to display confirmation messages.
    """
    since = float(request.args.get("since", 0.0))
    confirmation_service = get_confirmation_service()
    confirmations = confirmation_service.get_recent_confirmations(since_timestamp=since)
    
    import zoneinfo
    from datetime import datetime
    tz = zoneinfo.ZoneInfo("Asia/Kolkata")
    
    return jsonify(
        {
            "confirmations": [
                {
                    "student_id": c.student_id,
                    "student_name": c.student_name,
                    "roll_number": c.roll_number,
                    "timestamp": c.timestamp,
                    "status": c.status,
                    "phone": c.phone,
                    "class_name": c.class_name,
                    "date_str": c.date.strftime("%B %d, %Y") if c.date else "",
                    "formatted_time": datetime.fromtimestamp(c.timestamp, tz).strftime("%I:%M %p")
                }
                for c in confirmations
            ],
            "stats": {
                "total_detected": confirmation_service.session_total_detected,
                "total_marked": confirmation_service.session_total_marked,
                "total_unknown": confirmation_service.session_total_unknown
            }
        }
    )


