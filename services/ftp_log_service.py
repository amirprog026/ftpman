import os
import re
from datetime import datetime
from models import FTPLog, db

class FTPLogService:
    VSFTPD_LOG_FILE = '/var/log/vsftpd.log'
    XFERLOG_FILE = '/var/log/xferlog'
    
    @staticmethod
    def get_recent_logs(limit=100):
        """Get recent FTP logs"""
        logs = []
        
        # Try to read from vsftpd.log
        if os.path.exists(FTPLogService.VSFTPD_LOG_FILE):
            logs.extend(FTPLogService._parse_vsftpd_log(limit))
        
        # Try to read from xferlog (transfer log)
        if os.path.exists(FTPLogService.XFERLOG_FILE):
            logs.extend(FTPLogService._parse_xfer_log(limit))
        
        # Sort by timestamp and limit
        logs.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        return logs[:limit]
    
    @staticmethod
    def _parse_vsftpd_log(limit=50):
        """Parse vsftpd.log file"""
        logs = []
        try:
            with open(FTPLogService.VSFTPD_LOG_FILE, 'r') as f:
                lines = f.readlines()
                
            # Get last N lines
            recent_lines = lines[-limit:] if len(lines) > limit else lines
            
            for line in recent_lines:
                line = line.strip()
                if not line:
                    continue
                
                # Parse different log formats
                log_entry = FTPLogService._parse_log_line(line)
                if log_entry:
                    logs.append(log_entry)
                    
        except Exception as e:
            print(f"Error reading vsftpd log: {e}")
            
        return logs
    
    @staticmethod
    def _parse_xfer_log(limit=50):
        """Parse xferlog (transfer log) file"""
        logs = []
        try:
            with open(FTPLogService.XFERLOG_FILE, 'r') as f:
                lines = f.readlines()
                
            # Get last N lines
            recent_lines = lines[-limit:] if len(lines) > limit else lines
            
            for line in recent_lines:
                line = line.strip()
                if not line:
                    continue
                
                # Parse xferlog format
                log_entry = FTPLogService._parse_xfer_line(line)
                if log_entry:
                    logs.append(log_entry)
                    
        except Exception as e:
            print(f"Error reading xfer log: {e}")
            
        return logs
    
    @staticmethod
    def _parse_log_line(line):
        """Parse a single log line from vsftpd.log"""
        try:
            # Common vsftpd log patterns
            patterns = [
                # Login pattern: Mon Dec 4 10:30:15 2023 [pid 1234] [user] OK LOGIN: Client "192.168.1.100"
                r'(\w+\s+\w+\s+\d+\s+\d+:\d+:\d+\s+\d+)\s+\[pid\s+(\d+)\]\s+\[([^\]]+)\]\s+(\w+)\s+(\w+):\s+(.+)',
                # Connection pattern: Mon Dec 4 10:30:15 2023 [pid 1234] CONNECT: Client "192.168.1.100"
                r'(\w+\s+\w+\s+\d+\s+\d+:\d+:\d+\s+\d+)\s+\[pid\s+(\d+)\]\s+(\w+):\s+(.+)',
                # Generic pattern
                r'(\w+\s+\w+\s+\d+\s+\d+:\d+:\d+\s+\d+)\s+(.+)'
            ]
            
            for pattern in patterns:
                match = re.match(pattern, line)
                if match:
                    groups = match.groups()
                    
                    if len(groups) >= 6:  # Full pattern
                        return {
                            'timestamp': groups[0],
                            'pid': groups[1],
                            'username': groups[2],
                            'status': groups[3],
                            'action': groups[4],
                            'details': groups[5],
                            'ip_address': FTPLogService._extract_ip(groups[5])
                        }
                    elif len(groups) >= 4:  # Connection pattern
                        return {
                            'timestamp': groups[0],
                            'pid': groups[1],
                            'username': 'unknown',
                            'status': 'INFO',
                            'action': groups[2],
                            'details': groups[3],
                            'ip_address': FTPLogService._extract_ip(groups[3])
                        }
                    elif len(groups) >= 2:  # Generic pattern
                        return {
                            'timestamp': groups[0],
                            'pid': 'unknown',
                            'username': 'unknown',
                            'status': 'INFO',
                            'action': 'LOG',
                            'details': groups[1],
                            'ip_address': FTPLogService._extract_ip(groups[1])
                        }
            
            # If no pattern matches, return basic entry
            return {
                'timestamp': datetime.now().strftime('%a %b %d %H:%M:%S %Y'),
                'pid': 'unknown',
                'username': 'unknown',
                'status': 'INFO',
                'action': 'LOG',
                'details': line,
                'ip_address': FTPLogService._extract_ip(line)
            }
            
        except Exception as e:
            return None
    
    @staticmethod
    def _parse_xfer_line(line):
        """Parse xferlog format line"""
        try:
            # xferlog format: DDD MMM dd hh:mm:ss YYYY n hostname filesize filename b _ o r username ftp 0 * c
            parts = line.split()
            if len(parts) >= 14:
                return {
                    'timestamp': ' '.join(parts[:5]),
                    'pid': 'xfer',
                    'username': parts[13] if parts[13] != '*' else 'anonymous',
                    'status': 'OK',
                    'action': 'TRANSFER',
                    'details': f"File: {parts[8]}, Size: {parts[7]} bytes",
                    'ip_address': parts[6]
                }
        except Exception:
            pass
        return None
    
    @staticmethod
    def _extract_ip(text):
        """Extract IP address from log text"""
        ip_pattern = r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b'
        match = re.search(ip_pattern, text)
        return match.group(0) if match else 'unknown'
    
    @staticmethod
    def sync_logs_to_db():
        """Sync recent logs to database (optional)"""
        try:
            recent_logs = FTPLogService.get_recent_logs(50)
            
            for log_data in recent_logs:
                # Check if log entry already exists
                existing = FTPLog.select().where(
                    (FTPLog.timestamp == log_data['timestamp']) &
                    (FTPLog.username == log_data['username']) &
                    (FTPLog.action == log_data['action'])
                ).exists()
                
                if not existing:
                    FTPLog.create(
                        timestamp=log_data['timestamp'],
                        username=log_data['username'],
                        action=log_data['action'],
                        ip_address=log_data['ip_address'],
                        status=log_data['status'],
                        details=log_data['details']
                    )
                    
        except Exception as e:
            print(f"Error syncing logs to database: {e}")
    
    @staticmethod
    def get_log_stats():
        """Get log statistics"""
        try:
            logs = FTPLogService.get_recent_logs(1000)
            
            stats = {
                'total_entries': len(logs),
                'successful_logins': len([l for l in logs if 'LOGIN' in l.get('action', '') and l.get('status') == 'OK']),
                'failed_logins': len([l for l in logs if 'LOGIN' in l.get('action', '') and l.get('status') != 'OK']),
                'transfers': len([l for l in logs if 'TRANSFER' in l.get('action', '')]),
                'unique_ips': len(set([l.get('ip_address') for l in logs if l.get('ip_address') != 'unknown']))
            }
            
            return stats
        except Exception as e:
            return {'error': str(e)}