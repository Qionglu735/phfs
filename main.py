# -*- coding: utf-8 -*-

from flask import Blueprint, make_response, render_template, request, Response, send_file, url_for
from flask_login import current_user

import datetime
import functools
import json
import os
import re
import sys
import uuid

from auth import login_required
from config import *
from model import db, Token, User

main = Blueprint("main", __name__)


def parse_file_path(file_path):
    if file_path is not None and file_path != "":
        file_path = file_path.replace("\\", "/")
        path_list = file_path.lstrip("/").split("/")
        real_root = ROOT_FOLDER_DICT[path_list[0]]
        return os.path.join(real_root, *path_list[1:])


def detect_binary(file_path):
    text_chars = bytearray({7, 8, 9, 10, 12, 13, 27} | set(range(0x20, 0x100)) - {0x7f})
    return bool(open(file_path, "rb").read(1024).translate(None, text_chars))


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


def generate_file_tree():
    tree = {
        "type": "dir",
        "name": "/",
        "path": "/",
        "sub": dict()
    }
    anonymous_path_list = list()
    if DB_ENABLE:
        for anonymous_token in Token.query.join(User).filter_by(email="Anonymous"):
            anonymous_path_list.append(anonymous_token.file_path)
    root_folder_list = [[root_name, root_folder] for root_name, root_folder in ROOT_FOLDER_DICT.items()]
    root_folder_list.sort(key=lambda x: [0])
    for root_item in root_folder_list:
        root_name = root_item[0]
        root_folder = root_item[1].rstrip("/")
        if sys.platform == "win32" and root_folder.endswith(":"):
            root_folder += "/"
        sub_tree = {
            "type": "dir",
            "name": root_name,
            "path": "/" + root_name + "/",
            "sub": dict()
        }
        tree["sub"][root_name] = sub_tree
        for root, dirs, files in os.walk(root_folder):
            dirs[:] = [d for d in dirs if len([x for x in FOLDER_BLACK_LIST if re.match(x, d) is not None]) == 0]
            root = root.replace("\\", "/")
            # print(root)
            root = root.replace(root_folder, "", 1)
            path_list = list()
            if "/" in root:
                path_list = root.split("/")[1:]

            sub_tree = tree["sub"][root_name]
            for p in path_list:
                sub_tree = sub_tree["sub"][p]
            for d in sorted(dirs):
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
                    "lock": None,
                }
                if DB_ENABLE:
                    sub_tree["sub"][f]["lock"] = parse_file_path(sub_tree["sub"][f]["path"]) not in anonymous_path_list
    return tree


def dfs(tree, depth=0, node_list=None):
    if node_list is None:
        node_list = list()
    node_list.append({
        "id": len(node_list),
        "depth": depth,
        "info": tree,
    })
    if "sub" in tree:
        def node_cmp(_x, _y):
            res = 0
            if tree["sub"][_x]["type"] == tree["sub"][_y]["type"]:
                res = -1 if _x.lower() < _y.lower() else 0 if _x.lower() == _y.lower() else 1
            elif tree["sub"][_x]["type"] == "dir" and tree["sub"][_y]["type"] == "file":
                res = -1
            elif tree["sub"][_x]["type"] == "file" and tree["sub"][_y]["type"] == "dir":
                res = 1
            return res

        sorted_list = [_x for _x in tree["sub"]]
        sorted_list.sort(key=functools.cmp_to_key(node_cmp))

        for name in sorted_list:
            dfs(tree["sub"][name], depth + 1, node_list)
    return node_list


def find_next_node(node_list, node_id):
    if node_id + 1 < len(node_list) and node_list[node_id + 1]["depth"] == node_list[node_id]["depth"]:
        return node_list[node_id + 1]
    else:
        while node_id > 0 and node_list[node_id - 1]["depth"] == node_list[node_id]["depth"]:
            node_id -= 1
        return node_list[node_id]


