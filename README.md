
# FTPMAN | VSFTPD Manager Console
FTPMAN is a solution to manage VSFTPD 
# Features
- User Modification
- Quota check
- Connections Management

# Security Considerations

- Change Default Password: Always change the default admin password
- Firewall: Restrict access to management port 
- SSL/TLS: Consider enabling FTPS in production
- User Permissions: Regularly audit FTP user permissions
- Log Monitoring: Monitor logs for suspicious activity
### Structure

```
/opt/vsftpd-manager/
├── app.py                 # Main application
├── models.py              # Database models
├── auth.py                # Authentication module
├── services/              # Service layer
│   ├── ftp_user_service.py
│   ├── ftp_log_service.py
│   ├── ftp_connection_service.py
│   ├── ftp_config_service.py
│   └── quota_service.py
├── templates/             # HTML templates
│   ├── dashboard.html
│   ├── quota.html
│   
├── static/               # Static files (CSS, JS)
├── venv/                 # Python virtual environment
├── setup.sh              # Installation script
└── README.md             # This file
```
# Installation
- Easy install:   ./setup.sh
*** default path considered /etc/vsftpd/vsftpd.conf in some distros you need to replace it with the actual conf path

# 
## 🚀 About Developer
Developed by AMIR AHMADABADIHA

follow me on [LinkedIn](https://www.linkedin.com/in/amir-ahmadabadiha-259113175/)

Use My free Online [Storage](https://filesaver.ir)


