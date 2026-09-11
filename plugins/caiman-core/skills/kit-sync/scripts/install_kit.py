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
    # Companion installs preserve all existing root instructions, data and engines.
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
            'files': expected, 'root_files_replaced': 0, 'engine_executed': False,
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
        return {k: val for k, val in receipt.items() if k != 'files'} | {
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
