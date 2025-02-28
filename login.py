from flask import Flask, request, jsonify, Blueprint
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
from datetime import datetime

# app = Flask(__name__)
# CORS(app)

login = Blueprint('login', __name__)
CORS(login)

# Database file
DATABASE = 'certificates.db'

def init_db():
    """Initialize the SQLite database"""
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                password TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                mobile TEXT UNIQUE NOT NULL,
                role TEXT DEFAULT 'user',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()

# Initialize database
init_db()

@login.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Missing JSON body"}), 400

    user_id = data.get('user_id')
    password = data.get('password')
    role = data.get('role', 'user')
    mobile = data.get('mobile')
    email = data.get('email')

    # Ensure required fields are present
    if not user_id or not password or not mobile or not email:
        return jsonify({"error": "Missing data"}), 400

    hashed_password = generate_password_hash(password, method='pbkdf2:sha256')

    try:
        with sqlite3.connect(DATABASE) as conn:
            cursor = conn.cursor()

            # Check if the user_id, mobile, or email already exists
            cursor.execute("SELECT 1 FROM users WHERE user_id = ? OR mobile = ? OR email = ?", (user_id, mobile, email))
            if cursor.fetchone():
                return jsonify({"error": "User ID, Mobile number, or Email already exists"}), 400

            # Insert new user into the database
            cursor.execute(
                """
                INSERT INTO users (user_id, password, role, mobile, email) 
                VALUES (?, ?, ?, ?, ?)
                """,
                (user_id, hashed_password, role, mobile, email)
            )
            conn.commit()

        return jsonify({"message": "User registered successfully"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@login.route('/login', methods=['POST'])
def login_user():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Missing JSON body'}), 400

    user_id = data.get('user_id')
    password = data.get('password')

    if not user_id or not password:
        return jsonify({'error': 'Missing data'}), 400

    try:
        with sqlite3.connect(DATABASE) as conn:
            cursor = conn.cursor()

            # Find user in the database
            cursor.execute("SELECT password, role FROM users WHERE user_id = ?", (user_id,))
            result = cursor.fetchone()

            if result and check_password_hash(result[0], password):
                # Include user_id in the response
                return jsonify({
                    'message': 'Login successful',
                    'user_id': user_id,  # Send user_id back to the client
                    'role': result[1]
                }), 200
            else:
                return jsonify({'error': 'Invalid credentials'}), 401
    except Exception as e:
        return jsonify({"error": str(e)}), 500


