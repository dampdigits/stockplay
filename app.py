"""Flask App"""

from datetime import datetime
from cs50 import SQL
from flask import Flask, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")
stock = {}


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""

    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""

    # Query database for user info
    user_info = db.execute("SELECT * FROM users WHERE id = ?", session["user_id"])

    # Query database for stock & shares owned by user
    stocks = db.execute(
        "SELECT symbol, shares FROM stocks WHERE username = ?", user_info[0]["username"]
    )

    # To store user stocks and current values
    stock_holdings = []

    # To store net worth of user portfolio
    portfolio_value = 0

    for item in stocks:
        temp = {}
        temp["symbol"] = item["symbol"]
        temp["shares"] = item["shares"]
        temp["stock_price"] = lookup(temp["symbol"])["price"]
        temp["holding_value"] = temp["shares"] * temp["stock_price"]

        stock_holdings.append(temp)

        # Add value of stock holding to net worth
        portfolio_value += temp["holding_value"]

    # If no stocks
    if not stocks:
        temp = {}
        temp["symbol"] = "None"
        temp["shares"] = 0
        temp["stock_price"] = 0.00
        temp["holding_value"] = 0.00
        stock_holdings.append(temp)

    # Add user cash to net worth
    portfolio_value += user_info[0]["cash"]

    # Display homepage
    return render_template(
        "index.html",
        user_stocks = stock_holdings,
        portfolio_value = portfolio_value,
        user_info = user_info,
    )


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    # Query database for user info
    user_info = db.execute("SELECT * FROM users WHERE id = ?", session["user_id"])

    # Query database for user's transaction history
    transactions = db.execute(
        "SELECT * FROM history WHERE username = ?", user_info[0]["username"]
    )

    # Display webpage containing history
    return render_template("history.html", transactions = transactions)


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # User reached route via GET (requesting registration page)
    if request.method == "GET":
        return render_template("register.html")

    # User reached route via POST (redirect to homepage)
    # Ensure form was filled
    if (
        (not request.form.get("username"))
        or (not request.form.get("password"))
        or (not request.form.get("confirmation"))
    ):
        return apology("missing input", 400)

    # Ensure password was confirmed correctly
    if request.form.get("password") != request.form.get("confirmation"):
        return apology("confirmed password doesn't match", 400)

    # Query database to fetch list of usernames
    username_list = db.execute("SELECT username FROM users")

    # Search matching username from list of dictionaries
    for username in username_list:
        if request.form.get("username") == username["username"]:
            return apology("sorry this username is unavailable", 400)

    # Add new user to database
    db.execute(
        "INSERT INTO users (username,hash) VALUES (?,?)",
        request.form.get("username"),
        generate_password_hash(request.form.get("password")),
    )

    # Query database for user info
    user_info = db.execute(
        "SELECT * FROM users WHERE username = ?", request.form.get("username")
    )

    # Remember which user has logged in
    session["user_id"] = user_info[0]["id"]
    session["user_name"] = user_info[0]["username"]

    # Redirect user to home page
    return redirect("/")


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via GET (as by clicking a link or via redirect)
    if request.method == "GET":
        return render_template("login.html")

    # User reached route via POST (as by submitting a form via POST)
    # Query database for user info
    user_info = db.execute(
        "SELECT * FROM users WHERE username = ?", request.form.get("username")
    )

    # Ensure username exists and password is correct
    if len(user_info) != 1 or not check_password_hash(
        user_info[0]["hash"], request.form.get("password")
    ):
        return apology("invalid username and/or password", 403)

    # Remember which user has logged in
    session["user_id"] = user_info[0]["id"]
    session["user_name"] = user_info[0]["username"]

    # Redirect user to home page
    return redirect("/")


