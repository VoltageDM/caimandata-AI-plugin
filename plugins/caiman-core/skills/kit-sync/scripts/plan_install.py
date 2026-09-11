#!/usr/bin/env python3
"""Bounded local kit intake and complete copy plan. No transfer or installation."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import zipfile
sys.dont_write_bytecode = True
import verify_kit as v

MAX_ARCHIVE_BYTES = 128 * 1024 * 1024
MAX_EXPANDED_BYTES = 256 * 1024 * 1024
MAX_MEMBER_BYTES = 64 * 1024 * 1024
MAX_CONTENT_BLOCKS = 16
MAX_PLAN_OUTPUT_BYTES = 4096

class PlanError(v.VerificationError):
    pass

def source_path(raw):
    path = Path(raw).expanduser().absolute()
    for part in (path, *path.parents):
        if v.linklike(part):
            raise PlanError('source or staging path has a symlink/reparse ancestor')
    v.regular(path)
    return path

def decode_json(text):
    try:
        return json.loads(text, object_pairs_hook=v.pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(PlanError('non-finite JSON')))
    except (ValueError, UnicodeError) as exc:
        raise PlanError('invalid strict JSON in saved response') from exc

def unwrap(raw):
    """Only the demonstrated SDK text-content array and direct local format."""
    if isinstance(raw, dict):
        return raw, 'direct-json'
    if not isinstance(raw, list) or not 1 <= len(raw) <= MAX_CONTENT_BLOCKS:
        raise PlanError('unsupported or oversized SDK content wrapper')
    found = []
    for block in raw:
        if not isinstance(block, dict) or block.get('type') != 'text' or not isinstance(block.get('text'), str):
            raise PlanError('unsupported SDK content block; no bulk/binary decoding')
        text = block['text'].strip()
        if not text or text[:1] not in ('{', '['):
            continue  # SDK explanatory prose is neither metadata nor authorization.
        value = decode_json(text)
        if not isinstance(value, dict):
            raise PlanError('unexpected JSON payload in SDK content wrapper')
        found.append(value)
    if len(found) != 1:
        raise PlanError('saved response must contain exactly one unambiguous manifest object')
    return found[0], 'sdk-text-content-array'

def normalized_manifest(raw):
    if isinstance(raw,dict) and raw.get('schema')==v.SCHEMA:
        v.manifest_set(raw)
        return raw,{'source_kind':'documented-local-format','reported_superseded_files':0}
    if not isinstance(raw,dict) or set(raw)!={'retrieved_at','source','note','kits'}:
        raise PlanError('unsupported manifest fields; retain the original response for support mapping')
    if any(not isinstance(raw[key],str) or not raw[key].strip() or len(raw[key])>2048 for key in ('retrieved_at','source','note')):
        raise PlanError('invalid or oversized agent-saved retrieval metadata')
    kits=raw['kits']
    if not isinstance(kits,list) or not 1<=len(kits)<=2:
        raise PlanError('one or two explicitly reported kits required; zero is not installation permission')
    normalized={'schema':v.SCHEMA,'kits':[]};seen=set();total=0;superseded=0;reported=[]
    for item in kits:
        if not isinstance(item,dict) or set(item)!={'kit','version','files','superseded_file_count'}:
            raise PlanError('unsupported agent-saved kit fields; no silent pagination or metadata dropping')
        if item['kit'] not in v.TIER_ORDER or item['kit'] in seen:
            raise PlanError('unknown or repeated reported tier')
        seen.add(item['kit']);files=item['files'];omitted=item['superseded_file_count']
        if type(omitted) is not int or not 0<=omitted<=v.MAX_FILES or not isinstance(files,list) or not 1<=len(files)<=v.MAX_FILES:
            raise PlanError('invalid bounded reported membership')
        total+=len(files);superseded+=omitted
        if total>v.MAX_FILES or superseded>v.MAX_FILES:
            raise PlanError('combined reported membership exceeds local bound')
        mapped={}
        for entry in files:
            if not isinstance(entry,dict) or set(entry)!={'path','sha256','size_bytes','is_binary'}:
                raise PlanError('unsupported file metadata; retain complete actual field shape')
            name=entry['path']
            if not isinstance(name,str) or name in mapped or type(entry['size_bytes']) is not int or not 0<=entry['size_bytes']<=MAX_EXPANDED_BYTES or type(entry['is_binary']) is not bool:
                raise PlanError('duplicate path or invalid size/binary metadata')
            mapped[name]={'sha256':entry['sha256'],'size_bytes':entry['size_bytes'],'is_binary':entry['is_binary']}
        record={'kit':item['kit'],'version':item['version'],'files':mapped}
        v.manifest_set({'schema':v.SCHEMA,'kits':[record]})
        normalized['kits'].append(record)
        reported.append({'kit':item['kit'],'version':item['version'],'reported_files':len(files),'reported_superseded_files':omitted})
    return normalized,{'source_kind':'agent-saved-observed-manifest','reported_kits':reported,
        'reported_file_rows':total,'reported_superseded_files':superseded,
        'source_authenticity':'Retrieval metadata and signed/authoritative wording are agent reports, not cryptographic proof.',
        'membership_completeness':'FILTERED_OR_UNATTESTED' if superseded else 'AGENT_REPORTED_ONLY'}

def save_normalized(path_raw, data, project):
    path = Path(path_raw).expanduser().absolute()
    try:
        path.relative_to(project)
    except ValueError:
        pass
    else:
        raise PlanError('normalized manifest belongs in separate local staging, not the client project')
    for ancestor in (path, *path.parents):
        if v.linklike(ancestor):
            raise PlanError('staging path has a symlink/reparse ancestor')
    if not path.parent.is_dir():
        raise PlanError('select an existing local staging directory')
    encoded = (json.dumps(data, sort_keys=True, separators=(',', ':'), ensure_ascii=False)+'\n').encode()
    if len(encoded) > v.MAX_JSON_BYTES:
        raise PlanError('normalized manifest exceeds bounded size')
    if path.exists():
        v.regular(path)
        if path.read_bytes() != encoded:
            raise PlanError('staging output already exists with different bytes')
    else:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0)
        with os.fdopen(os.open(path, flags, 0o600), 'wb') as handle:
            handle.write(encoded)
    return path

def runtime_present(root):
    for base in ('Operating Framework/VIP Machine', 'VIP Machine'):
        for name in ('config/brand.json','state','runs','ledger','scorecard'):
            path = root/base/name
            if path.exists() or v.linklike(path):
                return True
    return False

def examples(items):
    return [{'path': x['path'][:160], 'path_shortened':len(x['path']) > 160, 'state':x['state']} for x in items[:3]]

def base_result(root):
    return {'schema':'caiman.kit-install-plan.v1','project_root':str(root),
        'project_changed':False,'transfer_performed':False,'engine_executed':False,
        'schedules_installed':False,'live_entitlement_verified':False,
        'source_code_execution_authorized':False,'selective_copy_allowed':False}

def plan_manifest(root_raw, source_raw, normalized_out, selected_tier=None):
    root = v.root_path(root_raw)
    source = source_path(source_raw)
    raw, wrapper = unwrap(v.strict_json(source))
    normalized, intake = normalized_manifest(raw)
    omitted_for_selected=intake['reported_superseded_files']
    if selected_tier is not None:
        if selected_tier not in v.TIER_ORDER:
            raise PlanError('unknown requested tier')
        selected=[item for item in normalized['kits'] if item['kit']==selected_tier]
        if len(selected)!=1:
            raise PlanError('requested tier is absent from the supplied kit report; do not infer entitlement')
        reported=intake.get('reported_kits',[])
        selected_report=next((item for item in reported if item['kit']==selected_tier),None)
        omitted_for_selected=selected_report['reported_superseded_files'] if selected_report else 0
        intake.update(requested_tier=selected_tier,other_kit_rows_not_selected=sum(len(item['files']) for item in normalized['kits'] if item['kit']!=selected_tier),selected_reported_superseded_files=omitted_for_selected,selection='Explicit requested tier in supplied report; actual service authorization remains separate.')
        normalized={'schema':v.SCHEMA,'kits':selected}
    target = save_normalized(normalized_out, normalized, root)
    out = base_result(root)
    out.update(manifest_wrapper=wrapper,source_sha256=v.sha(source),
        normalized_manifest_path=str(target),normalized_manifest_sha256=v.sha(target),intake=intake)
    try:
        checked = v.inspect(root, target, limit=3)
    except v.VerificationError as exc:
        out.update(status='STOP_MANIFEST_BOUNDARY',reason=str(exc)[:500],complete_copy_verified=False,
            next_action='Support must resolve the complete selected-tier manifest; do not drop conflicting paths or fetch a subset.')
        return out
    status = checked['status'] if checked['coverage_complete'] else 'BULK_TRANSFER_UNAVAILABLE'
    if runtime_present(root) and not checked['coverage_complete']:
        status = 'EXISTING_RUNTIME_UPDATER_REQUIRED'
    if omitted_for_selected:
        status='MANIFEST_COMPLETENESS_UNVERIFIED'
        out['completeness_issue']='The requested tier is an overlap-deduplicated projection; obtain its complete effective membership before any install/current claim.'
    out.update(status=status,kits=checked['kits'],expected_files=checked['expected_files'],counts=checked['counts'],
        complete_copy_verified=checked['coverage_complete'] and not omitted_for_selected,state_complete=checked['state_complete'],
        exceptions=examples(checked['exceptions']),
        exceptions_omitted=checked['exceptions_omitted']+max(0,len(checked['exceptions'])-3),
        transfer_route='Use an actually documented out-of-context transfer or approved local complete archive; never GetKitFile loops.',
        freshness='Supplied local response only; server freshness and authorization are not established by parsing.')
    return out

def archive_members(archive, archive_sha256, selected_tier, approved_release):
    if not v.HEX.fullmatch(archive_sha256):
        raise PlanError('supply the raw archive SHA-256 from the approved package receipt')
    if selected_tier not in v.TIER_ORDER or not approved_release or len(approved_release)>160:
        raise PlanError('supply the known selected tier and exact approved release')
    path = source_path(archive)
    if path.stat().st_size > MAX_ARCHIVE_BYTES:
        raise PlanError('archive exceeds bounded local intake size')
    if v.sha(path) != archive_sha256:
        raise PlanError('archive does not match the approved raw SHA-256')
    with zipfile.ZipFile(path) as z:
        infos=z.infolist()
        if not 1 <= len(infos) <= v.MAX_FILES:
            raise PlanError('archive member count exceeds bound')
        names={}; total=0
        for info in infos:
            name=info.filename[:-1] if info.is_dir() else info.filename
            v.portable(name)
            if name.casefold() in names:
                raise PlanError('duplicate or case-colliding archive member')
            names[name.casefold()]=name
            mode=info.external_attr >> 16
            kind=stat.S_IFMT(mode)
            if kind not in (0,stat.S_IFDIR if info.is_dir() else stat.S_IFREG):
                raise PlanError('archive contains a link or special member')
            if info.flag_bits & 1:
                raise PlanError('encrypted archive is unsupported')
            if info.file_size > MAX_MEMBER_BYTES:
                raise PlanError('archive member exceeds bounded size')
            total += info.file_size
            if total > MAX_EXPANDED_BYTES:
                raise PlanError('expanded archive exceeds bounded size')
        manifests=[i for i in infos if not i.is_dir() and i.filename.endswith('/RELEASE_MANIFEST.json')]
        if any(i.filename=='RELEASE_MANIFEST.json' and not i.is_dir() for i in infos):
            manifests += [i for i in infos if i.filename=='RELEASE_MANIFEST.json']
        if len(manifests)!=1:
            raise PlanError('archive must have one release manifest at its single package root')
        mi=manifests[0]
        prefix=mi.filename[:-len('RELEASE_MANIFEST.json')]
        if prefix and len(prefix.rstrip('/').split('/')) != 1:
            raise PlanError('unsupported nested package root')
        if mi.file_size > v.MAX_JSON_BYTES:
            raise PlanError('release manifest exceeds bound')
        release=decode_json(z.read(mi).decode('utf-8'))
        if not isinstance(release,dict) or release.get('schema')!='caiman_client_tier_release_manifest_v1' or release.get('artifact_type')!='client_full_kit':
            raise PlanError('unsupported complete client archive manifest')
        if {'gls_plus':'gls-plus'}.get(release.get('tier'),release.get('tier'))!=selected_tier or release.get('release')!=approved_release:
            raise PlanError('archive tier or release differs from the approved selection')
        expected={}
        for info in infos:
            if info.is_dir():
                if prefix and info.filename!=prefix and not info.filename.startswith(prefix):
                    raise PlanError('archive contains a directory outside its package root')
                continue
            if not info.filename.startswith(prefix):
                raise PlanError('archive contains a file outside its package root')
            relative=info.filename[len(prefix):]
            v.portable(relative)
            h=hashlib.sha256()
            with z.open(info) as stream:
                for chunk in iter(lambda:stream.read(1024*1024),b''):h.update(chunk)
            expected[relative]=h.hexdigest()
        expected=v.file_map(expected)
        tree=hashlib.sha256()
        for name in sorted(n for n in expected if n!='RELEASE_MANIFEST.json'):
            tree.update(name.encode('utf-8')+b'\0'+bytes.fromhex(expected[name]))
        if release.get('source_file_count_excluding_manifest')!=len(expected)-1 or release.get('source_tree_sha256')!=tree.hexdigest():
            raise PlanError('archive complete file count or release tree hash differs')
        return expected,release,prefix,total

def plan_archive(root_raw, archive, archive_sha256, selected_tier, approved_release):
    root=v.root_path(root_raw)
    expected,release,prefix,total=archive_members(archive,archive_sha256,selected_tier,approved_release)
    boundary=root/'ENTITLEMENTS.json'
    if boundary.exists() or v.linklike(boundary):
        local=v.strict_json(source_path(boundary));tier=local.get('plan_tier') if isinstance(local,dict) else None
        if {'gls_plus':'gls-plus'}.get(tier,tier)!=selected_tier:
            raise PlanError('existing project tier differs from selected package')
    counts={'unchanged':0,'missing':0,'conflicting_existing':0};exceptions=[]
    for name,digest in expected.items():
        path=v.confined(root,name)
        kind='missing' if not path.exists() else ('unchanged' if v.sha(path)==digest else 'conflicting_existing')
        counts[kind]+=1
        if kind!='unchanged':exceptions.append({'path':name,'state':kind})
    complete=counts['unchanged']==len(expected)
    if complete:status='COMPLETE_VERIFIED_COPY'
    elif runtime_present(root):status='EXISTING_RUNTIME_UPDATER_REQUIRED'
    elif counts['conflicting_existing']:status='EXISTING_FILES_REVIEW_REQUIRED'
    else:status='COMPLETE_ARCHIVE_COPY_PLAN_READY'
    out=base_result(root)
    out.update(status=status,archive_sha256=archive_sha256,release=release['release'],selected_tier=selected_tier,
        archive_root=prefix,archive_files=len(expected),uncompressed_bytes=total,counts=counts,
        complete_copy_verified=complete,installation_receipt_created=False,
        exceptions=examples(exceptions),exceptions_omitted=max(0,len(exceptions)-3),
        package_provenance='Caller-supplied approved package hash/release; approval and live subscription are not authenticated by this local helper.',
        next_action='Copy the entire verified package only within existing user authorization; then run this plan again. Preserve existing client work. Do not execute engine/setup/schedules from copy permission.')
    return out

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    m=sub.add_parser('manifest');m.add_argument('--root',required=True);m.add_argument('--source',required=True);m.add_argument('--normalized-out',required=True);m.add_argument('--selected-tier',choices=sorted(v.TIER_ORDER))
    a=sub.add_parser('archive');a.add_argument('--root',required=True);a.add_argument('--archive',required=True);a.add_argument('--archive-sha256',required=True);a.add_argument('--selected-tier',required=True,choices=sorted(v.TIER_ORDER));a.add_argument('--approved-release',required=True)
    args=p.parse_args(argv)
    try:
        out=plan_manifest(args.root,args.source,args.normalized_out,args.selected_tier) if args.command=='manifest' else plan_archive(args.root,args.archive,args.archive_sha256,args.selected_tier,args.approved_release)
    except (v.VerificationError,OSError,zipfile.BadZipFile,UnicodeError,RuntimeError) as exc:
        out={'schema':'caiman.kit-install-plan.v1','status':'STOP','reason':str(exc)[:500],
             'project_changed':False,'transfer_performed':False,'engine_executed':False,'schedules_installed':False}
    rendered=json.dumps(out,sort_keys=True,ensure_ascii=False)
    if len(rendered.encode('utf-8'))>MAX_PLAN_OUTPUT_BYTES:
        out={'schema':'caiman.kit-install-plan.v1','status':'STOP','reason':'plan metadata exceeds compact output bound; no current/copy-ready claim','project_changed':False,'transfer_performed':False,'engine_executed':False,'schedules_installed':False}
        rendered=json.dumps(out,sort_keys=True)
    print(rendered)
    return 0 if out['status'] in ('CURRENT','COMPLETE_STATE_UPDATE_REQUIRED','COMPLETE_VERIFIED_COPY','COMPLETE_ARCHIVE_COPY_PLAN_READY') else 2

if __name__=='__main__':raise SystemExit(main())
