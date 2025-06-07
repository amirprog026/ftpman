from peewee import *
from flask_login import UserMixin
from datetime import datetime
import hashlib

db = SqliteDatabase('vsftpd_manager.db')

class BaseModel(Model):
    class Meta:
        database = db

class User(BaseModel, UserMixin):
    username = CharField(unique=True)
    password_hash = CharField()
    email = CharField(unique=True)
    is_admin = BooleanField(default=False)
    created_at = DateTimeField(default=datetime.now)
    
    def set_password(self, password):
        self.password_hash = hashlib.sha256(password.encode()).hexdigest()
    
    def check_password(self, password):
        return self.password_hash == hashlib.sha256(password.encode()).hexdigest()

class FTPUser(BaseModel):
    username = CharField(unique=True)
    home_directory = CharField()
    is_active = BooleanField(default=True)
    is_blocked = BooleanField(default=False)
    created_at = DateTimeField(default=datetime.now)
    created_by = ForeignKeyField(User, backref='ftp_users')

class FTPLog(BaseModel):
    timestamp = DateTimeField()
    username = CharField()
    action = CharField()
    ip_address = CharField()
    file_path = CharField(null=True)
    status = CharField()
    created_at = DateTimeField(default=datetime.now)

class FTPConnection(BaseModel):
    username = CharField()
    ip_address = CharField()
    connected_at = DateTimeField()
    pid = IntegerField()
    is_active = BooleanField(default=True)

class ConfigChange(BaseModel):
    config_key = CharField()
    old_value = TextField(null=True)
    new_value = TextField()
    changed_by = ForeignKeyField(User, backref='config_changes')
    changed_at = DateTimeField(default=datetime.now)

def create_tables():
    with db:
        db.create_tables([User, FTPUser, FTPLog, FTPConnection, ConfigChange])