#!/usr/bin/env python3
"""Scoped Caiman workflow reminders and output gate; never account or access authority.

State is local to an opaque host session and stores workflow metadata and file references,
not conversation text or raw business reports.
The selected workspace is learned only from an observed installed helper result.
Callbacks are local observations, not independent provider attestations.
"""
from pathlib import Path
import argparse, hashlib, json, os, re, shlex, sqlite3, stat, sys, tempfile, time
sys.dont_write_bytecode=True
SCHEMA='caiman.core-workflow-callback.v1'
REMINDER=('For this Caiman business task, execute CLIENT_START.py from the active installed guide with the complete request. '
 'Read its real local memory and all selected methods; retain original source captures in that folder. '
 'Use PREPARE_OPERATING_INPUTS.py and BUILD_OPERATING_VIEW.py for the existing interactive view, and LISTING_REVIEW.py for requested listing/image PDFs with campaign intents. '
 'Do not replace those outputs with an independently designed Artifact. Run DELIVERY_CHECK.py on the actual saved files and present them. '
 'Source gaps permit clearly limited factual answers and drafts, never unsupported recommendations or a complete claim. '
 'Read source-backed field limits as limits, never claims about indexing or display. ACOS is not profit. Keep product relationships literal. Do not mention internal hooks to the customer. '
 'An owner question or true provider wait may pause the dependent step. Account changes remain separately gated.')
def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False)
def digest(v):return hashlib.sha256(v if isinstance(v,bytes) else v.encode()).hexdigest()
def context(kind,text):return {'hookSpecificOutput':{'hookEventName':kind,'additionalContext':text}}
def deny(text):return {'hookSpecificOutput':{'hookEventName':'PreToolUse','permissionDecision':'deny','permissionDecisionReason':text}}
def store_dir():
 uid=str(os.getuid()) if hasattr(os,'getuid') else digest(str(Path.home()))[:16]
 base=Path(tempfile.gettempdir())/('caiman-core-workflow-'+uid)
 base.mkdir(mode=0o700,exist_ok=True)
 if base.is_symlink() or not base.is_dir():raise ValueError('Unsafe session state directory')
 if hasattr(os,'getuid') and base.stat().st_uid!=os.getuid():raise ValueError('Session state owner differs')
 os.chmod(base,0o700);return base
def strings(value,depth=0):
 if depth>7:return
 if isinstance(value,str):yield value
 elif isinstance(value,dict):
  for key in ('stdout','text','content','output','result','structuredContent','data'):
   if key in value:yield from strings(value[key],depth+1)
 elif isinstance(value,list):
  for v in value[:150]:yield from strings(v,depth+1)
def objects(value):
 if isinstance(value,dict):yield value
 for s in strings(value):
  if len(s)>24*1024*1024:continue
  for raw in [s,*s.splitlines()[-20:]]:
   try:v=json.loads(raw)
   except (ValueError,TypeError):continue
   if isinstance(v,dict):yield v
def confined(root,name):
 if not isinstance(name,str) or not name or Path(name).is_absolute() or any(p in ('..','') for p in Path(name).parts):raise ValueError('Unsafe receipt path')
 p=root
 for part in Path(name).parts:
  p=p/part
  if p.is_symlink() or getattr(p,'is_junction',lambda:False)():raise ValueError('Linked receipt path')
 if not p.is_file():raise ValueError('Receipt file is unavailable in this host')
 return p
def checked(root,ref):
 p=confined(root,ref.get('path'));raw=p.read_bytes()
 if len(raw)>32*1024*1024 or digest(raw)!=ref.get('sha256'):raise ValueError('Receipt file differs')
 return raw
