import re
from datetime import datetime
from models import FTPLog, db

class FTPLogService:
    LOG_FILE = '/var/log/vsftpd.log'
    
    @staticmethod
    def parse_log_line(line):
        """Parse vsftpd log line"""
        # Example: Thu Jun 03 10:30:45 2025 [pid 2] [user1] OK LOGIN: Client "192.168.1.100"
        pattern = r'(\w+ \w+ \d+ \d+:\d+:\d+ \d+) \[pid \d+\] \[([^\]]*)\] (\w+) ([^:]+): (.+)'
        match = re.match(pattern, line)
        
        if match:
            timestamp_str, username, status, action, details = match.groups()
            timestamp = datetime.strptime(timestamp_str, '%a %b %d %H:%M:%S %Y')
            
            # Extract IP if present
            ip_match = re.search(r'Client "([^"]+)"', details)
            ip_address = ip_match.group(1) if ip_match else 'Unknown'
            
            return {
                'timestamp': timestamp,
                'username': username,
                'status': status,
                'action': action,
                'ip_address': ip_address,
                'details': details
            }
        return None
    
    @staticmethod
    def get_recent_logs(limit=100):
        """Get recent logs from vsftpd log file"""
        logs = []
        try:
            with open(FTPLogService.LOG_FILE, 'r') as f:
                lines = f.readlines()[-limit:]
                
            for line in lines:
                parsed = FTPLogService.parse_log_line(line.strip())
                if parsed:
                    logs.append(parsed)
                    
        except Exception as e:
            print(f"Error reading logs: {str(e)}")
            
        return logs
    
    @staticmethod
    def sync_logs_to_db():
        """Sync log file entries to database"""
        recent_logs = FTPLogService.get_recent_logs(500)
        
        for log in recent_logs:
            FTPLog.get_or_create(
                timestamp=log['timestamp'],
                username=log['username'],
                action=log['action'],
                ip_address=log['ip_address'],
                status=log['status']
            )