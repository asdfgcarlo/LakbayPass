"""Isolated MySQL fixture server for scanner.browser.cjs; stdin 'stop' cleans up."""
import hashlib
import json
from pathlib import Path
import sys
import threading
import uuid

import MySQLdb
from werkzeug.serving import make_server

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import app
from missions import import_mission_cards


# Keep the DB name plus ':mission-import' within MySQL's 64-byte lock limit.
database_name = 'lp_browser_' + uuid.uuid4().hex
options = dict(host=app.config['MYSQL_HOST'], user=app.config['MYSQL_USER'],
               passwd=app.config['MYSQL_PASSWORD'], port=app.config['MYSQL_PORT'],
               connect_timeout=app.config['MYSQL_CONNECT_TIMEOUT'], charset='utf8mb4')
admin = MySQLdb.connect(**options)
database = None
try:
    with admin.cursor() as cursor:
        cursor.execute(f'CREATE DATABASE `{database_name}` CHARACTER SET utf8mb4')
    database = MySQLdb.connect(db=database_name, **options)
    import_mission_cards(database)
    with database.cursor() as cursor:
        for number in (1, 2):
            cursor.execute('INSERT INTO users (username,email,password) VALUES (%s,%s,%s)', (
                f'Scanner tester {number}', f'scanner-{number}@example.test',
                hashlib.sha256(b'scanner-test-password').hexdigest(),
            ))
    database.commit()
    app.config.update(MYSQL_DB=database_name, TESTING=True)
    server = make_server('127.0.0.1', 0, app, threaded=True)
    def stop_from_stdin():
        sys.stdin.readline()
        server.shutdown()
    threading.Thread(target=stop_from_stdin, daemon=True).start()
    print(json.dumps({'port': server.server_port}), flush=True)
    server.serve_forever()
    server.server_close()
finally:
    if database:
        database.close()
    # This name is created above using only a fixed prefix and uuid.hex.
    with admin.cursor() as cursor:
        cursor.execute(f'DROP DATABASE IF EXISTS `{database_name}`')
    admin.close()
