
# -*- coding: utf-8 -*-

from flask import Blueprint, render_template, redirect, request, send_file, url_for
from flask_login import current_user
from werkzeug.utils import secure_filename

import datetime
import json
import os
import uuid

from auth import login_required
from config import ROOT_FOLDER
from model import db, Token

main = Blueprint("main", __name__)


@main.route("/")
def root_page():
    return redirect(url_for("main.index"))


@main.route('/favicon.ico')
def favicon():
    return send_file("static/favicon.ico", mimetype='image/vnd.microsoft.icon')


@main.route("/treasure")
@login_required(10)
def index():
    return render_template("index.html")


@main.route("/profile")
@login_required(10)
def profile():
    return render_template("auth/profile.html", name=current_user.name)


@main.route("/file_tree", methods=["GET"])
@login_required(10)
def file_tree():
    if request.method == "GET":
        root_folder = ROOT_FOLDER.rstrip("/")
        tree = {
            "type": "dir",
            "name": "/",
            "path": "/",
            "sub": dict()
        }
        for root, dirs, files in os.walk(root_folder):
            # print root
            root = root.replace("\\", "/")
            # if "venv" in root or ".idea" in root or "plugins" in root:
            #     continue

            root = root.replace(ROOT_FOLDER, "", 1)
            path_list = list()
            if "/" in root:
                path_list = root.split("/")[1:]

            sub_tree = tree
            for p in path_list:
                sub_tree = sub_tree["sub"][p]
            for d in sorted(dirs):
                # if "venv" in d or ".idea" in d or "plugins" in d:
                #     continue
                sub_tree["sub"][d] = {
                    "type": "dir",
                    "name": d,
                    "path": sub_tree["path"] + d + "/",
                    "sub": dict()
                }
            for f in sorted(files):
                sub_tree["sub"][f] = {
                    "type": "file",
                    "path": sub_tree["path"] + f,
                    "name": f,
                }
        return json.dumps(tree)


@main.route("/file_api", methods=["GET", "POST", "PUT"])
@login_required(10)
def file_api():
    if request.method == "GET":
        file_path = request.args.get("file_path")
        token = request.args.get("token")
        now = datetime.datetime.now()
        if token is None:
            token = Token.query.filter_by(user_id=current_user.id, file_path=file_path).first()
            if not token or token.effective_time + datetime.timedelta(hours=token.shelf_life) < now:
                token = Token(token_id=uuid.uuid4().hex,
                              file_path=file_path,
                              effective_time=now,
                              user_id=current_user.id)
                db.session.add(token)
                db.session.commit()

            return "/preview?" + "&".join([
                # "file_path=" + file_path,
                "token=" + token.token_id,
            ])
        elif token == "":
            return "Error"
        else:
            token = Token.query.filter_by(token_id=token).first()
            if token is None:
                return "Error"
            if token.use >= token.max_use:
                return "Error"
            if token.effective_time + datetime.timedelta(hours=token.shelf_life) < now:
                return "Error"
            else:
                token.use += 1
                db.session.commit()
                file_path = token.file_path.lstrip("/")
                print ROOT_FOLDER, file_path, os.path.join(ROOT_FOLDER, file_path)
                return send_file(os.path.join(ROOT_FOLDER, file_path), as_attachment=True)
    elif request.method == "POST":
        file_path = request.form.get("file_path").lstrip("/")
        print ROOT_FOLDER, file_path, os.path.join(ROOT_FOLDER, file_path)
        return send_file(os.path.join(ROOT_FOLDER, file_path), as_attachment=True)
    elif request.method == "PUT":
        file_path = request.form.get("file_path").lstrip("/")
        upload_file = request.files.get("upload_file")
        print ROOT_FOLDER, file_path, upload_file.filename
        filename = secure_filename(upload_file.filename)
        if os.path.exists(os.path.join(ROOT_FOLDER, file_path, filename)):
            duplicate = 2
            extension = ""
            if "." in filename:
                extension = filename.split(".")[-1]
                filename = ".".join(filename.split(".")[:-1])
            while os.path.exists(
                    os.path.join(ROOT_FOLDER, file_path, "{}({}).{}".format(filename, duplicate, extension))):
                duplicate += 1
            filename = "{}({}).{}".format(filename, duplicate, extension)
        upload_file.save(os.path.join(ROOT_FOLDER, file_path, filename))
        return "OK"


@main.route("/preview")
@login_required(10)
def preview():
    token = request.args.get("token", "")
    token = Token.query.filter_by(token_id=token).first()
    if token is None:
        return "Error"
    if token.file_path.split(".")[-1] in ["jpg", "png"]:
        return render_template("image.html",
                               filename=token.file_path.split("/")[-1],
                               token=token.token_id)
    if token.file_path.split(".")[-1] in ["mp4"]:
        return render_template("video.html",
                               filename=token.file_path.split("/")[-1],
                               token=token.token_id)
