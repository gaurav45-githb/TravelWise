import os

from datetime import datetime, date, time, timedelta

from decimal import Decimal

from flask import Flask, render_template, url_for, request, redirect, session, flash, jsonify, abort

from flask_sqlalchemy import SQLAlchemy

from flask_migrate import Migrate

from werkzeug.security import generate_password_hash, check_password_hash

from dotenv import load_dotenv

from models import (

    db, User, Trip, TripPreference, Transportation,

    Accommodation, Budget, Itinerary, ItineraryActivity

)

import json

from google import genai

from google.genai import types

load_dotenv()

app = Flask(__name__)

app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "travelwise_secret_key_2026")

app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL")

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

migrate = Migrate(app, db)

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

    return dict(current_user=current_user, timedelta=timedelta)

@app.route("/")

def home():

    return render_template("index.html")

# ==========================================

# HELPER: Generate AI Day-by-Day Activities with Gemini

def generate_ai_activities_for_trip(
    itinerary_id, source, destination, start_date, days, travelers,
    transport, accommodation, trip_type, interests
):
    """Generate a day-wise itinerary with Gemini and add activities to the DB session."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is missing. Add it to your .env file and restart Flask.")

    client = genai.Client(api_key=api_key)
    model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    schema = {
        "type": "OBJECT",
        "properties": {
            "days": {
                "type": "ARRAY",
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "day_number": {"type": "INTEGER"},
                        "activities": {
                            "type": "ARRAY",
                            "items": {
                                "type": "OBJECT",
                                "properties": {
                                    "place_name": {"type": "STRING"},
                                    "activity_name": {"type": "STRING"},
                                    "description": {"type": "STRING"},
                                    "start_time": {"type": "STRING"},
                                    "end_time": {"type": "STRING"}
                                },
                                "required": ["place_name", "activity_name", "description", "start_time", "end_time"]
                            }
                        }
                    },
                    "required": ["day_number", "activities"]
                }
            }
        },
        "required": ["days"]
    }
    prompt = f"""
Create a practical, realistic day-wise itinerary for TravelWise.
Source: {source}
Destination: {destination}
Start date: {start_date.isoformat()}
Trip duration: exactly {days} days
Travelers: {travelers}
Preferred transport: {transport}
Accommodation: {accommodation}
Trip type: {trip_type}
Interests: {interests}

