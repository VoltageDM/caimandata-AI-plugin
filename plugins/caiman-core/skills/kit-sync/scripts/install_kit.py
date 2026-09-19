#!/usr/bin/env python3
"""Install a complete approved kit locally. No provider calls or runtime execution."""
from __future__ import annotations
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import uuid
import zipfile
sys.dont_write_bytecode = True
import plan_install as plan
import verify_kit as v


def stamp():
    return dt.datetime.now(dt.timezone.utc).isoformat().replace('+00:00', 'Z')


def safe_dir(root, relative):
    p = root
    for part in relative.split('/'):
        if part in ('', '.', '..') or any(c in part for c in ':\\'):
            raise plan.PlanError('unsafe installation metadata path')
        p = p / part
        if v.linklike(p) or p.exists() and not p.is_dir():
            raise plan.PlanError('installation metadata path is linked or conflicts')
        p.mkdir(exist_ok=True)
    return p


def exclusive(path, data):
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                           getattr(os, 'O_NOFOLLOW', 0), 0o600), 'wb') as f:
        f.write(data)


def encode(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False)+'\n').encode()


def acquire_lock(path):
    """Use a persistent OS-locked file; closing releases the lock without unlink."""
    if v.linklike(path): raise plan.PlanError('installation lock is linked')
    fd=os.open(path,os.O_RDWR|os.O_CREAT|getattr(os,'O_NOFOLLOW',0),0o600)
    try:
        v.regular(path)
        if os.name=='nt':
            import msvcrt
            if os.fstat(fd).st_size==0:os.write(fd,b' ')
            os.lseek(fd,0,os.SEEK_SET);msvcrt.locking(fd,msvcrt.LK_NBLCK,1)
        else:
            import fcntl
            fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        return fd
    except Exception:
        os.close(fd);raise


def workspace_id(meta):
    marker=meta/'workspace-id.json'
    if not marker.exists():
        try:exclusive(marker,encode({'schema':'caiman.workspace-id.v1','id':str(uuid.uuid4())}))
        except FileExistsError:pass
    record=v.strict_json(marker)
    if record.get('schema')!='caiman.workspace-id.v1':raise plan.PlanError('unknown workspace identity record')
    try:uuid.UUID(record['id'])
    except (ValueError,KeyError,TypeError):raise plan.PlanError('invalid workspace identity record')
    return record['id']


def verify_tree(root, expected):
    for name, digest in expected.items():
        p = v.confined(root, name)
        if not p.is_file() or v.sha(p) != digest:
            raise plan.PlanError('complete archive readback failed: '+name)



