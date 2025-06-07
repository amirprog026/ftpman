import os
import re
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
        'max_per_ip': {'type': 'int', 'description': 'Max connections per IP'}
    }
    
    @staticmethod
    def read_config():
        """Read current vsftpd configuration"""
        config = {}
        try:
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
                if line.strip().startswith(f'{key}='):
                    new_lines.append(f'{key}={value}\n')
                    updated = True
                else:
                    new_lines.append(line)
            
            # If key wasn't found, add it
            if not updated:
                new_lines.append(f'{key}={value}\n')
            
            # Write back
            with open(FTPConfigService.CONFIG_FILE, 'w') as f:
                f.writelines(new_lines)
            
            # Log change
            ConfigChange.create(
                config_key=key,
                old_value=old_value,
                new_value=value,
                changed_by=user
            )
            
            # Restart vsftpd
            import subprocess
            subprocess.run(['sudo', 'systemctl', 'restart', 'vsftpd'], check=True)
            
            return True, "Configuration updated successfully"
            
        except Exception as e:
            return False, f"Error updating config: {str(e)}"