Rules:
- Return exactly {days} days numbered 1 through {days}, in order.
- Include 2 to 4 activities per day.
- Activities must be relevant to the destination and interests.
- Keep nearby attractions together and avoid unrealistic travel schedules.
- Use 24-hour HH:MM times; end time must be later than start time.
- Do not claim that bookings, prices, opening hours, transport schedules, or availability were verified.
- Do not include costs or calculate a budget; the application calculates the budget separately.
- Return only JSON matching the supplied schema.
"""
    response = client.models.generate_content(
        model=model_name,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=schema,
            temperature=0.4
        )
    )
    if not response.text:
        raise RuntimeError("Gemini returned an empty itinerary. Please try again.")
    try:
        itinerary_data = json.loads(response.text)
    except json.JSONDecodeError as exc:
        raise ValueError("Gemini returned invalid itinerary JSON. Please try again.") from exc

    generated_days = itinerary_data.get("days", [])
    if len(generated_days) != days:
        raise ValueError(f"Gemini returned {len(generated_days)} days; {days} were requested.")

    seen_days = set()
    activity_count = 0
    for day in generated_days:
        day_number = int(day.get("day_number", 0))
        if day_number < 1 or day_number > days or day_number in seen_days:
            raise ValueError("Gemini returned invalid or duplicate day numbers.")
        seen_days.add(day_number)
        activities = day.get("activities", [])
        if not 2 <= len(activities) <= 4:
            raise ValueError(f"Gemini returned an invalid number of activities for day {day_number}.")

        for order, activity in enumerate(activities, start=1):
            place_name = str(activity.get("place_name", "")).strip()[:150]
            activity_name = str(activity.get("activity_name", "")).strip()[:150]
            description = str(activity.get("description", "")).strip()
            if not place_name or not activity_name:
                raise ValueError("Gemini returned an activity without a place or title.")
            try:
                start_time = datetime.strptime(activity["start_time"], "%H:%M").time()
                end_time = datetime.strptime(activity["end_time"], "%H:%M").time()
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError("Gemini returned an invalid activity time.") from exc
            if end_time <= start_time:
                raise ValueError("Gemini returned an invalid activity time range.")
            db.session.add(ItineraryActivity(
                itinerary_id=itinerary_id,
                day_number=day_number,
                place_name=place_name,
                activity_name=activity_name,
                description=description,
                start_time=start_time,
                end_time=end_time,
                estimated_cost=Decimal("0"),
                activity_order=order
            ))
            activity_count += 1

    if seen_days != set(range(1, days + 1)) or activity_count == 0:
        raise ValueError("Gemini returned an incomplete itinerary.")
    return activity_count


# HELPER: Create Full Trip with Relations in DB

# ==========================================

def create_new_trip_in_db(user_id, source, destination, start_date_str, end_date_str, travelers, budget_amount, transport_pref, accommodation_type, trip_type, interests):

    try:

        start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date() if start_date_str else datetime.utcnow().date()

    except (ValueError, TypeError):

        start_date = datetime.utcnow().date()

    try:

        end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date() if end_date_str else start_date

    except (ValueError, TypeError):

        end_date = start_date

    if end_date < start_date:

        end_date = start_date

    days = max((end_date - start_date).days + 1, 1)

    travelers_count = max(int(travelers or 1), 1)

    budget_val = max(float(budget_amount or 20000.0), 1000.0)

    # 1. Create Trip

    new_trip = Trip(

        user_id=user_id,

        source=source or "Delhi",

        destination=destination or "Goa",

        start_date=start_date,

        end_date=end_date,

        travelers=travelers_count,

        trip_status="planned"

    )

    db.session.add(new_trip)

    db.session.flush()

    # 2. Create TripPreference

    budget_cat = "Luxury" if (accommodation_type == "Luxury" or budget_val >= 50000) else ("Budget" if (accommodation_type == "Budget" or budget_val <= 15000) else "Standard")

    pref = TripPreference(

        trip_id=new_trip.trip_id,

        trip_type=trip_type or "Leisure",

        transport_preference=transport_pref or "Train",

        accommodation_type=accommodation_type or "Standard",

        food_preference=interests or "Local Cuisine",

        budget_category=budget_cat

    )

    db.session.add(pref)

    # 3. Create Budget Breakdown

    trans_est = Decimal(str(round(budget_val * 0.20, 2)))

    stay_est = Decimal(str(round(budget_val * 0.35, 2)))

    food_est = Decimal(str(round(budget_val * 0.22, 2)))

    act_est = Decimal(str(round(budget_val * 0.13, 2)))

    min_budget = Decimal(str(round(budget_val * 0.85, 2)))

    max_budget = Decimal(str(round(budget_val * 1.15, 2)))

    new_budget = Budget(

        trip_id=new_trip.trip_id,

        min_transport_cost=round(trans_est * Decimal("0.85"), 2),

        max_transport_cost=round(trans_est * Decimal("1.15"), 2),

        min_stay_cost=round(stay_est * Decimal("0.85"), 2),

        max_stay_cost=round(stay_est * Decimal("1.15"), 2),

        min_food_cost=round(food_est * Decimal("0.85"), 2),

        max_food_cost=round(food_est * Decimal("1.15"), 2),

        min_activity_cost=round(act_est * Decimal("0.85"), 2),

        max_activity_cost=round(act_est * Decimal("1.15"), 2),

        total_min_budget=min_budget,

        total_max_budget=max_budget

    )

    db.session.add(new_budget)

    # 4. Create Transportation

    primary_transport = (transport_pref or "Train").split(',')[0].strip()

    new_trans = Transportation(

        trip_id=new_trip.trip_id,

        transport_type=primary_transport,

        route_details=f"{new_trip.source} → {new_trip.destination}",

        estimated_cost=trans_est,

        is_selected=True

    )

    db.session.add(new_trans)

    # 5. Create Accommodation

    nights = max(days - 1, 1)

    price_per_night = round(stay_est / Decimal(str(nights)), 2)

    new_acc = Accommodation(

        trip_id=new_trip.trip_id,

        hotel_name=f"{new_trip.destination} {accommodation_type or 'Standard'} Hotel",

        accommodation_type=accommodation_type or "Standard",

        location=f"Central {new_trip.destination}",

        price_per_night=price_per_night,

        total_nights=nights,

        estimated_total=stay_est,

        is_selected=True

    )

    db.session.add(new_acc)

    # 6. Create Itinerary & Activities

    new_itinerary = Itinerary(

        trip_id=new_trip.trip_id,

        plan_name=f"{days}-Day {new_trip.destination} Experience Plan",

        total_days=days,

        estimated_cost=Decimal(str(budget_val)),

        plan_status="generated"

    )

    db.session.add(new_itinerary)

    db.session.flush()

    try:
        generate_ai_activities_for_trip(
            itinerary_id=new_itinerary.itinerary_id,
            source=new_trip.source,
            destination=new_trip.destination,
            start_date=start_date,
            days=days,
            travelers=travelers_count,
            transport=primary_transport,
            accommodation=accommodation_type or "Standard",
            trip_type=trip_type or "Leisure",
            interests=interests or "Local Cuisine"
        )
    except Exception:
        db.session.rollback()
        raise

    db.session.commit()

    return new_trip

# @app.route("/", methods=["GET", "POST"])

# def home():

#     if request.method == "POST":

#         return plan_trip()

#     return render_template("index.html")

@app.route("/main", methods=["GET", "POST"])

def main():

    if request.method == "POST":

        return plan_trip()

    return render_template("index.html")

@app.route("/plan-trip", methods=["POST"])

@app.route("/plan_trip", methods=["POST"])

def plan_trip():

    """Create a new Trip and TripPreference in the database from the form."""

    source = request.form.get("source", "Delhi").strip()

    destination = request.form.get("destination", "Goa").strip()

    start_date_str = request.form.get("start_date")

    end_date_str = request.form.get("end_date")

    travelers = request.form.get("travelers", "4")

    budget = request.form.get("budget", "20000")

    transport_pref = request.form.get("transport_preference", "Train, Bus")

    interests = request.form.get("interests", "Beach, Nature, Food")

    accommodation_type = request.form.get("accommodation_type", "Standard")

    trip_type = request.form.get("trip_type", "Leisure")

    user_id = session.get("user_id")

    if not user_id:

        # Save submitted details to session so they are not lost after login/register

        session["pending_trip"] = {

            "source": source,

            "destination": destination,

            "start_date": start_date_str,

            "end_date": end_date_str,

            "travelers": travelers,

            "budget": budget,

            "transport_preference": transport_pref,

            "interests": interests,

            "accommodation_type": accommodation_type,

            "trip_type": trip_type

        }

        flash("Please log in or register to save and view your personalized trip plan!", "info")

        return redirect(url_for("login"))

    try:
        new_trip = create_new_trip_in_db(

        user_id=user_id,

        source=source,

        destination=destination,

        start_date_str=start_date_str,

        end_date_str=end_date_str,

        travelers=travelers,

        budget_amount=budget,

        transport_pref=transport_pref,

        accommodation_type=accommodation_type,

        trip_type=trip_type,

        interests=interests

        )
    except Exception as exc:
        app.logger.exception("TravelWise could not generate/save the trip itinerary")
        db.session.rollback()
        flash(f"Could not generate your itinerary: {exc}", "danger")
        return redirect(url_for("main"))

    flash(f"Trip to {new_trip.destination} created successfully!", "success")

    return redirect(url_for("trip_details", trip_id=new_trip.trip_id))

@app.route("/bashboard")

def dashboard():

    """Dashboard view displaying the logged-in user's trips."""

    user_id = session.get("user_id")

    if not user_id:

        flash("Please log in to open your dashboard.", "warning")

        return redirect(url_for("login"))

    user = None

    trips = []

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

        # Check if user had started planning a trip prior to login

        pending = session.pop("pending_trip", None)

        if pending:

            try:
                new_trip = create_new_trip_in_db(
    
                    user_id=user.user_id,
    
                    source=pending.get("source"),
    
                    destination=pending.get("destination"),
    
                    start_date_str=pending.get("start_date"),
    
                    end_date_str=pending.get("end_date"),
    
                    travelers=pending.get("travelers"),
    
                    budget_amount=pending.get("budget"),
    
                    transport_pref=pending.get("transport_preference"),
    
                    accommodation_type=pending.get("accommodation_type"),
    
                    trip_type=pending.get("trip_type"),
    
                    interests=pending.get("interests")
    
                )
            except Exception as exc:
                app.logger.exception("Could not save pending trip")
                db.session.rollback()
                session["pending_trip"] = pending
                flash(f"Login succeeded, but itinerary generation failed: {exc}", "danger")
                return redirect(url_for("main"))

            flash(f"Welcome back, {user.name}! Your planned trip to {new_trip.destination} has been saved.", "success")

            return redirect(url_for("trip_details", trip_id=new_trip.trip_id))

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

        if not name or not email or not password:

            flash("Please fill all required fields.", "danger")

            return redirect(url_for("register"))

        if confirm_password and password != confirm_password:

            flash("Passwords do not match.", "danger")

            return redirect(url_for("register"))

        existing_user = User.query.filter_by(email=email).first()

        if existing_user:

            flash("Email is already registered. Please login.", "danger")

            return redirect(url_for("register"))

        hashed_password = generate_password_hash(password)

        new_user = User(

            name=name,

            email=email,

            password_hash=hashed_password

        )

        db.session.add(new_user)

        db.session.commit()

        session["user_id"] = new_user.user_id

        # Check if user had started planning a trip prior to registration

        pending = session.pop("pending_trip", None)

        if pending:

            try:
                new_trip = create_new_trip_in_db(
    
                    user_id=new_user.user_id,
    
                    source=pending.get("source"),
    
                    destination=pending.get("destination"),
    
                    start_date_str=pending.get("start_date"),
    
                    end_date_str=pending.get("end_date"),
    
                    travelers=pending.get("travelers"),
    
                    budget_amount=pending.get("budget"),
    
                    transport_pref=pending.get("transport_preference"),
    
                    accommodation_type=pending.get("accommodation_type"),
    
                    trip_type=pending.get("trip_type"),
    
                    interests=pending.get("interests")
    
                )
            except Exception as exc:
                app.logger.exception("Could not save pending trip")
                db.session.rollback()
                session["pending_trip"] = pending
                flash(f"Registration succeeded, but itinerary generation failed: {exc}", "danger")
                return redirect(url_for("main"))

            flash(f"Registration successful! Welcome to TravelWise, {new_user.name}. Your trip to {new_trip.destination} has been saved.", "success")

            return redirect(url_for("trip_details", trip_id=new_trip.trip_id))

        flash(f"Registration successful! Welcome to TravelWise, {new_user.name}.", "success")

        return redirect(url_for("dashboard"))

    return render_template("register.html")

