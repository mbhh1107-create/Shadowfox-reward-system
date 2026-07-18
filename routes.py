from flask import *
from datetime import datetime
import database
import pandas as pd

user_details = {}
session = {}
page = {}

# Initialise the application
app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

#####################################################
##  INDEX
#####################################################

@app.route('/')
def index():
    # Check if the user is logged in
    if ('logged_in' not in session or not session['logged_in']):
        return redirect(url_for('login'))
    page['title'] = 'ShadowFox Rewards System'
    
    return redirect(url_for('dashboard'))

#####################################################
##  LOGIN
#####################################################

@app.route('/login', methods=['POST', 'GET'])
def login():
    if (request.method == 'POST'):
        login_return_data = check_login(request.form['username'], request.form['password'])

        if login_return_data is None:
            page['bar'] = False
            flash("Incorrect login info, please try again.")
            return redirect(url_for('login'))

        # Log them in
        page['bar'] = True
        welcomestr = f"Welcome back, {login_return_data['username']}"
        flash(welcomestr)
        session['logged_in'] = True

        global user_details
        user_details = login_return_data
        return redirect(url_for('index'))

    elif (request.method == 'GET'):
        return render_template('login.html', page=page)

#####################################################
##  LOGOUT
#####################################################

@app.route('/logout')
def logout():
    session['logged_in'] = False
    page['bar'] = True
    flash('You have been logged out. See you soon!')
    return redirect(url_for('index'))

#####################################################
##  DASHBOARD
#####################################################

@app.route('/dashboard', methods=['GET'])
def dashboard():
    if 'logged_in' not in session or not session['logged_in']:
        return redirect(url_for('login'))

    clubs = database.get_all_clubs()

    # Debug: Print the fetched data
    print(clubs)  # Ensure this prints the list of clubs with all columns
    return render_template('dashboard.html', clubs=clubs, session=session, page=page)


#####################################################
##  ADD CLUB
#####################################################

@app.route('/add-club', methods=['GET', 'POST'])
def add_club():
    if ('logged_in' not in session or not session['logged_in']):
        return redirect(url_for('login'))

    if (request.method == 'GET'):
        return render_template('add_club.html', session=session, page=page)

    elif (request.method == 'POST'):
        success = database.add_club(request.form['club_name'], request.form['referral_id'])
        if success:
            page['bar'] = True
            flash("Club added successfully!")
            return redirect(url_for('dashboard'))
        else:
            page['bar'] = False
            flash("Error: Club name or referral ID already exists.")
            return redirect(url_for('add_club'))

#####################################################
##  REDEEM REWARDS
#####################################################

@app.route('/redeem-rewards', methods=['GET', 'POST'])
def redeem_rewards():
    if 'logged_in' not in session or not session['logged_in']:
        return redirect(url_for('login'))

    if request.method == 'GET':
        rewards = database.get_all_rewards()
        return render_template('redeem_rewards.html', rewards=rewards, session=session, page=page)

    elif request.method == 'POST':
        club_name = request.form.get('club_name')
        referral_id = request.form.get('referral_id')

        # Strip the "reward_" prefix from keys in the rewards input
        rewards_input = {
            key.replace("reward_", ""): int(value)
            for key, value in request.form.items() if key.startswith('reward_')
        }

        # Debugging inputs
        print(f"Club Name: {club_name}")
        print(f"Referral ID: {referral_id}")
        print(f"Rewards Input: {rewards_input}")

        # Call the redeem_rewards function
        result = database.redeem_rewards(club_name, referral_id, rewards_input)

        if result.startswith("Error"):
            flash(result, "error")
            return redirect(url_for('redeem_rewards'))
        elif result.startswith("Success"):
            flash(result, "success")
            return redirect(url_for('dashboard'))
        else:
            flash("Unknown error occurred.", "error")
            return redirect(url_for('redeem_rewards'))



#####################################################
##  UPDATE REGISTRATIONS
#####################################################

@app.route('/update-registrations', methods=['GET', 'POST'])
def update_registrations():
    if 'logged_in' not in session or not session['logged_in']:
        return redirect(url_for('login'))

    if request.method == 'GET':
        return render_template('update_registrations.html', session=session, page=page)

    elif request.method == 'POST':
        # Check if the file is part of the request
        if 'file' not in request.files:
            flash("No file part found in the request", "error")
            return redirect(url_for('update-registrations'))

        file = request.files['file']

        # Ensure the file is not empty
        if file.filename == '':
            flash("No file selected. Please upload a valid CSV file.", "error")
            return redirect(url_for('update-registrations'))

        try:
            # Read the CSV file
            data = pd.read_csv(file)
            print("CSV data successfully read")
            print(data.head())  # Debugging

            # Pass the data to the database for processing
            success = database.update_registrations(data)

            if success:
                flash("Registrations updated successfully!", "success")
            else:
                flash("Failed to update registrations.", "error")
        except ParserError as e:  # Using the explicit import
            flash("Error parsing the CSV file. Ensure it is formatted correctly.", "error")
            print(f"Parsing error: {e}")
        except Exception as e:
            flash("An unexpected error occurred. Please try again.", "error")
            print(f"Unexpected error: {e}")

        return redirect(url_for('dashboard'))



#####################################################
##  SEARCH CLUB
#####################################################

@app.route('/search', methods=['GET'])
def search_club():
    if ('logged_in' not in session or not session['logged_in']):
        return redirect(url_for('login'))

    club_name = request.args.get('club_name')
    if not club_name:
        flash("Club Name is required.", "error")
        return redirect(url_for('dashboard'))

    club = database.search_club(club_name)
    if not club:
        flash("Club not found.", "error")
        return redirect(url_for('dashboard'))

    return render_template('search_club.html', club=club, session=session, page=page)

#####################################################
##  LOGIN CHECK FUNCTION
#####################################################

def check_login(username, password):
    admin_info = database.check_login(username, password)
    if admin_info is None:
        return None
    else:
        return {
            'username': admin_info[0],
        }