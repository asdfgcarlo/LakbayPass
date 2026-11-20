import hashlib
import os
import re
import secrets
from pathlib import Path

import click
import MySQLdb
import MySQLdb.cursors
from flask import Flask, abort, flash, jsonify, make_response, redirect, render_template, request, session, url_for
from flask_mysqldb import MySQL

from missions import AssignmentConflict, MISSION_TYPES, import_mission_cards, player_progress

app = Flask(__name__)
app.config.from_mapping(
    MYSQL_HOST='sql12.freesqldatabase.com',
    MYSQL_USER='sql12841075',
    MYSQL_PASSWORD='BdFpCtEVNb',
    MYSQL_DB='sql12841075',
    MYSQL_PORT=3306,
    MYSQL_CONNECT_TIMEOUT=10,
    MYSQL_CHARSET='utf8mb4',
    SESSION_COOKIE_SAMESITE='Lax',
)
# Environment variables can override the configured database when needed.
for setting in ('MYSQL_HOST', 'MYSQL_USER', 'MYSQL_PASSWORD', 'MYSQL_DB', 'MYSQL_PORT'):
    app.config[setting] = os.environ.get(f'LAKBAYPASS_{setting}', app.config[setting])
try:
    app.config['MYSQL_PORT'] = int(app.config['MYSQL_PORT'])
    if not 1 <= app.config['MYSQL_PORT'] <= 65535:
        raise ValueError
except (TypeError, ValueError):
    raise ValueError('MYSQL_PORT / LAKBAYPASS_MYSQL_PORT must be an integer from 1 to 65535.') from None

# Persist a private signing key locally, or use the deployment environment key.
# The previous public placeholder key cannot protect point-claim identities.
app.secret_key = os.environ.get('LAKBAYPASS_SECRET_KEY')
if not app.secret_key:
    key_file = Path(app.instance_path) / 'secret_key'
    key_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        with key_file.open('x', encoding='utf-8') as key:
            key.write(secrets.token_hex(32))
    except FileExistsError:
        pass
    app.secret_key = key_file.read_text(encoding='utf-8').strip()
mysql = MySQL(app)


@app.cli.command('import-mission-cards')
def import_cards_command():
    """Install mission tables and import the 18 exact QR assignments safely."""
    try:
        added = import_mission_cards(mysql.connection)
    except (AssignmentConflict, MySQLdb.Error) as error:
        raise click.ClickException(f'Import stopped; existing cards and claims were preserved.\n{error}') from error
    click.echo(f'Mission cards ready: {added} added, {18 - added} unchanged. No QR assignment conflicts.')

# Drop the matching photo into static/destinations to replace its placeholder.
DESTINATIONS = (
    ('palawan', 'Palawan', 'Mitra’s Ranch', 'palawan-mitras-ranch.jpg'),
    ('vigan', 'Vigan', 'Calle Crisologo', 'vigan-calle-crisologo.jpg'),
    ('cebu', 'Cebu', 'Binalayan Hidden Falls', 'cebu-binalayan-hidden-falls.jpg'),
    ('siquijor', 'Siquijor', 'Paliton Beach', 'siquijor-paliton-beach.jpg'),
    ('siargao', 'Siargao', 'Sugba Lagoon', 'siargao-sugba-lagoon.jpg'),
    ('camiguin', 'Camiguin', 'Mantigue Island', 'camiguin-mantigue-island.jpg'),
)


def get_destinations():
    """Resolve the same destination photos for the gallery and detail pages."""
    destinations = []
    for slug, destination, attraction, filename in DESTINATIONS:
        image = f'destinations/{filename}'
        has_photo = (Path(app.static_folder) / image).is_file()
        destinations.append({
            'slug': slug,
            'destination': destination,
            'attraction': attraction,
            'image': image if has_photo else 'destinations/photo-placeholder.svg',
            'has_photo': has_photo,
        })
    return destinations


