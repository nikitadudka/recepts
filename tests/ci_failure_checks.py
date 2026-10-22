"""Linux CI negative checks in a disposable copy, using synthetic data only."""
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]


def expect_failure(root, environment, marker):
    process = subprocess.Popen(['npm', 'test'], cwd=root, env=environment,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               text=True, start_new_session=True)
    try:
        output, _ = process.communicate(timeout=120)
        if process.returncode == 0 or marker not in output:
            raise AssertionError(f'Expected npm test failure containing {marker!r}\n{output}')
        try:
            os.killpg(process.pid, 0)
        except ProcessLookupError:
            pass
        else:
            raise AssertionError('Test failure left child processes running')
        if list(Path(environment['TMPDIR']).glob('kroshka-test-*')):
            raise AssertionError('Test failure left temporary databases behind')
        print(f'PASS: npm test failed as expected ({marker}); resources cleaned', flush=True)
    finally:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait(timeout=10)


if __name__ == '__main__':
    lifecycle = subprocess.Popen([sys.executable, str(ROOT / 'tests/server_lifecycle_test.py')],
                                 cwd=ROOT, start_new_session=True)
    try:
        if lifecycle.wait(timeout=90) != 0:
            raise AssertionError('Server lifecycle regression failed')
    finally:
        try:
            os.killpg(lifecycle.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        lifecycle.wait(timeout=10)
    with tempfile.TemporaryDirectory(prefix='kroshka-ci-negative-') as directory:
        base = Path(directory)
        root = base / 'source'
        shutil.copytree(ROOT, root, ignore=shutil.ignore_patterns(
            '.git', '.env', '.venv', 'node_modules', '__pycache__', 'data',
            '*.sqlite', '*.sqlite-wal', '*.sqlite-shm', 'test-results'))
        temporary = base / 'temporary'
        temporary.mkdir()
        environment = dict(os.environ, TMPDIR=str(temporary))
        environment['CHROMIUM_EXECUTABLE'] = str(base / 'missing-chromium')
        expect_failure(root, environment, 'executable doesn\'t exist')
        environment = dict(os.environ, TMPDIR=str(temporary))
        with (root / 'tests/install.test.js').open('a') as output:
            output.write("\ntest('A10 deliberate failure', () => { throw new Error('A10 failure sentinel'); });\n")
        expect_failure(root, environment, 'A10 failure sentinel')
