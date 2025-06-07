#!/bin/bash

# VSFTPD Manager Setup Script - Root Approach

echo "Starting VSFTPD Manager setup..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root for this setup
if [[ $EUID -ne 0 ]]; then
   print_error "This setup script must be run as root for FTP user management"
   print_status "Please run: sudo ./setup.sh"
   exit 1
fi

# Get the original user who ran sudo
ORIGINAL_USER=${SUDO_USER:-$USER}
if [ "$ORIGINAL_USER" = "root" ]; then
    print_error "Please run this script with sudo from a regular user account"
    print_status "Example: sudo ./setup.sh"
    exit 1
fi

print_status "Setting up VSFTPD Manager for user: $ORIGINAL_USER"

# Update system
print_status "Updating system packages..."
apt update

# Install required system packages
print_status "Installing system dependencies..."
apt install -y python3 python3-pip python3-venv vsftpd sqlite3 net-tools psmisc

# Create application directory
APP_DIR="/opt/vsftpd-manager"
print_status "Creating application directory: $APP_DIR"
mkdir -p $APP_DIR

# Copy application files
print_status "Copying application files..."
cp -r . $APP_DIR/
cd $APP_DIR

# Set ownership to original user for development
chown -R $ORIGINAL_USER:$ORIGINAL_USER $APP_DIR

# Create virtual environment as original user
print_status "Creating Python virtual environment..."
sudo -u $ORIGINAL_USER python3 -m venv venv

# Install dependencies as original user
print_status "Installing Python dependencies..."
sudo -u $ORIGINAL_USER bash -c "
source venv/bin/activate
pip install --upgrade pip
pip install Flask==2.3.3
pip install Werkzeug==2.3.7
pip install flask-login==0.6.3
pip install peewee==3.16.3
pip install psutil==5.9.5
pip install Jinja2==3.1.2
pip install MarkupSafe==2.1.3
pip install click==8.1.7
pip install itsdangerous==2.1.2
"

