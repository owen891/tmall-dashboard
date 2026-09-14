import json, sqlite3, urllib.request, os, mimetypes
from pathlib import Path
root=Path(r'E:\www\tmall-dashboard')
db=root/'data/demo/dashboard.db'
out=root/'frontend/ui_demo/assets/product-thumbs'
c=sqlite3.connect(db)
rows=c.execute('select product_id,image_url from products').fetchall()
local=[(p,u) for p,u in rows if str(u or '').startswith('/assets/product-thumbs/')]
blank=[p for p,u in rows if not str(u or '').strip()]
remote=[(p,u) for p,u in rows if str(u or '').startswith('http')]
missing=[]; invalid=[]
for p,u in local:
 f=out/Path(u).name
 if not f.exists() or f.stat().st_size==0: missing.append((p,u)); continue
 h=f.read_bytes()[:16]
 if not (h.startswith(b'\xff\xd8\xff') or h.startswith(b'\x89PNG\r\n\x1a\n') or h[:6] in (b'GIF87a',b'GIF89a') or h.startswith(b'RIFF') or h.startswith(b'BM')): invalid.append((p,u,h))
print('db local remote blank',len(local),len(remote),len(blank))
print('files',len(list(out.iterdir())),'size_mb',round(sum(f.stat().st_size for f in out.iterdir() if f.is_file())/1024/1024,2))
print('missing local',len(missing),'invalid header',len(invalid))
print('sample local',local[:3])
# validate the local route through running Flask server
for p,u in local[:3]:
 try:
  with urllib.request.urlopen('http://127.0.0.1:5000'+u,timeout=10) as r:
   print(r.status,r.headers.get_content_type(),r.headers.get('Content-Length'),u)
 except Exception as e: print('http ERR',u,repr(e))
print('report',json.loads((root/'data/product_image_repair.json').read_text(encoding='utf-8')) | {'unresolved_product_ids':'(omitted)'})
