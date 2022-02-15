
# -*- coding: utf-8 -*-

from flask import Flask
from flask_login import LoginManager
from flask_migrate import Migrate

from auth import auth as auth_blueprint
from config import DB_ENABLE, DB_URI
from main import main as main_blueprint
from model import db, User

app = Flask(__name__)
app.secret_key = "d5ff7c15-6134-4de9-a88b-6e9edece3739"

# init SQLAlchemy so we can use it later in our models
app.config["SQLALCHEMY_DATABASE_URI"] = DB_URI
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = True

db.init_app(app)
migrate = Migrate(app, db)

# blueprint for auth routes in our app
app.register_blueprint(auth_blueprint, url_prefix="/treasure")

# blueprint for non-auth parts of app
app.register_blueprint(main_blueprint, url_prefix="/treasure")

login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.init_app(app)
login_manager.login_message = ""


@login_manager.user_loader
def load_user(user_id):
    # since the user_id is just the primary key of our user table, use it in the query for the user
    if DB_ENABLE:
        return User.query.get(int(user_id))
    else:
        return 1


if __name__ == "__main__":
    # db.create_all(app=app)  # pass the create_app result so Flask-SQLAlchemy gets the configuration.
    app.run(host="0.0.0.0", port=12345, threaded=True, debug=True)
