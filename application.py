import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True


# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""

    # get current user_id
    user_id = session["user_id"]

    # get how much cash to the user's account
    user_cash = db.execute("SELECT cash FROM users WHERE id = ?", user_id)

    # get all actions off user
    stocks = db.execute(
        "SELECT symbol, sum(shares) FROM transactions WHERE user_id = ? GROUP BY symbol HAVING sum(shares) > 0 ORDER BY symbol ASC", user_id)

    # In the loop, we add to the dictionary array the values of the price, the name of the companies and the amount for each row
    total_actions = 0
    for stock in stocks:
        stock["all_shares"] = stock.pop("sum(shares)")
        quote = lookup(stock["symbol"])

        stock["name"] = quote["name"]
        stock["price"] = quote["price"]
        stock["total"] = quote["price"] * stock["all_shares"]

        # we count the sum of all shares
        total_actions += stock["total"]

    # calculate grand total (total value plus cash)
    total = user_cash[0]["cash"] + total_actions

    return render_template("index.html", cash=user_cash, stocks=stocks, total=total)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    if request.method == "POST":

        # get the "symbol" value from the form
        symbol = request.form.get("symbol")
        if not symbol:
            return apology("missing symbol")
        # get the "shares" value from the form

        shares = request.form.get("shares")
        if not shares:
            return apology("missing shares")

        if shares.isnumeric() == False:
            return apology("Invalid shares")

        shares = int(shares)
        if shares < 1:
            return apology("Invalid shares")

        # Get a dictionary with data on company shares
        quote = lookup(symbol)

        # Checking for non-existent data
        if not quote:
            return apology("Invalid Symbol")

        # get the price of currently purchased shares
        price = quote["price"]

        # get current user_id
        user_id = session["user_id"]

        # get how much cash to the user's account
        user_cash = db.execute("SELECT cash FROM users WHERE id = ?", user_id)

        # Checking whether there is enough cash in the account for the transaction
        amount = price * shares
        if amount > user_cash[0]["cash"]:
            return apology("can't afford")

        balance = user_cash[0]["cash"] - amount

        db.execute("UPDATE users SET cash = ? WHERE id = ?", balance, user_id)

        db.execute(
            "INSERT INTO transactions (user_id, symbol, shares, price, operation_date, operation_type) VALUES(?, ?, ?, ?, CURRENT_TIMESTAMP, ?)", user_id, symbol, shares, price, "Buy")
        return redirect("/")
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    # get current user_id
    user_id = session["user_id"]

    operations = db.execute("SELECT * FROM transactions WHERE user_id = ? ORDER BY operation_date DESC", user_id)
    return render_template("history.html", operations=operations)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

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


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":

        # get the "symbol" value from the form
        symbol = request.form.get("symbol")

        # Get a dictionary with data on company shares
        quote = lookup(symbol)

        # Checking for non-existent data
        if not quote:
            return apology("Invalid Symbol")

        # Return the result
        return render_template("quoted.html", quote=quote)
    else:

        # Return the form for entering a stock’s symbol
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    if request.method == "POST":

        # Get data from the form
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        # Checking if there is already such a user
        userexist = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))
        if userexist:
            return apology("A user with this username already exists")

        # Checking for sending an empty field username
        if not username:
            return apology("No username entered")

        # Checking for sending an empty field password
        if not password:
            return apology("No password entered")

        # Checkings for the complexity of the entered password
        pass_len = len(password)

        # Restriction on setting a password of less than 6 characters
        if pass_len < 6:
            return apology("The password must be at least 6 characters long")
        if pass_len > 15:
            return apology("The password is too long. Max:15 characters")

        # Checking for the presence of a number in the string
        if any(map(str.isdigit, password)) == False:
            return apology("The password must contain at least one number")

        # Checking for the presence of a capital letters in the string
        if any(map(str.isupper, password)) == False:
            return apology("The password must contain at least one a capital letter")

        # Checking for the error of re-entering the password
        if password != confirmation:
            return apology("YOUR PASSWORDS DON'T MATCH")

        # Password hashing
        hashcode = generate_password_hash(password)
        db.execute("INSERT INTO users (username, hash) VALUES(?, ?)", username, hashcode)

        # In case of successful registration, we redirect to the main page
        return redirect("/")
    else:

        # Opening the registration form
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    user_id = session["user_id"]

    if request.method == "POST":

        # get the "symbol" value from the form
        symbol = request.form.get("symbol")
        if not symbol:
            return apology("missing symbol")

        # get the "shares" value from the form
        shares = request.form.get("shares")
        if not shares:
            return apology("missing shares")

        if shares.isnumeric() == False:
            return apology("Invalid shares")

        shares = int(shares)
        if shares < 1:
            return apology("Invalid shares")

        # Get a dictionary with data on company shares
        quote = lookup(symbol)

        # get the price of currently selling shares
        price = quote["price"]

        # Check how many shares of this company the user has
        user_shares = db.execute("SELECT SUM(shares) FROM transactions WHERE symbol = ?", symbol)

        # Checking whether there is enough actions for the transaction

        if user_shares[0]["SUM(shares)"] < shares:
            return apology("There are not enough shares")

        if user_shares[0]["SUM(shares)"] < 1:
            return apology("There are no such stocks in your portfolio")

        # get how much cash to the user's account
        user_cash = db.execute("SELECT cash FROM users WHERE id = ?", user_id)

        amount = price * shares

        balance = user_cash[0]["cash"] + amount

        db.execute("UPDATE users SET cash = ? WHERE id = ?", balance, user_id)

        # Assign a minus sign to a number
        shares = shares * -1

        db.execute(
            "INSERT INTO transactions (user_id, symbol, shares, price, operation_date, operation_type) VALUES(?, ?, ?, ?, CURRENT_TIMESTAMP, ?)", user_id, symbol, shares, price, "Sell")

        return redirect("/")
    else:
        actions = db.execute(
            "SELECT symbol FROM transactions WHERE user_id = ? GROUP BY symbol HAVING sum(shares) > 0 ORDER BY symbol ASC", user_id)
        return render_template("sell.html", actions=actions)


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
