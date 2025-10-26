from .extensions import db
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.sql import func

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    pontos = db.Column(db.Integer, default=0, index=True)
    created_at = db.Column(db.DateTime, server_default=func.now())
    streak_count = db.Column(db.Integer, default=0, nullable=False, index=True)
    last_active_date = db.Column(db.Date, nullable=True, index=True)

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
        
class Achievement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(255), nullable=False)
    icon = db.Column(db.String(50), nullable=True)
    goal = db.Column(db.Integer, nullable=True)
    points_reward = db.Column(db.Integer, default=0)

    def to_dict(self):
        return {
            'id': self.id,
            'code': self.code,
            'title': self.title,
            'description': self.description,
            'icon': self.icon,
            'goal': self.goal,
            'points_reward': self.points_reward
        }

class UserAchievement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    achievement_id = db.Column(db.Integer, db.ForeignKey('achievement.id'), nullable=False, index=True)
    progress = db.Column(db.Integer, default=0)
    unlocked_at = db.Column(db.DateTime, nullable=True)

    user = db.relationship('User', backref=db.backref('user_achievements', lazy=True))
    achievement = db.relationship('Achievement', backref=db.backref('user_achievements', lazy=True))

    __table_args__ = (db.UniqueConstraint('user_id', 'achievement_id', name='uq_user_achievement'),)

    def to_dict(self, achievement_data=None):
        ach_data = achievement_data or self.achievement.to_dict()
        return {
            'user_id': self.user_id,
            'achievement_id': self.achievement_id,
            'progress': self.progress,
            'unlocked': self.unlocked_at is not None,
            'unlocked_at': self.unlocked_at.isoformat() if self.unlocked_at else None,
            **ach_data
        }
        
class Measurement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    
    value = db.Column(db.Float, nullable=False)
    date = db.Column(db.DateTime(timezone=True), nullable=False)
    note = db.Column(db.Text, nullable=True)
    
    local_id = db.Column(db.String(100), nullable=True, index=True)

    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())

    user = db.relationship('User', backref=db.backref('measurements', lazy='dynamic'))

    def __repr__(self):
        return f'<Measurement {self.id} (User {self.user_id})>'