"""A22: literal HTTP bodies, isolated SQLite books, no browser or personal data."""
import contextlib
import http.client
import json
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import tempfile
import time
import unittest


ROOT = Path(__file__).resolve().parents[1]
PASSWORD = 'a22-synthetic-password'
SMALL_LIMIT = 4096
LIBRARY_LIMIT = 64 * 1024 * 1024
CATALOG_ID = json.loads((ROOT / 'catalog/recipes.json').read_text())[0]['id']


class Book:
    def __init__(self, directory):
        self.directory = directory
        self.cookie = None
        self.process = None

    def start(self):
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            self.port = sock.getsockname()[1]
        environment = dict(os.environ, HOST='127.0.0.1', PORT=str(self.port), DATA_DIR=self.directory)
        environment.pop('FAMILY_PASSWORD', None)
        environment.pop('PUBLIC_URL', None)
        self.process = subprocess.Popen(['node', 'server.js'], cwd=ROOT, env=environment,
                                        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        for _ in range(100):
            if self.process.poll() is not None:
                raise AssertionError(self.process.stderr.read().decode())
            try:
                if self.request('GET', '/api/session')[0] == 200:
                    return
            except OSError:
                time.sleep(.05)
        raise AssertionError('A22 server did not start')

    def stop(self):
        if self.process is not None:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=10)
            self.process.stderr.close()
            self.process = None

    def request(self, method, path, body=b'', media='application/json', authenticated=True,
                headers=None, chunked=False):
        request_headers = dict(headers or {})
        if media is not None:
            request_headers['Content-Type'] = media
        if authenticated and self.cookie:
            request_headers['Cookie'] = self.cookie
        connection = http.client.HTTPConnection('127.0.0.1', self.port, timeout=20)
        try:
            payload = (body[i:i + 65536] for i in range(0, len(body), 65536)) if chunked else body
            connection.request(method, path, body=payload, headers=request_headers, encode_chunked=chunked)
            response = connection.getresponse()
            result = (response.status, json.loads(response.read()), dict(response.getheaders()))
            if response.getheader('Set-Cookie') and response.status == 200:
                self.cookie = response.getheader('Set-Cookie').split(';')[0]
            return result
        finally:
            connection.close()

    def login(self, setup=False):
        response = self.request('POST', '/api/setup' if setup else '/api/login',
                                json.dumps({'password': PASSWORD}).encode())
        assert response[0] == 200, response[1]

    def library(self):
        status, data, _ = self.request('GET', '/api/library')
        assert status == 200, data
        return data

    def stored(self):
        with sqlite3.connect(f'file:{self.directory}/recipes.sqlite?mode=ro', uri=True) as db:
            return tuple(db.execute(f'SELECT * FROM {table} ORDER BY 1').fetchall()
                         for table in ('recipes', 'settings', 'sessions'))


@contextlib.contextmanager
def book(setup=True):
    with tempfile.TemporaryDirectory(prefix='kroshka-test-a22-') as directory:
        instance = Book(directory)
        try:
            instance.start()
            if setup:
                instance.login(setup=True)
            yield instance
        finally:
            instance.stop()


