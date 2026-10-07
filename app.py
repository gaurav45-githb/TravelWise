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
# HELPER: Generate Default Day-by-Day Activities
# ==========================================
def create_default_activities_for_trip(itinerary_id, destination, source, days, primary_transport):
    dest_lower = (destination or "").lower()

    dest_data = {
        "goa": [
            ("Arrival & Baga Sunset", [
                (time(8, 30), f"Departure from {source}", f"Commence journey towards Goa via {primary_transport}.", 1200),
                (time(16, 0), "Hotel Check-in & Relax", "Settle in at hotel, refresh and unpack.", 0),
                (time(18, 0), "Baga Beach Sunset", "Golden hour stroll along Baga shoreline with sea breeze.", 300),
                (time(20, 30), "Dinner at Britto's", "Savor iconic Goan seafood curry and beach shack ambiance.", 1200)
            ]),
            ("North Goa Forts & Watersports", [
                (time(9, 30), "Fort Aguada & Lighthouse", "17th-century Portuguese fortress with sweeping ocean panoramas.", 400),
                (time(13, 0), "Goan Thali Lunch", "Enjoy traditional fish thali and kokum drink at a coastal tavern.", 700),
                (time(15, 30), "Calangute & Anjuna Watersports", "Thrilling parasailing, jet-skiing and banana boat rides.", 2000),
                (time(19, 30), "Curlies or Sunset Shack", "Relaxing music, coastal breeze and tropical beverages.", 900)
            ]),
            ("Heritage Churches & Latin Quarter", [
                (time(9, 0), "Old Goa Heritage Churches", "Visit Basilica of Bom Jesus & Se Cathedral (UNESCO World Heritage).", 300),
                (time(13, 30), "Fontainhas Heritage Walk", "Explore colorful Portuguese villas in Panjim's Latin Quarter.", 500),
                (time(18, 0), "Mandovi River Sunset Cruise", "Live Goan folk dance, music and scenic river views.", 1200),
                (time(21, 0), "Panaji Fine Dining", "Authentic Portuguese-Goan fusion dinner.", 1400)
            ]),
            ("South Goa Serenity & Waterfalls", [
                (time(8, 30), "Dudhsagar Waterfalls Trek", "Majestic 4-tiered waterfall through lush Western Ghats.", 1800),
                (time(14, 0), "Spice Plantation Tour & Buffet", "Guided tour of aromatic spices with authentic Goan buffet lunch.", 800),
                (time(17, 30), "Palolem Beach Leisure", "Crescent-shaped serene beach with palm trees and gentle waves.", 400),
                (time(20, 0), "Beach Shack Candlelight Dinner", "Fresh catch of the day by the moonlit sea.", 1500)
            ]),
            ("Leisure & Return Journey", [
                (time(9, 30), "Panaji Market Shopping", "Pick up cashew nuts, feni, port wine and Goan spices.", 1500),
                (time(12, 0), "Farewell Coastal Brunch", "Relaxed beachside cafe lunch.", 800),
                (time(15, 0), f"Departure Journey to {source}", f"Board {primary_transport} for safe return trip home.", 1200)
            ])
        ],
        "manali": [
            ("Journey into the Himalayas", [
                (time(8, 0), f"Departure from {source}", f"Scenic mountain transit towards Manali via {primary_transport}.", 1500),
                (time(16, 30), "Riverside Resort Check-in", "Check in and enjoy hot ginger tea by the Beas River.", 0),
                (time(18, 30), "Mall Road & Tibetan Monastery", "Leisure walk, explore Tibetan handicrafts and peaceful prayer wheels.", 400),
                (time(20, 30), "Traditional Himachali Dinner", "Try Siddu, Trout fish and steaming mountain soups.", 900)
            ]),
            ("Solang Valley & Adventure Sports", [
                (time(9, 0), "Solang Valley Adventures", "Paragliding over pine valleys, zorbing and cable car ropeway.", 2800),
                (time(14, 0), "Cafe Hopping in Old Manali", "Rustic wooden cafes serving wood-fired pizzas and fresh apple pie.", 800),
                (time(17, 0), "Vashisht Hot Springs", "Natural sulfur thermal baths and ancient stone temple.", 200),
                (time(20, 0), "Bonfire & Stargazing", "Chilly mountain evening with cozy bonfire.", 500)
            ]),
            ("Atal Tunnel & Sissu Snow Valley", [
                (time(8, 30), "Atal Tunnel Crossing", "Drive through world's longest highway tunnel above 10,000 feet.", 600),
                (time(11, 0), "Sissu Waterfall & Valley", "Spectacular stark landscapes of Lahaul Valley and glaciers.", 500),
                (time(14, 30), "Lahauli Noodle Soup Lunch", "Warm thukpa and momos in the cold mountain air.", 500),
                (time(19, 0), "Return to Manali & Dinner", "Cozy cabin dinner with live acoustic music.", 1100)
            ]),
            ("Hadimba Temple & Jogini Falls", [
                (time(9, 30), "Hadimba Devi Temple", "Iconic wooden pagoda temple nestled among towering cedar trees.", 200),
                (time(12, 0), "Jogini Waterfall Hike", "Scenic forest trek through apple orchards and pine groves.", 400),
                (time(15, 0), "Vashisht Village Tea & Crafts", "Handmade woolen shawls, caps and local wild honey.", 1200),
                (time(20, 0), "Old Manali Riverside Dinner", "River terrace dining under the Himalayan night sky.", 1200)
            ]),
            ("Farewell to the Mountains", [
                (time(9, 0), "Morning Apple Orchard Walk", "Crisp mountain morning stroll and fresh fruit preserves.", 300),
                (time(11, 30), "Souvenir Shopping & Woolens", "Kullu shawls and wooden artifacts from government emporium.", 1500),
                (time(14, 0), f"Departure Journey to {source}", f"Begin return transit with unforgettable memories.", 1500)
            ])
        ],
        "jaipur": [
            ("Arrival in the Pink City", [
                (time(9, 0), f"Journey from {source}", f"Travel to royal Jaipur via {primary_transport}.", 1000),
                (time(14, 30), "Heritage Haveli Check-in", "Warm Rajasthani welcome with marigold garlands.", 0),
                (time(17, 0), "Albert Hall Museum & Gardens", "Indo-Saracenic architecture illuminated in majestic evening lights.", 300),
                (time(19, 30), "Chokhi Dhani Cultural Village", "Folk dances, puppet shows, camel rides & authentic Royal Thali.", 1600)
            ]),
            ("Fortresses of the Royals", [
                (time(8, 30), "Amer Fort Jeep Tour", "Magnificent hilltop palace with Sheesh Mahal (Mirror Palace).", 800),
                (time(12, 30), "Jal Mahal Lake Viewpoint", "Palace floating serenely in the middle of Man Sagar Lake.", 200),
                (time(14, 0), "Rajasthani Lunch & Delicacies", "Spicy traditional Rajasthani lunch at heritage dining room.", 900),
                (time(16, 30), "Nahargarh Fort Sunset View", "Spectacular sunset view over the entire Pink City.", 400),
                (time(20, 30), "Rooftop Dinner", "Dining with panoramic view of illuminated city walls.", 1200)
            ]),
            ("Palaces, Astronomy & Bazaars", [
                (time(9, 0), "Hawa Mahal (Palace of Winds)", "Honeycomb facade with 953 ornate windows.", 300),
                (time(11, 0), "City Palace & Royal Museum", "Courtyards, royal costumes and Peacock Gate photography.", 700),
                (time(14, 0), "Jantar Mantar Observatory", "World's largest stone sundial (UNESCO World Heritage).", 400),
                (time(16, 30), "Johari & Bapu Bazaar Shopping", "Block print textiles, blue pottery, and lac bangles.", 2000),
                (time(20, 30), "Heritage Sweet Tasting & Dinner", "Famous Rawat Pyaaz Kachori and Ghewar.", 800)
            ]),
            ("Jaigarh & Artisan Village", [
                (time(9, 30), "Jaigarh Fort & Jaivana Cannon", "World's largest wheeled cannon with subterranean water tanks.", 500),
                (time(13, 0), "Anokhi Hand Printing Museum", "Live block printing demonstration and artisan workshops.", 400),
                (time(16, 0), "Sisodia Rani Garden & Palace", "Tiered fountains, painted pavilions and peacocks.", 300),
                (time(19, 30), "Fine Dining at Spice Court", "Royal dining experience with live sitar music.", 1500)
            ]),
            ("Farewell to Royalty", [
                (time(9, 30), "Birla Mandir & Moti Dungri", "Carved white marble temple and peaceful gardens.", 200),
                (time(12, 0), "LMB Restaurant Feast", "Famous century-old Rajasthani culinary landmark.", 900),
                (time(15, 0), f"Departure Journey to {source}", f"Return journey home with royal souvenirs.", 1000)
            ])
        ]
    }

    matched_key = None
    for k in dest_data:
        if k in dest_lower:
            matched_key = k
            break

    order = 1
    for day_idx in range(1, days + 1):
        if matched_key and day_idx <= len(dest_data[matched_key]):
            day_title, activities_list = dest_data[matched_key][day_idx - 1]
        elif matched_key and day_idx == days:
            day_title, activities_list = dest_data[matched_key][-1]
        else:
            if day_idx == 1:
                day_title = f"Arrival & {destination} Orientation"
                activities_list = [
                    (time(9, 0), f"Transit from {source}", f"Travel towards {destination} via {primary_transport}.", 1000),
                    (time(15, 0), "Hotel Check-in & Freshen Up", "Check in to accommodation and relax after journey.", 0),
                    (time(17, 30), "City Center Exploration", "Stroll through famous avenues and local landmarks.", 400),
                    (time(20, 0), "Welcome Dinner", "Savor local cuisine and regional specialties.", 900)
                ]
            elif day_idx == days:
                day_title = f"Final Sightseeing & Departure to {source}"
                activities_list = [
                    (time(9, 30), "Local Market & Souvenir Shopping", "Pick up famous local gifts and handcrafted souvenirs.", 1200),
                    (time(12, 30), "Farewell Lunch & Hotel Checkout", "Enjoy final favorite local lunch and pack bags.", 700),
                    (time(15, 0), f"Return Journey to {source}", f"Board {primary_transport} for safe journey back.", 1000)
                ]
            else:
                day_title = f"Day {day_idx} - {destination} Highlights & Culture"
                activities_list = [
                    (time(9, 30), f"Explore Iconic Landmark in {destination}", "Guided tour of top-rated historical and scenic spots.", 600),
                    (time(13, 0), "Authentic Regional Lunch", "Popular local eatery serving traditional dishes.", 700),
                    (time(15, 30), "Cultural Attraction & Activities", "Museum, garden, or exciting local adventure.", 500),
                    (time(19, 30), "Evening Sunset & Dinner", "Spectacular viewpoint followed by relaxing dinner.", 1100)
                ]

        for t, act_name, desc, cost in activities_list:
            act = ItineraryActivity(
                itinerary_id=itinerary_id,
                day_number=day_idx,
                place_name=destination,
                activity_name=act_name,
                description=desc,
                start_time=t,
                end_time=None,
                estimated_cost=Decimal(str(cost)),
                activity_order=order
            )
            db.session.add(act)
            order += 1


# ==========================================
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

    create_default_activities_for_trip(new_itinerary.itinerary_id, new_trip.destination, new_trip.source, days, primary_transport)

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

            max_order = db.session.query(db.func.max(ItineraryActivity.activity_order))\
                .filter_by(itinerary_id=itinerary.itinerary_id).scalar() or 0

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