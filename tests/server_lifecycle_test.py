"""Reproduce a browser connection that outlives SIGTERM during smoke restart."""
import signal
import socket
from pathlib import Path
import unittest
import urllib.request

from smoke import RecipeBookTests


class ServerLifecycleTests(RecipeBookTests):
    def test_restart_with_incomplete_http_connection(self):
        old_server = type(self).server
        port = int(self.url.rsplit(':', 1)[1])
        with socket.create_connection(('127.0.0.1', port), timeout=5) as pending:
            # An incomplete request remains active while server.close() drains HTTP.
            pending.sendall(b'GET /healthz HTTP/1.1\r\nHost: localhost\r\n')
            urllib.request.urlopen(self.url + '/healthz', timeout=5).close()
            # Run the original browser/persistence scenario with that connection open.
            RecipeBookTests.test_14_server_restart_keeps_recipes_and_login(self)
            self.assertEqual(old_server.returncode, -signal.SIGKILL)
            self.assertIsNot(type(self).server, old_server)


if __name__ == '__main__':
    # Select only the added scenario, not the inherited smoke suite a second time.
    suite = unittest.TestSuite([ServerLifecycleTests('test_restart_with_incomplete_http_connection')])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if hasattr(ServerLifecycleTests, 'server'):
        if ServerLifecycleTests.server.poll() is None:
            raise AssertionError('Restart regression left the test server running')
        if Path(ServerLifecycleTests.data_dir.name).exists():
            raise AssertionError('Restart regression left its temporary database behind')
    raise SystemExit(not result.wasSuccessful())
