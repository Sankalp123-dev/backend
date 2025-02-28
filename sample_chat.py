from flask import Flask, request, jsonify, Blueprint
from langchain_groq import ChatGroq
from pydantic import BaseModel, Field
from typing import Optional, Literal
from dotenv import load_dotenv
from flask_cors import CORS
import sqlite3
import json
import os

sample_chat = Blueprint('sample_chat', __name__)
CORS(sample_chat)

# app = Flask(__name__)
# CORS(app)
load_dotenv()

# Get Groq API key
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
llm = ChatGroq(model="llama-3.3-70b-versatile")

# Database setup
def create_database():
    conn = sqlite3.connect('certificates.db')
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS Applications (
        application_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id VARCHAR(50) REFERENCES users(user_id) ON DELETE CASCADE,
        certificate_type TEXT NOT NULL,
        status VARCHAR(20) DEFAULT 'Pending',
        application_data JSON,
        pdf_file BLOB
    )
    ''')
    conn.commit()
    conn.close()

create_database()

# Certificate type model
class CertificateType(BaseModel):
    certificate_type: Optional[Literal["Birth Certificate", "Death Certificate", "Land Certificate", "Income Certificate"]] = Field(
        None, description="The type of certificate selected by the user. Do not guess or create placeholder data."
    )

# Individual certificate models
class BirthCertificate(BaseModel):
    full_name: Optional[str] = Field(None, description="Full name of the person. Do not guess or create placeholder data.")
    date_of_birth: Optional[str] = Field(None, pattern=r'^\d{4}-\d{2}-\d{2}$', description="Date of birth (YYYY-MM-DD)")
    place_of_birth: Optional[str] = Field(None, description="Place of birth. Do not guess or create placeholder data.")
    fathers_name: Optional[str] = Field(None, description="Father's name. Do not guess or create placeholder data.")
    mothers_name: Optional[str] = Field(None, description="Mother's name. Do not guess or create placeholder data.")

class DeathCertificate(BaseModel):
    name: Optional[str] = Field(None, description="Name of the deceased. Do not guess or create placeholder data.")
    date_of_death: Optional[str] = Field(None, pattern=r'^\d{4}-\d{2}-\d{2}$', description="Date of death (YYYY-MM-DD)")
    place_of_death: Optional[str] = Field(None, description="Place of death. Do not guess or create placeholder data.")
    cause_of_death: Optional[str] = Field(None, description="Cause of death. Do not guess or create placeholder data.")

class LandCertificate(BaseModel):
    property_address: Optional[str] = Field(None, description="Address of the property. Do not guess or create placeholder data.")
    owner_name: Optional[str] = Field(None, description="Name of the property owner. Do not guess or create placeholder data.")
    survey_number: Optional[str] = Field(None, description="Survey number of the property. Do not guess or create placeholder data.")
    area_sqft: Optional[float] = Field(None, gt=0, description="Area in square feet")
    market_value: Optional[float] = Field(None, gt=0, description="Market value of the property")

class IncomeCertificate(BaseModel):
    name: Optional[str] = Field(None, description="Name of the person. Do not guess or create placeholder data.")
    annual_income: Optional[float] = Field(None, gt=0, description="Annual income amount")
    source_of_income: Optional[str] = Field(None, description="Source of income. Do not guess or create placeholder data.")
    address: Optional[str] = Field(None, description="Residential address. Do not guess or create placeholder data.")

def check_what_is_empty(certificate_details):
    """Check which fields are empty in the certificate details."""
    ask_for = []
    for field, value in certificate_details.model_dump().items():
        if value in [None, "", 0]:
            ask_for.append(field)
    return ask_for

def add_non_empty_details(current_details, new_details):
    """Update current details with new non-empty values."""
    non_empty_details = {k: v for k, v in new_details.model_dump().items() if v not in [None, ""]}
    updated_details = current_details.model_copy(update=non_empty_details)
    return updated_details

def ask_for_info(ask_for, certificate_type):
    """Generate next question based on missing information."""
    from langchain.prompts import ChatPromptTemplate
    
    prompt = ChatPromptTemplate.from_template(
        "Below are fields of information to ask the user for in a conversational way. "
        "You are helping with a {certificate_type} application. "
        "For the first missing field, you can introduce that you need more information. "
        "For subsequent questions, ask directly without repeating phrases. "
        "Ensure each question is concise and avoids unnecessary repetition. "
        "Do not greet the user, and do not say 'Hi.' "
        "If the ask_for list is empty, thank the user. \n\n"
        "### ask_for list: {ask_for}"
    )

    response = (prompt | llm).invoke({
        "ask_for": ask_for,
        "certificate_type": certificate_type
    })
    
    return response.content if hasattr(response, 'content') else str(response)

def save_to_database(user_id, certificate_type, application_data):
    """Save the application to the database"""
    try:
        conn = sqlite3.connect('certificates.db')
        cursor = conn.cursor()
        # certificate_type.replace('','_')
        # Convert application data to JSON string
        application_data_json = json.dumps(application_data)
        
        cursor.execute('''
        INSERT INTO Applications (user_id, certificate_type, application_data, status)
        VALUES (?, ?, ?, ?)
        ''', (user_id, certificate_type, application_data_json, 'Pending'))
        
        application_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return application_id
    except Exception as e:
        print(f"Database error: {str(e)}")
        return None

def format_confirmation_message(certificate_type, details):
    """Format the details for user confirmation"""
    message = f"Please confirm the following details for your {certificate_type}:\n\n"
    
    for key, value in details.items():
        if value:  # Only include non-empty values
            formatted_key = key.replace('_', ' ').title()
            message += f"{formatted_key}: {value}\n"
    
    message += "\nPlease reply with 'confirm' to save these details or 'edit' to make changes."
    return message

# Initialize chains for different certificate types
type_chain = llm.with_structured_output(CertificateType)
certificate_chains = {
    "Birth Certificate": llm.with_structured_output(BirthCertificate),
    "Death Certificate": llm.with_structured_output(DeathCertificate),
    "Land Certificate": llm.with_structured_output(LandCertificate),
    "Income Certificate": llm.with_structured_output(IncomeCertificate)
}

# User session storage (in production, use a proper database)
user_sessions = {}

def filter_response(text_input, certificate_type, current_form):
    """Process user response and update details."""
    try:
        if not certificate_type:
            # Only detect certificate type if explicitly mentioned
            certificate_types = ["birth certificate", "death certificate", "land certificate", "income certificate"]
            mentioned_types = [cert_type for cert_type in certificate_types if cert_type in text_input.lower()]
            
            if mentioned_types:
                # Only process the first mentioned certificate type
                cert_type = mentioned_types[0].title()
                return CertificateType(certificate_type=cert_type), None
            else:
                return None, None
        else:
            # Get the current field being asked about
            current_field = None
            if current_form:
                empty_fields = check_what_is_empty(current_form)
                if empty_fields:
                    current_field = empty_fields[0]

            if current_field:
                # Create a dictionary with only the current field
                field_data = {current_field: text_input.strip()}
                
                # Create a new instance of the appropriate certificate class
                model_class = globals()[certificate_type.replace(" ", "")]
                try:
                    new_form = model_class(**field_data)
                    if current_form:
                        # Update only the current field
                        updated_form = current_form.model_copy()
                        setattr(updated_form, current_field, getattr(new_form, current_field))
                        return None, updated_form
                    return None, new_form
                except Exception as e:
                    print(f"Validation error for field {current_field}: {str(e)}")
                    return None, current_form
            
            return None, current_form
            
    except Exception as e:
        print(f"Error processing response: {str(e)}")
        return None, current_form

@sample_chat.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        user_id = data.get('user_id')
        message = data.get('message')

        if not user_id or not message:
            return jsonify({'error': 'Missing user_id or message'}), 400

        # Get or initialize user session
        if user_id not in user_sessions:
            user_sessions[user_id] = {
                "certificate_type": None,
                "current_form": None,
                "awaiting_confirmation": False
            }

        session = user_sessions[user_id]

        # Handle confirmation response
        if session.get("awaiting_confirmation"):
            if message.lower() == 'confirm':
                application_id = save_to_database(
                    user_id,
                    session["certificate_type"],
                    session["current_form"].model_dump()
                )
                if application_id:
                    response = f"Thank you! Your application has been saved. Your application ID is: {application_id}"
                    user_sessions[user_id] = {
                        "certificate_type": None,
                        "current_form": None,
                        "awaiting_confirmation": False
                    }
                    return jsonify({
                        'response': response,
                        'type': 'complete',
                        'certificate_type': session["certificate_type"],
                        'current_details': session["current_form"].model_dump() if session["current_form"] else None
                    })
                else:
                    response = "Sorry, there was an error saving your application. Please try again."
                    return jsonify({'error': response}), 500
            elif message.lower() == 'edit':
                session["awaiting_confirmation"] = False
                
        # Process message
        type_result, form_result = filter_response(
            message,
            session["certificate_type"],
            session["current_form"]
        )

        if not session["certificate_type"]:
            if type_result and type_result.certificate_type:
                # Update certificate type
                session["certificate_type"] = type_result.certificate_type
                model_class = globals()[type_result.certificate_type.replace(" ", "")]
                session["current_form"] = model_class()
                
                # Get missing fields and generate first question
                ask_for = check_what_is_empty(session["current_form"])
                initial_question = ask_for_info(ask_for, type_result.certificate_type)
                
                response = f"I'll help you apply for a {type_result.certificate_type}. {initial_question}"
                response_type = 'question'
            else:
                response = "Welcome! Please specify which certificate you'd like to apply for:\n- Birth Certificate\n- Death Certificate\n- Land Certificate\n- Income Certificate"
                response_type = 'question'
        elif form_result:
            # Update form data
            session["current_form"] = form_result
            ask_for = check_what_is_empty(form_result)
            
            if not ask_for:
                # All fields are filled, show confirmation
                response = format_confirmation_message(
                    session["certificate_type"],
                    session["current_form"].model_dump()
                )
                session["awaiting_confirmation"] = True
                response_type = 'confirmation'
            else:
                response = ask_for_info(ask_for, session["certificate_type"])
                response_type = 'question'
        else:
            response = "I didn't quite understand that. Could you please rephrase?"
            response_type = 'error'

        user_sessions[user_id] = session

        return jsonify({
            'response': response,
            'type': response_type,
            'certificate_type': session["certificate_type"],
            'current_details': session["current_form"].model_dump() if session["current_form"] else None
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@sample_chat.route('/user_details/<user_id>', methods=['GET'])
def get_user_details(user_id):
    """Endpoint to get current user certificate details."""
    if user_id not in user_sessions:
        return jsonify({'error': 'User not found'}), 404
    session = user_sessions[user_id]
    return jsonify({
        'certificate_type': session["certificate_type"],
        'details': session["current_form"].model_dump() if session["current_form"] else None
    })