@app.route("/logout")

def logout():

    session.pop("user_id", None)

    flash("You have been logged out successfully.", "info")

    return redirect(url_for("login"))

# ==========================================

# 2. DYNAMIC MY TRIPS VIEW

# ==========================================

@app.route("/mytrips")

def mytrips():

    """Fetch trips = Trip.query.filter_by(user_id=session['user_id']).all() and render in mytrips.html."""

    user_id = session.get("user_id")

    if not user_id:

        flash("Please log in to view your planned trips.", "warning")

        return redirect(url_for("login"))

    trips = Trip.query.filter_by(user_id=session["user_id"]).order_by(Trip.created_at.desc()).all()

    return render_template("mytrips.html", trips=trips)

@app.route("/trip/<int:trip_id>/delete", methods=["POST"])

def delete_trip(trip_id):

    """Delete a trip from the database."""

    user_id = session.get("user_id")

    if not user_id:

        return jsonify({"success": False, "error": "Unauthorized"}), 401

    trip = db.session.get(Trip, trip_id)

    if not trip or trip.user_id != user_id:

        return jsonify({"success": False, "error": "Trip not found or unauthorized"}), 404

    dest = trip.destination

    db.session.delete(trip)

    db.session.commit()

    flash(f"Trip to {dest} has been deleted.", "info")

    return jsonify({"success": True})

