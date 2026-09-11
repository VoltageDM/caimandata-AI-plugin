#!/usr/bin/env python3
"""Explicit local SIM postflight: whole-package readback, then authorized read-only guide status."""
from __future__ import annotations
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import subprocess
import sys
sys.dont_write_bytecode=True
import plan_install as p

PROVENANCE_SCHEMA='caiman.local-simulation-source.v1'
MAX_STATUS_BYTES=32768
GUIDES={'vip':('GUIDED_SETUP.py','caiman.guided-setup.v1'),
        'gls-plus':('GLS_GUIDED_SETUP.py','caiman.gls-guided-setup.v1')}

def simulation_provenance(path,archive_sha256,tier,release):
    source=p.source_path(path)
    raw=p.v.strict_json(source)
    keys={'schema','scope','source_kind','archive_sha256','tier','release','authorization_reference','read_only_status_authorized'}
    if not isinstance(raw,dict) or set(raw)!=keys or raw.get('schema')!=PROVENANCE_SCHEMA or raw.get('scope')!='SIMULATION_ONLY' or raw.get('source_kind')!='authorized_vendor_pre_release':
        raise p.PlanError('expected separate explicit vendor/pre-release SIM provenance')
    if raw['archive_sha256']!=archive_sha256 or raw['tier']!=tier or raw['release']!=release:
        raise p.PlanError('SIM provenance differs from selected archive hash/tier/release')
    if not isinstance(raw['authorization_reference'],str) or not raw['authorization_reference'].strip() or len(raw['authorization_reference'])>500 or type(raw['read_only_status_authorized']) is not bool:
        raise p.PlanError('SIM provenance needs the actual authorization reference and explicit status permission')
    return raw,{'path':str(source),'sha256':p.v.sha(source),'authority':'caller-attested local test source; not live service entitlement'}

def postflight(root_raw,archive,archive_sha256,tier,release,provenance,run_status=False):
    root=p.v.root_path(root_raw)
    source,binding=simulation_provenance(provenance,archive_sha256,tier,release)
    # This checks every local expected file. A downloadable archive or a cloud
    # work folder elsewhere cannot satisfy this selected path's coverage.
    copy=p.plan_archive(root,archive,archive_sha256,tier,release)
    out={'schema':'caiman.local-install-postflight.v1','status':'INCOMPLETE_LOCAL_COPY',
         'scope':'SIMULATION_ONLY','project_root':str(root),'archive_sha256':archive_sha256,
         'release':release,'selected_tier':tier,'provenance':binding,
         'complete_local_copy':copy['complete_copy_verified'],'expected_files':copy['archive_files'],
         'counts':copy['counts'],'guide_status_executed':False,'full_setup_verified':False,
         'live_entitlement_verified':False,'live_business_operation_verified':False,
         'host_selected_folder_identity':'Caller must match this exact path to observed host selected-folder access; this script cannot authenticate the host mount.',
         'account_or_schedule_commands_run':False,'project_changed_by_postflight':False}
    if not copy['complete_copy_verified']:
        out['next_action']='Complete the authorized package copy in the actual selected folder; cloud staging or a reference-only subset is incomplete.'
        return out
    if not run_status or not source['read_only_status_authorized']:
        out['status']='COMPLETE_COPY_GUIDE_STATUS_PENDING'
        out['next_action']='Run the existing verified tier guide status only within actual local code permission; copy permission alone does not grant it.'
        return out
    expected,meta,_,_=p.archive_members(archive,archive_sha256,tier,release)
    guide_name,schema=GUIDES[tier]
    workflow=meta.get('guided_workflow')
    if not isinstance(workflow,dict) or workflow.get('helper')!=guide_name or workflow.get('entrypoint')!='AGENT_START.md':
        raise p.PlanError('package lacks its declared tier guide; reference-only fallback cannot claim setup')
    for name,digest in [('AGENT_START.md',workflow.get('entrypoint_sha256')),(guide_name,workflow.get('helper_sha256'))]:
        if not isinstance(digest,str) or expected.get(name)!=digest or p.v.sha(p.v.confined(root,name))!=digest:
            raise p.PlanError('guide declaration/hash is not bound to the complete approved archive')
    command=[sys.executable,str(root/guide_name),'status','--project-root',str(root)]
    env={key:os.environ[key] for key in ('PATH','SYSTEMROOT','WINDIR','TMP','TEMP') if key in os.environ}
    env.update(PYTHONDONTWRITEBYTECODE='1',PYTHONNOUSERSITE='1')
    result=subprocess.run(command,cwd=root,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=30,check=False)
    out['guide_status_executed']=True
    if result.returncode or len(result.stdout)>MAX_STATUS_BYTES or len(result.stderr)>MAX_STATUS_BYTES:
        out['status']='GUIDE_STATUS_FAILED'
        out['next_action']='Resolve the existing guide status failure; no installed/full-setup claim is permitted.'
        return out
    status=p.decode_json(result.stdout.decode('utf-8'))
    if not isinstance(status,dict) or status.get('schema')!=schema or status.get('status')!='GUIDANCE_ONLY' or status.get('project_root')!=str(root) or status.get('mutation_performed') is not False:
        raise p.PlanError('guide result is not read-only guidance for the exact selected root')
    action=status.get('next_action')
    if not isinstance(action,dict) or not isinstance(action.get('code'),str) or not action['code'] or len(action['code'])>100 or not isinstance(action.get('instruction'),str) or not action['instruction']:
        raise p.PlanError('guide result has no concrete next setup action')
    # Re-read after the status command; an altered package cannot pass postflight.
    for name,digest in expected.items():
        if p.v.sha(p.v.confined(root,name))!=digest:
            raise p.PlanError('package changed during guide postflight')
    out.update(status='COMPLETE_LOCAL_COPY_SETUP_PENDING',
        guide_status_schema=schema,guide_sha256=expected[guide_name],
        guide_result_sha256=__import__('hashlib').sha256(result.stdout).hexdigest(),
        observed_at=dt.datetime.now(dt.timezone.utc).isoformat(),
        next_action={'code':action['code'],'instruction':action['instruction'][:500]},
        allowed_claim='The complete local test package is present at this exact root. Follow the reported setup gate; full setup and live business readiness are not established.')
    return out

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for flag in ('root','archive','archive-sha256','selected-tier','approved-release','simulation-provenance'):
        parser.add_argument('--'+flag,required=True)
    parser.add_argument('--run-read-only-status',action='store_true')
    args=parser.parse_args(argv)
    try:
        out=postflight(args.root,args.archive,args.archive_sha256,args.selected_tier,args.approved_release,args.simulation_provenance,args.run_read_only_status)
    except (p.v.VerificationError,OSError,ValueError,subprocess.SubprocessError,p.zipfile.BadZipFile) as exc:
        out={'schema':'caiman.local-install-postflight.v1','status':'STOP','reason':str(exc)[:500],'full_setup_verified':False,'live_entitlement_verified':False}
    rendered=json.dumps(out,ensure_ascii=False,sort_keys=True)
    if len(rendered.encode())>p.MAX_PLAN_OUTPUT_BYTES:
        out={'schema':'caiman.local-install-postflight.v1','status':'STOP','reason':'postflight output metadata exceeds compact bound','full_setup_verified':False,'live_entitlement_verified':False};rendered=json.dumps(out)
    print(rendered)
    return 0 if out['status']=='COMPLETE_LOCAL_COPY_SETUP_PENDING' else 2

if __name__=='__main__':raise SystemExit(main())
