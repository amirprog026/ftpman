#!/bin/bash

# VSFTPD Manager Setup Script with Virtual Environment

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

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   print_error "This script should not be run as root for security reasons"
   print_status "Please run as a regular user with sudo privileges"
   exit 1
fi

# Update system
print_status "Updating system packages..."
sudo apt update

# Install required system packages
print_status "Installing system dependencies..."
sudo apt install -y python3 python3-pip python3-venv vsftpd sqlite3 net-tools psmisc

# Create application directory
APP_DIR="/opt/vsftpd-manager"
print_status "Creating application directory: $APP_DIR"
sudo mkdir -p $APP_DIR
sudo chown $USER:$USER $APP_DIR

# Copy application files
print_status "Copying application files..."
cp -r . $APP_DIR/
cd $APP_DIR

# Create virtual environment
print_status "Creating Python virtual environment..."
python3 -m venv venv

# Activate virtual environment and install dependencies
print_status "Installing Python dependencies in virtual environment..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Create vsftpd directories
print_status "Setting up VSFTPD directories..."
sudo mkdir -p /etc/vsftpd
sudo touch /etc/vsftpd/user_list

# Backup original vsftpd config if it exists
if [ -f /etc/vsftpd.conf ]; then
    print_status "Backing up existing VSFTPD configuration..."
    sudo cp /etc/vsftpd.conf /etc/vsftpd.conf.backup.$(date +%Y%m%d_%H%M%S)
fi

# Create VSFTPD configuration
print_status "Creating VSFTPD configuration..."
sudo tee /etc/vsftpd/vsftpd.conf > /dev/null <<EOF
# VSFTPD Configuration for VSFTPD Manager
listen=YES
listen_ipv6=NO
anonymous_enable=NO
local_enable=YES
write_enable=YES
local_umask=022
dirmessage_enable=YES
use_localtime=YES
xferlog_enable=YES
connect_from_port_20=YES
chroot_local_user=YES
allow_writeable_chroot=YES
secure_chroot_dir=/var/run/vsftpd/empty
pam_service_name=vsftpd
rsa_cert_file=/etc/ssl/certs/ssl-cert-snakeoil.pem
rsa_private_key_file=/etc/ssl/private/ssl-cert-snakeoil.key
ssl_enable=NO
userlist_enable=YES
userlist_file=/etc/vsftpd/user_list
userlist_deny=YES
log_ftp_protocol=YES
xferlog_file=/var/log/vsftpd.log
dual_log_enable=YES
vsftpd_log_file=/var/log/vsftpd.log
pasv_enable=YES
pasv_min_port=21100
pasv_max_port=21110
pasv_address=\$(hostname -I | awk '{print \$1}')
EOF

# Set proper permissions
print_status "Setting file permissions..."
sudo chmod 644 /etc/vsftpd/vsftpd.conf
sudo chmod 644 /etc/vsftpd/user_list

# Create log file
sudo touch /var/log/vsftpd.log
sudo chmod 644 /var/log/vsftpd.log

# Create startup script
print_status "Creating startup script..."
cat > $APP_DIR/start.sh << 'EOF'
#!/bin/bash

# VSFTPD Manager Startup Script
APP_DIR="/opt/vsftpd-manager"
cd $APP_DIR

# Activate virtual environment
source venv/bin/activate

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
        print('Username: admin')
        print('Password: admin123')
    else:
        print('Admin user already exists')
except Exception as e:
    print(f'Error initializing database: {e}')
"

# Start Flask application
echo "Starting VSFTPD Manager..."
python3 app.py
EOF

chmod +x $APP_DIR/start.sh

# Create systemd service
print_status "Creating systemd service..."
sudo tee /etc/systemd/system/vsftpd-manager.service > /dev/null <<EOF
[Unit]
Description=VSFTPD Manager Flask Application
After=network.target vsftpd.service
Requires=vsftpd.service

[Service]
Type=simple
User=$USER
Group=$USER
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

# Create sudoers file for the application user
print_status "Setting up sudo permissions for VSFTPD management..."
sudo tee /etc/sudoers.d/vsftpd-manager > /dev/null <<EOF
# Allow $USER to manage VSFTPD and users without password
$USER ALL=(ALL) NOPASSWD: /usr/sbin/useradd
$USER ALL=(ALL) NOPASSWD: /usr/sbin/userdel
$USER ALL=(ALL) NOPASSWD: /usr/bin/passwd
$USER ALL=(ALL) NOPASSWD: /bin/systemctl restart vsftpd
$USER ALL=(ALL) NOPASSWD: /bin/systemctl start vsftpd
$USER ALL=(ALL) NOPASSWD: /bin/systemctl stop vsftpd
$USER ALL=(ALL) NOPASSWD: /bin/systemctl status vsftpd
$USER ALL=(ALL) NOPASSWD: /bin/kill
$USER ALL=(ALL) NOPASSWD: /bin/chmod
$USER ALL=(ALL) NOPASSWD: /bin/chown
$USER ALL=(ALL) NOPASSWD: /usr/bin/netstat
EOF

# Enable and start VSFTPD service
print_status "Enabling and starting VSFTPD service..."
sudo systemctl enable vsftpd
sudo systemctl start vsftpd

# Check VSFTPD status
if sudo systemctl is-active --quiet vsftpd; then
    print_status "VSFTPD service is running successfully"
else
    print_warning "VSFTPD service is not running. Checking status..."
    sudo systemctl status vsftpd
fi

# Enable the VSFTPD Manager service
print_status "Enabling VSFTPD Manager service..."
sudo systemctl daemon-reload
sudo systemctl enable vsftpd-manager

# Create a manual start script for development
cat > $APP_DIR/run_dev.sh << 'EOF'
#!/bin/bash

# Development startup script
APP_DIR="/opt/vsftpd-manager"
cd $APP_DIR

# Activate virtual environment
source venv/bin/activate

# Set Flask environment variables
export FLASK_ENV=development
export FLASK_DEBUG=1

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

# Create firewall rules (if UFW is available)
if command -v ufw &> /dev/null; then
    print_status "Configuring firewall rules..."
    sudo ufw allow 21/tcp
    sudo ufw allow 5000/tcp
    sudo ufw allow 21100:21110/tcp
    print_status "Firewall rules added for FTP (21), Web Interface (5000), and Passive ports (21100-21110)"
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
echo "  Start service:    sudo systemctl start vsftpd-manager"
echo "  Stop service:     sudo systemctl stop vsftpd-manager"
echo "  Service status:   sudo systemctl status vsftpd-manager"
echo "  View logs:        journalctl -u vsftpd-manager -f"
echo ""
echo -e "${YELLOW}Development Mode:${NC}"
echo "  Run manually:     $APP_DIR/run_dev.sh"
echo ""
echo -e "${YELLOW}Access URLs:${NC}"
echo "  Web Interface:    http://$(hostname -I | awk '{print $1}'):5000"
echo "  Local Access:     http://localhost:5000"
echo ""
echo -e "${YELLOW}Important Files:${NC}"
echo "  Application:      $APP_DIR"
echo "  VSFTPD Config:    /etc/vsftpd/vsftpd.conf"
echo "  User List:        /etc/vsftpd/user_list"
echo "  Logs:             /var/log/vsftpd.log"
echo ""
echo -e "${GREEN}Next Steps:${NC}"
echo "1. Change the default admin password after first login"
echo "2. Configure your firewall if needed"
echo "3. Start the service: sudo systemctl start vsftpd-manager"
echo ""