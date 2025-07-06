from flask import Flask, request, jsonify, render_template
from pymongo import MongoClient
from datetime import datetime
import os
import uuid

app = Flask(__name__)

# MongoDB connection (default to local, but override via MONGO_URI env variable)
MONGO_URI = os.environ.get('MONGO_URI', 'mongodb://localhost:27017/')
client = MongoClient(MONGO_URI)
db = client['github_webhook']
collection = db['events']

def parse_github_event(data, event_type):
    """
    Parses GitHub webhook payload and returns a structured event dictionary.
    """
    event = {
        "request_id": str(uuid.uuid4()),
        "author": None,
        "action": None,
        "from_branch": None,
        "to_branch": None,
        "timestamp": None
    }

    if event_type == "push":
        event["author"] = data.get('pusher', {}).get('name')
        event["action"] = "push"
        ref = data.get("ref", "")
        event["to_branch"] = ref.split('/')[-1] if ref else None
        event["timestamp"] = data.get('head_commit', {}).get('timestamp', datetime.utcnow().isoformat())

    elif event_type == "pull_request":
        action = data.get("action")
        pr = data.get("pull_request", {})
        merged = pr.get("merged", False)

        event["author"] = pr.get("user", {}).get("login")
        event["from_branch"] = pr.get("head", {}).get("ref")
        event["to_branch"] = pr.get("base", {}).get("ref")
        event["timestamp"] = pr.get("updated_at", datetime.utcnow().isoformat())

        if merged and action == "closed":
            event["action"] = "merge"
        else:
            event["action"] = "pull_request"
    else:
        return None

    return event

@app.route('/webhook', methods=['POST'])
def webhook():
    """
    Endpoint to receive GitHub webhook events.
    """
    event_type = request.headers.get('X-GitHub-Event')
    data = request.json

    parsed_event = parse_github_event(data, event_type)
    if parsed_event:
        collection.insert_one(parsed_event)
        return jsonify({"status": "success"}), 200
    else:
        return jsonify({"status": "ignored"}), 200

@app.route('/events')
def get_events():
    """
    Fetch and return the latest 20 events from MongoDB.
    """
    events = list(collection.find().sort("timestamp", -1).limit(20))
    for e in events:
        e['_id'] = str(e['_id'])  # Convert ObjectId to string
    return jsonify(events)

@app.route('/')
def index():
    """
    Render the main UI.
    """
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)
