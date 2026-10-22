#!/bin/bash
set -euo pipefail
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:${PATH:-}"
TASK_SOURCE_DIR="$(cd "$(dirname "$0")" && pwd)"
TASK_BASE_DIR="$HOME/Library/Application Support/Kroshka"
TASK_RUNTIME_DIR="$TASK_BASE_DIR/app"
TASK_DATA_DIR="$TASK_BASE_DIR/data"
TASK_PLIST="$HOME/Library/LaunchAgents/dev.kroshka.recipes.plist"
TASK_DOMAIN="gui/$(id -u)"
finish_error() { echo; echo "$1"; echo 'Нажмите Enter, чтобы закрыть окно.'; read -r _; exit 1; }
[ "$(uname -s)" = Darwin ] || { echo 'Этот установщик предназначен для macOS.'; exit 1; }
TASK_NODE_BIN="$(command -v node || true)"
[ -n "$TASK_NODE_BIN" ] || finish_error 'Нужен Node.js 22.13 или новее. Установите LTS с https://nodejs.org и откройте установщик снова.'
"$TASK_NODE_BIN" --input-type=module -e "import {DatabaseSync} from 'node:sqlite';const [a,b]=process.versions.node.split('.').map(Number);if(a<22||(a===22&&b<13))process.exit(1)" >/dev/null 2>&1 || finish_error 'Node.js не запускается или слишком старый. Установите текущую LTS-версию с https://nodejs.org.'
for TASK_REQUIRED in server.js catalog.js recipes.seed.json catalog/recipes.json catalog/cocktails.json catalog/image-index.json catalog.css; do
  [ -f "$TASK_SOURCE_DIR/$TASK_REQUIRED" ] || finish_error 'Сначала распакуйте весь архив, затем откройте установщик внутри распакованной папки.'
done
if ! launchctl print "$TASK_DOMAIN/dev.kroshka.recipes" >/dev/null 2>&1 && /usr/sbin/lsof -iTCP:3847 -sTCP:LISTEN -t >/dev/null 2>&1; then
  finish_error 'Порт 3847 занят другой программой. Закройте её и запустите установщик снова. Крошка не останавливает чужие процессы.'
fi
printf '\nКрошка — устанавливаем вашу семейную книгу\n\n'
mkdir -p "$TASK_RUNTIME_DIR/assets" "$TASK_DATA_DIR" "$TASK_BASE_DIR/logs" "$HOME/Library/LaunchAgents" "$HOME/Applications/Крошка.app/Contents/MacOS" "$HOME/Applications/Крошка.app/Contents/Resources"
chmod 700 "$TASK_BASE_DIR" "$TASK_DATA_DIR"
if [ -f "$TASK_PLIST" ]; then launchctl bootout "$TASK_DOMAIN" "$TASK_PLIST" >/dev/null 2>&1 || true; fi
for TASK_FILE in server.js catalog.js recipes.seed.json package.json index.html app.js theme.js style.css halloween.css catalog.css manifest.webmanifest sw.js offline.html; do
  cp "$TASK_SOURCE_DIR/$TASK_FILE" "$TASK_RUNTIME_DIR/$TASK_FILE"
done
cp -R "$TASK_SOURCE_DIR/assets/." "$TASK_RUNTIME_DIR/assets/"
mkdir -p "$TASK_RUNTIME_DIR/catalog"
cp -R "$TASK_SOURCE_DIR/catalog/." "$TASK_RUNTIME_DIR/catalog/"
TASK_LOCAL_HOST="$(/usr/sbin/scutil --get LocalHostName 2>/dev/null || true)"
# Paths and XML characters are escaped by the bundled configuration writer.
"$TASK_NODE_BIN" "$TASK_SOURCE_DIR/mac/write-launch-agent.js" "$TASK_PLIST" "$TASK_NODE_BIN" "$TASK_RUNTIME_DIR" "$TASK_DATA_DIR" "$TASK_BASE_DIR" "$TASK_LOCAL_HOST"
/usr/bin/plutil -lint "$TASK_PLIST"
cp "$TASK_SOURCE_DIR/mac/Info.plist" "$HOME/Applications/Крошка.app/Contents/Info.plist"
cp "$TASK_SOURCE_DIR/mac/Kroshka" "$HOME/Applications/Крошка.app/Contents/MacOS/Kroshka"
chmod 755 "$HOME/Applications/Крошка.app/Contents/MacOS/Kroshka"
if [ -f "$TASK_SOURCE_DIR/assets/icon-512.png" ]; then
  TASK_ICON_DIR="$(mktemp -d "$TASK_BASE_DIR/icon-build.XXXXXX")"
  mkdir "$TASK_ICON_DIR/Kroshka.iconset"
  for TASK_SIZE in 16 32 128 256 512; do
    /usr/bin/sips -z "$TASK_SIZE" "$TASK_SIZE" "$TASK_SOURCE_DIR/assets/icon-512.png" --out "$TASK_ICON_DIR/Kroshka.iconset/icon_${TASK_SIZE}x${TASK_SIZE}.png" >/dev/null
  done
  cp "$TASK_SOURCE_DIR/assets/icon-512.png" "$TASK_ICON_DIR/Kroshka.iconset/icon_256x256@2x.png"
  /usr/bin/iconutil -c icns "$TASK_ICON_DIR/Kroshka.iconset" -o "$HOME/Applications/Крошка.app/Contents/Resources/Kroshka.icns" 2>/dev/null || true
  rm -rf "$TASK_ICON_DIR"
fi
launchctl bootstrap "$TASK_DOMAIN" "$TASK_PLIST" || finish_error 'Не удалось включить фоновый запуск. Проверьте «Системные настройки → Основные → Объекты входа».'
TASK_READY=0
for TASK_ATTEMPT in {1..30}; do
  if /usr/bin/curl --fail --silent --max-time 1 http://localhost:3847/healthz >/dev/null; then TASK_READY=1; break; fi
  sleep 0.5
done
[ "$TASK_READY" = 1 ] || finish_error "Сайт пока не запустился. Журнал: $TASK_BASE_DIR/logs/server-error.log"
/usr/bin/open "$HOME/Applications/Крошка.app"
/usr/bin/open -R "$HOME/Applications/Крошка.app"
echo
echo 'Готово! Войдите с вашим семейным паролем. При первом запуске создайте его на открывшейся странице.'
echo 'Для телефона нажмите на сайте «Открыть на телефоне».'
echo 'Приложение «Крошка» находится в папке «Программы» вашего пользователя; перетащите его в Dock.'
echo 'Книга запускается автоматически при вашем входе в macOS. Это окно можно закрыть.'
echo 'Mac должен быть включён; при питании от сети Крошка предотвращает автоматический сон. Закрытая крышка или ручной сон отключат доступ.'
