# -*- coding: utf-8 -*-

from flask import Blueprint, render_template, request, send_file, url_for
from flask_login import current_user

import datetime
import json
import os
import re
import sys
import uuid

from auth import login_required
from config import DB_ENABLE, ROOT_FOLDER, TITLE, UPLOAD_CHUNK_SIZE
from model import db, Token

main = Blueprint("main", __name__)

FOLDER_BLACK_LIST = [r"\..*"]
FILE_BLACK_LIST = [r"\..*"]
EXTENSION_WHITE_LIST = ["tar.gz"]


def encode_print(x):
    if sys.platform == "win32":
        print(x.encode("gbk"))
    else:
        print(x.encode("utf-8"))


@main.route("/")
@login_required(10)
def index():
    return render_template("index.html", title=TITLE, chunk_size=UPLOAD_CHUNK_SIZE)


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
            dirs[:] = [d for d in dirs if len([x for x in FOLDER_BLACK_LIST if re.match(x, d) is not None]) == 0]
            # print root
            root = root.replace("\\", "/")
            # if len([x for x in FOLDER_BLACK_LIST if re.search(x, root) is not None]) > 0:
            #     continue

            root = root.replace(ROOT_FOLDER, "", 1)
            path_list = list()
            if "/" in root:
                path_list = root.split("/")[1:]

            sub_tree = tree
            for p in path_list:
                sub_tree = sub_tree["sub"][p]
            for d in sorted(dirs):
                # if len([x for x in FOLDER_BLACK_LIST if re.search(x, d) is not None]) > 0:
                #     continue
                sub_tree["sub"][d] = {
                    "type": "dir",
                    "name": d,
                    "path": sub_tree["path"] + d + "/",
                    "sub": dict()
                }
            for f in sorted(files):
                if len([x for x in FILE_BLACK_LIST if re.match(x, f) is not None]) > 0:
                    continue
                sub_tree["sub"][f] = {
                    "type": "file",
                    "path": sub_tree["path"] + f,
                    "name": f,
                }
        return json.dumps(tree)


@main.route("/file_api", methods=["GET", "POST", "PUT", "DELETE"])
@login_required(10)
def file_api():
    if request.method == "GET":
        file_path = request.args.get("file_path")
        token = request.args.get("token")
        if token is None:
            if DB_ENABLE:
                token = get_or_create_token(file_path, current_user)
                return url_for("main.preview") + "?" + "&".join([
                    # "file_path=" + file_path,
                    "token=" + token.token_id,
                ])
            else:
                return url_for("main.preview") + "?" + "&".join([
                    # "file_path=" + file_path,
                    "token=" + file_path,
                ])
        else:
            if DB_ENABLE:
                token = use_token(token)
                if isinstance(token, Token):
                    token.use += 1
                    db.session.commit()
                    file_path = token.file_path.lstrip("/")
                    encode_print(u"{} {} {}".format(ROOT_FOLDER, file_path, os.path.join(ROOT_FOLDER, file_path)))
                    return send_file(os.path.join(ROOT_FOLDER, file_path), as_attachment=True)
                else:
                    return render_template("error.html", message=token)
            else:
                file_path = token.lstrip("/")
                encode_print(u"{} {} {}".format(ROOT_FOLDER, file_path, os.path.join(ROOT_FOLDER, file_path)))
                return send_file(os.path.join(ROOT_FOLDER, file_path), as_attachment=True)
    elif request.method == "POST":
        file_path = request.form.get("file_path").lstrip("/")
        encode_print(u"{} {} {}".format(ROOT_FOLDER, file_path, os.path.join(ROOT_FOLDER, file_path)))
        return send_file(os.path.join(ROOT_FOLDER, file_path), as_attachment=True)
    elif request.method == "PUT":
        file_path = request.form.get("file_path").lstrip("/")
        upload_type = request.form.get("type")
        if upload_type == "folder":
            folder_name = request.form.get("folder_name")
            if os.path.exists(os.path.join(ROOT_FOLDER, file_path)):
                if os.path.exists(os.path.join(ROOT_FOLDER, file_path, folder_name)):
                    duplicate = 2
                    while os.path.exists(
                            os.path.join(ROOT_FOLDER, file_path, u"{}({})".format(folder_name, duplicate))):
                        duplicate += 1
                    folder_name = u"{}({})".format(folder_name, duplicate)
                os.mkdir(os.path.join(ROOT_FOLDER, file_path, folder_name))
            return "OK"
        else:
            upload_file = request.files.get("upload_file")
            part_info = request.form.get("part_info")
            part_index, part_total = 0, 0
            if re.match(r"\d+\|\d+", part_info):
                _part_info_list = part_info.split("|")
                part_index = int(_part_info_list[0])
                part_total = int(_part_info_list[1])
            filename = secure_filename(upload_file.filename)
            if os.path.exists(os.path.join(ROOT_FOLDER, file_path, filename)):
                duplicate = 2
                extension = None
                for ext in EXTENSION_WHITE_LIST:
                    if filename.endswith(ext):
                        extension = ext
                        filename = filename[:-len("." + ext)]
                filename_list = filename.split(".")
                if extension is None and len(filename_list) > 1:
                    extension = filename_list[-1]
                    del filename_list[-1]

                def merge_filename():
                    return u"{}({})".format(".".join(filename_list), duplicate) \
                           + ".{}".format(extension) if extension is not None else ""

                while os.path.exists(
                        os.path.join(ROOT_FOLDER, file_path, merge_filename())):
                    duplicate += 1
                filename = merge_filename()
            if part_index > 0:
                filename += u".part{}".format(part_index)
            encode_print(u"PUT {} {} {}".format(ROOT_FOLDER, file_path, filename))
            upload_file.save(os.path.join(ROOT_FOLDER, file_path, filename))
            if 0 < part_total == part_index:
                true_filename = filename[:-len(u".part{}".format(part_total))]
                with open(os.path.join(ROOT_FOLDER, file_path, true_filename), "wb") as f_out:
                    for i in range(1, part_total + 1):
                        part_filename = true_filename + u".part{}".format(i)
                        encode_print(u"MERGE {} {} {}".format(ROOT_FOLDER, file_path, part_filename))
                        with open(os.path.join(ROOT_FOLDER, file_path, part_filename), "rb") as f_in:
                            f_out.write(f_in.read())
                        os.remove(os.path.join(ROOT_FOLDER, file_path, part_filename))
            return "OK"
    elif request.method == "DELETE":
        file_path = request.form.get("file_path").lstrip("/")
        if os.path.exists(os.path.join(ROOT_FOLDER, file_path)):
            encode_print(u"DELETE {}".format(os.path.join(ROOT_FOLDER, file_path)))
            os.remove(os.path.join(ROOT_FOLDER, file_path))
        return "OK"


