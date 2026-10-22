import {readFile} from 'node:fs/promises';
import {randomInt} from 'node:crypto';

// Read-only application content, kept outside the family's writable SQLite book.
const dishes=JSON.parse(await readFile(new URL('./catalog/recipes.json',import.meta.url),'utf8'));
const drinks=JSON.parse(await readFile(new URL('./catalog/cocktails.json',import.meta.url),'utf8'));
export const catalogArt=JSON.parse(await readFile(new URL('./catalog/image-index.json',import.meta.url),'utf8'));
export const catalog=[...dishes,...drinks];
for(const recipe of catalog)if(Object.hasOwn(catalogArt,recipe.id))recipe.image='art:'+recipe.id;
const legacyMethods={'Сковородка': 'Жарить', 'Духовка': 'Запекать', 'Аэрогриль': 'В аэрогриле', 'На пару': 'Готовить на пару', 'Кастрюля (варка)': 'Варить'};
for(const recipe of catalog)recipe.cookingMethods=[...new Set((recipe.cookingMethods||[]).map(m=>legacyMethods[m]||m))];
export const catalogById=new Map(catalog.map(recipe=>[recipe.id,recipe]));
if(catalogById.size!==catalog.length)throw new Error('Duplicate catalog identifiers');
const normalize=text=>String(text).toLowerCase().replaceAll('ё','е').replace(/[^\p{L}\p{N}\s]/gu,' ').trim();
const stem=word=>word.length>4?word.replace(/(?:ами|ями|ого|ому|ов|ев|ей|ой|ый|ий|ая|яя|ое|ее|ую|юю|ам|ям|ах|ях|ом|ем|а|я|ы|и|у|ю|е|о)$/u,''):word;
const index=catalog.map(recipe=>({recipe,words:normalize(recipe.title+' '+recipe.ingredients.map(i=>i.name).join(' ')).split(/\s+/).map(stem)}));
export const catalogCounts=Object.fromEntries(['dish','mocktail','cocktail'].map(kind=>[kind,catalog.filter(r=>r.recipeKind===kind).length]));
export function randomCatalogRecipe({query='',kind='',excluded=[]}={}){
  const tokens=normalize(query).split(/\s+/).filter(t=>t&&!['и','с','из'].includes(t)).map(stem);
  const matches=index.filter(({recipe,words})=>(!kind||recipe.recipeKind===kind)&&tokens.every(token=>words.some(word=>word.includes(token)))).map(item=>item.recipe);
  const skip=new Set(excluded);
  const fresh=matches.filter(recipe=>!skip.has(recipe.id));
  const pool=fresh.length?fresh:matches;
  return {total:catalog.length,counts:catalogCounts,matched:matches.length,recipe:pool.length?pool[randomInt(pool.length)]:null};
}
