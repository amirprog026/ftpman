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
    try:
        # Get users from database and sync with system users
        db_users = list(FTPUser.select().dicts())
        system_users = FTPUserService.get_system_users()
        blocked_users = FTPUserService.get_blocked_users()
        
        # Combine information
        users_data = []
        
        # Add database users
        for user in db_users:
            user['exists_in_system'] = user['username'] in system_users
            user['is_blocked'] = user['username'] in blocked_users
            users_data.append(user)
        
        # Add system users not in database
        for sys_user in system_users:
            if not any(u['username'] == sys_user for u in db_users):
                users_data.append({
                    'id': None,
                    'username': sys_user,
                    'home_directory': FTPUserService.get_user_home_dir(sys_user),
                    'is_active': True,
                    'is_blocked': sys_user in blocked_users,
                    'created_at': None,
                    'created_by': None,
                    'exists_in_system': True
                })
        
        return jsonify(users_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/users', methods=['POST'])
@login_required
def create_ftp_user():
    try:
        data = request.json
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        home_dir = data.get('home_directory', '').strip()
        
        # Validation
        if not username:
            return jsonify({'success': False, 'message': 'Username is required'}), 400
        
        if not password:
            return jsonify({'success': False, 'message': 'Password is required'}), 400
            
        if len(password) < 6:
            return jsonify({'success': False, 'message': 'Password must be at least 6 characters'}), 400
        
        # Set default home directory if not provided
        if not home_dir:
            home_dir = f'/home/{username}'
        
        # Check if user already exists
        if FTPUserService.check_user_exists(username):
            return jsonify({'success': False, 'message': 'User already exists'}), 400
        
        # Create system user
        success, message = FTPUserService.create_system_user(username, password, home_dir)
        
        if success:
            # Create database record
            try:
                ftp_user = FTPUser.create(
                    username=username,
                    home_directory=home_dir,
                    created_by=current_user,
                    is_active=True,
                    is_blocked=False
                )
                return jsonify({'success': True, 'message': message, 'user_id': ftp_user.id})
            except Exception as db_error:
                return jsonify({'success': True, 'message': f"{message} (DB warning: {str(db_error)})"})
        else:
            return jsonify({'success': False, 'message': message}), 400
            
    except Exception as e:
        return jsonify({'success': False, 'message': f'Unexpected error: {str(e)}'}), 500

@app.route('/api/users/<username>', methods=['DELETE'])
@login_required
def delete_ftp_user(username):
    try:
        # Delete system user
        success, message = FTPUserService.delete_system_user(username)
        
        if success:
            # Delete from database if exists
            try:
                ftp_user = FTPUser.get(FTPUser.username == username)
                ftp_user.delete_instance()
            except FTPUser.DoesNotExist:
                pass  # User not in database, that's OK
            
            return jsonify({'success': True, 'message': message})
        else:
            return jsonify({'success': False, 'message': message}), 400
            
    except Exception as e:
        return jsonify({'success': False, 'message': f'Unexpected error: {str(e)}'}), 500

@app.route('/api/users/<username>/block', methods=['POST'])
@login_required
def block_user(username):
    try:
        success, message = FTPUserService.block_user(username)
        return jsonify({'success': success, 'message': message})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500

@app.route('/api/users/<username>/unblock', methods=['POST'])
@login_required
def unblock_user(username):
    try:
        success, message = FTPUserService.unblock_user(username)
        return jsonify({'success': success, 'message': message})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500

@app.route('/api/logs', methods=['GET'])
@login_required
def get_logs():
    try:
        # Get logs from FTP log service
        logs = FTPLogService.get_recent_logs(limit=100)
        return jsonify(logs)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/connections', methods=['GET'])
@login_required
def get_connections():
    try:
        # Get active connections
        connections = FTPConnectionService.get_active_connections()
        return jsonify(connections)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/connections/<int:pid>/kill', methods=['POST'])
@login_required
def kill_connection(pid):
    try:
        success, message = FTPConnectionService.kill_connection(pid)
        return jsonify({'success': success, 'message': message})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500

@app.route('/api/config', methods=['GET'])
@login_required
def get_config():
    try:
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
            else:
                config_with_meta[key] = {
                    'value': value,
                    'type': 'string',
                    'description': 'Custom configuration option'
                }
        return jsonify(config_with_meta)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/config', methods=['POST'])
@login_required
def update_config():
    try:
        data = request.json
        key = data.get('key')
        value = data.get('value')
        
        success, message = FTPConfigService.update_config(key, value, current_user)
        return jsonify({'success': success, 'message': message})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500

@app.route('/api/stats', methods=['GET'])
@login_required
def get_stats():
    try:
        # Get statistics for dashboard
        system_users = FTPUserService.get_system_users()
        blocked_users = FTPUserService.get_blocked_users()
        active_connections = FTPConnectionService.get_active_connections()
        
        total_users = len(system_users)
        total_blocked = len(blocked_users)
        total_connections = len(active_connections)
        
        # Get recent activity
        recent_logs = FTPLogService.get_recent_logs(limit=10)
        
        return jsonify({
            'total_users': total_users,
            'active_connections': total_connections,
            'blocked_users': total_blocked,
            'recent_activity': len(recent_logs),
            'vsftpd_status': FTPConfigService.get_service_status()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Health check endpoint
@app.route('/health')
def health_check():
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})

# Debug endpoints
@app.route('/api/debug/system-users')
@login_required
def debug_system_users():
    try:
        users = FTPUserService.get_system_users()
        return jsonify({'system_users': users})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/debug/blocked-users')
@login_required
def debug_blocked_users():
    try:
        users = FTPUserService.get_blocked_users()
        return jsonify({'blocked_users': users})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/users/<username>/fix-permissions', methods=['POST'])
@login_required
def fix_user_permissions(username):
    try:
        success, message = FTPUserService.fix_user_permissions(username)
        return jsonify({'success': success, 'message': message})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500

@app.route('/api/users/<username>/test-write', methods=['GET'])
@login_required
def test_user_write_access(username):
    try:
        success, result = FTPUserService.test_user_write_access(username)
        return jsonify({'success': success, 'result': result})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500


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