from .extensions import db
from datetime import datetime, date
from werkzeug.security import generate_password_hash, check_password_hash

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    pontos = db.Column(db.Integer, default=0, index=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    streak_count = db.Column(db.Integer, nullable=False, server_default='0')
    last_active_date = db.Column(db.Date, nullable=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            'id': self.id,
            'nome': self.nome,
            'email': self.email,
            'pontos': self.pontos,
            'streak_count': self.streak_count,
            'last_active_date': self.last_active_date.isoformat() if self.last_active_date else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
