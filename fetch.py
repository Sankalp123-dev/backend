from flask import Flask, request, jsonify, Blueprint
from flask_cors import CORS
import sqlite3
import json

# app = Flask(__name__)
# CORS(app)  # Enable CORS for all routes

fetch = Blueprint('fetch', __name__)
CORS(fetch)

DATABASE_PATH = "certificates.db"  # Update if needed


# Function to connect to SQLite
def get_db_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row  # Fetch rows as dictionaries
    return conn


# 1️⃣ Fetch applications based on certificate type
@fetch.route('/fetch_application_data', methods=['GET'])
def fetch_application_data():
    try:
        certificate_type = request.args.get('certificate_type')

        if not certificate_type:
            return jsonify({"error": "Certificate type is required"}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        query = """
        SELECT application_id, user_id, certificate_type, status, application_data
        FROM Applications
        WHERE certificate_type = ?
        """
        cursor.execute(query, (certificate_type,))
        rows = cursor.fetchall()
        conn.close()

        # Convert JSON field correctly
        applications = []
        for row in rows:
            application = dict(row)
            try:
                application["application_data"] = json.loads(application["application_data"])
            except (TypeError, json.JSONDecodeError):
                application["application_data"] = {}  # Handle empty or invalid JSON

            applications.append(application)
            print(applications)

        return jsonify({"data": applications}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# 2️⃣ Update application status (Approve/Reject)
@fetch.route('/update_certificate_status', methods=['POST'])
def update_certificate_status():
    try:
        data = request.get_json()
        certificate_id = data.get('certificateId')  # Matches Flutter key
        action = data.get('action')

        if not certificate_id or not action:
            return jsonify({"error": "Certificate ID and action are required"}), 400

        if action not in ['approve', 'reject']:
            return jsonify({"error": "Invalid action. Use 'approve' or 'reject'."}), 400

        status = 'Approved' if action == 'approve' else 'Rejected'

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE Applications SET status = ? WHERE application_id = ?",
            (status, certificate_id),
        )
        conn.commit()
        conn.close()

        return jsonify({"message": f"Certificate {action.capitalize()} successfully."}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# 1️⃣ Fetch applications based on certificate status
@fetch.route('/fetch_application_status', methods=['GET'])
def fetch_application_status():
    try:
        certificate_type = request.args.get('certificate_type')

        if not certificate_type:
            return jsonify({"error": "Certificate type is required"}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        query = """
        SELECT application_id, user_id, certificate_type, status, application_data
        FROM Applications
        WHERE certificate_type = ? AND status = 'Approved'
        """
        cursor.execute(query, (certificate_type,))
        rows = cursor.fetchall()
        conn.close()

        # Convert JSON field correctly
        applications = []
        for row in rows:
            application = dict(row)
            try:
                application["application_data"] = json.loads(application["application_data"])
            except (TypeError, json.JSONDecodeError):
                application["application_data"] = {}  # Handle empty or invalid JSON

            applications.append(application)

        return jsonify({"data": applications}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500



@fetch.route('/get_certificate_history', methods=['GET'])
def get_certificate_history():
    try:
        user_id = request.args.get('user_id')

        if not user_id:
            return jsonify({"error": "user id is required"}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        query = """
        SELECT application_id, certificate_type, status, application_data,remarks
        FROM Applications
        WHERE user_id = ? 
        """
        cursor.execute(query, (user_id,))
        rows = cursor.fetchall()
        conn.close()

        # Convert JSON field correctly
        applications = []
        for row in rows:
            application = dict(row)
            try:
                application["application_data"] = json.loads(application["application_data"])
            except (TypeError, json.JSONDecodeError):
                application["application_data"] = {}  # Handle empty or invalid JSON

            applications.append(application)
            print(applications)

        return jsonify({"data": applications}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@fetch.route('/get_complaint_history', methods=['GET'])
def get_complaint_history():
    try:
        user_id = request.args.get('user_id', '').strip()

        if not user_id:
            return jsonify({"error": "user_id is required"}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        query = """
        SELECT id, name, phone, short_description, full_complaint
        FROM complaints
        WHERE userid = ?
        """
        cursor.execute(query, (user_id,))
        rows = cursor.fetchall()
        conn.close()

        # Debugging: Print fetched rows
        print("Fetched Rows:", rows)

        # Convert rows to a list of dictionaries
        columns = [desc[0] for desc in cursor.description]
        complaints = [dict(zip(columns, row)) for row in rows]

        return jsonify({"data": complaints}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@fetch.route('/get_complaint', methods=['GET'])
def get_complaint():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        query = """
        SELECT id, name, phone, short_description, full_complaint
        FROM complaints
        """
        cursor.execute(query)  # ✅ No user_id filter
        rows = cursor.fetchall()
        conn.close()

        # Debugging: Print fetched rows
        print("Fetched Rows:", rows)

        # Convert rows to a list of dictionaries
        columns = [desc[0] for desc in cursor.description]
        complaints = [dict(zip(columns, row)) for row in rows]

        return jsonify({"data": complaints}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@fetch.route('/update_remarks', methods=['POST'])
def update_remarks():
    try:
        data = request.get_json()
        certificate_id = data.get('certificateId', '').strip()  # Match Flutter key
        remarks = data.get('remarks', '').strip()

        if not certificate_id:
            return jsonify({"error": "Certificate ID is required"}), 400
        if not remarks:
            return jsonify({"error": "Remarks are required"}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        query = """
        UPDATE Applications
        SET remarks = ?
        WHERE application_id = ?
        """
        cursor.execute(query, (remarks, certificate_id))
        conn.commit()
        conn.close()

        print(f"Remarks '{remarks}' updated for certificate ID: {certificate_id}")
        print("Remarks updated successfully")
        
        return jsonify({"message": "Remarks updated successfully"}), 200
    
    except Exception as e:
        print(f"Error updating remarks: {str(e)}")
        return jsonify({"error": str(e)}), 500