def current_guide_note(root, target, pointer, selected_tier, release, check_only=False):
    """Add a small current-guide entry without replacing any member-authored rules."""
    begin=b'<!-- CAIMAN_CURRENT_GUIDE_BEGIN -->'
    end=b'<!-- CAIMAN_CURRENT_GUIDE_END -->'
    block=begin+b'\nFor Caiman work, first read [CAIMAN_CURRENT.md](CAIMAN_CURRENT.md). It identifies the currently installed guide and its exact commands. Older kit versions and root helpers remain preserved history; do not choose them from remembered version names. Keep the member rules in this file.\n'+end+b'\n'
    meta=safe_dir(root,'.caiman/instruction-history')
    def replace_saved(path, raw):
        if v.linklike(path):raise plan.PlanError('instruction entry is linked')
        old=path.read_bytes() if path.exists() else None
        if old==raw:return
        if old is not None:
            backup=meta/(hashlib.sha256(old).hexdigest()+'.md')
            if backup.exists() and backup.read_bytes()!=old:raise plan.PlanError('instruction backup differs')
            if not backup.exists():exclusive(backup,old)
        fd,name=tempfile.mkstemp(prefix='current-guide-',dir=root)
        with os.fdopen(fd,'wb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
        if (path.read_bytes() if path.exists() else None)!=old:raise plan.PlanError('member instructions changed during merge; staged note retained')
        os.replace(name,path)
    rel=target.relative_to(root).as_posix() if target!=root else '.'
    note=('<!-- CAIMAN_GENERATED_CURRENT_GUIDE -->\n# Current Caiman guide\n\n'
          'Installed tier: '+selected_tier+'. Installed release: '+release+'. This is local installation evidence, not live account authorization.\n\n'
          'Read ['+rel+'/AGENT_START.md](<'+rel+'/AGENT_START.md>) before Caiman business work. Use that directory as the command root and this business folder as the data root. The receipt-bound selection is `.caiman/active-guidance.json`.\n\n'
          'For a dashboard refresh, run this current guide’s `REFRESH_OPERATING_VIEW.py --project-root <this business folder>` once. Present its exact returned HTML and source-bound `client_brief`; keep ACoS/TACoS, dates and estimate labels intact. Older dashboard files and prior chat summaries are history, not current selection.\n').encode()
    visible=root/'CAIMAN_CURRENT.md'
    if visible.exists() and not visible.read_bytes().startswith(b'<!-- CAIMAN_GENERATED_CURRENT_GUIDE -->'):raise plan.PlanError('CAIMAN_CURRENT.md contains member content; preserve it and select another explicit guide entry')
    merge_bytes=None
    if target!=root:
        entry=root/'CLAUDE.md'
        if v.linklike(entry):raise plan.PlanError('root instructions are linked')
        old=entry.read_bytes() if entry.exists() else b''
        if begin in old or end in old:
            if old.count(begin)!=1 or old.count(end)!=1:raise plan.PlanError('ambiguous current-guide block; preserve member instructions')
            start=old.index(begin);stop=old.index(end,start)+len(end)
            existing=old[start:stop].rstrip()+b'\n'
            if existing!=block:raise plan.PlanError('current-guide block was edited; preserve and reconcile it')
        else:merge_bytes=block+b'\n'+old
    if not check_only:
        replace_saved(visible,note)
        if merge_bytes is not None:replace_saved(entry,merge_bytes)
    return {'entry':'CAIMAN_CURRENT.md','sha256':hashlib.sha256(note).hexdigest(),'member_rule_policy':'Prior root instructions retained byte-for-byte after the managed entry; exact previous full files saved under .caiman/instruction-history.'}


ROOT_ENTRYPOINT_PREDECESSORS = {'vip': ['32cd9178775ce701b70ee7d2547f0bfabda410f8ad3eaedd70379acd6a6d3831', 'c744534bf629e3109f63864fdfe3174a93533c99fba0b784f8732f8d90e2d455', 'b79fa617c3ddef38865c1303af6ecd33e0bf4a45e3dddc6c210d3b757a4ff3bd', '00c8271c1526c2f2378eb68f112914b8249f76c88df531bf56a0927301edc10e', '37a8cd5496840802046e96c7570ea8c84fb37f2b7c907fc1f585b7db1c42d75f', '33739f2b386d1e8a3f98cd679ca9b23b8fafdeffc46377056e4e6d5354bb71fa'], 'gls-plus': ['dbd3e0f6208d27f2cada9b43a05ce6a64f2e60f020fefef41df11510b877c1d0', 'a770a31443b1ecaa0ab6f02ffe4b3505022eb469f6de17b8273962dc5434b807', '459ff73a8e0fb297508a70005708b5d66b2a32f8710d8bf5c72368b3a6e40ace', 'ab42e42279b543a9a542f47531523752a34f954ed6bd9e1f782627fb9505959d']}
ROOT_ENTRYPOINT_SOURCE = '#!/usr/bin/env python3\n"""Caiman current-guide entrypoint. Original package entrypoint is preserved in backups."""\nimport hashlib,json,runpy,sys\nfrom pathlib import Path\nsys.dont_write_bytecode=True\nTIER=__TIER__\nENTRY=__ENTRY__\ndef _file(root,relative):\n if not isinstance(relative,str) or relative.startswith(\'/\') or any(x in (\'\',\'.\',\'..\') for x in relative.split(\'/\')) or \':\' in relative or \'\\\\\' in relative:raise ValueError(\'Invalid current-guide relative path\')\n p=root\n for part in relative.split(\'/\'):\n  p=p/part\n  if p.is_symlink() or getattr(p,\'is_junction\',lambda:False)():raise ValueError(\'Linked current-guide path\')\n if not p.is_file():raise ValueError(\'Current-guide file is missing: \'+relative)\n return p\ndef _json(p):\n if p.stat().st_size>2*1024*1024:raise ValueError(\'Current-guide metadata exceeds bound\')\n def pairs(items):\n  d={}\n  for k,v in items:\n   if k in d:raise ValueError(\'Duplicate metadata key\')\n   d[k]=v\n  return d\n return json.loads(p.read_text(),object_pairs_hook=pairs)\ndef _selected():\n location=Path(__file__).absolute()\n if any(p.is_symlink() or getattr(p,\'is_junction\',lambda:False)() for p in (location,*location.parents)):raise ValueError(\'Linked entrypoint\')\n root=location.parent.resolve();p=_json(_file(root,\'.caiman/active-guidance.json\'));marker=_json(_file(root,\'.caiman/workspace-id.json\'))\n if p.get(\'schema\')!=\'caiman.active-guidance.v1\' or p.get(\'tier\')!=TIER or p.get(\'workspace_id\')!=marker.get(\'id\'):raise ValueError(\'Current-guide workspace/tier binding differs\')\n ref=p.get(\'receipt\',{});name=ref.get(\'path\',\'\')\n if not name.startswith(\'.caiman/kit-installations/\') or len(name.split(\'/\'))!=3:raise ValueError(\'Invalid current-guide receipt path\')\n receipt_file=_file(root,name)\n if hashlib.sha256(receipt_file.read_bytes()).hexdigest()!=ref.get(\'sha256\'):raise ValueError(\'Current-guide receipt changed\')\n receipt=_json(receipt_file);relative=p.get(\'guidance_relative\',\'\')\n if not relative.startswith(\'.caiman/kit-versions/\') or len(relative.split(\'/\'))!=3:raise ValueError(\'A companion guide is required; do not recurse into the legacy entrypoint\')\n if receipt.get(\'status\')!=\'COMPLETE_ARCHIVE_INSTALLED\' or receipt.get(\'workspace_id\')!=marker.get(\'id\') or receipt.get(\'tier\')!=TIER or receipt.get(\'guidance_relative\')!=relative:raise ValueError(\'Current-guide installation binding differs\')\n target=_file(root,relative+\'/\'+ENTRY)\n if hashlib.sha256(target.read_bytes()).hexdigest()!=receipt.get(\'files\',{}).get(ENTRY):raise ValueError(\'Current guide bytes differ from its installation receipt\')\n return target\ntry:\n _target=_selected()\n if __name__==\'__main__\':\n  sys.argv[0]=str(_target);runpy.run_path(str(_target),run_name=\'__main__\')\n else:globals().update(runpy.run_path(str(_target),run_name=__name__))\nexcept (ValueError,OSError,KeyError) as e:\n if __name__!=\'__main__\':raise\n print(json.dumps({\'status\':\'GUIDANCE_REFERENCE_NEEDS_ATTENTION\',\'error\':str(e),\'project_changed\':False}));raise SystemExit(2)\n'

def activate_root_entrypoint(root,target,tier):
    if target==root:return {'status':'DIRECT_CURRENT_GUIDE','changed':0}
    entry='GUIDED_SETUP.py' if tier=='vip' else 'GLS_GUIDED_SETUP.py'
    path=v.confined(root,entry)
    if path.exists() or v.linklike(path):v.regular(path)
    before=path.read_bytes() if path.exists() else None
    raw=ROOT_ENTRYPOINT_SOURCE.replace('__TIER__',repr(tier)).replace('__ENTRY__',repr(entry)).encode()
    after_sha=hashlib.sha256(raw).hexdigest()
    if before==raw:return {'status':'CURRENT_GUIDE_FORWARDER_ALREADY_ACTIVE','changed':0,'entrypoint':entry,'sha256':after_sha}
    before_sha=hashlib.sha256(before).hexdigest() if before is not None else None
    if before_sha is not None and before_sha not in ROOT_ENTRYPOINT_PREDECESSORS[tier]:
        return {'status':'UNKNOWN_ROOT_ENTRYPOINT_PRESERVED','changed':0,'entrypoint':entry,'sha256':before_sha,'next_action':'Use the verified companion guide path directly. Preserve and reconcile the client-edited root entrypoint; do not overwrite it.'}
    folder=safe_dir(root,'.caiman/entrypoint-history');backup=None
    if before is not None:
        backup=folder/(before_sha+'-'+entry)
        if backup.exists() and backup.read_bytes()!=before:raise plan.PlanError('entrypoint backup differs')
        if not backup.exists():exclusive(backup,before)
    fd,pending=tempfile.mkstemp(prefix='entrypoint-',dir=folder)
    with os.fdopen(fd,'wb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
    if (path.read_bytes() if path.exists() else None)!=before:raise plan.PlanError('root entrypoint changed during activation; original and staged launcher retained')
    os.replace(pending,path)
    if v.sha(path)!=after_sha:raise plan.PlanError('root entrypoint readback differs')
    record={'schema':'caiman.root-entrypoint-activation.v1','status':'CURRENT_GUIDE_FORWARDER_ACTIVE','entrypoint':entry,'before_sha256':before_sha,'after_sha256':after_sha,'backup':backup.relative_to(root).as_posix() if backup else None,'guide_pointer_sha256':v.sha(root/'.caiman/active-guidance.json'),'meaning':'Only a recognized package entrypoint is replaced. Its original bytes are retained; the forwarder verifies the current same-tier workspace receipt before dispatch.'}
    receipt=folder/(after_sha+'-'+str(before_sha or 'absent')+'.json')
    if not receipt.exists():exclusive(receipt,encode(record))
    return {**record,'changed':1,'receipt':receipt.relative_to(root).as_posix(),'receipt_sha256':v.sha(receipt)}

def install(root_raw, archive, archive_sha256, selected_tier, approved_release, mode):
    root = v.root_path(root_raw)
    source = plan.source_path(archive)
    expected, release, prefix, total = plan.archive_members(
        source, archive_sha256, selected_tier, approved_release)
    boundary = root/'ENTITLEMENTS.json'
    if boundary.exists() or v.linklike(boundary):
        local = v.strict_json(plan.source_path(boundary))
        tier = {'gls_plus': 'gls-plus'}.get(local.get('plan_tier'), local.get('plan_tier'))
        if tier != selected_tier:
            raise plan.PlanError('existing workspace tier differs; no automatic tier conversion')
    # Companion installs preserve member rules, data and engines; a managed current-guide entry is added.
    # Fresh installs are permitted only when every archive target is absent or exact.
    before = plan.plan_archive(root, source, archive_sha256, selected_tier, approved_release)
    if mode == 'fresh' and before['status'] not in (
            'COMPLETE_ARCHIVE_COPY_PLAN_READY', 'COMPLETE_VERIFIED_COPY'):
        raise plan.PlanError('existing work needs companion mode; no file replacement permitted')
    meta = safe_dir(root, '.caiman')
    lock = meta/'kit-install.lock'
    lock_fd=acquire_lock(lock)
    stage = None
    try:
        identity=workspace_id(meta)
        # Recheck under our lock, then verify every staged byte before touching targets.
        if plan.plan_archive(root, source, archive_sha256, selected_tier, approved_release) != before:
            raise plan.PlanError('workspace changed after inspection; preserve it and inspect again')
        cache = safe_dir(root, '.caiman/kit-versions')
        target = root if mode == 'fresh' else cache/(selected_tier+'-'+archive_sha256[:20])
        current_guide_note(root,target,None,selected_tier,approved_release,check_only=True)
        if mode == 'fresh' and before['complete_copy_verified']:
            verify_tree(target,expected)
        elif mode == 'companion' and (target.exists() or v.linklike(target)):
            target = v.root_path(target)
            verify_tree(target, expected)
        else:
            stage = Path(tempfile.mkdtemp(prefix='incoming-', dir=cache))
            with zipfile.ZipFile(source) as z:
                for name, digest in expected.items():
                    p = v.confined(stage, name)
                    p.parent.mkdir(parents=True, exist_ok=True)
                    raw = z.read(prefix+name)
                    if hashlib.sha256(raw).hexdigest() != digest:
                        raise plan.PlanError('archive changed during extraction')
                    exclusive(p, raw)
            if v.sha(source) != archive_sha256:
                raise plan.PlanError('source archive changed during extraction')
            verify_tree(stage, expected)
            if mode == 'companion':
                if target.exists() or v.linklike(target):
                    raise plan.PlanError('companion destination appeared during staging')
                os.rename(stage, target)
                stage = None
            else:
                for name, digest in expected.items():
                    dest = v.confined(root, name)
                    if dest.exists():
                        if v.sha(dest) != digest:
                            raise plan.PlanError('client file changed during installation: '+name)
                        continue
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    # O_EXCL refuses a competing file rather than replacing it.
                    exclusive(dest, (stage/name).read_bytes())
        verify_tree(target, expected)
        if mode == 'fresh':
            existing, state = v.state_files(root, None)
            if existing and existing != expected:
                raise plan.PlanError('existing sync state differs; preserve it for migration')
        receipt = {
            'schema': 'caiman.local-kit-installation.v1', 'status': 'COMPLETE_ARCHIVE_INSTALLED',
            'observed_at': stamp(), 'project_root': str(root), 'guidance_root': str(target),
            'workspace_id':identity,'guidance_relative':'.' if target==root else target.relative_to(root).as_posix(),
            'mode': mode, 'tier': selected_tier, 'release': approved_release,
            'archive_sha256': archive_sha256, 'representation': 'COMPLETE_PACKED_ARCHIVE',
            'verified_files': len(expected), 'uncompressed_bytes': total,
            'files': expected, 'archive_copy_root_replacements': 0, 'engine_executed': False,
            'root_entrypoint_policy':'A separate, backed-up forwarder may activate a recognized legacy guide entrypoint; unknown edits are preserved.',
            'temporary_files_policy': 'RETAINED_NO_DELETE_PERMISSION_REQUIRED',
            'account_actions': False, 'schedules': False, 'provider_entitlement_verified': False,
            'next_action': 'Run the guide status from guidance_root against project_root. '
                           'Existing runtime upgrades use the separate inspected backup/rollback path.'}
        receipts = safe_dir(root, '.caiman/kit-installations')
        receipt_path = receipts/(selected_tier+'-'+archive_sha256[:20]+'-'+mode+'.json')
        if receipt_path.exists():
            previous = v.strict_json(receipt_path)
            comparable = lambda r: {k: val for k, val in r.items() if k not in ('observed_at','project_root','guidance_root')}
            if comparable(previous) != comparable(receipt):
                raise plan.PlanError('existing installation receipt differs')
            receipt = previous
        else:
            exclusive(receipt_path, encode(receipt))
        # No generic kit-state claim: that state uses the server's distinct expanded
        # representation/version. Bind a separate exact-archive receipt instead.
        pointer = {'schema': 'caiman.active-guidance.v1', 'tier': selected_tier,
                   'workspace_id':identity,'guidance_relative':'.' if target==root else target.relative_to(root).as_posix(),
                   'receipt': {'path': receipt_path.relative_to(root).as_posix(),
                               'sha256': v.sha(receipt_path)}}
        pointer_path = meta/'active-guidance.json'
        data = encode(pointer)
        if pointer_path.exists() or v.linklike(pointer_path):
            v.regular(pointer_path)
            old = pointer_path.read_bytes()
            if old != data:
                old_sha = hashlib.sha256(old).hexdigest()
                backup = receipts/('previous-guidance-'+old_sha+'.json')
                if backup.exists():
                    if backup.read_bytes() != old: raise plan.PlanError('pointer backup differs')
                else: exclusive(backup, old)
                if pointer_path.read_bytes() != old: raise plan.PlanError('guidance pointer changed')
                fd, name = tempfile.mkstemp(prefix='guidance-', dir=meta)
                with os.fdopen(fd, 'wb') as f: f.write(data)
                os.replace(name, pointer_path)
        else:
            exclusive(pointer_path, data)
        note=current_guide_note(root,target,pointer,selected_tier,approved_release)
        activation=activate_root_entrypoint(root,target,selected_tier)
        return {k: val for k, val in receipt.items() if k != 'files'} | {
            'current_instruction_entry':note, 'root_entrypoint_activation':activation,
            'root_files_replaced':activation['changed'],
            'project_root':str(root),'guidance_root':str(target),
            'receipt': str(receipt_path), 'receipt_sha256': v.sha(receipt_path),
            'guide': str(target/('GUIDED_SETUP.py' if selected_tier == 'vip' else 'GLS_GUIDED_SETUP.py'))}
    finally:
        # Retain staged and partial new files for a safe exact-byte resume.
        # Installation should not request permanent-delete access to a business.
        os.close(lock_fd)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('root', 'archive', 'archive-sha256', 'selected-tier', 'approved-release'):
        p.add_argument('--'+name, required=True)
    p.add_argument('--mode', choices=['fresh', 'companion'], required=True)
    a = p.parse_args()
    try:
        result = install(a.root, a.archive, a.archive_sha256, a.selected_tier, a.approved_release, a.mode)
    except (v.VerificationError, OSError, ValueError, zipfile.BadZipFile) as e:
        result = {'status': 'INSTALLATION_NEEDS_ATTENTION', 'error': str(e)[:600],
                  'installed': False, 'account_actions': False, 'schedules': False}
    print(json.dumps(result, sort_keys=True))
    return 0 if result['status'] == 'COMPLETE_ARCHIVE_INSTALLED' else 2


if __name__ == '__main__': raise SystemExit(main())