# ==========================================

# 3. PARAMETER-BASED ROUTES: DETAILS, ITINERARY, BUDGET

# ==========================================

def get_owned_trip_or_404(trip_id):

    """Return a trip only when it belongs to the logged-in user."""

    user_id = session.get("user_id")

    if not user_id:

        flash("Please log in to access your trips.", "warning")

        return None

    trip = db.session.get(Trip, trip_id)

    if not trip or trip.user_id != user_id:

        abort(404)

    return trip

@app.route("/trip/<int:trip_id>")

@app.route("/tripresult/<int:trip_id>")

def trip_details(trip_id):

    """View specific trip result & overview."""

    trip = get_owned_trip_or_404(trip_id)

    if trip is None:

        return redirect(url_for("login"))

    duration_days = max((trip.end_date - trip.start_date).days + 1, 1)

    nights = max(duration_days - 1, 1)

    pref = trip.preferences

    budget = trip.budget

    transport = trip.transportation[0] if trip.transportation else None

    accommodation = trip.accommodations[0] if trip.accommodations else None

    itinerary = trip.itineraries[0] if trip.itineraries else None

    return render_template(

        "tripresult.html",

        trip=trip,

        duration_days=duration_days,

        nights=nights,

        pref=pref,

        budget=budget,

        transport=transport,

        accommodation=accommodation,

        itinerary=itinerary

    )