def proof(value,helper,command,tool_name):
 record=value.get('workflow_record')
 if not isinstance(record,dict):raise ValueError('Saved workflow record is missing')
 serialized=(json.dumps(record,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
 if digest(serialized)!=value.get('workflow_receipt',{}).get('sha256'):raise ValueError('Saved record bytes differ')
 pins=json.loads((Path(__file__).parent/'workflow-producers.json').read_text())
 expected=pins.get(helper,[])
 if record.get('producer_sha256') not in expected:raise ValueError('Unrecognized helper version')
 if record.get('schema')!=value.get('schema') or record.get('status')!=value.get('status'):raise ValueError('Helper record differs')
 # A cloud hook cannot pretend the device bridge is a local mount. It may retain
 # the actual response to one literal pinned helper command, but labels that as
 # an observed remote helper result, not independent host-file verification.
 args=shlex.split(command)
 if len(args)>1 and args[1]=='-B':args.pop(1)
 if len(args)<4 or Path(args[0]).name not in ('python','python3') or args[1]!=str(Path(record['guide'])/helper):raise ValueError('Require one literal helper command')
 if not any(x in tool_name.casefold() for x in ('bash','exec','command','run')):raise ValueError('Not an observed execution tool')
 flags={};i=2
 allowed={'--project-root','--goal'} if helper=='CLIENT_START.py' else {'--project-root','--dashboard','--review','--require-pdf'}
 while i<len(args):
  name=args[i]
  if name not in allowed or name in flags:raise ValueError('Unexpected command argument')
  if name=='--require-pdf':flags[name]=True;i+=1;continue
  if i+1>=len(args):raise ValueError('Missing command value')
  flags[name]=args[i+1];i+=2
 if flags.get('--project-root')!=record['project_root']:raise ValueError('Command workspace differs')
 root=Path(value['project_root'])
 if not root.is_absolute() or root.is_symlink():raise ValueError('Selected root invalid')
 if not root.is_dir():return {**record,'callback_observation':'REMOTE_HELPER_RESULT_HOST_READBACK_REQUIRED'}
 raw=checked(root,value['workflow_receipt']);record=json.loads(raw)
 # Only the saved record is authoritative; no fields added to stdout are trusted.
 if record.get('schema')!=value.get('schema') or record.get('status')!=value.get('status'):raise ValueError('Helper record differs')
 marker=json.loads(confined(root,'.caiman/workspace-id.json').read_bytes())
 if record.get('workspace_id')!=marker.get('id'):raise ValueError('Workspace marker differs')
 guide=Path(record['guide'])
 try:relative=guide.relative_to(root)
 except ValueError:raise ValueError('Guide outside selected workspace')
 producer=confined(root,str(relative/helper))
 if record.get('producer_sha256')!=digest(producer.read_bytes()):raise ValueError('Producer differs')
 active=json.loads(confined(root,'.caiman/active-guidance.json').read_bytes())
 # Resolve through the installation receipt without executing customer code.
 # The helper itself checked the active guide; here retain exact receipt/producer custody.
 if not isinstance(active,dict):raise ValueError('Missing active guidance')
 for ref in record.get('foundation',[]):checked(root,ref)
 for ref in record.get('artifacts',{}).values():checked(root,ref)
 return {**record,'callback_observation':'LOCAL_RECEIPT_REREAD_NOT_PROVIDER_ATTESTATION'}
def is_caiman_skill(event):
 name=event.get('tool_name','').casefold();v=event.get('tool_input',{})
 if 'skill' not in name:return False
 return any(isinstance(v.get(k),str) and re.fullmatch(r'(?:caiman-core:)?caiman',v[k],re.I) for k in ('skill','name','skill_name'))
def business_tool(name):
 n=name.casefold().replace('-','_')
 return 'caiman' in n and any(x in n for x in ('get_listing','search_listings','list_campaign','get_fba','business_report','ads_report','list_ad_group','analytics_','aplus','search_term','sqp'))
def html_artifact(event):
 n=event.get('tool_name','').casefold();args=event.get('tool_input',{})
 if 'artifact' not in n or any(x in n for x in ('read','list','get','open','present')):return None
 if args.get('command') in ('view','read','list','open'):return None
 for key in ('content','html','code'):
  s=args.get(key)
  if isinstance(s,str) and ('<html' in s.casefold() or '<!doctype html' in s.casefold()):return s
 return None
def question_titles(value):
 if isinstance(value,dict):
  for key,item in value.items():
   if key in ('question','title','prompt') and isinstance(item,str):yield item
   elif key in ('questions','input'):yield from question_titles(item)
 elif isinstance(value,list):
  for item in value:yield from question_titles(item)

def redundant_scope_question(event,state):
 name=event.get('tool_name','').casefold()
 if not any(x in name for x in ('question','ask_user','request_user_input')) or not state.get('start_verified') or not state.get('output_request'):return False
 request=state.get('request_scope') or {}
 if len(request.get('required_outputs',[]))<2:return False
 for title in question_titles(event.get('tool_input',{})):
  if re.search(r'apply|publish|spend|paid|connect|physical|which product|budget ceiling',title,re.I):continue
  if re.search(r'(want me to|would you like me to|shall i|may i) .{0,120}(keep going|continue|draft|prepare|deeper proposal)',title,re.I):return True
 return False

def handle(event,db):
 kind=event.get('hook_event_name');sid=event.get('session_id')
 if not isinstance(sid,str) or not 1<=len(sid)<=500:return context(kind,'Caiman workflow hook cannot verify a session ID. Follow the installed guide; do not claim active callback enforcement.') if is_caiman_skill(event) else {}
 key=digest(sid);row=db.execute('SELECT payload FROM sessions WHERE key=?',(key,)).fetchone();s=json.loads(row[0]) if row else {'active':False,'generation':0}
 if kind=='UserPromptSubmit':
  prompt=str(event.get('prompt',''));pending=s.get('output_request') and (s.get('delivery') or {}).get('request_coverage',{}).get('status') not in ('COMPLETE_LOCAL_OUTPUTS','COMPLETE_LOCAL_OUTPUTS_WITH_LIMITS');active=s['active'] or bool(re.search(r'\bcaiman\b',prompt,re.I))
  s={**s,'active':active,'generation':s['generation']+1,'prompt_sha256':digest(prompt),'business_reads':0,'start_verified':s.get('start_verified',False),'delivery':s.get('delivery') if pending else None,'stop_notices':0,'requires_pdf':bool(pending and s.get('requires_pdf')) or bool(re.search(r'\b(listing|images?|visual|pdf)\b',prompt,re.I)),'output_request':bool(pending) or bool(re.search(r'\b(set.?up|onboard|overview|dashboard|review|audit|report|improve|listings?|images?)\b',prompt,re.I))}
 if is_caiman_skill(event):s['active']=True
 if not s['active']:return {}
 result={}
 if kind=='UserPromptSubmit' or is_caiman_skill(event):result=context(kind,REMINDER)
 if kind=='PreToolUse':
  if redundant_scope_question(event,s):result=deny('The saved request already asks for these local proposals. Continue every independently supported requested output through the saved checklist. Ask only for a specific missing fact, generation capability, material business choice or separately gated account action; do not re-ask whether to draft the requested work.')
  args=event.get('tool_input',{});tool=event.get('tool_name','').casefold()
  directory=args.get('path',args.get('directory',args.get('folder_path')))
  if not s.get('root') and ('list' in tool and any(x in tool for x in ('directory','folder','file'))) and (not directory or str(directory).strip() in ('~','/','.',str(Path.home()))):
   result=deny('Ask the member to attach the exact business folder to this conversation using Add folder. A Project folder link may not mount it in this session. Do not list home or guess a default workspace. Continue from the explicitly selected path.')
  if business_tool(event.get('tool_name','')):
   s['business_reads']=s.get('business_reads',0)+1
   if not s.get('start_verified'):result=context(kind,REMINDER+' Begin the selected workflow now before continuing the business analysis; successful data reads alone are not setup or delivery.')
  content=html_artifact(event)
  if content and (s.get('output_request') or s.get('business_reads')):
   approved=(s.get('delivery') or {}).get('artifacts',{}).get('dashboard',{}).get('sha256')
   if digest(content)!=approved:result=deny('Caiman business output requires the existing saved dashboard. Run DELIVERY_CHECK.py, then open its exact HTML using the host file presentation tool. Do not create a replacement Artifact. '+REMINDER)
 if kind=='PostToolUse':
  command=str(event.get('tool_input',{}).get('command',''))
  for value in objects(event.get('tool_response',{})):
   match={'caiman.workflow-start.v1':('CLIENT_START.py','WORKFLOW_STARTED'),'caiman.delivery-file-check.v1':('DELIVERY_CHECK.py','OUTPUT_FILES_VERIFIED')}.get(value.get('schema'))
   if not match or match[0] not in command or value.get('status')!=match[1]:continue
   try:verified=proof(value,match[0],command,event.get('tool_name',''))
   except (ValueError,OSError,KeyError,TypeError):
    result=context(kind,'Caiman helper output was observed, but this hook could not independently reread its saved receipt in the selected host folder. Do not claim hook enforcement or complete delivery. Keep the actual host file readback and resolve the selected mount.');continue
   if match[0]=='CLIENT_START.py':s.update(start_verified=True,workspace_id=verified['workspace_id'],root=verified['project_root'],request_scope={k:(verified.get('request_scope') or {}).get(k,[]) for k in ('required_outputs','selected_methods')})
   elif verified.get('workspace_id')==s.get('workspace_id'):
    s['delivery']=verified
    result=context(kind,'Caiman saved output files were checked. Present the exact dashboard and requested PDF through the host and inspect them. File verification does not establish business readiness or host presentation.')
 if kind=='Stop' and s.get('output_request') and (s.get('business_reads') or s.get('start_verified')):
  delivery=s.get('delivery');complete=delivery and delivery.get('request_coverage',{}).get('status') in ('COMPLETE_LOCAL_OUTPUTS','COMPLETE_LOCAL_OUTPUTS_WITH_LIMITS') and (not s.get('requires_pdf') or 'pdf' in delivery.get('artifacts',{}))
  final=str(event.get('last_assistant_message',''))
  # An honest question/hold is allowed. Never erase the user's prompt or loop forever.
  claim_text=re.sub(r'\b(not|isn.t|aren.t)\s+(ready|complete|live|healthy)\b','',final,flags=re.I)
  claims=bool(re.search(r'\b(ready|complete|live|built|created|generated|healthy|no stockout risk)\b|setup.{0,12}done',claim_text,re.I))
  explicit_hold=bool(re.search(r'\b(incomplete|not (?:ready|complete)|cannot complete|still missing|need from you)\b',final,re.I))
  independent_gaps=any(g.startswith(('Selected method not accounted','Saved advertising report omitted')) for g in (delivery or {}).get('request_coverage',{}).get('gaps',[]))
  if not complete and (claims and (not explicit_hold or not delivery or independent_gaps) or not final) and s.get('stop_notices',0)<2:
   s['stop_notices']=s.get('stop_notices',0)+1
   result={'decision':'block','reason':'Caiman delivery is incomplete: the complete saved request has unresolved output, method or source coverage. Continue the installed workflow, or state the exact missing owner input/provider wait without claiming completion. '+REMINDER}
  elif not complete:s['last_outcome']='INCOMPLETE_NOT_ACCEPTED'
  else:s['last_outcome']='LOCAL_SCOPE_CHECKED_PRESENTATION_STILL_REQUIRES_NATIVE_PROOF'
 db.execute('INSERT OR REPLACE INTO sessions VALUES(?,?,?)',(key,canonical(s),time.time()))
 db.execute('INSERT INTO callbacks VALUES(?,?,?,?,?)',(key,kind,event.get('tool_name',''),time.time(),'deny' if result.get('hookSpecificOutput',{}).get('permissionDecision')=='deny' else result.get('decision','observed')))
 return result
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--event',required=True);a=p.parse_args()
 try:
  raw=sys.stdin.buffer.read(26*1024*1024+1)
  if len(raw)>26*1024*1024:raise ValueError('Hook input exceeds bound')
  event=json.loads(raw)
  if event.get('hook_event_name')!=a.event:raise ValueError('Hook event differs')
  dbpath=store_dir()/'sessions.sqlite'
  if dbpath.is_symlink():raise ValueError('Unsafe state file')
  db=sqlite3.connect(dbpath,timeout=2);os.chmod(dbpath,0o600)
  try:
   db.execute('CREATE TABLE IF NOT EXISTS sessions(key TEXT PRIMARY KEY,payload TEXT NOT NULL,updated REAL NOT NULL)')
   db.execute('CREATE TABLE IF NOT EXISTS callbacks(session TEXT,event TEXT,tool TEXT,at REAL,decision TEXT)')
   db.execute('BEGIN IMMEDIATE');out=handle(event,db);db.commit()
  finally:db.close()
 except Exception:
  # Never discard a user prompt or disable independent host permissions on a hook error.
  out=context(a.event,'Caiman workflow callback verification is unavailable. Use the installed workflow and actual host readback; do not claim enforcement or complete output from this hook.') if a.event in ('PostToolUse','Stop') else {}
 print(canonical(out));return 0
if __name__=='__main__':raise SystemExit(main())
