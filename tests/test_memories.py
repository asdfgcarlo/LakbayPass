"""Real upload, persistence, privacy and failure recovery through Flask routes."""
import io
import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import MySQLdb
from PIL import Image

import app as lakbay
import memories
from memories_fixture import Connection, image_upload


class MemoriesTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.connection = Connection()
        self.addCleanup(self.connection.database.close)
        database = patch.object(lakbay, 'mysql', SimpleNamespace(connection=self.connection))
        database.start()
        self.addCleanup(database.stop)
        config = patch.dict(lakbay.app.config, TESTING=True, MEMORIES_UPLOAD_FOLDER=str(self.root))
        config.start()
        self.addCleanup(config.stop)
        self.client = lakbay.app.test_client()
        self.sign_in()

    def sign_in(self, user_id=42):
        with self.client.session_transaction() as session:
            session.clear()
            session.update(loggedin=True, id=user_id, username='Traveler', memories_csrf='test-token')

    def upload(self, count=3, captions=None, invalid=None, token='test-token'):
        images = [(image_upload(), f'photo-{i}.jpg') for i in range(count)]
        if invalid is not None:
            images[-1] = (io.BytesIO(invalid), 'fake.jpg')
        response = self.client.post('/api/memories', data={
            'images': images, 'captions': captions if captions is not None else ['A photo'] * count,
            'user_id': '99',
        }, headers={'X-CSRF-Token': token})
        self.addCleanup(response.close)
        self.addCleanup(response.request.input_stream.close)
        return response

    def count(self):
        return self.connection.database.execute('SELECT COUNT(*) FROM user_memories').fetchone()[0]

    def test_minimum_and_maximum_enforced_on_server(self):
        for count, message in (
            (0, 'Please add at least 1 image to save your memories.'),
            (4, 'Please add no more than 3 images at a time.'),
        ):
            with self.subTest(count=count):
                response = self.upload(count)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json['message'], message)
        self.assertEqual(self.count(), 0)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_one_two_and_three_image_submissions_persist(self):
        total = 0
        for count in (1, 2, 3):
            with self.subTest(count=count):
                response = self.upload(count)
                self.assertEqual(response.status_code, 201)
                self.assertEqual(len(response.json['memories']), count)
                total += count
                self.assertEqual(self.count(), total)
                self.assertEqual(len(list(self.root.iterdir())), total)
                self.assertEqual(len(self.client.get('/api/memories').json['memories']), total)

    def test_batch_persists_captions_private_images_and_strips_metadata(self):
        response = self.upload(captions=['First', '', '<script>not code</script>'])
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.headers['Cache-Control'], 'no-store')
        self.assertEqual([m['caption'] for m in response.json['memories']], ['First', '', '<script>not code</script>'])
        self.assertEqual(self.count(), 3)
        self.assertEqual(len(self.client.get('/api/memories').json['memories']), 3)
        entry = response.json['memories'][0]
        self.assertNotIn('filename', entry)
        photo = self.client.get(entry['image_url'])
        self.assertEqual(photo.status_code, 200)
        self.assertIn('no-store', photo.headers['Cache-Control'])
        with Image.open(io.BytesIO(photo.data)) as image:
            self.assertEqual(len(image.getexif()), 0)
        photo.close()
        self.assertEqual(list(self.connection.database.execute('SELECT DISTINCT user_id FROM user_memories'))[0][0], 42)

    def test_png_transparency_and_webp_are_supported(self):
        created = memories.save_memories(self.connection, 42,
            [image_upload('PNG', 'RGBA'), image_upload('WEBP'), image_upload()], ['', '', ''], self.root)
        self.assertEqual(len(created), 3)
        with Image.open(self.root / created[0]['filename']) as image:
            self.assertEqual(image.mode, 'RGBA')

    def test_invalid_or_oversized_file_rejects_entire_batch(self):
        for invalid, code in ((b'not an image', 400), (b'x' * (memories.MAX_IMAGE_BYTES + 1), 413)):
            response = self.upload(invalid=invalid)
            self.assertEqual(response.status_code, code)
            self.assertEqual(self.count(), 0)
            self.assertEqual(list(self.root.iterdir()), [])

    def test_unsupported_image_format_rejected_despite_filename(self):
        response = self.client.post('/api/memories', data={
            'images': [(image_upload('GIF'), f'{i}.jpg') for i in range(3)], 'captions': ['', '', '']
        }, headers={'X-CSRF-Token': 'test-token'})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.count(), 0)

    def test_caption_length_and_alignment(self):
        for captions in (['short', 'short'], ['x' * 301, '', '']):
            self.assertEqual(self.upload(captions=captions).status_code, 400)
        self.assertEqual(self.count(), 0)

    def test_every_write_requires_csrf_before_service_calls(self):
        with patch.object(lakbay, 'save_memories') as save, patch.object(lakbay, 'update_memory_caption') as update, patch.object(lakbay, 'delete_memory') as delete:
            self.assertEqual(self.upload(token='wrong').status_code, 403)
            self.assertEqual(self.client.patch('/api/memories/1', json={'caption': ''}).status_code, 403)
            self.assertEqual(self.client.delete('/api/memories/1').status_code, 403)
            for service in (save, update, delete):
                service.assert_not_called()

    def test_unauthenticated_and_invalid_session_cannot_access_memories(self):
        for user_id in (None, '42', 0):
            self.sign_in(user_id)
            for method, path in (('get', '/api/memories'), ('post', '/api/memories'), ('patch', '/api/memories/1'), ('delete', '/api/memories/1'), ('get', '/memories/1/image')):
                response = getattr(self.client, method)(path)
                self.assertEqual(response.status_code, 401)
                self.assertIn('no-store', response.headers['Cache-Control'])

    def test_other_account_cannot_read_edit_or_delete(self):
        entry = self.upload().json['memories'][0]
        self.sign_in(99)
        self.assertEqual(self.client.get('/api/memories?user_id=42').json['memories'], [])
        self.assertEqual(self.client.get(entry['image_url']).status_code, 404)
        endpoint = f'/api/memories/{entry["id"]}'
        headers = {'X-CSRF-Token': 'test-token'}
        self.assertEqual(self.client.patch(endpoint, json={'caption': 'stolen'}, headers=headers).status_code, 404)
        self.assertEqual(self.client.delete(endpoint, headers=headers).status_code, 404)
        self.assertEqual(self.count(), 3)

    def test_owner_can_edit_and_delete_after_other_photos_deleted(self):
        entries = self.upload().json['memories']
        headers = {'X-CSRF-Token': 'test-token'}
        for entry in entries:
            endpoint = f'/api/memories/{entry["id"]}'
            response = self.client.patch(endpoint, json={'caption': 'New description', 'user_id': 99}, headers=headers)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json['memory']['caption'], 'New description')
            self.assertEqual(self.client.delete(endpoint, headers=headers).status_code, 200)
        self.assertEqual(self.count(), 0)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_malformed_updates_are_rejected(self):
        for payload in ({}, [], {'caption': 3}, {'caption': None}, {'caption': 'x' * 301}):
            response = self.client.patch('/api/memories/1', json=payload, headers={'X-CSRF-Token': 'test-token'})
            self.assertEqual(response.status_code, 400)

    def test_missing_account_cannot_create_photos(self):
        self.sign_in(1000)
        self.assertEqual(self.upload().status_code, 401)
        self.assertEqual(self.count(), 0)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_database_failure_removes_all_rows_and_staged_files(self):
        self.connection.fail_on_insert = 2
        with self.assertRaises(sqlite3.OperationalError):
            memories.save_memories(self.connection, 42, [image_upload() for _ in range(3)], ['', '', ''], self.root)
        self.assertEqual(self.count(), 0)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_disk_failure_removes_all_rows_and_staged_files(self):
        with patch.object(memories.os, 'replace', side_effect=OSError('Synthetic disk failure')):
            with self.assertLogs(lakbay.app.logger, level='ERROR'):
                self.assertEqual(self.upload().status_code, 503)
        self.assertEqual(self.count(), 0)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_delete_commit_failure_restores_photo_and_row(self):
        entry = self.upload().json['memories'][0]
        self.connection.fail_commit = True
        with self.assertRaises(sqlite3.OperationalError):
            memories.delete_memory(self.connection, 42, entry['id'], self.root)
        self.assertEqual(self.count(), 3)
        self.assertEqual(len(list(self.root.iterdir())), 3)
        response = self.client.get(entry['image_url'])
        self.assertEqual(response.status_code, 200)
        response.close()

    def test_delete_restores_photo_when_connection_is_lost_during_rollback(self):
        entry = self.upload().json['memories'][0]
        self.connection.fail_commit = True
        def failed_rollback():
            self.connection.database.rollback()
            raise MySQLdb.OperationalError(2006, 'Synthetic lost connection')
        with patch.object(self.connection, 'rollback', side_effect=failed_rollback):
            with self.assertLogs(lakbay.app.logger, level='ERROR'):
                response = self.client.delete(f'/api/memories/{entry["id"]}', headers={'X-CSRF-Token': 'test-token'})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(self.count(), 3)
        self.assertEqual(len(list(self.root.iterdir())), 3)
        self.assertFalse(list(self.root.glob('.deleted-*')))
        response = self.client.get(entry['image_url'])
        self.assertEqual(response.status_code, 200)
        response.close()


if __name__ == '__main__':
    unittest.main()
