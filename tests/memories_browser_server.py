"""Real memories services on disposable storage; no hosted database access."""
import json
import sys
import tempfile
import threading
from pathlib import Path
from types import SimpleNamespace

from flask import redirect, session
from werkzeug.serving import make_server

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app as lakbay
from memories_fixture import Connection
from missions import MISSION_TYPES, QR_ASSIGNMENTS

temporary = tempfile.TemporaryDirectory()
connection = Connection(str(Path(temporary.name) / 'fixture.sqlite'))
lakbay.mysql = SimpleNamespace(connection=connection)
lakbay.app.config.update(TESTING=True, MEMORIES_UPLOAD_FOLDER=str(Path(temporary.name) / 'photos'))


def profile(connection, user_id):
    return dict(username='Traveler', total_points=25, available_points=25,
                max_points=270, tier='Bronze', visited_count=1, claimed_count=2,
                destinations={slug: dict(claimed_count=2 if slug == 'palawan' else 0,
                    missions=[dict(mission_type=kind, name=value[0], claimed=slug == 'palawan' and kind != 'activities')
                              for kind, value in MISSION_TYPES.items()]) for slug in QR_ASSIGNMENTS})


lakbay.player_profile = profile


@lakbay.app.get('/_preview/session/<int:user_id>')
def preview_session(user_id):
    session.clear()
    session.update(loggedin=True, id=user_id, username='Traveler', role='user')
    return redirect('/profile')


if __name__ == '__main__':
    server = make_server('127.0.0.1', 0, lakbay.app, threaded=False)
    def stop():
        sys.stdin.readline()
        server.shutdown()
    threading.Thread(target=stop, daemon=True).start()
    print(json.dumps(dict(port=server.server_port)), flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()
        connection.database.close()
        temporary.cleanup()