@app.route("/trip/<int:trip_id>/itinerary", methods=["GET", "POST"])

def trip_itinerary(trip_id):

    """View and edit specific trip day-by-day itinerary activities."""

    trip = get_owned_trip_or_404(trip_id)

    if trip is None:

        return redirect(url_for("login"))

    duration_days = max((trip.end_date - trip.start_date).days + 1, 1)

    # Ensure trip has an Itinerary object

    itinerary = trip.itineraries[0] if trip.itineraries else None

    if not itinerary:

        itinerary = Itinerary(

            trip_id=trip.trip_id,

            plan_name=f"{duration_days}-Day {trip.destination} Tour",

            total_days=duration_days,

            estimated_cost=trip.budget.total_max_budget if trip.budget else Decimal("20000"),

            plan_status="generated"

        )

        db.session.add(itinerary)

        db.session.commit()

    if request.method == "POST":

        action = request.form.get("action", "add_activity")

        if action == "add_activity":

            day_number = max(request.form.get("day_number", type=int) or 1, 1)

            place_name = request.form.get("place_name", trip.destination).strip()

            activity_name = request.form.get("activity_name", "").strip() or "Sightseeing Exploration"

            description = request.form.get("description", "").strip()

            time_str = request.form.get("start_time", "10:00")

            cost_val = request.form.get("estimated_cost", type=float) or 0.0

            try:

                start_t = datetime.strptime(time_str, "%H:%M").time()

            except Exception:

                start_t = time(10, 0)

            max_order = (
                db.session.query(db.func.max(ItineraryActivity.activity_order))
                .filter_by(itinerary_id=itinerary.itinerary_id).scalar() or 0
            )

            new_activity = ItineraryActivity(

                itinerary_id=itinerary.itinerary_id,

                day_number=day_number,

                place_name=place_name,

                activity_name=activity_name,

                description=description,

                start_time=start_t,

                estimated_cost=Decimal(str(cost_val)),

                activity_order=max_order + 1

            )

            db.session.add(new_activity)

            db.session.commit()

            flash("New activity added to your itinerary!", "success")

            return redirect(url_for("trip_itinerary", trip_id=trip.trip_id))

        elif action == "delete_activity":

            activity_id = request.form.get("activity_id", type=int)

            act = db.session.get(ItineraryActivity, activity_id)

            if act and act.itinerary_id == itinerary.itinerary_id:

                db.session.delete(act)

                db.session.commit()

                flash("Activity removed from itinerary.", "info")

            return redirect(url_for("trip_itinerary", trip_id=trip.trip_id))

    # Group activities by day_number

    activities_by_day = {}

    for d in range(1, duration_days + 1):

        activities_by_day[d] = []

    if itinerary and itinerary.activities:

        for act in sorted(itinerary.activities, key=lambda a: (a.day_number, a.activity_order, a.start_time or time(0, 0))):

            activities_by_day.setdefault(act.day_number, []).append(act)

    return render_template(

        "itinerary.html",

        trip=trip,

        itinerary=itinerary,

        duration_days=duration_days,

        activities_by_day=activities_by_day

    )

