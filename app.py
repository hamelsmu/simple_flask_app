import os
from flask import (Flask, session, render_template, 
                   session, redirect, url_for, request,
                   flash, jsonify)
from flask_session import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker


app = Flask(__name__)

# Check for environment variable
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")

# Configure session to use filesystem. Hamel: BOILERPLATE.
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Set up database
engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))

# think about logging in with sessions
# https://www.tutorialspoint.com/flask/flask_sessions.htm


@app.route("/", methods=["GET", "POST"])
def index():
    "Defines routes for main landing page."
    # So you can send alerts.  A better way to use this is flash() which you learned about later.
    error = None
    alert = session.pop('alert', None)

    # if user tries to login, try to authenticate them using naive approach.
    if request.method == "POST":
        email = request.form['email']

        if authenticate(email = email, password = request.form['password']):
            session['username'] = email
            return redirect(url_for('search'))

        else:
            error = f'Was not able to authenticate <span style="font-weight:bold">{email}</span>'

    return render_template("index.html", alert=alert, error=error)


@app.route("/register", methods=["GET", "POST"])
def register():
    "Routes for allowing new users to register."
    error=None
    
    # collect all data from user
    if request.method == "POST":
        email = request.form.get('email') 
        pass1 = request.form.get('password')
        pass2 = request.form.get('confirm-password')

        # Data validation
        if user_exists(email):
            error = f'User with email {email} already exists.'

        # make sure there are no blank fields
        blank_fields = [k for k, v in request.form.items() if v.strip() == '']
        if blank_fields:
            fields = (', ').join(blank_fields)
            error = f'The following fields were left blank: {fields}. Cannot register user.'
        
        if pass1 != pass2:
            error = 'Passwords entered do not match.'

        # Add user to database, and redirect back to login page
        if not error:
            try:
                db.execute("INSERT INTO book_users (email, password, name) VALUES (:email, :password, :name)",
                            {'email': email,
                            'name': request.form.get('name'),
                            'password': request.form.get('password')})
                db.commit()

                assert user_exists(email), f'Database error: {email} not inserted properly.'
                session['username'] = email
                session['alert'] = f'User <span style="font-weight:bold">{email}</span> created. Please login.'
                # take them to login screen
                return redirect(url_for('index'))

            # send exception directly back to user if this fails.
            except BaseException as exception:
                return render_template("register.html", error=f'Error: {exception}')
    
    return render_template("register.html", error=error)


@app.route('/logout')
def logout():
   "If user logs out, clear the session completely."
   session = {}
   return redirect(url_for('index'))


@app.route('/api/<string:username>')
def api(username):
   results = db.execute("SELECT * FROM query_logs WHERE email = :email",
                         {'email': username}).fetchall()
   return jsonify([dict(u) for u in results])


@app.route('/search', methods=['GET', 'POST'])
def search():
    "Routes for search page."
    # intialize state of the search page.
    error = None
    alert = None

    # Get Data from database that match query
    if request.method == 'POST' and not error:
        if not [x for x in request.form.values() if x.strip() != '']:
            error = 'You cannot leave all fields blank.'

        if not error:   
            session['results'] = search_books(**request.form)
            session['query'] = log_search(**request.form)
            print(session['query'])

            if not session['results']:
                alert = "Your query did not return any results."
        
    return render_template("search.html", 
                           username=session['username'], 
                           results=session['results'],
                           log_msg=session.get('query'),
                           error=error,
                           alert=alert)


@app.route('/log_relevant', methods=['POST'])
def log_relevant():
    "Save user feedback about query relevance to database."

    # get the relevance markers (checkboxes) from the form
    idxs = request.form.getlist('chkbox')

    # if there are no relevant queries, log this to database and pass warning.
    if not idxs:
        flash('Marked that no query results were relevant.')
        db.execute("""INSERT INTO query_logs (email, query, isbn_list) 
                  VALUES (:email, :query, :isbn_list)""",
                    {'email': session['username'],
                    'query': session['query'],
                    'isbn_list': 'None'})
        return redirect(url_for('search'))

    positions = [int(x) for x in idxs]
    isbns = [x.isbn for x in session['results']]
    
    # if there are relevant queries marked, log that information to the database.
    db.execute("""INSERT INTO query_logs (email, query, isbn_list, position_list, num_results, top_position, top_relevant) 
                  VALUES (:email, :query, :isbn_list, :position_list, :num_results, :top_position, :top_relevant)""",
                {'email': session['username'],
                'query': session['query'],
                'isbn_list': str([isbns[x] for x in positions]),
                'position_list': str(positions),
                'num_results': len(isbns),
                'top_position': min(positions),
                'top_relevant': isbns[positions[0]]})
    db.commit()
    flash(f'Saved {len(positions)} query results as relevant.')

    return redirect(url_for('search'))


@app.route('/data', methods=['GET'])
def data():
    "This allows you to see data from the database.  You probably don't want to do this for large data."

    # select all the data for the query history for the user that is logged in.
    results = db.execute("SELECT * FROM query_logs WHERE email = :email",
                         {'email': session['username']}).fetchall()
    return render_template('data.html', 
                           username=session['username'],
                           results=results)


def user_exists(email):
    "Check if the email exists as a registered user in the database."

    if db.execute("SELECT email FROM book_users WHERE email = :email",
                  {'email':email}).fetchone():
        return True
    else:
        return False


def authenticate(email, password):
    "Authenticate the user given their username and password."

    if db.execute("SELECT email FROM book_users WHERE email = :email and password = :password",
                  {'email': email, 'password': password}).fetchone():
        return True
    else:
        return False


def search_books(author, title, isbn):
    "Search for books using wildcard queries on all fields."

    results = db.execute("""SELECT isbn, title, author, year 
                            FROM books 
                            WHERE author ~* :author and
                                  title ~* :title and
                                  isbn ~* :isbn""" ,
                         {'author': author, 'title': title, 'isbn': isbn}).fetchall()
    return results


@app.after_request
def set_response_headers(response):
    "clear browser caches."

    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


def log_search(author, title, isbn):
    "Generate log of query parameters that is nicely formatted."

    author_log = '' if author == '' else f'Author: {author}'
    title_log = '' if title == '' else f'Title: {title}'
    isbn_log = '' if isbn == '' else f'ISBN: {isbn}'
    message = f'{author_log} {title_log} {isbn_log}'
    return message

