#!/usr/bin/env python3
"""Copy the pinned helpers from an approved local carrier; execute none."""
import argparse,hashlib,io,json,os,pathlib,re,stat,tempfile,zipfile
PREFIX='caiman-core/skills/kit-sync/scripts/'
FILES={'plan_install.py': '81dc330bbc6a2a16604fefc849f01c3a148273ae3fd9c2612a0d2a1b7fd6c43a', 'verify_kit.py': '269fa90b1abef5ccf0d6d12db33958be86529cf131a095e4d77f4799eaf852fa', 'postflight_install.py': '0b1d3d9370415b1b4c5a5be7a05190a2c8156527ce69aaf56cd30edfb0176700', 'install_kit.py': '16df011bebbf7c7f060ce2c381e481911e5acb674548974c15f612d80bb6a128', 'download_kit.py': '4c6c81e0d5b24ff782652b1f6953a4bdb8c078299e5da9e9ccd87824bbb08e5f', 'resolve_guidance.py': 'e2c958ab0204a9274fd8ea3c637f558726875769d27736ec34eb4c994c6e7ed2'}

def safe_path(raw,directory=False):
 p=pathlib.Path(raw)
 if not p.is_absolute() or '..' in p.parts or len(str(p))>1024:raise ValueError('use a bounded absolute local path')
 for item in (p,*p.parents):
  s=item.lstat()
  if stat.S_ISLNK(s.st_mode) or getattr(s,'st_file_attributes',0)&0x400:raise ValueError('symlink/reparse ancestor')
 if not (p.is_dir() if directory else p.is_file()):raise ValueError('wrong local source/staging type')
 return p

def bootstrap(archive,expected_sha,parent,carrier_kind='core'):
 prefix=PREFIX if carrier_kind=='core' else ('Caiman VIP - Guided Kit/Install tools/' if carrier_kind=='vip' else 'Caiman GLS Plus - Guided Kit/Install tools/')
 package_root=prefix.split('/')[0]
 maximum=2097152 if carrier_kind=='core' else 134217728
 stage=None;written=[]
 try:
  if not re.fullmatch('[0-9a-f]{64}',expected_sha):raise ValueError('approved archive SHA-256 required')
  src=safe_path(archive);parent=safe_path(parent,True)
  if src.stat().st_size>maximum:raise ValueError('carrier exceeds its bounded size')
  with src.open('rb') as f:raw=f.read(maximum+1)
  if len(raw)>maximum or hashlib.sha256(raw).hexdigest()!=expected_sha:raise ValueError('carrier SHA-256 mismatch')
  payload={}
  with zipfile.ZipFile(io.BytesIO(raw)) as z:
   entries=z.infolist();seen=set();total=0
   if not 3<=len(entries)<=(64 if carrier_kind=='core' else 20000):raise ValueError('carrier member count outside bound')
   for i in entries:
    name=i.filename[:-1] if i.is_dir() else i.filename;parts=name.split('/');key=name.casefold();mode=i.external_attr>>16
    if not (name.startswith(package_root+'/') or name==package_root and i.is_dir()) or '\\' in name or ':' in name or key in seen or any(x in ('','.','..') or x.endswith((' ','.')) or any(ord(c)<32 or c in '<>"|?*' for c in x) or re.fullmatch(r'(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(\..*)?',x,re.I) for x in parts):raise ValueError('unsafe/duplicate carrier member')
    seen.add(key);total+=i.file_size
    if i.flag_bits&1 or stat.S_IFMT(mode) not in (0,stat.S_IFDIR if i.is_dir() else stat.S_IFREG) or i.file_size>(262144 if carrier_kind=='core' else 67108864) or total>(524288 if carrier_kind=='core' else 268435456):raise ValueError('unsupported/oversized carrier member')
   for name,digest in FILES.items():
    data=z.read(prefix+name)
    if hashlib.sha256(data).hexdigest()!=digest:raise ValueError('pinned helper mismatch: '+name)
    payload[name]=data
  stage=pathlib.Path(tempfile.mkdtemp(prefix='caiman-local-helpers-',dir=parent))
  for name,data in payload.items():
   path=stage/name
   with os.fdopen(os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0),0o600),'wb') as f:f.write(data)
   if hashlib.sha256(path.read_bytes()).hexdigest()!=FILES[name]:raise ValueError('local helper readback mismatch')
   written.append(name)
  result={'schema':'caiman.local-helper-bootstrap.v1','status':'LOCAL_HELPERS_READY','staging_dir':str(stage),'archive_sha256':expected_sha,'helpers':FILES,'copied':len(FILES),'helper_or_engine_code_executed':False,'account_or_schedule_actions':False}
  (stage/'LOCAL_HELPERS.json').write_text(json.dumps(result,sort_keys=True)+'\n')
  return result
 except (OSError,ValueError,KeyError,RuntimeError,zipfile.BadZipFile) as e:
  return {'schema':'caiman.local-helper-bootstrap.v1','status':'STOP','reason':str(e)[:300],'partial_staging_dir':str(stage) if stage else None,'copied_before_stop':written,'helper_or_engine_code_executed':False}

def main():
 p=argparse.ArgumentParser(description=__doc__)
 for name in ('archive','archive-sha256','staging-parent'):p.add_argument('--'+name,required=True)
 p.add_argument('--carrier-kind',choices=['core','vip','gls-plus'],default='core')
 a=p.parse_args();r=bootstrap(a.archive,a.archive_sha256,a.staging_parent,a.carrier_kind);print(json.dumps(r,sort_keys=True));return 0 if r['status']=='LOCAL_HELPERS_READY' else 2
if __name__=='__main__':raise SystemExit(main())
