from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import random

db = SQLAlchemy()

# สร้างรหัสโครงการ (8 หลัก ตัวแรกไม่ใช่ 0)
def gen_project_id():
    first = str(random.randint(1, 9))
    rest = "".join(str(random.randint(0, 9)) for _ in range(7))
    return first + rest

# ---------------- Models ----------------
class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)

    pledges = db.relationship('Pledge', backref='user', lazy=True)

class Category(db.Model):
    __tablename__ = 'categories'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False, unique=True)

    projects = db.relationship('Project', backref='category', lazy=True)

class Project(db.Model):
    __tablename__ = 'projects'
    id = db.Column(db.String(8), primary_key=True, default=gen_project_id)  # 8 หลัก
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False, default="")
    goal_amount = db.Column(db.Integer, nullable=False)   # > 0
    current_amount = db.Column(db.Integer, default=0)
    deadline = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)  # ใหม่สุดใช้ field นี้
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=False)

    reward_tiers = db.relationship('RewardTier', backref='project', lazy=True)
    pledges = db.relationship('Pledge', backref='project', lazy=True)

class RewardTier(db.Model):
    __tablename__ = 'reward_tiers'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    project_id = db.Column(db.String(8), db.ForeignKey('projects.id'), nullable=False)
    description = db.Column(db.String(200), nullable=False)
    min_amount = db.Column(db.Integer, nullable=False)
    qty_remaining = db.Column(db.Integer, nullable=True)  # None = unlimited

    pledges = db.relationship('Pledge', backref='reward_tier', lazy=True)

class Pledge(db.Model):
    __tablename__ = 'pledges'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    project_id = db.Column(db.String(8), db.ForeignKey('projects.id'), nullable=False)
    reward_tier_id = db.Column(db.Integer, db.ForeignKey('reward_tiers.id'), nullable=True)

    amount = db.Column(db.Integer, nullable=False)
    time = db.Column(db.DateTime, default=datetime.utcnow)
    accepted = db.Column(db.Boolean, default=False)
    rejected_reason = db.Column(db.String(200), nullable=True)