def auth_values_and_errors(registering=False):
    """Validate on the server too, including requests made without JavaScript."""
    values = {'email': request.form.get('email', '').strip()}
    password = request.form.get('password', '')
    errors = {}
    if registering:
        values['username'] = request.form.get('username', '').strip()
        if not values['username']:
            errors['username'] = 'Enter your username.'
        elif len(values['username']) > 100:
            errors['username'] = 'Use 100 characters or fewer for your username.'
    if not values['email']:
        errors['email'] = 'Enter your email address.'
    elif len(values['email']) > 100:
        errors['email'] = 'Use 100 characters or fewer for your email address.'
    elif not re.fullmatch(r'[^\s@]+@[^\s@]+', values['email']):
        errors['email'] = 'Enter an email address like name@example.com.'
    if not password:
        errors['password'] = 'Enter your password.'
    return values, password, errors


@app.route('/register', methods=['GET', 'POST'])
def register():
    values, errors = {}, {}
    if request.method == 'POST':
        values, password, errors = auth_values_and_errors(registering=True)
        if not errors:
            hashed_password = hashlib.sha256(password.encode()).hexdigest()
            cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
            try:
                cursor.execute('SELECT * FROM users WHERE email=%s', (values['email'],))
                if cursor.fetchone():
                    errors['email'] = 'An account with this email already exists. Log in instead.'
                else:
                    try:
                        cursor.execute(
                            'INSERT INTO users (username, email, password) VALUES (%s, %s, %s)',
                            (values['username'], values['email'], hashed_password),
                        )
                        mysql.connection.commit()
                    except MySQLdb.IntegrityError as error:
                        mysql.connection.rollback()
                        if error.args[0] != 1062:
                            raise
                        errors['email'] = 'An account with this email already exists. Log in instead.'
                    else:
                        flash('Your account is ready. You can log in now.', 'success')
                        return redirect(url_for('login'))
            finally:
                cursor.close()
    return render_template('lakbayRegister.html', values=values, errors=errors)


@app.route('/', methods=['GET', 'POST'])
@app.route('/login', methods=['GET', 'POST'])
def login():
    values, errors = {}, {}
    if request.method == 'POST':
        values, password, errors = auth_values_and_errors()
        if not errors:
            hashed_password = hashlib.sha256(password.encode()).hexdigest()
            cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
            try:
                cursor.execute(
                    'SELECT * FROM users WHERE email=%s AND password=%s',
                    (values['email'], hashed_password),
                )
                account = cursor.fetchone()
            finally:
                cursor.close()
            if account:
                session['loggedin'] = True
                session['id'] = account['id']
                session['username'] = account['username']
                return redirect(url_for('dashboard'))
            errors['password'] = 'We couldn’t log you in. Check your email and password.'
    return render_template('lakbayLogin.html', values=values, errors=errors)


@app.route('/dashboard')
def dashboard():
    if 'loggedin' in session:
        return render_template('lakbayDashboard.html', username=session['username'], destinations=get_destinations())
    return redirect(url_for('login'))


@app.route('/destinations/<slug>')
def destination(slug):
    if 'loggedin' in session:
        place = next((place for place in get_destinations() if place['slug'] == slug), None)
        if place is None:
            abort(404)
        session.setdefault('claim_csrf', secrets.token_urlsafe(32))
        progress = player_progress(mysql.connection, session.get('id', 0), slug)
        response = make_response(render_template(
            f'destinations/{slug}.html', place=place, username=session['username'], progress=progress,
        ))
        response.headers['Cache-Control'] = 'no-store'
        return response
    return redirect(url_for('login'))


def claim_response(payload, status=200):
    response = jsonify(payload)
    response.status_code = status
    response.headers['Cache-Control'] = 'no-store'
    return response


def claim_player_id():
    player_id = session.get('id')
    if not session.get('loggedin') or type(player_id) is not int or player_id <= 0:
        return None
    return player_id


