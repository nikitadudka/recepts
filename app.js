'use strict';
(async function startKroshka() {
const $ = (selector, scope = document) => scope.querySelector(selector);
const $$ = (selector, scope = document) => [...scope.querySelectorAll(selector)];
const icon = (name) => `<svg aria-hidden="true"><use href="#i-${name}"/></svg>`;
const escapeHTML = (value) => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const storageKey = 'kroshka-recipes-v1';
const ingredient = (name, amount, unit = 'г') => ({name, amount, unit});
const seeds = [
  {id:'lentil-soup',title:'Чечевичный суп с овощами',time:35,servings:4,meal:'Обед',size:'Полноценное',macro:'Углеводное',meat:'Без мяса',calories:78,protein:4.2,fat:2.1,carbs:11.5,image:'sample:soup',ingredients:[ingredient('Красная чечевица',200),ingredient('Лук',100),ingredient('Морковь',120),ingredient('Томаты',200),ingredient('Оливковое масло',15),ingredient('Вода',1000,'мл'),ingredient('Соль и паприка','','по вкусу')],instructions:'Промойте чечевицу. Нарежьте лук, морковь и томаты.\nВ кастрюле разогрейте масло. Обжарьте лук и морковь 5 минут, добавьте томаты и паприку.\nВсыпьте чечевицу, залейте водой. Доведите до кипения и варите 20–25 минут до мягкости.\nПосолите по вкусу. Подавайте с зеленью и ломтиком лимона.',favorite:false,createdAt:8},
  {id:'avocado-toast',title:'Тост с авокадо и яйцом',time:15,servings:1,meal:'Завтрак',size:'Лёгкое',macro:'Жирное',meat:'Без мяса',calories:196,protein:7.8,fat:12.4,carbs:13.2,image:'sample:toast',ingredients:[ingredient('Цельнозерновой хлеб',60),ingredient('Авокадо',80),ingredient('Яйцо',1,'шт'),ingredient('Лимонный сок',5,'мл'),ingredient('Соль и перец','','по вкусу')],instructions:'Поджарьте хлеб на сухой сковороде или в тостере.\nРазомните авокадо вилкой с лимонным соком, солью и перцем.\nПриготовьте яйцо на сковороде 3–4 минуты или сварите пашот.\nНамажьте авокадо на тост, сверху положите яйцо. Подавайте сразу.',favorite:true,createdAt:7},
  {id:'chicken-bowl',title:'Боул с курицей и киноа',time:30,servings:2,meal:'Обед',size:'Полноценное',macro:'Белковое',meat:'С мясом',calories:145,protein:14.6,fat:4.3,carbs:12.1,image:'sample:bowl',ingredients:[ingredient('Куриное филе',250),ingredient('Киноа',100),ingredient('Огурец',120),ingredient('Помидоры черри',100),ingredient('Салат',50),ingredient('Оливковое масло',10),ingredient('Соль и специи','','по вкусу')],instructions:'Промойте киноа, залейте водой в соотношении 1:2 и варите под крышкой 15 минут.\nНарежьте курицу, посолите и приправьте. Обжаривайте на масле 8–10 минут до полной готовности, температура внутри — не менее 74 °C.\nНарежьте огурец и помидоры, промойте салат.\nРазложите киноа, курицу и овощи по мискам. Добавьте любимую заправку.',favorite:false,createdAt:6},
  {id:'berry-oats',title:'Овсянка с ягодами',time:10,servings:1,meal:'Завтрак',size:'Полноценное',macro:'Углеводное',meat:'Без мяса',calories:112,protein:3.5,fat:3.1,carbs:17.8,image:'sample:oats',ingredients:[ingredient('Овсяные хлопья',50),ingredient('Молоко',200,'мл'),ingredient('Ягоды',70),ingredient('Мёд',10),ingredient('Миндаль',10)],instructions:'Налейте молоко в небольшую кастрюлю и доведите до слабого кипения.\nДобавьте хлопья и варите 5–7 минут, помешивая.\nПереложите в тарелку, добавьте ягоды, мёд и рубленый миндаль.',favorite:false,createdAt:5},
  {id:'green-salad',title:'Зелёный салат с фетой',time:15,servings:2,meal:'Ужин',size:'Лёгкое',macro:'Жирное',meat:'Без мяса',calories:121,protein:4.7,fat:9.2,carbs:4.6,image:'sample:salad',ingredients:[ingredient('Листья салата',100),ingredient('Огурец',150),ingredient('Фета',100),ingredient('Авокадо',100),ingredient('Оливковое масло',10),ingredient('Лимонный сок',10,'мл')],instructions:'Промойте и обсушите листья салата. Порвите крупными кусочками.\nНарежьте огурец и авокадо, раскрошите фету.\nСмешайте масло с лимонным соком. Аккуратно перемешайте салат с заправкой перед подачей.',favorite:true,createdAt:4},
  {id:'salmon',title:'Лосось с овощами',time:25,servings:2,meal:'Ужин',size:'Полноценное',macro:'Белковое',meat:'Без мяса',calories:156,protein:15.3,fat:8.6,carbs:4.2,image:'sample:salmon',ingredients:[ingredient('Филе лосося',300),ingredient('Брокколи',200),ingredient('Кабачок',150),ingredient('Лимон',50),ingredient('Оливковое масло',10),ingredient('Соль и перец','','по вкусу')],instructions:'Разогрейте духовку до 200 °C. Разберите брокколи на соцветия, нарежьте кабачок.\nВыложите овощи и лосось в форму, сбрызните маслом, приправьте и добавьте ломтики лимона.\nЗапекайте 18–20 минут до готовности рыбы (температура внутри — 63 °C).',favorite:false,createdAt:3},
  {id:'lentil-cutlets',title:'Котлетки из чечевицы',time:40,servings:3,meal:'Ужин',size:'Полноценное',macro:'Белковое',meat:'Без мяса',calories:134,protein:8.2,fat:3.6,carbs:17.1,image:'sample:cutlets',ingredients:[ingredient('Зелёная чечевица',200),ingredient('Лук',100),ingredient('Морковь',80),ingredient('Овсяная мука',30),ingredient('Оливковое масло',15),ingredient('Соль и зира','','по вкусу')],instructions:'Отварите чечевицу до мягкости, слейте воду и дайте немного остыть.\nМелко нарежьте лук, натрите морковь. Обжарьте 5 минут с половиной масла.\nРазомните чечевицу, смешайте с овощами, мукой и специями. Сформируйте небольшие котлетки.\nОбжарьте на оставшемся масле по 4–5 минут с каждой стороны.',favorite:false,createdAt:2},
  {id:'cottage-cheese',title:'Творожный боул с ягодами',time:5,servings:1,meal:'Перекус',size:'Лёгкое',macro:'Белковое',meat:'Без мяса',calories:128,protein:12.8,fat:4.2,carbs:9.4,image:'sample:curd',ingredients:[ingredient('Творог 5%',150),ingredient('Натуральный йогурт',50),ingredient('Клубника',70),ingredient('Мёд',10)],instructions:'Смешайте творог с йогуртом до нежной консистенции.\nНарежьте ягоды и выложите сверху. Добавьте мёд по вкусу.',favorite:false,createdAt:1}
];
let recipes = [];
let catalogArt = {};
let revision = 0;
let legacyRecipes = [];
let lastSaveError = '';
let authState;
let formDirty = false;
let editingSnapshot = null;
let syncing = false;
async function api(url,options={}) {
  let response;
  try { response = await fetch(url,{...options,headers:{'Content-Type':'application/json',...options.headers},cache:'no-store'}); }
  catch { throw new Error('Не удаётся связаться с Mac. Проверьте Wi-Fi и убедитесь, что Mac включён и не спит.'); }
  let result;
  try { result = await response.json(); } catch { throw new Error('Не удалось открыть книгу. Откройте её через приложение «Крошка», а не файл index.html.'); }
  if (!response.ok) { const error = new Error(result.error || 'Не удалось сохранить изменения.'); error.status=response.status; throw error; }
  return result;
}
async function refreshLibrary(force=false) {
  const result=await api('/api/library'+(force?'':`?revision=${revision}`));
  if (!result.unchanged) { recipes=result.recipes; revision=result.revision; if (!document.querySelector('dialog[open]')) render(); }
  $('#connection-status').textContent='Семейная книга · всё сохранено';
}
async function connect() {
  try {
    authState=await api('/api/session');
    $('#retry-connection').hidden=true;
    if (!authState.authenticated) { showAuth(); return; }
    catalogArt=(await api('/api/catalog/art')).images;
    await refreshLibrary(true);
    $('#auth-screen').hidden=true; $('#app-shell').hidden=false;
    await findLegacyRecipes();
  } catch(error) { $('#auth-screen').hidden=false; $('#app-shell').hidden=true; $('#auth-description').textContent=error.message; $('#retry-connection').hidden=false; }
}
function showAuth() {
  $('#app-shell').hidden=true; $('#auth-screen').hidden=false;
  const setup=authState.needsSetup;
  $('#auth-title').textContent=setup?'Давайте откроем вашу кухню':'С возвращением на кухню';
  $('#auth-description').textContent=setup?'Придумайте общий пароль от 8 символов. Вы и ваши близкие будете входить с ним в одну книгу.':'Введите семейный пароль. Все ваши любимые рецепты уже здесь.';
  $('#auth-form').hidden=setup&&!authState.canSetup;
  $('#confirm-password-label').hidden=!setup;
  $('#confirm-password').required=setup;
  $('#family-password').minLength=setup?8:1;
  $('#family-password').autocomplete=setup?'new-password':'current-password';
  $('#auth-submit').textContent=setup?'Создать семейную книгу':'Войти в книгу';
  if (setup&&!authState.canSetup) $('#auth-description').textContent='Сначала откройте приложение «Крошка» на домашнем Mac и задайте семейный пароль. После этого вход будет доступен на телефоне.';
}
function legacyFingerprint(recipe){const text=JSON.stringify(recipe);let hash=2166136261;for(let i=0;i<text.length;i++){hash^=text.charCodeAt(i);hash=Math.imul(hash,16777619);}return `${recipe.id}:${hash>>>0}`;}
async function findLegacyRecipes() {
  try {
    const legacy=await new Promise(resolve=>{
      const request=indexedDB.open(storageKey);
      request.onupgradeneeded=()=>{request.transaction.abort();resolve(null);};
      request.onerror=()=>resolve(null);
      request.onsuccess=()=>{const db=request.result;if(!db.objectStoreNames.contains('library')){db.close();resolve(null);return;}const read=db.transaction('library').objectStore('library').get('recipes');read.onsuccess=()=>{resolve(read.result);db.close();};read.onerror=()=>{db.close();resolve(null);};};
    });
    let local=legacy;
    if (!local) { try { const text=localStorage.getItem(storageKey); local=text?JSON.parse(text):null; } catch {} }
    let migrated=[];try{migrated=JSON.parse(localStorage.getItem('kroshka-migrated-v2')||'[]');if(!Array.isArray(migrated))migrated=[];}catch{}
    legacyRecipes=Array.isArray(local)?local.filter(r=>r&&r.id&&!migrated.includes(legacyFingerprint(r))&&Array.isArray(r.ingredients)&&typeof r.instructions==='string'&&!seeds.some(seed=>JSON.stringify(seed)===JSON.stringify(r))&&!recipes.some(current=>JSON.stringify(current)===JSON.stringify(r))):[];
    $('#legacy-banner').hidden=!legacyRecipes.length;
  } catch { /* Existing browser data is never modified during migration. */ }
}
const state = {collection:'all',quick:'all',query:'',sort:'newest',view:'grid'};
let currentCatalogRecipe=null;
let catalogRequest=0;
let catalogSeen=[];
let catalogSearchTimer;
let editingId = null;
let editingShelf = 'main';
let draftImage = '';
let toastTimer;
let imageRevision = 0;
function toast(message) { $('#toast').textContent = message; $('#toast').classList.add('visible'); clearTimeout(toastTimer); toastTimer = setTimeout(() => $('#toast').classList.remove('visible'), 4000); }
let writeQueue=Promise.resolve();
function persist(update) {
  const operation=writeQueue.then(async()=>{
    const next=typeof update==='function'?update(recipes):update;
    $('#connection-status').textContent='Сохраняем…';
    try { const result=await api('/api/library',{method:'PUT',body:JSON.stringify({revision,recipes:next})}); recipes=next;revision=result.revision;lastSaveError='';$('#connection-status').textContent='Семейная книга · всё сохранено';return true; }
    catch(error) { lastSaveError=error.message; if(error.status===409) await refreshLibrary(true); else if(error.status===401) {authState=await api('/api/session');showAuth();} $('#connection-status').textContent='Изменения не сохранены';toast(lastSaveError);return false; }
  }).catch(error=>{lastSaveError=error.message;toast(lastSaveError);return false;});
  writeQueue=operation.then(()=>{});return operation;
}
function normalized(text) { return String(text).toLowerCase().replaceAll('ё','е').replace(/[^\p{L}\p{N}\s]/gu,' ').replace(/\s+/g,' ').trim(); }
function stem(word) { return word.length > 4 ? word.replace(/(?:ами|ями|ого|ому|ов|ев|ей|ой|ый|ий|ая|яя|ое|ее|ую|юю|ам|ям|ах|ях|ом|ем|а|я|ы|и|у|ю|е|о)$/u,'') : word; }
function matchesQuery(recipe, query) {
  const tokens = normalized(query).split(' ').filter(t => t && !['и','с','из'].includes(t));
  const haystack = normalized(recipe.title + ' ' + recipe.ingredients.map(i => i.name).join(' ')).split(' ').map(stem);
  return tokens.every(token => haystack.some(word => word.includes(stem(token))));
}
function format(value) { return value === null || value === undefined || value === '' ? '—' : Number(value).toLocaleString('ru-RU',{maximumFractionDigits:1}); }
const sampleCrops = {hero:[0,0,418,389],soup:[418,0,418,389],toast:[836,0,418,389],bowl:[0,389,418,390],oats:[418,389,418,390],salad:[836,389,418,390],salmon:[0,779,418,475],cutlets:[418,779,418,475],curd:[836,779,418,475]};
function safeImage(source) { return typeof source === 'string' && (source.startsWith('art:')&&Object.hasOwn(catalogArt,source.slice(4)) || Object.hasOwn(sampleCrops,source.replace('sample:','')) && source.startsWith('sample:') || /^data:image\/(?:png|jpeg|webp);base64,[A-Za-z0-9+/=\s]+$/.test(source)) ? source : ''; }
function photo(source, title, loading = 'lazy', recipeKind='dish') {
  const image = safeImage(source);
  if(image.startsWith('art:')){
    const art=catalogArt[image.slice(4)];
    return `<svg class="food-photo generated-food-photo" style="--art-ratio:${art.width}/${art.height}" viewBox="${art.x} ${art.y} ${art.width} ${art.height}" preserveAspectRatio="xMidYMid slice" role="img" aria-label="Сгенерированная иллюстрация: ${escapeHTML(title)}"><image href="assets/catalog-sheets/${escapeHTML(art.sheet)}.webp" width="${art.fullWidth}" height="${art.fullHeight}"/></svg>`;
  }
  if (image.startsWith('sample:')) return `<svg class="food-photo" viewBox="${sampleCrops[image.slice(7)].join(' ')}" preserveAspectRatio="xMidYMid slice" role="img" aria-label="Иллюстрация: ${escapeHTML(title)}"><image href="assets/food-grid.png" width="1254" height="1254"/></svg>`;
  return image ? `<img src="${escapeHTML(image)}" alt="${escapeHTML(title)}" loading="${loading}">` : `<div class="image-placeholder">${icon(recipeKind==='dish'?'bowl':'drink')}</div>`;
}
function macroClass(macro) { return ({'Белковое':'protein','Углеводное':'carbs','Жирное':'fat'})[macro] || ''; }
function favoriteButton(recipe) { return `<button class="favorite-button ${recipe.favorite ? 'is-favorite' : ''}" data-favorite="${escapeHTML(recipe.id)}" aria-label="${recipe.favorite ? 'Убрать из избранного' : 'В избранное'}: ${escapeHTML(recipe.title)}" aria-pressed="${!!recipe.favorite}">${icon('heart')}</button>`; }
const legacyMethods={"Сковородка": "Жарить", "Духовка": "Запекать", "Аэрогриль": "В аэрогриле", "На пару": "Готовить на пару", "Кастрюля (варка)": "Варить"};
function recipeMethods(recipe) {return [...new Set((Array.isArray(recipe.cookingMethods)?recipe.cookingMethods:[]).map(m=>legacyMethods[m]||m))];}
function recipeEquipment(recipe) {return Array.isArray(recipe.equipment)?recipe.equipment:[];}
function sourceNote(recipe) {
  if(!recipe.sourceTitle)return '';
  const url=typeof recipe.sourceUrl==='string'&&/^https?:\/\//.test(recipe.sourceUrl)?recipe.sourceUrl:'';
  return `<p class="source-note">Источник: ${url?`<a href="${escapeHTML(url)}" target="_blank" rel="noopener noreferrer">${escapeHTML(recipe.sourceTitle)}</a>`:escapeHTML(recipe.sourceTitle)}</p>`;
}
function catalogSavedRecipe(recipe=currentCatalogRecipe){return recipe&&recipes.find(r=>r.catalogId===recipe.id||r.id==='catalog-'+recipe.id);}
function catalogSaved(recipe=currentCatalogRecipe){return !!catalogSavedRecipe(recipe);}
function updateCatalogSave(){
  const saved=catalogSavedRecipe();
  const trial=saved?.shelf==='trial';
  $('#catalog-save').disabled=!currentCatalogRecipe||!!saved&&!trial;
  $('#catalog-save').innerHTML=icon(saved?'book':'plus')+(saved&&!trial?'Уже в вашей книге':trial?'В книгу рецептов':'Добавить к себе');
  $('#catalog-save-trial').disabled=!currentCatalogRecipe||!!saved;
  $('#catalog-save-trial').innerHTML=icon('spark')+(trial?'Уже на пробе':saved?'Уже в вашей книге':'На пробу');
}
function renderCatalogRecipe(recipe){
  const kind=({'dish':'Рецепт для вашей кухни','mocktail':'Безалкогольный коктейль','cocktail':'Алкогольный коктейль'})[recipe.recipeKind];
  $('#catalog-content').innerHTML=`<article class="catalog-recipe">${recipe.image?`<div class="catalog-recipe-art ${recipe.recipeKind!=='dish'?'catalog-drink-art':''}">${photo(recipe.image,recipe.title,'eager',recipe.recipeKind)}<span>Иллюстрация блюда</span></div>`:''}<div class="catalog-recipe-heading"><span class="catalog-emblem">${icon(recipe.recipeKind==='dish'?'bowl':'drink')}</span><div><div class="catalog-recipe-kind">${escapeHTML(kind)}</div><h3>${escapeHTML(recipe.title)}</h3></div></div><div class="catalog-recipe-stats"><span>${icon('clock')}${format(recipe.time)} мин</span><span>${icon('bowl')}Порций: ${format(recipe.servings)}</span>${recipe.cookingMethods.length?`<span>${escapeHTML(recipeMethods(recipe).join(' · '))}</span>`:''}</div><div class="catalog-columns"><section><h4>Что понадобится</h4><ul class="detail-ingredients">${recipe.ingredients.map(i=>`<li><span>${escapeHTML(i.name)}</span><span>${escapeHTML(i.amount)} ${escapeHTML(i.unit)}</span></li>`).join('')}</ul></section><section><h4>Как приготовить</h4><ol class="detail-steps">${recipe.steps.map(step=>`<li>${escapeHTML(step)}</li>`).join('')}</ol></section></div>${sourceNote(recipe)}<p class="catalog-recipe-note">После добавления можно изменить рецепт и категории под себя. Пищевая ценность не указана.</p></article>`;
}
async function loadCatalogRecipe(reset=false){
  const request=++catalogRequest;
  if(reset)catalogSeen=[];
  const params=new URLSearchParams({q:$('#catalog-search').value.trim(),kind:$('#catalog-kind').value,exclude:catalogSeen.slice(-80).join(',')});
  currentCatalogRecipe=null;updateCatalogSave();$('#catalog-next').disabled=true;
  $('#catalog-content').setAttribute('aria-busy','true');
  $('#catalog-content').innerHTML='<div class="catalog-loading">Подбираем что-нибудь интересное…</div>';
  $('#catalog-summary').textContent='Открываем каталог…';
  try{
    const result=await api('/api/catalog/random?'+params);
    if(request!==catalogRequest)return;
    $('#catalog-summary').textContent=`В каталоге: ${result.total.toLocaleString('ru-RU')} · По вашим условиям: ${result.matched.toLocaleString('ru-RU')}`;
    currentCatalogRecipe=result.recipe;
    if(result.recipe){catalogSeen.push(result.recipe.id);renderCatalogRecipe(result.recipe);$('#catalog-next').disabled=false;}
    else $('#catalog-content').innerHTML=`<div class="catalog-empty">${icon('book')}<h3>Пока нет такой идеи</h3><p>Попробуйте другой ингредиент или раздел каталога.</p></div>`;
    $('#catalog-content').scrollTop=0;updateCatalogSave();
  }catch(error){
    if(request!==catalogRequest)return;
    $('#catalog-summary').textContent='Не удалось открыть каталог';
    $('#catalog-content').innerHTML=`<div class="catalog-empty"><h3>Попробуем ещё раз?</h3><p>${escapeHTML(error.message)}</p></div>`;
    $('#catalog-next').disabled=false;
  }finally{if(request===catalogRequest)$('#catalog-content').setAttribute('aria-busy','false');}
}
function openCatalog(){
  if(!$('#catalog-dialog').open)$('#catalog-dialog').showModal();
  clearTimeout(catalogSearchTimer);loadCatalogRecipe(true);
}
$('#catalog-next').addEventListener('click',()=>{clearTimeout(catalogSearchTimer);loadCatalogRecipe();});
$('#catalog-kind').addEventListener('change',()=>{clearTimeout(catalogSearchTimer);loadCatalogRecipe(true);});
$('#catalog-search').addEventListener('input',()=>{
  clearTimeout(catalogSearchTimer);catalogRequest++;currentCatalogRecipe=null;updateCatalogSave();$('#catalog-next').disabled=true;
  catalogSearchTimer=setTimeout(()=>loadCatalogRecipe(true),250);
});
$('#catalog-dialog').addEventListener('close',()=>{clearTimeout(catalogSearchTimer);catalogRequest++;});
async function saveCatalogTo(destination){
  const recipe=currentCatalogRecipe,saved=catalogSavedRecipe(recipe);
  if(!recipe||(saved&&(destination==='trial'||saved.shelf!=='trial')))return;
  $('#catalog-save').disabled=true;$('#catalog-save-trial').disabled=true;
  const operation=writeQueue.then(async()=>{
    const result=await api('/api/catalog/'+encodeURIComponent(recipe.id)+'/save',{method:'POST',body:JSON.stringify({destination})});
    await refreshLibrary(true);render();
    toast(result.alreadySaved?'Этот рецепт уже сохранён':destination==='trial'?'Сохранено в «Блюда на пробу»':result.moved?'Рецепт перенесён в основную книгу':'Рецепт добавлен в вашу семейную книгу');
  });
  writeQueue=operation.catch(()=>{});
  try{await operation;}catch(error){toast(error.message);}finally{updateCatalogSave();}
}
$('#catalog-save').addEventListener('click',()=>saveCatalogTo('main'));
$('#catalog-save-trial').addEventListener('click',()=>saveCatalogTo('trial'));
async function trialAction(id,promote){
  const operation=writeQueue.then(async()=>{
    await api('/api/trials/'+encodeURIComponent(id)+(promote?'/promote':''),{method:promote?'POST':'DELETE',body:'{}'});
    await refreshLibrary(true);$('#recipe-dialog').close();render();updateCatalogSave();
    toast(promote?'Рецепт теперь во «Все рецепты»':'Блюдо удалено из списка на пробу');
  });
  writeQueue=operation.catch(()=>{});
  try{await operation;}catch(error){await refreshLibrary(true).catch(()=>{});if(!recipes.some(r=>r.id===id&&r.shelf==='trial'))$('#recipe-dialog').close();render();toast(error.message);}
}
function filteredRecipes() {
  return recipes.filter(r => (state.collection==='trial'?r.shelf==='trial':r.shelf!=='trial') && (state.collection !== 'favorites' || r.favorite) && matchesQuery(r,state.query) &&
    (!$('#filter-equipment').value || recipeEquipment(r).includes($('#filter-equipment').value)) && (!$('#filter-preparation').value || !!r.isPreparation===($('#filter-preparation').value==='yes')) &&
    (!$('#filter-meal').value || r.meal === $('#filter-meal').value) && (!$('#filter-size').value || r.size === $('#filter-size').value) &&
    (!$('#filter-macro').value || r.macro === $('#filter-macro').value) && (!$('#filter-meat').value || r.meat === $('#filter-meat').value) &&
    (!$('#filter-cooking-method').value || ($('#filter-cooking-method').value==='unassigned' ? recipeMethods(r).length===0 : recipeMethods(r).includes($('#filter-cooking-method').value))) &&
    (state.quick !== 'preparation' || !!r.isPreparation) && (state.quick !== 'fast' || r.time <= 30) && (state.quick !== 'vegetarian' || r.meat === 'Без мяса') && (state.quick !== 'protein' || r.macro === 'Белковое'))
    .sort((a,b) => {
      if (state.sort === 'newest') return b.createdAt - a.createdAt;
      if (state.sort === 'time') return a.time - b.time;
      const av = a[state.sort], bv = b[state.sort];
      if (av === null || av === undefined || av === '') return (bv === null || bv === undefined || bv === '') ? 0 : 1;
      if (bv === null || bv === undefined || bv === '') return -1;
      return bv - av;
    });
}
function render() {
  const visible = filteredRecipes();
  $('.recipe-section').dataset.collectionView=state.collection;
  $('.collection-hint').textContent=state.collection==='trial'?'Идеи, которые хочется приготовить':document.documentElement.dataset.theme==='halloween'?'Проверенные семейные заклинания':'Маленькая коллекция больших удовольствий';
  const mainRecipes=recipes.filter(r=>r.shelf!=='trial'),trialRecipes=recipes.filter(r=>r.shelf==='trial');
  $('#all-count').textContent = mainRecipes.length;
  $('#favorite-count').textContent = mainRecipes.filter(r => r.favorite).length;
  $('#trial-count').textContent=trialRecipes.length;
  const meal = $('#filter-meal').value;
  $('#collection-title').innerHTML = `${state.collection==='trial'?'Блюда на пробу':state.collection === 'favorites' ? 'Избранное' : ({'Завтрак':'Завтраки','Обед':'Обеды','Ужин':'Ужины','Перекус':'Перекусы','Напиток':'Напитки'}[meal] || 'Все рецепты')} <span id="result-count">${visible.length}</span>`;
  $('#recipe-grid').innerHTML = visible.map(r => `<article class="recipe-card" data-id="${escapeHTML(r.id)}"><button class="card-open" data-open="${escapeHTML(r.id)}" aria-label="Открыть рецепт: ${escapeHTML(r.title)}"><div class="card-image">${photo(r.image,r.title,'lazy',r.recipeKind)}<span class="meal-badge">${escapeHTML(r.meal)}</span></div><div class="card-content"><h3 class="card-title">${escapeHTML(r.title)}</h3><p class="card-ingredients">${escapeHTML(r.ingredients.slice(0,3).map(i => i.name).join(' · '))}</p><div class="card-tags">${r.isPreparation?'<span class="recipe-tag preparation-tag">Заготовка</span>':''}${r.recipeKind&&r.recipeKind!=='dish'?`<span class="recipe-tag">${r.recipeKind==='cocktail'?'Алкогольный':'Без алкоголя'}</span>`:`<span class="recipe-tag">${escapeHTML(r.meat)}</span>${r.macro!=='Не указан'?`<span class="recipe-tag ${macroClass(r.macro)}">${escapeHTML(r.macro)}</span>`:''}`}</div>${recipeMethods(r).length?`<p class="card-methods">${escapeHTML(recipeMethods(r).join(' · '))}</p>`:''}<div class="card-meta"><span class="card-time">${icon('clock')}${format(r.time)} мин</span><span class="card-macros"><span>Б <b>${format(r.protein)}</b></span><span>Ж <b>${format(r.fat)}</b></span><span>У <b>${format(r.carbs)}</b></span></span></div><div class="macro-label">на 100 г</div></div></button>${r.shelf==='trial'?`<div class="trial-card-actions"><button type="button" class="button" data-promote-trial="${escapeHTML(r.id)}">В книгу рецептов</button><button type="button" class="trial-delete" title="Убрать из блюд на пробу" data-delete-trial="${escapeHTML(r.id)}" aria-label="Удалить из блюд на пробу: ${escapeHTML(r.title)}">${icon('close')}</button></div>`:favoriteButton(r)}</article>`).join('');
  $('#empty-state').hidden = visible.length > 0;
  const hasConditions=!!(state.query||state.quick!=='all'||$$('.filters select').some(el=>el.value));
  const sectionName=({'Завтрак':'завтраков','Обед':'обедов','Ужин':'ужинов','Перекус':'перекусов','Напиток':'напитков'})[meal];
  $('#empty-title').textContent=state.collection==='trial'&&!trialRecipes.length?'Что хочется приготовить?':!mainRecipes.length&&state.collection!=='trial'?'Начнём вашу семейную книгу':state.collection==='favorites'&&!mainRecipes.some(r=>r.favorite)?'Здесь будут ваши любимые рецепты':meal&&!state.query&&state.quick==='all'&&$$('.filters select').filter(el=>el.value).length===1?`Пока нет ${sectionName}`:'Подходящих рецептов пока нет';
  $('#empty-message').textContent=state.collection==='trial'&&!trialRecipes.length?'Сохраняйте сюда идеи из каталога. Когда попробуете блюдо, перенесите его в основную книгу или удалите.':!mainRecipes.length&&state.collection!=='trial'?'Добавьте свой рецепт или найдите идею в книге вдохновения.':state.collection==='favorites'&&!hasConditions?'Нажмите сердечко на понравившемся рецепте — и он появится здесь.':meal&&!state.query?'Добавьте рецепт в этот раздел или посмотрите всю семейную книгу.':'Попробуйте другие ингредиенты или сбросьте выбранные условия.';
  $('#empty-action').textContent=state.collection==='trial'&&trialRecipes.length?'Сбросить поиск и фильтры':'Показать все рецепты';
  $('#empty-action').hidden=state.collection==='trial'?!trialRecipes.length&&!mainRecipes.length:!mainRecipes.length;
  $('#empty-add').textContent=state.collection==='trial'?'Найти идею в каталоге':'Добавить рецепт';

  const filterCount = $$('.filters select').filter(el => el.value).length;
  $('#filter-count').textContent = filterCount;
  $('#filter-count').hidden = !filterCount;
  $$('[data-collection]').forEach(el => el.classList.toggle('active',el.dataset.collection === state.collection && (!meal||state.collection==='trial')));
  $$('[data-meal]').forEach(el => el.classList.toggle('active',state.collection!=='trial'&&el.dataset.meal === meal));
  $$('[data-quick]').forEach(el => el.classList.toggle('active',el.dataset.quick === state.quick));
}
function resetFilters() { $$('.filters select').forEach(el => el.value = ''); state.quick = 'all'; render(); }
async function toggleFavorite(id) {
  if (await persist(current => current.map(r => r.id === id ? {...r,favorite:!r.favorite} : r))) {
    render();
    if ($('#recipe-dialog').open) { const r = recipes.find(r => r.id === id); const button = $('[data-favorite]', $('#recipe-dialog')); if (button && r) button.outerHTML = favoriteButton(r); }
  }
}
function showRecipe(id) {
  const r = recipes.find(r => r.id === id); if (!r) return;
  $('#recipe-detail').innerHTML = `<div class="detail-photo ${r.recipeKind&&r.recipeKind!=='dish'?'drink-detail-photo':''}">${photo(r.image,r.title,'eager',r.recipeKind)}<button class="icon-button close-dialog" aria-label="Закрыть">${icon('close')}</button></div><div class="detail-body"><div class="detail-heading"><h2>${escapeHTML(r.title)}</h2>${favoriteButton(r)}</div>${r.shelf==='trial'?'<p class="trial-detail-note">Блюдо на пробу · ещё не в основной книге</p>':''}<div class="detail-categories">${[r.meal,r.size,r.macro,r.meat,...(r.isPreparation?['Заготовка']:[]),...(r.recipeKind==='cocktail'?['Алкогольный коктейль']:r.recipeKind==='mocktail'?['Безалкогольный коктейль']:[])].map(tag => `<span class="recipe-tag ${tag === r.macro ? macroClass(r.macro) : ''}">${escapeHTML(tag)}</span>`).join('')}</div><p class="detail-methods"><span>Способ приготовления</span><strong>${escapeHTML(recipeMethods(r).join(' · ')||'Не указан')}</strong></p>${recipeEquipment(r).length?`<p class="detail-methods"><span>Инвентарь</span><strong>${escapeHTML(recipeEquipment(r).join(' · '))}</strong></p>`:''}<div class="detail-stats"><span>${icon('clock')}${format(r.time)} мин</span><span>${icon('bowl')}Порций: ${format(r.servings)}</span></div><h3>Ингредиенты</h3><ul class="detail-ingredients">${r.ingredients.map(i => `<li><span>${escapeHTML(i.name)}</span><span>${escapeHTML(i.amount)} ${escapeHTML(i.unit)}</span></li>`).join('')}</ul><h3>Готовим с удовольствием</h3><ol class="detail-steps">${(Array.isArray(r.steps)?r.steps:r.instructions.split('\n')).filter(s => s.trim()).map(s => `<li>${escapeHTML(s)}</li>`).join('')}</ol><h3>На 100 г готового блюда</h3><div class="detail-nutrition">${[['calories','ккал'],['protein','белки, г'],['fat','жиры, г'],['carbs','углеводы, г']].map(([key,label]) => `<div><strong>${format(r[key])}</strong><span>${label}</span></div>`).join('')}</div><p class="field-hint" style="margin-top:12px">Значения указаны автором рецепта, автоматически не рассчитываются.</p>${sourceNote(r)}</div><div class="dialog-footer"><button class="detail-delete" ${r.shelf==='trial'?'data-delete-trial':'data-delete'}="${escapeHTML(r.id)}">${r.shelf==='trial'?'Убрать из списка':'Удалить рецепт'}</button><button class="button ${r.shelf==='trial'?'':'primary'}" data-edit="${escapeHTML(r.id)}">${icon('edit')}Редактировать</button>${r.shelf==='trial'?`<button class="button primary" data-promote-trial="${escapeHTML(r.id)}">В книгу рецептов</button>`:''}</div>`;
  if (!$('#recipe-dialog').open) $('#recipe-dialog').showModal();
  $('#recipe-dialog').scrollTop = 0;
}
function addIngredientRow(data = {name:'',amount:'',unit:'г'}) {
  const row = document.createElement('div'); row.className = 'ingredient-row';
  row.innerHTML = `<input class="ingredient-name" aria-label="Ингредиент" placeholder="Например, чечевица" required maxlength="100" value="${escapeHTML(data.name)}"><input class="ingredient-amount" aria-label="Количество" type="number" min="0.1" max="100000" step="0.001" inputmode="decimal" placeholder="100" value="${escapeHTML(data.amount)}"><select class="ingredient-unit" aria-label="Единица измерения">${['г','мл','шт','ч. л.','ст. л.','стакан','зубчик','пучок','щепотка','головка','банка','пакетик','упаковка','пачка','горсть','веточка','ломтик','стебель','капля','по вкусу'].map(unit => `<option ${unit === data.unit ? 'selected' : ''}>${unit}</option>`).join('')}</select><button type="button" class="delete-ingredient" aria-label="Удалить ингредиент">${icon('close')}</button>`;
  $('#ingredient-rows').append(row);
  updateIngredientRequirement(row);
  updateIngredientCount();
}
function updateIngredientRequirement(row) {
  const byTaste = $('.ingredient-unit',row).value === 'по вкусу';
  $('.ingredient-amount',row).required = !byTaste;
  $('.ingredient-amount',row).disabled = byTaste;
  if (byTaste) $('.ingredient-amount',row).value = '';
}
function updateImagePreview() {
  $('#image-preview').innerHTML = draftImage ? photo(draftImage,'Фото рецепта','eager') : icon('bowl');
  $('#remove-image').hidden = !draftImage;
  $('#photo-action-label').textContent=draftImage?'Заменить фотографию':'Добавить фотографию';
}
function readIngredients() { return $$('.ingredient-row').map(row => ({name:$('.ingredient-name',row).value.trim(),amount:$('.ingredient-amount',row).value,unit:$('.ingredient-unit',row).value})); }
function updateIngredientCount() { const count=$$('.ingredient-row').length;$('#ingredient-count').textContent=`${count} ${count%10===1&&count%100!==11?'ингредиент':count%10>=2&&count%10<=4&&!(count%100>=12&&count%100<=14)?'ингредиента':'ингредиентов'}`; }
function addStep(value='') {
  const row=document.createElement('div');row.className='step-row';
  row.innerHTML=`<span class="step-number"></span><textarea class="step-text" aria-label="Описание шага" required maxlength="15000" rows="3" placeholder="Что нужно сделать? Например, промойте чечевицу и нарежьте овощи.">${escapeHTML(value)}</textarea><div class="step-actions"><button type="button" data-step-action="up" aria-label="Переместить шаг выше">↑</button><button type="button" data-step-action="down" aria-label="Переместить шаг ниже">↓</button><button type="button" data-step-action="delete" aria-label="Удалить шаг">${icon('close')}</button></div>`;
  $('#step-rows').append(row);renumberSteps();
}
function renumberSteps() { $$('.step-row').forEach((row,index,rows)=>{ $('.step-number',row).textContent=String(index+1).padStart(2,'0');$('.step-text',row).setAttribute('aria-label',`Шаг ${index+1}`);$('[data-step-action=up]',row).disabled=index===0;$('[data-step-action=down]',row).disabled=index===rows.length-1;$('[data-step-action=delete]',row).disabled=rows.length===1;}); }
function closeEditor() { if(formDirty&&!confirm('Закрыть рецепт без сохранения изменений?'))return; $('#editor-dialog').close(); }
function openEditor(id=null) {
  const recipe=recipes.find(r=>r.id===id);editingShelf=recipe?.shelf??(state.collection==='trial'?'trial':'main');editingId=recipe?id:null;editingSnapshot=recipe?JSON.stringify(recipe):null;imageRevision++;
  $('#recipe-form').reset();$('#form-error').textContent='';$('#save-copy').hidden=true;
  $('#editor-title').textContent=recipe?'Редактировать рецепт':'Новый рецепт';
  $('#ingredient-rows').replaceChildren();$('#step-rows').replaceChildren();
  if(recipe){for(const key of ['title','time','servings','meal','size','macro','meat','calories','protein','fat','carbs'])$('#recipe-form').elements[key].value=recipe[key]??'';recipe.ingredients.forEach(addIngredientRow);(Array.isArray(recipe.steps)?recipe.steps:recipe.instructions.split('\n')).filter(step=>step.trim()).forEach(addStep);}
  else {addIngredientRow();addStep();}
  $$('input[name=cookingMethods]').forEach(input=>input.checked=!!recipe&&recipeMethods(recipe).includes(input.value));
  $$('input[name=equipment]').forEach(input=>input.checked=!!recipe&&recipeEquipment(recipe).includes(input.value));
  $('#recipe-form').elements.isPreparation.checked=!!recipe?.isPreparation;
  $('#nutrition-details').open=!!recipe&&['calories','protein','fat','carbs'].some(key=>recipe[key]!==null&&recipe[key]!==undefined);
  draftImage=recipe?.image||'';updateImagePreview();formDirty=false;
  $('#recipe-dialog').close();$('#editor-dialog').showModal();$('#editor-dialog').scrollTop=0;
}
$('#add-recipe').addEventListener('click',() => openEditor());
$('#empty-add').addEventListener('click',()=>{if(state.collection==='trial'){openCatalog();return;}const meal=$('#filter-meal').value;openEditor();if(meal)$('#recipe-form').elements.meal.value=meal;});
$('.brand').addEventListener('click',event => { event.preventDefault(); state.collection = 'all'; state.query = ''; $('#search').value = ''; resetFilters(); window.scrollTo({top:0,behavior:'smooth'}); });
$('.mobile-brand').addEventListener('click',event => { event.preventDefault(); window.scrollTo({top:0,behavior:'smooth'}); });
$('#search').addEventListener('input',event => { state.query = event.target.value; render(); });
$('#sort').addEventListener('change',event => { state.sort = event.target.value; render(); });
$('#filter-toggle').addEventListener('click',() => { $('#filters').hidden = !$('#filters').hidden; $('#filter-toggle').setAttribute('aria-expanded',!$('#filters').hidden); });
$$('.filters select').forEach(el => el.addEventListener('change',render));
$('#reset-filters').addEventListener('click',resetFilters);
$$('[data-collection]').forEach(el => el.addEventListener('click',() => { state.collection = el.dataset.collection; $('#filter-meal').value = ''; render(); }));
$$('[data-meal]').forEach(el => el.addEventListener('click',() => { state.collection = 'all'; $('#filter-meal').value = $('#filter-meal').value === el.dataset.meal ? '' : el.dataset.meal; render(); $('.recipe-section').scrollIntoView({behavior:'smooth',block:'start'}); }));
$$('[data-quick]').forEach(el => el.addEventListener('click',() => { state.quick = el.dataset.quick; render(); }));
for (const view of ['grid','list']) $(`#${view}-view`).addEventListener('click',() => { state.view = view; $('#recipe-grid').classList.toggle('list-view',view === 'list'); for (const option of ['grid','list']) { $(`#${option}-view`).classList.toggle('active',option === view); $(`#${option}-view`).setAttribute('aria-pressed',option === view); } });
$('#empty-action').addEventListener('click',() => { if (!recipes.length) openEditor(); else { state.collection = state.collection==='trial'&&recipes.some(r=>r.shelf==='trial')?'trial':'all'; state.query = ''; $('#search').value = ''; resetFilters(); } });
$('#inspire').addEventListener('click',openCatalog);
$('#add-ingredient').addEventListener('click',() => { addIngredientRow();formDirty=true; $$('.ingredient-name').at(-1).focus(); });
$('#ingredient-rows').addEventListener('change',event => { if (event.target.matches('.ingredient-unit')) updateIngredientRequirement(event.target.closest('.ingredient-row')); });
$('#ingredient-rows').addEventListener('click',event => { const button = event.target.closest('.delete-ingredient'); if (!button) return; if ($$('.ingredient-row').length > 1) {button.closest('.ingredient-row').remove();formDirty=true;updateIngredientCount();} else toast('Оставьте хотя бы один ингредиент'); });
document.addEventListener('click',async event => {
  const close = event.target.closest('.close-dialog'); if (close) { const dialog=close.closest('dialog');if(dialog.id==='editor-dialog')closeEditor();else dialog.close();return; }
  const promoteTrial=event.target.closest('[data-promote-trial]');if(promoteTrial){trialAction(promoteTrial.dataset.promoteTrial,true);return;}
  const removeTrial=event.target.closest('[data-delete-trial]');if(removeTrial){if(confirm('Удалить блюдо из списка на пробу?'))trialAction(removeTrial.dataset.deleteTrial,false);return;}
  const favorite = event.target.closest('[data-favorite]'); if (favorite) { toggleFavorite(favorite.dataset.favorite); return; }
  const open = event.target.closest('[data-open]'); if (open) { showRecipe(open.dataset.open); return; }
  const edit = event.target.closest('[data-edit]'); if (edit) { openEditor(edit.dataset.edit); return; }
  const remove = event.target.closest('[data-delete]'); if (remove && confirm('Удалить рецепт из вашей книги? Это действие нельзя отменить.')) { if (await persist(current => current.filter(r => r.id !== remove.dataset.delete))) { $('#recipe-dialog').close(); render(); toast('Рецепт удалён'); } }
});
$$('dialog').forEach(dialog => dialog.addEventListener('click',event => { const rect = dialog.getBoundingClientRect(); if (event.target === dialog && (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom)) {if(dialog.id==='editor-dialog')closeEditor();else dialog.close();} }));
$('#editor-dialog').addEventListener('close',() => {imageRevision++;});
$('#editor-dialog').addEventListener('cancel',event=>{event.preventDefault();closeEditor();});
document.addEventListener('keydown',event => { if (event.key === '/' && !event.ctrlKey && !event.metaKey && !event.altKey && !['INPUT','TEXTAREA','SELECT'].includes(document.activeElement.tagName) && !document.querySelector('dialog[open]')) { event.preventDefault(); $('#search').focus(); } });
$('#recipe-form').addEventListener('submit',async event => {
  event.preventDefault();
  const form = event.currentTarget;
  const title = form.elements.title.value.trim();
  const steps=$$('.step-text').map(input=>input.value.trim()).filter(Boolean);
  const instructions=steps.join('\n');
  const ingredients = readIngredients();
  if (!title || !instructions || ingredients.some(i => !i.name)) { $('#form-error').textContent = 'Заполните название, ингредиенты и описание приготовления.'; return; }
  const existing = recipes.find(r => r.id === editingId);
  if(editingId&&(!existing||JSON.stringify(existing)!==editingSnapshot)){ $('#form-error').textContent='Этот рецепт изменили на другом устройстве. Сохраните свою версию как копию, чтобы сохранить оба варианта.';$('#save-copy').hidden=false;return;}
  const recipe = {id:editingId || (crypto.randomUUID?crypto.randomUUID():`${Date.now()}-${Math.random().toString(36).slice(2)}`),title,instructions,steps,ingredients,image:draftImage,favorite:existing?.favorite || false,createdAt:existing?.createdAt || Date.now()};
  recipe.shelf=editingShelf;
  recipe.cookingMethods=$$('input[name=cookingMethods]:checked',form).map(input=>input.value);
  recipe.equipment=$$('input[name=equipment]:checked',form).map(input=>input.value);
  recipe.isPreparation=form.elements.isPreparation.checked;
  for(const key of ['catalogId','recipeKind','sourceTitle','sourceUrl'])if(existing&&existing[key]!==undefined)recipe[key]=existing[key];
  for (const key of ['time','servings']) recipe[key] = Number(form.elements[key].value);
  for (const key of ['meal','size','macro','meat']) recipe[key] = form.elements[key].value;
  for (const key of ['calories','protein','fat','carbs']) recipe[key] = form.elements[key].value === '' ? null : Number(form.elements[key].value);
  const update = current => existing ? current.map(r => r.id === recipe.id ? recipe : r) : [recipe,...current];
  const saveButton = $('[type=submit]',form); saveButton.disabled = true;
  if (await persist(update)) { formDirty=false;$('#editor-dialog').close(); state.collection = recipe.shelf==='trial'?'trial':'all'; state.query = ''; $('#search').value = ''; resetFilters(); state.sort = 'newest'; $('#sort').value = 'newest'; render(); toast(existing ? 'Изменения сохранены' : 'Рецепт добавлен в вашу книгу'); }
  else $('#form-error').textContent = lastSaveError||'Рецепт не сохранён. Проверьте соединение с Mac и попробуйте ещё раз.';
  saveButton.disabled = false;
});
$('#image-upload').addEventListener('change',async event => {
  const file = event.target.files[0]; if (!file) return;
  if (!['image/jpeg','image/png','image/webp'].includes(file.type) || file.size > 15 * 1024 * 1024) { toast('Выберите JPG, PNG или WebP размером до 15 МБ'); event.target.value = ''; return; }
  const revision = ++imageRevision;
  try {
    const bitmap = await createImageBitmap(file);
    const scale = Math.min(1,1000 / Math.max(bitmap.width,bitmap.height));
    const canvas = document.createElement('canvas'); canvas.width = Math.round(bitmap.width * scale); canvas.height = Math.round(bitmap.height * scale);
    canvas.getContext('2d').drawImage(bitmap,0,0,canvas.width,canvas.height); bitmap.close();
    if (revision !== imageRevision || !$('#editor-dialog').open) return;
    draftImage = canvas.toDataURL('image/jpeg',.8);formDirty=true;updateImagePreview();
  } catch { toast('Не удалось открыть изображение'); }
});
$('#remove-image').addEventListener('click',() => { imageRevision++;formDirty=true;draftImage = ''; $('#image-upload').value = ''; updateImagePreview(); });
$('#export-data').addEventListener('click',() => {
  const blob = new Blob([JSON.stringify({version:1,exportedAt:new Date().toISOString(),recipes},null,2)],{type:'application/json'});
  const url = URL.createObjectURL(blob); const link = document.createElement('a'); link.href = url; link.download = 'kroshka-recipes.json'; link.click(); setTimeout(() => URL.revokeObjectURL(url),1000); toast('Книга рецептов скачана');
});
$('#auth-form').addEventListener('submit',async event=>{
  event.preventDefault();$('#auth-error').textContent='';
  const password=$('#family-password').value;
  if(authState.needsSetup&&password!==$('#confirm-password').value){$('#auth-error').textContent='Пароли не совпадают.';return;}
  $('#auth-submit').disabled=true;
  try {await api(authState.needsSetup?'/api/setup':'/api/login',{method:'POST',body:JSON.stringify({password})});$('#auth-form').reset();await connect();}
  catch(error){$('#auth-error').textContent=error.message;}
  finally{$('#auth-submit').disabled=false;}
});
$('#retry-connection').addEventListener('click',connect);
$('#logout').addEventListener('click',async()=>{try{await api('/api/logout',{method:'POST',body:'{}'});authState=await api('/api/session');showAuth();}catch(error){toast(error.message);}});
$('#recipe-form').addEventListener('input',()=>formDirty=true);
$('#recipe-form').addEventListener('change',()=>formDirty=true);
$('#save-copy').addEventListener('click',()=>{editingId=null;editingSnapshot=null;$('#recipe-form').requestSubmit();});
$('#add-step').addEventListener('click',()=>{addStep();formDirty=true;$$('.step-text').at(-1).focus();});
$('#step-rows').addEventListener('click',event=>{const button=event.target.closest('[data-step-action]');if(!button)return;const row=button.closest('.step-row');if(button.dataset.stepAction==='delete'&&$$('.step-row').length>1)row.remove();if(button.dataset.stepAction==='up'&&row.previousElementSibling)row.previousElementSibling.before(row);if(button.dataset.stepAction==='down'&&row.nextElementSibling)row.nextElementSibling.after(row);renumberSteps();formDirty=true;});
$('#ingredient-rows').addEventListener('keydown',event=>{if(event.key==='Enter'&&event.target.matches('input,select')){event.preventDefault();addIngredientRow();formDirty=true;$$('.ingredient-name').at(-1).focus();}});
$$('[data-editor-section]').forEach(button=>button.addEventListener('click',()=>{document.getElementById(button.dataset.editorSection).scrollIntoView({behavior:'smooth',block:'start'});}));
window.addEventListener('beforeunload',event=>{if(formDirty&&$('#editor-dialog').open){event.preventDefault();event.returnValue='';}});
async function importRecipes(incoming,migration=false) {
  if(!Array.isArray(incoming)||incoming.length>10000||incoming.some(r=>!r||typeof r.id!=='string'||typeof r.title!=='string'||!Array.isArray(r.ingredients)||typeof r.instructions!=='string')){toast('В файле нет подходящих рецептов. Выберите копию, скачанную из «Крошки».');return;}
  if(!confirm(`Добавить рецепты в семейную книгу (${incoming.length})? При совпадении изменённого рецепта будет создана копия.`))return;
  let added=0;
  const success=await persist(current=>{const result=[...current];for(const recipe of incoming){const match=result.find(r=>r.id===recipe.id);if(match&&JSON.stringify(match)===JSON.stringify(recipe))continue;const copy={...recipe};if(match){copy.id=`${Date.now()}-${Math.random().toString(36).slice(2)}`;copy.title=(copy.title+' (копия)').slice(0,100);copy.createdAt=Date.now();}result.push(copy);added++;}return result;});
  if(success){if(migration){try{const previous=JSON.parse(localStorage.getItem('kroshka-migrated-v2')||'[]');localStorage.setItem('kroshka-migrated-v2',JSON.stringify([...new Set([...(Array.isArray(previous)?previous:[]),...incoming.map(legacyFingerprint)])]));}catch{}}render();await findLegacyRecipes();toast(`Добавлено рецептов: ${added}`);}return success;
}
$('#import-data').addEventListener('click',()=>$('#import-file').click());
$('#import-file').addEventListener('change',async event=>{const file=event.target.files[0];if(!file)return;try{if(file.size>64*1024*1024)throw new Error('size');const parsed=JSON.parse(await file.text());await importRecipes(Array.isArray(parsed)?parsed:parsed.recipes);}catch{toast('Не удалось прочитать файл. Нужна JSON-копия книги рецептов до 64 МБ.');}finally{event.target.value='';}});
$('#migrate-recipes').addEventListener('click',()=>importRecipes(legacyRecipes,true));
$('#open-connection').addEventListener('click',async()=>{
  $('#connection-links').textContent='Ищем адрес домашнего Mac…';$('#connection-dialog').showModal();
  try{const result=await api('/api/connection');const urls=result.urls.length?result.urls:[location.origin];$('#connection-links').innerHTML=urls.map(url=>`<div class="connection-address"><code>${escapeHTML(url)}</code><button class="button" data-copy-url="${escapeHTML(url)}">Скопировать</button></div>`).join('');}catch(error){$('#connection-links').textContent=error.message;}
});
$('#connection-links').addEventListener('click',async event=>{const button=event.target.closest('[data-copy-url]');if(!button)return;try{if(navigator.clipboard&&window.isSecureContext)await navigator.clipboard.writeText(button.dataset.copyUrl);else{const field=document.createElement('textarea');field.value=button.dataset.copyUrl;$('#connection-dialog').append(field);field.select();if(!document.execCommand('copy'))throw new Error('copy');field.remove();}button.textContent='Скопировано';}catch{toast('Выделите адрес и скопируйте его вручную.');}});
setInterval(async()=>{if(syncing||document.hidden||$('#app-shell').hidden)return;syncing=true;try{await writeQueue;await refreshLibrary();}catch{$('#connection-status').textContent='Нет связи с Mac';}finally{syncing=false;}},5000);
window.addEventListener('online',()=>refreshLibrary().catch(()=>{}));
const motionPreference=window.matchMedia('(prefers-reduced-motion: reduce)');
function updateCatMotion(){
  $$('.cat-motion-animation').forEach(animation=>{
    try{if(motionPreference.matches){animation.endElement();animation.parentElement.setAttribute('scale','0');}else{animation.beginElement();}}catch{/* Static artwork remains usable if SVG animation is unsupported. */}
  });
}
motionPreference.addEventListener('change',updateCatMotion);updateCatMotion();
if('serviceWorker' in navigator&&window.isSecureContext)navigator.serviceWorker.register('/sw.js').catch(()=>{});
await connect();
})().catch(() => { document.querySelector('#auth-description').textContent='Не удалось открыть книгу. Запустите приложение «Крошка» на Mac и попробуйте ещё раз.';document.querySelector('#retry-connection').hidden=false; });
