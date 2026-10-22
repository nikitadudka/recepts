import http from 'node:http';
import { readFile } from 'node:fs/promises';
import { mkdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import os from 'node:os';
import { randomBytes, scryptSync, timingSafeEqual, createHash } from 'node:crypto';
import { DatabaseSync } from 'node:sqlite';
import {catalog,catalogById,catalogCounts,catalogArt,randomCatalogRecipe} from './catalog.js';

const root = path.dirname(fileURLToPath(import.meta.url));
const port = Number(process.env.PORT || 3847);
const dataDir = path.resolve(process.env.DATA_DIR || path.join(root,'data'));
mkdirSync(dataDir,{recursive:true,mode:0o700});
const db = new DatabaseSync(path.join(dataDir,'recipes.sqlite'));
db.exec('PRAGMA journal_mode=WAL; PRAGMA busy_timeout=5000; CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL); CREATE TABLE IF NOT EXISTS sessions (token TEXT PRIMARY KEY, expires INTEGER NOT NULL); CREATE TABLE IF NOT EXISTS recipes (id TEXT PRIMARY KEY, content TEXT NOT NULL);');
const getSetting = key => db.prepare('SELECT value FROM settings WHERE key=?').get(key)?.value;
const setSetting = (key,value) => db.prepare('INSERT OR REPLACE INTO settings VALUES (?,?)').run(key,String(value));
if (!getSetting('revision')) {
  const seeds = JSON.parse(await readFile(path.join(root,'recipes.seed.json'),'utf8'));
  db.exec('BEGIN IMMEDIATE');
  try { for (const recipe of seeds) db.prepare('INSERT INTO recipes VALUES (?,?)').run(recipe.id,JSON.stringify(recipe)); setSetting('revision','1'); db.exec('COMMIT'); }
  catch (error) { db.exec('ROLLBACK'); throw error; }
}
const hashPassword = password => { const salt=randomBytes(16).toString('hex'); return `${salt}:${scryptSync(password,salt,64).toString('hex')}`; };
if (process.env.FAMILY_PASSWORD && !getSetting('password')) {
  if (process.env.FAMILY_PASSWORD.length < 8) throw new Error('FAMILY_PASSWORD must contain at least 8 characters.');
  setSetting('password',hashPassword(process.env.FAMILY_PASSWORD));
}
const mime={'.html':'text/html; charset=utf-8','.css':'text/css; charset=utf-8','.js':'text/javascript; charset=utf-8','.png':'image/png','.webp':'image/webp','.svg':'image/svg+xml','.ttf':'font/ttf','.txt':'text/plain; charset=utf-8','.webmanifest':'application/manifest+json'};
const publicFiles=new Set(['index.html','style.css','app.js','theme.js','halloween.css','catalog.css','assets/halloween-hero.png','manifest.webmanifest','sw.js','offline.html','assets/family-cat-cozy.png','assets/cat-tail-motion.svg','assets/cat-paw-motion.svg','assets/lora-Lora-Italic[wght].ttf','assets/lora-OFL.txt','assets/icon.svg','assets/icon-192.png','assets/icon-512.png','assets/food-grid.png','assets/golostext-GolosText[wght].ttf','assets/manrope-Manrope[wght].ttf','assets/golostext-OFL.txt','assets/manrope-OFL.txt']);
const catalogSheetFiles=new Set(Object.values(catalogArt).map(item=>'assets/catalog-sheets/'+item.sheet+'.webp'));
const sampleNames=new Set(['hero','soup','toast','bowl','oats','salad','salmon','cutlets','curd']);
const limits = new Map();
function json(res,status,data) { res.writeHead(status,{'Content-Type':'application/json; charset=utf-8','Cache-Control':'no-store'}); res.end(JSON.stringify(data)); }
function isLocal(req) { return ['127.0.0.1','::1','::ffff:127.0.0.1'].includes(req.socket.remoteAddress); }
function setupAllowed(req) { return isLocal(req) && /^(localhost|127\.0\.0\.1|\[::1\])(?::\d+)?$/.test(req.headers.host || ''); }
function session(req) {
  const token=(req.headers.cookie || '').split(';').map(c=>c.trim()).find(c=>c.startsWith('kroshka_session='))?.slice(16);
  if (!token || !/^[a-f0-9]{64}$/.test(token)) return false;
  return !!db.prepare('SELECT token FROM sessions WHERE token=? AND expires>?').get(createHash('sha256').update(token).digest('hex'),Date.now());
}
function cookie(res,token,clear=false) { res.setHeader('Set-Cookie',`kroshka_session=${token}; Path=/; HttpOnly; SameSite=Strict; Max-Age=${clear?0:2592000}${process.env.PUBLIC_URL?.startsWith('https:') ? '; Secure' : ''}`); }
function login(res) {
  const token=randomBytes(32).toString('hex');
  db.prepare('DELETE FROM sessions WHERE expires<?').run(Date.now());
  db.prepare('INSERT INTO sessions VALUES (?,?)').run(createHash('sha256').update(token).digest('hex'),Date.now()+2592000000);
  cookie(res,token); json(res,200,{authenticated:true});
}
function jsonContentType(value='') {
  const [type,...parameters]=value.split(';').map(part=>part.trim().toLowerCase());
  return type==='application/json' && parameters.every(part=>!/^charset\s*(?:=|$)/.test(part) || /^charset\s*=\s*(?:utf-8|"utf-8")$/.test(part));
}
function body(req,max=64*1024*1024,allowEmpty=false) {
  return new Promise((resolve,reject)=>{
    let length=0,failed=false; const chunks=[];
    const fail=(status,message)=>{
      if(failed)return;
      failed=true;chunks.length=0;
      const error=new Error(message);error.status=status;reject(error);
    };
    // Keep draining an oversized request so the client can receive the JSON 413.
    // Breaking an async iterator would destroy the socket before the response.
    req.on('data',chunk=>{
      if(failed)return;
      length+=chunk.length;
      if(length>max)return fail(413,'Слишком большой запрос. Уменьшите размер фотографий.');
      chunks.push(chunk);
    });
    req.on('end',()=>{
      if(failed)return;
      if(!length && allowEmpty)return resolve({});
      let input;
      try { input=JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(Buffer.concat(chunks))); }
      catch { return fail(400,'Не удалось прочитать JSON. Проверьте данные запроса.'); }
      if(input===null || typeof input!=='object' || Array.isArray(input))return fail(400,'Ожидается объект JSON. Данные не изменены.');
      resolve(input);
    });
    req.on('error',()=>fail(400,'Не удалось прочитать запрос. Данные не изменены.'));
    req.on('aborted',()=>fail(400,'Запрос прерван. Данные не изменены.'));
  });
}
function validRecipe(r) {
  if (!r || typeof r!=='object' || typeof r.id!=='string' || !/^[\w-]{1,100}$/.test(r.id) || typeof r.title!=='string' || !r.title.trim() || r.title.length>100 || typeof r.instructions!=='string' || !r.instructions.trim() || r.instructions.length>15000) return false;
  if (r.cookingMethods!==undefined && (!Array.isArray(r.cookingMethods) || r.cookingMethods.length>12 || r.cookingMethods.some(method=>!['Варить', 'Жарить', 'Запекать', 'Тушить', 'Готовить на пару', 'В аэрогриле', 'Без нагрева', 'Сковородка', 'Духовка', 'Аэрогриль', 'На пару', 'Кастрюля (варка)'].includes(method)) || new Set(r.cookingMethods).size!==r.cookingMethods.length)) return false;
  if (r.equipment!==undefined && (!Array.isArray(r.equipment)||r.equipment.length>6||r.equipment.some(item=>!['Блендер', 'Венчик', 'Миксер', 'Тёрка', 'Сито', 'Кухонные весы'].includes(item))||new Set(r.equipment).size!==r.equipment.length)) return false;
  if (r.isPreparation!==undefined && typeof r.isPreparation!=='boolean') return false;
  if (r.shelf!==undefined && !['main','trial'].includes(r.shelf)) return false;
  if (r.catalogId!==undefined && (typeof r.catalogId!=='string' || !/^[\w-]{1,80}$/.test(r.catalogId))) return false;
  if (r.recipeKind!==undefined && !['dish','mocktail','cocktail'].includes(r.recipeKind)) return false;
  if (r.sourceTitle!==undefined && (typeof r.sourceTitle!=='string' || r.sourceTitle.length>200)) return false;
  if (r.sourceUrl!==undefined && (typeof r.sourceUrl!=='string' || r.sourceUrl.length>1000 || !/^https?:\/\//.test(r.sourceUrl))) return false;
  if (r.steps!==undefined && (!Array.isArray(r.steps) || !r.steps.length || r.steps.length>100 || r.steps.some(step=>typeof step!=='string'||!step.trim()) || r.steps.join('\n')!==r.instructions)) return false;
  if (!Number.isInteger(r.time) || r.time<1 || r.time>2880 || !Number.isInteger(r.servings) || r.servings<1 || r.servings>100 || !Number.isFinite(r.createdAt) || typeof r.favorite!=='boolean') return false;
  if (!['Завтрак','Обед','Ужин','Перекус','Напиток'].includes(r.meal) || !['Лёгкое','Полноценное'].includes(r.size) || !['Белковое','Углеводное','Жирное','Не указан'].includes(r.macro) || !['Без мяса','С мясом'].includes(r.meat)) return false;
  if (!Array.isArray(r.ingredients) || !r.ingredients.length || r.ingredients.length>100 || r.ingredients.some(i=>!i || typeof i.name!=='string' || !i.name.trim() || i.name.length>100 || !['г','мл','шт','ч. л.','ст. л.','стакан','зубчик','пучок','щепотка','головка','банка','пакетик','упаковка','пачка','горсть','веточка','ломтик','стебель','капля','по вкусу'].includes(i.unit) || (i.unit!=='по вкусу' && (!Number.isFinite(Number(i.amount)) || Number(i.amount)<=0 || Number(i.amount)>100000)))) return false;
  for (const key of ['protein','fat','carbs','calories']) if (r[key]!==null && (typeof r[key]!=='number' || !Number.isFinite(r[key]) || r[key]<0 || r[key]>(key==='calories'?1000:100))) return false;
  if (typeof r.image!=='string' || r.image.length>3*1024*1024 || (r.image!=='' && !(r.image.startsWith('art:')&&Object.hasOwn(catalogArt,r.image.slice(4))) && !(r.image.startsWith('sample:') && sampleNames.has(r.image.slice(7))) && !/^data:image\/(?:jpeg|png|webp);base64,[A-Za-z0-9+/=\s]+$/.test(r.image))) return false;
  return true;
}
if (!catalog.every(validRecipe)) throw new Error('Invalid built-in catalog recipe: '+catalog.find(r=>!validRecipe(r))?.id);
// Upgrade existing copies from the earlier text-only catalog once. User photos stay intact.
if(Object.keys(catalogArt).length===catalog.length&&getSetting('catalogArtVersion')!=='1'){
  db.exec('BEGIN IMMEDIATE');
  try{
    let changed=false;
    for(const row of db.prepare('SELECT id,content FROM recipes').all()){
      const recipe=JSON.parse(row.content);
      if(recipe.catalogId&&recipe.image===''&&Object.hasOwn(catalogArt,recipe.catalogId)){
        recipe.image='art:'+recipe.catalogId;db.prepare('UPDATE recipes SET content=? WHERE id=?').run(JSON.stringify(recipe),row.id);changed=true;
      }
    }
    if(changed)setSetting('revision',Number(getSetting('revision'))+1);
    setSetting('catalogArtVersion','1');db.exec('COMMIT');
  }catch(error){db.exec('ROLLBACK');throw error;}
}

// Idempotent migration keeps old family recipes and backups compatible.
if(!getSetting('cookingActionsVersion')){
  const aliases={'Сковородка': 'Жарить', 'Духовка': 'Запекать', 'Аэрогриль': 'В аэрогриле', 'На пару': 'Готовить на пару', 'Кастрюля (варка)': 'Варить'};
  db.exec('BEGIN IMMEDIATE');
  try{
    let changed=false;
    for(const row of db.prepare('SELECT id,content FROM recipes').all()){
      const recipe=JSON.parse(row.content);
      if(Array.isArray(recipe.cookingMethods)){
        const methods=[...new Set(recipe.cookingMethods.map(m=>aliases[m]||m))];
        if(JSON.stringify(methods)!==JSON.stringify(recipe.cookingMethods)){
          recipe.cookingMethods=methods;db.prepare('UPDATE recipes SET content=? WHERE id=?').run(JSON.stringify(recipe),row.id);changed=true;
        }
      }
    }
    if(changed)setSetting('revision',Number(getSetting('revision'))+1);
    setSetting('cookingActionsVersion','1');db.exec('COMMIT');
  }catch(error){db.exec('ROLLBACK');throw error;}
}
function library() { return {revision:Number(getSetting('revision')),recipes:db.prepare('SELECT content FROM recipes').all().map(row=>JSON.parse(row.content))}; }
const server=http.createServer(async(req,res)=>{
  res.setHeader('X-Content-Type-Options','nosniff'); res.setHeader('Referrer-Policy','same-origin'); res.setHeader('X-Frame-Options','DENY');
  try {
    const url=new URL(req.url,'http://localhost');
    if (url.pathname==='/healthz' && req.method==='GET') return json(res,200,{app:'kroshka',version:2});
    if (url.pathname.startsWith('/api/')) {
      if (!['GET','HEAD'].includes(req.method)) {
        let origin; try { origin=req.headers.origin ? new URL(req.headers.origin).host : null; } catch { return json(res,403,{error:'Недопустимый источник запроса.'}); }
        if (origin && origin!==req.headers.host && req.headers.origin!==process.env.PUBLIC_URL) return json(res,403,{error:'Запрос с другого сайта запрещён.'});
        if (!jsonContentType(req.headers['content-type'])) return json(res,415,{error:'Ожидаются данные application/json в кодировке UTF-8.'});
      }
      if (url.pathname==='/api/session' && req.method==='GET') return json(res,200,{authenticated:session(req),needsSetup:!getSetting('password'),canSetup:setupAllowed(req)});
      if (url.pathname==='/api/setup' && req.method==='POST') {
        if (getSetting('password')) return json(res,409,{error:'Пароль уже задан. Войдите в книгу.'});
        if (!setupAllowed(req)) return json(res,403,{error:'Для первого запуска откройте книгу на самом Mac через localhost.'});
        const input=await body(req,4096);
        if (typeof input.password!=='string' || input.password.length<8 || input.password.length>128) return json(res,400,{error:'Придумайте пароль от 8 до 128 символов.'});
        // Recheck after the asynchronous body read, before changing shared state.
        if (getSetting('password')) return json(res,409,{error:'Пароль уже задан. Войдите в книгу.'});
        setSetting('password',hashPassword(input.password)); return login(res);
      }
      if (url.pathname==='/api/login' && req.method==='POST') {
        const address=req.socket.remoteAddress; const now=Date.now();
        if (limits.size>1000) for (const [key,value] of limits) if (now-value.since>900000) limits.delete(key);
        let count=limits.get(address); if (!count || now-count.since>900000) { count={since:now,attempts:0}; limits.set(address,count); }
        if (++count.attempts>20) return json(res,429,{error:'Слишком много попыток. Попробуйте через 15 минут.'});
        const input=await body(req,4096); const hash=getSetting('password');
        if (!hash || typeof input.password!=='string' || input.password.length>128) return json(res,401,{error:'Неверный пароль.'});
        const [salt,expected]=hash.split(':');
        if (!timingSafeEqual(scryptSync(input.password,salt,64),Buffer.from(expected,'hex'))) return json(res,401,{error:'Неверный пароль.'});
        limits.delete(address); return login(res);
      }
      if (!session(req)) return json(res,401,{error:'Войдите в семейную книгу.'});
      if (url.pathname==='/api/logout' && req.method==='POST') {
        await body(req,4096,true);
        const token=(req.headers.cookie || '').split(';').map(c=>c.trim()).find(c=>c.startsWith('kroshka_session='))?.slice(16);
        if (token) db.prepare('DELETE FROM sessions WHERE token=?').run(createHash('sha256').update(token).digest('hex'));
        cookie(res,'',true); return json(res,200,{ok:true});
      }
      if (url.pathname==='/api/catalog/art' && req.method==='GET') return json(res,200,{images:catalogArt});
      if (url.pathname==='/api/catalog' && req.method==='GET') return json(res,200,{total:catalog.length,counts:catalogCounts});
      if (url.pathname==='/api/catalog/random' && req.method==='GET') {
        const kind=url.searchParams.get('kind')||'',query=url.searchParams.get('q')||'';
        const excluded=(url.searchParams.get('exclude')||'').split(',').filter(Boolean);
        if (!['','dish','mocktail','cocktail'].includes(kind) || query.length>150 || excluded.length>100 || excluded.some(id=>!/^[\w-]{1,80}$/.test(id))) return json(res,400,{error:'Проверьте поиск и раздел каталога.'});
        return json(res,200,randomCatalogRecipe({query,kind,excluded}));
      }
      const catalogSave=url.pathname.match(/^\/api\/catalog\/([\w-]{1,80})\/save$/);
      if (catalogSave && req.method==='POST') {
        const original=catalogById.get(catalogSave[1]);
        if (!original) return json(res,404,{error:'Такого рецепта в каталоге нет.'});
        const input=await body(req,4096);
        const destination=input.destination??'main';
        if(!['main','trial'].includes(destination))return json(res,400,{error:'Выберите книгу рецептов или блюда на пробу.'});
        db.exec('BEGIN IMMEDIATE');
        try {
          const existing=db.prepare('SELECT content FROM recipes').all().map(row=>JSON.parse(row.content)).find(r=>r.catalogId===original.id || r.id==='catalog-'+original.id);
          if (existing) {
            if(existing.shelf==='trial'&&destination==='main'){
              const recipe={...existing,shelf:'main',createdAt:Date.now()};
              db.prepare('UPDATE recipes SET content=? WHERE id=?').run(JSON.stringify(recipe),existing.id);
              const revision=Number(getSetting('revision'))+1;setSetting('revision',revision);db.exec('COMMIT');
              return json(res,200,{alreadySaved:false,moved:true,recipe,revision});
            }
            db.exec('COMMIT');return json(res,200,{alreadySaved:true,moved:false,recipe:existing,revision:Number(getSetting('revision'))});
          }
          const recipe={...original,id:'catalog-'+original.id,catalogId:original.id,shelf:destination,createdAt:Date.now()};
          delete recipe.catalogCategory;
          db.prepare('INSERT INTO recipes VALUES (?,?)').run(recipe.id,JSON.stringify(recipe));
          const revision=Number(getSetting('revision'))+1;setSetting('revision',revision);db.exec('COMMIT');
          return json(res,201,{alreadySaved:false,recipe,revision});
        } catch(error) {db.exec('ROLLBACK');throw error;}
      }
      const trialAction=url.pathname.match(/^\/api\/trials\/([\w-]{1,100})(\/promote)?$/);
      if(trialAction&&((trialAction[2]&&req.method==='POST')||(!trialAction[2]&&req.method==='DELETE'))){
        await body(req,4096);
        db.exec('BEGIN IMMEDIATE');
        try{
          const stored=db.prepare('SELECT content FROM recipes WHERE id=?').get(trialAction[1]);
          if(!stored){db.exec('ROLLBACK');return json(res,404,{error:'Рецепт уже удалён на другом устройстве.'});}
          const recipe=JSON.parse(stored.content);
          if(trialAction[2]){
            if(recipe.shelf!=='trial'){db.exec('COMMIT');return json(res,200,{moved:false,recipe,revision:Number(getSetting('revision'))});}
            recipe.shelf='main';recipe.createdAt=Date.now();
            db.prepare('UPDATE recipes SET content=? WHERE id=?').run(JSON.stringify(recipe),recipe.id);
          }else{
            if(recipe.shelf!=='trial'){db.exec('ROLLBACK');return json(res,409,{error:'Рецепт уже перенесён в основную книгу. Он не удалён.'});}
            db.prepare('DELETE FROM recipes WHERE id=?').run(recipe.id);
          }
          const revision=Number(getSetting('revision'))+1;setSetting('revision',revision);db.exec('COMMIT');
          return json(res,200,{moved:!!trialAction[2],recipe,revision});
        }catch(error){db.exec('ROLLBACK');throw error;}
      }
      if (url.pathname==='/api/library' && req.method==='GET') {
        if (url.searchParams.get('revision')===getSetting('revision')) return json(res,200,{unchanged:true,revision:Number(getSetting('revision'))});
        return json(res,200,library());
      }
      if (url.pathname==='/api/library' && req.method==='PUT') {
        const input=await body(req);
        if (!Number.isInteger(input.revision) || !Array.isArray(input.recipes) || input.recipes.length>10000 || !input.recipes.every(validRecipe) || new Set(input.recipes.map(r=>r.id)).size!==input.recipes.length) return json(res,400,{error:'Проверьте название, ингредиенты, шаги, способы приготовления и числовые значения рецептов.'});
        db.exec('BEGIN IMMEDIATE');
        try {
          if (input.revision!==Number(getSetting('revision'))) { db.exec('ROLLBACK'); return json(res,409,{error:'Книгу уже изменили на другом устройстве. Мы загрузили обновления; проверьте рецепт и сохраните ещё раз.'}); }
          const keep=new Set(input.recipes.map(r=>r.id));
          for (const row of db.prepare('SELECT id FROM recipes').all()) if (!keep.has(row.id)) db.prepare('DELETE FROM recipes WHERE id=?').run(row.id);
          const put=db.prepare('INSERT INTO recipes VALUES (?,?) ON CONFLICT(id) DO UPDATE SET content=excluded.content WHERE content<>excluded.content');
          for (const recipe of input.recipes) put.run(recipe.id,JSON.stringify(recipe));
          setSetting('revision',input.revision+1); db.exec('COMMIT');
        } catch(error) { db.exec('ROLLBACK'); throw error; }
        return json(res,200,{revision:input.revision+1});
      }
      if (url.pathname==='/api/connection' && req.method==='GET') {
        const urls=[]; const host=process.env.KROSHKA_HOSTNAME;
        if (host && /^[a-zA-Z0-9-]+\.local$/.test(host)) urls.push(`http://${host}:${port}`);
        for (const entries of Object.values(os.networkInterfaces())) for (const entry of entries || []) if (entry.family==='IPv4' && !entry.internal && /^(192\.168\.|10\.|172\.(1[6-9]|2\d|3[01])\.)/.test(entry.address)) urls.push(`http://${entry.address}:${port}`);
        return json(res,200,{urls:[...new Set(urls)]});
      }
      return json(res,404,{error:'Такой функции нет.'});
    }
    if (!['GET','HEAD'].includes(req.method)) return json(res,405,{error:'Метод не поддерживается.'});
    let name; try { name=decodeURIComponent(url.pathname==='/'?'index.html':url.pathname.slice(1)); } catch { return json(res,400,{error:'Некорректный путь.'}); }
    if (!publicFiles.has(name) && !catalogSheetFiles.has(name)) return json(res,404,{error:'Страница не найдена.'});
    const content=await readFile(path.join(root,name));
    res.writeHead(200,{'Content-Type':mime[path.extname(name)] || 'application/octet-stream','Cache-Control':'no-cache'}); res.end(req.method==='HEAD'?undefined:content);
  } catch(error) { if (!res.writableEnded && !res.destroyed) json(res,error.status || 500,{error:error.status?error.message:'Не удалось сохранить или прочитать книгу. Проверьте свободное место на Mac.'}); }
});
server.listen(port,process.env.HOST || '0.0.0.0',()=>console.log(`Крошка: http://localhost:${server.address().port}`));
function shutdown() { server.close(()=>{db.close(); process.exit(0);}); }
process.on('SIGTERM',shutdown); process.on('SIGINT',shutdown);
