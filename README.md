
# PHFS: Python Html File Server








Creating an Environment

    flask db init

Editing the .ini File

    vi migrations/alembic.ini
    
        sqlalchemy.url = mysql://root:root@127.0.0.1:3306/phfs?charset=utf8

Create Migration Script

    flask db migrate

Running Migration

    flask db upgrade

ERROR [flask_migrate] Error: Can't locate revision identified by '...'

    flask db history
    # Update the version_num field to the head version (in mysql)
    flask db migrate
    flask db upgrade
