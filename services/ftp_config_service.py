import os
import re
import subprocess
from models import ConfigChange, db

class FTPConfigService:
    CONFIG_FILE = '/etc/vsftpd/vsftpd.conf'
    
    # Common vsftpd configuration options
    CONFIG_OPTIONS = {
        'anonymous_enable': {'type': 'bool', 'description': 'Allow anonymous FTP'},
        'local_enable': {'type': 'bool', 'description': 'Allow local users to log in'},
        'write_enable': {'type': 'bool', 'description': 'Enable write commands'},
        'local_umask': {'type': 'string', 'description': 'Default umask for local users'},
        'anon_upload_enable': {'type': 'bool', 'description': 'Allow anonymous uploads'},
        'anon_mkdir_write_enable': {'type': 'bool', 'description': 'Allow anonymous mkdir'},
        'dirmessage_enable': {'type': 'bool', 'description': 'Enable directory messages'},
        'xferlog_enable': {'type': 'bool', 'description': 'Enable transfer logging'},
        'connect_from_port_20': {'type': 'bool', 'description': 'Use port 20 for data'},
        'idle_session_timeout': {'type': 'int', 'description': 'Idle session timeout (seconds)'},
        'data_connection_timeout': {'type': 'int', 'description': 'Data connection timeout'},
        'ftpd_banner': {'type': 'string', 'description': 'FTP server banner'},
        'chroot_local_user': {'type': 'bool', 'description': 'Chroot local users'},
        'max_clients': {'type': 'int', 'description': 'Maximum number of clients'},
        'max_per_ip': {'type': 'int', 'description': 'Max connections per IP'},
        'userlist_enable': {'type': 'bool', 'description': 'Enable user list'},
        'userlist_deny': {'type': 'bool', 'description': 'Deny users in user list'},
        'pasv_enable': {'type': 'bool', 'description': 'Enable passive mode'},
        'pasv_min_port': {'type': 'int', 'description': 'Passive mode min port'},
        'pasv_max_port': {'type': 'int', 'description': 'Passive mode max port'}
    }
    
    @staticmethod
    def read_config():
        """Read current vsftpd configuration"""
        config = {}
        try:
            if not os.path.exists(FTPConfigService.CONFIG_FILE):
                return config
                
            with open(FTPConfigService.CONFIG_FILE, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        if '=' in line:
                            key, value = line.split('=', 1)
                            config[key.strip()] = value.strip()
        except Exception as e:
            print(f"Error reading config: {str(e)}")
            
        return config
    
    @staticmethod
    def update_config(key, value, user):
        """Update vsftpd configuration"""
        try:
            # Backup current config
            backup_success, backup_msg = FTPConfigService._backup_config()
            if not backup_success:
                return False, f"Failed to backup config: {backup_msg}"
            
            # Read current config
            current_config = FTPConfigService.read_config()
            old_value = current_config.get(key, None)
            
            # Read file content
            with open(FTPConfigService.CONFIG_FILE, 'r') as f:
                lines = f.readlines()
            
            # Update or add configuration
            updated = False
            new_lines = []
            
            for line in lines:
                stripped_line = line.strip()
                if stripped_line.startswith(f'{key}='):
                    new_lines.append(f'{key}={value}\n')
                    updated = True
                else:
                    new_lines.append(line)
            
            # If key wasn't found, add it
            if not updated:
                new_lines.append(f'{key}={value}\n')
            
            # Write back to temporary file first
            temp_file = f"{FTPConfigService.CONFIG_FILE}.tmp"
            with open(temp_file, 'w') as f:
                f.writelines(new_lines)
            
            # Move temp file to actual config file
            subprocess.run(['sudo', 'mv', temp_file, FTPConfigService.CONFIG_FILE], check=True)
            subprocess.run(['sudo', 'chmod', '644', FTPConfigService.CONFIG_FILE], check=True)
            
            # Log change
            ConfigChange.create(
                config_key=key,
                old_value=old_value,
                new_value=value,
                changed_by=user
            )
            
            # Restart vsftpd
            restart_success, restart_msg = FTPConfigService._restart_vsftpd()
            if not restart_success:
                return False, f"Config updated but failed to restart VSFTPD: {restart_msg}"
            
            return True, "Configuration updated successfully"
            
        except Exception as e:
            return False, f"Error updating config: {str(e)}"
    
    @staticmethod
    def _backup_config():
        """Create backup of current configuration"""
        try:
            from datetime import datetime
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_file = f"{FTPConfigService.CONFIG_FILE}.backup.{timestamp}"
            
            subprocess.run([
                'sudo', 'cp', FTPConfigService.CONFIG_FILE, backup_file
            ], check=True)
            
            return True, f"Config backed up to {backup_file}"
        except Exception as e:
            return False, str(e)
    
    @staticmethod
    def _restart_vsftpd():
        """Restart VSFTPD service"""
        try:
            subprocess.run(['sudo', 'systemctl', 'restart', 'vsftpd'], 
                         check=True, capture_output=True)
            return True, "VSFTPD restarted successfully"
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.decode() if e.stderr else str(e)
            return False, f"Failed to restart VSFTPD: {error_msg}"
    
    @staticmethod
    def validate_config():
        """Validate current VSFTPD configuration"""
        try:
            # Test configuration by checking if vsftpd can start
            result = subprocess.run([
                'sudo', 'vsftpd', '-t', FTPConfigService.CONFIG_FILE
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                return True, "Configuration is valid"
            else:
                return False, f"Configuration error: {result.stderr}"
                
        except Exception as e:
            return False, f"Error validating config: {str(e)}"