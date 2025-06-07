import subprocess
import os
from models import FTPUser, db
from datetime import datetime

class FTPUserService:
    @staticmethod
    def create_system_user(username, password, home_dir):
        """Create system user for FTP"""
        try:
            # Create user with home directory
            subprocess.run(['sudo', 'useradd', '-m', '-d', home_dir, '-s', '/sbin/nologin', username], check=True)
            
            # Set password
            process = subprocess.Popen(['sudo', 'passwd', username], stdin=subprocess.PIPE)
            process.communicate(input=f'{password}\n{password}\n'.encode())
            
            # Set permissions
            subprocess.run(['sudo', 'chmod', '755', home_dir], check=True)
            subprocess.run(['sudo', 'chown', f'{username}:{username}', home_dir], check=True)
            
            return True, "User created successfully"
        except subprocess.CalledProcessError as e:
            return False, f"Error creating user: {str(e)}"
    
    @staticmethod
    def delete_system_user(username):
        """Delete system user"""
        try:
            subprocess.run(['sudo', 'userdel', '-r', username], check=True)
            return True, "User deleted successfully"
        except subprocess.CalledProcessError as e:
            return False, f"Error deleting user: {str(e)}"
    
    @staticmethod
    def block_user(username):
        """Block FTP user by adding to vsftpd userlist"""
        try:
            with open('/etc/vsftpd/user_list', 'a') as f:
                f.write(f"{username}\n")
            
            # Update database
            ftp_user = FTPUser.get(FTPUser.username == username)
            ftp_user.is_blocked = True
            ftp_user.save()
            
            # Restart vsftpd
            subprocess.run(['sudo', 'systemctl', 'restart', 'vsftpd'], check=True)
            return True, "User blocked successfully"
        except Exception as e:
            return False, f"Error blocking user: {str(e)}"
    
    @staticmethod
    def unblock_user(username):
        """Unblock FTP user"""
        try:
            # Remove from user_list
            with open('/etc/vsftpd/user_list', 'r') as f:
                lines = f.readlines()
            
            with open('/etc/vsftpd/user_list', 'w') as f:
                for line in lines:
                    if line.strip() != username:
                        f.write(line)
            
            # Update database
            ftp_user = FTPUser.get(FTPUser.username == username)
            ftp_user.is_blocked = False
            ftp_user.save()
            
            # Restart vsftpd
            subprocess.run(['sudo', 'systemctl', 'restart', 'vsftpd'], check=True)
            return True, "User unblocked successfully"
        except Exception as e:
            return False, f"Error unblocking user: {str(e)}"