import subprocess
import os
from models import FTPUser, db
from datetime import datetime

class FTPUserService:
    USER_LIST_FILE = '/etc/vsftpd/user_list'
    
    @staticmethod
    def create_system_user(username, password, home_dir):
        """Create system user for FTP"""
        try:
            # Check if user already exists
            try:
                subprocess.run(['id', username], check=True, capture_output=True)
                return False, f"User {username} already exists"
            except subprocess.CalledProcessError:
                # User doesn't exist, continue with creation
                pass
            
            # Create user with home directory and nologin shell
            subprocess.run([
                'sudo', 'useradd', 
                '-m',                    # Create home directory
                '-d', home_dir,         # Set home directory
                '-s', '/bin/bash',      # Set shell (changed from /sbin/nologin to allow FTP)
                username
            ], check=True, capture_output=True)
            
            # Set password using chpasswd (more reliable than passwd)
            password_input = f"{username}:{password}"
            process = subprocess.run([
                'sudo', 'chpasswd'
            ], input=password_input, text=True, check=True, capture_output=True)
            
            # Set proper permissions for home directory
            subprocess.run(['sudo', 'chmod', '755', home_dir], check=True)
            subprocess.run(['sudo', 'chown', f'{username}:{username}', home_dir], check=True)
            
            # Create a test file in user's home directory
            test_file = os.path.join(home_dir, 'welcome.txt')
            subprocess.run([
                'sudo', 'bash', '-c', 
                f'echo "Welcome to FTP server!" > {test_file} && chown {username}:{username} {test_file}'
            ], check=True)
            
            return True, f"User {username} created successfully"
            
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.decode() if e.stderr else str(e)
            return False, f"Error creating user: {error_msg}"
        except Exception as e:
            return False, f"Unexpected error: {str(e)}"
    
    @staticmethod
    def delete_system_user(username):
        """Delete system user"""
        try:
            # Remove from blocked list first
            FTPUserService._remove_from_user_list(username)
            
            # Delete system user and home directory
            subprocess.run(['sudo', 'userdel', '-r', username], check=True, capture_output=True)
            
            return True, f"User {username} deleted successfully"
            
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.decode() if e.stderr else str(e)
            return False, f"Error deleting user: {error_msg}"
        except Exception as e:
            return False, f"Unexpected error: {str(e)}"
    
    @staticmethod
    def block_user(username):
        """Block FTP user by adding to vsftpd userlist"""
        try:
            # Add to user_list file (blocked users)
            success, message = FTPUserService._add_to_user_list(username)
            if not success:
                return False, message
            
            # Update database
            try:
                ftp_user = FTPUser.get(FTPUser.username == username)
                ftp_user.is_blocked = True
                ftp_user.save()
            except FTPUser.DoesNotExist:
                return False, f"User {username} not found in database"
            
            # Restart vsftpd to apply changes
            restart_success, restart_msg = FTPUserService._restart_vsftpd()
            if not restart_success:
                return False, f"User blocked but failed to restart VSFTPD: {restart_msg}"
            
            return True, f"User {username} blocked successfully"
            
        except Exception as e:
            return False, f"Error blocking user: {str(e)}"
    
    @staticmethod
    def unblock_user(username):
        """Unblock FTP user by removing from userlist"""
        try:
            # Remove from user_list file
            success, message = FTPUserService._remove_from_user_list(username)
            if not success:
                return False, message
            
            # Update database
            try:
                ftp_user = FTPUser.get(FTPUser.username == username)
                ftp_user.is_blocked = False
                ftp_user.save()
            except FTPUser.DoesNotExist:
                return False, f"User {username} not found in database"
            
            # Restart vsftpd to apply changes
            restart_success, restart_msg = FTPUserService._restart_vsftpd()
            if not restart_success:
                return False, f"User unblocked but failed to restart VSFTPD: {restart_msg}"
            
            return True, f"User {username} unblocked successfully"
            
        except Exception as e:
            return False, f"Error unblocking user: {str(e)}"
    
    @staticmethod
    def _add_to_user_list(username):
        """Add username to vsftpd user_list file"""
        try:
            # Check if user is already in the list
            if os.path.exists(FTPUserService.USER_LIST_FILE):
                with open(FTPUserService.USER_LIST_FILE, 'r') as f:
                    existing_users = [line.strip() for line in f.readlines()]
                    if username in existing_users:
                        return True, f"User {username} already in block list"
            
            # Add user to the list
            with open(FTPUserService.USER_LIST_FILE, 'a') as f:
                f.write(f"{username}\n")
            
            return True, f"User {username} added to block list"
            
        except Exception as e:
            return False, f"Error adding user to block list: {str(e)}"
    
    @staticmethod
    def _remove_from_user_list(username):
        """Remove username from vsftpd user_list file"""
        try:
            if not os.path.exists(FTPUserService.USER_LIST_FILE):
                return True, "User list file doesn't exist"
            
            # Read current list
            with open(FTPUserService.USER_LIST_FILE, 'r') as f:
                lines = f.readlines()
            
            # Filter out the username
            filtered_lines = [line for line in lines if line.strip() != username]
            
            # Write back the filtered list
            with open(FTPUserService.USER_LIST_FILE, 'w') as f:
                f.writelines(filtered_lines)
            
            return True, f"User {username} removed from block list"
            
        except Exception as e:
            return False, f"Error removing user from block list: {str(e)}"
    
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
    def get_system_users():
        """Get list of system users that can use FTP"""
        try:
            # Get users from /etc/passwd with UID >= 1000 (regular users)
            result = subprocess.run([
                'awk', '-F:', '$3>=1000 && $3<65534 {print $1}', '/etc/passwd'
            ], capture_output=True, text=True, check=True)
            
            users = result.stdout.strip().split('\n')
            return [user for user in users if user]  # Filter empty strings
            
        except Exception as e:
            return []
    
    @staticmethod
    def check_user_exists(username):
        """Check if system user exists"""
        try:
            subprocess.run(['id', username], check=True, capture_output=True)
            return True
        except subprocess.CalledProcessError:
            return False
    
    @staticmethod
    def get_user_home_dir(username):
        """Get user's home directory"""
        try:
            result = subprocess.run([
                'getent', 'passwd', username
            ], capture_output=True, text=True, check=True)
            
            # Parse passwd entry: username:x:uid:gid:gecos:home:shell
            parts = result.stdout.strip().split(':')
            if len(parts) >= 6:
                return parts[5]  # home directory
            return f"/home/{username}"
            
        except Exception:
            return f"/home/{username}"