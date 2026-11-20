"""Canonical QR assignments, safe imports, and saved mission progress."""
from pathlib import Path

import MySQLdb.cursors


MISSION_TYPES = {
    'itinerary': ('Itinerary', 10, 'Explore the destination.'),
    'local_foods': ('Local Foods', 15, 'Discover the delicacies of the destination.'),
    'activities': ('Activities', 20, 'Try activities for new experience.'),
}
QR_ASSIGNMENTS = {
    'palawan': ('LP-T5V5BWZM', 'LP-BALJDMK4', 'LP-KT2QEJGK'),
    'vigan': ('LP-KE9WGKU6', 'LP-LNZSEHEX', 'LP-T93EPVGV'),
    'cebu': ('LP-LQ8XBEJA', 'LP-QG99QBYR', 'LP-2KK9Y69H'),
    'siquijor': ('LP-DEZHUVQJ', 'LP-EXSBZNRP', 'LP-NW2SAZUN'),
    'siargao': ('LP-WQS7FMFF', 'LP-ARX3WG6V', 'LP-HCH32HR3'),
    'camiguin': ('LP-F5ZZ2HX8', 'LP-5Q9BRMSM', 'LP-4GS6E5ZE'),
}


class AssignmentConflict(ValueError):
    """An import cannot proceed without changing an existing assignment."""


def expected_cards():
    return [
        dict(destination_slug=slug, mission_type=kind, qr_code=qr, points=MISSION_TYPES[kind][1])
        for slug, codes in QR_ASSIGNMENTS.items()
        for kind, qr in zip(MISSION_TYPES, codes)
    ]


def assignment_conflicts(rows):
    """Check every QR and destination/mission slot before inserting anything."""
    desired = expected_cards()
    by_qr = {card['qr_code']: card for card in desired}
    by_slot = {(card['destination_slug'], card['mission_type']): card for card in desired}
    conflicts, seen_qr, seen_slot = [], set(), set()
    for row in rows:
        slot = (row['destination_slug'], row['mission_type'])
        qr = row['qr_code']
        expected = by_qr.get(qr) or by_slot.get(slot)
        if expected and any(row[field] != expected[field] for field in expected):
            conflicts.append(
                f"Card {row['id']}: {qr} is assigned to {slot[0]}/{slot[1]} "
                f"({row['points']} pts); expected {expected['qr_code']} at "
                f"{expected['destination_slug']}/{expected['mission_type']} ({expected['points']} pts)."
            )
        if qr in seen_qr:
            conflicts.append(f"Duplicate qr_code {qr!r}; card IDs must be resolved without deleting claims.")
        if slot in seen_slot:
            conflicts.append(f"Duplicate mission slot {slot[0]}/{slot[1]}; existing card IDs were preserved.")
        seen_qr.add(qr)
        seen_slot.add(slot)
    return conflicts


def import_mission_cards(connection):
    """Create missing tables, reject conflicts, and insert only missing cards.

    Never REPLACE, UPDATE, truncate, or delete a card/claim. An advisory lock
    serializes importers; a transaction makes all 18 assignments one import.
    """
    cursor = connection.cursor(MySQLdb.cursors.DictCursor)
    locked = False
    try:
        cursor.execute("SELECT GET_LOCK(CONCAT(DATABASE(), ':mission-import'), 10) AS acquired")
        locked = cursor.fetchone()['acquired'] == 1
        if not locked:
            raise AssignmentConflict('Another mission import is running. Try again shortly.')
        schema = Path(__file__).with_name('database').joinpath('schema.sql').read_text(encoding='utf-8')
        for statement in schema.split(';'):
            if statement.strip():
                cursor.execute(statement)
        connection.begin()
        cursor.execute('SELECT id, destination_slug, mission_type, qr_code, points FROM mission_cards FOR UPDATE')
        existing = cursor.fetchall()
        conflicts = assignment_conflicts(existing)
        if conflicts:
            raise AssignmentConflict('\n'.join(conflicts))
        # Existing compatible tables must have the same uniqueness guarantees.
        for table, columns, name in (
            ('mission_cards', ('qr_code',), 'uq_mission_qr'),
            ('mission_cards', ('destination_slug', 'mission_type'), 'uq_destination_mission'),
            ('point_claims', ('user_id', 'mission_card_id'), 'uq_user_mission'),
        ):
            cursor.execute(f'SHOW INDEX FROM {table}')
            unique = {}
            for index in cursor.fetchall():
                if not index['Non_unique']:
                    unique.setdefault(index['Key_name'], []).append((index['Seq_in_index'], index['Column_name']))
            if not any(tuple(col for _, col in sorted(items)) == columns for items in unique.values()):
                # ALTER only adds an index; a duplicate raises and preserves all rows.
                cursor.execute(f"ALTER TABLE {table} ADD UNIQUE KEY {name} ({', '.join(columns)})")
        connection.begin()
        present = {row['qr_code'] for row in existing}
        added = 0
        for card in expected_cards():
            if card['qr_code'] not in present:
                cursor.execute(
                    'INSERT INTO mission_cards (destination_slug, mission_type, qr_code, points) VALUES (%s, %s, %s, %s)',
                    (card['destination_slug'], card['mission_type'], card['qr_code'], card['points']),
                )
                added += 1
        connection.commit()
        return added
    except Exception:
        connection.rollback()
        raise
    finally:
        if locked:
            cursor.execute("SELECT RELEASE_LOCK(CONCAT(DATABASE(), ':mission-import'))")
        cursor.close()


