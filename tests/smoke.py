"""Real-browser checks. Requires: pip install playwright; Chromium or playwright install chromium."""
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import time
import tempfile
import unittest
import urllib.error
import urllib.request
from playwright.sync_api import sync_playwright, expect
from contrast import assert_text_contrast, measurements, artwork_measurements, ratio

ROOT = Path(__file__).resolve().parents[1]


class RecipeBookTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        cls.url = f'http://127.0.0.1:{port}'
        environment = os.environ.copy()
        environment['PORT'] = str(port)
        cls.data_dir = tempfile.TemporaryDirectory(prefix='kroshka-test-')
        cls.addClassCleanup(cls.data_dir.cleanup)
        environment['DATA_DIR'] = cls.data_dir.name
        environment['HOST'] = '127.0.0.1'
        environment.pop('PUBLIC_URL', None)
        environment['KROSHKA_HOSTNAME'] = 'kroshka-test.local'
        environment.pop('FAMILY_PASSWORD', None)
        cls.environment = environment
        cls.server = subprocess.Popen(['node', 'server.js'], cwd=ROOT, env=environment, stdout=subprocess.DEVNULL)
        cls.addClassCleanup(cls.stop_server)
        for _ in range(50):
            try:
                urllib.request.urlopen(cls.url, timeout=1).close()
                break
            except OSError:
                time.sleep(.1)
        else:
            raise RuntimeError('Test server did not start')
        cls.playwright = sync_playwright().start()
        cls.addClassCleanup(cls.playwright.stop)
        executable = os.environ.get('CHROMIUM_EXECUTABLE') or shutil.which('chromium') or shutil.which('google-chrome')
        cls.browser = cls.playwright.chromium.launch(headless=True, **({'executable_path': executable} if executable else {}))
        cls.addClassCleanup(cls.browser.close)
        cls.password = 'test-family-password'
        context = cls.browser.new_context()
        try:
            response = context.request.post(cls.url + '/api/setup', data={'password': cls.password})
            assert response.status == 200, response.text()
        finally:
            context.close()
        cls.seeds = json.loads((ROOT / 'recipes.seed.json').read_text())

    @classmethod
    def stop_server(cls):
        if cls.server.poll() is None:
            cls.server.terminate()
            try:
                cls.server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                # Browser connections can keep graceful HTTP shutdown pending.
                print('Test server did not drain in 10s; killing before cleanup/restart', flush=True)
                cls.server.kill()
                cls.server.wait(timeout=10)

    def setUp(self):
        self.context = self.browser.new_context(viewport={'width': 1440, 'height': 1000})
        self.addCleanup(self.context.close)
        response = self.context.request.post(self.url + '/api/login', data={'password': self.password})
        self.assertEqual(response.status, 200)
        snapshot = self.context.request.get(self.url + '/api/library').json()
        self.assertEqual(self.context.request.put(self.url + '/api/library', data={'revision': snapshot['revision'], 'recipes': self.seeds}).status, 200)
        self.page = self.context.new_page()
        self.errors = []
        self.page.on('pageerror', lambda error: self.errors.append(str(error)))
        self.page.goto(self.url, wait_until='networkidle')
        expect(self.page.locator('.recipe-card')).to_have_count(8)

    def tearDown(self):
        self.assertEqual(self.errors, [])

    def titles(self):
        return self.page.locator('.card-title').all_text_contents()

    def fill_recipe(self, title='Новый суп с чечевицей'):
        self.page.locator('#add-recipe').click()
        form = self.page.locator('#recipe-form')
        form.locator('[name=title]').fill(title)
        form.locator('[name=time]').fill('22')
        form.locator('.step-text').first.fill('Промыть чечевицу.')
        self.page.locator('#add-step').click()
        form.locator('.step-text').nth(1).fill('Добавить лук и варить до готовности.')
        self.page.locator('#add-ingredient').click()
        names = form.locator('.ingredient-name')
        names.nth(0).fill('Чечевица')
        names.nth(1).fill('Лук')
        amounts = form.locator('.ingredient-amount')
        amounts.nth(0).fill('200')
        amounts.nth(1).fill('100')
        return form

    def save(self, form):
        form.locator('[type=submit]').click()
        expect(self.page.locator('#editor-dialog')).not_to_be_visible()

    def test_01_search_requires_all_ingredients_and_accepts_word_forms(self):
        search = self.page.locator('#search')
        for query in ['чечевица', 'ЧЕЧЕВИЦА и ЛУК', 'чечевицей, луком']:
            search.fill(query)
            expect(self.page.locator('.recipe-card')).to_have_count(2)
        search.fill('чечевица и авокадо')
        expect(self.page.locator('.recipe-card')).to_have_count(0)
        expect(self.page.locator('#empty-state')).to_be_visible()
        self.page.locator('#empty-action').click()
        expect(self.page.locator('.recipe-card')).to_have_count(8)

    def test_02_categories_quick_filters_and_sorting(self):
        self.page.locator('[data-quick=fast]').click()
        expect(self.page.locator('.recipe-card')).to_have_count(6)
        self.page.locator('[data-quick=protein]').click()
        expect(self.page.locator('.recipe-card')).to_have_count(4)
        self.page.locator('[data-quick=all]').click()
        self.page.locator('#filter-toggle').click()
        self.page.locator('#filter-meal').select_option('Завтрак')
        expect(self.page.locator('.recipe-card')).to_have_count(2)
        self.page.locator('#filter-macro').select_option('Углеводное')
        self.assertEqual(self.titles(), ['Овсянка с ягодами'])
        self.page.locator('#reset-filters').click()
        self.page.locator('#filter-meat').select_option('С мясом')
        self.assertEqual(self.titles(), ['Боул с курицей и киноа'])
        self.page.locator('#reset-filters').click()
        for mode, first in [('time', 'Творожный боул с ягодами'), ('protein', 'Лосось с овощами'), ('fat', 'Тост с авокадо и яйцом'), ('carbs', 'Овсянка с ягодами')]:
            self.page.locator('#sort').select_option(mode)
            self.assertEqual(self.titles()[0], first)

    def test_03_create_edit_upload_and_persistence(self):
        form = self.fill_recipe()
        form.locator('#nutrition-details summary').click()
        form.locator('[name=protein]').fill('21')
        self.page.locator('#image-upload').set_input_files(ROOT / 'assets/food-grid.png')
        expect(self.page.locator('#image-preview img')).to_be_visible()
        self.save(form)
        expect(self.page.locator('.recipe-card')).to_have_count(9)
        self.page.reload(wait_until='networkidle')
        expect(self.page.locator('.recipe-card')).to_have_count(9)
        self.assertEqual(self.titles()[0], 'Новый суп с чечевицей')
        self.page.locator('.card-open').first.click()
        expect(self.page.locator('.detail-ingredients li')).to_have_count(2)
        expect(self.page.locator('.detail-photo img')).to_be_visible()
        self.page.locator('[data-edit]').click()
        form = self.page.locator('#recipe-form')
        expect(form.locator('[name=protein]')).to_have_value('21')
        form.locator('[name=title]').fill('Суп по семейному рецепту')
        self.save(form)
        self.assertEqual(self.titles()[0], 'Суп по семейному рецепту')
        self.page.reload(wait_until='networkidle')
        expect(self.page.locator('.card-title').first).to_have_text('Суп по семейному рецепту')

    def test_04_favorites_and_both_views(self):
        self.page.locator('[data-favorite=lentil-soup]').click()
        expect(self.page.locator('#favorite-count')).to_have_text('3')
        self.page.locator('[data-collection=favorites]').click()
        expect(self.page.locator('.recipe-card')).to_have_count(3)
        self.page.locator('#list-view').click()
        expect(self.page.locator('#recipe-grid')).to_have_class('recipe-grid list-view')
        self.page.locator('#grid-view').click()
        expect(self.page.locator('#recipe-grid')).to_have_class('recipe-grid')
        self.page.reload(wait_until='networkidle')
        expect(self.page.locator('#favorite-count')).to_have_text('3')

    def test_05_delete_cancel_and_persist(self):
        self.page.locator('[data-open=lentil-soup]').click()
        self.page.once('dialog', lambda dialog: dialog.dismiss())
        self.page.locator('[data-delete]').click()
        expect(self.page.locator('#recipe-dialog')).to_be_visible()
        self.page.once('dialog', lambda dialog: dialog.accept())
        self.page.locator('[data-delete]').click()
        expect(self.page.locator('.recipe-card')).to_have_count(7)
        self.page.reload(wait_until='networkidle')
        expect(self.page.locator('.recipe-card')).to_have_count(7)
        self.assertNotIn('Чечевичный суп с овощами', self.titles())

    def test_06_export_contains_full_recipes(self):
        with self.page.expect_download() as info:
            self.page.locator('#export-data').click()
        data = json.loads(Path(info.value.path()).read_text())
        self.assertEqual(data['version'], 1)
        self.assertEqual(len(data['recipes']), 8)
        self.assertEqual(next(r for r in data['recipes'] if r['id'] == 'lentil-soup')['ingredients'][0]['name'], 'Красная чечевица')

    def test_07_ai_removed_and_step_editor_keyboard(self):
        self.page.locator('#add-recipe').click()
        self.assertEqual(self.page.locator('#generate-image, #ai-status, .breadcrumb').count(), 0)
        self.page.locator('.ingredient-name').first.fill('Лук')
        self.page.locator('.ingredient-name').first.press('Enter')
        expect(self.page.locator('.ingredient-row')).to_have_count(2)
        self.page.locator('.step-text').first.fill('Первый шаг')
        self.page.locator('#add-step').click()
        self.page.locator('.step-text').nth(1).fill('Второй шаг')
        self.page.locator('[data-step-action=up]').nth(1).click()
        expect(self.page.locator('.step-text').first).to_have_value('Второй шаг')
        self.page.locator('[data-step-action=delete]').nth(1).click()
        expect(self.page.locator('.step-row')).to_have_count(1)

    def test_08_responsive_layout_assets_and_dialogs(self):
        for width in [320, 390, 680, 768, 1024, 1440]:
            self.page.set_viewport_size({'width': width, 'height': 900})
            self.assertLessEqual(self.page.evaluate('document.documentElement.scrollWidth'), width, f'Horizontal overflow at {width}px')
            expect(self.page.locator('#add-recipe')).to_be_visible()
            self.page.locator('#add-recipe').click()
            self.assertLessEqual(self.page.locator('#editor-dialog').evaluate('(el) => el.scrollWidth'), width)
            self.page.keyboard.press('Escape')
            expect(self.page.locator('#editor-dialog')).not_to_be_visible()
        self.assertTrue(self.page.evaluate('document.fonts.check(\'400 14px "Golos Text"\')'))
        for name in ['food-grid.png', 'golostext-GolosText%5Bwght%5D.ttf', 'manrope-Manrope%5Bwght%5D.ttf']:
            self.assertEqual(self.page.request.get(self.url + '/assets/' + name).status, 200)

    def test_09_safe_text_unknown_nutrition_and_taste_units(self):
        form = self.fill_recipe('<img src=x onerror=alert(1)>')
        form.locator('.ingredient-unit').nth(1).select_option('по вкусу')
        expect(form.locator('.ingredient-amount').nth(1)).to_be_disabled()
        self.save(form)
        expect(self.page.locator('.card-title').first).to_have_text('<img src=x onerror=alert(1)>')
        self.assertEqual(self.page.locator('.card-title img').count(), 0)
        self.page.locator('#sort').select_option('protein')
        self.assertEqual(self.titles()[-1], '<img src=x onerror=alert(1)>')
        self.page.locator('.card-open').last.click()
        expect(self.page.locator('.detail-nutrition strong').first).to_have_text('—')

    def test_10_server_failure_keeps_editor_and_existing_data(self):
        form = self.fill_recipe()
        self.page.route('**/api/library', lambda route: route.fulfill(status=507, content_type='application/json', body=json.dumps({'error': 'Недостаточно места для сохранения.'})) if route.request.method == 'PUT' else route.continue_())
        form.locator('[type=submit]').click()
        expect(self.page.locator('#form-error')).to_contain_text('Недостаточно места')
        expect(self.page.locator('#editor-dialog')).to_be_visible()
        self.page.reload(wait_until='networkidle')
        expect(self.page.locator('.recipe-card')).to_have_count(8)

    def test_11_server_hides_private_files_and_handles_api_methods(self):
        for route in ['/.env', '/server.js', '/package.json', '/.git/config', '/data/recipes.sqlite', '/recipes.seed.json']:
            self.assertEqual(self.page.request.get(self.url + route).status, 404)
        self.assertEqual(self.page.request.post(self.url + '/api/generate-image', data={}).status, 404)
        guest = self.browser.new_context()
        self.assertEqual(guest.request.get(self.url + '/api/library').status, 401)
        self.assertEqual(guest.request.post(self.url + '/api/login', data={'password': 'wrong'}).status, 401)
        self.assertEqual(guest.request.post(self.url + '/api/setup', data={'password': 'cannot-reset-password'}).status, 409)
        guest.close()
        response = self.page.request.put(self.url + '/api/library', headers={'Origin': 'https://other.invalid'}, data={'revision': 1, 'recipes': []})
        self.assertEqual(response.status, 403)

    def test_12_two_devices_share_recipes_and_favorites(self):
        other = self.browser.new_context(viewport={'width': 390, 'height': 844})
        self.assertEqual(other.request.post(self.url + '/api/login', data={'password': self.password}).status, 200)
        phone = other.new_page()
        phone.goto(self.url, wait_until='networkidle')
        expect(phone.locator('.recipe-card')).to_have_count(8)
        self.save(self.fill_recipe('Общий семейный суп'))
        expect(phone.locator('.recipe-card')).to_have_count(9, timeout=10000)
        expect(phone.locator('.card-title').first).to_have_text('Общий семейный суп')
        phone.locator('.favorite-button').first.click()
        expect(phone.locator('#favorite-count')).to_have_text('3')
        expect(self.page.locator('#favorite-count')).to_have_text('3', timeout=10000)
        other.close()

    def test_13_concurrent_edits_preserve_both_versions(self):
        self.page.locator('[data-open=lentil-soup]').click()
        self.page.locator('[data-edit]').click()
        form = self.page.locator('#recipe-form')
        form.locator('[name=title]').fill('Моя версия супа')
        remote = self.context.request.get(self.url + '/api/library').json()
        next(recipe for recipe in remote['recipes'] if recipe['id'] == 'lentil-soup')['title'] = 'Версия жены'
        self.assertEqual(self.context.request.put(self.url + '/api/library', data=remote).status, 200)
        form.locator('[type=submit]').click()
        expect(self.page.locator('#form-error')).to_contain_text('другом устройстве')
        form.locator('[type=submit]').click()
        expect(self.page.locator('#save-copy')).to_be_visible()
        self.page.locator('#save-copy').click()
        expect(self.page.locator('#editor-dialog')).not_to_be_visible()
        self.assertIn('Версия жены', self.titles())
        self.assertIn('Моя версия супа', self.titles())

    def test_14_server_restart_keeps_recipes_and_login(self):
        self.save(self.fill_recipe('Суп после перезапуска'))
        cls = type(self)
        cls.stop_server()
        cls.server = subprocess.Popen(['node', 'server.js'], cwd=ROOT, env=cls.environment, stdout=subprocess.DEVNULL)
        for _ in range(50):
            try:
                urllib.request.urlopen(self.url + '/healthz', timeout=1).close()
                break
            except OSError:
                time.sleep(.1)
        self.page.reload(wait_until='networkidle')
        expect(self.page.locator('.recipe-card')).to_have_count(9)
        expect(self.page.locator('.card-title').first).to_have_text('Суп после перезапуска')

    def test_15_revision_conflicts_invalid_data_and_login_logout(self):
        snapshot = self.context.request.get(self.url + '/api/library').json()
        self.assertEqual(self.context.request.put(self.url + '/api/library', data=snapshot).status, 200)
        self.assertEqual(self.context.request.put(self.url + '/api/library', data=snapshot).status, 409)
        snapshot = self.context.request.get(self.url + '/api/library').json()
        snapshot['recipes'][0]['time'] = -10
        self.assertEqual(self.context.request.put(self.url + '/api/library', data=snapshot).status, 400)
        self.page.locator('#logout').click()
        expect(self.page.locator('#auth-form')).to_be_visible()
        self.assertEqual(self.context.request.get(self.url + '/api/library').status, 401)
        self.page.locator('#family-password').fill(self.password)
        self.page.locator('#auth-submit').click()
        expect(self.page.locator('.recipe-card')).to_have_count(8)

    def test_16_phone_connection_and_app_manifest(self):
        self.page.locator('#open-connection').click()
        expect(self.page.locator('#connection-links')).to_contain_text('kroshka-test.local')
        self.page.set_viewport_size({'width': 320, 'height': 800})
        self.assertLessEqual(self.page.locator('#connection-dialog').evaluate('(el)=>el.scrollWidth'), 320)
        manifest = self.context.request.get(self.url + '/manifest.webmanifest').json()
        self.assertEqual(manifest['display'], 'standalone')
        self.assertEqual(self.context.request.get(self.url + '/assets/icon.svg').status, 200)
        self.assertEqual(self.context.request.get(self.url + '/offline.html').status, 200)

    def test_17_import_adds_copies_instead_of_overwriting(self):
        incoming = json.loads(json.dumps(self.seeds[:1]))
        incoming[0]['title'] = 'Суп из старой книги'
        self.page.once('dialog', lambda dialog: dialog.accept())
        self.page.locator('#import-file').set_input_files({'name': 'recipes.json', 'mimeType': 'application/json', 'buffer': json.dumps({'recipes': incoming}).encode()})
        expect(self.page.locator('.recipe-card')).to_have_count(9)
        self.assertIn('Чечевичный суп с овощами', self.titles())
        self.assertIn('Суп из старой книги (копия)', self.titles())

    def test_18_close_editor_checks_unsaved_changes(self):
        self.fill_recipe()
        self.page.once('dialog', lambda dialog: dialog.dismiss())
        self.page.locator('#editor-dialog .close-dialog').first.click()
        expect(self.page.locator('#editor-dialog')).to_be_visible()
        self.page.once('dialog', lambda dialog: dialog.accept())
        self.page.keyboard.press('Escape')
        expect(self.page.locator('#editor-dialog')).not_to_be_visible()

    def test_19_legacy_browser_recipes_are_copied_once_and_preserved(self):
        legacy = json.loads(json.dumps(self.seeds[0]))
        legacy['title'] = 'Мой старый суп'
        self.page.evaluate("""recipe => new Promise((resolve,reject)=>{const request=indexedDB.open('kroshka-recipes-v1',1);request.onupgradeneeded=()=>request.result.createObjectStore('library');request.onerror=()=>reject(request.error);request.onsuccess=()=>{const db=request.result;const tx=db.transaction('library','readwrite');tx.objectStore('library').put([recipe],'recipes');tx.oncomplete=()=>{db.close();resolve();};tx.onerror=()=>reject(tx.error);};})""", legacy)
        self.page.reload(wait_until='networkidle')
        expect(self.page.locator('#legacy-banner')).to_be_visible()
        self.page.once('dialog', lambda dialog: dialog.accept())
        self.page.locator('#migrate-recipes').click()
        expect(self.page.locator('.recipe-card')).to_have_count(9)
        expect(self.page.locator('#legacy-banner')).not_to_be_visible()
        self.page.reload(wait_until='networkidle')
        expect(self.page.locator('#legacy-banner')).not_to_be_visible()
        self.assertIn('Мой старый суп (копия)', self.titles())
        stored = self.page.evaluate("""() => new Promise(resolve=>{const request=indexedDB.open('kroshka-recipes-v1',1);request.onsuccess=()=>{const db=request.result;const read=db.transaction('library').objectStore('library').get('recipes');read.onsuccess=()=>{resolve(read.result);db.close();};};})""")
        self.assertEqual(stored[0]['title'], 'Мой старый суп')

    def test_20_multiline_step_stays_one_step_after_editing(self):
        form = self.fill_recipe('Суп с заметками')
        form.locator('.step-text').first.fill('Промыть чечевицу.\nЗаметка: воду слить.')
        self.save(form)
        self.page.locator('.card-open').first.click()
        expect(self.page.locator('.detail-steps li')).to_have_count(2)
        self.page.locator('[data-edit]').click()
        expect(self.page.locator('.step-row')).to_have_count(2)
        expect(self.page.locator('.step-text').first).to_have_value('Промыть чечевицу.\nЗаметка: воду слить.')

    def test_21_cooking_methods_create_filter_edit_and_share(self):
        form = self.fill_recipe('Обжаренный и запечённый суп')
        form.locator('input[name=cookingMethods][value="Жарить"]').check()
        form.locator('input[name=cookingMethods][value="Запекать"]').check()
        self.save(form)
        expect(self.page.locator('.card-methods').first).to_have_text('Жарить · Запекать')
        self.page.reload(wait_until='networkidle')
        self.page.locator('#filter-toggle').click()
        self.page.locator('#search').fill('чечевица и лук')
        for method in ['Жарить', 'Запекать']:
            self.page.locator('#filter-cooking-method').select_option(method)
            expect(self.page.locator('.recipe-card')).to_have_count(1)
        expect(self.page.locator('#filter-count')).to_have_text('1')
        self.page.locator('#filter-cooking-method').select_option('В аэрогриле')
        expect(self.page.locator('#empty-state')).to_be_visible()
        self.page.locator('#filter-cooking-method').select_option('unassigned')
        expect(self.page.locator('.recipe-card')).to_have_count(2)
        self.page.locator('#reset-filters').click()
        expect(self.page.locator('#filter-cooking-method')).to_have_value('')
        self.page.locator('#search').fill('')
        self.page.locator('.card-open').first.click()
        expect(self.page.locator('.detail-methods')).to_contain_text('Жарить · Запекать')
        self.page.locator('[data-edit]').click()
        form = self.page.locator('#recipe-form')
        expect(form.locator('input[name=cookingMethods][value="Жарить"]')).to_be_checked()
        expect(form.locator('input[name=cookingMethods][value="Запекать"]')).to_be_checked()
        form.locator('input[name=cookingMethods][value="Запекать"]').uncheck()
        form.locator('input[name=cookingMethods][value="Готовить на пару"]').check()
        self.save(form)
        other = self.browser.new_context()
        other.request.post(self.url + '/api/login', data={'password': self.password})
        recipe = next(r for r in other.request.get(self.url + '/api/library').json()['recipes'] if r['title'] == 'Обжаренный и запечённый суп')
        self.assertEqual(recipe['cookingMethods'], ['Жарить', 'Готовить на пару'])
        other.close()

    def test_22_old_recipes_keep_data_and_support_optional_methods(self):
        self.page.locator('[data-open=salmon]').click()
        expect(self.page.locator('.detail-methods')).to_contain_text('Не указан')
        self.page.locator('[data-edit]').click()
        form = self.page.locator('#recipe-form')
        self.assertEqual(form.locator('input[name=cookingMethods]:checked').count(), 0)
        form.locator('input[name=cookingMethods][value="В аэрогриле"]').check()
        self.save(form)
        recipe = next(r for r in self.context.request.get(self.url + '/api/library').json()['recipes'] if r['id'] == 'salmon')
        self.assertEqual(recipe['cookingMethods'], ['В аэрогриле'])
        original = next(r for r in self.seeds if r['id'] == 'salmon')['ingredients']
        self.assertEqual([(i['name'], str(i['amount']), i['unit']) for i in recipe['ingredients']], [(i['name'], str(i['amount']), i['unit']) for i in original])
        self.page.locator('[data-open=salmon]').click()
        self.page.locator('[data-edit]').click()
        form.locator('input[name=cookingMethods][value="В аэрогриле"]').uncheck()
        self.save(form)
        self.page.locator('#filter-toggle').click()
        self.page.locator('#filter-cooking-method').select_option('unassigned')
        expect(self.page.locator('.recipe-card')).to_have_count(8)

    def test_23_method_validation_and_backup_round_trip(self):
        for invalid in [['Микроволновка'], ['Запекать', 'Запекать'], 'Готовить на пару', None]:
            snapshot = self.context.request.get(self.url + '/api/library').json()
            snapshot['recipes'][0]['cookingMethods'] = invalid
            self.assertEqual(self.context.request.put(self.url + '/api/library', data=snapshot).status, 400)
        form = self.fill_recipe('Паровое блюдо')
        form.locator('input[name=cookingMethods][value="Готовить на пару"]').check()
        self.save(form)
        with self.page.expect_download() as info:
            self.page.locator('#export-data').click()
        backup = json.loads(Path(info.value.path()).read_text())
        recipe = next(r for r in backup['recipes'] if r['title'] == 'Паровое блюдо')
        self.assertEqual(recipe['cookingMethods'], ['Готовить на пару'])
        snapshot = self.context.request.get(self.url + '/api/library').json()
        snapshot['recipes'] = self.seeds
        self.assertEqual(self.context.request.put(self.url + '/api/library', data=snapshot).status, 200)
        self.page.reload(wait_until='networkidle')
        self.page.once('dialog', lambda dialog: dialog.accept())
        self.page.locator('#import-file').set_input_files({'name': 'methods.json', 'mimeType': 'application/json', 'buffer': json.dumps({'recipes': [recipe]}).encode()})
        expect(self.page.locator('.recipe-card')).to_have_count(9)
        self.page.locator('#filter-toggle').click()
        self.page.locator('#filter-cooking-method').select_option('Готовить на пару')
        self.assertEqual(self.titles(), ['Паровое блюдо'])

    def test_24_methods_fit_mobile_editor_and_filter_panel(self):
        self.page.set_viewport_size({'width': 320, 'height': 844})
        self.page.locator('#filter-toggle').click()
        self.assertLessEqual(self.page.evaluate('document.documentElement.scrollWidth'), 320)
        self.page.locator('#filter-cooking-method').select_option('Жарить')
        self.page.locator('#add-recipe').click()
        self.page.locator('.cooking-methods').first.scroll_into_view_if_needed()
        self.assertLessEqual(self.page.locator('#editor-dialog').evaluate('(el)=>el.scrollWidth'), 320)
        for value in ['Жарить', 'Запекать', 'В аэрогриле', 'Готовить на пару']:
            field = self.page.locator(f'input[name=cookingMethods][value="{value}"]')
            field.check()
            expect(field).to_be_checked()

    def test_25_cat_moves_as_a_continuous_image_and_respects_motion_preference(self):
        from io import BytesIO
        from PIL import Image, ImageChops
        logo = self.page.locator('.sidebar>.brand')
        timeline = self.page.locator('.svg-definitions')
        timeline.evaluate('(el)=>{el.pauseAnimations();el.setCurrentTime(0)}')
        still = Image.open(BytesIO(logo.screenshot())).convert('RGB')
        timeline.evaluate('(el)=>el.setCurrentTime(2.4)')
        tail = Image.open(BytesIO(logo.screenshot())).convert('RGB')
        timeline.evaluate('(el)=>el.setCurrentTime(3.8)')
        paw = Image.open(BytesIO(logo.screenshot())).convert('RGB')
        width, height = still.size
        tail_region = (0, int(height*.2), int(width*.43), int(height*.8))
        paw_region = (int(width*.85), int(height*.5), width, int(height*.85))
        self.assertIsNotNone(ImageChops.difference(still.crop(tail_region), tail.crop(tail_region)).getbbox())
        self.assertIsNotNone(ImageChops.difference(still.crop(paw_region), paw.crop(paw_region)).getbbox())
        self.page.emulate_media(reduced_motion='reduce')
        self.page.wait_for_function("[...document.querySelectorAll('feDisplacementMap')].every(el=>el.scale.animVal===0)")
        reduced = Image.open(BytesIO(logo.screenshot())).convert('RGB')
        self.assertIsNone(ImageChops.difference(still, reduced).getbbox())

    def test_26_theme_switch_persists_without_changing_recipes_or_filters(self):
        before = self.context.request.get(self.url + '/api/library').json()
        self.page.locator('#search').fill('чечевица и лук')
        expect(self.page.locator('.recipe-card')).to_have_count(2)
        self.page.locator('.topbar .theme-toggle').click()
        self.page.locator('[data-theme-choice=classic]').click()
        expect(self.page.locator('html')).to_have_attribute('data-theme', 'classic')
        expect(self.page.locator('.hero h2')).to_contain_text('Что приготовим')
        self.page.locator('#close-theme').click()
        expect(self.page.locator('.recipe-card')).to_have_count(2)
        self.page.reload(wait_until='networkidle')
        expect(self.page.locator('html')).to_have_attribute('data-theme', 'classic')
        self.page.set_viewport_size({'width': 320, 'height': 844})
        self.page.locator('.topbar .theme-toggle').click()
        self.page.locator('[data-theme-choice=halloween]').click()
        expect(self.page.locator('html')).to_have_attribute('data-theme', 'halloween')
        self.assertLessEqual(self.page.locator('#theme-dialog').evaluate('(el)=>el.scrollWidth'), 320)
        self.page.keyboard.press('Escape')
        self.assertLessEqual(self.page.evaluate('document.documentElement.scrollWidth'), 320)
        self.page.locator('#add-recipe').click()
        expect(self.page.locator('#editor-dialog')).to_be_visible()
        self.assertEqual(self.context.request.get(self.url + '/api/library').json(), before)

    def test_27_seasonal_theme_ends_on_november_first_and_manual_choice_wins(self):
        from datetime import datetime, timezone
        self.page.clock.install(time=datetime(2026, 10, 19, 12, tzinfo=timezone.utc))
        self.page.reload(wait_until='networkidle')
        expect(self.page.locator('html')).to_have_attribute('data-theme', 'classic')
        for month, day, theme in [(10, 20, 'halloween'), (10, 31, 'halloween'), (11, 1, 'classic')]:
            self.page.clock.set_system_time(datetime(2026, month, day, 12, tzinfo=timezone.utc))
            self.page.evaluate('document.dispatchEvent(new Event("visibilitychange"))')
            expect(self.page.locator('html')).to_have_attribute('data-theme', theme)
        self.page.locator('.topbar .theme-toggle').click()
        self.page.locator('[data-theme-choice=halloween]').click()
        expect(self.page.locator('html')).to_have_attribute('data-theme', 'halloween')
        self.page.locator('[data-theme-choice=auto]').click()
        expect(self.page.locator('html')).to_have_attribute('data-theme', 'classic')

    def test_28_pot_method_saves_edits_filters_and_exports(self):
        form = self.fill_recipe('Варёная чечевица')
        form.locator('input[name=cookingMethods][value="Варить"]').check()
        self.save(form)
        self.page.locator('#filter-toggle').click()
        self.page.locator('#filter-cooking-method').select_option('Варить')
        self.assertEqual(self.titles(), ['Варёная чечевица'])
        self.page.locator('.card-open').first.click()
        expect(self.page.locator('.detail-methods')).to_contain_text('Варить')
        self.page.locator('[data-edit]').click()
        expect(form.locator('input[name=cookingMethods][value="Варить"]')).to_be_checked()
        for value in ['Жарить', 'Запекать', 'В аэрогриле', 'Готовить на пару']:
            form.locator(f'input[name=cookingMethods][value="{value}"]').check()
        self.save(form)
        recipe = next(r for r in self.context.request.get(self.url + '/api/library').json()['recipes'] if r['title'] == 'Варёная чечевица')
        self.assertEqual(len(recipe['cookingMethods']), 5)
        with self.page.expect_download() as info:
            self.page.locator('#export-data').click()
        self.assertIn('Варить', next(r for r in json.loads(Path(info.value.path()).read_text())['recipes'] if r['title'] == recipe['title'])['cookingMethods'])

    def test_29_empty_sections_have_readable_themed_content_and_useful_actions(self):
        snapshot = self.context.request.get(self.url + '/api/library').json()
        snapshot['recipes'] = [r for r in snapshot['recipes'] if r['meal'] != 'Перекус']
        self.assertEqual(self.context.request.put(self.url + '/api/library', data=snapshot).status, 200)
        self.page.reload(wait_until='networkidle')
        self.page.locator('[data-meal="Перекус"]').click()
        expect(self.page.locator('#empty-title')).to_have_text('Пока нет перекусов')
        for theme in ['classic', 'halloween']:
            self.page.locator('.topbar .theme-toggle').click()
            self.page.locator(f'[data-theme-choice={theme}]').click()
            self.page.locator('#close-theme').click()
            for selector in ['#empty-title', '#empty-message']:
                contrast = self.page.locator(selector).evaluate(r'''el=>{
                  const rgb=s=>s.match(/[\d.]+/g).slice(0,3).map(Number).map(v=>{v/=255;return v<=.04045?v/12.92:((v+.055)/1.055)**2.4});
                  const luminance=s=>{const [r,g,b]=rgb(s);return .2126*r+.7152*g+.0722*b};
                  const fg=luminance(getComputedStyle(el).color),bg=luminance(getComputedStyle(document.querySelector('#empty-state')).backgroundColor);
                  return (Math.max(fg,bg)+.05)/(Math.min(fg,bg)+.05);
                }''')
                self.assertGreaterEqual(contrast, 4.5, (theme, selector, contrast))
        self.page.set_viewport_size({'width': 320, 'height': 844})
        self.assertLessEqual(self.page.evaluate('document.documentElement.scrollWidth'), 320)
        self.page.locator('#empty-add').click()
        expect(self.page.locator('#recipe-form [name=meal]')).to_have_value('Перекус')
        self.page.locator('#editor-dialog .close-dialog').first.click()
        self.page.locator('#empty-action').click()
        expect(self.page.locator('.recipe-card')).to_have_count(7)

    def test_30_catalog_is_private_separate_searchable_and_does_not_seed_family_book(self):
        before = self.context.request.get(self.url + '/api/library').json()
        stats = self.context.request.get(self.url + '/api/catalog').json()
        self.assertGreater(stats['total'], 1000)
        self.assertEqual(stats['counts']['cocktail'], 20)
        self.assertEqual(stats['counts']['mocktail'], 20)
        import urllib.parse
        first = self.context.request.get(self.url + '/api/catalog/random?' + urllib.parse.urlencode({'q': 'чечевица и лук', 'kind': 'dish'})).json()
        self.assertGreater(first['matched'], 1)
        second = self.context.request.get(self.url + '/api/catalog/random?' + urllib.parse.urlencode({'q': 'чечевица и лук', 'kind': 'dish', 'exclude': first['recipe']['id']})).json()
        self.assertNotEqual(first['recipe']['id'], second['recipe']['id'])
        for query in ['kind=invalid', 'q=' + 'a' * 151, 'exclude=' + ','.join(['x'] * 101)]:
            self.assertEqual(self.context.request.get(self.url + '/api/catalog/random?' + query).status, 400)
        self.assertIsNone(self.context.request.get(self.url + '/api/catalog/random?q=xyz-nothing-found').json()['recipe'])
        for name in ['catalog/recipes.json', 'catalog/cocktails.json', 'catalog.js']:
            self.assertEqual(self.context.request.get(self.url + '/' + name).status, 404)
        guest = self.browser.new_context()
        self.assertEqual(guest.request.get(self.url + '/api/catalog/random').status, 401)
        self.assertEqual(guest.request.post(self.url + '/api/catalog/mojito/save', data={}).status, 401)
        guest.close()
        self.assertEqual(self.context.request.get(self.url + '/api/library').json(), before)

    def test_31_catalog_save_edit_dedup_source_export_and_drink_category(self):
        self.page.locator('#inspire').click()
        expect(self.page.locator('#catalog-dialog')).to_be_visible()
        self.page.locator('#catalog-kind').select_option('cocktail')
        self.page.locator('#catalog-search').fill('мохито')
        expect(self.page.locator('.catalog-recipe h3')).to_have_text('Мохито')
        self.page.locator('#catalog-save').click()
        expect(self.page.locator('#catalog-save')).to_contain_text('Уже в вашей книге')
        expect(self.page.locator('#all-count')).to_have_text('9')
        self.page.locator('#catalog-dialog .close-dialog').click()
        self.page.locator('[data-meal="Напиток"]').click()
        self.assertEqual(self.titles(), ['Мохито'])
        self.page.locator('.card-open').first.click()
        expect(self.page.locator('.detail-categories')).to_contain_text('Алкогольный коктейль')
        expect(self.page.locator('#recipe-detail .source-note')).to_contain_text('Крошка')
        self.page.locator('[data-edit]').click()
        form = self.page.locator('#recipe-form')
        form.locator('[name=title]').fill('Мой мохито')
        self.save(form)
        duplicate = self.context.request.post(self.url + '/api/catalog/mojito/save', data={})
        self.assertEqual(duplicate.status, 200)
        self.assertTrue(duplicate.json()['alreadySaved'])
        self.assertEqual(duplicate.json()['recipe']['title'], 'Мой мохито')
        self.assertEqual(len(self.context.request.get(self.url + '/api/library').json()['recipes']), 9)
        with self.page.expect_download() as info:
            self.page.locator('#export-data').click()
        recipe = next(r for r in json.loads(Path(info.value.path()).read_text())['recipes'] if r['title'] == 'Мой мохито')
        self.assertEqual(recipe['catalogId'], 'mojito')
        self.assertEqual(recipe['recipeKind'], 'cocktail')
        self.assertIsNone(recipe['protein'])
        self.assertIn('Крошка', recipe['sourceTitle'])
        self.page.locator('#inspire').click()
        expect(self.page.locator('.catalog-recipe h3')).to_have_text('Мохито')
        expect(self.page.locator('#catalog-save')).to_be_disabled()
        self.assertEqual(self.context.request.post(self.url + '/api/catalog/not-existing/save', data={}).status, 404)

    def test_32_concurrent_catalog_saves_are_idempotent_and_shared(self):
        statuses = self.page.evaluate('''async()=>await Promise.all(['mojito','mojito','virgin-mojito'].map(async id=>{
          const result=await fetch('/api/catalog/'+id+'/save',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
          return result.status;
        }))''')
        self.assertEqual(sorted(statuses), [200, 201, 201])
        other = self.browser.new_context()
        other.request.post(self.url + '/api/login', data={'password': self.password})
        stored = other.request.get(self.url + '/api/library').json()
        self.assertEqual(len(stored['recipes']), 10)
        self.assertEqual(len([r for r in stored['recipes'] if r.get('catalogId') == 'mojito']), 1)
        self.assertEqual(next(r for r in stored['recipes'] if r.get('catalogId') == 'virgin-mojito')['recipeKind'], 'mocktail')
        other.close()

    def test_33_catalog_mobile_filters_empty_results_and_network_recovery(self):
        external = []
        self.page.on('request', lambda r: external.append(r.url) if r.url.startswith(('http:', 'https:')) and not r.url.startswith(self.url) else None)
        self.page.set_viewport_size({'width': 320, 'height': 844})
        self.page.locator('#inspire').click()
        self.page.locator('#catalog-kind').select_option('mocktail')
        self.page.locator('#catalog-search').fill('мохито')
        expect(self.page.locator('.catalog-recipe h3')).to_have_text('Безалкогольный мохито')
        self.assertLessEqual(self.page.locator('#catalog-dialog').evaluate('(el)=>el.scrollWidth'), 320)
        self.assertEqual(self.page.locator('#catalog-content').evaluate('(el)=>el.scrollWidth'), self.page.locator('#catalog-content').evaluate('(el)=>el.clientWidth'))
        self.page.locator('#catalog-search').fill('совсемнесуществующийрецепт')
        expect(self.page.locator('.catalog-empty h3')).to_have_text('Пока нет такой идеи')
        expect(self.page.locator('#catalog-save')).to_be_disabled()
        self.page.route('**/api/catalog/random?*', lambda route: route.abort())
        self.page.locator('#catalog-search').fill('лайм')
        expect(self.page.locator('#catalog-summary')).to_have_text('Не удалось открыть каталог')
        self.page.unroute('**/api/catalog/random?*')
        self.page.locator('#catalog-next').click()
        expect(self.page.locator('.catalog-recipe')).to_be_visible()
        self.assertEqual(external, [])


    def test_34_trial_shelf_is_separate_from_main_and_favorites(self):
        self.page.locator('#inspire').click()
        self.page.locator('#catalog-kind').select_option('cocktail')
        self.page.locator('#catalog-search').fill('мохито')
        expect(self.page.locator('.catalog-recipe h3')).to_have_text('Мохито')
        self.page.locator('#catalog-save-trial').click()
        expect(self.page.locator('#catalog-save-trial')).to_contain_text('Уже на пробе')
        expect(self.page.locator('#all-count')).to_have_text('8')
        expect(self.page.locator('#favorite-count')).to_have_text('2')
        expect(self.page.locator('#trial-count')).to_have_text('1')
        self.page.locator('#catalog-dialog .close-dialog').click()
        self.page.locator('[data-collection=trial]').click()
        self.assertEqual(self.titles(), ['Мохито'])
        self.page.reload(wait_until='networkidle')
        self.page.locator('[data-collection=trial]').click()
        self.assertEqual(self.titles(), ['Мохито'])
        self.page.locator('[data-collection=all]').click()
        expect(self.page.locator('.recipe-card')).to_have_count(8)
        self.page.locator('[data-collection=favorites]').click()
        expect(self.page.locator('.recipe-card')).to_have_count(2)

    def test_35_trial_edit_promote_and_delete_preserve_recipe(self):
        self.context.request.post(self.url + '/api/catalog/mojito/save', data={'destination': 'trial'})
        self.page.reload(wait_until='networkidle')
        self.page.locator('[data-collection=trial]').click()
        self.page.locator('.card-open').click()
        expect(self.page.locator('.trial-detail-note')).to_contain_text('Блюдо на пробу')
        self.page.locator('[data-edit]').click()
        form = self.page.locator('#recipe-form')
        form.locator('[name=title]').fill('Семейный мохито на пробу')
        self.save(form)
        expect(self.page.locator('#collection-title')).to_contain_text('Блюда на пробу')
        before = next(r for r in self.context.request.get(self.url + '/api/library').json()['recipes'] if r.get('catalogId') == 'mojito')
        self.assertEqual(before['shelf'], 'trial')
        self.page.locator('#recipe-grid [data-promote-trial]').click()
        expect(self.page.locator('#trial-count')).to_have_text('0')
        expect(self.page.locator('#all-count')).to_have_text('9')
        stored = self.context.request.get(self.url + '/api/library').json()['recipes']
        promoted = next(r for r in stored if r['id'] == before['id'])
        self.assertEqual(promoted['shelf'], 'main')
        for field in ['title', 'steps', 'ingredients', 'sourceTitle', 'recipeKind', 'catalogId', 'image']:
            self.assertEqual(promoted[field], before[field])
        self.context.request.post(self.url + '/api/catalog/virgin-mojito/save', data={'destination': 'trial'})
        self.page.reload(wait_until='networkidle')
        self.page.locator('[data-collection=trial]').click()
        self.page.once('dialog', lambda dialog: dialog.accept())
        self.page.locator('#recipe-grid [data-delete-trial]').click()
        expect(self.page.locator('#trial-count')).to_have_text('0')
        self.assertEqual(len(self.context.request.get(self.url + '/api/library').json()['recipes']), 9)

    def test_36_trial_catalog_promotion_dedup_and_concurrent_delete_protection(self):
        first = self.context.request.post(self.url + '/api/catalog/mojito/save', data={'destination': 'trial'})
        self.assertEqual(first.status, 201)
        self.assertEqual(self.context.request.post(self.url + '/api/catalog/mojito/save', data={'destination': 'trial'}).status, 200)
        moved = self.context.request.post(self.url + '/api/catalog/mojito/save', data={'destination': 'main'}).json()
        self.assertTrue(moved['moved'])
        self.assertEqual(moved['recipe']['shelf'], 'main')
        again = self.context.request.post(self.url + '/api/catalog/mojito/save', data={'destination': 'trial'}).json()
        self.assertTrue(again['alreadySaved'])
        self.assertEqual(again['recipe']['shelf'], 'main')
        self.assertEqual(self.context.request.delete(self.url + '/api/trials/catalog-mojito', data={}).status, 409)
        self.assertEqual(len(self.context.request.get(self.url + '/api/library').json()['recipes']), 9)
        self.assertEqual(self.context.request.post(self.url + '/api/catalog/mojito/save', data={'destination': 'other'}).status, 400)
        self.assertEqual(self.context.request.delete(self.url + '/api/trials/not-existing', data={}).status, 404)
        self.assertEqual(self.context.request.post(self.url + '/api/trials/not-existing/promote', data={}).status, 404)

    def test_37_trial_backup_and_mobile_navigation_and_dialog_actions(self):
        self.context.request.post(self.url + '/api/catalog/virgin-mojito/save', data={'destination': 'trial'})
        self.page.reload(wait_until='networkidle')
        with self.page.expect_download() as info:
            self.page.locator('#export-data').click()
        backup = json.loads(Path(info.value.path()).read_text())
        self.assertEqual(next(r for r in backup['recipes'] if r.get('catalogId') == 'virgin-mojito')['shelf'], 'trial')
        for width in [320, 390]:
            self.page.set_viewport_size({'width': width, 'height': 844})
            self.page.locator('[data-collection=trial]').click()
            self.assertEqual(self.titles(), ['Безалкогольный мохито'])
            self.assertLessEqual(self.page.evaluate('document.documentElement.scrollWidth'), width)
            self.page.locator('#inspire').click()
            expect(self.page.locator('.catalog-recipe')).to_be_visible()
            self.assertLessEqual(self.page.locator('#catalog-dialog').evaluate('(e)=>e.scrollWidth'), width)
            for selector in ['#catalog-save', '#catalog-save-trial', '#catalog-next']:
                box=self.page.locator(selector).bounding_box()
                self.assertGreaterEqual(box['x'], 0)
                self.assertLessEqual(box['x']+box['width'], width)
            self.page.locator('#catalog-dialog .close-dialog').click()
        self.page.locator('.card-open').click()
        expect(self.page.locator('#recipe-detail [data-promote-trial]')).to_be_visible()

    def test_38_every_catalog_recipe_has_distinct_valid_compact_local_art(self):
        from io import BytesIO
        from PIL import Image
        items=json.loads((ROOT/'catalog/recipes.json').read_text())+json.loads((ROOT/'catalog/cocktails.json').read_text())
        artwork=self.context.request.get(self.url+'/api/catalog/art').json()['images']
        self.assertEqual(set(artwork), {recipe['id'] for recipe in items})
        positions={(art['sheet'],art['x'],art['y']) for art in artwork.values()}
        self.assertEqual(len(positions), len(items))
        import hashlib
        tile_hashes=set()
        total_bytes=0
        for sheet in {art['sheet'] for art in artwork.values()}:
            response=self.context.request.get(self.url+'/assets/catalog-sheets/'+sheet+'.webp')
            self.assertEqual(response.status, 200)
            self.assertEqual(response.headers['content-type'], 'image/webp')
            data=response.body();total_bytes+=len(data)
            image=Image.open(BytesIO(data));width,height=image.size;image.verify()
            decoded=Image.open(BytesIO(data)).convert('RGB')
            for art in [value for value in artwork.values() if value['sheet']==sheet]:
                self.assertEqual((art['fullWidth'],art['fullHeight']),(width,height))
                self.assertLessEqual(art['x']+art['width'],width)
                self.assertLessEqual(art['y']+art['height'],height)
                tile=decoded.crop((art['x'],art['y'],art['x']+art['width'],art['y']+art['height']))
                tile_hashes.add(hashlib.sha256(tile.tobytes()).hexdigest())
        self.assertEqual(len(tile_hashes),len(items))
        self.assertLess(total_bytes,40*1024*1024)
        recipe=items[0]
        saved=self.context.request.post(self.url+'/api/catalog/'+recipe['id']+'/save',data={'destination':'trial'}).json()['recipe']
        self.assertEqual(saved['image'],'art:'+recipe['id'])
        self.page.reload(wait_until='networkidle')
        self.page.locator('[data-collection=trial]').click()
        art=artwork[recipe['id']]
        expect(self.page.locator('.generated-food-photo')).to_have_attribute('viewBox',f"{art['x']} {art['y']} {art['width']} {art['height']}")
        self.assertEqual(self.context.request.get(self.url+'/assets/catalog-sheets/not-real.webp').status,404)

    def test_39_trial_backups_restore_shelf_and_art_without_merging_into_main(self):
        for id in ['mojito','virgin-mojito']:
            self.context.request.post(self.url+'/api/catalog/'+id+'/save',data={'destination':'trial'})
        self.page.reload(wait_until='networkidle')
        with self.page.expect_download() as info:self.page.locator('#export-data').click()
        backup=Path(info.value.path()).read_bytes()
        snapshot=self.context.request.get(self.url+'/api/library').json()
        self.assertEqual(self.context.request.put(self.url+'/api/library',data={'revision':snapshot['revision'],'recipes':[]}).status,200)
        self.page.reload(wait_until='networkidle')
        self.page.once('dialog',lambda dialog:dialog.accept())
        self.page.locator('#import-file').set_input_files({'name':'trial-backup.json','mimeType':'application/json','buffer':backup})
        expect(self.page.locator('#all-count')).to_have_text('8')
        expect(self.page.locator('#trial-count')).to_have_text('2')
        self.page.locator('[data-collection=trial]').click()
        self.assertEqual(set(self.titles()),{'Мохито','Безалкогольный мохито'})
        expect(self.page.locator('.generated-food-photo')).to_have_count(2)

    def test_40_text_catalog_upgrade_keeps_existing_photos_and_trial_status(self):
        import sqlite3
        for id in ['mojito','virgin-mojito']:
            self.context.request.post(self.url+'/api/catalog/'+id+'/save',data={'destination':'trial'})
        snapshot=self.context.request.get(self.url+'/api/library').json()
        for recipe in snapshot['recipes']:
            if recipe.get('catalogId')=='mojito':recipe['image']=''
            if recipe.get('catalogId')=='virgin-mojito':recipe['image']='sample:salad'
        self.assertEqual(self.context.request.put(self.url+'/api/library',data=snapshot).status,200)
        self.__class__.stop_server()
        with sqlite3.connect(Path(self.data_dir.name)/'recipes.sqlite') as db:
            db.execute("UPDATE settings SET value='0' WHERE key='catalogArtVersion'")
        self.__class__.server=subprocess.Popen(['node','server.js'],cwd=ROOT,env=self.environment,stdout=subprocess.DEVNULL)
        for _ in range(60):
            try:urllib.request.urlopen(self.url+'/healthz',timeout=1).close();break
            except OSError:time.sleep(.1)
        else:self.fail('Server did not restart')
        recipes=self.context.request.get(self.url+'/api/library').json()['recipes']
        self.assertEqual(len(recipes),10)
        self.assertEqual(next(r for r in recipes if r.get('catalogId')=='mojito')['image'],'art:mojito')
        self.assertEqual(next(r for r in recipes if r.get('catalogId')=='virgin-mojito')['image'],'sample:salad')
        self.assertEqual([r['shelf'] for r in recipes if r.get('catalogId')],['trial','trial'])

    def test_41_equipment_preparations_and_legacy_methods(self):
        form=self.fill_recipe('Заготовка чечевицы')
        for value in ['Варить','Тушить']:
            form.locator(f'input[name=cookingMethods][value="{value}"]').check()
        for value in ['Блендер','Венчик']:
            form.locator(f'input[name=equipment][value="{value}"]').check()
        form.locator('[name=isPreparation]').check()
        self.save(form)
        self.page.reload(wait_until='networkidle')
        self.page.locator('#filter-toggle').click()
        self.page.locator('#filter-preparation').select_option('yes')
        expect(self.page.locator('.recipe-card')).to_have_count(1)
        self.page.locator('#filter-equipment').select_option('Миксер')
        expect(self.page.locator('#empty-state')).to_be_visible()
        self.page.locator('#filter-equipment').select_option('Венчик')
        self.page.locator('.card-open').click()
        expect(self.page.locator('.detail-methods').last).to_contain_text('Блендер · Венчик')
        self.page.locator('[data-edit]').click()
        expect(form.locator('[name=isPreparation]')).to_be_checked()
        expect(form.locator('input[name=equipment][value="Венчик"]')).to_be_checked()
        form.locator('input[name=equipment][value="Венчик"]').uncheck()
        self.save(form)
        snapshot=self.context.request.get(self.url+'/api/library').json()
        recipe=next(r for r in snapshot['recipes'] if r['title']=='Заготовка чечевицы')
        self.assertEqual(recipe['equipment'],['Блендер'])
        self.assertTrue(recipe['isPreparation'])
        for field,value in [('equipment',['Неверный предмет']),('equipment',['Блендер','Блендер']),('isPreparation','yes')]:
            invalid=json.loads(json.dumps(snapshot));invalid['recipes'][0][field]=value
            self.assertEqual(self.context.request.put(self.url+'/api/library',data=invalid).status,400)
        recipe['cookingMethods']=['Сковородка','Кастрюля (варка)']
        self.assertEqual(self.context.request.put(self.url+'/api/library',data=snapshot).status,200)
        self.page.reload(wait_until='networkidle')
        self.page.locator('[data-open="'+recipe['id']+'"]').click()
        expect(self.page.locator('.detail-methods').first).to_contain_text('Жарить · Варить')

    def test_42_editor_settings_and_filters_fit_both_themes(self):
        self.page.locator('#add-recipe').click()
        for theme in ['classic','halloween']:
            self.page.evaluate('(theme)=>document.documentElement.dataset.theme=theme',theme)
            for width in [320,390,768,1440]:
                self.page.set_viewport_size({'width':width,'height':900})
                self.page.locator('[data-editor-section=recipe-settings]').click()
                self.assertLessEqual(self.page.evaluate('document.documentElement.scrollWidth'),width)
                self.assertTrue(self.page.locator('#editor-dialog').evaluate('(e)=>e.scrollWidth<=e.clientWidth'))
                for checkbox in self.page.locator('input[name=equipment]').all():
                    checkbox.check()
                    expect(checkbox).to_be_checked()
        self.page.on('dialog',lambda dialog:dialog.accept())
        self.page.locator('#editor-dialog .close-dialog').first.click()
        self.page.locator('[data-quick=preparation]').click()
        expect(self.page.locator('#empty-state')).to_be_visible()
        self.page.locator('[data-quick=all]').click()
        expect(self.page.locator('.recipe-card')).to_have_count(8)

    def test_43_upgrade_migrates_legacy_methods_without_losing_fields(self):
        import sqlite3
        cls=type(self)
        cls.stop_server()
        path=Path(cls.data_dir.name)/'recipes.sqlite'
        with sqlite3.connect(path) as db:
            recipe=json.loads(db.execute('SELECT content FROM recipes WHERE id=?',('salmon',)).fetchone()[0])
            recipe.update(cookingMethods=['Сковородка','Духовка','Кастрюля (варка)'],equipment=['Венчик'],isPreparation=True)
            db.execute('UPDATE recipes SET content=? WHERE id=?',(json.dumps(recipe),'salmon'))
            db.execute("DELETE FROM settings WHERE key='cookingActionsVersion'")
        cls.server=subprocess.Popen(['node','server.js'],cwd=ROOT,env=cls.environment,stdout=subprocess.DEVNULL)
        for _ in range(50):
            try:
                urllib.request.urlopen(self.url+'/healthz',timeout=1).close();break
            except OSError:time.sleep(.1)
        saved=next(r for r in self.context.request.get(self.url+'/api/library').json()['recipes'] if r['id']=='salmon')
        self.assertEqual(saved,{**recipe,'cookingMethods':['Жарить','Запекать','Варить']})

    def test_44_invalid_json_import_and_unreadable_file_keep_book(self):
        before = self.context.request.get(self.url + '/api/library').json()
        writes = []
        self.page.on('request', lambda request: writes.append(request.url)
                     if request.method == 'PUT' and request.url.endswith('/api/library') else None)
        for payload in [b'', b'{broken', b'null', b'42', b'{}', b'{"recipes":null}', b'{"recipes":[null]}']:
            with self.subTest(payload=payload):
                self.page.locator('#import-file').set_input_files({
                    'name': 'a22.json', 'mimeType': 'application/json', 'buffer': payload})
                expect(self.page.locator('#toast')).to_contain_text(
                    'Не удалось прочитать файл' if payload in (b'', b'{broken', b'null')
                    else 'В файле нет подходящих рецептов')
                expect(self.page.locator('#import-file')).to_have_value('')
                self.assertEqual(self.context.request.get(self.url + '/api/library').json(), before)
        # No selected file (cancel/missing selection) leaves the book alone.
        self.page.locator('#import-file').set_input_files([])
        self.page.locator('#import-file').dispatch_event('change')
        # Simulate missing/unreadable files after selection, without changing app code.
        self.page.evaluate('() => { window.a22FileText = File.prototype.text; }')
        try:
            for error_name in ['NotFoundError', 'NotReadableError']:
                self.page.evaluate("name => { File.prototype.text = async () => { throw new DOMException('Synthetic read failure', name); }; }", error_name)
                self.page.locator('#import-file').set_input_files({
                    'name': 'unreadable.json', 'mimeType': 'application/json', 'buffer': b'{}'})
                expect(self.page.locator('#toast')).to_contain_text('Не удалось прочитать файл')
                expect(self.page.locator('#import-file')).to_have_value('')
        finally:
            self.page.evaluate('() => { File.prototype.text = window.a22FileText; delete window.a22FileText; }')
        self.assertEqual(writes, [])
        self.assertEqual(self.context.request.get(self.url + '/api/library').json(), before)
        # A valid legacy import still works after every refusal.
        incoming = {**self.seeds[0], 'id': 'a22-import', 'title': 'A22 после ошибки импорта'}
        self.page.once('dialog', lambda dialog: dialog.accept())
        self.page.locator('#import-file').set_input_files({
            'name': 'legacy.json', 'mimeType': 'application/json',
            'buffer': json.dumps([incoming]).encode()})
        expect(self.page.locator('.recipe-card')).to_have_count(9)
        saved = self.context.request.get(self.url + '/api/library').json()
        self.assertEqual(next(r for r in saved['recipes'] if r['id'] == incoming['id']), incoming)

    def remote_context(self):
        context = self.browser.new_context()
        self.addCleanup(context.close)
        self.assertEqual(context.request.post(self.url + '/api/login', data={'password': self.password}).status, 200)
        return context

    def remote_update(self, context, change):
        snapshot = context.request.get(self.url + '/api/library').json()
        change(snapshot['recipes'])
        response = context.request.put(self.url + '/api/library', data=snapshot)
        self.assertEqual(response.status, 200, response.text())
        return response.json()['revision']

    def receive_revision(self, revision, polling=False):
        with self.page.expect_response(lambda response: '/api/library' in response.url
                                       and response.request.method == 'GET'
                                       and response.json().get('revision') == revision, timeout=10000):
            if not polling:
                self.page.evaluate("window.dispatchEvent(new Event('online'))")
        # Let the real fetch continuation and DOM tasks finish before closing.
        self.page.evaluate('() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))')

    def test_46_remote_edit_refreshes_cards_on_close_without_another_poll(self):
        other = self.remote_context()
        self.page.locator('[data-open="lentil-soup"]').click()
        revision = self.remote_update(other, lambda recipes: next(r for r in recipes if r['id'] == 'lentil-soup').update(title='Суп после синхронизации'))
        self.receive_revision(revision, polling=True)
        self.page.route('**/api/library*', lambda route: route.abort())
        self.page.keyboard.press('Escape')
        expect(self.page.locator('[data-id="lentil-soup"] .card-title')).to_have_text('Суп после синхронизации', timeout=1000)
        expect(self.page.locator('[data-open="lentil-soup"]')).to_be_focused()

    def test_45_json_rejection_preserves_draft_photo_and_allows_retry(self):
        before = self.context.request.get(self.url + '/api/library').json()
        form = self.fill_recipe('A22 сохранение после ошибки')
        self.page.locator('#image-upload').set_input_files(ROOT / 'assets/food-grid.png')
        expect(self.page.locator('#image-preview img')).to_be_visible()
        photo = self.page.locator('#image-preview img').get_attribute('src')

        def corrupt_body(route):
            route.continue_(post_data='null') if route.request.method == 'PUT' else route.continue_()

        self.page.route('**/api/library', corrupt_body)
        with self.page.expect_response(lambda response: response.request.method == 'PUT'
                                       and response.url.endswith('/api/library')) as response:
            form.locator('[type=submit]').click()
        self.assertEqual(response.value.status, 400)
        expect(self.page.locator('#form-error')).to_contain_text('Ожидается объект JSON')
        expect(self.page.locator('#editor-dialog')).to_be_visible()
        expect(form.locator('[name=title]')).to_have_value('A22 сохранение после ошибки')
        self.assertEqual(self.page.locator('#image-preview img').get_attribute('src'), photo)
        self.assertEqual(self.context.request.get(self.url + '/api/library').json(), before)
        self.page.unroute('**/api/library', corrupt_body)
        self.save(form)
        expect(self.page.locator('.recipe-card')).to_have_count(9)
        saved = self.context.request.get(self.url + '/api/library').json()
        self.assertEqual(saved['revision'], before['revision'] + 1)
        added = next(r for r in saved['recipes'] if r['title'] == 'A22 сохранение после ошибки')
        self.assertEqual(added['image'], photo)
        self.assertEqual([r for r in saved['recipes'] if r['id'] != added['id']], before['recipes'])

    def test_47_sync_close_paths_keep_filters_view_focus_and_latest_snapshot(self):
        other = self.remote_context()
        for theme, view, close in [('classic', 'grid', 'cross'), ('halloween', 'list', 'backdrop'), ('classic', 'list', 'programmatic')]:
            with self.subTest(theme=theme, view=view, close=close):
                self.page.evaluate('(theme) => localStorage.setItem("kroshka-appearance", theme)', theme)
                self.page.reload(wait_until='networkidle')
                self.page.locator('#search').fill('чечевица')
                self.page.locator('#sort').select_option('time')
                self.page.locator('#filter-toggle').click()
                self.page.locator('#filter-meat').select_option('Без мяса')
                self.page.locator('#' + view + '-view').click()
                self.page.locator('[data-open="lentil-soup"]').scroll_into_view_if_needed()
                self.page.locator('[data-open="lentil-soup"]').click()
                # Native focus may scroll the card on click; compare the actual
                # reading position before remote sync, not the pre-click offset.
                expect(self.page.locator('#recipe-dialog')).to_be_visible()
                scroll_y = self.page.evaluate('window.scrollY')
                old_title = self.page.locator('#recipe-detail h2').inner_text()
                for index in range(2):
                    title = f'Чечевица {theme} {close} {index}'
                    revision = self.remote_update(other, lambda recipes: next(r for r in recipes if r['id'] == 'lentil-soup').update(title=title))
                    self.receive_revision(revision)
                expect(self.page.locator('#recipe-sync-notice')).to_be_visible()
                expect(self.page.locator('#recipe-sync-message')).to_have_text('Рецепт изменён на другом устройстве')
                expect(self.page.locator('#recipe-detail h2')).to_have_text(old_title)
                # An unchanged response must not discard the pending render.
                with self.page.expect_response(lambda response: '/api/library?' in response.url and response.json().get('unchanged')):
                    self.page.evaluate("window.dispatchEvent(new Event('online'))")
                if close == 'cross':
                    self.page.locator('#recipe-dialog .close-dialog').click()
                elif close == 'backdrop':
                    self.page.mouse.click(1, 1)
                else:
                    self.page.locator('#recipe-dialog').evaluate('(dialog) => dialog.close()')
                expect(self.page.locator('#recipe-dialog')).not_to_be_visible()
                expect(self.page.locator('[data-id="lentil-soup"] .card-title')).to_have_text(title, timeout=1000)
                expect(self.page.locator('[data-open="lentil-soup"]')).to_be_focused()
                self.assertLessEqual(abs(self.page.evaluate('window.scrollY') - scroll_y), 2)
                expect(self.page.locator('#search')).to_have_value('чечевица')
                expect(self.page.locator('#sort')).to_have_value('time')
                expect(self.page.locator('#filter-meat')).to_have_value('Без мяса')
                expect(self.page.locator('#' + view + '-view')).to_have_attribute('aria-pressed', 'true')
                self.assertEqual(self.page.locator('#recipe-grid').evaluate('(grid) => grid.classList.contains("list-view")'), view == 'list')
                self.assertEqual(self.context.request.get(self.url + '/api/library').json()['revision'], revision)

    def test_48_open_view_updates_explicitly_and_deleted_actions_are_disabled(self):
        other = self.remote_context()
        self.page.set_viewport_size({'width': 390, 'height': 844})
        self.page.locator('[data-open="lentil-soup"]').click()
        revision = self.remote_update(other, lambda recipes: next(r for r in recipes if r['id'] == 'lentil-soup').update(title='Новая версия супа', time=42))
        self.receive_revision(revision)
        expect(self.page.locator('#recipe-detail h2')).to_have_text('Чечевичный суп с овощами')
        expect(self.page.locator('#recipe-sync-notice')).to_have_attribute('role', 'status')
        scroll = self.page.locator('#recipe-dialog').evaluate('(dialog) => { dialog.scrollTop = 200; return dialog.scrollTop; }')
        self.page.locator('#recipe-sync-action').evaluate('(button) => button.click()')
        self.assertEqual(self.page.locator('#recipe-dialog').evaluate('(dialog) => dialog.scrollTop'), scroll)
        expect(self.page.locator('#recipe-detail h2')).to_have_text('Новая версия супа')
        expect(self.page.locator('#recipe-detail h2')).to_be_focused()
        expect(self.page.locator('#recipe-sync-notice')).to_be_hidden()
        expect(self.page.locator('.detail-stats')).to_contain_text('42 мин')
        revision = self.remote_update(other, lambda recipes: recipes.__setitem__(slice(None), [r for r in recipes if r['id'] != 'lentil-soup']))
        self.receive_revision(revision)
        expect(self.page.locator('#recipe-sync-message')).to_have_text('Этот рецепт удалён на другом устройстве')
        for selector in ['[data-edit]', '[data-delete]', '[data-favorite]']:
            expect(self.page.locator('#recipe-detail ' + selector)).to_be_disabled()
        self.page.locator('#recipe-sync-action').click()
        expect(self.page.locator('[data-id="lentil-soup"]')).to_have_count(0)
        expect(self.page.locator('#collection-title')).to_be_focused()
        expect(self.page.locator('#result-count')).to_have_text('7')
        self.assertEqual(self.context.request.get(self.url + '/api/library').json()['revision'], revision)

    def test_49_dirty_editor_survives_sync_cancel_and_saves_conflict_as_copy(self):
        other = self.remote_context()
        self.page.locator('[data-open="lentil-soup"]').click()
        self.page.locator('[data-edit]').click()
        form = self.page.locator('#recipe-form')
        form.locator('[name=title]').fill('Мой черновик A04')
        form.locator('.ingredient-name').first.fill('Красная чечевица A04')
        form.locator('.step-text').first.fill('Шаг A04')
        self.page.locator('#image-upload').set_input_files(ROOT / 'assets/food-grid.png')
        expect(self.page.locator('#image-preview img')).to_be_visible()
        photo = self.page.locator('#image-preview img').get_attribute('src')
        form.locator('.step-text').first.focus()
        form.locator('.step-text').first.evaluate('(field) => field.setSelectionRange(2, 4)')
        scroll = self.page.locator('#editor-dialog').evaluate('(dialog) => dialog.scrollTop')
        revision = self.remote_update(other, lambda recipes: next(r for r in recipes if r['id'] == 'lentil-soup').update(title='Версия другой сессии A04'))
        self.receive_revision(revision)
        expect(form.locator('.step-text').first).to_be_focused()
        self.assertEqual(form.locator('.step-text').first.evaluate('(field) => [field.selectionStart, field.selectionEnd]'), [2, 4])
        self.assertEqual(self.page.locator('#editor-dialog').evaluate('(dialog) => dialog.scrollTop'), scroll)
        self.page.once('dialog', lambda dialog: dialog.dismiss())
        self.page.keyboard.press('Escape')
        expect(self.page.locator('#editor-dialog')).to_be_visible()
        expect(form.locator('[name=title]')).to_have_value('Мой черновик A04')
        expect(form.locator('.ingredient-name').first).to_have_value('Красная чечевица A04')
        expect(form.locator('.step-text').first).to_have_value('Шаг A04')
        self.assertEqual(self.page.locator('#image-preview img').get_attribute('src'), photo)
        form.locator('[type=submit]').click()
        expect(self.page.locator('#save-copy')).to_be_visible()
        self.assertEqual(self.context.request.get(self.url + '/api/library').json()['revision'], revision)
        self.page.locator('#save-copy').click()
        expect(self.page.locator('#editor-dialog')).not_to_be_visible()
        stored = self.context.request.get(self.url + '/api/library').json()['recipes']
        self.assertEqual(next(r for r in stored if r['id'] == 'lentil-soup')['title'], 'Версия другой сессии A04')
        copy = next(r for r in stored if r['title'] == 'Мой черновик A04')
        self.assertEqual(copy['image'], photo)
        self.assertEqual(copy['ingredients'][0]['name'], 'Красная чечевица A04')
        self.assertEqual(copy['steps'][0], 'Шаг A04')
        self.assertEqual(len(stored), 9)

    def test_50_sync_transition_to_editor_and_unrelated_save_keep_remote_fields(self):
        other = self.remote_context()
        self.page.locator('[data-open="lentil-soup"]').click()
        with self.page.expect_response(lambda response: '/api/library' in response.url and response.request.method == 'PUT'):
            self.page.locator('#recipe-detail [data-favorite]').click()
        revision = self.remote_update(other, lambda recipes: next(r for r in recipes if r['id'] == 'salmon').update(title='Лосось A04'))
        self.receive_revision(revision)
        expect(self.page.locator('#recipe-sync-notice')).to_be_hidden()
        self.page.locator('[data-edit]').click()
        expect(self.page.locator('#editor-dialog')).to_be_visible()
        expect(self.page.locator('#recipe-dialog')).not_to_be_visible()
        # The queued close event must not render the library behind the new modal.
        expect(self.page.locator('[data-id="salmon"] .card-title')).to_have_text('Лосось с овощами')
        form = self.page.locator('#recipe-form')
        form.locator('[name=title]').fill('Суп A04')
        self.save(form)
        expect(self.page.locator('[data-id="salmon"] .card-title')).to_have_text('Лосось A04')
        stored = self.context.request.get(self.url + '/api/library').json()['recipes']
        self.assertEqual(next(r for r in stored if r['id'] == 'salmon')['title'], 'Лосось A04')
        self.assertEqual(next(r for r in stored if r['id'] == 'lentil-soup')['title'], 'Суп A04')
        form = self.fill_recipe('Новый рецепт A04')
        revision = self.remote_update(other, lambda recipes: next(r for r in recipes if r['id'] == 'salmon').update(title='Лосось после нового черновика'))
        self.receive_revision(revision)
        expect(form.locator('[name=title]')).to_have_value('Новый рецепт A04')
        self.save(form)
        expect(self.page.locator('[data-id="salmon"] .card-title')).to_have_text('Лосось после нового черновика')
        expect(self.page.locator('.recipe-card')).to_have_count(9)

    def test_51_catalog_other_dialogs_and_promoted_trial_apply_pending_sync(self):
        other = self.remote_context()
        for opener, dialog in [('#inspire', '#catalog-dialog'), ('#open-connection', '#connection-dialog'), ('.topbar .theme-toggle', '#theme-dialog')]:
            with self.subTest(dialog=dialog):
                self.page.locator(opener).first.click()
                title = 'Суп A04 ' + dialog
                revision = self.remote_update(other, lambda recipes: next(r for r in recipes if r['id'] == 'lentil-soup').update(title=title))
                self.receive_revision(revision)
                expect(self.page.locator(dialog)).to_be_visible()
                self.page.keyboard.press('Escape')
                expect(self.page.locator('[data-id="lentil-soup"] .card-title')).to_have_text(title, timeout=1000)
        self.assertEqual(other.request.post(self.url + '/api/catalog/mojito/save', data={'destination': 'trial'}).status, 201)
        self.receive_revision(other.request.get(self.url + '/api/library').json()['revision'])
        self.page.locator('[data-collection=trial]').first.click()
        self.page.locator('[data-open="catalog-mojito"]').click()
        before = other.request.get(self.url + '/api/library').json()
        self.assertEqual(other.request.post(self.url + '/api/trials/catalog-mojito/promote', data={}).status, 200)
        promoted = other.request.get(self.url + '/api/library').json()
        self.receive_revision(promoted['revision'])
        expect(self.page.locator('#recipe-detail [data-delete-trial]')).to_be_disabled()
        expect(self.page.locator('#recipe-detail [data-promote-trial]')).to_be_disabled()
        self.assertEqual(other.request.delete(self.url + '/api/trials/catalog-mojito', data={}).status, 409)
        self.page.locator('#recipe-sync-action').click()
        expect(self.page.locator('.trial-detail-note')).to_have_count(0)
        expect(self.page.locator('#recipe-detail [data-delete]')).to_be_enabled()
        self.page.keyboard.press('Escape')
        expect(self.page.locator('#recipe-grid .recipe-card')).to_have_count(0)
        expect(self.page.locator('#collection-title')).to_be_focused()
        expect(self.page.locator('#trial-count')).to_have_text('0')
        expect(self.page.locator('#all-count')).to_have_text('9')
        prior = next(r for r in before['recipes'] if r['id'] == 'catalog-mojito')
        after = next(r for r in promoted['recipes'] if r['id'] == 'catalog-mojito')
        self.assertGreaterEqual(after['createdAt'], prior['createdAt'])
        self.assertEqual({**prior, 'shelf': 'main', 'createdAt': after['createdAt']}, after)
        self.assertEqual(other.request.get(self.url + '/api/library').json(), promoted)

    def test_52_filtered_out_card_and_stacked_dialogs_restore_focus_safely(self):
        other = self.remote_context()
        self.page.locator('[data-collection=favorites]').first.click()
        self.page.locator('[data-open="avocado-toast"]').click()
        revision = self.remote_update(other, lambda recipes: next(r for r in recipes if r['id'] == 'avocado-toast').update(favorite=False))
        self.receive_revision(revision)
        self.page.locator('#theme-dialog').evaluate('(dialog) => dialog.showModal()')
        self.page.locator('#recipe-dialog').evaluate('(dialog) => dialog.close()')
        self.page.evaluate('() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))')
        expect(self.page.locator('#theme-dialog')).to_be_visible()
        expect(self.page.locator('#recipe-grid .recipe-card')).to_have_count(2)
        self.page.keyboard.press('Escape')
        expect(self.page.locator('#recipe-grid .recipe-card')).to_have_count(1)
        expect(self.page.locator('#collection-title')).to_be_focused()
        expect(self.page.locator('[data-collection=favorites]').first).to_have_class('nav-item active')
        self.assertEqual(self.context.request.get(self.url + '/api/library').json()['revision'], revision)

    def tab_to(self, selector, backwards=False):
        target = self.page.locator(selector).first
        for _ in range(160):
            if target.evaluate('(element) => element === document.activeElement'):
                return target
            self.page.keyboard.press('Shift+Tab' if backwards else 'Tab')
        self.fail(f'Keyboard cannot reach {selector}')

    def keyboard_text(self, text):
        self.page.keyboard.press('Control+a')
        self.page.keyboard.insert_text(text)

    def test_53_keyboard_create_edit_photo_and_focus_in_both_themes(self):
        # Arm interception before raw keyboard events; unlike locator.click(),
        # keyboard.press() has no actionability wait while interception starts.
        self.page.on('filechooser', lambda chooser: None)
        for theme, width in [('classic', 1440), ('halloween', 390)]:
            with self.subTest(theme=theme, width=width):
                self.page.evaluate('(theme) => localStorage.setItem("kroshka-appearance",theme)', theme)
                self.page.set_viewport_size({'width': width, 'height': 1000})
                self.page.reload(wait_until='networkidle')
                self.tab_to('#add-recipe')
                self.page.keyboard.press('Enter')
                expect(self.page.get_by_role('dialog', name='Новый рецепт')).to_be_visible()
                expect(self.page.locator('[name=title]')).to_be_focused()
                title = 'Клавиатурный суп ' + theme
                self.page.keyboard.insert_text(title)
                self.tab_to('[name=time]')
                self.keyboard_text('22')
                self.tab_to('.ingredient-name')
                self.page.keyboard.insert_text('Синтетическая чечевица')
                self.page.keyboard.press('Tab')
                self.page.keyboard.insert_text('200')
                self.tab_to('#add-ingredient')
                self.page.keyboard.press('Enter')
                expect(self.page.locator('.ingredient-name').nth(1)).to_be_focused()
                self.page.keyboard.insert_text('Тестовый лук')
                self.page.keyboard.press('Tab')
                self.page.keyboard.insert_text('50')
                self.tab_to('.step-text')
                self.page.keyboard.insert_text('Промыть ингредиенты.')
                self.tab_to('#add-step')
                self.page.keyboard.press('Space')
                expect(self.page.locator('.step-text').nth(1)).to_be_focused()
                self.page.keyboard.insert_text('Сварить суп.')
                self.tab_to('#choose-image')
                expect(self.page.get_by_role('button', name='Добавить фотографию', exact=True)).to_be_focused()
                with self.page.expect_file_chooser() as chooser:
                    self.page.keyboard.press('Enter')
                chooser.value.set_files(ROOT / 'assets/food-grid.png')
                expect(self.page.locator('#image-preview img')).to_be_visible()
                expect(self.page.locator('#editor-dialog [data-announcement]')).to_have_text('Фотография добавлена')
                self.tab_to('#save-recipe')
                self.page.keyboard.press('Enter')
                expect(self.page.locator('#editor-dialog')).not_to_be_visible()
                expect(self.page.locator('#add-recipe')).to_be_focused()
                expect(self.page.locator('#announcements')).to_have_text('Рецепт добавлен в вашу книгу')
                stored = self.context.request.get(self.url + '/api/library').json()['recipes']
                recipe = next(r for r in stored if r['title'] == title)
                self.assertEqual([i['name'] for i in recipe['ingredients']], ['Синтетическая чечевица', 'Тестовый лук'])
                self.assertEqual(recipe['steps'], ['Промыть ингредиенты.', 'Сварить суп.'])
                self.assertTrue(recipe['image'].startswith('data:image/jpeg;base64,'))
                opener = f'[data-open="{recipe["id"]}"]'
                self.tab_to(opener)
                self.page.keyboard.press('Enter')
                expect(self.page.get_by_role('dialog', name=title, exact=True)).to_be_visible()
                expect(self.page.locator('#recipe-title')).to_be_focused()
                self.tab_to('#recipe-dialog [data-edit]')
                self.page.keyboard.press('Space')
                expect(self.page.locator('[name=title]')).to_be_focused()
                self.keyboard_text(title + ' изменён')
                self.tab_to('#save-recipe')
                self.page.keyboard.press('Enter')
                expect(self.page.locator('#editor-dialog')).not_to_be_visible()
                expect(self.page.locator(opener)).to_be_focused()
                expect(self.page.locator('#announcements')).to_have_text('Изменения сохранены')
                self.page.reload(wait_until='networkidle')
                expect(self.page.locator(f'[data-id="{recipe["id"]}"] .card-title')).to_have_text(title + ' изменён')

    def test_54_photo_space_cancel_remove_and_retry_same_file(self):
        self.page.on('filechooser', lambda chooser: None)
        self.fill_recipe('Фото A05.1')
        self.tab_to('#choose-image')
        for key in ['Space', 'Enter']:
            expect(self.page.locator('#choose-image')).to_be_focused()
            with self.page.expect_file_chooser() as chooser:
                self.page.keyboard.press(key)
            chooser.value.set_files(ROOT / 'assets/food-grid.png')
            expect(self.page.locator('#image-preview img')).to_be_visible()
            photo = self.page.locator('#image-preview img').get_attribute('src')
            expect(self.page.locator('#choose-image')).to_be_focused()
            with self.page.expect_file_chooser() as chooser:
                self.page.keyboard.press(key)
            # Headless cancellation surrogate; native OS chooser remains manual QA.
            chooser.value.set_files([])
            self.assertEqual(self.page.locator('#image-preview img').get_attribute('src'), photo)
            self.tab_to('#remove-image')
            self.page.keyboard.press('Enter')
            expect(self.page.locator('#choose-image')).to_be_focused()
            expect(self.page.locator('#image-preview img')).to_have_count(0)
            expect(self.page.locator('#editor-dialog [data-announcement]')).to_have_text('Фотография удалена')
            expect(self.page.locator('#choose-image')).to_have_accessible_name('Добавить фотографию')
        self.page.locator('#image-upload').set_input_files(ROOT / 'assets/food-grid.png')
        expect(self.page.locator('#image-preview img')).to_be_visible()
        self.save(self.page.locator('#recipe-form'))
        snapshot = self.context.request.get(self.url + '/api/library').json()
        recipe = next(r for r in snapshot['recipes'] if r['title'] == 'Фото A05.1')
        self.tab_to(f'[data-open="{recipe["id"]}"]')
        self.page.keyboard.press('Enter')
        self.tab_to('#recipe-dialog [data-edit]')
        self.page.keyboard.press('Enter')
        self.tab_to('#choose-image')
        with self.page.expect_file_chooser() as chooser:
            self.page.keyboard.press('Space')
        chooser.value.set_files([])
        self.assertEqual(self.page.locator('#image-preview img').get_attribute('src'), recipe['image'])
        self.assertEqual(self.context.request.get(self.url + '/api/library').json(), snapshot)

    def test_55_photo_failures_keep_draft_and_existing_photo(self):
        form = self.fill_recipe('Ошибки фото A05.1')
        upload = self.page.locator('#image-upload')
        upload.set_input_files(ROOT / 'assets/food-grid.png')
        expect(self.page.locator('#image-preview img')).to_be_visible()
        photo = self.page.locator('#image-preview img').get_attribute('src')
        before = self.context.request.get(self.url + '/api/library').json()
        for file, message in [
            ({'name': 'bad.txt', 'mimeType': 'text/plain', 'buffer': b'bad'}, 'Выберите JPG, PNG или WebP размером до 15 МБ'),
            ({'name': 'large.png', 'mimeType': 'image/png', 'buffer': b'x' * (15 * 1024 * 1024 + 1)}, 'Выберите JPG, PNG или WebP размером до 15 МБ'),
            ({'name': 'broken.png', 'mimeType': 'image/png', 'buffer': b'not an image'}, 'Не удалось открыть изображение')
        ]:
            upload.set_input_files(file)
            expect(self.page.locator('#photo-error')).to_have_text(message)
            expect(self.page.locator('#photo-error')).to_have_attribute('role', 'alert')
            expect(self.page.locator('#choose-image')).to_have_attribute('aria-describedby', 'photo-hint photo-error')
            self.assertEqual(self.page.locator('#image-preview img').get_attribute('src'), photo)
            expect(form.locator('[name=title]')).to_have_value('Ошибки фото A05.1')
            expect(form.locator('.ingredient-name').first).to_have_value('Чечевица')
            expect(form.locator('.step-text').nth(1)).to_have_value('Добавить лук и варить до готовности.')
            self.assertEqual(self.context.request.get(self.url + '/api/library').json(), before)
        upload.set_input_files(ROOT / 'assets/food-grid.png')
        expect(self.page.locator('#photo-error')).to_be_empty()
        self.save(form)
        saved = next(r for r in self.context.request.get(self.url + '/api/library').json()['recipes'] if r['title'] == 'Ошибки фото A05.1')
        self.assertEqual(saved['image'], photo)

    def test_56_all_native_dialog_names_focus_tab_escape_and_return(self):
        cases = [
            ('#add-recipe', '#editor-dialog', 'Новый рецепт', '[name=title]'),
            ('[data-open=lentil-soup]', '#recipe-dialog', 'Чечевичный суп с овощами', '#recipe-title'),
            ('#inspire', '#catalog-dialog', None, '#catalog-search'),
            ('#open-connection', '#connection-dialog', 'Ваша кухня всегда рядом', '#connection-dialog .close-dialog'),
            ('.topbar .theme-toggle', '#theme-dialog', 'Немного другой магии', '#close-theme')
        ]
        for theme, width in [('classic', 1440), ('halloween', 390)]:
            self.page.evaluate('(theme) => localStorage.setItem("kroshka-appearance",theme)', theme)
            self.page.set_viewport_size({'width': width, 'height': 1000})
            self.page.reload(wait_until='networkidle')
            for opener, selector, name, initial in cases:
                with self.subTest(theme=theme, dialog=selector):
                    self.tab_to(opener)
                    self.page.keyboard.press('Enter')
                    dialog = self.page.locator(selector)
                    expect(dialog).to_be_visible()
                    if selector == '#catalog-dialog':
                        name = self.page.locator('#catalog-title').inner_text()
                        expect(self.page.locator('#catalog-next')).to_be_enabled()
                    expect(dialog).to_have_accessible_name(name)
                    expect(self.page.locator(initial)).to_be_focused()
                    # Walk more than one complete cycle in each direction.
                    count = dialog.locator('button:visible:enabled, input:visible:enabled, select:visible:enabled, textarea:visible:enabled, a[href]:visible, summary:visible').count()
                    for key in ['Tab', 'Shift+Tab']:
                        for _ in range(count + 2):
                            self.page.keyboard.press(key)
                            # Chromium may visit browser chrome (activeElement=body)
                            # at a cycle boundary. No background control may receive focus;
                            # the next Tab in the same direction must re-enter this modal.
                            if self.page.evaluate('document.activeElement === document.body'):
                                self.page.keyboard.press(key)
                            self.assertTrue(dialog.evaluate('(dialog) => dialog.contains(document.activeElement)'), key + ' focused background outside ' + selector)
                    self.page.keyboard.press('Escape')
                    expect(dialog).not_to_be_visible()
                    expect(self.page.locator(opener).first).to_be_focused()

    def test_57_dirty_keyboard_escape_cross_backdrop_and_confirm(self):
        self.tab_to('#add-recipe')
        self.page.keyboard.press('Enter')
        self.page.keyboard.insert_text('Не терять черновик')
        for close in ['escape', 'cross', 'backdrop']:
            self.page.once('dialog', lambda dialog: dialog.dismiss())
            if close == 'escape':
                self.page.keyboard.press('Escape')
            elif close == 'cross':
                self.tab_to('#editor-dialog .icon-button.close-dialog', backwards=True)
                self.page.keyboard.press('Enter')
            else:
                self.page.mouse.click(1, 1)
            expect(self.page.locator('#editor-dialog')).to_be_visible()
            expect(self.page.locator('[name=title]')).to_have_value('Не терять черновик')
            self.assertTrue(self.page.locator('#editor-dialog').evaluate('(dialog) => dialog.contains(document.activeElement)'))
        self.page.once('dialog', lambda dialog: dialog.accept())
        self.page.keyboard.press('Escape')
        expect(self.page.locator('#editor-dialog')).not_to_be_visible()
        expect(self.page.locator('#add-recipe')).to_be_focused()
        expect(self.page.locator('.recipe-card')).to_have_count(8)

    def test_58_selected_states_and_favorite_keyboard_focus(self):
        for selector in ['[data-collection=all]', '[data-quick=all]', '#grid-view']:
            expect(self.page.locator(selector).first).to_have_attribute('aria-pressed', 'true')
        for selector in ['[data-collection=favorites]', '[data-quick=fast]', '#list-view', '[data-meal="Завтрак"]']:
            self.tab_to(selector)
            self.page.keyboard.press('Enter')
            expect(self.page.locator(selector).first).to_have_attribute('aria-pressed', 'true')
            expect(self.page.locator(selector).first).to_be_focused()
        self.tab_to('[data-meal="Завтрак"]')
        self.page.keyboard.press('Enter')
        expect(self.page.locator('[data-meal="Завтрак"]')).to_have_attribute('aria-pressed', 'false')
        expect(self.page.locator('[data-collection=all]').first).to_have_attribute('aria-pressed', 'true')
        self.tab_to('[data-quick=all]')
        self.page.keyboard.press('Enter')
        self.tab_to('[data-favorite=lentil-soup]')
        self.page.keyboard.press('Enter')
        favorite = self.page.locator('[data-favorite=lentil-soup]')
        expect(favorite).to_have_attribute('aria-pressed', 'true')
        expect(favorite).to_be_focused()
        self.tab_to('[data-open=lentil-soup]', backwards=True)
        self.page.keyboard.press('Enter')
        self.tab_to('#recipe-dialog [data-favorite]')
        self.page.keyboard.press('Space')
        expect(self.page.locator('#recipe-dialog [data-favorite]')).to_have_attribute('aria-pressed', 'false')
        expect(self.page.locator('#recipe-dialog [data-favorite]')).to_be_focused()
        self.page.keyboard.press('Escape')
        expect(self.page.locator('[data-open=lentil-soup]')).to_be_focused()
        self.tab_to('#filter-toggle')
        self.page.keyboard.press('Space')
        expect(self.page.locator('#filter-toggle')).to_have_attribute('aria-expanded', 'true')
        expect(self.page.locator('#filter-toggle')).to_have_attribute('aria-controls', 'filters')
        self.tab_to('#filter-meat')
        self.page.keyboard.press('End')
        expect(self.page.locator('#filter-meat')).to_have_value('С мясом')
        # Additional meal conditions do not change the collection being searched.
        self.page.locator('#filter-meal').select_option('Завтрак')
        expect(self.page.locator('[data-collection=all]').first).to_have_attribute('aria-pressed', 'true')
        self.tab_to('[data-collection=favorites]')
        self.page.keyboard.press('Enter')
        self.page.locator('#filter-meal').select_option('Завтрак')
        expect(self.page.locator('[data-collection=favorites]').first).to_have_attribute('aria-pressed', 'true')
        expect(self.page.locator('[data-collection=all]').first).to_have_attribute('aria-pressed', 'false')

    def test_59_linked_field_errors_and_save_failure_retry_announcements(self):
        form = self.fill_recipe('   ')
        before = self.context.request.get(self.url + '/api/library').json()
        form.locator('[type=submit]').click()
        expect(form.locator('[name=title]')).to_have_attribute('aria-invalid', 'true')
        expect(form.locator('[name=title]')).to_have_attribute('aria-describedby', 'form-error')
        expect(form.locator('[name=title]')).to_be_focused()
        expect(self.page.locator('#form-error')).to_contain_text('Заполните название')
        self.keyboard_text('Сохранение A05.1')
        expect(form.locator('[name=title]')).not_to_have_attribute('aria-invalid', 'true')

        def reject(route):
            if route.request.method == 'PUT':
                route.fulfill(status=503, content_type='application/json', body=json.dumps({'error': 'Тестовая ошибка сохранения'}))
            else:
                route.continue_()

        self.page.route('**/api/library', reject)
        form.locator('[type=submit]').click()
        expect(self.page.locator('#form-error')).to_have_text('Тестовая ошибка сохранения')
        expect(self.page.locator('#form-error')).to_have_attribute('role', 'alert')
        expect(self.page.locator('#editor-dialog [data-announcement]')).to_be_empty()
        expect(form.locator('[name=title]')).to_have_value('Сохранение A05.1')
        self.assertEqual(self.context.request.get(self.url + '/api/library').json(), before)
        self.page.unroute('**/api/library', reject)
        self.save(form)
        expect(self.page.locator('#announcements')).to_have_text('Рецепт добавлен в вашу книгу')
        expect(self.page.locator('#announcements')).to_have_attribute('role', 'status')
        # A toast inside a modal needs a live region in that modal's accessible subtree.
        self.page.locator('#inspire').click()
        expect(self.page.locator('#catalog-save')).to_be_enabled()
        self.page.locator('#catalog-save').click()
        expect(self.page.locator('#catalog-dialog [data-announcement]')).to_contain_text('Рецепт добавлен')
        expect(self.page.locator('#catalog-dialog [data-announcement]')).to_have_attribute('role', 'status')

    def test_60_search_and_remote_notice_do_not_repeat_on_polling(self):
        expect(self.page.locator('#search-results-status')).to_have_text('Найдено рецептов: 8')
        self.page.evaluate('''() => {
            window.resultAnnouncements = [];
            new MutationObserver(() => resultAnnouncements.push(document.querySelector('#search-results-status').textContent))
                .observe(document.querySelector('#search-results-status'), {childList:true,subtree:true,characterData:true});
        }''')
        self.page.keyboard.press('/')
        self.page.keyboard.type('чечевица', delay=20)
        expect(self.page.locator('#search-results-status')).to_have_text('Найдено рецептов: 2. Поиск: чечевица')
        self.assertEqual(self.page.evaluate('resultAnnouncements'), ['Найдено рецептов: 2. Поиск: чечевица'])
        expect(self.page.locator('#search')).to_be_focused()
        with self.page.expect_response(lambda r: '/api/library?' in r.url and r.json().get('unchanged')):
            self.page.evaluate("window.dispatchEvent(new Event('online'))")
        self.assertEqual(self.page.evaluate('resultAnnouncements'), ['Найдено рецептов: 2. Поиск: чечевица'])
        self.tab_to('[data-open=lentil-soup]')
        self.page.keyboard.press('Enter')
        other = self.remote_context()
        revision = self.remote_update(other, lambda recipes: next(r for r in recipes if r['id'] == 'lentil-soup').update(title='Суп A05.1 из другой сессии'))
        self.receive_revision(revision)
        expect(self.page.locator('#recipe-sync-message')).to_have_text('Рецепт изменён на другом устройстве')
        self.page.evaluate('''() => {
            window.syncAnnouncements = 0;
            new MutationObserver(() => syncAnnouncements++)
                .observe(document.querySelector('#recipe-sync-message'), {childList:true,subtree:true,characterData:true});
        }''')
        revision = self.remote_update(other, lambda recipes: next(r for r in recipes if r['id'] == 'salmon').update(title='Другая запись A05.1'))
        self.receive_revision(revision)
        self.assertEqual(self.page.evaluate('syncAnnouncements'), 0)
        expect(self.page.locator('#recipe-title')).to_be_focused()
        self.page.keyboard.press('Escape')
        expect(self.page.locator('[data-open=lentil-soup]')).to_be_focused()
        expect(self.page.locator('[data-id=lentil-soup] .card-title')).to_have_text('Суп A05.1 из другой сессии')

    def test_61_contrast_themes_viewports_and_surfaces(self):
        # All text, inputs/placeholders, essential icons/edges and pseudo labels
        # use resolved styles, inheritance, opacity and gradient stop bounds.
        for theme in ['classic', 'halloween']:
            for width in [1440, 390]:
                with self.subTest(theme=theme, width=width):
                    self.page.set_viewport_size({'width': width, 'height': 1000})
                    self.page.evaluate('(t)=>localStorage.setItem("kroshka-appearance",t)', theme)
                    self.page.reload(wait_until='networkidle')
                    self.page.locator('#filter-toggle').click()
                    assert_text_contrast(self, self.page)
                    for target in ['#add-recipe', '.chip.active', '.nav-item.active']:
                        self.page.locator(target).first.hover()
                        assert_text_contrast(self, self.page)
                    self.page.locator('[data-quick=protein]').click()
                    assert_text_contrast(self, self.page)
                    self.page.locator('[data-quick=all]').click()
                    self.page.locator('#list-view').click()
                    assert_text_contrast(self, self.page)
                    self.page.locator('#grid-view').click()
                    for opener, root in [
                        ('[data-open=lentil-soup]', '#recipe-dialog'),
                        ('#add-recipe', '#editor-dialog'),
                        ('#inspire', '#catalog-dialog'),
                        ('#open-connection', '#connection-dialog'),
                        ('.topbar .theme-toggle', '#theme-dialog')
                    ]:
                        self.page.locator(opener).click()
                        if root == '#editor-dialog':
                            self.page.locator('#nutrition-details summary').click()
                            self.page.locator('.method-option').first.click()
                            self.page.locator('#choose-image').hover()
                        if root == '#catalog-dialog':
                            expect(self.page.locator('#catalog-next')).to_be_enabled()
                        assert_text_contrast(self, self.page, root)
                        if root == '#editor-dialog':
                            self.page.once('dialog', lambda d: d.accept())
                        self.page.keyboard.press('Escape')

    def test_62_contrast_keyboard_focus_and_photo_controls(self):
        for theme in ['classic', 'halloween']:
            for width in [1440, 390]:
                with self.subTest(theme=theme, width=width):
                    self.page.set_viewport_size({'width': width, 'height': 1000})
                    self.page.evaluate('(t)=>localStorage.setItem("kroshka-appearance",t)', theme)
                    self.page.reload(wait_until='networkidle')
                    for target in ['#search', '#add-recipe', '[data-open=lentil-soup]', '[data-favorite=lentil-soup]', '.topbar .theme-toggle']:
                        self.tab_to(target)
                        assert_text_contrast(self, self.page)
                        focused = self.page.locator(target)
                        self.assertTrue(focused.evaluate('(e)=>e.matches(":focus-visible")'))
                        # The outer card ring is on the unclipped parent.
                        ring = focused.locator('..') if target.startswith('[data-open=') or target == '#search' else focused
                        style = ring.evaluate('(e)=>{const s=getComputedStyle(e);return [s.outlineWidth,s.outlineOffset,s.outlineStyle]}')
                        self.assertEqual(style, ['2px', '2px', 'solid'])
                    self.page.locator('#add-recipe').click()
                    for target in ['[name=title]', '.ingredient-name', '.step-text', '#choose-image', '#nutrition-details summary', '.method-option input']:
                        self.tab_to(target)
                        assert_text_contrast(self, self.page, '#editor-dialog')
                    # Checkbox mark uses the native accent, checked AND unchecked.
                    self.page.keyboard.press('Space')
                    assert_text_contrast(self, self.page, '#editor-dialog')
                    self.page.once('dialog', lambda d: d.accept())
                    self.page.keyboard.press('Escape')

    def test_63_contrast_auth_errors_save_conflict_status_and_trials(self):
        for theme in ['classic', 'halloween']:
            for width in [1440, 390]:
                with self.subTest(theme=theme, width=width):
                    self.page.set_viewport_size({'width': width, 'height': 1000})
                    self.page.evaluate('(t)=>localStorage.setItem("kroshka-appearance",t)', theme)
                    self.page.reload(wait_until='networkidle')
                    snapshot = self.context.request.get(self.url + '/api/library').json()
                    self.assertEqual(self.context.request.put(self.url + '/api/library', data={'revision':snapshot['revision'],'recipes':self.seeds}).status, 200)
                    self.page.reload(wait_until='networkidle')
                    form = self.fill_recipe('   ')
                    form.locator('[type=submit]').click()
                    expect(self.page.locator('#form-error')).not_to_be_empty()
                    assert_text_contrast(self, self.page, '#editor-dialog')
                    form.locator('[name=title]').fill('Контраст A05.2')
                    # Hold the actual PUT to inspect disabled pending controls.
                    pending = []
                    def reject(route):
                        if route.request.method == 'PUT':
                            pending.append(route)
                        else:
                            route.continue_()
                    self.page.route('**/api/library', reject)
                    form.locator('[type=submit]').click()
                    expect(self.page.locator('#save-recipe')).to_be_disabled()
                    disabled_rows = measurements(self.page, '#editor-dialog')
                    self.assertTrue(any(r['disabled'] for r in disabled_rows))
                    assert_text_contrast(self, self.page, '#editor-dialog')
                    self.assertEqual(len(pending), 1)
                    pending[0].fulfill(status=503, content_type='application/json', body=json.dumps({'error':'Тестовая ошибка сохранения'}))
                    expect(self.page.locator('#form-error')).to_have_text('Тестовая ошибка сохранения')
                    assert_text_contrast(self, self.page, '#editor-dialog')
                    self.page.unroute('**/api/library', reject)
                    self.save(form)
                    expect(self.page.locator('.toast.visible')).to_have_css('opacity', '1')
                    assert_text_contrast(self, self.page)
                    self.page.locator('[data-open=lentil-soup]').click()
                    other = self.remote_context()
                    revision = self.remote_update(other, lambda recipes: next(r for r in recipes if r['id']=='lentil-soup').update(title='Удалённая правка A05.2'))
                    self.receive_revision(revision)
                    expect(self.page.locator('#recipe-sync-notice')).to_be_visible()
                    assert_text_contrast(self, self.page, '#recipe-dialog')
                    self.page.locator('#recipe-sync-action').click()
                    self.page.locator('[data-edit]').click()
                    self.page.locator('[name=title]').fill('Локальная правка A05.2')
                    revision = self.remote_update(other, lambda recipes: next(r for r in recipes if r['id']=='lentil-soup').update(title='Новая удалённая правка A05.2'))
                    self.receive_revision(revision)
                    self.page.locator('#save-recipe').click()
                    expect(self.page.locator('#save-copy')).to_be_visible()
                    assert_text_contrast(self, self.page, '#editor-dialog')
                    self.page.once('dialog', lambda d: d.accept())
                    self.page.keyboard.press('Escape')
                    self.page.locator('[data-collection=trial]').first.click()
                    assert_text_contrast(self, self.page)
                    self.page.locator('#inspire').click()
                    expect(self.page.locator('#catalog-save-trial')).to_be_enabled()
                    self.page.locator('#catalog-save-trial').click()
                    self.page.keyboard.press('Escape')
                    assert_text_contrast(self, self.page)
                    self.page.locator('#logout').click()
                    expect(self.page.locator('#auth-screen')).to_be_visible()
                    assert_text_contrast(self, self.page, '#auth-screen')
                    self.page.locator('#family-password').fill('invalid-test-password')
                    self.page.locator('#auth-form [type=submit]').click()
                    expect(self.page.locator('#auth-error')).not_to_be_empty()
                    assert_text_contrast(self, self.page, '#auth-screen')
                    self.page.locator('#family-password').fill(self.password)
                    self.page.locator('#auth-form [type=submit]').click()
                    expect(self.page.locator('#auth-screen')).not_to_be_visible()

    def test_64_contrast_rendered_hero_artwork_and_photo_focus(self):
        self.page.emulate_media(reduced_motion='reduce')
        for theme in ['classic', 'halloween']:
            for width in [1440, 390]:
                with self.subTest(theme=theme, width=width):
                    self.page.set_viewport_size({'width':width,'height':1000})
                    self.page.evaluate('(t)=>localStorage.setItem("kroshka-appearance",t)', theme)
                    self.page.reload(wait_until='networkidle')
                    rows = artwork_measurements(self.page, '.hero')
                    self.assertGreater(len(rows), 3)
                    self.assertEqual([r for r in rows if r['ratio'] < r['minimum']], [], str(rows))
                    # Opaque icon/badge surfaces retain contrast on synthetic extremes,
                    # without changing or relying on any real user's photograph.
                    for photo in ['#000', '#fff']:
                        self.page.locator('[data-id=lentil-soup] .card-image').evaluate('(e,c)=>{e.querySelectorAll("img,.food-photo").forEach(n=>n.remove());e.style.background=c}',photo)
                        self.tab_to('[data-favorite=lentil-soup]')
                        assert_text_contrast(self, self.page)
                        button = self.page.locator('[data-favorite=lentil-soup]')
                        self.assertNotEqual(button.evaluate('(e)=>getComputedStyle(e).boxShadow'), 'none')

if __name__ == '__main__':
    unittest.main(verbosity=2)
