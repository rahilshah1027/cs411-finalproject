from flask import Flask, url_for, session
from flask import render_template, redirect
from flask_sqlalchemy import SQLAlchemy
from authlib.integrations.flask_client import OAuth
from sqlalchemy import Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
import os, requests
from api import fetch_places
from flask import jsonify, request
from dotenv import load_dotenv

app = Flask(__name__, template_folder='../client/templates')
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
#class Itinerary(db.Model):
    #pass
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
        print("User in session")
    else:
        print("User not in session")
        return redirect(url_for('login'))

    return render_template('home.html')

@app.route('/search', methods=['POST'])
def search():
    interests = request.form.getlist('interests')
    locations = {
        'amusement': 'Disneyland Park, Anaheim, CA',
        'sports': 'Yankee Stadium, Bronx, NY',
        # Add more interests and locations as needed
    }
    selected_locations = [locations[interest] for interest in interests if interest in locations]

    #opentripmap api call
    #interests = request.form.getlist('interests')
    lat, lon = 40.7128, -74.0060
    places_response = fetch_places(lat, lon)
    #kinds = ','.join(interests)
    
    return render_template('results.html', selected_locations=selected_locations, places=places_response['features'])

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
    db.session.commit()
    print("User Added: ", user)
    return redirect(url_for('/'))

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

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect('/')

if __name__ == '__main__':
    app.run(debug=True)
