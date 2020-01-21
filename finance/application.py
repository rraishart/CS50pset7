from cs50 import SQL
from flask import (Flask, flash, redirect, render_template,
                request, session, url_for)
from flask_session import Session
from passlib.apps import custom_app_context as pwd_context
from tempfile import mkdtemp

from helpers import *
#
# configure application
app = Flask(__name__)

# ensure responses aren't cached
if app.config["DEBUG"]:
    @app.after_request
    def after_request(response):
        response.headers[
            "Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Expires"] = 0
        response.headers["Pragma"] = "no-cache"
        return response

# custom filter
app.jinja_env.filters["usd"] = usd

# configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

@app.route("/")
@login_required
def index():
    # get list of symbol names for order history
    rows = db.execute(
        "SELECT symbol FROM orderhistory WHERE userid = :userid",
            userid=session["user_id"])
    symbolset = set()
    # remove duplicate names
    for row in rows:
        symbolset.add(row['symbol'])
        
    # check inventory
    symbols = set()
    for symbol in symbolset:
        shares = getshares(db, session['user_id'], symbol)
        # remove symbol if all sold
        if shares > 0:
            symbols.add(symbol)
            
    portfolio = []    
    
    for symbol in symbols:
        # store name
        stock = [symbol]
        # store quantity
        shares = getshares(db, session['user_id'], symbol)
        stock.append(shares)
        # store price
        price = lookup(symbol)
        stock.append(price["price"])
        # store holdings
        stock.append(price["price"] * shares)
        # store stock
        portfolio.append(stock)
        print(portfolio)
        
    # find value of shares
    stockvalue = 0
    for stock in portfolio:
        stockvalue = stockvalue + stock[3]
        
    # format portfolio
    for stock in portfolio:
        stock[2] = usd(stock[2])
        stock[3] = usd(stock[3])
    # get users cash
    rows = db.execute(
                    "SELECT cash, username FROM users WHERE id = :id",
                        id=session["user_id"])
                    
    return render_template(
        "index.html", port = portfolio, cash = usd(rows[0]["cash"]),
            total = usd(rows[0]["cash"] + stockvalue))

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock."""
    if request.method=="POST":
        # check symbol
        method = "buy"
        
        if (request.form.get("symbol") and
            lookup(request.form.get("symbol")) is not None):
            # check number of shares
            shares = int(request.form.get("shares"))
            
            if shares > 0:
                rows = db.execute(
                    "SELECT cash, username FROM users WHERE id = :id",
                        id=session["user_id"])  
                # find total cost
                stock = lookup(request.form.get("symbol"))
                total = stock["price"] * shares
                
                # check funds
                if total < rows[0]["cash"]:
                    # update cash
                    db.execute(
                        "UPDATE users SET cash=cash-:total WHERE id = :id",
                            total=total, id=session["user_id"])  
                    # insert record
                    db.execute(
                        """INSERT INTO orderhistory (
                            userid, username, method, symbol, shares, price)
                            VALUES (:userid, :username, :method, :symbol,
                            :shares, :price)""",
                            userid=session["user_id"],
                            username=rows[0]["username"], method = method,
                            symbol=request.form.get("symbol"),
                            shares=shares, price=total)
                else:
                    return apology("Not enough money")
            else:
                return apology("Enter valid number of shares")
        else:
            return apology("invalid symbol")
        return redirect(url_for("index"))
    else:
        return render_template("buy.html")
    
@app.route("/history")
@login_required
def history():
    """Show history of transactions."""
    rows = db.execute(
        "SELECT * FROM orderhistory WHERE userid=:userid",
         userid=session['user_id'])
         
    # format price
    for row in rows:
        row['price'] = usd(row['price'])
        
    return render_template("history.html", history=rows)

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in."""

    # forget any user_id
    session.clear()

    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username")
            
        elif not request.form.get("password").isalnum():
            return apology("Password can only contain", "numbers and letters")
            
        # ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password")

        # query database for username
        rows = db.execute(
            "SELECT * FROM users WHERE username = :username",
            username=request.form.get("username"))

        # ensure username exists and password is correct
        if (len(rows) != 1 or not pwd_context.verify(request.form.get(
            "password"), rows[0]["hash"])):
            return apology("invalid username and/or password")

        # remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # redirect user to home page
        return redirect(url_for("index"))

    # else if user reached route via GET (as by clicking link or via redirect)
    else:
        return render_template("login.html")

