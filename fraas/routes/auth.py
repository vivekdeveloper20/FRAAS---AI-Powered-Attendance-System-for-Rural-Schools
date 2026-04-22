from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user

from .. import db
from ..models import User

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/init-admin")
def init_admin():
    """One-time helper to create an initial admin user if none exists."""
    if User.query.first():
        flash("Admin already initialized.", "info")
        return redirect(url_for("auth.login"))
    admin = User(username="admin", role="Admin")
    admin.set_password("admin123")
    db.session.add(admin)
    db.session.commit()
    flash("Default admin created (username: admin, password: admin123). Please change it.", "success")
    return redirect(url_for("auth.login"))


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("admin.dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for("admin.dashboard"))
        flash("Invalid username or password", "danger")

    return render_template("login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Logged out successfully.", "info")
    return redirect(url_for("auth.login"))


