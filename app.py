from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_login import login_required, current_user
import json
import os
import sys
from datetime import datetime

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models import *
from auth import auth_bp, login_manager
from services.ftp_user_service import FTPUserService
from services.ftp_log_service import FTPLogService
from services.ftp_connection_service import FTPConnectionService
from services.ftp_config_service import FTPConfigService

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-change-in-production')

# Initialize database
create_tables()

# Initialize login manager
login_manager.init_app(app)
login_manager.login_view = 'auth.login'

# Register blueprints
app.register_blueprint(auth_bp)

@app.route('/')
@login_required
def index():
    return redirect(url_for('dashboard'))

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')

# API Routes
@app.route('/api/users', methods=['GET'])
@login_required
def get_ftp_users():
    users = FTPUser.select().dicts()
    return jsonify(list(users))

@app.route('/api/users', methods=['POST'])
@login_required
def create_ftp_user():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    home_dir = data.get('home_directory', f'/home/{username}')
    
    # Create system user
    success, message = FTPUserService.create_system_user(username, password, home_dir)
    
    if success:
        # Create database record
        ftp_user = FTPUser.create(
            username=username,
            home_directory=home_dir,
            created_by=current_user
        )
        return jsonify({'success': True, 'message': message})
    else:
        return jsonify({'success': False, 'message': message}), 400

@app.route('/api/users/<username>', methods=['DELETE'])
@login_required
def delete_ftp_user(username):
    success, message = FTPUserService.delete_system_user(username)
    
    if success:
        # Delete from database
        FTPUser.delete().where(FTPUser.username == username).execute()
        return jsonify({'success': True, 'message': message})
    else:
        return jsonify({'success': False, 'message': message}), 400

@app.route('/api/users/<username>/block', methods=['POST'])
@login_required
def block_user(username):
    success, message = FTPUserService.block_user(username)
    return jsonify({'success': success, 'message': message})

@app.route('/api/users/<username>/unblock', methods=['POST'])
@login_required
def unblock_user(username):
    success, message = FTPUserService.unblock_user(username)
    return jsonify({'success': success, 'message': message})

@app.route('/api/logs', methods=['GET'])
@login_required
def get_logs():
    # Sync logs first
    FTPLogService.sync_logs_to_db()
    
    # Get logs from database
    logs = FTPLog.select().order_by(FTPLog.timestamp.desc()).limit(100).dicts()
    return jsonify(list(logs))

@app.route('/api/connections', methods=['GET'])
@login_required
def get_connections():
    # Update connections
    FTPConnectionService.update_connections()
    
    # Get active connections
    connections = FTPConnection.select().where(FTPConnection.is_active == True).dicts()
    return jsonify(list(connections))

@app.route('/api/connections/<int:pid>/kill', methods=['POST'])
@login_required
def kill_connection(pid):
    success, message = FTPConnectionService.kill_connection(pid)
    return jsonify({'success': success, 'message': message})

@app.route('/api/config', methods=['GET'])
@login_required
def get_config():
    config = FTPConfigService.read_config()
    # Add metadata
    config_with_meta = {}
    for key, value in config.items():
        if key in FTPConfigService.CONFIG_OPTIONS:
            config_with_meta[key] = {
                'value': value,
                'type': FTPConfigService.CONFIG_OPTIONS[key]['type'],
                'description': FTPConfigService.CONFIG_OPTIONS[key]['description']
            }
    return jsonify(config_with_meta)

@app.route('/api/config', methods=['POST'])
@login_required
def update_config():
    data = request.json
    key = data.get('key')
    value = data.get('value')
    
    success, message = FTPConfigService.update_config(key, value, current_user)
    return jsonify({'success': success, 'message': message})

@app.route('/api/stats', methods=['GET'])
@login_required
def get_stats():
    # Get statistics for dashboard
    total_users = FTPUser.select().count()
    active_connections = FTPConnection.select().where(FTPConnection.is_active == True).count()
    blocked_users = FTPUser.select().where(FTPUser.is_blocked == True).count()
    
    return jsonify({
        'total_users': total_users,
        'active_connections': active_connections,
        'blocked_users': blocked_users
    })

# Health check endpoint
@app.route('/health')
def health_check():
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})

# Create default admin user if not exists
def create_default_admin():
    try:
        if not User.select().where(User.username == 'admin').exists():
            admin = User(username='admin', email='admin@example.com', is_admin=True)
            admin.set_password('admin123')
            admin.save()
            print("Default admin user created successfully")
            print("Username: admin")
            print("Password: admin123")
        else:
            print("Admin user already exists")
    except Exception as e:
        print(f"Error creating default admin user: {e}")

if __name__ == '__main__':
    create_default_admin()
    
    # Get host and port from environment or use defaults
    host = os.environ.get('FLASK_HOST', '0.0.0.0')
    port = int(os.environ.get('FLASK_PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    
    print(f"Starting VSFTPD Manager on {host}:{port}")
    print(f"Debug mode: {debug}")
    
    app.run(host=host, port=port, debug=debug)