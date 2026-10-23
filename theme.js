/* Appearance is local to this device and never changes the family recipe book. */
(() => {
  const key = 'kroshka-appearance';
  const choices = ['auto', 'halloween', 'classic'];
  let choice = 'auto';
  try { const saved = localStorage.getItem(key); if (choices.includes(saved)) choice = saved; } catch {}
  const root = document.documentElement;
  // Select before the SVG is parsed/painted. Safari and iOS WebKit use the
  // original bitmap without displacement filters (edge artifacts on devices).
  const ua = navigator.userAgent;
  const webkit = /AppleWebKit\//.test(ua) && !/(?:Chrome|Chromium|Edg|OPR|SamsungBrowser)\//.test(ua);
  root.dataset.catMotion = webkit ? 'css' : 'smil';
  let originals;
  const seasonalCopy = {
    '.page-heading .eyebrow': 'ОСЕНЬ НА КУХНЕ · 20–31 ОКТЯБРЯ',
    '.page-heading h1': 'Рецепты с щепоткой <em>волшебства</em>',
    '.page-heading p': 'Любимые блюда, тёплые вечера и немного домашних чар.',
    '.hero-tag': '<svg><use href="#i-moon"/></svg> ТЫКВЫ, ПРЯНОСТИ И НЕМНОГО МАГИИ',
    '.hero h2': 'Сварим немного<br><em>волшебства?</em>',
    '.hero-copy p': 'Пусть за окном темнеет.<br>На нашей кухне всегда тепло.',
    '.hero-link': 'Открыть книгу заклинаний <svg><use href="#i-arrow"/></svg>',
    '.sidebar-note p': 'Домашняя магия<br>начинается на кухне.',
    '.sidebar-note>span': 'Щепотка корицы.<br>И целый вечер вместе.',
    '#catalog-title': 'Книга заклинаний',
    '.collection-hint': 'Проверенные семейные заклинания',
  };
  function apply() {
    const now = new Date();
    const seasonal = now.getMonth() === 9 && now.getDate() >= 20 && now.getDate() <= 31;
    const theme = choice === 'auto' ? (seasonal ? 'halloween' : 'classic') : choice;
    root.dataset.theme = theme;
    document.querySelector('meta[name="theme-color"]')?.setAttribute('content', theme === 'halloween' ? '#211a24' : '#f7f9f5');
    if (!originals) return;
    for (const [selector, content] of Object.entries(theme === 'halloween' ? seasonalCopy : originals)) {
      const element = document.querySelector(selector);
      if (element) element.innerHTML = selector==='.collection-hint'&&document.querySelector('.recipe-section')?.dataset.collectionView==='trial'?'Идеи, которые хочется приготовить':content;
    }
    document.querySelectorAll('[data-theme-choice]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.themeChoice === choice)));
  }
  apply();
  document.addEventListener('DOMContentLoaded', () => {
    originals = Object.fromEntries(Object.keys(seasonalCopy).map(selector => [selector, document.querySelector(selector)?.innerHTML ?? '']));
    const dialog = document.querySelector('#theme-dialog');
    document.querySelectorAll('.theme-toggle').forEach(button => button.addEventListener('click', () => dialog.showModal()));
    document.querySelector('#close-theme')?.addEventListener('click', () => dialog.close());
    dialog?.addEventListener('click', event => { if (event.target === dialog) { const r = dialog.getBoundingClientRect(); if (event.clientX < r.left || event.clientX > r.right || event.clientY < r.top || event.clientY > r.bottom) dialog.close(); } });
    document.querySelectorAll('[data-theme-choice]').forEach(button => button.addEventListener('click', () => {
      choice = button.dataset.themeChoice;
      try { localStorage.setItem(key, choice); } catch {}
      apply();
    }));
    apply();
  });
  // Also update tabs left open over the end of October or restored from sleep.
  document.addEventListener('visibilitychange', () => { if (!document.hidden) apply(); });
  window.addEventListener('storage', event => {
    if (event.key === key) { choice = choices.includes(event.newValue) ? event.newValue : 'auto'; apply(); }
  });
  setInterval(apply, 60000);
})();
