import os
from flask import Flask, render_template, url_for
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")

app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL")

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/main")
def main():
    return render_template("index.html")

@app.route("/login")
def login():
    return render_template("login.html")

@app.route("/register")
def register():
    return render_template("register.html")

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

    # with app.app_context():
    #     db.create_all()

    app.run(debug=True, port=5005)