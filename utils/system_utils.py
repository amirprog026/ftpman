import subprocess
import os
import psutil
from typing import List, Dict, Tuple

class SystemUtils:
    @staticmethod
    def run_command(command: List[str], check: bool = True) -> Tuple[bool, str]:
        """Run system command safely"""
        try:
            result = subprocess.run(
                command, 
                capture_output=True, 
                text=True, 
                check=check
            )
            return True, result.stdout.strip()
        except subprocess.CalledProcessError as e:
            return False, e.stderr.strip()
        except Exception as e:
            return False, str(e)
    
    @staticmethod
    def is_service_running(service_name: str) -> bool:
        """Check if a system service is running"""
        success, output = SystemUtils.run_command([
            'systemctl', 'is-active', service_name
        ], check=False)
        return success and output == 'active'
    
    @staticmethod
    def restart_service(service_name: str) -> Tuple[bool, str]:
        """Restart a system service"""
        return SystemUtils.run_command([
            'sudo', 'systemctl', 'restart', service_name
        ])
    
    @staticmethod
    def get_service_status(service_name: str) -> Dict:
        """Get detailed service status"""
        status = {
            'active': False,
            'enabled': False,
            'uptime': None,
            'memory_usage': 0,
            'cpu_usage': 0
        }
        
        # Check if active
        status['active'] = SystemUtils.is_service_running(service_name)
        
        # Check if enabled
        success, output = SystemUtils.run_command([
            'systemctl', 'is-enabled', service_name
        ], check=False)
        status['enabled'] = success and output == 'enabled'
        
        # Get process info
        try:
            for proc in psutil.process_iter(['pid', 'name', 'memory_info', 'cpu_percent', 'create_time']):
                if proc.info['name'] == service_name:
                    status['memory_usage'] = proc.info['memory_info'].rss / 1024 / 1024  # MB
                    status['cpu_usage'] = proc.info['cpu_percent']
                    break
        except Exception:
            pass
        
        return status
    
    @staticmethod
    def backup_file(file_path: str) -> Tuple[bool, str]:
        """Create backup of a file"""
        try:
            backup_path = f"{file_path}.backup"
            success, output = SystemUtils.run_command([
                'sudo', 'cp', file_path, backup_path
            ])
            return success, backup_path if success else output
        except Exception as e:
            return False, str(e)
    
    @staticmethod
    def get_disk_usage(path: str = '/') -> Dict:
        """Get disk usage information"""
        try:
            usage = psutil.disk_usage(path)
            return {
                'total': usage.total,
                'used': usage.used,
                'free': usage.free,
                'percent': (usage.used / usage.total) * 100
            }
        except Exception:
            return {'total': 0, 'used': 0, 'free': 0, 'percent': 0}
    
    @staticmethod
    def get_memory_usage() -> Dict:
        """Get system memory usage"""
        try:
            memory = psutil.virtual_memory()
            return {
                'total': memory.total,
                'available': memory.available,
                'used': memory.used,
                'percent': memory.percent
            }
        except Exception:
            return {'total': 0, 'available': 0, 'used': 0, 'percent': 0}