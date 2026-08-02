from functools import wraps

from flask import Flask, request, render_template, make_response, redirect, url_for, flash, abort
from flask_login import LoginManager, login_user, logout_user, current_user, login_required

from routes.admin.player_routes import player_routes
from routes.admin.relevant_drops_routes import relevant_drop_routes
from routes.admin.team_routes import team_routes
from routes.admin.tile_routes import tile_routes
from routes.tutorial_routes import tutorial_routes
from routes.user_routes import user_routes
from routes.admin.admin_routes import admin_routes
from routes.dink import drop_submission_route
from routes.board_routes import board_routes
import os
import threading
from dotenv import load_dotenv
load_dotenv()
import bot

from utils.database import (
    add_user,
    get_user_by_email,
    check_password,
    get_user_by_id,
    ensure_schema
)

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'development secret')

login_manager = LoginManager(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return get_user_by_id(user_id)

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        user = get_user_by_email(email)
        if user:
            flash('Email is already registered.', 'danger')
            return redirect(url_for('register'))
        add_user(username, email, password)
        flash('Your account has been created! You can now log in', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = get_user_by_email(email)
        if user and check_password(user.password, password):
            login_user(user)
            return redirect(url_for('home'))
        else:
            flash('Login Unsuccessful. Please check email and password', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('home'))

@app.route('/getcookie')
def get_cookie(key):
    value = request.cookies.get(key)
    return value

@app.route('/setcookie')
def set_cookie(key, value):
    resp = make_response("Cookie is set")
    resp.set_cookie(key, value, max_age=60*60*24*30,
                    samesite='Strict')
    return resp


app.config['UPLOAD_FOLDER'] = 'uploads'

app.register_blueprint(drop_submission_route, url_prefix='/dink')
app.register_blueprint(admin_routes, url_prefix="/admin")
app.register_blueprint(user_routes, url_prefix="/user")
app.register_blueprint(board_routes, url_prefix='/board')
app.register_blueprint(tutorial_routes, url_prefix="/tutorial")
app.register_blueprint(tile_routes, url_prefix="/tile")
app.register_blueprint(team_routes, url_prefix="/team")
app.register_blueprint(player_routes, url_prefix="/player")
app.register_blueprint(relevant_drop_routes, url_prefix="/relevant_drop")

def start_bot():
    bot.run()

def create_app():
    return app

if __name__ == "__main__":
    ensure_schema()
    from waitress import serve

    print("Starting bot....")
    bot_thread = threading.Thread(target=start_bot)
    bot_thread.start()
    print("Bot started!")

    print("Starting server...")
    port = os.environ.get('PORT', 80)
    print("Server started!")
    serve(app, host="0.0.0.0", port=port)
