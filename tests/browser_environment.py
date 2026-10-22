"""Report and launch the exact Chromium selected for the test run."""
import json
import os
from pathlib import Path

import playwright
from playwright.sync_api import sync_playwright


if __name__ == '__main__':
    manifest = Path(playwright.__file__).parent / 'driver/package/browsers.json'
    chromium = next(b for b in json.loads(manifest.read_text())['browsers']
                    if b['name'] == 'chromium')
    print(f"Playwright Chromium: {chromium['browserVersion']}, build {chromium['revision']}", flush=True)
    executable = os.environ['CHROMIUM_EXECUTABLE']
    if not Path(executable).is_file():
        raise RuntimeError('Selected Chromium executable is missing')
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, executable_path=executable)
        try:
            print(f'Actual browser: {browser.version}; executable: {executable}', flush=True)
        finally:
            browser.close()
