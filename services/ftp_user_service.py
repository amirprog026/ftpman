import subprocess
import os
import pwd
import grp
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
                pwd.getpwnam(username)
                return False, f"User {username} already exists"
            except KeyError:
                # User doesn't exist, continue with creation
                pass
            
            # Create user with home directory
            cmd = [
                'sudo', 'useradd', 
                '-m',                    # Create home directory
                '-d', home_dir,         # Set home directory
                '-s', '/bin/bash',      # Set shell to allow FTP
                username
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                return False, f"Failed to create user: {result.stderr}"
            
            # Set password using chpasswd with echo
            password_cmd = f"echo '{username}:{password}' | sudo chpasswd"
            result = subprocess.run(password_cmd, shell=True, capture_output=True, text=True)
            if result.returncode != 0:
                return False, f"Failed to set password: {result.stderr}"
            
            # Set proper permissions for home directory
            subprocess.run(['sudo', 'chmod', '755', home_dir], capture_output=True, text=True)
            subprocess.run(['sudo', 'chown', f'{username}:{username}', home_dir], capture_output=True, text=True)
            
            # Create a welcome file
            welcome_cmd = f"echo 'Welcome to FTP server, {username}!' | sudo tee {home_dir}/welcome.txt > /dev/null"
            subprocess.run(welcome_cmd, shell=True, capture_output=True, text=True)
            subprocess.run(['sudo', 'chown', f'{username}:{username}', f'{home_dir}/welcome.txt'], capture_output=True, text=True)
            
            return True, f"User {username} created successfully"
            
        except Exception as e:
            return False, f"Unexpected error: {str(e)}"
    
    @staticmethod
    def delete_system_user(username):
        """Delete system user"""
        try:
            # Remove from blocked list first
            FTPUserService._remove_from_user_list(username)
            
            # Delete system user and home directory
            result = subprocess.run(['sudo', 'userdel', '-r', username], capture_output=True, text=True)
            if result.returncode != 0:
                return False, f"Failed to delete user: {result.stderr}"
            
            return True, f"User {username} deleted successfully"
            
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
            # Ensure the user_list file exists
            if not os.path.exists(FTPUserService.USER_LIST_FILE):
                subprocess.run(['sudo', 'touch', FTPUserService.USER_LIST_FILE], check=True)
                subprocess.run(['sudo', 'chmod', '644', FTPUserService.USER_LIST_FILE], check=True)
            
            # Check if user is already in the list
            existing_users = []
            try:
                with open(FTPUserService.USER_LIST_FILE, 'r') as f:
                    existing_users = [line.strip() for line in f.readlines()]
            except (FileNotFoundError, PermissionError):
                pass
            
            if username in existing_users:
                return True, f"User {username} already in block list"
            
            # Add user to the list using echo and tee
            add_cmd = f"echo '{username}' | sudo tee -a {FTPUserService.USER_LIST_FILE} > /dev/null"
            result = subprocess.run(add_cmd, shell=True, capture_output=True, text=True)
            
            if result.returncode != 0:
                return False, f"Failed to add user to block list: {result.stderr}"
            
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
            try:
                with open(FTPUserService.USER_LIST_FILE, 'r') as f:
                    lines = f.readlines()
            except (FileNotFoundError, PermissionError):
                return True, "User list file doesn't exist or not accessible"
            
            # Filter out the username
            filtered_lines = [line for line in lines if line.strip() != username]
            
            # Create temporary file with filtered content
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
                tmp_file.writelines(filtered_lines)
                temp_path = tmp_file.name
            
            # Move temp file to actual file with sudo
            result = subprocess.run(['sudo', 'mv', temp_path, FTPUserService.USER_LIST_FILE], 
                                  capture_output=True, text=True)
            if result.returncode != 0:
                os.unlink(temp_path)  # Clean up temp file
                return False, f"Failed to update user list: {result.stderr}"
            
            subprocess.run(['sudo', 'chmod', '644', FTPUserService.USER_LIST_FILE], 
                         capture_output=True, text=True)
            
            return True, f"User {username} removed from block list"
            
        except Exception as e:
            return False, f"Error removing user from block list: {str(e)}"
    
    @staticmethod
    def _restart_vsftpd():
        """Restart VSFTPD service"""
        try:
            result = subprocess.run(['sudo', 'systemctl', 'restart', 'vsftpd'], 
                                  capture_output=True, text=True)
            if result.returncode != 0:
                return False, f"Failed to restart VSFTPD: {result.stderr}"
            return True, "VSFTPD restarted successfully"
        except Exception as e:
            return False, f"Failed to restart VSFTPD: {str(e)}"
    
    @staticmethod
    def check_user_exists(username):
        """Check if system user exists"""
        try:
            pwd.getpwnam(username)
            return True
        except KeyError:
            return False
    
    @staticmethod
    def get_user_home_dir(username):
        """Get user's home directory"""
        try:
            user_info = pwd.getpwnam(username)
            return user_info.pw_dir
        except KeyError:
            return f"/home/{username}"
    
    @staticmethod
    def get_blocked_users():
        """Get list of blocked users from user_list file"""
        try:
            if not os.path.exists(FTPUserService.USER_LIST_FILE):
                return []
            
            with open(FTPUserService.USER_LIST_FILE, 'r') as f:
                blocked_users = [line.strip() for line in f.readlines() if line.strip()]
            
            return blocked_users
            
        except Exception as e:
            print(f"Error reading blocked users: {e}")
            return []
    
    @staticmethod
    def get_system_users():
        """Get list of system users that can use FTP"""
        try:
            users = []
            for user in pwd.getpwall():
                # Get users with UID >= 1000 (regular users)
                if user.pw_uid >= 1000 and user.pw_uid < 65534:
                    users.append(user.pw_name)
            return users
        except Exception as e:
            print(f"Error getting system users: {e}")
            return []