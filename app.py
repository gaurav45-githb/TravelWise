import os
from flask import Flask, render_template, url_for, request, redirect, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
from models import db, User, Trip

load_dotenv()

app = Flask(__name__)

app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "travelwise_secret_key_2026")
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)


@app.context_processor
def inject_user():
    """Make the logged-in User instance from DB available to all templates."""
    current_user = None
    user_id = session.get("user_id")
    if user_id:
        try:
            current_user = db.session.get(User, user_id)
            if not current_user:
                session.pop("user_id", None)
        except Exception:
            current_user = None
    return dict(current_user=current_user)


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/main")
def main():
    return render_template("index.html")


@app.route("/dashboard")
@app.route("/bashboard")
def dashboard():
    """Dashboard view displaying user stats, recent trips, budget chart, and quick links."""
    user = None
    trips = []
    user_id = session.get("user_id")
    if user_id:
        try:
            user = db.session.get(User, user_id)
            if user:
                trips = Trip.query.filter_by(user_id=user.user_id).order_by(Trip.created_at.desc()).all()
        except Exception:
            user = None
            trips = []
    return render_template("dashboard.html", user=user, trips=trips)


@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        if not email or not password:
            flash("Please enter both email and password.", "danger")
            return redirect(url_for("login"))

        user = User.query.filter_by(email=email).first()

        if not user or not check_password_hash(user.password_hash, password):
            flash("Invalid email or password. Please try again.", "danger")
            return redirect(url_for("login"))

        session["user_id"] = user.user_id
        flash(f"Welcome back, {user.name}!", "success")
        return redirect(url_for("dashboard"))

    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if "user_id" in session:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirmPassword", "")

        # Check empty fields
        if not name or not email or not password:
            flash("Please fill all required fields.", "danger")
            return redirect(url_for("register"))

        if confirm_password and password != confirm_password:
            flash("Passwords do not match.", "danger")
            return redirect(url_for("register"))

        # Check if email already exists
        existing_user = User.query.filter_by(email=email).first()

        if existing_user:
            flash("Email is already registered. Please login.", "danger")
            return redirect(url_for("register"))

        # Hash password
        hashed_password = generate_password_hash(password)

        # Create user
        new_user = User(
            name=name,
            email=email,
            password_hash=hashed_password
        )

        db.session.add(new_user)
        db.session.commit()

        # Log the user into session immediately
        session["user_id"] = new_user.user_id

        flash(f"Registration successful! Welcome to TravelWise, {new_user.name}.", "success")
        return redirect(url_for("dashboard"))

    return render_template("register.html")


@app.route("/logout")
def logout():
    session.pop("user_id", None)
    flash("You have been logged out successfully.", "info")
    return redirect(url_for("login"))


@app.route("/mytrips")
def mytrips():
    return render_template("mytrips.html")


@app.route("/itinerary")
def itinerary():
    return render_template("itinerary.html")


@app.route("/budget")
def budget():
    return render_template("budget.html")


@app.route("/tripresult")
def tripresult():
    return render_template("tripresult.html")


if __name__ == "__main__":
    with app.app_context():
        db.create_all()

    app.run(debug=True, port=5005)