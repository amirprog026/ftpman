import subprocess
import os
import pwd
import grp
import tempfile
from models import FTPUser, db
from datetime import datetime

class FTPUserService:
    USER_LIST_FILE = '/etc/vsftpd/user_list'
    
    @staticmethod
    def create_system_user(username, password, home_dir):
        """Create system user for FTP (running as root)"""
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
                'useradd', 
                '-m',                    # Create home directory
                '-d', home_dir,         # Set home directory
                '-s', '/bin/bash',      # Set shell to allow FTP
                username
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                return False, f"Failed to create user: {result.stderr}"
            
            # Set password using chpasswd
            password_process = subprocess.run(
                ['chpasswd'],
                input=f"{username}:{password}",
                text=True,
                capture_output=True
            )
            
            if password_process.returncode != 0:
                return False, f"Failed to set password: {password_process.stderr}"
            
            # Set proper permissions for home directory
            os.chmod(home_dir, 0o755)
            
            # Get user info for chown
            user_info = pwd.getpwnam(username)
            os.chown(home_dir, user_info.pw_uid, user_info.pw_gid)
            
            # Create a welcome file
            welcome_file = os.path.join(home_dir, 'welcome.txt')
            with open(welcome_file, 'w') as f:
                f.write(f'Welcome to FTP server, {username}!\n')
            os.chown(welcome_file, user_info.pw_uid, user_info.pw_gid)
            
            return True, f"User {username} created successfully"
            
        except Exception as e:
            return False, f"Unexpected error: {str(e)}"
    
    @staticmethod
    def delete_system_user(username):
        """Delete system user (running as root)"""
        try:
            # Remove from blocked list first
            FTPUserService._remove_from_user_list(username)
            
            # Delete system user and home directory
            result = subprocess.run(['userdel', '-r', username], capture_output=True, text=True)
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
                with open(FTPUserService.USER_LIST_FILE, 'w') as f:
                    pass
                os.chmod(FTPUserService.USER_LIST_FILE, 0o644)
            
            # Check if user is already in the list
            existing_users = []
            try:
                with open(FTPUserService.USER_LIST_FILE, 'r') as f:
                    existing_users = [line.strip() for line in f.readlines()]
            except FileNotFoundError:
                pass
            
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
            result = subprocess.run(['systemctl', 'restart', 'vsftpd'], 
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