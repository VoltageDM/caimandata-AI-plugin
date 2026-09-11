#!/usr/bin/env python3
"""Download one complete archive from a verified service descriptor; no installation."""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import tempfile
import urllib.parse
import urllib.request
import sys
sys.dont_write_bytecode = True
import plan_install as plan
import verify_kit as v

ORIGIN = 'https://tools.caimandata.ai'


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ValueError('download redirect refused; request a fresh descriptor')


def download(descriptor, staging):
    d = v.strict_json(plan.source_path(descriptor))
    if d.get('schema') != 'caiman.kit-download.v1' or d.get('tier') not in v.TIER_ORDER:
        raise ValueError('unsupported complete-archive download descriptor')
    if d.get('representation') != 'COMPLETE_PACKED_ARCHIVE' or not v.HEX.fullmatch(d.get('sha256', '')):
        raise ValueError('exact complete-archive hash required')
    if type(d.get('bytes')) is not int or not 0 < d['bytes'] <= plan.MAX_ARCHIVE_BYTES:
        raise ValueError('bounded archive byte count required')
    if not isinstance(d.get('release'), str) or not d['release']:
        raise ValueError('release required')
    now = dt.datetime.now(dt.timezone.utc)
    expiry = dt.datetime.fromisoformat(d['expires_at'].replace('Z', '+00:00'))
    if expiry.tzinfo is None or expiry <= now or (expiry-now).total_seconds() > 900:
        raise ValueError('expired or unbounded download ticket')
    url = urllib.parse.urlsplit(d['download_url'])
    if (url.scheme+'://'+url.netloc != ORIGIN or url.username or url.password or
        url.fragment or not url.path.startswith('/api/kit-download/') or
        any(ord(c) <= 32 for c in d['download_url'])):
        raise ValueError('download descriptor is outside the published service route')
    parent = v.root_path(staging)
    dest = parent/(d['tier']+'-'+d['sha256'][:20]+'.zip')
    if dest.exists() or v.linklike(dest):
        if v.sha(dest) != d['sha256']: raise ValueError('staged archive differs')
        plan.archive_members(dest, d['sha256'], d['tier'], d['release'])
    else:
        fd, temporary = tempfile.mkstemp(prefix='download-', dir=parent)
        try:
            h = hashlib.sha256(); size = 0
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
            request = urllib.request.Request(d['download_url'], headers={'Accept': 'application/zip'})
            with os.fdopen(fd, 'wb') as out, opener.open(request, timeout=60) as response:
                if response.status != 200: raise ValueError('archive service did not return a complete file')
                for chunk in iter(lambda: response.read(1024*1024), b''):
                    size += len(chunk)
                    if size > d['bytes']: raise ValueError('download exceeds declared archive size')
                    h.update(chunk); out.write(chunk)
            if size != d['bytes'] or h.hexdigest() != d['sha256']:
                raise ValueError('download count or checksum differs')
            plan.archive_members(temporary, d['sha256'], d['tier'], d['release'])
            # Create the final verified copy without delete/rename permission.
            # Keep the staging file as recoverable evidence; cleanup is optional.
            with os.fdopen(os.open(dest,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0),0o600),'wb') as target, open(temporary,'rb') as source:
                for chunk in iter(lambda:source.read(1024*1024),b''):target.write(chunk)
            if v.sha(dest)!=d['sha256']:raise ValueError('final archive readback differs')
        finally:
            pass  # Deliberately retained; no broad device deletion permission.
    return {'schema': 'caiman.archive-download-receipt.v1', 'status': 'COMPLETE_ARCHIVE_DOWNLOADED',
            'path': str(dest), 'sha256': v.sha(dest), 'bytes': dest.stat().st_size,
            'tier': d['tier'], 'release': d['release'], 'installed': False,
            'descriptor_source': 'authenticated service response required; local parsing is not entitlement proof'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--descriptor', required=True); p.add_argument('--staging', required=True)
    a = p.parse_args()
    try: result = download(a.descriptor, a.staging)
    except Exception as e:
        # Exception text from HTTP clients can contain the bearer URL; do not echo it.
        result = {'status': 'DOWNLOAD_UNAVAILABLE', 'error_type': type(e).__name__,
                  'next_action': 'Use one approved complete ZIP, or request a fresh service descriptor. '
                                 'Do not relay bulk content or repeat failed downloads.'}
    print(json.dumps(result, sort_keys=True))
    return 0 if result['status'] == 'COMPLETE_ARCHIVE_DOWNLOADED' else 2


if __name__ == '__main__': raise SystemExit(main())
