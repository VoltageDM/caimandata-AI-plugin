#!/usr/bin/env python3
"""Read-only local Caiman manifest coverage; no transfer or entitlement assertion."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
sys.dont_write_bytecode = True
SCHEMA = 'caiman.kit-verification-manifest.v1'
STATE_SCHEMA = 'caiman.kit-state.v2'
HEX = re.compile(r'[0-9a-f]{64}\Z')
TIER_ORDER = {'gls-plus': 1, 'vip': 2}
MAX_JSON_BYTES = 4 * 1024 * 1024
MAX_FILES = 20000

class VerificationError(ValueError):
    pass

def pairs(items):
    out = {}
    for key, value in items:
        if key in out:
            raise VerificationError('duplicate JSON key')
        out[key] = value
    return out

def strict_json(path):
    regular(path)
    if path.stat().st_size > MAX_JSON_BYTES:
        raise VerificationError('JSON input exceeds bounded local verifier size')
    try:
        return json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=pairs,
                          parse_constant=lambda value: (_ for _ in ()).throw(VerificationError('non-finite JSON')))
    except (ValueError, UnicodeError) as exc:
        raise VerificationError('invalid strict JSON input: ' + path.name) from exc

def linklike(path):
    try:
        st = os.lstat(path)
    except FileNotFoundError:
        return False
    return stat.S_ISLNK(st.st_mode) or bool(getattr(st, 'st_file_attributes', 0) & 0x400)

def regular(path):
    if linklike(path) or not stat.S_ISREG(os.lstat(path).st_mode):
        raise VerificationError('expected a regular non-link file: ' + path.name)

def root_path(raw):
    supplied = Path(raw).expanduser().absolute()
    for parent in (supplied, *supplied.parents):
        if linklike(parent):
            raise VerificationError('project root has a symlink or reparse ancestor')
    if not supplied.is_dir():
        raise VerificationError('select an existing Caiman project folder')
    return supplied.resolve(strict=True)

def portable(name):
    if not isinstance(name, str) or not name or len(name) > 1024 or '\\' in name or ':' in name or name.startswith('/'):
        raise VerificationError('unsafe manifest/state path')
    parts = name.split('/')
    reserved = re.compile(r'(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?\Z', re.I)
    if any(part in ('', '.', '..') or part.endswith((' ', '.')) or
           any(ord(c) < 32 or c in '<>"|?*' for c in part) or reserved.fullmatch(part) for part in parts):
        raise VerificationError('unsafe portable manifest/state path: ' + name)
    if parts[0].casefold() in {'.caiman', '.git', '.claude', '.codex', '.ssh'} or any(
        part.casefold() == '.env' or part.casefold().startswith('.env.') for part in parts
    ):
        raise VerificationError('manifest/state file map cannot own protected client metadata')
    lowered = [part.casefold() for part in parts]
    if lowered[0] in {'client_rules.md', 'memory.md', 'memory', 'knowledge'}:
        raise VerificationError('manifest/state file map cannot own client foundation records')
    runtime = lowered[1:] if lowered[0] == 'vip machine' else (
        lowered[2:] if lowered[:2] == ['operating framework', 'vip machine'] else []
    )
    if runtime and (runtime[0] in {'state', 'runs', 'evidence', 'feeders', 'recommendations',
                                  'scorecard', 'lifecycle', 'ledger', 'outputs', 'health'} or
                    runtime[:2] == ['config', 'brand.json']):
        raise VerificationError('manifest/state file map cannot own initialized client runtime data')
    return parts

def confined(root, name):
    cursor = root
    for part in portable(name):
        cursor = cursor / part
        if linklike(cursor):
            raise VerificationError('symlink/reparse path is not a managed file: ' + name)
        if cursor.exists() and cursor != root.joinpath(*portable(name)) and not cursor.is_dir():
            raise VerificationError('file ancestor is not a directory: ' + name)
    return cursor

def sha(path):
    regular(path)
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()

def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()

def file_map(raw):
    if not isinstance(raw, dict) or len(raw) > MAX_FILES:
        raise VerificationError('file map must be a bounded path-to-sha256 object')
    out = {}
    for name, meta in raw.items():
        portable(name)
        value = meta.get('sha256') if isinstance(meta, dict) else meta
        if not isinstance(value, str) or not HEX.fullmatch(value):
            raise VerificationError('invalid SHA-256 for ' + name)
        out[name] = value
    folded = {}
    all_folded = {name.casefold() for name in out}
    for name in out:
        if name.casefold() in folded:
            raise VerificationError('case-colliding file paths')
        folded[name.casefold()] = name
        pieces = name.split('/')
        for length in range(1, len(pieces)):
            if '/'.join(pieces[:length]).casefold() in all_folded:
                raise VerificationError('file/directory prefix collision')
    return out

def manifest_set(raw):
    if not isinstance(raw, dict) or set(raw) != {'schema', 'kits'} or raw['schema'] != SCHEMA:
        raise VerificationError('expected local verification manifest schema; do not guess server fields')
    kits = raw['kits']
    if not isinstance(kits, list) or not 1 <= len(kits) <= 2:
        raise VerificationError('one or two explicitly entitled kits are required')
    seen = set(); parsed = []
    for item in kits:
        if not isinstance(item, dict) or set(item) != {'kit', 'version', 'files'}:
            raise VerificationError('invalid kit entry')
        slug = item['kit']; version = item['version']
        if slug not in TIER_ORDER or slug in seen:
            raise VerificationError('unknown or duplicate kit tier; support review required')
        if isinstance(version, bool) or not isinstance(version, int) or version < 1:
            raise VerificationError('kit version must be a positive integer from the manifest')
        seen.add(slug); parsed.append((slug, version, file_map(item['files'])))
    parsed.sort(key=lambda x: TIER_ORDER[x[0]], reverse=True)
    effective = {}; lower_unique = []
    for index, (slug, _, files) in enumerate(parsed):
        for name, digest in files.items():
            if name in effective:
                continue
            if index:
                parts = name.split('/')
                if parts[0].casefold() in {'skills', 'operating framework', 'manual operating framework', 'vip machine'} or name.casefold() in {
                    'entitlements.json', 'claude.md', 'agent_start.md', 'guided_setup.py', 'capabilities.json',
                    'machine_root_guard.py', 'release_manifest.json', 'capability_index.json',
                    'evidence contract.md', 'gls_plus_config.template.json', 'manual data guide.md',
                    'skills.md', 'source evidence notes.md', 'weekly checklist.md',
                }:
                    raise VerificationError('lower-tier-only capability or operating boundary needs support review: ' + name)
                lower_unique.append(name)
            effective[name] = digest
    effective = file_map(effective)
    if not effective:
        raise VerificationError('empty effective manifest is not a complete kit')
    versions = {slug: version for slug, version, _ in parsed}
    return effective, versions, lower_unique

def state_files(root, raw_state):
    path = Path(raw_state) if raw_state else root/'.caiman/kit-state.json'
    # State is a specific project-local file, never a user-supplied external path.
    if not path.is_absolute():
        path = root/path
    try:
        relative = path.relative_to(root)
    except ValueError as exc:
        raise VerificationError('state path must be inside the selected project') from exc
    if '..' in relative.parts:
        raise VerificationError('state path traversal is forbidden')
    for ancestor in (path, *path.parents):
        if linklike(ancestor):
            raise VerificationError('state has a symlink/reparse ancestor')
        if ancestor == root:
            break
    if not path.exists():
        return {}, None
    state = strict_json(path)
    if not isinstance(state, dict) or 'files' not in state:
        raise VerificationError('state must have an explicit installed-files map')
    if state.get('schema', STATE_SCHEMA) != STATE_SCHEMA:
        raise VerificationError('unsupported sync-state schema; preserve it for review')
    return file_map(state['files']), state

def inspect(root_raw, manifest_raw, state_raw=None, limit=10):
    root = root_path(root_raw)
    manifest_path = Path(manifest_raw).expanduser().absolute()
    expected, versions, lower_unique = manifest_set(strict_json(manifest_path))
    recorded, state = state_files(root, state_raw)
    boundary = root/'ENTITLEMENTS.json'
    if boundary.exists() or linklike(boundary):
        contract = strict_json(boundary)
        selected = contract.get('plan_tier') if isinstance(contract, dict) else None
        selected = {'gls_plus': 'gls-plus'}.get(selected, selected)
        if selected not in TIER_ORDER or selected != max(versions, key=lambda k:TIER_ORDER[k]):
            raise VerificationError('selected local tier differs from supplied manifest; support review required')
    counts = dict(unchanged=0, missing=0, stale_owned=0, member_edited=0, retired_owned=0, retired_member_edited=0)
    exceptions = []
    for name, expected_sha in expected.items():
        path = confined(root, name)
        if not path.exists():
            kind = 'missing'
        else:
            observed = sha(path)
            kind = 'unchanged' if observed == expected_sha else ('stale_owned' if recorded.get(name) == observed else 'member_edited')
        counts[kind] += 1
        if kind != 'unchanged':
            exceptions.append({'path': name, 'state': kind})
    retired_record_paths = set(recorded)-set(expected)
    for name in sorted(retired_record_paths):
        path = confined(root, name)
        if path.exists():
            kind = 'retired_owned' if sha(path) == recorded[name] else 'retired_member_edited'
            counts[kind] += 1; exceptions.append({'path': name, 'state': kind})
    effective_sha = canonical_hash({'kits': versions, 'files': expected})
    state_complete = False
    if state is not None:
        state_versions = state.get('kits')
        if state_versions is None and state.get('kit') in TIER_ORDER:
            state_versions = {state['kit']: state.get('version')}
        if not isinstance(state_versions, dict) or any(
            name not in TIER_ORDER or type(version) is not int or version < 1
            for name, version in state_versions.items()
        ):
            raise VerificationError('sync-state kit versions are malformed')
        same_map = recorded == expected and not retired_record_paths
        state_complete = bool(same_map and state_versions == versions and state.get('status', 'complete') == 'complete')
        if 'manifest_sha256' in state:
            state_complete = state_complete and state['manifest_sha256'] == effective_sha
    files_complete = counts['unchanged'] == len(expected)
    pending = bool(counts['retired_owned'])
    status = 'CURRENT' if files_complete and state_complete and not pending else ('COMPLETE_STATE_UPDATE_REQUIRED' if files_complete and not pending else 'INCOMPLETE')
    return {
        'schema': 'caiman.kit-local-verification.v1', 'status': status,
        'scope': 'local bytes against supplied manifest; live entitlement and provider freshness are not verified',
        'project_root': str(root), 'kits': versions, 'manifest_sha256': effective_sha,
        'manifest_file_sha256': sha(manifest_path), 'expected_files': len(expected),
        'counts': counts, 'coverage_complete': files_complete, 'state_complete': state_complete,
        'lower_tier_unique_count': len(lower_unique), 'lower_tier_unique_paths': lower_unique[:limit],
        'exceptions': exceptions[:limit], 'exceptions_omitted': max(0,len(exceptions)-limit),
        'transfer_performed': False, 'project_changed': False,
    }

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',required=True)
    parser.add_argument('--manifest',required=True)
    parser.add_argument('--state')
    parser.add_argument('--max-items',type=int,default=10,choices=range(1,51))
    args=parser.parse_args(argv)
    try:
        result=inspect(args.root,args.manifest,args.state,args.max_items)
    except (VerificationError,OSError) as exc:
        result={'schema':'caiman.kit-local-verification.v1','status':'STOP','reason':str(exc),'project_changed':False,'transfer_performed':False}
    print(json.dumps(result,indent=2,sort_keys=True,ensure_ascii=False))
    return 0 if result['status']=='CURRENT' else 2

if __name__=='__main__':
    raise SystemExit(main())
