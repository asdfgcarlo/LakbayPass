"""Reward catalog and transactional, repeat-safe point redemptions."""
import re
import secrets

import MySQLdb.cursors

from missions import player_earned_points, player_total_points


REWARDS = (
    dict(code='ecert', name='Digital Certificate', cost=90,
         description='Redeem your points for an Digital Certificate.'),
    dict(code='card_game_discount', name='20% Discount for the New Card Game', cost=180,
         description='Use your points toward a discount on the new card game.'),
    dict(code='keychain', name='Physical Keychain', cost=270,
         description='Turn your completed missions into a Physical Keychain.'),
)
REWARDS_BY_CODE = {reward['code']: reward for reward in REWARDS}


class RedemptionError(ValueError):
    def __init__(self, status, message):
        self.status = status
        super().__init__(message)


def reward_overview(connection, user_id):
    cursor = connection.cursor(MySQLdb.cursors.DictCursor)
    try:
        cursor.execute('SELECT id FROM users WHERE id = %s', (user_id,))
        if cursor.fetchone() is None:
            return None
        cursor.execute(
            'SELECT reward_name, points_spent, reference, status, redeemed_at '
            'FROM reward_redemptions WHERE user_id = %s ORDER BY id DESC LIMIT 50', (user_id,),
        )
        history = cursor.fetchall()
    finally:
        cursor.close()
    return dict(balance=player_total_points(connection, user_id),
                earned=player_earned_points(connection, user_id), history=history)


def redeem_reward(connection, user_id, reward_code, request_key):
    reward = REWARDS_BY_CODE.get(reward_code)
    if reward is None:
        raise RedemptionError('unknown_reward', 'Choose one of the available rewards.')
    if not isinstance(request_key, str) or re.fullmatch(r'[a-f0-9]{32}', request_key) is None:
        raise RedemptionError('invalid_request', 'Refresh the rewards page and try again.')
    cursor = connection.cursor(MySQLdb.cursors.DictCursor)
    try:
        connection.begin()
        # Every redemption for an account locks this row first. The subsequent
        # balance read sees prior committed spending, including concurrent tabs.
        cursor.execute('SELECT id FROM users WHERE id = %s FOR UPDATE', (user_id,))
        if cursor.fetchone() is None:
            raise RedemptionError('login_required', 'Log in again to redeem your points.')
        cursor.execute(
            'SELECT reward_code, reward_name, points_spent, reference '
            'FROM reward_redemptions WHERE user_id = %s AND request_key = %s FOR UPDATE',
            (user_id, request_key),
        )
        existing = cursor.fetchone()
        if existing is not None:
            if existing['reward_code'] != reward_code:
                raise RedemptionError('invalid_request', 'Refresh the rewards page and try again.')
            connection.commit()
            return dict(existing, already_redeemed=True)
        balance = player_total_points(connection, user_id)
        if balance < reward['cost']:
            missing = reward['cost'] - balance
            unit = 'point' if missing == 1 else 'points'
            raise RedemptionError('insufficient_points', f'You need {missing} more {unit} for this reward.')
        reference = 'LP-' + secrets.token_hex(8).upper()
        cursor.execute(
            'INSERT INTO reward_redemptions '
            '(user_id, reward_code, reward_name, points_spent, request_key, reference) '
            'VALUES (%s, %s, %s, %s, %s, %s)',
            (user_id, reward['code'], reward['name'], reward['cost'], request_key, reference),
        )
        connection.commit()
        return dict(reward_name=reward['name'], points_spent=reward['cost'],
                    reference=reference, already_redeemed=False)
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