def secure_filename(x):
    return x.replace(" ", "_")


@main.route("/preview")
@login_required(10)
def preview():
    token = request.args.get("token", "")
    if DB_ENABLE:
        token = check_token(token)
        if isinstance(token, Token):
            if token.file_path.split(".")[-1] in ["jpg", "png"]:
                return render_template("image.html",
                                       filename=token.file_path.split("/")[-1],
                                       token=token.token_id)
            elif token.file_path.split(".")[-1] in ["mp4"]:
                return render_template("video.html",
                                       filename=token.file_path.split("/")[-1],
                                       token=token.token_id)
            else:
                token = use_token(token)
                if isinstance(token, Token):
                    file_path = token.file_path.lstrip("/")
                    encode_print(u"{} {} {}".format(ROOT_FOLDER, file_path, os.path.join(ROOT_FOLDER, file_path)))
                    return send_file(os.path.join(ROOT_FOLDER, file_path))
                else:
                    return render_template("error.html", message=token)
        else:
            return render_template("error.html", message=token)
    else:
        if token.split(".")[-1] in ["jpg", "png"]:
            return render_template("image.html",
                                   filename=token.split("/")[-1],
                                   token=token)
        elif token.split(".")[-1] in ["mp4"]:
            return render_template("video.html",
                                   filename=token.split("/")[-1],
                                   token=token)
        else:
            file_path = token.lstrip("/")
            encode_print(u"{} {} {}".format(ROOT_FOLDER, file_path, os.path.join(ROOT_FOLDER, file_path)))
            return send_file(os.path.join(ROOT_FOLDER, file_path))


def get_or_create_token(file_path, target_user):
    now = datetime.datetime.now()
    token = Token.query.filter_by(user_id=target_user.id, file_path=file_path).first()
    if token is None or token.effective_time + datetime.timedelta(hours=token.shelf_life) < now:
        token = Token(token_id=uuid.uuid4().hex,
                      file_path=file_path,
                      effective_time=now,
                      user_id=current_user.id)
        db.session.add(token)
        db.session.commit()
    return token


def check_token(token):
    now = datetime.datetime.now()
    if not isinstance(token, Token):
        token = Token.query.filter_by(token_id=token).first()
    if token is None:
        return "Not exists"
    elif token.use >= token.max_use:
        return "Out of use"
    elif token.effective_time + datetime.timedelta(hours=token.shelf_life) < now:
        return "Out of time"
    else:
        return token


def use_token(token):
    token = check_token(token)
    if isinstance(token, Token):
        token.use += 1
        db.session.commit()
        return token
    else:
        return token