@app.route("/trip/<int:trip_id>/budget", methods=["GET", "POST"])

def trip_budget(trip_id):

    """View and edit specific trip budget allocation."""

    trip = get_owned_trip_or_404(trip_id)

    if trip is None:

        return redirect(url_for("login"))

    duration_days = max((trip.end_date - trip.start_date).days + 1, 1)

    budget = trip.budget

    if not budget:

        budget = Budget(

            trip_id=trip.trip_id,

            min_transport_cost=Decimal("3000"),

            max_transport_cost=Decimal("4500"),

            min_stay_cost=Decimal("6000"),

            max_stay_cost=Decimal("9000"),

            min_food_cost=Decimal("4000"),

            max_food_cost=Decimal("6000"),

            min_activity_cost=Decimal("3000"),

            max_activity_cost=Decimal("4500"),

            total_min_budget=Decimal("16000"),

            total_max_budget=Decimal("24000")

        )

        db.session.add(budget)

        db.session.commit()

    if request.method == "POST":

        # Parse updated costs from the edit budget form

        min_trans = request.form.get("min_transport_cost", type=float)

        max_trans = request.form.get("max_transport_cost", type=float)

        min_stay = request.form.get("min_stay_cost", type=float)

        max_stay = request.form.get("max_stay_cost", type=float)

        min_food = request.form.get("min_food_cost", type=float)

        max_food = request.form.get("max_food_cost", type=float)

        min_act = request.form.get("min_activity_cost", type=float)

        max_act = request.form.get("max_activity_cost", type=float)

        min_tot = request.form.get("total_min_budget", type=float)

        max_tot = request.form.get("total_max_budget", type=float)

        if min_trans is not None: budget.min_transport_cost = Decimal(str(min_trans))

        if max_trans is not None: budget.max_transport_cost = Decimal(str(max_trans))

        if min_stay is not None: budget.min_stay_cost = Decimal(str(min_stay))

        if max_stay is not None: budget.max_stay_cost = Decimal(str(max_stay))

        if min_food is not None: budget.min_food_cost = Decimal(str(min_food))

        if max_food is not None: budget.max_food_cost = Decimal(str(max_food))

        if min_act is not None: budget.min_activity_cost = Decimal(str(min_act))

        if max_act is not None: budget.max_activity_cost = Decimal(str(max_act))

        calculated_min = (budget.min_transport_cost or 0) + (budget.min_stay_cost or 0) + (budget.min_food_cost or 0) + (budget.min_activity_cost or 0)

        calculated_max = (budget.max_transport_cost or 0) + (budget.max_stay_cost or 0) + (budget.max_food_cost or 0) + (budget.max_activity_cost or 0)

        budget.total_min_budget = Decimal(str(min_tot)) if min_tot is not None else calculated_min

        budget.total_max_budget = Decimal(str(max_tot)) if max_tot is not None else calculated_max

        db.session.commit()

        flash("Trip budget updated successfully!", "success")

        return redirect(url_for("trip_budget", trip_id=trip.trip_id))

    return render_template(

        "budget.html",

        trip=trip,

        budget=budget,

        duration_days=duration_days

    )

