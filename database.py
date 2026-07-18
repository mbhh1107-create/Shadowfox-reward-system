import psycopg2
from psycopg2 import sql
from psycopg2.extras import DictCursor

# Database connection parameters
userid = "y24s2c9120_hmal0567"
passwd = "bxgHrSW2"
myHost = "awsprddbs4836.shared.sydney.edu.au"

# Open a connection to the database
def openConnection():
    """
    Opens and returns a database connection using psycopg2.
    Returns:
        conn: A psycopg2 connection object, or None if the connection fails.
    """
    try:
        conn = psycopg2.connect(
            host=myHost,
            database=userid,
            user=userid,
            password=passwd
        )
        print("Database connection established.")
        return conn
    except psycopg2.Error as e:
        print(f"Error connecting to the database: {e.pgerror or 'Unknown error'}")
        return None


# Check admin login
def check_login(username, password):
    conn = openConnection()
    if not conn:
        return None

    try:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute("SELECT username FROM admins WHERE username = %s AND password = %s", (username, password))
            result = cur.fetchone()
        conn.close()
        return result
    except psycopg2.Error as sqle:
        print("Error checking login: " + str(sqle.pgerror or "Unknown error"))
        return None

def get_all_clubs():
    conn = openConnection()
    if not conn:
        return []

    try:
        with conn.cursor() as cur:
            cur.execute("SELECT referral_id, club_name, points_balance FROM referral_mapping")
            rows = cur.fetchall()

            # Convert the result to a list of dictionaries
            clubs = [
                {'referral_id': row[0], 'club_name': row[1], 'points_balance': row[2]} for row in rows
            ]
        conn.close()
        return clubs
    except psycopg2.Error as sqle:
        print("Error retrieving clubs: " + str(sqle.pgerror or "Unknown error"))
        return []



# Add a new club
def add_club(club_name, referral_id):
    conn = openConnection()
    if not conn:
        return False

    try:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO referral_mapping (club_name, referral_id, points_balance) VALUES (%s, %s, 0)",
                        (club_name, referral_id))
            conn.commit()
        conn.close()
        return True
    except psycopg2.Error as sqle:
        print("Error adding club: " + str(sqle.pgerror or "Unknown error"))
        return False

# Redeem rewards
def redeem_rewards(club_name, referral_id, rewards_input):
    conn = openConnection()
    if not conn:
        return "Error: Database connection failed."

    try:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            # Step 1: Validate club name and referral ID
            cur.execute(
                "SELECT points_balance FROM referral_mapping WHERE club_name = %s AND referral_id = %s",
                (club_name, referral_id)
            )
            club = cur.fetchone()

            if not club:
                print("Club and referral ID do not match.")
                return "Error: Club name and referral ID do not match."

            current_points = club['points_balance']
            total_points_deducted = 0

            # Step 2: Calculate total points required
            for reward_type, quantity in rewards_input.items():
                if quantity > 0:
                    cur.execute("SELECT points_required FROM rewards WHERE reward_type = %s", (reward_type,))
                    reward = cur.fetchone()

                    if not reward:
                        print(f"Invalid reward type: {reward_type}")
                        return f"Error: Invalid reward type '{reward_type}'."

                    points_required = reward['points_required']
                    total_points_deducted += points_required * quantity

            # Log calculations
            print(f"Current Points: {current_points}")
            print(f"Total Points Deducted: {total_points_deducted}")

            # Step 3: Check if enough points are available
            if current_points < total_points_deducted:
                print("Insufficient points for redemption.")
                return "Error: Club does not have enough points to redeem the rewards."

            # Step 4: Deduct points
            cur.execute(
                "UPDATE referral_mapping SET points_balance = points_balance - %s WHERE referral_id = %s",
                (total_points_deducted, referral_id)
            )
            print(f"Rows affected: {cur.rowcount}")

            # Step 5: Log redemption
            for reward_type, quantity in rewards_input.items():
                if quantity > 0:
                    cur.execute(
                        "INSERT INTO redemptions (referral_id, reward_type, quantity, points_deducted) VALUES (%s, %s, %s, %s)",
                        (referral_id, reward_type, quantity, reward['points_required'] * quantity)
                    )

            # Commit the transaction
            conn.commit()
            print("Transaction committed successfully.")

        conn.close()
        return "Success: Rewards redeemed successfully."
    except psycopg2.Error as sqle:
        print("Error during redemption:", sqle.pgerror or "Unknown error")
        conn.rollback()
        return "Error: Redemption failed."

# Update registrations
def update_registrations(data):
    """
    Updates the balance points for each club based on referral registrations and completions.
    Args:
        data (pd.DataFrame): DataFrame containing the CSV data with registration and completion info.
    Returns:
        bool: True if the update succeeds, False otherwise.
    """
    try:
        # Open a database connection
        conn = openConnection()
        if not conn:
            raise Exception("Failed to connect to the database.")

        cursor = conn.cursor()

        # Process the data
        registrations = data["Referral_ID_Registration"].dropna().tolist()
        completions = data["Referral_ID_Completion"].dropna().tolist()

        # Debugging: Print the data
        print("Registrations:", registrations)
        print("Completions:", completions)

        # Get a count of total registrations per club
        registration_counts = {}
        for referral_id in registrations:
            if referral_id not in registration_counts:
                registration_counts[referral_id] = 0
            registration_counts[referral_id] += 1

        # Get a count of total completions per club
        completion_counts = {}
        for referral_id in completions:
            if referral_id not in completion_counts:
                completion_counts[referral_id] = 0
            completion_counts[referral_id] += 1

        # Allocate 25 points for completions
        for referral_id, count in completion_counts.items():
            cursor.execute("""
                UPDATE referral_mapping
                SET points_balance = points_balance + %s
                WHERE referral_id = %s
            """, (count * 25, referral_id))

        # Allocate 5 points for registrations if completions meet the 20% threshold
        for referral_id, reg_count in registration_counts.items():
            completion_count = completion_counts.get(referral_id, 0)
            completion_percentage = (completion_count / reg_count) * 100

            if completion_percentage >= 20:
                cursor.execute("""
                    UPDATE referral_mapping
                    SET points_balance = points_balance + %s
                    WHERE referral_id = %s
                """, (reg_count * 5, referral_id))
            else:
                print(f"Registration points not awarded for {referral_id} due to insufficient completions.")

        # Commit the transaction
        conn.commit()
        print("Registration updates applied successfully.")

        # Close resources
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"Error updating registrations: {e}")
        return False





# Get all rewards
def get_all_rewards():
    conn = openConnection()
    if not conn:
        return []

    try:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute("SELECT * FROM rewards")
            rewards = cur.fetchall()
        conn.close()
        return rewards
    except psycopg2.Error as sqle:
        print("Error retrieving rewards: " + str(sqle.pgerror or "Unknown error"))
        return []
