import os

from cs50 import SQL
from flask import Flask, render_template, request, session, redirect, url_for
from flask_session import Session
from flask_socketio import join_room, leave_room, send, SocketIO
from functools import wraps
import random 
from string import ascii_uppercase
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.static_url_path = '/static'

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

app.config["SECRET_KEY"] = "key_name" #key doesnt matter right now this isnt a public application so doesnt need to be secure
socketio = SocketIO(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///accounts.db")

#setting a dictionary for the chat rooms 
rooms = {}

# Define the showErrorAndRedirect function
def showError(message):
    return f"<script>alert('{message}');</script>"

#Define the generate unique code function
def generate_unique_code(length):
    while True:
        code = ""
        for _ in range(length):
            code += random.choice(ascii_uppercase)
        if code not in rooms:
            break     
    return code

#defining login @login_required
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

#This code ensures that HTTP responses are not cached by the client browser, 
# so that clients always receive the latest data from the server in real-time.
@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return showError("must provide username")
    

        # Ensure password was submitted
        elif not request.form.get("password"):
            return showError("must provide password")
            

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return showError("invalid username and/or password")

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]
        session["username"] = rows[0]["username"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    
    # Forget any user_id
    session.clear()

    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            return showError("must provide username")

        # Ensure password was submitted
        elif not request.form.get("password") or not request.form.get("confirm-password"):
            return showError("must provide password")
        
        # Ensure password and confirmation match
        elif request.form.get("password") != request.form.get("confirm-password"):
            return showError("passwords must match")

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))
        
        # Ensure username is not already taken
        if len(rows) > 0:
            return showError("username already taken")
        # Insert new user into database
        db.execute("INSERT INTO users (username, hash) VALUES (?, ?)",
                    request.form.get("username"), generate_password_hash(request.form.get("password")))

        # Redirect user to home page
        return redirect("/")
    else:
        return render_template("register.html")
    
@app.route("/", methods=["POST", "GET"])
@login_required
def home():
    if request.method == "POST":
        code = request.form.get("code")
        join = request.form.get("join", False)
        create = request.form.get("create", False)

        if join != False and not code:
            return showError("please enter a room code")
        
        room = code
        if create != False:
            room = generate_unique_code(4)
            rooms[room] = {"members": 0, "messages": []}
        elif code not in rooms:
            return showError("room does not exist")
        
        session["room"] = room
        return redirect(url_for("room"))

    return render_template("home.html")


@app.route("/room")
def room():
    room = session.get("room")
    if room is None or room not in rooms:
        return redirect(url_for("home"))

    return render_template("room.html", code=room, messages=rooms[room]["messages"])

@socketio.on("message")
def message(data):
    room = session.get("room")
    if room not in rooms:
        return
    
    content = {
        "name": session["username"],
        "message": data["data"]
    }
    send(content, to=room)
    rooms[room]["messages"].append(content)


@socketio.on("connect")
def connect(auth):
    room = session.get("room")
    name = session["username"]
    if not room or not name:
        return
    if room not in rooms:
        leave_room(room)
        return
    
    join_room(room)
    send({"name": name, "message": " has joined the room"}, to=room)
    rooms[room]["members"] +=1
    print(f"{name} joined room {room}")

@socketio.on("disconnect")
def disconnect():
    room = session.get("room")
    name = session["username"]
    leave_room(room)

    if room in rooms:
        rooms[room]["members"] -= 1
        if rooms[room]["members"] <= 0:
            del rooms[room]
    send({"name": name, "message": " has left the room"}, to=room)
    print(f"{name} left the room {room}")


if __name__ == "__main__":
    socketio.run(app, debug=True)