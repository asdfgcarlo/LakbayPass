"""Private photo memories, owned by the authenticated account."""
import io
import os
import re
import tempfile
import uuid
import warnings
from pathlib import Path

import MySQLdb.cursors
from PIL import Image, ImageOps, UnidentifiedImageError

MIN_IMAGES, MAX_IMAGES = 1, 3
MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_CAPTION_LENGTH = 300
MAX_IMAGE_PIXELS = 40_000_000
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS user_memories (
    id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    filename VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    caption VARCHAR(300) NOT NULL DEFAULT '',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_memory_filename (filename),
    KEY idx_user_memories (user_id, created_at, id),
    CONSTRAINT fk_memory_user FOREIGN KEY (user_id) REFERENCES users (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""


class MemoryError(Exception):
    def __init__(self, message, status_code=400):
        super().__init__(message)
        self.status_code = status_code


def install_memories(connection):
    cursor = connection.cursor()
    try:
        cursor.execute(SCHEMA_SQL)
        connection.commit()
    finally:
        cursor.close()


def _caption(value):
    if not isinstance(value, str) or len(value) > MAX_CAPTION_LENGTH:
        raise MemoryError('Enter a description of up to 300 characters.')
    return value.strip()


def _require_user(cursor, user_id, lock=False):
    if type(user_id) is not int or user_id <= 0:
        raise MemoryError('Log in again to manage your memories.', 401)
    cursor.execute('SELECT id FROM users WHERE id = %s' + (' FOR UPDATE' if lock else ''), (user_id,))
    if cursor.fetchone() is None:
        raise MemoryError('Log in again to manage your memories.', 401)


def _owned(cursor, user_id, memory_id, lock=False):
    cursor.execute('SELECT id, caption, created_at, filename FROM user_memories WHERE id = %s AND user_id = %s'
                   + (' FOR UPDATE' if lock else ''), (memory_id, user_id))
    return cursor.fetchone()


def list_memories(connection, user_id):
    cursor = connection.cursor(MySQLdb.cursors.DictCursor)
    try:
        _require_user(cursor, user_id)
        cursor.execute('SELECT id, caption, created_at, filename FROM user_memories '
                       'WHERE user_id = %s ORDER BY created_at DESC, id DESC', (user_id,))
        return list(cursor.fetchall())
    finally:
        cursor.close()


def get_memory(connection, user_id, memory_id):
    cursor = connection.cursor(MySQLdb.cursors.DictCursor)
    try:
        _require_user(cursor, user_id)
        return _owned(cursor, user_id, memory_id)
    finally:
        cursor.close()


def _normalize_image(upload):
    data = upload.read(MAX_IMAGE_BYTES + 1)
    if len(data) > MAX_IMAGE_BYTES:
        raise MemoryError('Each image must be 10 MB or smaller.', 413)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as source:
                if source.format not in {'JPEG', 'PNG', 'WEBP'}:
                    raise MemoryError('Please use JPG, PNG or WebP images.')
                if source.width * source.height > MAX_IMAGE_PIXELS:
                    raise MemoryError('This photo is too large to process. Choose a photo under 40 megapixels.')
                source.load()
                oriented = ImageOps.exif_transpose(source)
                alpha = 'A' in oriented.getbands() or 'transparency' in oriented.info
                converted = oriented.convert('RGBA' if alpha else 'RGB')
                # Fresh pixels strip EXIF/GPS and other embedded metadata.
                clean = Image.new(converted.mode, converted.size)
                try:
                    clean.paste(converted)
                    output = io.BytesIO()
                    clean.save(output, format='PNG' if alpha else 'JPEG', **({} if alpha else {'quality': 90}))
                    return output.getvalue(), '.png' if alpha else '.jpg'
                finally:
                    clean.close()
                    converted.close()
                    if oriented is not source:
                        oriented.close()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise MemoryError('An image is invalid or damaged. Choose a valid JPG, PNG or WebP photo.') from None


def _cleanup(paths):
    for path in paths:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass


def save_memories(connection, user_id, files, captions, storage_path):
    if len(files) < MIN_IMAGES:
        raise MemoryError('Please add at least 1 image to save your memories.')
    if len(files) > MAX_IMAGES:
        raise MemoryError('Please add no more than 3 images at a time.')
    if len(captions) != len(files):
        raise MemoryError('Include one description field for each image. Descriptions may be empty.')
    descriptions = [_caption(value) for value in captions]
    root = Path(storage_path)
    root.mkdir(parents=True, exist_ok=True)
    cleanup, staged, created = [], [], []
    cursor = connection.cursor(MySQLdb.cursors.DictCursor)
    transaction = False
    try:
        # Stage one decoded image at a time before opening a database transaction.
        for upload in files:
            image_bytes, extension = _normalize_image(upload)
            filename = uuid.uuid4().hex + extension
            descriptor, temporary = tempfile.mkstemp(prefix='.memory-', dir=root)
            temporary = Path(temporary)
            cleanup.append(temporary)
            with os.fdopen(descriptor, 'wb') as handle:
                handle.write(image_bytes)
            staged.append((temporary, root / filename, filename))
        connection.begin()
        transaction = True
        _require_user(cursor, user_id, lock=True)
        for (temporary, final, filename), caption in zip(staged, descriptions):
            cursor.execute('INSERT INTO user_memories (user_id, filename, caption) VALUES (%s, %s, %s)',
                           (user_id, filename, caption))
            memory_id = cursor.lastrowid
            cleanup.append(final)
            os.replace(temporary, final)
            created.append(_owned(cursor, user_id, memory_id))
        connection.commit()
        return created
    except Exception:
        try:
            if transaction:
                connection.rollback()
        finally:
            _cleanup(cleanup)
        raise
    finally:
        cursor.close()


def update_memory_caption(connection, user_id, memory_id, caption):
    description = _caption(caption)
    cursor = connection.cursor(MySQLdb.cursors.DictCursor)
    try:
        connection.begin()
        _require_user(cursor, user_id)
        memory = _owned(cursor, user_id, memory_id, lock=True)
        if memory is None:
            raise MemoryError('Memory not found.', 404)
        cursor.execute('UPDATE user_memories SET caption = %s WHERE id = %s AND user_id = %s',
                       (description, memory_id, user_id))
        connection.commit()
        memory['caption'] = description
        return memory
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()


def delete_memory(connection, user_id, memory_id, storage_path):
    cursor = connection.cursor(MySQLdb.cursors.DictCursor)
    original, tombstone = None, None
    try:
        connection.begin()
        _require_user(cursor, user_id)
        memory = _owned(cursor, user_id, memory_id, lock=True)
        if memory is None:
            raise MemoryError('Memory not found.', 404)
        if not re.fullmatch(r'[a-f0-9]{32}\.(jpg|png)', memory['filename']):
            raise MemoryError('This memory is unavailable.', 503)
        original = Path(storage_path) / memory['filename']
        if original.exists():
            tombstone = original.with_name('.deleted-' + uuid.uuid4().hex)
            os.replace(original, tombstone)
        cursor.execute('DELETE FROM user_memories WHERE id = %s AND user_id = %s', (memory_id, user_id))
        connection.commit()
    except Exception:
        try:
            connection.rollback()
        finally:
            # A lost connection can make rollback raise too. Always restore the
            # private photo so a surviving database row can still serve it.
            if tombstone is not None and tombstone.exists():
                os.replace(tombstone, original)
        raise
    else:
        if tombstone is not None:
            _cleanup([tombstone])
    finally:
        cursor.close()
