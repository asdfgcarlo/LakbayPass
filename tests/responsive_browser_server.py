"""Local visual fixtures; no database connections or application data writes."""
import copy
import json
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
import sys
import threading

import MySQLdb
from flask import redirect, session
from werkzeug.serving import make_server

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app as lakbay
from missions import MISSION_TYPES, QR_ASSIGNMENTS


LONG_NAME = 'Traveler' * 12 + 'Name'
LONG_EMAIL = 'traveler-' + 'a' * 72 + '@example.test'
USERS = {
    1: dict(id=1, username=LONG_NAME, email=LONG_EMAIL, role='user', earned_points=270, available_points=180),
    2: dict(id=2, username='New traveler', email='new@example.test', role='user', earned_points=0, available_points=0),
    3: dict(id=3, username='LakbayPass Admin', email='admin@example.test', role='admin', earned_points=0, available_points=0),
}
REDEMPTIONS = [dict(user_id=1, username=LONG_NAME, email=LONG_EMAIL,
                    reward_name='Digital Certificate', points_spent=90,
                    reference='LP-1234567890ABCDEF', status='requested',
                    redeemed_at=datetime(2026, 11, 20, 12, 30))]


def balance(connection, user_id):
    if user_id == 4:
        raise MySQLdb.OperationalError(2003, 'Synthetic unavailable state')
    return USERS[user_id]['available_points']


def progress(connection, user_id, slug):
    total = balance(connection, user_id)
    return dict(total_points=total, missions=[
        dict(mission_type=kind, name=name, description=description, points=points,
             claimed=user_id == 1, points_awarded=points if user_id == 1 else 0,
             claimed_at='2026-11-20T12:00:00' if user_id == 1 else None)
        for kind, (name, points, description) in MISSION_TYPES.items()
    ])


def profile(connection, user_id):
    total = balance(connection, user_id)
    user = USERS[user_id]
    return dict(username=user['username'], total_points=user['earned_points'],
                available_points=total, max_points=270, tier='Gold' if user_id == 1 else 'Bronze',
                visited_count=6 if user_id == 1 else 0, claimed_count=18 if user_id == 1 else 0,
                destinations={slug: dict(claimed_count=3 if user_id == 1 else 0,
                                        missions=progress(connection, user_id, slug)['missions'])
                              for slug in QR_ASSIGNMENTS})


def rewards(connection, user_id):
    total = balance(connection, user_id)
    return dict(balance=total, earned=USERS[user_id]['earned_points'],
                history=copy.deepcopy(REDEMPTIONS) if user_id == 1 else [])


lakbay.mysql = SimpleNamespace(connection=object())
lakbay.player_total_points = balance
lakbay.player_progress = progress
lakbay.player_profile = profile
lakbay.reward_overview = rewards
lakbay.admin_account = lambda connection, user_id: USERS[user_id]
lakbay.admin_overview = lambda connection: dict(total_users=len(USERS), users=list(USERS.values()),
                                               redemptions=copy.deepcopy(REDEMPTIONS))
lakbay.app.config.update(TESTING=True)


@lakbay.app.get('/_preview/session/<int:user_id>')
def preview_session(user_id):
    session.clear()
    user = USERS.get(user_id, USERS[1])
    session.update(loggedin=True, id=user_id, username=user['username'], role=user['role'])
    return redirect('/admin' if user_id == 3 else '/dashboard')


if __name__ == '__main__':
    server = make_server('127.0.0.1', 0, lakbay.app, threaded=True)
    def stop():
        sys.stdin.readline()
        server.shutdown()
    threading.Thread(target=stop, daemon=True).start()
    print(json.dumps(dict(port=server.server_port)), flush=True)
    server.serve_forever()
    server.server_close()
