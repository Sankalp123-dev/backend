from flask import Flask, request, jsonify, Blueprint
from flask_cors import CORS
import sqlite3
import json

# app = Flask(__name__)
# CORS(app)  # Enable CORS for all routes

certificate = Blueprint('certificate', __name__)
CORS(certificate)

# Function to save data in the Applications table with standardized certificate type names
def save_certificate_in_application(certificate_data, certificate_type, user_id):
    try:
        # Valid certificate types with standardized names
        valid_certificates = ["Birth Certificate", "Death Certificate", "Land Certificate", "Income Certificate"]
        if certificate_type not in valid_certificates:
            raise ValueError(f"Invalid certificate type: {certificate_type}")

        # Establish database connection
        conn = sqlite3.connect('certificates.db')
        cursor = conn.cursor()

        # Create the insert query to save data in the Applications table
        insert_query = """INSERT INTO Applications (user_id, certificate_type, application_data, status) 
                          VALUES (?, ?, ?, ?)"""

        # Convert application data to JSON format
        application_data = json.dumps(certificate_data)

        # Execute the query
        cursor.execute(insert_query, (user_id, certificate_type, application_data, "Pending"))
        conn.commit()
        print(f"Data saved successfully in Applications table for user {user_id}!")

    except sqlite3.Error as e:
        print(f"Database Error: {e}")
        raise  # Reraise exception for logging
    except Exception as e:
        print(f"Error: {e}")
        raise  # Reraise exception
    finally:
        conn.close()


# Route to handle certificate saving in the Applications table
@certificate.route('/save_certificate', methods=['POST'])
def save_certificate_route():
    try:
        # Get data from request
        certificate_type = request.json.get("certificate_type")
        certificate_data = request.json.get("data")
        user_id = request.json.get("user_id")  # Get user ID from request

        # Normalize keys in certificate_data (convert spaces to underscores, lowercase first letter)
        certificate_data = {key.lower().replace(" ", "_"): value for key, value in certificate_data.items()}

        print(f"Normalized certificate data: {certificate_data}")
        print(f"User ID: {user_id}")

        # Define required fields for each certificate type
        required_fields = {
            "Birth Certificate": ["full_name", "date_of_birth", "place_of_birth", "fathers_name", "mothers_name"],
            "Death Certificate": ["name", "date_of_death", "place_of_death", "cause_of_death"],
            "Land Certificate": ["property_address", "owner_name", "survey_number", "area_sqft", "market_value"],
            "Income Certificate": ["name", "annual_income", "source_of_income", "address"]
        }

        # Check if the certificate type is valid
        if certificate_type not in required_fields:
            return jsonify({"error": "Invalid certificate type"}), 400

        # Validate required fields
        missing_fields = [field for field in required_fields[certificate_type] if field not in certificate_data]
        if missing_fields:
            return jsonify({"error": f"Missing fields: {', '.join(missing_fields)}"}), 400

        # Save the certificate data in the Applications table
        save_certificate_in_application(certificate_data, certificate_type, user_id)
        
        return jsonify({"message": f"Data successfully saved to Applications table for {certificate_type} certificate"}), 200

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"error": str(e)}), 500

