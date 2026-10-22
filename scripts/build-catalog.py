"""Normalize a pinned Russian recipe corpus; no network or generated recipe variants.
Usage: python3 scripts/build-catalog.py /path/to/russian-recipes-parser
"""
import sys,json,re,html,unicodedata,collections,hashlib
from pathlib import Path
source=Path(sys.argv[1]);root=Path(__file__).resolve().parents[1]
units={'г':('г',1),'кг':('г',1000),'мл':('мл',1),'л':('мл',1000),'шт.':('шт',1),'шт':('шт',1),'ст.л.':('ст. л.',1),'ст.л':('ст. л.',1),'ч.л.':('ч. л.',1),'ч.л':('ч. л.',1)}
for canonical,forms in {'стакан':['стакан','стакана','стаканов'],'зубчик':['зубчик','зубчика','зубчиков'],'пучок':['пучок','пучка','пучков'],'щепотка':['щепотка','щепотки'],'головка':['головка','головки'],'банка':['банка','банки'],'пакетик':['пакетик','пакетика'],'упаковка':['упаковка','упаковки'],'пачка':['пачка','пачки'],'горсть':['горсть','горсти'],'веточка':['веточка','веточки','веточек'],'ломтик':['ломтик','ломтика','ломтиков'],'стебель':['стебель','стебля']}.items():
 for form in forms:units[form]=(canonical,1)
fractions={'½':.5,'¼':.25,'¾':.75,'⅓':1/3,'⅔':2/3,'⅛':.125,'⅜':.375,'⅝':.625,'⅞':.875}
def clean(s):return re.sub(r'\s+',' ',html.unescape(re.sub('<[^>]*>','',s or ''))).strip()
def number(s):
 s=clean(str(s)).replace(',','.');value=0
 for k,v in fractions.items():
  if k in s:
   if s.count(k)!=1:raise ValueError()
   value=v;s=s.replace(k,'').strip();break
 if s:
  if re.fullmatch(r'\d+\s*/\s*\d+',s):a,b=map(float,s.split('/'));value+=a/b
  else:value+=float(s)
 if not 0<value<=100000:raise ValueError()
 return round(value,3)
def minutes(s):
 s=clean(s).lower();result=0
 for value,unit in re.findall(r'(\d+(?:[.,]\d+)?)\s*(дн|день|дня|сут|час|ч\b|мин)',s):result+=float(value.replace(',','.'))*(1440 if unit in ['дн','день','дня','сут'] else 60 if unit in ['час','ч'] else 1)
 if not 1<=result<=2880:raise ValueError()
 return round(result)
def convert(path):
 r=json.loads(path.read_text());title=clean(r['title'])
 if not title or len(title)>100 or len(r['ingredients'])!=1:raise ValueError()
 group=r['ingredients'][0];m=re.search(r'на\s+(\d+)\s+порц',group.get('name') or '')
 if not m or not 1<=int(m[1])<=100:raise ValueError()
 t=minutes(r.get('cooktime'))
 if r.get('preparetime'):t+=minutes(r['preparetime'])
 if t>2880:raise ValueError()
 ingredients=[]
 for i in group['list']:
  name=clean(i['name']+' '+(i.get('notes') or ''));raw=i.get('value');unit=i.get('type')
  if not name or len(name)>100:raise ValueError()
  if raw in [None,'']:
   if not re.search(r'соль|перец|специ|зелень|корица|ванилин|паприка|мускат|тмин|зира|кориандр',name):raise ValueError()
   amount='';unit='по вкусу'
  else:
   if unit not in units:raise ValueError()
   unit,mult=units[unit];amount=round(number(raw)*mult,3)
  ingredients.append({'name':name,'amount':amount,'unit':unit})
 steps=[clean(i['text']) for i in r['instruction'] if clean(i['text'])]
 if not 2<=len(steps)<=35 or not 2<=len(ingredients)<=35:raise ValueError()
 instructions='\n'.join(steps)
 if not 100<=len(instructions)<=12000:raise ValueError()
 category=r.get('category') or 'Разное'
 if category in ['Заготовки','Соусы','Тесто домашнее','Молочные продукты домашние','Напитки']:raise ValueError()
 text=' '.join(i['name'] for i in ingredients).lower()
 meat=bool(re.search(r'говядин|свинин|баранин|куриц|курин|индейк|индюш|бекон|ветчин|колбас|сосиск|мяс|фарш|теляти|утк|кролик',text))
 meal='Перекус' if category in ['Закуски','Десерты','Выпечка'] else 'Обед'
 if re.search(r'омлет|сырник|каша|оладь|блин',title,re.I):meal='Завтрак'
 methodtext=(title+' '+instructions).lower();methods=[]
 if re.search(r'сковород|обжар',methodtext):methods.append('Сковородка')
 if re.search(r'духов|духовк|запека|выпека',methodtext):methods.append('Духовка')
 if 'аэрогрил' in methodtext:methods.append('Аэрогриль')
 if 'на пару' in methodtext:methods.append('На пару')
 if re.search(r'кастрюл|\bварим|\bварить|\bварит|отвар|сварить|сварим',methodtext):methods.append('Кастрюля (варка)')
 return {'id':'ru-'+path.stem,'title':title,'time':t,'servings':int(m[1]),'meal':meal,'size':'Полноценное' if category in ['Вторые блюда','Супы'] else 'Лёгкое','macro':'Не указан','meat':'С мясом' if meat else 'Без мяса','calories':None,'protein':None,'fat':None,'carbs':None,'image':'','ingredients':ingredients,'steps':steps,'instructions':instructions,'cookingMethods':methods,'favorite':False,'createdAt':0,'recipeKind':'dish','catalogCategory':category,'sourceTitle':'Вкусо.ру · '+(r.get('cuisine') or 'Домашняя кухня'),'sourceUrl':r['source']}
valid=[];seen=set();fail=0
for path in sorted((source/'storage/recipes').rglob('*.json')):
 try:
  r=convert(path);fingerprint=r['title'].lower().replace('ё','е')
  if fingerprint in seen:continue
  seen.add(fingerprint);valid.append(r)
 except (ValueError,KeyError,TypeError,ZeroDivisionError):fail+=1
# Distribute categories rather than choosing only one part of the source dump.
groups=collections.defaultdict(list)
for r in valid:groups[r['catalogCategory']].append(r)
selected=[]
while len(selected)<1800 and any(groups.values()):
 for key in sorted(groups):
  if groups[key] and len(selected)<1800:selected.append(groups[key].pop(0))
(root/'catalog/recipes.json').write_text(json.dumps(selected,ensure_ascii=False,separators=(',',':'))+'\n')
print('Eligible:',len(valid),'selected:',len(selected),'categories:',dict(collections.Counter(r['catalogCategory'] for r in selected)))