@app.get('/api/destinations/<slug>/missions')
def mission_progress(slug):
    player_id = claim_player_id()
    if player_id is None:
        return claim_response({'status': 'login_required', 'message': 'Log in again to view your points.'}, 401)
    if slug not in {place[0] for place in DESTINATIONS}:
        abort(404)
    try:
        return claim_response(player_progress(mysql.connection, player_id, slug))
    except MySQLdb.Error:
        app.logger.exception('Could not load mission progress')
        return claim_response({'status': 'unavailable', 'message': 'Your points could not be loaded. Please try again.'}, 503)


@app.post('/api/claims')
def claim_points():
    player_id = claim_player_id()
    if player_id is None:
        return claim_response({'status': 'login_required', 'message': 'Log in again to claim this mission.'}, 401)
    csrf = session.get('claim_csrf', '')
    if not csrf or not secrets.compare_digest(request.headers.get('X-CSRF-Token', '').encode('utf-8'), csrf.encode('utf-8')):
        return claim_response({'status': 'expired', 'message': 'Refresh this page before scanning again.'}, 403)
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return claim_response({'status': 'invalid_request', 'message': 'Scan a LakbayPass mission QR code.'}, 400)
    qr, slug = data.get('qr_code'), data.get('destination_slug')
    if not isinstance(qr, str) or not qr or len(qr) > 512:
        return claim_response({'status': 'invalid_request', 'message': 'Scan a LakbayPass mission QR code.'}, 400)
    if not isinstance(slug, str) or slug not in {place[0] for place in DESTINATIONS}:
        return claim_response({'status': 'invalid_destination', 'message': 'Open a destination from the gallery, then scan again.'}, 400)
    if not re.fullmatch(r'LP-[A-Z0-9]{8}', qr):
        return claim_response({'status': 'unknown_qr', 'message': 'QR not recognized. Scan a LakbayPass mission card.', 'points_awarded': 0}, 404)
    connection = mysql.connection
    cursor = connection.cursor(MySQLdb.cursors.DictCursor)
    try:
        connection.begin()
        cursor.execute('SELECT id FROM users WHERE id = %s', (player_id,))
        if cursor.fetchone() is None:
            connection.rollback()
            return claim_response({'status': 'login_required', 'message': 'Log in again to claim this mission.'}, 401)
        cursor.execute('SELECT id, destination_slug, mission_type, points FROM mission_cards WHERE qr_code = %s', (qr,))
        card = cursor.fetchone()
        if card is None:
            connection.rollback()
            return claim_response({'status': 'unknown_qr', 'message': 'QR not recognized. Scan a LakbayPass mission card.', 'points_awarded': 0}, 404)
        if card['destination_slug'] != slug:
            connection.rollback()
            place_name = next((place[1] for place in DESTINATIONS if place[0] == card['destination_slug']), 'another destination')
            return claim_response({
                'status': 'wrong_destination', 'message': f'This card belongs to {place_name}. Open that destination to claim it.',
                'points_awarded': 0,
            }, 409)
        try:
            cursor.execute(
                'INSERT INTO point_claims (user_id, mission_card_id, points_awarded) VALUES (%s, %s, %s)',
                (player_id, card['id'], card['points']),
            )
            connection.commit()
            status, awarded = 'claimed', card['points']
        except MySQLdb.IntegrityError as error:
            connection.rollback()
            if error.args[0] != 1062:
                raise
            # A duplicate insert waits on the UNIQUE key, then reaches here.
            # Rollback first so the following progress read sees that claim.
            status, awarded = 'already_claimed', 0
        progress = player_progress(connection, player_id, slug)
        name = MISSION_TYPES[card['mission_type']][0]
        message = (f'{name} claimed! You earned {awarded} points.' if awarded else
                   f'{name} is already claimed. No additional points were added.')
        return claim_response({
            **progress, 'status': status, 'message': message, 'points_awarded': awarded,
            'mission_type': card['mission_type'],
        }, 201 if awarded else 409)
    except MySQLdb.Error:
        connection.rollback()
        app.logger.exception('Could not save mission claim')
        return claim_response({'status': 'unavailable', 'message': 'Your claim could not be confirmed. Scan again to check; points are awarded only once.'}, 503)
    finally:
        cursor.close()


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


if __name__ == '__main__':
    app.run(debug=True)
