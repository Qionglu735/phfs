
# -*- coding: utf-8 -*-

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_user, logout_user
from flask_login import login_required as _login_required
from werkzeug.security import check_password_hash, generate_password_hash

import functools

from config import DB_ENABLE
from model import db, User

auth = Blueprint("auth", __name__)


@auth.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("auth/login.html")
    elif request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        remember = True if request.form.get("remember") else False

        user = User.query.filter_by(email=email).first()

        # check if the user actually exists
        # take the user-supplied password, hash it, and compare it to the hashed password in the database
        if not user or not check_password_hash(user.password, password):
            flash("Please check your login details and try again.")
            return redirect(url_for("auth.login"))  # if the user doesn't exist or password is wrong, reload the page

        # if the above check passes, then we know the user has the right credentials
        login_user(user, remember=remember)
        return redirect(session["last_url"] or default_page())


@auth.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "GET":
        return render_template("auth/signup.html")
    elif request.method == "POST":
        email = request.form.get("email")
        name = request.form.get("name")
        password = request.form.get("password")

        user = User.query.filter_by(
            email=email).first()  # if this returns a user, then the email already exists in database

        if user:  # if a user is found, we want to redirect back to signup page so user can try again
            return redirect(url_for("auth.signup"))

        # create a new user with the form data. Hash the password so the plaintext version isn"t saved.
        new_user = User(email=email, name=name, password=generate_password_hash(password), auth=1)

        # add the new user to the database
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for("auth.login"))


@auth.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("main.index"))


def default_page():
    return url_for("main.index")


def access_denied():
    return "Access Denied."


def login_required(auth_level=1):
    def decorate(f):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            session["last_url"] = request.url

            if DB_ENABLE:
                @_login_required  # from flask_login import login_required as _login_required
                def inner(*_args, **_kwargs):
                    if current_user.auth < auth_level:
                        return access_denied()
                    return f(*_args, **_kwargs)
                return inner(*args, **kwargs)
            else:
                return f(*args, **kwargs)
        return wrapper
    return decorate
