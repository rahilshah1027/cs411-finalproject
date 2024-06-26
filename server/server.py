from flask import Flask, url_for, session
from flask import render_template, redirect
from flask_sqlalchemy import SQLAlchemy
from authlib.integrations.flask_client import OAuth
from sqlalchemy import Integer, String, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from api import fetch_places
from flask import jsonify, request
from dotenv import load_dotenv
import os, requests, random

app = Flask(__name__, template_folder='../client/templates', static_folder='../static')
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///project.db"
app.secret_key = "randomstuff"
db = SQLAlchemy(app)
oauth = OAuth(app)
load_dotenv()

# creating database models
class User(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=True)
    email: Mapped[str]

class UserInterests(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    location: Mapped[str] = mapped_column()
    interests: Mapped[str] = mapped_column()
    food: Mapped[str] = mapped_column()
    user_id: Mapped[int] = mapped_column(ForeignKey('user.id'))
    user: Mapped[User] = relationship('User', backref='preferences')

with app.app_context():
    db.create_all()

GOOGLE_CLIENT_ID = os.getenv('CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.getenv('CLIENT_SECRET')

CONF_URL = 'https://accounts.google.com/.well-known/openid-configuration'
oauth.register(
    name='google',
    client_id = GOOGLE_CLIENT_ID,
    client_secret = GOOGLE_CLIENT_SECRET,
    server_metadata_url=CONF_URL,
    client_kwargs={
        'scope': 'openid email profile'
    }
)

# all the routes
# @app.route("/users")
# def user_list():
#     users = db.session.execute(db.select(User).order_by(User.username)).scalars()
#     return render_template("user/list.html", users=users)

@app.route('/')
def homepage():
    if 'user' in session:
        user = session['user']
        # check if user has already been to site before and has a previous selection
        email = session.get('user').get('email')
        user = User.query.filter_by(email=email).first()
        prev_userinterests = UserInterests.query.filter_by(user_id=user.id).first()
        print("User in session")
    else:
        print("User not in session")
        return render_template('login.html')
    return render_template('home.html', prev=prev_userinterests)

@app.route('/search', methods=['POST'])
def search():
    location = request.form.get('location')
    interests = request.form.getlist('interests')
    food = request.form.getlist('food')
    name = request.form.getlist('name')

    # check if the user entered any interests
    if len(interests) == 0:
        error = "Please select an interest"
        return render_template("results.html", error=error)
    
    email = session.get('user').get('email')
    user = User.query.filter_by(email=email).first()
    user_interests = UserInterests.query.filter_by(user_id=user.id).first()
    if user_interests:
        user_interests.location=location
        user_interests.interests=', '.join(interests)
        user_interests.food=', '.join(food)
        db.session.commit()
    else:
        user_interests = UserInterests(
            location=location, 
            interests=', '.join(interests),
            food=', '.join(food),
            user_id=user.id,
        )
        session['user_id'] = user.id
        db.session.add(user_interests)
        db.session.commit()
    
    interest_map = {
        'nature': 'natural',
        'sports': 'sport',
        'historical': 'historic',
        'architecture': 'architecture',
        'amusements': 'amusements',
    }
    kinds = ','.join(interest_map[i] for i in interests if i in interest_map)
    
    food_map = {
        'restaurants': 'restaurants',
        'fast food': 'fast_food',
        'cafes': 'cafes',
        'bars': 'bars',
    }
    foods = ','.join(food_map[i] for i in food if i in food_map)

    #opentripmap api call
    location_coords = {
        "New York City": (40.7128, -74.0060), 
        "Los Angeles": (34.052235, -118.243683),
        "Boston": (42.360081, -71.058884),
        "Chicago": (41.878113, -87.629799),
        "Miami": (25.761681, -80.191788)
    }
    #lat, lon = 40.7128, -74.0060
    lat, lon = location_coords[location][0], location_coords[location][1]
    places_response = fetch_places(lat, lon, radius=20000, kinds=kinds)
    food_response = fetch_places(lat, lon, radius=20000, kinds=foods)
    #filter out places with no names and choose 5 random ones
    random5 = random.choices([place for place in places_response['features'] if place['properties']['name'] != ''], k=min(5, len(places_response['features'])))
    random3 = random.choices([food for food in food_response['features'] if food['properties']['name'] != ''], k=min(3, len(food_response['features'])))
    
    return render_template('results.html', interests=interests, places=random5, foods=random3, destination=location, name=name)

@app.route('/prev/')
def prev():
    if 'user' in session:
        email = session.get('user').get('email')
        user = User.query.filter_by(email=email).first()
        prev_userinterests = UserInterests.query.filter_by(user_id=user.id).all()
        print(prev_userinterests[0].interests)
        print(prev_userinterests[0].location)
    return render_template('prev.html', user=user, previous=prev_userinterests[0])

@app.route('/login')
def login():
    if 'user' in session:
        return redirect(url_for('/'))
    redirect_uri = url_for('auth', _external=True)
    return oauth.google.authorize_redirect(redirect_uri)
    
def user_create(name, email):
    user = User(
        name=name,
        email=email,
    )
    db.session.add(user)
    print("User Added: ", user)
    db.session.commit()

@app.route('/auth')
def auth():
    if 'user' not in session:
        token = oauth.google.authorize_access_token()
        session['user'] = token['userinfo']
        user_info = session['user']
        user = User.query.filter_by(email=user_info['email']).first()
        if not user:
            user_create(user_info['name'], user_info['email'])
    return redirect('/')

@app.route('/logout', methods=['POST'])
def logout():
    session.pop('user', None)
    return redirect('/')

if __name__ == '__main__':
    app.run(debug=True)