def player_earned_points(connection, user_id):
    """Lifetime earned points determine mission progress and the player's tier."""
    cursor = connection.cursor(MySQLdb.cursors.DictCursor)
    try:
        cursor.execute('SELECT COALESCE(SUM(points_awarded), 0) AS total FROM point_claims WHERE user_id = %s', (user_id,))
        return int(cursor.fetchone()['total'])
    finally:
        cursor.close()


def player_total_points(connection, user_id):
    """Spendable balance: awarded mission points minus saved redemptions."""
    cursor = connection.cursor(MySQLdb.cursors.DictCursor)
    try:
        cursor.execute(
            # MySQL 5.5 can coerce negative UNION rows to unsigned values and
            # ignore the spending. Aggregate independently, then subtract two
            # explicitly signed totals on every supported server version.
            'SELECT CAST((SELECT COALESCE(SUM(points_awarded), 0) '
            'FROM point_claims WHERE user_id = %s) AS SIGNED) '
            '- CAST((SELECT COALESCE(SUM(points_spent), 0) '
            'FROM reward_redemptions WHERE user_id = %s) AS SIGNED) AS total',
            (user_id, user_id),
        )
        return int(cursor.fetchone()['total'])
    finally:
        cursor.close()


def player_tier(points):
    if points <= 90:
        return 'Bronze'
    if points <= 180:
        return 'Silver'
    return 'Gold'


def player_profile(connection, user_id):
    """Read one user's identity and claims without changing their progress."""
    cursor = connection.cursor(MySQLdb.cursors.DictCursor)
    try:
        cursor.execute('SELECT username FROM users WHERE id = %s', (user_id,))
        account = cursor.fetchone()
        if account is None:
            return None
        cursor.execute(
            'SELECT c.destination_slug, c.mission_type, p.id AS claim_id '
            'FROM mission_cards c LEFT JOIN point_claims p '
            'ON p.mission_card_id = c.id AND p.user_id = %s', (user_id,),
        )
        claimed = {(row['destination_slug'], row['mission_type'])
                   for row in cursor.fetchall() if row['claim_id'] is not None}
    finally:
        cursor.close()
    destinations = {}
    for slug in QR_ASSIGNMENTS:
        missions = [dict(mission_type=kind, name=details[0], claimed=(slug, kind) in claimed)
                    for kind, details in MISSION_TYPES.items()]
        destinations[slug] = dict(missions=missions, claimed_count=sum(item['claimed'] for item in missions))
    total = player_earned_points(connection, user_id)
    return dict(
        username=account['username'], total_points=total,
        available_points=player_total_points(connection, user_id),
        max_points=sum(card['points'] for card in expected_cards()),
        tier=player_tier(total), destinations=destinations,
        visited_count=sum(place['claimed_count'] > 0 for place in destinations.values()),
        claimed_count=sum(place['claimed_count'] for place in destinations.values()),
    )


def player_progress(connection, user_id, slug):
    """Both initial render and claim responses use this database-backed state."""
    cursor = connection.cursor(MySQLdb.cursors.DictCursor)
    try:
        cursor.execute(
            'SELECT c.mission_type, c.points, p.id AS claim_id, p.points_awarded, p.claimed_at '
            'FROM mission_cards c LEFT JOIN point_claims p '
            'ON p.mission_card_id = c.id AND p.user_id = %s WHERE c.destination_slug = %s',
            (user_id, slug),
        )
        rows = {row['mission_type']: row for row in cursor.fetchall()}
        missions = []
        for kind, (name, _, description) in MISSION_TYPES.items():
            row = rows.get(kind)
            if row is None:
                raise RuntimeError('Mission cards are missing. Run flask --app app import-mission-cards.')
            missions.append({
                'mission_type': kind, 'name': name, 'description': description,
                'points': row['points'], 'claimed': row['claim_id'] is not None,
                'points_awarded': row['points_awarded'] if row['claim_id'] is not None else 0,
                'claimed_at': row['claimed_at'].isoformat() if row['claimed_at'] else None,
            })
        return {'missions': missions, 'total_points': player_total_points(connection, user_id)}
    finally:
        cursor.close()
