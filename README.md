
# PHFS: Python Html File Server

Copy config.py

    cp config.example.py config.py

Init db & migrations

    flask db init
    flask db migrate
    flask db upgrade

---

ERROR [flask_migrate] Error: Can't locate revision identified by '...'

    flask db history
    # Update the version_num field to the head version (in mysql)
    flask db migrate
    flask db upgrade