@main.route("/file_tree", methods=["GET"])
@login_required(10)
def file_tree():
    if request.method == "GET":
        tree = generate_file_tree()
        node_list = dfs(tree)
        return json.dumps(node_list)


def get_chunk(file_path, byte1=None, byte2=None):
    file_size = os.stat(file_path).st_size
    start = 0

    if byte1 < file_size:
        start = byte1
    if byte2:
        length = byte2 + 1 - byte1
    else:
        length = file_size - start

    with open(file_path, "rb") as f:
        f.seek(start)
        chunk = f.read(length)
    return chunk, start, length, file_size


@main.route("/file_api", methods=["GET", "POST", "PUT", "DELETE", "UPDATE"])
@login_required(10)
def file_api():
    if request.method == "GET":
        file_path = parse_file_path(request.args.get("file_path"))
        node_id = request.args.get("node_id")
        token = request.args.get("token")
        if token is None:
            tree = generate_file_tree()
            node_list = dfs(tree)
            next_node = find_next_node(node_list, int(node_id))
            if DB_ENABLE:
                token = get_or_create_token(file_path, current_user)
                return url_for("main.preview") + "?" + "&".join([
                    "token=" + token.token_id,
                ])
            else:
                return url_for("main.preview") + "?" + "&".join([
                    "token=" + file_path,
                    "next_path=" + next_node["info"]["path"],
                    "next_node_id=" + str(next_node["id"]),
                ])
        else:
            range_header = request.headers.get("Range", None)
            byte1, byte2 = 0, None
            if range_header:
                match = re.search(r'(\d+)-(\d*)', range_header)
                groups = match.groups()
                if groups[0]:
                    byte1 = int(groups[0])
                if groups[1]:
                    byte2 = int(groups[1])
            if DB_ENABLE:
                token = use_token(token)
                if isinstance(token, Token):
                    token.use += 1
                    db.session.commit()
                    file_path = token.file_path
                    # encode_print(u"{}".format(file_path))
                    # return send_file(file_path, as_attachment=True)
                else:
                    return render_template("error.html", message=token)
            else:
                file_path = token.lstrip("/")
            encode_print(u"{}".format(file_path))
            # return send_file(file_path, as_attachment=True)
            chunk, start, length, file_size = get_chunk(file_path, byte1, byte2)
            resp = Response(chunk, 206, direct_passthrough=True)
            resp.headers.add("Content-Range", "bytes {0}-{1}/{2}".format(start, start + length - 1, file_size))
            return resp
    elif request.method == "POST":
        file_path = request.form.get("file_path").lstrip("/")
        file_path = parse_file_path(file_path)
        encode_print(u"{}".format(file_path))
        return send_file(file_path, as_attachment=True)
    elif request.method == "PUT":
        file_path = request.form.get("file_path").lstrip("/")
        file_path = parse_file_path(file_path)
        upload_type = request.form.get("type")
        if upload_type == "folder":
            folder_name = request.form.get("folder_name")
            if os.path.exists(file_path):
                if os.path.exists(os.path.join(file_path, folder_name)):
                    duplicate = 2
                    while os.path.exists(
                            os.path.join(file_path, u"{}({})".format(folder_name, duplicate))):
                        duplicate += 1
                    folder_name = u"{}({})".format(folder_name, duplicate)
                os.mkdir(os.path.join(file_path, folder_name))
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
            if os.path.exists(os.path.join(file_path, filename)):
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
                        os.path.join(file_path, merge_filename())):
                    duplicate += 1
                filename = merge_filename()
            if part_index > 0:
                filename += u".part{}".format(part_index)
            encode_print(u"PUT {} {}".format(file_path, filename))
            upload_file.save(os.path.join(file_path, filename))
            if 0 < part_total == part_index:
                true_filename = filename[:-len(u".part{}".format(part_total))]
                with open(os.path.join(file_path, true_filename), "wb") as f_out:
                    for i in range(1, part_total + 1):
                        part_filename = true_filename + u".part{}".format(i)
                        encode_print(u"MERGE {} {}".format(file_path, part_filename))
                        with open(os.path.join(file_path, part_filename), "rb") as f_in:
                            f_out.write(f_in.read())
                        os.remove(os.path.join(file_path, part_filename))
            return "OK"
    elif request.method == "DELETE":
        file_path = request.form.get("file_path").lstrip("/")
        file_path = parse_file_path(file_path)
        if os.path.exists(file_path):
            encode_print(u"DELETE {}".format(file_path))
            os.remove(file_path)
        return "OK"
    elif request.method == "UPDATE":
        op = request.form.get("op")
        file_path = request.form.get("file_path").lstrip("/")
        print(file_path, parse_file_path(file_path))
        file_path = parse_file_path(file_path)
        if DB_ENABLE:
            if op == "unlock":
                anonymous = User.query.filter_by(email="Anonymous").first()
                if anonymous is None:
                    anonymous = User(email="Anonymous", auth=1)
                    db.session.add(anonymous)
                    db.session.commit()
                token = Token.query.filter_by(user_id=anonymous.id, file_path=file_path).first()
                if token is None:
                    token = Token(token_id=uuid.uuid4().hex,
                                  file_path=file_path,
                                  user_id=anonymous.id)
                    db.session.add(token)
                    db.session.commit()
            elif op == "lock":
                anonymous = User.query.filter_by(email="Anonymous").first()
                if anonymous is not None:
                    token = Token.query.filter_by(user_id=anonymous.id, file_path=file_path).first()
                    if token is not None:
                        db.session.delete(token)
                        db.session.commit()

        return "Update"