@app.route("/logout")
def logout():
    """Log user out."""

    # forget any user_id
    session.clear()

    # redirect user to login form
    return redirect(url_for("login"))

@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method=="POST":
        if not request.form.get("symbol"):
           return apology("No symbol entered")
           
        elif not lookup(request.form.get("symbol")):
            return apology("Invalid", "symbol")
            
        price = lookup(request.form.get("symbol"))
        price['price'] = usd(price['price'])
        return render_template("quoted.html", price=price)
        
    else:
        return render_template("quote.html")

    
@app.route("/password", methods=["GET", "POST"])
@login_required
def password():
    """Change users password"""
    if request.method=="POST":
        pw = db.execute(
            "SELECT hash FROM users WHERE id=:userid",
            userid=session['user_id'])
        if not request.form.get("currentpw"):
            return apology("Enter your", "current password")
            
        elif not pwd_context.verify(request.form.get("currentpw"),
        pw[0]['hash']):
            return apology("Incorrect", "current password")
            
        elif not request.form.get("newpw"):
            return apology("Enter a", "new password")
            
        elif not request.form.get("confirmpw"):
            return apology("Please confirm", "your password")
            
        elif request.form.get("newpw") != request.form.get("confirmpw"):
            return apology("Passwords", "don't match")
            
        elif not request.form.get("newpw").isalnum():
            return apology("Password can only contain", "numbers and letters")
            
        pw = pwd_context.encrypt(request.form.get("newpw"))
        db.execute(
            "UPDATE users SET hash=:password WHERE id=:userid",
            password=pw, userid=session['user_id'])
        return redirect(url_for("index"))
        
    else:
        return render_template("password.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user."""
    #forget any user_id
    session.clear()
    
    # if user reached route via POST (as by submitting a form via POST)
    if request.method=="POST":
        
        #ensure username was entered
        if not request.form.get("username"):
            return apology("Must provide a username")
            
        # ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password")
            
        elif not request.form.get("password").isalnum():
            return apology("Password can only contain", "numbers and letters")
            
        # ensure password confirmed
        elif not request.form.get("passwordConfirm"):
            return apology("please confirm password")
            
        # query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))
        
        #ensure username is available
        if len(rows) > 0:
            return apology("Username is already taken")
            
        # ensure passwords match
        elif request.form.get("password") != request.form.get(
                              "passwordConfirm"):
             return apology("passwords must match")
        
        # encrypt password
        hash = pwd_context.encrypt(request.form.get("password"))
        
        # register user
        db.execute(
            "INSERT INTO users (username, hash) VALUES (:username, :hash)",
        username = request.form["username"], hash=hash)   
    else:
        return render_template("register.html")
        
    return apology("You may now log in")    
             
@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock."""
    if request.method=="POST":
        # check symbol
        method = "sell"
        
        if (request.form.get("symbol") and
        lookup(request.form.get("symbol")) is not None):
            # check number of shares
            shares = int(request.form.get("shares"))
            
            if shares > 0:
                # ensure sufficent shares
                if (getshares(
                    db, session['user_id'],
                    request.form.get("symbol")) >= shares):
                        
                    # find total cost
                    stock = lookup(request.form.get("symbol"))
                    total = stock["price"] * shares 
                    username = db.execute(
                        "SELECT username FROM users WHERE id = :id",
                        id=session['user_id'])
                    username = username[0]['username']
                    # insert record
                    db.execute(
                        """INSERT INTO orderhistory (
                            userid, username, method,
                            symbol, shares, price)
                            VALUES (:userid, :username, 
                            :method, :symbol, :shares, :price)""",
                            userid=session["user_id"], username=username, 
                            method = method,
                            symbol=request.form.get("symbol"),
                            shares=shares, price=total)
                    # update cash
                    db.execute(
                        "UPDATE users SET cash=cash+:total WHERE id = :id",
                        total=total, id=session["user_id"])  
                else:
                    return apology("You dont have", "enough shares")
            else:
                return apology("Enter valid number of shares")
        else:
            return apology("invalid symbol")
        return redirect(url_for("index"))
    else:
        return render_template("sell.html")
    