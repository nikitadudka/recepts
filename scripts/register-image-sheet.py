"""Store generated contact sheets as WebP without cropping/resizing their pixels.
The browser crops the 4x4 cells using SVG viewBox, retaining a distinct illustration per recipe.
"""
import argparse,json,fcntl,hashlib,os
from pathlib import Path
from PIL import Image
from sheet_geometry import photo_rectangles
p=argparse.ArgumentParser();p.add_argument('--name',required=True);p.add_argument('--source',required=True);args=p.parse_args()
root=Path(__file__).resolve().parents[1]
jobs=json.loads((root/'catalog/image-prompts.json').read_text());job=next(j for j in jobs if j['name']==args.name)
source=Path(args.source);out=root/'assets/catalog-sheets'/f'{args.name}.webp'
with Image.open(source) as image:
 width,height=image.size
 if min(width,height)<256:raise ValueError('Image sheet is too small')
 rectangles=photo_rectangles(image)
 image.convert('RGB').save(out,'WEBP',quality=60,method=6)
lock=Path('/tmp/kroshka-image-index.lock')
with lock.open('w') as guard:
 fcntl.flock(guard,fcntl.LOCK_EX)
 path=root/'catalog/image-index.json';index=json.loads(path.read_text()) if path.exists() else {}
 for n,id in enumerate(job['ids']):index[id]={'sheet':args.name,**rectangles[n],'fullWidth':width,'fullHeight':height}
 temp=path.with_suffix('.tmp');temp.write_text(json.dumps(index,separators=(',',':'))+'\n');os.replace(temp,path)
 log=root/'catalog/image-generation.json';records=json.loads(log.read_text()) if log.exists() else {}
 records[args.name]={'source':source.name,'sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'recipes':len(job['ids']),'width':width,'height':height,'bytes':out.stat().st_size,'quality':60,'cropVersion':2}
 log.write_text(json.dumps(records,indent=2)+'\n')
print(args.name,len(job['ids']),out.stat().st_size)
