from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


# =========================
# 1. USER TABLE
# =========================
class User(db.Model):
    __tablename__ = "users"

    user_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationship
    trips = db.relationship("Trip", back_populates="user",
                            cascade="all, delete-orphan")


# =========================
# 2. TRIP TABLE
# =========================
class Trip(db.Model):
    __tablename__ = "trips"

    trip_id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.user_id"),
        nullable=False
    )

    source = db.Column(db.String(100), nullable=False)
    destination = db.Column(db.String(100), nullable=False)

    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)

    travelers = db.Column(db.Integer, nullable=False)

    trip_status = db.Column(
        db.String(20),
        default="draft"
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    # Relationships
    user = db.relationship("User", back_populates="trips")

    preferences = db.relationship(
        "TripPreference",
        back_populates="trip",
        uselist=False,
        cascade="all, delete-orphan"
    )

    transportation = db.relationship(
        "Transportation",
        back_populates="trip",
        cascade="all, delete-orphan"
    )

    accommodations = db.relationship(
        "Accommodation",
        back_populates="trip",
        cascade="all, delete-orphan"
    )

    budget = db.relationship(
        "Budget",
        back_populates="trip",
        uselist=False,
        cascade="all, delete-orphan"
    )

    itineraries = db.relationship(
        "Itinerary",
        back_populates="trip",
        cascade="all, delete-orphan"
    )


# =========================
# 3. TRIP PREFERENCE TABLE
# =========================
class TripPreference(db.Model):
    __tablename__ = "trip_preferences"

    preference_id = db.Column(db.Integer, primary_key=True)

    trip_id = db.Column(
        db.Integer,
        db.ForeignKey("trips.trip_id"),
        unique=True,
        nullable=False
    )

    trip_type = db.Column(db.String(50))

    transport_preference = db.Column(
        db.String(30)
    )

    accommodation_type = db.Column(
        db.String(30)
    )

    food_preference = db.Column(
        db.String(30)
    )

    budget_category = db.Column(
        db.String(30)
    )

    # Relationship
    trip = db.relationship(
        "Trip",
        back_populates="preferences"
    )


# =========================
# 4. TRANSPORTATION TABLE
# =========================
class Transportation(db.Model):
    __tablename__ = "transportation"

    transport_id = db.Column(
        db.Integer,
        primary_key=True
    )

    trip_id = db.Column(
        db.Integer,
        db.ForeignKey("trips.trip_id"),
        nullable=False
    )

    transport_type = db.Column(
        db.String(30),
        nullable=False
    )

    route_details = db.Column(db.Text)

    distance_km = db.Column(
        db.Numeric(10, 2)
    )

    duration_hours = db.Column(
        db.Numeric(6, 2)
    )

    estimated_cost = db.Column(
        db.Numeric(10, 2),
        nullable=False
    )

    is_selected = db.Column(
        db.Boolean,
        default=False
    )

    # Relationship
    trip = db.relationship(
        "Trip",
        back_populates="transportation"
    )


# =========================
# 5. ACCOMMODATION TABLE
# =========================
class Accommodation(db.Model):
    __tablename__ = "accommodations"

    accommodation_id = db.Column(
        db.Integer,
        primary_key=True
    )

    trip_id = db.Column(
        db.Integer,
        db.ForeignKey("trips.trip_id"),
        nullable=False
    )

    hotel_name = db.Column(
        db.String(150)
    )

    accommodation_type = db.Column(
        db.String(30)
    )

    location = db.Column(
        db.String(150)
    )

    price_per_night = db.Column(
        db.Numeric(10, 2),
        nullable=False
    )

    total_nights = db.Column(
        db.Integer,
        nullable=False
    )

    estimated_total = db.Column(
        db.Numeric(10, 2),
        nullable=False
    )

    is_selected = db.Column(
        db.Boolean,
        default=False
    )

    # Relationship
    trip = db.relationship(
        "Trip",
        back_populates="accommodations"
    )


# =========================
# 6. BUDGET TABLE
# =========================
class Budget(db.Model):
    __tablename__ = "budgets"

    budget_id = db.Column(
        db.Integer,
        primary_key=True
    )

    trip_id = db.Column(
        db.Integer,
        db.ForeignKey("trips.trip_id"),
        unique=True,
        nullable=False
    )

    min_transport_cost = db.Column(
        db.Numeric(10, 2),
        default=0
    )

    max_transport_cost = db.Column(
        db.Numeric(10, 2),
        default=0
    )

    min_stay_cost = db.Column(
        db.Numeric(10, 2),
        default=0
    )

    max_stay_cost = db.Column(
        db.Numeric(10, 2),
        default=0
    )

    min_food_cost = db.Column(
        db.Numeric(10, 2),
        default=0
    )

    max_food_cost = db.Column(
        db.Numeric(10, 2),
        default=0
    )

    min_activity_cost = db.Column(
        db.Numeric(10, 2),
        default=0
    )

    max_activity_cost = db.Column(
        db.Numeric(10, 2),
        default=0
    )

    total_min_budget = db.Column(
        db.Numeric(12, 2),
        default=0
    )

    total_max_budget = db.Column(
        db.Numeric(12, 2),
        default=0
    )

    # Relationship
    trip = db.relationship(
        "Trip",
        back_populates="budget"
    )


# =========================
# 7. ITINERARY TABLE
# =========================
class Itinerary(db.Model):
    __tablename__ = "itineraries"

    itinerary_id = db.Column(
        db.Integer,
        primary_key=True
    )

    trip_id = db.Column(
        db.Integer,
        db.ForeignKey("trips.trip_id"),
        nullable=False
    )

    plan_name = db.Column(
        db.String(150),
        nullable=False
    )

    generated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    total_days = db.Column(
        db.Integer,
        nullable=False
    )

    estimated_cost = db.Column(
        db.Numeric(12, 2)
    )

    plan_status = db.Column(
        db.String(20),
        default="generated"
    )

    # Relationships
    trip = db.relationship(
        "Trip",
        back_populates="itineraries"
    )

    activities = db.relationship(
        "ItineraryActivity",
        back_populates="itinerary",
        cascade="all, delete-orphan"
    )


# =========================
# 8. ITINERARY ACTIVITY TABLE
# =========================
class ItineraryActivity(db.Model):
    __tablename__ = "itinerary_activities"

    activity_id = db.Column(
        db.Integer,
        primary_key=True
    )

    itinerary_id = db.Column(
        db.Integer,
        db.ForeignKey("itineraries.itinerary_id"),
        nullable=False
    )

    day_number = db.Column(
        db.Integer,
        nullable=False
    )

    place_name = db.Column(
        db.String(150),
        nullable=False
    )

    activity_name = db.Column(
        db.String(150),
        nullable=False
    )

    description = db.Column(db.Text)

    start_time = db.Column(db.Time)

    end_time = db.Column(db.Time)

    estimated_cost = db.Column(
        db.Numeric(10, 2),
        default=0
    )

    activity_order = db.Column(
        db.Integer,
        nullable=False
    )

    # Relationship
    itinerary = db.relationship(
        "Itinerary",
        back_populates="activities"
    )