"""Isolated SQL adapter for testing the MySQL repository without a live account."""
import io
import sqlite3

from PIL import Image


class Cursor:
    def __init__(self, connection):
        self.connection = connection
        self.cursor = connection.database.cursor()

    @property
    def lastrowid(self):
        return self.cursor.lastrowid

    def execute(self, query, params=()):
        if query.startswith('INSERT INTO user_memories'):
            self.connection.insert_count += 1
            if self.connection.insert_count == self.connection.fail_on_insert:
                raise sqlite3.OperationalError('Synthetic insert failure')
        return self.cursor.execute(query.replace('%s', '?').replace(' FOR UPDATE', ''), params)

    def fetchone(self):
        row = self.cursor.fetchone()
        return dict(row) if row else None

    def fetchall(self):
        return [dict(row) for row in self.cursor.fetchall()]

    def close(self):
        self.cursor.close()


class Connection:
    def __init__(self, filename=':memory:'):
        self.database = sqlite3.connect(filename, check_same_thread=False)
        self.database.row_factory = sqlite3.Row
        self.database.executescript('''
            PRAGMA foreign_keys = ON;
            CREATE TABLE users (id INTEGER PRIMARY KEY);
            INSERT INTO users VALUES (42), (99);
            CREATE TABLE user_memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id),
                filename TEXT NOT NULL UNIQUE,
                caption TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
        ''')
        self.insert_count = 0
        self.fail_on_insert = None
        self.fail_commit = False

    def cursor(self, *args):
        return Cursor(self)

    def begin(self):
        self.database.execute('BEGIN')

    def commit(self):
        if self.fail_commit:
            raise sqlite3.OperationalError('Synthetic commit failure')
        self.database.commit()

    def rollback(self):
        self.database.rollback()


def image_upload(format='JPEG', mode='RGB'):
    stream = io.BytesIO()
    with Image.new(mode, (24, 16), 'teal') as image:
        options = {}
        if format == 'JPEG':
            exif = Image.Exif()
            exif[270] = 'Private image metadata'
            options['exif'] = exif
        image.save(stream, format=format, **options)
    stream.seek(0)
    return stream
