import os
import sqlite3
import json
from venv import logger
from flask_cors import CORS
from flask import Flask, request, jsonify, Blueprint
from langchain_groq import ChatGroq

complaint_bot = Blueprint('complaint_bot', __name__)
CORS(complaint_bot, supports_credentials=True, resources={r"/*": {"origins": "*"}})

# Initialize Flask app
# app = Flask(__name__)
# CORS(app, supports_credentials=True, resources={r"/*": {"origins": "*"}})

# Initialize LLM
GROQ_API_KEY = "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"
llm = ChatGroq(model="llama-3.3-70b-versatile", api_key=GROQ_API_KEY)

# Database initialization
DB_NAME = "certificates.db"

def init_db():
    """Creates SQLite database and table if not exists."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS complaints (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        userid TEXT NOT NULL,
        name TEXT NOT NULL,
        phone TEXT NOT NULL,
        short_description TEXT NOT NULL,
        full_complaint TEXT NOT NULL
    )
    """)
    conn.commit()
    conn.close()

init_db()

def generate_follow_up_question(short_desc, details=None):
    """Dynamically generates follow-up questions using LLM."""
    try:
        context = f"User's issue: {short_desc}\nCurrent details: {json.dumps(details) if details else 'None'}"
        prompt = f"Based on this issue: {context}\n\nGenerate a specific follow-up question to gather more details. The question should help understand the problem better."
        
        response = llm.invoke(prompt).content.strip()
        
        if len(response) > 150 or "?" not in response:
            # Fallback questions
            if not details:
                return "When did you first notice this issue?"
            elif len(details) == 1:
                return "Have you tried any solutions to resolve this? If yes, what were they?"
            else:
                return "Is there any additional information you'd like to share?"
                
        return response
    except Exception as e:
        logger.error(f"Error generating follow-up question: {str(e)}")
        return "Could you provide more details about this issue?"

def generate_complaint_text(name, phone, short_desc, details):
    """Generates a formal complaint text."""
    try:
        context = f"""User's Name: {name}
User's Phone: {phone}
Short Description of the Issue: {short_desc}
Details Provided by the User: {json.dumps(details, indent=2)}"""

        prompt = f"""Based on the following information, generate a formal complaint letter paragraph:
{context}
Make it professional, clear, and concise."""

        generated_paragraph = llm.invoke(prompt).content.strip()

        return f"""Name: {name}
Phone: {phone}

Title: Complaint Regarding {short_desc}

Respected Sir/Madam,

{generated_paragraph}

Thank you."""
    except Exception as e:
        logger.error(f"Error generating complaint text: {str(e)}")
        return f"""Name: {name}
Phone: {phone}

Title: Complaint Regarding {short_desc}

Respected Sir/Madam,

I am writing to report an issue regarding {short_desc}. {' '.join(details.values())}

Thank you."""

@complaint_bot.route("/chat", methods=["POST"])
def chat():
    try:
        data = request.json
        user_message = data.get("message", "").strip()
        userid = data.get("user_id", "").strip()  # Changed from userid to user_id
        session_data = data.get("session_data", {})
        current_stage = session_data.get("stage", "")  # Get stage from session_data
        
        if not user_message:
            return jsonify({
                "response": "Please provide a message.",
                "stage": current_stage,
                "session_data": session_data
            }), 400

        # Initialize conversation
        if user_message.lower() == "hi":
            session_data = {
                "stage": "short_description",
                "userid": userid
            }
            return jsonify({
                "response": "Enter a short description about the issue.",
                "stage": "short_description",
                "session_data": session_data
            })

        # Handle different stages
        if current_stage == "short_description":
            follow_up = generate_follow_up_question(user_message)
            session_data = {
                "stage": "gathering_details",
                "short_description": user_message,
                "details": {},
                "details_count": 0
            }
            return jsonify({
                "response": follow_up,
                "stage": "gathering_details",
                "session_data": session_data
            })

        elif current_stage == "gathering_details":
            details = session_data.get("details", {})
            details_count = int(session_data.get("details_count", 0))
            details[f"detail_{len(details) + 1}"] = user_message
            
            if details_count >= 2:
                session_data = {
                    "stage": "ask_name",
                    "details": details,
                    "short_description": session_data.get("short_description")
                }
                return jsonify({
                    "response": "Please enter your full name.",
                    "stage": "ask_name",
                    "session_data": session_data
                })

            follow_up = generate_follow_up_question(
                session_data.get("short_description", ""),
                details
            )
            session_data = {
                "stage": "gathering_details",
                "details": details,
                "details_count": details_count + 1,
                "short_description": session_data.get("short_description")
            }
            return jsonify({
                "response": follow_up,
                "stage": "gathering_details",
                "session_data": session_data
            })

        elif current_stage == "ask_name":
            session_data = {
                "stage": "ask_phone",
                "name": user_message,
                "details": session_data.get("details", {}),
                "short_description": session_data.get("short_description")
            }
            return jsonify({
                "response": "Please enter your phone number.",
                "stage": "ask_phone",
                "session_data": session_data
            })

        elif current_stage == "ask_phone":
            complaint_text = generate_complaint_text(
                session_data.get("name", ""),
                user_message,
                session_data.get("short_description", ""),
                session_data.get("details", {})
            )
            session_data = {
                "stage": "confirm_complaint",
                "phone": user_message,
                "name": session_data.get("name"),
                "details": session_data.get("details", {}),
                "short_description": session_data.get("short_description"),
                "complaint_text": complaint_text
            }
            return jsonify({
                "response": complaint_text + "\n\nType 'yes' to submit or 'edit' to modify.",
                "stage": "confirm_complaint",
                "session_data": session_data
            })

        elif current_stage == "confirm_complaint":
            if user_message.lower() == "yes":
                try:
                    conn = sqlite3.connect(DB_NAME)
                    cursor = conn.cursor()
                    cursor.execute("""
                        INSERT INTO complaints (userid, name, phone, short_description, full_complaint) 
                        VALUES (?, ?, ?, ?, ?)
                    """, (
                        userid,
                        session_data.get("name", ""),
                        session_data.get("phone", ""),
                        session_data.get("short_description", ""),
                        session_data.get("complaint_text", "")
                    ))
                    conn.commit()
                    complaint_id = cursor.lastrowid
                    conn.close()
                    
                    session_data = {
                        "stage": "completed"
                    }
                    return jsonify({
                        "response": f"Your complaint has been submitted successfully with ID {complaint_id}.",
                        "stage": "completed",
                        "session_data": session_data
                    })
                except sqlite3.Error as e:
                    logger.error(f"Database error: {str(e)}")
                    return jsonify({
                        "response": "Failed to save complaint. Please try again.",
                        "stage": current_stage,
                        "session_data": session_data
                    }), 500

            elif user_message.lower() == "edit":
                session_data = {
                    "stage": "short_description"
                }
                return jsonify({
                    "response": "Enter a short description about the issue again.",
                    "stage": "short_description",
                    "session_data": session_data
                })

        return jsonify({
            "response": "I didn't understand that. Please start with 'hi' to begin the process.",
            "stage": "",
            "session_data": {}
        })

    except Exception as e:
        logger.error(f"Error in chat endpoint: {str(e)}")
        return jsonify({
            "response": "An error occurred. Please try again.",
            "stage": current_stage,
            "session_data": session_data
        }), 500
