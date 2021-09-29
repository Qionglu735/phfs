
# -*- coding: utf-8 -*-

TITLE = ""

DB_ENABLE = True

DB_URI = "mysql+pymysql://root:root@127.0.0.1:3306/phfs?charset=utf8mb4"

ROOT_FOLDER_DICT = {
    "folder_a": u"/home/folder_a",
    "folder_b": u"/home/folder_b",
}

FOLDER_BLACK_LIST = [r"\..+"]
FILE_BLACK_LIST = [r"\..+"]
EXTENSION_WHITE_LIST = ["tar.gz"]

UPLOAD_CHUNK_SIZE = 1024*1024*90