@app.route("/trip/<int:trip_id>/edit", methods=["GET", "POST"])

def edit_trip(trip_id):

    """Edit core trip parameters for the logged-in user's trip."""

    trip = get_owned_trip_or_404(trip_id)

    if trip is None:

        return redirect(url_for("login"))

    if request.method == "POST":

        trip.source = request.form.get("source", trip.source).strip()

        trip.destination = request.form.get("destination", trip.destination).strip()

        start_date_str = request.form.get("start_date")

        end_date_str = request.form.get("end_date")

        if start_date_str:

            try:

                trip.start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()

            except Exception:

                pass

        if end_date_str:

            try:

                trip.end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()

            except Exception:

                pass

        trip.travelers = max(request.form.get("travelers", type=int) or trip.travelers, 1)

        trip.trip_status = request.form.get("trip_status", trip.trip_status or "planned")

        if trip.preferences:

            trip.preferences.transport_preference = request.form.get("transport_preference", trip.preferences.transport_preference)

            trip.preferences.accommodation_type = request.form.get("accommodation_type", trip.preferences.accommodation_type)

            trip.preferences.trip_type = request.form.get("trip_type", trip.preferences.trip_type)

        db.session.commit()

        flash(f"Trip to {trip.destination} updated successfully!", "success")

        return redirect(url_for("trip_details", trip_id=trip.trip_id))

    duration_days = max((trip.end_date - trip.start_date).days + 1, 1)

    return render_template("tripresult.html", trip=trip, duration_days=duration_days, budget=trip.budget, transport=trip.transportation[0] if trip.transportation else None, accommodation=trip.accommodations[0] if trip.accommodations else None)

# ==========================================

# BACKWARD COMPATIBLE FALLBACK ROUTES

# ==========================================

@app.route("/tripresult")

def tripresult():

    trip_id = request.args.get("trip_id", type=int)

    if trip_id:

        return redirect(url_for("trip_details", trip_id=trip_id))

    user_id = session.get("user_id")

    if user_id:

        latest = Trip.query.filter_by(user_id=user_id).order_by(Trip.created_at.desc()).first()

        if latest:

            return redirect(url_for("trip_details", trip_id=latest.trip_id))

    return render_template("tripresult.html", trip=None, duration_days=5, nights=4, budget=None, transport=None, accommodation=None, itinerary=None)

@app.route("/itinerary")

def itinerary():

    trip_id = request.args.get("trip_id", type=int)

    if trip_id:

        return redirect(url_for("trip_itinerary", trip_id=trip_id))

    user_id = session.get("user_id")

    if user_id:

        latest = Trip.query.filter_by(user_id=user_id).order_by(Trip.created_at.desc()).first()

        if latest:

            return redirect(url_for("trip_itinerary", trip_id=latest.trip_id))

    return render_template("itinerary.html", trip=None, itinerary=None, duration_days=5, activities_by_day={})

@app.route("/budget")

def budget():

    trip_id = request.args.get("trip_id", type=int)

    if trip_id:

        return redirect(url_for("trip_budget", trip_id=trip_id))

    user_id = session.get("user_id")

    if user_id:

        latest = Trip.query.filter_by(user_id=user_id).order_by(Trip.created_at.desc()).first()

        if latest:

            return redirect(url_for("trip_budget", trip_id=latest.trip_id))

    return render_template("budget.html", trip=None, budget=None, duration_days=5)

if __name__ == "__main__":

    with app.app_context():

        db.create_all()

    app.run(debug=True, port=5005)