# Verify installation
print_status "Verifying package installation..."
sudo -u $ORIGINAL_USER bash -c "
cd $APP_DIR
source venv/bin/activate
python3 -c '
try:
    from flask import Flask
    from flask_login import LoginManager
    from peewee import SqliteDatabase
    import psutil
    print(\"All packages imported successfully!\")
except ImportError as e:
    print(f\"Import error: {e}\")
    exit(1)
'
"

# Create vsftpd directories
print_status "Setting up VSFTPD directories..."
mkdir -p /etc/vsftpd
touch /etc/vsftpd/user_list

# Backup original vsftpd config if it exists
if [ -f /etc/vsftpd.conf ]; then
    print_status "Backing up existing VSFTPD configuration..."
    cp /etc/vsftpd.conf /etc/vsftpd.conf.backup.$(date +%Y%m%d_%H%M%S)
fi

# Create VSFTPD configuration
print_status "Creating VSFTPD configuration..."
cat > /etc/vsftpd/vsftpd.conf << 'EOF'
# VSFTPD Configuration for VSFTPD Manager
listen=YES
listen_ipv6=NO

# Anonymous settings
anonymous_enable=NO
anon_upload_enable=NO
anon_mkdir_write_enable=NO

# Local user settings
local_enable=YES
write_enable=YES
local_umask=022

# Security settings
chroot_local_user=YES
allow_writeable_chroot=YES
secure_chroot_dir=/var/run/vsftpd/empty

# Directory settings
dirmessage_enable=YES
use_localtime=YES

# Logging
xferlog_enable=YES
log_ftp_protocol=YES
xferlog_file=/var/log/vsftpd.log
dual_log_enable=YES
vsftpd_log_file=/var/log/vsftpd.log

# Connection settings
connect_from_port_20=YES
idle_session_timeout=600
data_connection_timeout=120

# SSL/TLS (disabled for now)
ssl_enable=NO
rsa_cert_file=/etc/ssl/certs/ssl-cert-snakeoil.pem
rsa_private_key_file=/etc/ssl/private/ssl-cert-snakeoil.key

# User list settings
userlist_enable=YES
userlist_file=/etc/vsftpd/user_list
userlist_deny=YES

# Passive mode settings
pasv_enable=YES
pasv_min_port=21100
pasv_max_port=21110

# File permissions
file_open_mode=0666
local_umask=022

# Additional write permissions
chmod_enable=YES
EOF

# Get server IP for passive mode
SERVER_IP=$(hostname -I | awk '{print $1}')
if [ ! -z "$SERVER_IP" ]; then
    echo "pasv_address=$SERVER_IP" >> /etc/vsftpd/vsftpd.conf
fi

# Set proper permissions
chmod 644 /etc/vsftpd/vsftpd.conf
chmod 644 /etc/vsftpd/user_list

# Create log file
touch /var/log/vsftpd.log
chmod 644 /var/log/vsftpd.log

# Create startup script that runs as root
print_status "Creating startup script..."
cat > $APP_DIR/start.sh << 'EOF'
#!/bin/bash

# VSFTPD Manager Startup Script (runs as root)
APP_DIR="/opt/vsftpd-manager"
cd $APP_DIR

# Activate virtual environment
source venv/bin/activate

# Set environment variables
export FLASK_HOST="0.0.0.0"
export FLASK_PORT="5000"
export FLASK_DEBUG="False"

# Initialize database and create default admin user
python3 -c "
from models import create_tables, User, db
try:
    create_tables()
    if not User.select().where(User.username == 'admin').exists():
        admin = User(username='admin', email='admin@example.com', is_admin=True)
        admin.set_password('admin123')
        admin.save()
        print('Default admin user created successfully')
        print('Username: admin, Password: admin123')
    else:
        print('Admin user already exists')
except Exception as e:
    print(f'Error initializing database: {e}')
"

# Start Flask application as root
echo "Starting VSFTPD Manager as root..."
python3 app.py
EOF

chmod +x $APP_DIR/start.sh

# Create systemd service that runs as root
print_status "Creating systemd service..."
cat > /etc/systemd/system/vsftpd-manager.service << EOF
[Unit]
Description=VSFTPD Manager Flask Application
After=network.target vsftpd.service
Requires=vsftpd.service

[Service]
Type=simple
User=root
Group=root
WorkingDirectory=$APP_DIR
Environment=PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
ExecStart=$APP_DIR/start.sh
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Enable and start VSFTPD service
print_status "Enabling and starting VSFTPD service..."
systemctl enable vsftpd
systemctl start vsftpd

# Check VSFTPD status
if systemctl is-active --quiet vsftpd; then
    print_status "VSFTPD service is running successfully"
else
    print_warning "VSFTPD service is not running. Checking status..."
    systemctl status vsftpd
fi

# Enable the VSFTPD Manager service
print_status "Enabling VSFTPD Manager service..."
systemctl daemon-reload
systemctl enable vsftpd-manager

# Create development script
cat > $APP_DIR/run_dev.sh << EOF
#!/bin/bash

# Development startup script (run as root)
if [[ \$EUID -ne 0 ]]; then
   echo "Development mode must also run as root for user management"
   echo "Please run: sudo ./run_dev.sh"
   exit 1
fi

APP_DIR="/opt/vsftpd-manager"
cd \$APP_DIR

# Activate virtual environment
source venv/bin/activate

# Set Flask environment variables
export FLASK_ENV=development
export FLASK_DEBUG=1
export FLASK_HOST=0.0.0.0
export FLASK_PORT=5000

# Initialize database
python3 -c "
from models import create_tables, User
try:
    create_tables()
    if not User.select().where(User.username == 'admin').exists():
        admin = User(username='admin', email='admin@example.com', is_admin=True)
        admin.set_password('admin123')
        admin.save()
        print('Default admin user created')
    print('Database initialized successfully')
except Exception as e:
    print(f'Database initialization error: {e}')
"

echo "Starting VSFTPD Manager in development mode..."
echo "Access the application at: http://localhost:5000"
echo "Default credentials - Username: admin, Password: admin123"
python3 app.py
EOF

chmod +x $APP_DIR/run_dev.sh

# Configure firewall (if UFW is available)
if command -v ufw &> /dev/null; then
    print_status "Configuring firewall rules..."
    ufw allow 21/tcp
    ufw allow 5000/tcp
    ufw allow 21100:21110/tcp
    print_status "Firewall rules added"
fi

print_status "Setup completed successfully!"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${GREEN}VSFTPD Manager Installation Complete!${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo -e "${YELLOW}Default Admin Credentials:${NC}"
echo "  Username: admin"
echo "  Password: admin123"
echo ""
echo -e "${YELLOW}Service Management:${NC}"
echo "  Start service:    systemctl start vsftpd-manager"
echo "  Stop service:     systemctl stop vsftpd-manager"
echo "  Service status:   systemctl status vsftpd-manager"
echo "  View logs:        journalctl -u vsftpd-manager -f"
echo ""
echo -e "${YELLOW}Development Mode:${NC}"
echo "  Run manually:     sudo $APP_DIR/run_dev.sh"
echo ""
echo -e "${YELLOW}Access URLs:${NC}"
echo "  Web Interface:    http://$(hostname -I | awk '{print $1}'):5000"
echo "  Local Access:     http://localhost:5000"
echo ""
echo -e "${GREEN}Next Steps:${NC}"
echo "1. Start the service: systemctl start vsftpd-manager"
echo "2. Change the default admin password after first login"
echo ""