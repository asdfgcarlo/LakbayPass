"""Account roles, explicit admin setup, and read-only administration queries."""
import hashlib

import MySQLdb
import MySQLdb.cursors


def install_user_roles(connection):
    """Add roles to an existing installation without changing its users."""
    cursor = connection.cursor()
    try:
        cursor.execute("SHOW COLUMNS FROM users LIKE 'role'")
        if cursor.fetchone() is None:
            try:
                cursor.execute("ALTER TABLE users ADD COLUMN role ENUM('user', 'admin') NOT NULL DEFAULT 'user'")
            except MySQLdb.OperationalError as error:
                # Another setup process may have added the column after SHOW.
                if error.args[0] != 1060:
                    raise
        connection.commit()
    finally:
        cursor.close()


def setup_admin_account(connection, email, password):
    """Create or update only the explicitly selected administrator account."""
    install_user_roles(connection)
    cursor = connection.cursor()
    try:
        cursor.execute(
            "INSERT INTO users (username, email, password, role) VALUES (%s, %s, %s, 'admin') "
            "ON DUPLICATE KEY UPDATE password = VALUES(password), role = 'admin'",
            ('LakbayPass Admin', email, hashlib.sha256(password.encode()).hexdigest()),
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()


def admin_account(connection, user_id):
    """Authorize with the saved role, including sessions created before a change."""
    cursor = connection.cursor(MySQLdb.cursors.DictCursor)
    try:
        cursor.execute('SELECT id, username, role FROM users WHERE id = %s', (user_id,))
        return cursor.fetchone()
    finally:
        cursor.close()


def admin_overview(connection):
    """Keep each user's awards and spending separate to avoid multiplying sums."""
    cursor = connection.cursor(MySQLdb.cursors.DictCursor)
    try:
        cursor.execute(
            'SELECT u.id, u.username, u.email, u.role, '
            'CAST(COALESCE(c.earned, 0) AS SIGNED) AS earned_points, '
            'CAST(COALESCE(s.spent, 0) AS SIGNED) AS spent_points, '
            'CAST(COALESCE(c.earned, 0) AS SIGNED) '
            '- CAST(COALESCE(s.spent, 0) AS SIGNED) AS available_points '
            'FROM users u '
            'LEFT JOIN (SELECT user_id, SUM(points_awarded) AS earned '
            'FROM point_claims GROUP BY user_id) c ON c.user_id = u.id '
            'LEFT JOIN (SELECT user_id, SUM(points_spent) AS spent '
            'FROM reward_redemptions GROUP BY user_id) s ON s.user_id = u.id '
            'ORDER BY u.id'
        )
        users = cursor.fetchall()
        cursor.execute(
            'SELECT r.reference, r.reward_name, r.points_spent, r.status, r.redeemed_at, '
            'u.id AS user_id, u.username, u.email '
            'FROM reward_redemptions r JOIN users u ON u.id = r.user_id '
            'ORDER BY r.redeemed_at DESC, r.id DESC'
        )
        redemptions = cursor.fetchall()
        return dict(users=users, total_users=len(users), redemptions=redemptions)
    finally:
        cursor.close()
