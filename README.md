
# Python Html File Server








Creating an Environment

    flask db init

Editing the .ini File

    vi migrations/alembic.ini
    
        sqlalchemy.url = mysql://root:root@127.0.0.1:3306/phfs?charset=utf8

Create Migration Script

    flask db migrate

Running Migration

    flask db upgrade
