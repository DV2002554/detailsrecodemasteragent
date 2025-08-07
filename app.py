import os
import json
import uuid
from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory
from werkzeug.utils import secure_filename
from datetime import datetime

# --- NEW: Configuration for Production ---
# On Render, this will be '/var/data'. On your computer, it will be a 'local_data' folder.
DATA_DIR = os.environ.get('RENDER_DATA_DIR', 'local_data')
UPLOAD_FOLDER = os.path.join(DATA_DIR, 'uploads')
DATA_FILE = os.path.join(DATA_DIR, 'agents.json')

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.secret_key = 'super_secret_key_change_this'

# Create the data directories if they don't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# --- Helper Functions (No changes here) ---
def get_file_type(filename):
    if not filename or '.' not in filename: return None
    ext = filename.rsplit('.', 1)[1].lower()
    if ext in {'png', 'jpg', 'jpeg', 'gif'}: return 'image'
    if ext in {'mp4', 'mov', 'avi', 'webm'}: return 'video'
    return None

def load_agents():
    if not os.path.exists(DATA_FILE): return []
    try:
        with open(DATA_FILE, 'r') as f:
            agents = json.load(f)
            valid_agents = [agent for agent in agents if 'date' in agent]
            valid_agents.sort(key=lambda x: datetime.strptime(x['date'], '%Y-%m-%d'), reverse=True)
            return valid_agents
    except (json.JSONDecodeError, KeyError, TypeError): return []

def save_agents(agents):
    with open(DATA_FILE, 'w') as f:
        json.dump(agents, f, indent=4)

# --- Routes ---

# NEW: Route to serve files from our persistent disk
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/')
def index():
    agents = load_agents()
    today_date = datetime.now().strftime('%Y-%m-%d')
    return render_template('index.html', agents=agents, today_date=today_date)

# The rest of the routes are the same...
@app.route('/add', methods=['POST'])
def add_agent():
    files_info = []
    agent_id = str(uuid.uuid4())
    uploaded_files = request.files.getlist('files[]')
    for file in uploaded_files:
        if file.filename != '':
            filename = secure_filename(file.filename)
            unique_filename = f"{agent_id}_{uuid.uuid4()}_{filename}"
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_filename))
            files_info.append({'filename': unique_filename, 'filetype': get_file_type(unique_filename)})
    new_agent = {
        'id': agent_id, 'agent_no': request.form['agent_no'], 'date': request.form['date'],
        'full_name': request.form['full_name'], 'address': request.form['address'],
        'nid_no': request.form['nid_no'], 'pg_type': request.form['pg_type'], 'files': files_info
    }
    agents = load_agents()
    agents.append(new_agent)
    save_agents(agents)
    flash(f"Successfully added agent: {new_agent['full_name']}", 'success')
    return redirect(url_for('index'))

@app.route('/delete/<agent_id>', methods=['POST'])
def delete_agent(agent_id):
    agents = load_agents()
    agent_to_delete = next((agent for agent in agents if agent['id'] == agent_id), None)
    if agent_to_delete:
        for file_info in agent_to_delete.get('files', []):
            if file_info.get('filename'):
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], file_info['filename'])
                if os.path.exists(file_path): os.remove(file_path)
        agents.remove(agent_to_delete)
        save_agents(agents)
        flash(f"Successfully deleted agent: {agent_to_delete['full_name']}", 'success')
    else: flash("Agent not found.", 'error')
    return redirect(url_for('index'))

@app.route('/add_files/<agent_id>', methods=['POST'])
def add_files(agent_id):
    agents = load_agents()
    agent_to_update = next((agent for agent in agents if agent['id'] == agent_id), None)
    if not agent_to_update:
        flash("Agent not found.", "error")
        return redirect(url_for('index'))
    uploaded_files = request.files.getlist('files_to_add[]')
    files_added_count = 0
    for file in uploaded_files:
        if file.filename != '':
            filename = secure_filename(file.filename)
            unique_filename = f"{agent_id}_{uuid.uuid4()}_{filename}"
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_filename))
            agent_to_update.setdefault('files', []).append({'filename': unique_filename, 'filetype': get_file_type(unique_filename)})
            files_added_count += 1
    if files_added_count > 0:
        save_agents(agents)
        flash(f"Added {files_added_count} new file(s) to {agent_to_update['full_name']}.", 'success')
    return redirect(url_for('index'))

@app.route('/delete_file/<agent_id>/<filename>', methods=['POST'])
def delete_file(agent_id, filename):
    agents = load_agents()
    agent_to_update = next((agent for agent in agents if agent['id'] == agent_id), None)
    if agent_to_update:
        files = agent_to_update.get('files', [])
        file_to_delete = next((f for f in files if f['filename'] == filename), None)
        if file_to_delete:
            files.remove(file_to_delete)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            if os.path.exists(file_path): os.remove(file_path)
            save_agents(agents)
            flash(f"File deleted successfully.", 'success')
        else: flash("File not found.", 'error')
    else: flash("Agent not found.", 'error')
    return redirect(url_for('index'))

# The __main__ block is not needed for production with Gunicorn
# But it's good to keep for running locally
if __name__ == '__main__':
    app.run(debug=True)