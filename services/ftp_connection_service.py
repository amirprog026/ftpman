import subprocess
import psutil
import re
from datetime import datetime
from models import FTPConnection, db

class FTPConnectionService:
    
    @staticmethod
    def get_active_connections():
        """Get currently active FTP connections with proper username detection"""
        connections = []
        
        try:
            # Method 1: Parse vsftpd log for active sessions
            log_connections = FTPConnectionService._get_connections_from_logs()
            connections.extend(log_connections)
            
            # Method 2: Use netstat with process info
            netstat_connections = FTPConnectionService._get_connections_netstat()
            connections.extend(netstat_connections)
            
            # Method 3: Parse vsftpd processes
            process_connections = FTPConnectionService._get_connections_from_processes()
            connections.extend(process_connections)
            
            # Remove duplicates and merge information
            unique_connections = FTPConnectionService._merge_connection_data(connections)
            
            return unique_connections
            
        except Exception as e:
            print(f"Error getting connections: {e}")
            return []
    
    @staticmethod
    def _get_connections_from_logs():
        """Extract active connections from vsftpd logs"""
        connections = []
        try:
            log_file = '/var/log/vsftpd.log'
            if not os.path.exists(log_file):
                return connections
            
            # Read recent log entries
            with open(log_file, 'r') as f:
                lines = f.readlines()
            
            # Look for recent LOGIN entries without corresponding logout
            recent_logins = {}
            
            # Process last 100 lines to find active sessions
            for line in lines[-100:]:
                # Parse login entries
                login_match = re.search(r'\[pid\s+(\d+)\]\s+\[([^\]]+)\]\s+OK\s+LOGIN:', line)
                if login_match:
                    pid = login_match.group(1)
                    username = login_match.group(2)
                    
                    # Extract IP address
                    ip_match = re.search(r'Client\s+"([^"]+)"', line)
                    ip_address = ip_match.group(1) if ip_match else 'unknown'
                    
                    # Extract timestamp
                    time_match = re.search(r'^(\w+\s+\w+\s+\d+\s+\d+:\d+:\d+\s+\d+)', line)
                    timestamp = time_match.group(1) if time_match else datetime.now().strftime('%a %b %d %H:%M:%S %Y')
                    
                    recent_logins[pid] = {
                        'pid': int(pid),
                        'username': username,
                        'ip_address': ip_address,
                        'connected_at': timestamp,
                        'status': 'ACTIVE',
                        'source': 'log'
                    }
                
                # Look for logout/disconnect entries to remove from active list
                logout_match = re.search(r'\[pid\s+(\d+)\].*(?:LOGOUT|FTP session closed)', line)
                if logout_match:
                    pid = logout_match.group(1)
                    if pid in recent_logins:
                        del recent_logins[pid]
            
            # Check if PIDs are still active
            for pid_str, conn_info in recent_logins.items():
                try:
                    # Check if process still exists
                    proc = psutil.Process(int(pid_str))
                    if proc.is_running():
                        connections.append(conn_info)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    # Process no longer exists
                    continue
                    
        except Exception as e:
            print(f"Error parsing logs for connections: {e}")
            
        return connections
    
    @staticmethod
    def _get_connections_netstat():
        """Get connections using netstat with enhanced username detection"""
        connections = []
        try:
            # Get FTP connections on port 21
            result = subprocess.run([
                'netstat', '-tnp'
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                lines = result.stdout.split('\n')
                for line in lines:
                    if ':21 ' in line and 'ESTABLISHED' in line:
                        parts = line.split()
                        if len(parts) >= 7:
                            local_addr = parts[3]
                            foreign_addr = parts[4]
                            pid_program = parts[6] if len(parts) > 6 else ''
                            
                            # Extract PID
                            pid_match = re.search(r'(\d+)/', pid_program)
                            if pid_match:
                                pid = int(pid_match.group(1))
                                
                                # Extract IP
                                ip_match = re.search(r'([0-9.]+):', foreign_addr)
                                ip = ip_match.group(1) if ip_match else 'unknown'
                                
                                # Get username from process or log correlation
                                username = FTPConnectionService._get_username_for_connection(pid, ip)
                                
                                connections.append({
                                    'pid': pid,
                                    'ip_address': ip,
                                    'username': username,
                                    'connected_at': datetime.now().isoformat(),
                                    'local_address': local_addr,
                                    'remote_address': foreign_addr,
                                    'status': 'ESTABLISHED',
                                    'source': 'netstat'
                                })
                                
        except Exception as e:
            print(f"Error with netstat: {e}")
            
        return connections
    
    @staticmethod
    def _get_connections_from_processes():
        """Get connections by analyzing vsftpd processes"""
        connections = []
        try:
            # Find all vsftpd processes
            for proc in psutil.process_iter(['pid', 'name', 'username', 'create_time', 'connections', 'cmdline']):
                try:
                    if 'vsftpd' in proc.info['name'].lower():
                        pid = proc.info['pid']
                        
                        # Skip the main vsftpd process (usually has no connections)
                        proc_connections = proc.info.get('connections', [])
                        if not proc_connections:
                            continue
                        
                        # Look for established connections on port 21
                        for conn in proc_connections:
                            if (hasattr(conn, 'status') and 
                                conn.status == psutil.CONN_ESTABLISHED and 
                                hasattr(conn, 'laddr') and 
                                conn.laddr.port == 21):
                                
                                ip_address = conn.raddr.ip if hasattr(conn, 'raddr') and conn.raddr else 'unknown'
                                
                                # Try to get username from log correlation
                                username = FTPConnectionService._get_username_for_connection(pid, ip_address)
                                
                                connections.append({
                                    'pid': pid,
                                    'ip_address': ip_address,
                                    'username': username,
                                    'connected_at': datetime.fromtimestamp(proc.info['create_time']).isoformat(),
                                    'local_address': f"{conn.laddr.ip}:{conn.laddr.port}",
                                    'remote_address': f"{conn.raddr.ip}:{conn.raddr.port}" if hasattr(conn, 'raddr') and conn.raddr else 'unknown',
                                    'status': 'ESTABLISHED',
                                    'source': 'process'
                                })
                                
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
                    
        except Exception as e:
            print(f"Error analyzing processes: {e}")
            
        return connections
    
    @staticmethod
    def _get_username_for_connection(pid, ip_address):
        """Get username for a connection using multiple methods"""
        try:
            # Method 1: Check recent log entries for this PID
            log_file = '/var/log/vsftpd.log'
            if os.path.exists(log_file):
                try:
                    with open(log_file, 'r') as f:
                        lines = f.readlines()
                    
                    # Look for login entries with this PID
                    for line in reversed(lines[-50:]):  # Check last 50 lines
                        if f'[pid {pid}]' in line:
                            # Look for username in brackets
                            username_match = re.search(r'\[pid\s+' + str(pid) + r'\]\s+\[([^\]]+)\]', line)
                            if username_match:
                                return username_match.group(1)
                            
                            # Alternative pattern for LOGIN entries
                            login_match = re.search(r'\[pid\s+' + str(pid) + r'\].*LOGIN.*user\s+(\w+)', line, re.IGNORECASE)
                            if login_match:
                                return login_match.group(1)
                
                except Exception:
                    pass
            
            # Method 2: Check if we can correlate by IP address from recent logs
            if ip_address != 'unknown':
                try:
                    with open(log_file, 'r') as f:
                        lines = f.readlines()
                    
                    # Look for recent logins from this IP
                    for line in reversed(lines[-100:]):
                        if ip_address in line and 'LOGIN' in line:
                            username_match = re.search(r'\[([^\]]+)\]\s+OK\s+LOGIN', line)
                            if username_match:
                                return username_match.group(1)
                
                except Exception:
                    pass
            
            # Method 3: Try to get process owner (may not be the FTP user)
            try:
                proc = psutil.Process(pid)
                proc_username = proc.username()
                # If it's not 'nobody' or 'root', it might be the actual user
                if proc_username not in ['nobody', 'root', 'vsftpd']:
                    return proc_username
            except:
                pass
                
        except Exception as e:
            print(f"Error getting username for PID {pid}: {e}")
        
        return 'unknown'
    
    @staticmethod
    def _merge_connection_data(connections):
        """Merge connection data from different sources"""
        merged = {}
        
        for conn in connections:
            key = f"{conn['pid']}_{conn['ip_address']}"
            
            if key not in merged:
                merged[key] = conn
            else:
                # Merge data, preferring log data for usernames
                existing = merged[key]
                if conn.get('source') == 'log' and existing.get('username') in ['unknown', 'nobody']:
                    existing['username'] = conn['username']
                elif conn.get('username') not in ['unknown', 'nobody'] and existing.get('username') in ['unknown', 'nobody']:
                    existing['username'] = conn['username']
                
                # Update other fields if they're better
                for field in ['local_address', 'remote_address', 'status']:
                    if field in conn and conn[field] != 'unknown':
                        existing[field] = conn[field]
        
        return list(merged.values())
    
    @staticmethod
    def kill_connection(pid):
        """Kill an FTP connection by PID"""
        try:
            # First try to terminate gracefully
            result = subprocess.run(['kill', '-TERM', str(pid)], 
                                  capture_output=True, text=True)
            
            if result.returncode == 0:
                return True, f"Connection {pid} terminated successfully"
            else:
                # Try force kill
                result = subprocess.run(['kill', '-KILL', str(pid)], 
                                      capture_output=True, text=True)
                if result.returncode == 0:
                    return True, f"Connection {pid} force killed"
                else:
                    return False, f"Failed to kill connection {pid}: {result.stderr}"
                    
        except Exception as e:
            return False, f"Error killing connection: {str(e)}"
    
    @staticmethod
    def get_connection_stats():
        """Get connection statistics"""
        try:
            connections = FTPConnectionService.get_active_connections()
            
            stats = {
                'total_active': len(connections),
                'unique_ips': len(set([c.get('ip_address') for c in connections if c.get('ip_address') != 'unknown'])),
                'unique_users': len(set([c.get('username') for c in connections if c.get('username') not in ['unknown', 'nobody']]))
            }
            
            return stats
        except Exception as e:
            return {'error': str(e)}