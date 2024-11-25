import os
from flask import Flask, request, jsonify, send_from_directory
import google.generativeai as genai
import threading
import time
import requests
import random
import string
from collections import deque
import logging

app = Flask(__name__)

# Configuration for Generative AI API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)

# Separate generation configurations for different models
generation_config_flash = {
    "temperature": 1,
    "top_p": 0.95,
    "top_k": 64,
    "max_output_tokens": 8192,
    "response_mime_type": "text/plain",
}

generation_config_pro = {
    "temperature": 1.15,
    "top_p": 0.95,
    "top_k": 64,
    "max_output_tokens": 8192,
    "response_mime_type": "text/plain",
}

# Models for different requests
model_flash = genai.GenerativeModel(
    model_name="gemini-1.5-pro",
    generation_config=generation_config_flash,
)

model_pro = genai.GenerativeModel(
    model_name="gemini-1.5-pro",
    generation_config=generation_config_pro,
)

chat_sessions = {}  # Dictionary to store chat sessions per user
SESSION_TIMEOUT = 3600  # 1 hour timeout for sessions

def cleanup_sessions():
    """Remove expired sessions."""
    current_time = time.time()
    for user_id in list(chat_sessions.keys()):
        if current_time - chat_sessions[user_id]['last_activity'] > SESSION_TIMEOUT:
            del chat_sessions[user_id]

@app.route('/ask', methods=['GET'])
def ask():
    """Handle GET requests for retrieving responses."""
    query = request.args.get('q')
    user_id = request.args.get('id')

    if not query or not user_id:
        return jsonify({"error": "Please provide both query and id."}), 400

    try:
        if user_id not in chat_sessions:
            chat_sessions[user_id] = {
                "chat": model_flash.start_chat(history=[]),  # Using gemini-1.5-flash for /ask
                "history": deque(maxlen=5),  # Stores the last 5 messages
                "last_activity": time.time()
            }

        chat_session = chat_sessions[user_id]["chat"]
        history = chat_sessions[user_id]["history"]

        # Add the user query to history
        history.append(f"User: {query}")
        response = chat_session.send_message(query)
        # Add the bot response to history
        history.append(f"Bot: {response.text}")

        chat_sessions[user_id]["last_activity"] = time.time()  # Update session activity

        return jsonify({"response": response.text})
    
    except Exception as e:
        logging.error(f"Error during chat processing: {e}")
        return jsonify({"error": "An error occurred while processing your request."}), 500

@app.route('/response', methods=['POST'])
def response():
    """Handle POST requests for receiving responses."""
    data = request.get_json()
    query = data.get('q')
    user_id = data.get('id')

    if not query or not user_id:
        return jsonify({"error": "Please provide both query and id."}), 400

    try:
        if user_id not in chat_sessions:
            chat_sessions[user_id] = {
                "chat": model_pro.start_chat(history=[]),  # Using gemini-1.5-pro for /response
                "history": deque(maxlen=3),  # Stores the last 5 messages
                "last_activity": time.time()
            }

        chat_session = chat_sessions[user_id]["chat"]
        history = chat_sessions[user_id]["history"]

        # Add the user query to history
        history.append(f"User: {query}")
        response = chat_session.send_message(query)
        # Add the bot response to history
        history.append(f"Bot: {response.text}")

        chat_sessions[user_id]["last_activity"] = time.time()  # Update session activity

        return jsonify({"response": response.text})
    
    except Exception as e:
        logging.error(f"Error during chat processing: {e}")
        return jsonify({"error": "An error occurred while processing your request."}), 500

@app.route('/ping', methods=['GET'])
def ping():
    return jsonify({"status": "alive"})

def keep_alive():
    url = "https://my-ai-o83s.onrender.com"  # Replace with your actual URL
    while True:
        time.sleep(600)  # Ping every 10 minutes
        try:
            response = requests.get(url)
            if response.status_code == 200:
                print("Ping successful")
            else:
                print("Ping failed with status code", response.status_code)
        except requests.exceptions.RequestException as e:
            print("Ping failed with exception", e)

# Configuration for Temporary Email API
domains = [
    "1secmail.com",
    "1secmail.org",
    "1secmail.net",
    "vjuum.com",
    "laafd.com",
    "txcct.com",
    "rteet.com",
    "dpptd.com"
]

def generate_unique_username(length=8):
    """Generate a random username."""
    letters = string.ascii_lowercase
    return ''.join(random.choice(letters) for i in range(length))

@app.route('/v1', methods=['GET'])
def handle_request():
    if 'tempmail' in request.args:
        temp_emails = []
        for domain in domains:
            username = generate_unique_username()
            temp_emails.append(f"{username}@{domain}")
        return jsonify(temp_emails)
    
    elif 'inbox' in request.args:
        inbox_email = request.args.get('inbox')
        if '@' not in inbox_email:
            return jsonify({"error": "Invalid email format"}), 400
        
        username, domain = inbox_email.split('@')
        if domain not in domains:
            return jsonify({"error": "Invalid domain"}), 400
        
        # Get messages
        get_messages_url = f"https://www.1secmail.com/api/v1/?action=getMessages&login={username}&domain={domain}"
        response = requests.get(get_messages_url)
        messages = response.json()
        
        if not messages:
            return jsonify({"error": "No messages found"}), 404
        
        # Get the first message id
        message_id = messages[0]['id']
        
        # Get the message details
        read_message_url = f"https://www.1secmail.com/api/v1/?action=readMessage&login={username}&domain={domain}&id={message_id}"
        response = requests.get(read_message_url)
        message_details = response.json()
        
        # Extract the required fields
        result = {
            "date": message_details.get("date"),
            "from": message_details.get("from"),
            "subject": message_details.get("subject"),
            "body": message_details.get("textBody")
        }
        
        return jsonify(result)
    
    else:
        return jsonify({"error": "Invalid request"}), 400

# Serve static files (like CSS) from the root directory
@app.route('/')
def index():
    return send_from_directory('', 'index.html')

@app.route('/styles.css')
def styles():
    return send_from_directory('', 'styles.css')

# Start keep-alive thread
threading.Thread(target=keep_alive, daemon=True).start()

# Cleanup old sessions every 15 minutes
def periodic_cleanup():
    while True:
        time.sleep(900)  # Cleanup every 15 minutes
        cleanup_sessions()

threading.Thread(target=periodic_cleanup, daemon=True).start()

if __name__ == '__main__':
    from os import environ
    app.run(host='0.0.0.0', port=int(environ.get('PORT', 5000)))