class JsonApiTests(unittest.TestCase):
    invalid_bodies = [b'null', b'[]', b'[{}]', b'"text"', b'0', b'42', b'true', b'false',
                      b'{', b'', b' \n\t', b'{}{}', b'{"password":"secret",}', b'{"x":"\xff"}']
    invalid_media = [None, 'text/plain', 'application/jsonx', 'application/jsonp',
                     'application/json; charset=iso-8859-1']

    def rejected(self, instance, method, path, payload, expected=400, **kwargs):
        before = instance.stored()
        snapshot = instance.library() if instance.cookie else None
        status, data, headers = instance.request(method, path, payload, **kwargs)
        self.assertEqual(status, expected, (method, path, status, data))
        self.assertEqual(set(data), {'error'})
        self.assertIsInstance(data['error'], str)
        self.assertTrue(data['error'])
        self.assertEqual(headers['Content-Type'], 'application/json; charset=utf-8')
        self.assertEqual(headers['Cache-Control'], 'no-store')
        self.assertNotIn('Set-Cookie', headers)
        self.assertTrue(before == instance.stored(), 'Rejected request changed stored data/access')
        if snapshot is not None:
            self.assertEqual(instance.library(), snapshot)

    def test_setup_matrix_and_next_valid_request(self):
        cases = [(payload, 400, {}) for payload in self.invalid_bodies]
        cases += [(b'{}', 415, {'media': media}) for media in self.invalid_media]
        cases += [(b' ' * (SMALL_LIMIT + 1), 413, {})]
        for payload, status, options in cases:
            with self.subTest(payload=payload[:50], options=options), book(setup=False) as instance:
                self.rejected(instance, 'POST', '/api/setup', payload, status, **options)
                self.assertEqual(instance.request('GET', '/api/session')[1],
                                 {'authenticated': False, 'needsSetup': True, 'canSetup': True})
                instance.login(setup=True)
                self.assertTrue(instance.request('GET', '/api/session')[1]['authenticated'])

    def test_all_other_mutations_matrix_and_preservation(self):
        routes = [('POST', '/api/login'), ('POST', '/api/logout'),
                  ('POST', '/api/catalog/{catalog}/save'), ('POST', '/api/trials/{trial}/promote'),
                  ('DELETE', '/api/trials/{trial}'), ('PUT', '/api/library')]
        for method, template in routes:
            with self.subTest(route=template), book() as instance:
                saved = instance.library()
                saved['recipes'][0].update(image='data:image/png;base64,aGVsbG8=',
                                           sourceTitle='A22', sourceUrl='https://example.com/a22')
                self.assertEqual(instance.request('PUT', '/api/library', json.dumps(saved).encode())[0], 200)
                catalog = CATALOG_ID
                trial = instance.request('POST', f'/api/catalog/{catalog}/save', b'{"destination":"trial"}')[1]['recipe']['id']
                path = template.format(catalog=catalog, trial=trial)
                for payload in self.invalid_bodies:
                    if path == '/api/logout' and not payload:
                        continue
                    with self.subTest(payload=payload):
                        self.rejected(instance, method, path, payload)
                        if path == '/api/login':
                            instance.login()  # Reset the existing login limiter between cases.
                for media in self.invalid_media:
                    with self.subTest(media=media):
                        self.rejected(instance, method, path, b'{}', 415, media=media)
                if path == '/api/library':
                    for payload in [b'{}', b'{"revision":1,"recipes":null}',
                                    b'{"revision":1,"recipes":[null]}']:
                        self.rejected(instance, method, path, payload)
                    payload = json.dumps(instance.library()).encode()
                elif path == '/api/login':
                    payload = json.dumps({'password': PASSWORD}).encode()
                else:
                    payload = b'{}'
                self.assertIn(instance.request(method, path, payload)[0], (200, 201))

    def test_byte_limits_all_routes_and_chunked_transport(self):
        for route in ['setup', 'login', 'logout', 'save', 'promote', 'delete', 'library']:
            with self.subTest(route=route), book(setup=route != 'setup') as instance:
                method = 'POST'
                path = '/api/' + route
                data = {'password': PASSWORD} if route in ('setup', 'login') else {}
                limit = SMALL_LIMIT
                if route in ('save', 'promote', 'delete'):
                    catalog = CATALOG_ID
                    trial = instance.request('POST', f'/api/catalog/{catalog}/save', b'{"destination":"trial"}')[1]['recipe']['id']
                    path = f'/api/catalog/{catalog}/save' if route == 'save' else f'/api/trials/{trial}' + ('/promote' if route == 'promote' else '')
                    method = 'DELETE' if route == 'delete' else 'POST'
                if route == 'library':
                    method, limit = 'PUT', LIBRARY_LIMIT
                    data = instance.library()
                data['ignored'] = 'ёж'  # Boundaries count UTF-8 bytes, not characters.
                payload = json.dumps(data, ensure_ascii=False).encode()
                payload += b' ' * (limit - len(payload))
                self.assertEqual(len(payload), limit)
                # Invalid syntax within each boundary must be 400, never 413.
                for size in (limit - 1, limit):
                    self.rejected(instance, method, path, b'{' + b' ' * (size - 1))
                self.rejected(instance, method, path, payload + b' ', 413)
                self.rejected(instance, method, path, payload + b' ', 413, chunked=True)
                status, result, _ = instance.request(method, path, payload, chunked=True,
                                                     media='Application/JSON; charset="UTF-8"')
                self.assertIn(status, (200, 201), result)
                self.assertEqual(instance.request('GET', '/api/session')[0], 200)

    def test_logout_empty_and_object_compatibility(self):
        with book() as instance:
            for payload in [b'', b'{}']:
                before = instance.library()
                old_cookie = instance.cookie
                self.assertEqual(instance.request('POST', '/api/logout', payload)[0], 200)
                instance.cookie = old_cookie
                self.assertFalse(instance.request('GET', '/api/session')[1]['authenticated'])
                instance.login()
                self.assertEqual(instance.library(), before)

    def test_guard_order_rate_limit_conflict_and_stale_trial(self):
        with book() as instance:
            self.rejected(instance, 'PUT', '/api/library', b'null', 403,
                          media='text/plain', headers={'Origin': 'http://other.invalid'})
            self.rejected(instance, 'PUT', '/api/library', b'null', 415,
                          media='application/jsonx', authenticated=False)
            self.rejected(instance, 'PUT', '/api/library', b'null', 401, authenticated=False)
            self.rejected(instance, 'POST', '/api/setup', b'null', 409)
            self.rejected(instance, 'POST', '/api/catalog/missing-a22/save', b'null', 404)
            self.rejected(instance, 'POST', '/api/trials/missing-a22/promote', b'null', 400)
            self.rejected(instance, 'POST', '/api/trials/missing-a22/promote', b'{}', 404)
            self.rejected(instance, 'POST', '/api/login', b'{}', 401)
            for _ in range(19):
                self.rejected(instance, 'POST', '/api/login', b'null', 400)
            self.rejected(instance, 'POST', '/api/login', b'null', 429)
            # A new process resets only the in-memory limiter, not the book or sessions.
            before = instance.stored()
            instance.stop()
            instance.start()
            self.assertTrue(before == instance.stored())
            instance.login()
            snapshot = instance.library()
            self.assertEqual(instance.request('PUT', '/api/library', json.dumps(snapshot).encode())[0], 200)
            self.rejected(instance, 'PUT', '/api/library', json.dumps(snapshot).encode(), 409)
            catalog = CATALOG_ID
            trial = instance.request('POST', f'/api/catalog/{catalog}/save', b'{"destination":"trial"}')[1]['recipe']['id']
            self.assertEqual(instance.request('POST', f'/api/trials/{trial}/promote', b'{}')[0], 200)
            self.rejected(instance, 'DELETE', f'/api/trials/{trial}', b'{}', 409)

    def test_interrupted_body_does_not_mutate_or_stop_server(self):
        with book() as instance:
            before = instance.stored()
            with socket.create_connection(('127.0.0.1', instance.port), timeout=5) as stream:
                stream.sendall((f'PUT /api/library HTTP/1.1\r\nHost: 127.0.0.1:{instance.port}\r\n'
                                f'Cookie: {instance.cookie}\r\nContent-Type: application/json\r\n'
                                'Content-Length: 1000\r\n\r\n{"revision":').encode())
                stream.shutdown(socket.SHUT_WR)
                while stream.recv(4096):
                    pass
            self.assertTrue(before == instance.stored())
            self.assertEqual(instance.request('PUT', '/api/library', json.dumps(instance.library()).encode())[0], 200)

    def test_legacy_recipes_photos_sources_and_restart(self):
        with book() as instance:
            snapshot = instance.library()
            recipes = snapshot['recipes']
            # Historical optional fields stay optional and old method aliases remain accepted.
            recipes[0]['cookingMethods'] = ['Сковородка', 'Духовка']
            recipes[0]['image'] = 'data:image/png;base64,aGVsbG8='
            recipes[0]['sourceTitle'] = 'Синтетический источник A22'
            recipes[0]['sourceUrl'] = 'https://example.com/a22'
            self.assertNotIn('steps', recipes[0])
            self.assertNotIn('shelf', recipes[0])
            self.assertEqual(instance.request('PUT', '/api/library', json.dumps(snapshot).encode())[0], 200)
            saved = instance.library()
            self.assertEqual(saved['recipes'], recipes)
            self.rejected(instance, 'PUT', '/api/library', b'null')
            instance.stop()
            instance.start()
            self.assertEqual(instance.library(), saved)

    def test_storage_errors_remain_500_and_do_not_replace_data(self):
        with book() as instance:
            snapshot = instance.library()
            filename = Path(instance.directory) / 'recipes.sqlite'
            # A real SQLite write failure after DELETEs must roll back the whole PUT.
            with sqlite3.connect(filename) as db:
                db.execute("CREATE TRIGGER a22_write_failure BEFORE INSERT ON recipes "
                           "BEGIN SELECT RAISE(ABORT, 'synthetic write failure'); END")
            update = dict(snapshot, recipes=snapshot['recipes'][1:])
            self.rejected(instance, 'PUT', '/api/library', json.dumps(update).encode(), 500)
            with sqlite3.connect(filename) as db:
                db.execute('DROP TRIGGER a22_write_failure')
                db.execute('UPDATE recipes SET content=? WHERE id=?', ('{broken', snapshot['recipes'][0]['id']))
            before = instance.stored()
            status, data, _ = instance.request('GET', '/api/library')
            self.assertEqual(status, 500)
            self.assertIsInstance(data['error'], str)
            self.assertTrue(before == instance.stored(), 'Read failure replaced damaged stored JSON')
            with sqlite3.connect(filename) as db:
                db.execute('UPDATE recipes SET content=? WHERE id=?',
                           (json.dumps(snapshot['recipes'][0]), snapshot['recipes'][0]['id']))
            self.assertEqual(instance.library(), snapshot)
            self.assertEqual(instance.request('PUT', '/api/library', json.dumps(snapshot).encode())[0], 200)


if __name__ == '__main__':
    unittest.main()
