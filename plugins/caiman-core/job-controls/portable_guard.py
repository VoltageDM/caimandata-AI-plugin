#!/usr/bin/env python3
"""Paired plugin/kit job controls. No network calls or remote credentials.

The host owns hook invocation, permissions and remote authentication. This
component records event continuity and narrows operations within one workspace.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import signal
import sqlite3
import sys
import time

sys.dont_write_bytecode = True
from job_engine import Ledger, Refusal, require, digest, canonical
from amazon_policy import classify
from portable_context import PortableContext

BUNDLE = Path(__file__).resolve().parent
VERSION = '20260915-v1'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def member(root, relative):
    path = PurePosixPath(relative)
    require(isinstance(relative, str) and not path.is_absolute() and path.parts
            and '..' not in path.parts and '\\' not in relative,
            'UNSAFE_WORKSPACE_PATH', 'Only a path inside the selected workspace is allowed.')
    current = root
    for part in path.parts:
        current /= part
        require(not current.is_symlink(), 'UNSAFE_WORKSPACE_PATH', 'Symlinked workspace members are not supported.')
    require(current.resolve() == current and (current == root or root in current.parents),
            'UNSAFE_WORKSPACE_PATH', 'The path must remain inside the selected workspace.')
    return current


def read(path, limit=1024*1024):
    require(path.is_file() and not path.is_symlink(), 'SOURCE_UNAVAILABLE', 'A required local source is unavailable.')
    before = path.stat()
    require(before.st_size <= limit, 'SOURCE_TOO_LARGE', 'A local source exceeds its supported read size.')
    raw = path.read_bytes(); after = path.stat()
    require((before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns) ==
            (after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns),
            'SOURCE_CHANGED_DURING_READ', 'A local source changed while it was read.')
    return raw


def parse(raw):
    def unique(pairs):
        result={}
        for key,value in pairs:
            require(key not in result, 'INVALID_JSON', 'Duplicate JSON keys are not supported.')
            result[key]=value
        return result
    return json.loads(raw, object_pairs_hook=unique,
        parse_constant=lambda _: (_ for _ in ()).throw(Refusal('INVALID_JSON','Finite JSON is required.')))


def pointer(value, path):
    require(isinstance(path,str) and path.startswith('/') and len(path)<=512,
            'INVALID_IDENTITY_POINTER','An exact JSON pointer to the saved identity field is required.')
    for part in path[1:].split('/'):
        part=part.replace('~1','/').replace('~0','~')
        value=value[int(part)] if isinstance(value,list) and part.isdigit() else value[part]
    return value


def bundle():
    raw=read(BUNDLE/'portable-bundle.json',65536); value=parse(raw)
    require(value.get('schema')=='caiman.job-control-bundle.v1' and value.get('version')==VERSION,
            'BUNDLE_INVALID','The paired job-control bundle is required.')
    for name,expected in value['files'].items():
        require(Path(name).name==name and sha(read(BUNDLE/name))==expected,
                'BUNDLE_CHANGED','A reviewed job-control file has changed.')
    return value,sha(raw)


def selected_workspace(project):
    marker=parse(read(member(project,'.caiman/workspace-id.json'),32768))
    saved=parse(read(member(project,'.caiman/active-guidance.json'),32768))
    require(saved.get('schema')=='caiman.active-guidance.v1' and saved.get('workspace_id')==marker.get('id'),
            'WORKSPACE_BINDING_INVALID','The saved guide must match this selected business workspace.')
    ref=saved['receipt']; rel=ref['path']
    require(rel.startswith('.caiman/kit-installations/') and len(rel.split('/'))==3,
            'GUIDANCE_RECEIPT_INVALID','A workspace-local installation receipt is required.')
    raw=read(member(project,rel))
    require(sha(raw)==ref['sha256'], 'GUIDANCE_RECEIPT_CHANGED','The saved guide installation receipt changed.')
    receipt=parse(raw)
    require(receipt.get('status')=='COMPLETE_ARCHIVE_INSTALLED' and receipt.get('workspace_id')==marker['id']
            and receipt.get('tier')==saved.get('tier') and receipt.get('guidance_relative')==saved.get('guidance_relative'),
            'GUIDANCE_RECEIPT_INVALID','The installed guide is not bound to this workspace and tier.')
    guide_rel=saved['guidance_relative']
    require(guide_rel=='.' or (guide_rel.startswith('.caiman/kit-versions/') and len(guide_rel.split('/'))==3),
            'GUIDANCE_PATH_INVALID','The guide must be the selected root or its verified companion.')
    guide=project if guide_rel=='.' else member(project,guide_rel)
    tier=saved['tier']; filename='GUIDED_SETUP.py' if tier=='vip' else 'GLS_GUIDED_SETUP.py' if tier=='gls-plus' else None
    require(filename is not None and sha(read(member(guide,filename)))==receipt['files'].get(filename),
            'GUIDANCE_CHANGED','The current guide differs from its installed version.')
    ent_raw=read(member(guide,'ENTITLEMENTS.json'),32768); ent=parse(ent_raw)
    require(sha(ent_raw)==receipt['files'].get('ENTITLEMENTS.json') and ent.get('brand_limit')==1
            and ent.get('plan_tier')==('vip' if tier=='vip' else 'gls_plus'),
            'TIER_BINDING_INVALID','The installed kit must retain its one-brand tier boundary.')
    return {'workspace_id':marker['id'],'tier':tier,'guide_relative':guide_rel,
            'entitlement_relative':str((guide/'ENTITLEMENTS.json').relative_to(project)),
            'entitlement_sha256':sha(ent_raw),'live_entitlement_verified':False}


def verify_fields(project, fields, initial=False):
    require(isinstance(fields,dict) and {'brand_slug','marketplace_id'} <= set(fields)
            and set(fields) <= {'brand_slug','marketplace_id','seller_id','ads_profile_id'},
            'IDENTITY_FIELDS_NEEDED','Use exact saved brand and marketplace fields; account IDs remain separate when available.')
    values={}; sources={}
    for name,field in fields.items():
        require(set(field)=={'value','evidence','pointer'} and isinstance(field['value'],str)
                and 0<len(field['value'])<=256, 'IDENTITY_FIELDS_INVALID','Identity fields must be bounded saved strings.')
        ref=field['evidence']; path=member(project,ref['path'])
        require(set(ref)=={'path','sha256'} and isinstance(ref['sha256'],str)
                and re.fullmatch('[a-f0-9]{64}',ref['sha256']),
                'IDENTITY_EVIDENCE_INVALID','Identity evidence must contain only its local path and digest.')
        if ref['path'] not in sources:sources[ref['path']]=read(path)
        raw=sources[ref['path']]
        if initial:
            require(sha(raw)==ref['sha256'],'IDENTITY_SOURCE_CHANGED','The setup source must match its independently supplied digest.')
        # Unrelated config edits may change full bytes; the exact selected identity
        # projection must still match. Initial bytes remain in the install receipt.
        require(pointer(parse(raw),field['pointer'])==field['value'],
                'IDENTITY_CHANGED','The saved business/account identity no longer matches the installed binding.')
        values[name]=field['value']
    require(re.fullmatch('[a-z0-9][a-z0-9-]{0,127}',values['brand_slug'])
            and re.fullmatch('[A-Za-z0-9_-]{1,32}',values['marketplace_id'])
            and all(not value.startswith('REPLACE_') for value in values.values()),
            'IDENTITY_FIELDS_INVALID','Use real connector identifiers, not a display label or template placeholder.')
    return values


def load_binding(project, bundle_sha, require_install_receipt=True):
    raw=read(member(project,'.caiman/job-control/binding.json'),65536); b=parse(raw)
    require(b.get('schema')=='caiman.job-control-binding.v1' and b.get('bundle_sha256')==bundle_sha,
            'PAIRED_RUNTIME_MISMATCH','The plugin and installed kit need the same reviewed job-control bundle.')
    if require_install_receipt:
        receipt=parse(read(member(project,'.caiman/job-control/install-'+sha(raw)+'.json'),65536))
        require(receipt.get('schema')=='caiman.job-controls-installation.v1'
                and receipt.get('binding_sha256')==sha(raw) and receipt.get('bundle_sha256')==bundle_sha
                and receipt.get('workspace_id')==b.get('workspace_id'),
                'BINDING_INSTALLATION_MISMATCH','The binding must match its exact installation record.')
    marker=parse(read(member(project,'.caiman/workspace-id.json'),32768))
    require(marker.get('id')==b.get('workspace_id'),'WORKSPACE_MISMATCH','This binding belongs to another business workspace.')
    entitlement_raw=read(member(project,b['entitlement_relative']),32768)
    require(sha(entitlement_raw)==b['entitlement_sha256'],
            'TIER_CHANGED','The installed tier changed; verify the selected kit before continuing.')
    entitlement=parse(entitlement_raw)
    require(b['tier'] in ('vip','gls-plus') and entitlement.get('brand_limit')==1
            and entitlement.get('plan_tier')==('vip' if b['tier']=='vip' else 'gls_plus'),
            'TIER_BINDING_INVALID','The binding cannot change the installed kit tier.')
    current=selected_workspace(project)
    require(all(b.get(key)==value for key,value in current.items()),
            'GUIDANCE_BINDING_CHANGED','Verify and reenroll the selected compatible guide before continuing this job.')
    values=verify_fields(project,b['fields'])
    require(b['scope']=={k:values[k] for k in ('brand_slug','marketplace_id')},
            'IDENTITY_CHANGED','The declared scope no longer matches its saved evidence.')
    return b,sha(raw)


def install(project, plan_path, expected_plan_sha):
    require(sys.platform in ('darwin','linux'),'HOST_UNSUPPORTED','Automatic hook enrollment is currently supported on macOS/Linux hosts only.')
    package,package_sha=bundle(); selection=selected_workspace(project)
    plan_raw=read(plan_path,65536)
    require(sha(plan_raw)==expected_plan_sha,'PLAN_CHANGED','The exact setup plan digest is required.')
    plan=parse(plan_raw)
    require(set(plan)=={'schema','tier','connector','fields'} and plan['schema']=='caiman.job-control-setup.v1'
            and plan['tier']==selection['tier'], 'SETUP_SCOPE_INVALID','The setup plan must retain the selected installed tier.')
    connector=plan['connector']
    require(set(connector)=={'source_key','tool_prefixes'} and isinstance(connector['source_key'],str)
            and 0<len(connector['source_key'])<=100 and isinstance(connector['tool_prefixes'],list)
            and 0<len(connector['tool_prefixes'])<=8 and len(set(connector['tool_prefixes']))==len(connector['tool_prefixes'])
            and all(isinstance(p,str) and re.fullmatch(r'mcp__[A-Za-z0-9][A-Za-z0-9_-]{0,127}__',p) for p in connector['tool_prefixes']),
            'SOURCE_SELECTION_NEEDED','Use the already selected connector and its exact exposed tool prefixes.')
    values=verify_fields(project,plan['fields'],initial=True)
    b={'schema':'caiman.job-control-binding.v1','version':VERSION,'bundle_sha256':package_sha,
       **selection,'connector':connector,'fields':plan['fields'],
       'scope':{k:values[k] for k in ('brand_slug','marketplace_id')},
       'account_identity':{k:values.get(k) for k in ('seller_id','ads_profile_id')},
       'authority':'Declared identity restriction only; host permission, live entitlement and exact business approval remain separate.'}
    directory=member(project,'.caiman/job-control'); directory.mkdir(mode=0o700,parents=True,exist_ok=True)
    current=directory/'binding.json'; prior=read(current,65536) if current.exists() else None
    if prior:
        old=parse(prior)
        for key in ('workspace_id','tier','connector','scope','account_identity'):
            require(old.get(key)==b.get(key),'REBIND_REQUIRES_SEPARATE_SCOPE','An upgrade cannot change the selected business, account, source or tier.')
    release=directory/'runtime'/VERSION; release.mkdir(parents=True,exist_ok=True)
    for name in list(package['files'])+['portable-bundle.json']:
        dest=member(release,name); raw=read(BUNDLE/name)
        require(not dest.exists() or read(dest)==raw,'EXISTING_RUNTIME_CHANGED','An existing runtime differs; preserve it for review.')
        if not dest.exists():
            with dest.open('xb') as handle:handle.write(raw)
    new=(json.dumps(b,indent=2)+'\n').encode()
    if prior and prior!=new:
        backup=directory/('binding-before-'+sha(prior)+'.json')
        if not backup.exists():backup.write_bytes(prior)
    temp=directory/('binding-'+sha(new)+'.stage')
    if not temp.exists():temp.write_bytes(new)
    require((read(current,65536) if current.exists() else None)==prior,'BINDING_CHANGED','The binding changed during installation.')
    os.replace(temp,current); os.chmod(current,0o600)
    require(read(current)==new,'INSTALL_READBACK_FAILED','The installed binding did not read back exactly.')
    load_binding(project,package_sha,require_install_receipt=False)
    receipt={'schema':'caiman.job-controls-installation.v1','status':'FILES_INSTALLED_HOST_HOOK_UNVERIFIED',
             'version':VERSION,'workspace_id':selection['workspace_id'],'tier':selection['tier'],
             'binding_sha256':sha(new),'bundle_sha256':package_sha,'source_plan_sha256':sha(plan_raw),
             'prior_binding_sha256':sha(prior) if prior else None,'core_plugin_required':'0.2.18 or compatible',
             'account_actions':False,'credential_changes':False,'schedule_changes':False,'host_enforcement_verified':False}
    receipt_path=directory/('install-'+sha(new)+'.json')
    if not receipt_path.exists():receipt_path.write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt


def rollback(project, receipt_path, receipt_sha):
    raw=read(receipt_path,65536)
    require(sha(raw)==receipt_sha,'RECEIPT_CHANGED','The exact installation receipt digest is required.')
    receipt=parse(raw);marker=parse(read(member(project,'.caiman/workspace-id.json'),32768))
    require(receipt.get('schema')=='caiman.job-controls-installation.v1'
            and receipt.get('workspace_id')==marker.get('id'),
            'ROLLBACK_SCOPE_MISMATCH','This receipt does not belong to the selected business workspace.')
    directory=member(project,'.caiman/job-control');current=directory/'binding.json'
    prior_sha=receipt.get('prior_binding_sha256');installed_sha=receipt['binding_sha256']
    retired=directory/('binding-retired-'+installed_sha+'.json')
    if not current.exists():
        require(prior_sha is None and retired.is_file() and sha(read(retired))==installed_sha,
                'ROLLBACK_STATE_CHANGED','The installed binding is absent without its matching retirement receipt.')
        return {'status':'ALREADY_ROLLED_BACK','account_actions':False,'history_preserved':True}
    current_raw=read(current,65536);current_sha=sha(current_raw)
    if prior_sha and current_sha==prior_sha:
        return {'status':'ALREADY_ROLLED_BACK','account_actions':False,'history_preserved':True}
    require(current_sha==installed_sha,'ROLLBACK_STATE_CHANGED','A later or edited binding cannot be overwritten by this rollback.')
    if prior_sha:
        old=read(member(directory,'binding-before-'+prior_sha+'.json'),65536)
        require(sha(old)==prior_sha,'ROLLBACK_PREDECESSOR_CHANGED','The preserved predecessor does not match.')
        if not retired.exists():retired.write_bytes(current_raw)
        stage=directory/('rollback-'+prior_sha+'.stage');stage.write_bytes(old)
        require(sha(read(current))==installed_sha,'ROLLBACK_STATE_CHANGED','The binding changed during rollback.')
        os.replace(stage,current);os.chmod(current,0o600)
        require(sha(read(current))==prior_sha,'ROLLBACK_READBACK_FAILED','The prior binding did not read back.')
    else:
        require(not retired.exists() or sha(read(retired))==installed_sha,'ROLLBACK_STATE_CHANGED','The retirement path differs.')
        os.replace(current,retired)
    result={'schema':'caiman.job-controls-rollback.v1','status':'LOCAL_BINDING_ROLLED_BACK',
            'workspace_id':marker['id'],'installation_receipt_sha256':receipt_sha,
            'prior_binding_sha256':prior_sha,'history_preserved':True,'runtime_files_preserved':True,
            'account_actions':False,'paired_plugin_rollback':'Restore its matching plugin version separately when needed.'}
    out=directory/('rollback-'+receipt_sha+'.json')
    if not out.exists():out.write_text(json.dumps(result,indent=2)+'\n')
    return result


def allocate_budget(project, plan_path, expected_plan_sha):
    _package,package_sha=bundle();b,_bsha=load_binding(project,package_sha)
    raw=read(plan_path,65536)
    require(sha(raw)==expected_plan_sha,'PLAN_CHANGED','The exact finite allocation plan is required.')
    plan=parse(raw)
    require(set(plan)=={'schema','workspace_id','job_key','limits','reason'}
            and plan['schema']=='caiman.job-budget-allocation.v1' and plan['workspace_id']==b['workspace_id'],
            'BUDGET_SCOPE_MISMATCH','Budget allocation must name this exact business workspace.')
    ledger=Ledger(member(project,'.caiman/job-control/ledger.sqlite'))
    try:
        require(ledger.inspect(plan['job_key'])['room']==b['workspace_id'],
                'BUDGET_SCOPE_MISMATCH','The job belongs to another workspace.')
        return ledger.amend_budget(plan['job_key'],plan['limits'],plan['reason'],
            {'plan_sha256':sha(raw),'basis':'EXPLICIT_LOCAL_COORDINATOR_ALLOCATION_NOT_BUSINESS_APPROVAL'})
    finally:ledger.close()


def identity_sha(b):
    # A guide move or evidence-path refresh is provenance, not a different account.
    return digest({k:b[k] for k in ('workspace_id','tier','connector','scope','account_identity')})


def select_job(project, plan_path, expected_plan_sha):
    _package,package_sha=bundle();b,_bsha=load_binding(project,package_sha)
    raw=read(plan_path,65536)
    require(sha(raw)==expected_plan_sha,'PLAN_CHANGED','The exact job-selection plan is required.')
    plan=parse(raw)
    require(set(plan)=={'schema','workspace_id','session_id','prompt_id','mode','job_key','reason'}
            and plan['schema']=='caiman.job-selection.v1' and plan['workspace_id']==b['workspace_id']
            and isinstance(plan['reason'],str) and 1<=len(plan['reason'])<=1000,
            'JOB_SELECTION_MISMATCH','Select the exact current prompt and recorded job in this workspace.')
    directory=member(project,'.caiman/job-control')
    ledger=Ledger(member(directory,'ledger.sqlite'));ledger.close()
    contexts=PortableContext(member(directory,'host-context.sqlite'),b['workspace_id'],identity_sha(b))
    try:
        return contexts.select_job(plan,plan['mode'],plan['job_key'],digest(policy_for(b)),directory/'ledger.sqlite',
            {'plan_sha256':sha(raw),'reason':plan['reason'],'basis':'EXPLICIT_COORDINATOR_SELECTION_OF_RECORDED_HOST_PROMPT'})
    finally:contexts.close()


def policy_for(b):
    template=parse(read(BUNDLE/'portable-policy.json',65536))
    return {**template,'tool_prefixes':b['connector']['tool_prefixes'],
            'scopes':[b['scope']],'room_scopes':{b['workspace_id']:[b['scope']]},
            'identity_binding':identity_sha(b)}


def hook(event, project):
    marker_path=member(project,'.caiman/workspace-id.json')
    if not marker_path.is_file():return {}
    package,package_sha=bundle()
    marker=parse(read(marker_path,32768)); workspace=marker.get('id')
    require(isinstance(workspace,str) and 0<len(workspace)<=200,'WORKSPACE_BINDING_INVALID','A selected installed business workspace is required.')
    directory=member(project,'.caiman/job-control');directory.mkdir(mode=0o700,parents=True,exist_ok=True)
    state_path=member(directory,'host-context.sqlite')
    require(not state_path.is_symlink(),'UNSAFE_WORKSPACE_PATH','Host context must be local to this workspace.')
    contexts=PortableContext(state_path,workspace,'not-enrolled')
    os.chmod(state_path,0o600)
    ledger=None
    try:
        kind=event.get('hook_event_name')
        if kind=='UserPromptSubmit':
            record=contexts.register_prompt(event)
            return {'hookSpecificOutput':{'hookEventName':kind,'additionalContext':
                'Job controls retain selected job '+(record['job_key'] or 'UNSELECTED: choose a recorded original job before business tools')+'. Follow-ups reuse its reports and counters. '
                'For a genuinely different new request, use the recorded job-selection process before business tools; '
                'never create a replacement to evade a pending result or budget.'}}
        if kind=='SubagentStart':contexts.register_agent(event);return {}
        if kind=='Stop':contexts.stop(event);return {}
        if kind not in ('PreToolUse','PostToolUse','PostToolUseFailure'):return {}
        binding_path=member(directory,'binding.json')
        if not binding_path.exists():return {}
        b,bsha=load_binding(project,package_sha);contexts.binding_sha=identity_sha(b)
        name=event.get('tool_name','')
        is_selected=any(name.startswith(p) for p in b['connector']['tool_prefixes'])
        policy=policy_for(b)
        require(is_selected or not any(name.startswith(p) for p in policy['known_amazon_prefixes']),
                'SOURCE_SELECTION_MISMATCH','This request uses a different Amazon connector from the saved selection.')
        if not is_selected and name not in ('Agent','Task'):return {}
        if is_selected:
            short=next(name[len(p):] for p in b['connector']['tool_prefixes'] if name.startswith(p))
            if b['tier']=='gls-plus':
                require(short in policy['gls_tools'],'GLS_TIER_BOUNDARY','This kit retains connected Ads and manual Seller Central evidence; it does not gain connected SP-API tools.')
            inputs=event.get('tool_input',{})
            for aliases,field in ((('seller_id',),'seller_id'),(('ads_profile_id','profile_id'),'ads_profile_id')):
                for key in aliases:
                    if key in inputs:
                        require(b['account_identity'].get(field) is not None and inputs[key]==b['account_identity'][field],
                                'ACCOUNT_SCOPE_MISMATCH','The requested account differs from the saved business binding.')
        try:
            ctx=contexts.resolve(event)
        except Refusal as error:
            if kind!='PreToolUse' or error.result['code']!='HOST_PROMPT_NOT_ACTIVE':raise
            contexts.bind_initial_turn(event)
            ctx=contexts.resolve(event)
        def check_binding():
            current,current_sha=load_binding(project,package_sha)
            require(current_sha==bsha,'BINDING_CHANGED','The business binding changed during the job.')
        validate=contexts.revalidator(event,check_binding)
        ledger=Ledger(directory/'ledger.sqlite')
        if kind=='PreToolUse':
            admitted=ledger.enter(ctx,policy,validate)
            if not admitted['allowed']:return denied(admitted)
            cl=classify(policy,name,event.get('tool_input',{}));cl['embedded_worker']=bool(event.get('agent_id'))
            if cl['kind']=='report_poll' and cl.get('scope') is None:cl['scope']=ledger.report_scope(ctx,cl['report_id'])
            result=ledger.admit(ctx,policy,name,event.get('tool_use_id'),event.get('tool_input',{}),cl,validate)
            outcome={} if result['allowed'] else denied(result)
        else:
            result=ledger.observe(ctx,event.get('tool_use_id'),event.get('tool_response') if kind=='PostToolUse' else {'failure':True},kind=='PostToolUseFailure',validate)
            outcome={}
        log={'at':time.time(),'event':kind,'session_id':event.get('session_id'),'prompt_id':event.get('prompt_id'),
             'code':result.get('code',result.get('state')),'operation':result.get('operation'),
             'source_basis':ctx['source_basis'],
             'bundle_sha256':package_sha,'provenance':'LOCAL_CALLBACK_RECORD_NOT_INDEPENDENT_HOST_ATTESTATION'}
        with (directory/'callback-observations.jsonl').open('a') as output:output.write(canonical(log)+'\n')
        return outcome
    finally:
        if ledger:ledger.close()
        contexts.close()


def denied(result):
    return {'hookSpecificOutput':{'hookEventName':'PreToolUse','permissionDecision':'deny',
                                 'permissionDecisionReason':canonical(result)}}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['install','status','budget','select-job','rollback','hook'])
    p.add_argument('--project-root');p.add_argument('--plan');p.add_argument('--plan-sha256')
    p.add_argument('--event',choices=['UserPromptSubmit','SubagentStart','PreToolUse','PostToolUse','PostToolUseFailure','Stop'])
    a=p.parse_args();event={'hook_event_name':a.event} if a.event else {}
    try:
        if a.action=='hook':
            if hasattr(signal,'setitimer'):
                signal.signal(signal.SIGALRM,lambda *_: (_ for _ in ()).throw(Refusal('HOOK_DEADLINE','The local job-control deadline was reached.')))
                signal.setitimer(signal.ITIMER_REAL,3.5)
            raw=sys.stdin.buffer.read(18*1024*1024+1)
            require(len(raw)<=18*1024*1024,'INPUT_TOO_LARGE','The hook input exceeds its bounded size.')
            parsed=parse(raw)
            require(isinstance(parsed,dict) and a.event and parsed.get('hook_event_name')==a.event,
                    'HOOK_EVENT_MISMATCH','The hook must match its configured host event.')
            event=parsed
            selected=os.environ.get('CLAUDE_PROJECT_DIR') or event.get('cwd')
            require(isinstance(selected,str) and Path(selected).is_absolute(),'WORKSPACE_REQUIRED','The host must identify the selected project.')
            project=Path(selected).resolve()
            cwd=Path(event['cwd']).resolve()
            require(cwd==project or project in cwd.parents,'WORKSPACE_MISMATCH','The hook belongs to another project.')
            result=hook(event,project)
        else:
            project=Path(a.project_root).resolve()
            if a.action=='install':result=install(project,Path(a.plan).resolve(),a.plan_sha256)
            elif a.action=='budget':result=allocate_budget(project,Path(a.plan).resolve(),a.plan_sha256)
            elif a.action=='select-job':result=select_job(project,Path(a.plan).resolve(),a.plan_sha256)
            elif a.action=='rollback':result=rollback(project,Path(a.plan).resolve(),a.plan_sha256)
            else:
                package,package_sha=bundle();b,bsha=load_binding(project,package_sha)
                result={'status':'FILES_AND_IDENTITY_PROJECTION_VERIFIED','version':VERSION,'workspace_id':b['workspace_id'],
                        'tier':b['tier'],'binding_sha256':bsha,'live_entitlement_verified':False,
                        'host_enforcement':'REQUIRES_INDEPENDENT_NATIVE_CALLBACK_EVIDENCE'}
                directory=member(project,'.caiman/job-control')
                if (directory/'host-context.sqlite').exists():
                    contexts=PortableContext(directory/'host-context.sqlite',b['workspace_id'],identity_sha(b))
                    try:result['recent_host_prompts']=contexts.status()
                    finally:contexts.close()
                if (directory/'ledger.sqlite').exists():
                    ledger=Ledger(directory/'ledger.sqlite')
                    try:result['jobs']=[ledger.inspect(r[0]) for r in ledger.db.execute('SELECT job_key FROM jobs ORDER BY created DESC LIMIT 20').fetchall()]
                    finally:ledger.close()
        print(canonical(result));return 0
    except Exception as error:
        r=error.result if isinstance(error,Refusal) else {'allowed':False,'code':'JOB_CONTROL_UNAVAILABLE','detail':'The local job controls could not verify this request.'}
        if a.action=='hook':
            if event.get('hook_event_name')=='PreToolUse':print(canonical(denied(r)));return 0
            if event.get('hook_event_name') in ('PostToolUse','PostToolUseFailure'):
                print(canonical({'hookSpecificOutput':{'hookEventName':event['hook_event_name'],
                    'additionalContext':'JOB_OBSERVATION_PENDING: preserve the native result and do not repeat a report dispatch.'}}));return 0
            # Context metadata failure must not erase a user's prompt. Business
            # tools will reject missing continuity once the workspace is enrolled.
            print('{}');return 0
        print(canonical(r));return 2
    finally:
        if hasattr(signal,'setitimer'):signal.setitimer(signal.ITIMER_REAL,0)


if __name__=='__main__':raise SystemExit(main())
