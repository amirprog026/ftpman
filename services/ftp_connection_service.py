import psutil
import subprocess
from models import FTPConnection, db
from datetime import datetime

class FTPConnectionService:
    @staticmethod
    def get_active_connections():
        """Get active FTP connections using netstat and ps"""
        connections = []
        try:
            # Get vsftpd processes
            for proc in psutil.process_iter(['pid', 'name', 'username', 'create_time']):
                if proc.info['name'] == 'vsftpd':
                    # Get connection info
                    netstat_output = subprocess.check_output(
                        ['sudo', 'netstat', '-tnp'], 
                        universal_newlines=True
                    )
                    
                    for line in netstat_output.split('\n'):
                        if str(proc.info['pid']) in line and ':21' in line:
                            parts = line.split()
                            if len(parts) >= 5:
                                remote_addr = parts[4].split(':')[0]
                                
                                conn = {
                                    'pid': proc.info['pid'],
                                    'username': proc.info['username'],
                                    'ip_address': remote_addr,
                                    'connected_at': datetime.fromtimestamp(proc.info['create_time'])
                                }
                                connections.append(conn)
                                
        except Exception as e:
            print(f"Error getting connections: {str(e)}")
            
        return connections
    
    @staticmethod
    def update_connections():
        """Update connection records in database"""
        # Mark all as inactive
        FTPConnection.update(is_active=False).execute()
        
        # Get current connections
        active_conns = FTPConnectionService.get_active_connections()
        
        for conn in active_conns:
            FTPConnection.create(
                username=conn['username'],
                ip_address=conn['ip_address'],
                connected_at=conn['connected_at'],
                pid=conn['pid'],
                is_active=True
            )
    
    @staticmethod
    def kill_connection(pid):
        """Kill a specific FTP connection"""
        try:
            subprocess.run(['sudo', 'kill', str(pid)], check=True)
            return True, "Connection terminated"
        except subprocess.CalledProcessError as e:
            return False, f"Error terminating connection: {str(e)}"