import subprocess
import os
import pwd
import grp
import tempfile
from models import FTPUser, db
from datetime import datetime
import subprocess
import os
import pwd
import grp
import stat
import tempfile
from models import FTPUser, db
from datetime import datetime

class FTPUserService:
    USER_LIST_FILE = '/etc/vsftpd/user_list'
    
    @staticmethod
    def create_system_user(username, password, home_dir):
        """Create system user for FTP with proper write permissions"""
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
                '-G', 'ftp',           # Add to ftp group
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
            
            # Get user info for proper ownership
            user_info = pwd.getpwnam(username)
            uid = user_info.pw_uid
            gid = user_info.pw_gid
            
            # Set proper permissions for home directory
            os.chmod(home_dir, 0o755)
            os.chown(home_dir, uid, gid)
            
            # Create subdirectories with write permissions
            upload_dir = os.path.join(home_dir, 'uploads')
            downloads_dir = os.path.join(home_dir, 'downloads')
            public_dir = os.path.join(home_dir, 'public')
            
            for directory in [upload_dir, downloads_dir, public_dir]:
                os.makedirs(directory, exist_ok=True)
                os.chmod(directory, 0o755)
                os.chown(directory, uid, gid)
            
            # Create welcome file with proper permissions
            welcome_file = os.path.join(home_dir, 'README.txt')
            with open(welcome_file, 'w') as f:
                f.write(f'''Welcome to FTP server, {username}!

Your FTP account has been created successfully.

Directory structure:
- /uploads/   - Upload your files here
- /downloads/ - Download files from here  
- /public/    - Public files accessible to others

You have full read/write access to all directories.

Happy file transferring!
''')
            os.chmod(welcome_file, 0o644)
            os.chown(welcome_file, uid, gid)
            
            # Create test file to verify write access
            test_file = os.path.join(upload_dir, 'test_write_access.txt')
            with open(test_file, 'w') as f:
                f.write(f'This file confirms write access is working for {username}\n')
                f.write(f'Created on: {datetime.now()}\n')
            os.chmod(test_file, 0o644)
            os.chown(test_file, uid, gid)
            
            # Ensure the user can write to their home directory
            # This is crucial for chrooted users
            FTPUserService._fix_chroot_permissions(home_dir, uid, gid)
            
            return True, f"User {username} created successfully with write access"
            
        except Exception as e:
            return False, f"Unexpected error: {str(e)}"
    
    @staticmethod
    def _fix_chroot_permissions(home_dir, uid, gid):
        """Fix permissions for chrooted FTP users"""
        try:
            # For chrooted users, the home directory should be owned by root
            # but subdirectories should be owned by the user
            
            # Set home directory permissions (required for chroot)
            os.chmod(home_dir, 0o755)
            
            # Create a writable subdirectory structure
            writable_dirs = ['uploads', 'downloads', 'public', 'files']
            
            for dir_name in writable_dirs:
                dir_path = os.path.join(home_dir, dir_name)
                if not os.path.exists(dir_path):
                    os.makedirs(dir_path, exist_ok=True)
                
                # Make directory writable by user
                os.chmod(dir_path, 0o755)
                os.chown(dir_path, uid, gid)
                
                # Create a .keep file to ensure directory exists
                keep_file = os.path.join(dir_path, '.keep')
                if not os.path.exists(keep_file):
                    with open(keep_file, 'w') as f:
                        f.write('This file keeps the directory in version control\n')
                    os.chown(keep_file, uid, gid)
                    os.chmod(keep_file, 0o644)
            
        except Exception as e:
            print(f"Warning: Could not fix chroot permissions: {e}")
    
    @staticmethod
    def fix_user_permissions(username):
        """Fix permissions for an existing user"""
        try:
            if not FTPUserService.check_user_exists(username):
                return False, f"User {username} does not exist"
            
            user_info = pwd.getpwnam(username)
            home_dir = user_info.pw_dir
            uid = user_info.pw_uid
            gid = user_info.pw_gid
            
            # Fix permissions
            FTPUserService._fix_chroot_permissions(home_dir, uid, gid)
            
            return True, f"Permissions fixed for user {username}"
            
        except Exception as e:
            return False, f"Error fixing permissions: {str(e)}"
    
    @staticmethod
    def test_user_write_access(username):
        """Test if user has write access"""
        try:
            if not FTPUserService.check_user_exists(username):
                return False, "User does not exist"
            
            user_info = pwd.getpwnam(username)
            home_dir = user_info.pw_dir
            
            # Test write access in various directories
            test_results = {}
            test_dirs = ['uploads', 'downloads', 'public', '.']
            
            for test_dir in test_dirs:
                dir_path = os.path.join(home_dir, test_dir) if test_dir != '.' else home_dir
                test_file = os.path.join(dir_path, f'.write_test_{username}')
                
                try:
                    # Try to create a test file
                    with open(test_file, 'w') as f:
                        f.write('write test')
                    
                    # Check if file was created and is writable
                    if os.path.exists(test_file):
                        os.remove(test_file)  # Clean up
                        test_results[test_dir] = True
                    else:
                        test_results[test_dir] = False
                        
                except Exception as e:
                    test_results[test_dir] = False
            
            return True, test_results
            
        except Exception as e:
            return False, f"Error testing write access: {str(e)}"
    
    # ... (keep all other existing methods the same)
    
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
                # Create database entry if it doesn't exist
                try:
                    user_info = pwd.getpwnam(username)
                    FTPUser.create(
                        username=username,
                        home_directory=user_info.pw_dir,
                        is_blocked=True,
                        is_active=True
                    )
                except:
                    pass
            
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
                pass
            
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