@app.route("/logout")
def logout():
    """Log user out"""

    global stock

    # Forget any user_id
    session.clear()
    stock = {}

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""

    global stock

    # User reached route via GET (Look up stocks)
    if request.method == "GET":
        return render_template("findstock.html")

    # User reached route via POST (show details of requested stock)
    # Get requested stock details
    stock = lookup(request.form.get("symbol"))

    # Verify stock validity
    if not stock:
        return apology("invalid stock symbol", 400)

    return render_template("stockquote.html", stock = stock)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    global stock

    # User reached route via GET (Look up stocks)
    if request.method == "GET":
        return render_template("findtock.html")

    # User reached route via POST (Buy requested stock)
    # Ensure form was filled
    if (not request.form.get("symbol")) or (not request.form.get("shares")):
        return apology("missing input", 400)

    # Ensure stock symbol was confirmed
    if not request.form.get("symbol").upper() == stock["symbol"]:
        return apology("incorrect stock symbol", 400)

    # Check validity of number of shares
    if not request.form.get("shares").isdigit():
        return apology("invalid number of shares", 400)

    # Remember shares requested to buy
    new_shares = int(request.form.get("shares"))

    # Calculate cost of buying the shares of stock
    cost = new_shares * stock["price"]

    # Query database for user info
    user_info = db.execute("SELECT * FROM users WHERE id = ?", session["user_id"])

    # Check for insufficient balance
    if cost > user_info[0]["cash"]:
        return apology("you have insufficient balance", 400)

    # Query database for user shares
    user_shares = db.execute(
        "SELECT shares FROM stocks WHERE symbol = ? AND username = ?",
        stock["symbol"],
        user_info[0]["username"],
    )

    # Get transaction date and time
    date = datetime.now().strftime("%d-%m-%Y")
    time = datetime.now().strftime("%H:%M:%S")

    # Update user stocks in database
    # Add stock if user had no shares of it
    if not user_shares:
        db.execute(
            "INSERT INTO stocks (username, symbol, shares) VALUES (?,?,?)",
            user_info[0]["username"],
            stock["symbol"],
            new_shares,
        )
    # Increase shares if user already had shares
    else:
        db.execute(
            "UPDATE stocks SET shares = ? WHERE username = ? AND symbol = ?",
            (user_shares[0]["shares"] + new_shares),
            user_info[0]["username"],
            stock["symbol"],
        )

    # Store transaction details in history
    db.execute(
        """INSERT INTO history 
        (username, action, symbol, shares, rate, total_value, date, time)
        VALUES (?,?,?,?,?,?,?,?)""",
        user_info[0]["username"],
        "bought",
        stock["symbol"],
        new_shares,
        stock["price"],
        cost,
        date,
        time,
    )

    # Calculate balance after purchase
    new_balance = user_info[0]["cash"] - cost

    # Reduce cash in database
    db.execute(
        "UPDATE users SET cash = ? WHERE id = ?", new_balance, user_info[0]["id"]
    )

    # Reset
    stock = {}

    # Redirect to home page
    return redirect("/")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    global stock

    # # User reached route via GET (requesting page to sell stocks)
    if request.method == "GET":
        # Query database for stock symbols owned by user
        stock_symbols = db.execute(
            """SELECT symbol FROM stocks, users
            WHERE stocks.username = users.username
            AND users.id = ?""",
            session["user_id"],
        )

        return render_template("sellstock.html", stock_symbols=stock_symbols)

    # User reached route via POST (sell stocks upon form submission)
    # Ensure form was filled
    if (not request.form.get("symbol")) or (not request.form.get("shares")):
        return apology("missing", 400)

    # Check validity of number of shares
    if not request.form.get("shares").isdigit():
        return apology("invalid number of shares", 400)

    # Remember shares requested to buy
    sale_shares = int(request.form.get("shares"))

    # Get requested stock details
    stock = lookup(request.form.get("symbol"))

    # Query database for user info
    user_info = db.execute("SELECT * FROM users WHERE id = ?", session["user_id"])

    # Query database for user shares
    user_shares = int(
        db.execute(
            "SELECT shares FROM stocks WHERE symbol = ? AND username = ?",
            stock["symbol"],
            user_info[0]["username"],
        )[0]["shares"]
    )

    # Remaining shares
    remaining_shares = user_shares - sale_shares

    # Check validity of number of shares
    if remaining_shares < 0 or sale_shares < 0:
        return apology("you own lesser shares", 400)

    # Calculate cash obtained from selling
    income = sale_shares * stock["price"]

    # Get transaction date and time
    date = datetime.now().strftime("%d-%m-%Y")
    time = datetime.now().strftime("%H:%M:%S")

    # Update user stocks in database
    # Remove stock if no shares remain
    if remaining_shares == 0:
        db.execute("DELETE FROM stocks WHERE symbol = ?", stock["symbol"])
    else:
        db.execute(
            "UPDATE stocks SET shares = ? WHERE username = ? AND symbol = ?",
            remaining_shares,
            user_info[0]["username"],
            stock["symbol"],
        )

    # Store transaction details in history
    db.execute(
        """INSERT INTO history
        (username, action, symbol, shares, rate, total_value, date, time)
        VALUES (?,?,?,?,?,?,?,?)""",
        user_info[0]["username"],
        "sold",
        stock["symbol"],
        request.form.get("shares"),
        stock["price"],
        income,
        date,
        time,
    )

    # Calculate balance after selling
    new_balance = user_info[0]["cash"] + income

    # Increase user's cash in database
    db.execute(
        "UPDATE users SET cash = ? WHERE id = ?", new_balance, user_info[0]["id"]
    )

    # Reset
    stock = {}

    # Display homepage after stock selling
    return redirect("/")


@app.route("/pswdchange", methods=["GET", "POST"])
@login_required
def pswdchange():
    """Change user password"""

    # User reached route via GET (user requesting to change password)
    if request.method == "GET":
        return render_template("pswdchange.html")

    # User reached route via POST (change password on submission)
    # Query database for user info
    user_info = db.execute("SELECT * FROM users WHERE id = ?", session["user_id"])

    # Check if old password is invalid
    if not check_password_hash(
        user_info[0]["hash"], request.form.get("old-password")
    ):
        return apology("wrong password", 401)

    # Change password
    db.execute(
        "UPDATE users SET hash = ? WHERE id = ?",
        generate_password_hash(request.form.get("new-password")),
        session["user_id"],
    )

    # Redirect to homepage
    return redirect("/")


@app.route("/addcash", methods=["GET", "POST"])
@login_required
def addcash():
    """Allow user to add more cash"""

    # User reached route via GET (Provide form to request cash)
    if request.method == "GET":
        return render_template("addcash.html")

    # User reached route via POST (Add cash amount)
    # Check for invalid amount
    if not request.form.get("cash").isdigit():
        return apology("invalid cash amount", 403)

    # Remember cash amount to be added
    new_cash = int(request.form.get("cash"))

    # Query database for user cash
    user_cash = db.execute(
        "SELECT cash FROM users WHERE id = ?", session["user_id"]
    )

    # Query database to update cash amount
    db.execute(
        "UPDATE users SET cash = ? WHERE id = ?",
        user_cash[0]["cash"] + new_cash,
        session["user_id"],
    )

    # Get transaction date and time
    date = datetime.now().strftime("%d-%m-%Y")
    time = datetime.now().strftime("%H:%M:%S")

    # Add event to transaction history
    db.execute(
        """INSERT INTO history
        (username, action, symbol, shares, rate, total_value, date, time)
        VALUES (?,?,?,?,?,?,?,?)""",
        session["user_name"],
        "added cash",
        "N.A.",
        "0",
        "0.0",
        new_cash,
        date,
        time,
    )

    # Redirect to homepage
    return redirect("/")
