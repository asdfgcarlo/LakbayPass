-- Non-destructive bootstrap. Existing users, mission IDs and claims are retained.
CREATE TABLE IF NOT EXISTS users (
    id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(100) NOT NULL,
    email VARCHAR(100) NOT NULL,
    password VARCHAR(255) NOT NULL,
    UNIQUE KEY email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS mission_cards (
    id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    destination_slug VARCHAR(32) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    mission_type VARCHAR(32) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    qr_code VARCHAR(32) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    points SMALLINT UNSIGNED NOT NULL,
    UNIQUE KEY uq_mission_qr (qr_code),
    UNIQUE KEY uq_destination_mission (destination_slug, mission_type),
    CONSTRAINT chk_mission_points CHECK (points > 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS point_claims (
    id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    mission_card_id INT NOT NULL,
    points_awarded SMALLINT UNSIGNED NOT NULL,
    claimed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_user_mission (user_id, mission_card_id),
    CONSTRAINT fk_claim_user FOREIGN KEY (user_id) REFERENCES users (id),
    CONSTRAINT fk_claim_card FOREIGN KEY (mission_card_id) REFERENCES mission_cards (id),
    CONSTRAINT chk_claim_points CHECK (points_awarded > 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
