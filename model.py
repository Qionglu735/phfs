
# -*- coding: utf-8 -*-

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)  # primary keys are required by SQLAlchemy
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    name = db.Column(db.String(1000))
    auth = db.Column(db.Integer, default=0)
    token = db.relationship("Token")


class Token(db.Model):
    id = db.Column(db.Integer, primary_key=True)  # primary keys are required by SQLAlchemy
    token_id = db.Column(db.String(64), unique=True)
    file_path = db.Column(db.String(1000))
    effective_time = db.Column(db.DateTime)
    shelf_life = db.Column(db.Integer, default=1)
    use = db.Column(db.Integer, default=0)
    max_use = db.Column(db.Integer, default=10)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
