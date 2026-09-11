#!/usr/bin/env python3
"""Copy three pinned helpers from an approved local carrier; execute none."""
import argparse,hashlib,io,json,os,pathlib,re,stat,tempfile,zipfile
PREFIX='caiman-core/skills/kit-sync/scripts/'
FILES={
 'plan_install.py':'d4d6045bc8477435eb9048e560125b39c9ed3ccff16fa20a8618d55d1f57118a',
 'verify_kit.py':'269fa90b1abef5ccf0d6d12db33958be86529cf131a095e4d77f4799eaf852fa',
 'postflight_install.py':'0b1d3d9370415b1b4c5a5be7a05190a2c8156527ce69aaf56cd30edfb0176700'}
def safe_path(raw,directory=False):
 p=pathlib.Path(raw)
 if not p.is_absolute() or '..' in p.parts or len(str(p))>1024:raise ValueError('use a bounded absolute local path')
 for item in (p,*p.parents):
  s=item.lstat()
  if stat.S_ISLNK(s.st_mode) or getattr(s,'st_file_attributes',0)&0x400:raise ValueError('symlink/reparse ancestor')
 if not (p.is_dir() if directory else p.is_file()):raise ValueError('wrong local source/staging type')
 return p

def bootstrap(archive,expected_sha,parent):
 stage=None;written=[]
 try:
  if not re.fullmatch('[0-9a-f]{64}',expected_sha):raise ValueError('approved archive SHA-256 required')
  src=safe_path(archive);parent=safe_path(parent,True)
  if src.stat().st_size>2097152:raise ValueError('carrier exceeds 2 MiB')
  with src.open('rb') as f:raw=f.read(2097153)
  if len(raw)>2097152 or hashlib.sha256(raw).hexdigest()!=expected_sha:raise ValueError('carrier SHA-256 mismatch')
  payload={}
  with zipfile.ZipFile(io.BytesIO(raw)) as z:
   entries=z.infolist();seen=set();total=0
   if not 3<=len(entries)<=64:raise ValueError('carrier member count outside bound')
   for i in entries:
    name=i.filename[:-1] if i.is_dir() else i.filename;parts=name.split('/');key=name.casefold();mode=i.external_attr>>16
    if not (name.startswith('caiman-core/') or name=='caiman-core' and i.is_dir()) or '\\' in name or ':' in name or key in seen or any(x in ('','.','..') or x.endswith((' ','.')) or any(ord(c)<32 or c in '<>"|?*' for c in x) or re.fullmatch(r'(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(\..*)?',x,re.I) for x in parts):raise ValueError('unsafe/duplicate carrier member')
    seen.add(key);total+=i.file_size
    if i.flag_bits&1 or stat.S_IFMT(mode) not in (0,stat.S_IFDIR if i.is_dir() else stat.S_IFREG) or i.file_size>262144 or total>524288:raise ValueError('unsupported/oversized carrier member')
   for name,digest in FILES.items():
    data=z.read(PREFIX+name)
    if hashlib.sha256(data).hexdigest()!=digest:raise ValueError('pinned helper mismatch: '+name)
    payload[name]=data
  stage=pathlib.Path(tempfile.mkdtemp(prefix='caiman-local-helpers-',dir=parent))
  for name,data in payload.items():
   path=stage/name
   with os.fdopen(os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0),0o600),'wb') as f:f.write(data)
   if hashlib.sha256(path.read_bytes()).hexdigest()!=FILES[name]:raise ValueError('local helper readback mismatch')
   written.append(name)
  result={'schema':'caiman.local-helper-bootstrap.v1','status':'LOCAL_HELPERS_READY','staging_dir':str(stage),'archive_sha256':expected_sha,'helpers':FILES,'copied':3,'helper_or_engine_code_executed':False,'account_or_schedule_actions':False}
  (stage/'LOCAL_HELPERS.json').write_text(json.dumps(result,sort_keys=True)+'\n')
  return result
 except (OSError,ValueError,KeyError,RuntimeError,zipfile.BadZipFile) as e:
  return {'schema':'caiman.local-helper-bootstrap.v1','status':'STOP','reason':str(e)[:300],'partial_staging_dir':str(stage) if stage else None,'copied_before_stop':written,'helper_or_engine_code_executed':False}

def main():
 p=argparse.ArgumentParser(description=__doc__)
 for name in ('archive','archive-sha256','staging-parent'):p.add_argument('--'+name,required=True)
 a=p.parse_args();r=bootstrap(a.archive,a.archive_sha256,a.staging_parent);print(json.dumps(r,sort_keys=True));return 0 if r['status']=='LOCAL_HELPERS_READY' else 2
if __name__=='__main__':raise SystemExit(main())