def secure_filename(x):
    return x.replace(" ", "_")


@main.route("/preview")
@login_required(1)
def preview():
    token = request.args.get("token", "")
    if DB_ENABLE:
        token = check_token(token)
        if isinstance(token, Token):
            if token.file_path.split(".")[-1] in ["jpg", "png"]:
                return render_template("image.html",
                                       filename=token.file_path.split("/")[-1],
                                       token=token.token_id)
            elif token.file_path.split(".")[-1] in ["mp4", "webm", "ogg"]:
                response = make_response(render_template("video.html",
                                         filename=token.file_path.split("/")[-1],
                                         token=token.token_id))
                response.headers["Accept-Ranges"] = "bytes"
                return response
            else:
                token = use_token(token)
                if isinstance(token, Token):
                    file_path = token.file_path
                    encode_print(u"{}".format(file_path))
                    return send_file(file_path)
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
            encode_print(u"{}".format(file_path))
            print("is binary:", detect_binary(file_path))
            # return send_file(file_path, as_attachment=detect_binary(file_path))
            return send_file(file_path)


def get_or_create_token(file_path, target_user):
    now = datetime.datetime.now()
    anonymous_token = Token.query.filter_by(file_path=file_path).join(User) \
        .filter_by(email="Anonymous").first()
    if anonymous_token is not None:
        return anonymous_token
    token = Token.query.filter_by(user_id=target_user.id, file_path=file_path).first()
    if token is None or token.effective_time + datetime.timedelta(hours=token.shelf_life) < now:
        token = Token(token_id=uuid.uuid4().hex,
                      file_path=file_path,
                      effective_time=now,
                      user_id=target_user.id)
        db.session.add(token)
        db.session.commit()
    return token


def check_token(token):
    now = datetime.datetime.now()
    if not isinstance(token, Token):
        token = Token.query.filter_by(token_id=token).first()
    if token is None:
        return "Not exists"
    token_user = User.query.filter_by(id=token.user_id).first()
    if token_user is None:
        return "Access Denied"
    elif token_user.email == "Anonymous":
        return token
    elif "email" not in current_user.__dict__ or current_user.email != token_user.email:
        return "Access Denied"
    else:
        if token_user.auth < 10:
            return "Access Denied"
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
