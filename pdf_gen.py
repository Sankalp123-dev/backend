from flask import Flask, request, jsonify, send_file
from flask_cors import CORS  # Import CORS
import random
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.platypus import Paragraph, Frame
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.enums import TA_JUSTIFY
from PIL import Image
import sqlite3
import os

app = Flask(__name__)

# Enable CORS for all routes
CORS(app)

# Database connection setup
def get_db_connection():
    conn = sqlite3.connect('certificates.db')  # Update this to your database path
    conn.row_factory = sqlite3.Row
    return conn

# Helper function to fetch data from the database
def get_certificate_data(application_id, certificate_type):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM Applications WHERE application_id = ? AND certificate_type = ?", 
                   (application_id, certificate_type))
    certificate_data = cursor.fetchone()
    conn.close()
    return certificate_data

# Function to store PDF in the database
def store_pdf_in_db(application_id, certificate_type, pdf_file):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(""" 
        UPDATE Applications
        SET pdf_file = ?
        WHERE application_id = ? AND certificate_type = ?
    """, (pdf_file, application_id, certificate_type))
    conn.commit()
    conn.close()

@app.route('/generate_pdf', methods=['POST'])
def generate_pdf():
    # Get data from the JSON payload
    data = request.get_json()
    
    if not data:
        return jsonify({"error": "Invalid or missing JSON data"}), 400

    # Ensure the data is a dictionary and contains the required keys
    if not isinstance(data, dict):
        return jsonify({"error": "Expected data to be a JSON object"}), 400
    
    certificate_type = data.get('certificate_type')

    if certificate_type == "Birth Certificate":
        full_name = data.get('full_name')
        fathers_name = data.get('fathers_name')
        mothers_name = data.get('mothers_name')
        date_of_birth = data.get('date_of_birth')
        place_of_birth = data.get('place_of_birth')
    
    elif certificate_type == "Death Certificate":
        name = data.get('name')
        date_of_death = data.get('date_of_death')
        place_of_death = data.get('place_of_death')
        cause_of_death = data.get('cause_of_death')

    elif certificate_type == "Income Certificate":
        name = data.get('name')
        annual_income = data.get('annual_income')
        source_of_income = data.get('source_of_income')
        address = data.get('address')

    elif certificate_type == "Land Certificate":
        owner_name = data.get('owner_name')
        property_address = data.get('property_address')
        market_value = data.get('market_value')
        area_in_sq_ft = data.get('area_sqft')
        survey_number = data.get('survey_number')

    # Check for the presence of application_id
    application_id = data.get('application_id')
    if not application_id:
        return jsonify({"error": "Missing application_id in data"}), 400

    # Generate a random key number
    key_number = random.randint(100000, 999999)

    # Create a PDF in memory
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    # Add the light logo in the background (central logo)
    logo_path = "govt.jpeg"  # Replace with the actual path to your logo
    image = Image.open(logo_path)
    image = image.convert("RGBA")  # Ensure the image has an alpha channel

    # Modify the alpha values (transparency)
    data = image.getdata()
    new_data = [(item[0], item[1], item[2], 100) for item in data]
    image.putdata(new_data)

    image.save("light_govt.png")

    # Add the modified logo to the center of the page
    logo_width = 300
    logo_height = 180
    pdf.drawImage("light_govt.png", (width - logo_width) / 2, (height - logo_height) / 2,
                  width=logo_width, height=logo_height, mask='auto')

    # Add the randomly generated key number above the top-left logo
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(50, height - 50, f"KEYNO: {key_number}")

    # Add the top-left corner logo
    top_left_logo_path = "govt.jpeg"
    top_left_logo = Image.open(top_left_logo_path)
    top_left_logo = top_left_logo.convert("RGBA")

    # Modify transparency of the small logo
    data = top_left_logo.getdata()
    new_data = [(item[0], item[1], item[2], 100) for item in data]
    top_left_logo.putdata(new_data)
    top_left_logo.save("small_light_govt.png")

    # Add the small logo to the top-left corner
    logo_width_small = 50
    logo_height_small = 50
    pdf.drawImage("small_light_govt.png", 50, height - logo_height_small - 50,
                  width=logo_width_small, height=logo_height_small, mask='auto')

    # Add header content to the PDF
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawCentredString(width / 2, height - 50, "GOVERNMENT OF KERALA")

    # Add specific certificate content
    if certificate_type == "Birth Certificate":
        pdf.setFont("Helvetica-Bold", 16)
        pdf.drawCentredString(width / 2, height - 120, "BIRTH CERTIFICATE")

        # Add the justified paragraph (common for birth certificate)
        paragraph = (
            "(Issued under Section 12 of the Registration of Births and Deaths Acts, 1969 and Rule 8 of the Kerala "
            "Registration of Births and Deaths Rules, 1999) This is to certify that the following information has been "
            "taken from the original record of birth which is the register for (local area/local body) "
            "Thiruvananthapuram Corporation of Taluk Thiruvananthapuram of District Thiruvananthapuram of State Kerala."
            "These Certificates have no way relevence in real world and is for demonstration purposes only."
        )

        # Style for the paragraph
        styles = getSampleStyleSheet()
        style = styles["Normal"]
        style.fontName = "Helvetica"
        style.fontSize = 10
        style.leading = 12
        style.alignment = TA_JUSTIFY

        # Create and draw the paragraph
        p = Paragraph(paragraph, style)
        frame = Frame(50, height - 220, width - 100, 60, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0)
        frame.addFromList([p], pdf)

        pdf.setFont("Helvetica", 10)
        pdf.drawString(50, height - 300, f"Name: {full_name}")
        pdf.drawString(50, height - 320, f"Father's Name: {fathers_name}")
        pdf.drawString(50, height - 340, f"Mother's Name: {mothers_name}")
        pdf.drawString(50, height - 360, f"Date of Birth: {date_of_birth}")
        pdf.drawString(50, height - 380, f"Place of Birth: {place_of_birth}")

        pdf.drawString(50, 50, "NB: This certificate is for demonstration purposes.")

    pdf.showPage()
    pdf.save()

    # Save PDF to the specified directory
    save_path = r"C:\Users\Athul M Nair\Desktop\gen"  # Desired directory
    os.makedirs(save_path, exist_ok=True)  # Create the directory if it doesn't exist
    file_name = f"{certificate_type}_certificate_{application_id}.pdf"
    pdf_file_path = os.path.join(save_path, file_name)

    # Save the file to the specified location
    with open(pdf_file_path, 'wb') as f:
        f.write(buffer.getvalue())

    # Optionally, store the file path in the database (if needed)
    store_pdf_in_db(application_id, certificate_type, pdf_file_path)

    return jsonify({"message": "PDF generated and saved successfully", "file_path": pdf_file_path}), 200

@app.route('/get_pdf', methods=['POST'])
def get_pdf():
    # Get application_id and certificate_type from the request body
    data = request.get_json()
    application_id = data.get('application_id')
    certificate_type = data.get('certificate_type')

    if not application_id or not certificate_type:
        return jsonify({"error": "application_id and certificate_type are required"}), 400

    # Define the directory where the PDFs are stored
    save_path = r"C:\Users\Athul M Nair\Desktop\gen"  # Directory where PDFs are saved

    # Construct the file path for the requested PDF
    file_name = f"{certificate_type}_certificate_{application_id}.pdf"
    pdf_file_path = os.path.join(save_path, file_name)

    # Check if the file exists
    if not os.path.exists(pdf_file_path):
        return jsonify({"error": "No PDF found for the given application_id and certificate_type"}), 404

    # Return the PDF file as a response with headers for download
    return send_file(
        pdf_file_path,
        as_attachment=True,  # Set to True to trigger download
        download_name=file_name,  # Name of the file when downloaded
        mimetype='application/pdf'
    )

if __name__ == '__main__':
    app.run(debug=True, port=5500)
