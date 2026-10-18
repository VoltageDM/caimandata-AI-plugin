#!/usr/bin/env python3
"""Caiman workspace: one member's brands, each in its own business folder, under one folder.

  python3 workspace.py find        --workspace "<folder>"
  python3 workspace.py init        --workspace "<folder>"
  python3 workspace.py status      --workspace "<folder>" [--brands "<brand>,<brand>"] [--quick]
  python3 workspace.py plan        --workspace "<folder>" [--brands "<brand>,<brand>"] [--timeout 180]
  python3 workspace.py run start   <workflow> --workspace "<folder>" [--brands ...] [--goal "<request>"] [--scheduled] [--new]
                                   [--session "<session>"]
  python3 workspace.py run next    --workspace "<folder>" [--run "<run>"] [--session "<session>"]
                                   [--take-over <brand> | --leave <brand>]
  python3 workspace.py run done    <brand> --workspace "<folder>" --status done|skipped|failed|needs-answer --note "..."
                                   [--summary <file>] [--run "<run>"] [--session "<session>"]
  python3 workspace.py run reports <brand> --workspace "<folder>" --run "<run>" [--session "<session>"]
                                   [--add "<read>=<report id>" ...] [--failed "<read>=<what it said>" ...]
  python3 workspace.py run status  --workspace "<folder>" [--run "<run>"]
  python3 workspace.py run finish  --workspace "<folder>" [--partial] [--run "<run>"]
  python3 workspace.py summary     --workspace "<folder>" [--brands ...] [--quick]
  python3 workspace.py update-plan --workspace "<folder>" [--live-kit <release> ...]
  python3 workspace.py update      --workspace "<folder>" --zip "<kit zip>" [--zip "<other tier's kit zip>"] [--dry-run]
  python3 workspace.py routine     list|prompt [<workflow>] --workspace "<folder>"

A workspace is the folder that holds a member's business folders, one per brand (for example three brands in
three folders under one "brands" folder). Each brand keeps its own business folder, kit and Amazon account; nothing
moves. This program finds the business folders (up to three levels down), reads each one's identity from its own
files (never the connector), and runs one workflow across the brands one brand at a time, so a stopped run picks up
at the next brand and one combined note comes at the end. It never mixes one brand's data into another's.

find         lists the business folders and what each one is (brand, connector brand slug, marketplace, saved seller
             and Ads account IDs, membership, kit version, VIP Machine), and flags two folders bound to one brand,
             brands that share a seller account or Ads profile, and kits older than this plugin. It writes nothing.
init         writes CAIMAN WORKSPACE.json, a workspace section in the folder's CLAUDE.md (between its own START and END
             lines; the member's text outside them is never changed) and START HERE - all brands.md. Run it again to
             refresh them and pick up new brand folders.
status       one table across the brands: kit, setup step, VIP Machine, last weekly close, results due and alerts, from
             each folder's own scripts and saved outputs. It writes nothing.
plan         runs each brand's NEXT_STEP.py (which never contacts Amazon; it refreshes that brand's own CAIMAN PLAN.md as
             usual) and merges the steps into one ranked plan, each labeled with its brand: WORKSPACE PLAN.md and
             WORKSPACE PLAN.json.
run          a resumable run of one workflow across the brands: start writes workspace-runs/<date> <workflow>.json with
             each brand pending; next names the next brand, its folder and account and how to start the workflow there;
             done records a brand's result; finish writes one combined note from each brand's summary. An unfinished
             run continues with next. A brand handed to one session stays with it until it's recorded: another
             conversation asks the member first (--take-over or --leave), and a scheduled run leaves it alone and moves
             on. A VIP brand that shares its account with another brand and has no brand scope saved is flagged.
             For the report-heavy workflows (the Advertising Daily Check, both weekly reviews and the VIP Machine's
             weekly loop) start first asks for every brand's Ads reports, each with that brand's own slug; reports
             records their IDs per brand, and each brand's task polls its own instead of requesting them again.
summary      one read-only page across the brands from their latest saved outputs: WORKSPACE SUMMARY.html and .md.
             With a VIP Machine brand scope, figures built for the whole seller account are said to be so.
update-plan  each brand's kit against this plugin, and how to update them all.
update       updates every brand whose kit needs it, one folder at a time, with kit-sync and the kit zip for that
             brand's own membership; one result per brand. It never switches a brand to the other membership.
routine      the all-brands scheduled tasks: list says which brands each would cover; prompt prints the prompt for
             one, to create only after the member approves it.

Workflows a run takes: deep-seed, weekly-growth-review, listing-creative-pack, stock-profit-plan,
advertising-weekly-review, advertising-daily-check, advertising-structure-review (each brand's own CLIENT_START.py),
setup-check, request (the member's own words, --goal), and the VIP Machine's routines vip-weekly-loop,
vip-daily-brief, vip-health-check and vip-opportunity-review (each VIP brand's own routine prompt).

Everything prints JSON for Claude, with member_message in plain words. It never contacts Amazon, never changes an
account and never schedules anything. Standard-library Python 3.8+, in one file.
"""
import argparse
import datetime as dt
import hashlib
import html
import json
import os
import re
import secrets
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

sys.dont_write_bytecode = True

HERE = Path(__file__).resolve().parent                  # <plugin>/skills/caiman/scripts
SCHEMA = 'caiman.workspace.v1'
RUN_SCHEMA = 'caiman.workspace-run.v1'
PLAN_SCHEMA = 'caiman.workspace-plan.v1'
WORKSPACE_FILE = 'CAIMAN WORKSPACE.json'
START_FILE = 'START HERE - all brands.md'
PLAN_MD, PLAN_JSON = 'WORKSPACE PLAN.md', 'WORKSPACE PLAN.json'
SUMMARY_MD, SUMMARY_HTML = 'WORKSPACE SUMMARY.md', 'WORKSPACE SUMMARY.html'
RUNS = 'workspace-runs'
CLAUDE_FILE = 'CLAUDE.md'
MAX_DEPTH = 3
MACHINE_DIR = 'VIP Machine'
NESTED_MACHINE_DIR = 'Operating Framework/VIP Machine'
MACHINE_FILES = ('engine/vip_machine.py', 'config/brand.json', 'state/workspace.json')
TIER_NAMES = {'vip': 'Caiman VIP', 'gls-plus': 'Caiman GLS+'}
SECTION_START = ('<!-- CAIMAN WORKSPACE START: workspace.py init replaces this section when it runs again. Your own '
                 'notes go outside it. -->')
SECTION_END = '<!-- CAIMAN WORKSPACE END -->'
SECTION_START_RE = re.compile(r'<!--\s*CAIMAN[\s_-]*WORKSPACE[\s_-]*(?:START|BEGIN)\b.*?-->', re.I | re.S)
SECTION_END_RE = re.compile(r'<!--\s*CAIMAN[\s_-]*WORKSPACE[\s_-]*END\b.*?-->', re.I | re.S)
SKIP_EXACT = {'__pycache__', '__macosx', 'node_modules', RUNS}
KIT_COPY_NAMES = {'caiman vip - guided kit', 'caiman gls plus - guided kit'}
STEP_SECONDS = 180
SHORT_SECONDS = 60
SUMMARY_CHARS = 6000
MONTHS = ('January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October',
          'November', 'December')

# Workflows a run can take: (name, kind, first line of the request or routine prompt file).
WORKFLOWS = {
    'deep-seed': ('Deep Seed', 'kit', 'Deep Seed this business: set up the workspace, pull the history my accounts '
                                      'hold, and show me my first business view and the plan.'),
    'weekly-growth-review': ('Weekly Growth Review', 'kit',
                             'Run a Weekly Growth Review for this business and give me one prioritized action plan.'),
    'listing-creative-pack': ('Listing & Creative Pack', 'kit', 'Build a Listing & Creative Pack for one product or '
                                                                'clearly defined product family in this business.'),
    'stock-profit-plan': ('Stock & Profit Plan', 'kit', 'Build a Stock & Profit Plan for the selected products in this '
                                                        'business so I can make a purchasing or pricing decision.'),
    'advertising-weekly-review': ('Advertising Weekly Review', 'kit', 'Run the Advertising Weekly Review.'),
    'advertising-daily-check': ('Advertising Daily Check', 'kit', 'Run the Advertising Daily Check.'),
    'advertising-structure-review': ('Advertising Structure Review', 'kit',
                                     'Run an Advertising Structure Review for this business after Deep Seed, using the '
                                     'saved product and advertising history.'),
    'setup-check': ('Setup check', 'setup', None),
    'kit-update': ('Kit update', 'kit-update', None),
    'vip-weekly-loop': ('VIP Machine weekly review', 'routine', 'weekly-loop.prompt.md'),
    'vip-daily-brief': ('VIP Machine daily brief', 'routine', 'daily-brief.prompt.md'),
    'vip-health-check': ('VIP Machine health check', 'routine', 'health-check.prompt.md'),
    'vip-opportunity-review': ('VIP Machine opportunity review', 'routine', 'dreaming-loop.prompt.md'),
    'request': ('Your request', 'request', None),
}
# Runs of these start fresh each day: yesterday's unfinished run is closed rather than continued.
DAILY = ('advertising-daily-check', 'vip-daily-brief', 'vip-health-check', 'setup-check')
# An unfinished run of the other workflows this many days old is closed, not continued, when a new one starts.
STALE_DAYS = 6
DONE_STATUSES = ('done', 'skipped', 'failed', 'needs-answer')
STATUS_WORDS = {'pending': 'Not started', 'in-progress': 'In progress', 'done': 'Done', 'skipped': 'Skipped',
                'failed': "Didn't finish", 'needs-answer': 'Needs your answer', 'not-run': 'Not run'}
# The search for business folders looks at no more folders than this (as the setup check does): a home, Documents or
# Dropbox folder opened by mistake isn't searched through (Caiman 0.3.17).
DISCOVER_MAX_FOLDERS = 3000
# A brand handed to one session stays that session's until it's recorded (Caiman 0.3.17): another conversation asks
# the member first, and a scheduled run leaves it alone unless that session has had it this long (it most likely
# stopped).
CLAIM_HOLD_MINUTES = 180


class WorkspaceError(Exception):
    pass


class TooManyFolders(WorkspaceError):
    """The folder holds more folders than the search looks at: not a workspace (a home or Dropbox folder)."""


# ---------------------------------------------------------------- small helpers

def read_json(path, limit=32 * 1024 * 1024):
    try:
        path = Path(path)
        if not path.is_file() or path.stat().st_size > limit:
            return None
        with open(str(path), 'r', encoding='utf-8-sig') as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return None


def read_text(path, limit=4 * 1024 * 1024):
    try:
        path = Path(path)
        if not path.is_file() or path.stat().st_size > limit:
            return None
        return path.read_bytes().decode('utf-8', 'replace')
    except OSError:
        return None


def as_dict(value):
    return value if isinstance(value, dict) else {}


def text_value(value):
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        value = str(value)
    if isinstance(value, str) and value.strip() and not value.strip().startswith('REPLACE_'):
        return value.strip()
    return None


def norm_tier(value):
    if not isinstance(value, str):
        return None
    key = re.sub(r'[\s_]+', '-', value.strip().lower())
    return {'vip': 'vip', 'gls-plus': 'gls-plus', 'glsplus': 'gls-plus', 'gls+': 'gls-plus'}.get(key)


def parse_version(value):
    if isinstance(value, str):
        match = re.fullmatch(r'\s*v?(\d+)\.(\d+)(?:\.(\d+))?\s*', value)
        if match:
            return tuple(int(part or 0) for part in match.groups())
    return None


def name_key(value):
    return re.sub(r'[\W_]+', '', (text_value(value) or '').casefold())


def slug_shaped(value):
    return bool(re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', value or '')) and not value.isdigit()


def slugify(value):
    return re.sub(r'[^a-z0-9]+', '-', (value or '').lower()).strip('-') or 'brand'


LINK_KEYS = {'schema_version', 'record_type', 'identity_hash', 'brand_slug', 'connector_slug', 'linked_at', 'checked_with',
             'receipts', 'source_file_sha256s', 'reason', 'replaces', 'binding_sha256'}


def linked_slug(machine, config):
    """The connector slug a VIP Machine set up under another name is linked to (vip_machine.py link-connector-slug,
    Caiman 0.3.17 on), when its saved link belongs to this machine and its checksum holds; else None."""
    record = as_dict(read_json(machine / 'state' / 'connector_binding.json'))
    try:
        payload = {'brand_slug': config['brand']['slug'], 'seller_id': config['account_identity']['seller_id'],
                   'profile_id': config['account_identity']['profile_id'], 'marketplace_id': config['marketplace']['id']}
    except (KeyError, TypeError):
        return None
    sha = lambda value: hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'),
                                                  allow_nan=False).encode('utf-8')).hexdigest()
    if set(record) != LINK_KEYS or record.get('record_type') != 'connector_slug_link' \
            or record.get('identity_hash') != sha(payload) or record.get('brand_slug') != payload['brand_slug'] \
            or sha({key: record[key] for key in LINK_KEYS - {'binding_sha256'}}) != record.get('binding_sha256'):
        return None
    slug = text_value(record.get('connector_slug'))
    return slug if slug and slug_shaped(slug) else None


def now():
    return dt.datetime.now().astimezone()


def stamp(moment=None):
    return (moment or now()).astimezone(dt.timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def parse_time(value):
    if not isinstance(value, str):
        return None
    text = value.strip().replace('Z', '+00:00').replace('z', '+00:00')
    try:
        moment = dt.datetime.fromisoformat(text)
    except ValueError:
        try:
            moment = dt.datetime.combine(dt.date.fromisoformat(text[:10]), dt.time())
        except ValueError:
            return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=dt.timezone.utc)
    return moment


def plain_date(moment):
    local = moment.astimezone()
    return '{} {}, {}'.format(MONTHS[local.month - 1], local.day, local.year)


def plain_time(moment):
    local = moment.astimezone()
    return '{} at {}:{:02d} {}'.format(plain_date(local), local.hour % 12 or 12, local.minute,
                                       'AM' if local.hour < 12 else 'PM')


def one_line(text, limit=300):
    text = ' '.join(str(text or '').split())
    return text if len(text) <= limit else text[:limit - 3] + '...'


def plural(count, one, many=None):
    return '{} {}'.format(count, one if count == 1 else (many or one + 's'))


def names(items):
    items = [item for item in items if item]
    if len(items) <= 1:
        return ''.join(items)
    return ', '.join(items[:-1]) + ' and ' + items[-1]


def write_atomic(path, data):
    """Write bytes to path through a temporary file beside it, so a stopped write never leaves half a file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix='.' + path.name + '.', suffix='.tmp', dir=str(path.parent))
    try:
        with os.fdopen(handle, 'wb') as out:
            out.write(data)
        os.replace(temporary, str(path))
    except BaseException:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def write_json(path, value):
    write_atomic(path, (json.dumps(value, indent=2, ensure_ascii=False, sort_keys=False) + '\n').encode('utf-8'))


def run_program(argv, cwd, seconds):
    """(exit code, stdout, stderr, None), or (None, '', '', why) when it couldn't start or didn't finish in time."""
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONIOENCODING='utf-8')
    try:
        done = subprocess.run(argv, cwd=str(cwd), env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, timeout=seconds)
    except subprocess.TimeoutExpired:
        return None, '', '', 'it did not finish within {} seconds'.format(seconds)
    except OSError as error:
        return None, '', '', 'it could not start ({})'.format(error)
    return done.returncode, done.stdout.decode('utf-8', 'replace'), done.stderr.decode('utf-8', 'replace'), None


def json_from(text):
    text = (text or '').strip()
    if not text:
        return None
    try:
        value = json.loads(text)
    except ValueError:
        start = text.find('{')
        if start < 0:
            return None
        try:
            value = json.JSONDecoder().raw_decode(text[start:])[0]
        except ValueError:
            return None
    return value if isinstance(value, dict) else None


def python():
    return sys.executable or 'python3'


def quoted(path):
    return '"{}"'.format(str(path).replace('"', '\\"'))


def me():
    return quoted(Path(__file__).resolve())


# ---------------------------------------------------------------- the plugin

def plugin_version(explicit=None):
    if explicit:
        return explicit.strip()
    candidates = [HERE.parent.parent.parent]
    if os.environ.get('CLAUDE_PLUGIN_ROOT'):
        candidates.append(Path(os.environ['CLAUDE_PLUGIN_ROOT']))
    for root in candidates:
        manifest = as_dict(read_json(root / '.claude-plugin' / 'plugin.json'))
        if manifest.get('name') == 'caiman-core' and text_value(manifest.get('version')):
            return manifest['version'].strip()
    return None


def kit_sync_program():
    path = HERE.parent.parent / 'kit-sync' / 'scripts' / 'kit_sync.py'
    return path if path.is_file() else None


def given_kit_sync(value):
    """The kit_sync.py a --kit-sync option names, as an absolute path (Caiman 0.3.17). kit-sync runs from inside each
    brand's folder, so a path relative to the folder this was run from must be made absolute first. A path that isn't
    a file is refused in plain words; nothing has run yet."""
    path = Path(os.path.abspath(os.path.expanduser(value.strip())))
    if not path.is_file():
        raise WorkspaceError("There's no kit_sync.py at {}. Nothing was changed. Give the path of kit_sync.py with "
                             '--kit-sync (a path relative to the folder you run this from works too).'.format(path))
    return path


# ---------------------------------------------------------------- finding the business folders

def skip_reason(name):
    """Why a folder isn't searched, or None. Hidden and system folders are skipped without a word."""
    low = name.lower()
    if name.startswith('.') or low in SKIP_EXACT:
        return ''
    if low.startswith('_previous-kit'):
        return 'earlier kit files kept by kit-sync'
    if low.startswith('_archive'):
        return 'an archive'
    if low.startswith('_retired'):
        return 'retired'
    if 'backup' in low:
        return 'a backup'
    return None


def has_kit(folder):
    """True when the folder holds a Caiman kit: its release manifest or entitlements, or a kit an older installer put
    beside the business files."""
    manifest = read_json(folder / 'RELEASE_MANIFEST.json')
    if isinstance(manifest, dict) and any(manifest.get(key) for key in ('kit', 'tier', 'core_version', 'release')):
        return True
    entitlements = read_json(folder / 'ENTITLEMENTS.json')
    if isinstance(entitlements, dict) and entitlements.get('plan_tier'):
        return True
    return (folder / '.caiman' / 'active-guidance.json').is_file()


def too_many_folders_words(root):
    """Why a folder with more folders than the search looks at isn't searched, and where to open the workspace."""
    return ("{} holds more folders than Claude searches for business folders (it stopped after looking at {:,}), so it "
            "looks like a home, Documents or Dropbox folder rather than a workspace. Nothing was changed. Open the folder "
            "that holds your brands' business folders (each brand's own folder, side by side) as the workspace, or give "
            "that folder with --workspace.".format(root, DISCOVER_MAX_FOLDERS))


def discover(root):
    """(business folders, skipped [{folder, why}]) under root, up to MAX_DEPTH levels down. The search doesn't go
    inside a business folder, a link, or a folder of earlier kit files, archives, retired work or backups. It looks at
    no more than DISCOVER_MAX_FOLDERS folders, as the setup check does: past that it raises TooManyFolders."""
    found, skipped = [], []
    seen = [0]

    def walk(folder, depth):
        try:
            children = sorted((child for child in folder.iterdir() if child.is_dir()), key=lambda p: p.name.lower())
        except OSError as error:
            skipped.append({'folder': rel(root, folder), 'why': "it couldn't be opened ({})".format(
                error.strerror or error)})
            return
        for child in children:
            seen[0] += 1
            if seen[0] > DISCOVER_MAX_FOLDERS:
                raise TooManyFolders(too_many_folders_words(root))
            if child.is_symlink():
                continue
            why = skip_reason(child.name)
            if why is not None:
                if why and has_kit(child):
                    skipped.append({'folder': rel(root, child), 'why': why})
                continue
            if has_kit(child):
                if child.name.lower() in KIT_COPY_NAMES and not (child / '.caiman').is_dir():
                    skipped.append({'folder': rel(root, child), 'why': 'an unpacked kit, not a business folder'})
                    continue
                found.append(child)
                continue
            if depth < MAX_DEPTH:
                walk(child, depth + 1)

    walk(root, 1)
    return found, skipped


PROBE_DEPTH = 6
PROBE_MAX_FOLDERS = 3000


def deeper_business_folders(root):
    """When nothing is found within MAX_DEPTH levels: the folders further down (to PROBE_DEPTH levels, looking at no more
    than PROBE_MAX_FOLDERS folders) that hold business folders, [{folder, brands}], nearest first. [] when root is
    itself a business folder. It only reads folder names and each folder's kit marker files."""
    if has_kit(root):
        return []
    parents, seen = {}, [0]

    def walk(folder, depth):
        try:
            children = sorted((child for child in folder.iterdir() if child.is_dir() and not child.is_symlink()),
                              key=lambda p: p.name.lower())
        except OSError:
            return
        for child in children:
            seen[0] += 1
            if seen[0] > PROBE_MAX_FOLDERS:
                return
            if skip_reason(child.name) is not None:
                continue
            if has_kit(child):
                if not (child.name.lower() in KIT_COPY_NAMES and not (child / '.caiman').is_dir()):
                    key = rel(root, child.parent)
                    parents[key] = parents.get(key, 0) + 1
                continue
            if depth < PROBE_DEPTH:
                walk(child, depth + 1)

    walk(root, 1)
    return [{'folder': key, 'brands': count}
            for key, count in sorted(parents.items(), key=lambda item: (item[0].count('/'), item[0]))]


def deeper_words(root, deeper):
    """A plain sentence saying where the business folders are when they are deeper than MAX_DEPTH levels."""
    places = names(['{} ({})'.format(item['folder'], plural(item['brands'], 'business folder')) for item in deeper[:3]])
    return ("There's no business folder within three levels of {}, but there are some further down: {}. Open the folder "
            'that holds the brand folders ({}) as the workspace, or use it as --workspace. Never install a kit in this '
            'folder for that.'.format(root, places, root / deeper[0]['folder']))


def rel(root, path):
    try:
        text = Path(path).relative_to(root).as_posix()
    except ValueError:
        return str(path)
    return text or '.'


# ---------------------------------------------------------------- a brand's identity, from its own files

def folder_tier(folder):
    tier = norm_tier(as_dict(read_json(folder / 'ENTITLEMENTS.json')).get('plan_tier'))
    if tier:
        return tier
    manifest = as_dict(read_json(folder / 'RELEASE_MANIFEST.json'))
    tier = norm_tier(manifest.get('kit')) or norm_tier(manifest.get('tier'))
    if tier:
        return tier
    pointer = as_dict(read_json(folder / '.caiman' / 'active-guidance.json'))
    return norm_tier(pointer.get('tier'))


def machine_folder(folder):
    usual, nested = folder / MACHINE_DIR, folder / NESTED_MACHINE_DIR
    usual_is_machine = usual.is_dir() and any((usual / name).exists() for name in MACHINE_FILES)
    if not usual_is_machine and (nested / 'config' / 'brand.json').is_file() and (nested / 'state' / 'workspace.json').is_file():
        return nested, NESTED_MACHINE_DIR
    return usual, MACHINE_DIR


def source_identities(folder):
    found = []
    pointer = as_dict(read_json(folder / '.caiman' / 'active-source-index.json'))
    if isinstance(pointer.get('identity'), dict):
        found.append(pointer['identity'])
    target = pointer.get('path')
    if isinstance(target, str) and target.strip() and '..' not in target.replace('\\', '/').split('/') \
            and not target.startswith(('/', '\\')) and ':' not in target:
        found.append(as_dict(as_dict(read_json(folder / target)).get('identity')))
    if text_value(pointer.get('account_id')):
        found.append({'account_id': pointer['account_id']})
    found.append(as_dict(as_dict(read_json(folder / 'SOURCE_CAPTURES.json')).get('identity')))
    return [item for item in found if item]


def brand_scope_state(machine):
    """The VIP Machine's brand scope choice, from its own files: 'brand' (just this brand's products in a shared seller
    account), 'whole account' (the member chose the whole account), 'saved' (a choice is saved but can't be read here)
    or 'not saved' (no choice yet: the VIP Machine counts every product in the seller account)."""
    history = machine / 'state' / 'brand_scope_history.jsonl'
    current = machine / 'state' / 'brand_scope.json'
    mode = None
    for line in (read_text(history, 16 * 1024 * 1024) or '').splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        mode = as_dict(as_dict(row).get('current')).get('mode') or mode
    if mode is None:
        mode = as_dict(as_dict(read_json(current)).get('scope')).get('mode')
    if mode == 'brand_in_account':
        return 'brand'
    if mode == 'whole_account':
        return 'whole account'
    return 'saved' if history.exists() or current.exists() else 'not saved'


def recorded_currency(folder):
    saved = as_dict(as_dict(read_json(folder / '.caiman' / 'plan' / 'state.json')).get('settings')).get('currency')
    if isinstance(saved, str) and re.fullmatch(r'[A-Z]{3}', saved):
        return saved
    return None


def guide_folder(folder):
    """The folder whose kit scripts belong to the current kit (CAIMAN_CURRENT.md names it; usually the business folder)."""
    text = read_text(folder / 'CAIMAN_CURRENT.md', 256 * 1024) or ''
    match = re.search(r'^\s*Guide folder:\s*`?([^`\n(]+?)`?\s*(?:\(|$)', text, re.M)
    if match:
        named = match.group(1).strip()
        if named not in ('', '.'):
            parts = [part for part in named.replace('\\', '/').split('/') if part not in ('', '.')]
            if parts and '..' not in parts and not named.startswith(('/', '\\')) and ':' not in named:
                candidate = folder.joinpath(*parts)
                if (candidate / 'CLIENT_START.py').is_file():
                    return candidate
    return folder


def identity(root, folder):
    """What this business folder is, from its own files (never the connector)."""
    tier = folder_tier(folder)
    manifest = as_dict(read_json(folder / 'RELEASE_MANIFEST.json'))
    kit_version = text_value(manifest.get('version'))
    core = text_value(manifest.get('core_version')) or text_value(as_dict(manifest.get('plugin')).get('version'))
    layout = 'in-folder'
    if not manifest and (folder / '.caiman' / 'active-guidance.json').is_file():
        layout = 'side-by-side'
    machine, machine_rel = machine_folder(folder)
    config = as_dict(read_json(machine / 'config' / 'brand.json'))
    brand = as_dict(config.get('brand'))
    market = as_dict(config.get('marketplace'))
    accounts = as_dict(config.get('account_identity'))
    gls = as_dict(as_dict(read_json(folder / 'GLS_PLUS_CONFIG.json')).get('identity')) if tier != 'vip' else {}
    sources = source_identities(folder)

    def first(*values):
        return next((value for value in (text_value(item) for item in values) if value), None)

    slug, slug_from = text_value(brand.get('slug')), machine_rel + '/config/brand.json' if text_value(brand.get('slug')) else None
    if slug and (machine / 'state' / 'connector_binding.json').is_file() and linked_slug(machine, config):
        # A VIP Machine set up under another name: connector calls use the slug linked to it.
        slug, slug_from = linked_slug(machine, config), machine_rel + '/state/connector_binding.json'
    if not slug:
        for item in sources:
            candidate = text_value(item.get('source_brand_slug')) or text_value(item.get('account_id'))
            if candidate and slug_shaped(candidate) and not candidate.startswith('local-'):
                slug, slug_from = candidate, 'saved source list'
                break
    name = first(brand.get('name'), gls.get('brand_name'), *[item.get('account_label') for item in sources])
    marketplace = first(market.get('country_code'), market.get('id'), gls.get('marketplace'),
                        *[item.get('marketplace') for item in sources])
    currency = first(market.get('currency'), gls.get('currency'), recorded_currency(folder),
                     *[item.get('currency') for item in sources])
    machine_state = 'not part of GLS+' if tier == 'gls-plus' else None
    if machine_state is None:
        if not machine.is_dir() or not any((machine / item).exists() for item in MACHINE_FILES):
            machine_state = ('not used outside US dollars' if currency and currency.upper() != 'USD'
                             else 'not set up')
        elif not (machine / 'config' / 'brand.json').is_file() or not (machine / 'state' / 'workspace.json').is_file():
            machine_state = 'setup unfinished'
        elif as_dict(read_json(machine / 'state' / 'workspace.json')).get('bootstrap') is True:
            machine_state = 'setup unfinished'
        else:
            machine_state = 'set up'
    return {
        'name': name or folder.name, 'name_saved': bool(name), 'folder': rel(root, folder),
        'slug': slug, 'slug_from': slug_from, 'marketplace': marketplace, 'currency': currency,
        'seller_id': first(accounts.get('seller_id'), gls.get('seller_id')),
        'ads_profile_id': first(accounts.get('profile_id'), gls.get('ads_profile_id')),
        'tier': tier, 'tier_name': TIER_NAMES.get(tier, 'Caiman'),
        'kit_version': kit_version, 'kit_core_version': core, 'kit_layout': layout,
        'vip_machine': machine_state,
        'vip_machine_folder': machine_rel if machine_state in ('set up', 'setup unfinished') else None,
        'brand_scope': brand_scope_state(machine) if machine_state == 'set up' else None,
    }


def brand_ids(brands):
    """A short, stable ID for each brand: its folder's name, made unique with its parent folders when needed."""
    taken = {}
    for brand in brands:
        parts = brand['folder'].split('/') if brand['folder'] != '.' else [brand.get('name') or 'this-folder']
        for size in range(1, len(parts) + 1):
            candidate = slugify('-'.join(parts[-size:]))
            if candidate not in taken:
                break
        else:
            candidate = slugify(brand['folder']) + '-' + str(len(taken) + 1)
        taken[candidate] = brand
        brand['id'] = candidate
    return brands


def compare_kit(core, plugin):
    have, need = parse_version(core or ''), parse_version(plugin or '')
    if have is None:
        return 'older'
    if need is None:
        return 'unknown'
    return 'older' if have < need else ('newer' if have > need else 'current')


def alerts_for(brands, plugin):
    """Two folders bound to one brand, brands sharing a seller account or Ads profile, and kits that need updating."""
    alerts = []
    by_slug = {}
    for brand in brands:
        if brand.get('slug'):
            by_slug.setdefault(brand['slug'], []).append(brand)
    duplicates = set()
    for slug, group in sorted(by_slug.items()):
        if len(group) > 1:
            duplicates.update(brand['id'] for brand in group)
            alerts.append({
                'code': 'same-brand-two-folders', 'level': 'problem', 'brands': [brand['id'] for brand in group],
                'member_line': '{} is set up in {} folders ({}). Each brand belongs in one business folder.'.format(
                    group[0]['name'], len(group), names([brand['folder'] for brand in group])),
                'next_step': "These folders are bound to the same connector brand slug ({}). Ask the member which folder is "
                             "the current one for this brand; with their OK, move the other out of the workspace. Until "
                             "then, don't run work for this brand in either folder from an all-brands run.".format(slug)})
    by_name = {}
    for brand in brands:
        if brand['id'] in duplicates or not brand.get('name_saved'):
            continue
        by_name.setdefault((name_key(brand['name']), (brand.get('marketplace') or '').upper()), []).append(brand)
    for (key, market), group in sorted(by_name.items()):
        slugs = {brand.get('slug') for brand in group}
        if len(group) > 1 and key and (None in slugs or len(slugs) < len(group)):
            alerts.append({
                'code': 'looks-like-same-brand', 'level': 'attention', 'brands': [brand['id'] for brand in group],
                'member_line': '{} folders ({}) look like the same brand, {}.'.format(
                    len(group), names([brand['folder'] for brand in group]), group[0]['name']),
                'next_step': 'They save the same brand name and marketplace. Ask the member whether they are one brand; if '
                             'so, keep one folder for it.'})
    for key, label in (('seller_id', 'seller account'), ('ads_profile_id', 'Ads profile')):
        groups = {}
        for brand in brands:
            if brand.get(key) and brand['id'] not in duplicates:
                groups.setdefault(brand[key], []).append(brand)
        for value, group in sorted(groups.items()):
            if len(group) > 1:
                alerts.append({
                    'code': 'shared-' + ('seller-account' if key == 'seller_id' else 'ads-profile'), 'level': 'attention',
                    'brands': [brand['id'] for brand in group],
                    'member_line': '{} share one {}. Reports from that account cover all of their products, so each '
                                   "brand's work uses only its own products.".format(names([b['name'] for b in group]),
                                                                                     label),
                    'next_step': ('These brands save the same {} ({}). Read and propose only for each brand\'s own products '
                                  'in its own folder. On VIP, limit each brand\'s VIP Machine to its own products with its '
                                  'brand scope (the VIP Machine\'s README, "Brand scope"): vip_machine.py brand-scope-check '
                                  'with the account\'s saved listings and variation families (search_listings and '
                                  'get_variation_family, that brand\'s slug), the member confirms which families are the '
                                  'brand\'s, then change-settings --brand-scope <file> --reason "<their words>" (or '
                                  '--whole-account). Until a choice is saved, that brand\'s weekly review counts every '
                                  'product in the account.').format(label, value)})
    for brand in brands:
        verdict = compare_kit(brand.get('kit_core_version'), plugin)
        brand['kit_vs_plugin'] = verdict
        if verdict == 'older' and brand.get('kit_layout') != 'unknown':
            alerts.append({
                'code': 'kit-older', 'level': 'attention', 'brands': [brand['id']],
                'member_line': "{}'s kit is older than this Caiman plugin and needs an update.".format(brand['name']),
                'next_step': 'Update it with kit-sync ("Update all my brands" does every brand: the kit-sync skill, "Every '
                             'brand in a workspace").'})
        elif verdict == 'newer':
            alerts.append({
                'code': 'kit-newer', 'level': 'attention', 'brands': [brand['id']],
                'member_line': "{}'s kit is newer than this Caiman plugin; the plugin needs an update.".format(brand['name']),
                'next_step': 'Suggest the member updates the Caiman plugin. The kit can stay.'})
    return alerts


def brand_scope_alerts(brands):
    """VIP brands that share their seller account or Ads profile with another brand here and whose VIP Machine has no
    brand scope saved (Caiman 0.3.17): that VIP Machine counts every product in the account, the other brand's too.
    One alert per brand, with the one step that fixes it. A brand set up in two folders is left to that alert."""
    by_slug = {}
    for brand in brands:
        if brand.get('slug'):
            by_slug.setdefault(brand['slug'], []).append(brand['id'])
    duplicates = {item for group in by_slug.values() if len(group) > 1 for item in group}
    alerts = []
    for brand in brands:
        if brand.get('tier') != 'vip' or brand.get('brand_scope') != 'not saved' or brand['id'] in duplicates:
            continue
        shared = []
        for key, label in (('seller_id', 'seller account'), ('ads_profile_id', 'Ads profile')):
            others = [item['name'] for item in brands if item['id'] != brand['id'] and item['id'] not in duplicates
                      and brand.get(key) and item.get(key) == brand.get(key)]
            if others:
                shared.append((label, others))
        if not shared:
            continue
        label, others = shared[0]
        everyone = names(sorted({name for item in shared for name in item[1]}))
        alerts.append({
            'code': 'shared-account-no-brand-scope', 'level': 'attention', 'brands': [brand['id']],
            'member_line': ("{} shares its {} with {}, and its VIP Machine has no brand scope saved, so its weekly review "
                            "counts every product in that account, {}'s too. One step fixes it: save {}'s brand scope "
                            "(which products are this brand's).").format(brand['name'], label, names(others), everyone,
                                                                         brand['name']),
            'next_step': ("In {}'s own folder, save its brand scope (the VIP Machine's README, \"Brand scope\"): "
                          'save the account\'s listings and variation families with that brand\'s slug (search_listings, '
                          'every page, and get_variation_family), run vip_machine.py brand-scope-check with them, the '
                          'member confirms which families are the brand\'s, then change-settings --brand-scope <file> '
                          '--reason "<their words>" (or --whole-account if the member wants the VIP Machine to cover the '
                          'whole seller account). Until then its proposals and results can include {}\'s '
                          'products.').format(brand['name'], everyone)})
    return alerts


def scan(root, plugin):
    folders, skipped = discover(root)
    brands = [identity(root, folder) for folder in folders]
    root_alerts = []
    if has_kit(root):
        brands.insert(0, identity(root, root))
        root_alerts.append({
            'code': 'workspace-is-business-folder', 'level': 'attention', 'brands': [],
            'member_line': 'This folder is itself a business folder. It works, but each brand is easier to keep apart in '
                           'its own folder below this one.',
            'next_step': "Treat this folder's own kit as one more brand. Don't move anything without the member's OK."})
    brand_ids(brands)
    return brands, skipped, root_alerts + alerts_for(brands, plugin)


# The Claude app's device bridge (a Linux workspace on the member's computer) mounts each connected folder at
# $HOME/mnt/<folder name>, with $HOME a /sessions/<session id> folder that changes every session. A path written for a later
# session or a scheduled task uses $HOME (Caiman 0.3.24): /sessions/<id>/mnt/<name>/... won't exist on the task's next run.
SESSION_MOUNT = re.compile(r'^/sessions/[^/]+/mnt/([^/]+)((?:/.*)?)$')


def portable_path(path):
    """A path as a later session or a scheduled task can use it: $HOME/mnt/<name>/... for a folder the device bridge
    mounted for this session (/sessions/<id>/mnt/<name>/...), else the path as it is."""
    text = str(path)
    match = SESSION_MOUNT.match(text) if text.startswith('/sessions/') else None
    return '$HOME/mnt/' + match.group(1) + match.group(2) if match else text


def home_expanded(value):
    """value with a leading $HOME (or ${HOME}) as this session's home folder, for a path passed on without a shell."""
    match = re.match(r'^\$(?:HOME|\{HOME\})(?=/|$)', value)
    return os.path.expanduser('~') + value[match.end():] if match else value


def workspace_root(value):
    root = Path(os.path.abspath(os.path.expanduser(home_expanded((value or '').strip()) or '.')))
    if not root.is_dir():
        raise WorkspaceError("There's no folder at {}. Check the path of the folder that holds the brand folders.".format(
            root))
    return root


def saved_workspace(root):
    data = read_json(root / WORKSPACE_FILE)
    return data if isinstance(data, dict) and data.get('schema') == SCHEMA else None


def current_brands(root, plugin):
    """The brands as they are now: CAIMAN WORKSPACE.json's IDs are kept for folders it already lists."""
    brands, skipped, alerts = scan(root, plugin)
    saved = saved_workspace(root)
    if saved:
        known = {item.get('folder'): item.get('id') for item in saved.get('brands') or [] if isinstance(item, dict)}
        used = set()
        for brand in brands:
            if known.get(brand['folder']) and known[brand['folder']] not in used:
                old_id, new_id = brand['id'], known[brand['folder']]
                brand['id'] = new_id
                for alert in alerts:
                    alert['brands'] = [new_id if item == old_id else item for item in alert.get('brands', [])]
            used.add(brand['id'])
    return brands, skipped, alerts, saved


def pick_brands(brands, wanted):
    """The brands a --brands list names (ID, name, folder or connector slug, any case), in workspace order."""
    if not wanted:
        return list(brands)
    chosen = []
    for raw in [part.strip() for part in re.split(r'[,;\n]', wanted) if part.strip()]:
        key = name_key(raw)
        hits = [brand for brand in brands if key in (name_key(brand['id']), name_key(brand['name']),
                                                     name_key(brand['folder']), name_key(brand.get('slug')),
                                                     name_key(Path(brand['folder']).name))]
        if len(hits) != 1:
            raise WorkspaceError('{} "{}". The brands here are: {}.'.format(
                "More than one brand matches" if hits else 'No brand here matches', raw,
                '; '.join('{} ({})'.format(brand['name'], brand['id']) for brand in brands)))
        if hits[0] not in chosen:
            chosen.append(hits[0])
    return [brand for brand in brands if brand in chosen]


# ---------------------------------------------------------------- find and init

def public(brand):
    keys = ('id', 'name', 'folder', 'slug', 'marketplace', 'currency', 'seller_id', 'ads_profile_id', 'tier', 'tier_name',
            'kit_version', 'kit_core_version', 'kit_vs_plugin', 'vip_machine', 'vip_machine_folder', 'slug_from')
    return {key: brand.get(key) for key in keys}


def cmd_find(args):
    root = workspace_root(args.workspace)
    plugin = plugin_version(args.plugin_version)
    try:
        brands, skipped, alerts, saved = current_brands(root, plugin)
    except TooManyFolders as error:
        # A home or Dropbox folder: say where to open the workspace instead of searching it all (Caiman 0.3.17).
        return {'schema': SCHEMA, 'command': 'find', 'workspace': str(root), 'plugin_version': plugin,
                'status': 'too-many-folders', 'is_workspace': False, 'workspace_file': None, 'brands': [], 'deeper': [],
                'alerts': [], 'skipped': [], 'searched_at_most': DISCOVER_MAX_FOLDERS, 'member_message': str(error)}
    count = len(brands)
    deeper = deeper_business_folders(root) if count == 0 else []
    if count == 0 and deeper:
        message = deeper_words(root, deeper)
    elif count == 0:
        message = ("There are no Caiman business folders in this folder (Claude looked several levels down). Ask the "
                   "member which folder holds their brands' business folders; don't install a kit here for that.")
    else:
        message = 'This folder holds {}: {}.'.format(plural(count, 'business folder'), names(
            ['{} ({})'.format(brand['name'], brand['tier_name']) for brand in brands]))
    return {'schema': SCHEMA, 'command': 'find', 'workspace': str(root), 'plugin_version': plugin,
            'is_workspace': count >= 2 or saved is not None, 'workspace_file': WORKSPACE_FILE if saved else None,
            'brands': [public(brand) for brand in brands], 'deeper': deeper, 'alerts': alerts, 'skipped': skipped,
            'member_message': message + ('' if not alerts else ' ' + ' '.join(alert['member_line'] for alert in alerts))}


def workspace_section(brands):
    lines = [SECTION_START, '# Caiman workspace: {}'.format(plural(len(brands), 'brand')), '',
             'This folder holds the business folders of {}. Each brand keeps its own folder, kit and Amazon account; '
             'nothing moves.'.format(plural(len(brands), 'brand')), '',
             '| Brand | Business folder | Connector brand slug | Membership |', '|---|---|---|---|']
    for brand in brands:
        lines.append('| {} | `{}` | {} | {} |'.format(brand['name'].replace('|', '/'), brand['folder'],
                                                     brand.get('slug') or 'not saved yet', brand['tier_name']))
    lines += [
        '',
        "- **All brands, or several:** follow the caiman skill's workspace guide (`references/workspace.md`). Run the "
        "workflow with the skill's `workspace.py run`: one brand at a time, each in its own business folder with its own "
        "account, ending with one combined summary. Finish a brand and save its summary before starting the next.",
        "- **One brand named:** work in that brand's business folder only, exactly as for a single business.",
        '- **A request for one brand that names none:** ask once: "Which brand, or all of them?"',
        "- **Never mix brands.** One brand's data, files and account IDs never go into another brand's work or folder. "
        "If one brand fails or needs the member's answer, the others carry on; list it at the end.",
        "- **Approvals stay per brand.** Every account change still needs the member's go for that brand's exact change.",
        '- `{}` lists the messages to use; `{}` has the brands and their saved accounts.'.format(START_FILE,
                                                                                               WORKSPACE_FILE),
        SECTION_END]
    return '\n'.join(lines)


def merge_section(existing, section):
    """(new text, what happened). Only the workspace section is replaced; text outside it stays exactly as it was,
    and the section uses the file's own line endings."""
    if existing is None:
        return section + '\n', 'created'
    bom = '﻿' if existing.startswith('﻿') else ''       # a byte order mark stays at the very start
    text = existing[len(bom):]
    newline = '\r\n' if '\r\n' in text else '\n'
    body = section.replace('\n', newline)
    # As kit-sync does for its own section: an END belongs to the START before it only when no other START comes
    # between them, so a stray START line above the section never takes the member's text below it with it.
    starts = list(SECTION_START_RE.finditer(text))
    for index, start in enumerate(starts):
        limit = starts[index + 1].start() if index + 1 < len(starts) else len(text)
        end = SECTION_END_RE.search(text, start.end(), limit)
        if end:
            merged = bom + text[:start.start()] + body + text[end.end():]
            return merged, ('unchanged' if merged == existing else 'updated the workspace section')
    return bom + body + newline + newline + text, 'added the workspace section above your notes'


def start_text(brands):
    lines = ['# Your brands in one place', '',
             'This folder holds {}, each in its own business folder: {}. Ask Claude here and it works through the brands '
             "one at a time, each in its own folder and Amazon account, then gives you one summary.".format(
                 plural(len(brands), 'brand'), names([brand['name'] for brand in brands])), '',
             '## Messages to use', '',
             '| Say | What happens |', '|---|---|',
             '| "What\'s next across my brands?" | One plan for all your brands, most important first, each step labeled '
             'with its brand. |',
             '| "Run the Weekly Growth Review for all my brands." | Each brand\'s review in turn, then one summary. |',
             '| "Run the Advertising Daily Check for all my brands." | Each brand\'s daily check in turn, then one note. |',
             '| "Run the Advertising Weekly Review for {}." | Just that brand, in its own folder. |'.format(
                 brands[0]['name'] if brands else 'one brand'),
             '| "Update all my brands." | Each brand\'s kit updated in turn, keeping your files. |',
             '| "Check setup for all my brands." | The setup check for each brand. |',
             '| "Show me all my brands." | One page with each brand\'s latest numbers, results due, what has worked and '
             'what\'s waiting on you. |',
             '| "Continue." | A run that stopped picks up at the next brand. |', '',
             '## Good to know', '',
             "- Each brand keeps its own folder, files and Amazon account. One brand's data never goes into another's.",
             '- If one brand fails or needs your answer, the others carry on, and it\'s listed at the end.',
             '- Every change to an Amazon account still waits for your go, brand by brand.',
             '- Scheduled tasks: one task per routine covers all your brands (for example the daily ads check). Each stays '
             'off until you approve it, and they never change your accounts.',
             '- A new brand: make its folder here, set it up as usual, then say "Add my new brand to the workspace."', '']
    return '\n'.join(lines)


def cmd_init(args):
    root = workspace_root(args.workspace)
    plugin = plugin_version(args.plugin_version)
    brands, skipped, alerts, saved = current_brands(root, plugin)
    if not brands:
        deeper = deeper_business_folders(root)
        raise WorkspaceError(deeper_words(root, deeper) if deeper else (
            "There are no Caiman business folders in {} (Claude looked several levels down), so there's no workspace "
            "to set up. Ask the member which folder holds their brands' business folders.".format(root)))
    moment = stamp()
    previous = {item.get('folder'): item for item in (saved or {}).get('brands') or [] if isinstance(item, dict)}
    records = []
    for brand in brands:
        record = public(brand)
        record['added_at'] = (previous.get(brand['folder']) or {}).get('added_at') or moment
        records.append(record)
    found_now = {brand['folder'] for brand in brands}
    gone = [{'id': item.get('id'), 'name': item.get('name'), 'folder': folder, 'last_seen': (saved or {}).get('updated_at')}
            for folder, item in previous.items() if folder not in found_now]
    new = [brand for brand in brands if brand['folder'] not in previous]
    data = {'schema': SCHEMA,
            'about': ("Caiman workspace: the business folders of one member's brands under this folder. workspace.py init "
                      "refreshes it. Each brand's work happens in its own folder with its own account."),
            'created_at': (saved or {}).get('created_at') or moment, 'updated_at': moment, 'plugin_version': plugin,
            'brands': records, 'no_longer_found': gone + [item for item in (saved or {}).get('no_longer_found') or []
                                                         if isinstance(item, dict) and item.get('folder') not in found_now
                                                         and item.get('folder') not in previous],
            'alerts': alerts, 'skipped': skipped,
            'routines': (saved or {}).get('routines') if isinstance((saved or {}).get('routines'), dict) else {}}
    claude_path = root / CLAUDE_FILE
    existing = None
    if claude_path.exists() or claude_path.is_symlink():
        if claude_path.is_symlink() or not claude_path.is_file():
            raise WorkspaceError('Something that is not a normal file is named CLAUDE.md in {}, so the workspace section '
                                 "wasn't added. Ask the member before moving it.".format(root))
        raw = claude_path.read_bytes()
        if raw.startswith((b'\xff\xfe', b'\xfe\xff')) or b'\x00' in raw[:4096]:
            raise WorkspaceError("CLAUDE.md in {} isn't saved as UTF-8 text (it looks like UTF-16), so the workspace "
                                 "section wasn't added: it would mix two kinds of text in one file. Nothing was "
                                 'written. Ask the member before saving it again as UTF-8.'.format(root))
        existing = raw.decode('utf-8', 'surrogateescape')
    write_json(root / WORKSPACE_FILE, data)
    merged, how = merge_section(existing, workspace_section(brands))
    if how != 'unchanged':
        write_atomic(claude_path, merged.encode('utf-8', 'surrogateescape'))
    write_atomic(root / START_FILE, start_text(brands).encode('utf-8'))
    lines = ['The workspace is set up with {}: {}.'.format(plural(len(brands), 'brand'),
                                                           names([brand['name'] for brand in brands]))]
    if saved and new:
        lines.append('New since last time: {}.'.format(names([brand['name'] for brand in new])))
    if gone:
        lines.append('No longer found: {} (moved or renamed?).'.format(names([item['name'] or item['folder']
                                                                               for item in gone])))
    lines += [alert['member_line'] for alert in alerts]
    return {'schema': SCHEMA, 'command': 'init', 'workspace': str(root), 'status': 'refreshed' if saved else 'created',
            'workspace_file': WORKSPACE_FILE, 'claude_md': how, 'start_file': START_FILE,
            'brands': records, 'new_brands': [brand['id'] for brand in new] if saved else [],
            'no_longer_found': gone, 'alerts': alerts, 'skipped': skipped, 'member_message': ' '.join(lines)}


# ---------------------------------------------------------------- status

def kit_status(folder, seconds=SHORT_SECONDS):
    """kit-sync status for one folder (JSON), or None with why."""
    program = kit_sync_program()
    if program is None:
        return None, 'kit-sync is not next to the caiman skill'
    code, out, err, failed = run_program([python(), '-B', str(program), 'status', '--folder', str(folder), '--json'],
                                         folder, seconds)
    data = json_from(out)
    if failed or not data or data.get('status') in (None, 'error'):
        return None, failed or one_line((data or {}).get('message') or err or out, 200)
    return data, None


def setup_step(folder, tier, seconds=SHORT_SECONDS):
    """The kit's own setup helper's answer (GUIDED_SETUP.py or GLS_GUIDED_SETUP.py status, which only read)."""
    guide = guide_folder(folder)
    program = guide / ('GUIDED_SETUP.py' if tier == 'vip' else 'GLS_GUIDED_SETUP.py')
    if not program.is_file():
        return None, 'the kit has no {}'.format(program.name)
    code, out, err, failed = run_program([python(), '-B', str(program), 'status', '--project-root', str(folder)], folder,
                                         seconds)
    data = json_from(out)
    if failed or not data:
        return None, failed or 'its answer could not be read'
    action = as_dict(data.get('setup_next_action')) or as_dict(data.get('next_action'))
    summary = text_value(as_dict(data.get('client_delivery')).get('setup_summary'))
    return {'code': text_value(action.get('code')), 'summary': summary,
            'member_next': text_value(action.get('client_next'))}, None


def results_due(folder, seconds=SHORT_SECONDS):
    guide = guide_folder(folder)
    program = guide / 'MEASURE_CHANGES.py'
    if not program.is_file():
        return None, 'the kit has no MEASURE_CHANGES.py'
    code, out, err, failed = run_program([python(), '-B', str(program), 'due', '--brief', '--project-root', str(folder)],
                                         folder, seconds)
    data = json_from(out) or json_from(err)
    if failed or not data or data.get('status') != 'ok':
        return None, failed or one_line((data or {}).get('error') or err or out, 300)
    return {key: data.get(key) for key in ('due', 'overdue', 'waiting', 'measured', 'oldest_due_on') if key in data}, None


def last_weekly_close(folder, machine_rel):
    """The newest weekly review recorded: a week the VIP Machine closed, or a Weekly Growth Review NEXT_STEP.py recorded."""
    moments = []
    if machine_rel:
        log = folder / machine_rel / 'runs' / 'run_receipts.jsonl'
        text = read_text(log, 64 * 1024 * 1024) or ''
        for line in text.splitlines():
            try:
                row = json.loads(line)
            except ValueError:
                continue
            closed = parse_time(as_dict(row).get('closed_at'))
            if closed:
                moments.append(closed)
    state = as_dict(read_json(folder / '.caiman' / 'plan' / 'state.json'))
    for item in as_dict(state.get('items')).values():
        item = as_dict(item)
        if item.get('workflow') in ('weekly-growth-review', 'advertising-weekly-review') and item.get('status') in (
                'delivered', 'complete', 'applied', 'measured'):
            moment = parse_time(item.get('delivered_at'))
            if moment:
                moments.append(moment)
    return max(moments) if moments else None


def saved_setup_headline(folder):
    text = read_text(folder / 'CAIMAN STATUS.md', 256 * 1024) or ''
    match = re.search(r'^\*\*(.+?)\*\*\s*$', text, re.M)
    when = re.search(r'^Checked on (.+?) \(', text, re.M)
    return (match.group(1).strip() if match else None), (when.group(1).strip() if when else None)


def machine_health(folder, machine_rel):
    if not machine_rel:
        return None
    data = as_dict(read_json(folder / machine_rel / 'health' / 'status.json'))
    status = text_value(data.get('status')) or text_value(data.get('overall_status'))
    return {'status': status, 'checked_at': data.get('checked_at') or data.get('generated_at')} if status else None


def has_business_view(folder):
    reviews = folder / 'Reviews'
    if not reviews.is_dir():
        return False
    for current, subfolders, files in os.walk(str(reviews)):
        if 'operating-view.json' in files or ('review-receipt.json' in files and 'dashboard.json' in files):
            return True
    return False


def brand_status(root, brand, plugin, quick=False):
    folder = root / brand['folder'] if brand['folder'] != '.' else root
    row = {'id': brand['id'], 'name': brand['name'], 'folder': brand['folder'], 'tier': brand['tier'],
           'tier_name': brand['tier_name'], 'alerts': []}
    kit, why = (None, 'skipped') if quick else kit_status(folder)
    if kit:
        verdict = kit.get('status')
        row['kit'] = {'version': brand.get('kit_version'), 'core_version': brand.get('kit_core_version'),
                      'status': verdict, 'needs_update': verdict not in ('current', 'newer', 'skills-blocked',
                                                                         'skills-locked')}
    else:
        verdict = brand.get('kit_vs_plugin') or compare_kit(brand.get('kit_core_version'), plugin)
        row['kit'] = {'version': brand.get('kit_version'), 'core_version': brand.get('kit_core_version'),
                      'status': verdict, 'needs_update': verdict == 'older', 'checked_by': 'versions only: ' + why}
    if row['kit']['needs_update']:
        row['alerts'].append('kit needs an update')
    elif row['kit']['status'] == 'newer':
        row['alerts'].append('the Caiman plugin needs an update')
    setup, why = (None, 'skipped') if quick else setup_step(folder, brand['tier'])
    row['setup'] = setup or {'code': None, 'summary': None, 'not_checked': why}
    row['deep_seed_done'] = has_business_view(folder)
    row['vip_machine'] = brand['vip_machine']
    health = machine_health(folder, brand.get('vip_machine_folder'))
    if health:
        row['vip_machine_health'] = health
        if health['status'] not in ('healthy', 'ok', 'ready'):
            row['alerts'].append('VIP Machine health: {}'.format(health['status']))
    closed = last_weekly_close(folder, brand.get('vip_machine_folder'))
    row['last_weekly_close'] = stamp(closed) if closed else None
    due, why = (None, 'skipped') if quick else results_due(folder)
    row['results'] = due or {'not_checked': why}
    if due and due.get('due'):
        row['alerts'].append('{} due'.format(plural(due['due'], 'result')))
    headline, when = saved_setup_headline(folder)
    if headline:
        row['last_setup_check'] = {'headline': headline, 'checked': when}
        if not headline.lower().startswith("everything's working"):
            row['alerts'].append('setup check: ' + headline.rstrip('.'))
    last = as_dict(read_json(folder / '.caiman' / 'plan' / 'last-plan.json', 16 * 1024 * 1024))
    waiting = [item for item in last.get('waiting_on_member') or [] if isinstance(item, dict)]
    if waiting:
        row['waiting_on_member'] = [one_line(item.get('title'), 120) for item in waiting]
        row['alerts'].append('{} waiting for your decision'.format(plural(len(waiting), 'proposal')))
    return row


def short_alert(alert, brand_id, by_id):
    """A workspace alert in a few words for one brand's row."""
    others = names([by_id[item]['name'] for item in alert.get('brands', []) if item != brand_id and item in by_id])
    code = alert['code']
    if code == 'same-brand-two-folders':
        return 'set up in more than one folder ({} too)'.format(others) if others else 'set up in more than one folder'
    if code == 'looks-like-same-brand':
        return 'may be the same brand as {}'.format(others)
    if code == 'shared-seller-account':
        return 'shares its seller account with {}'.format(others)
    if code == 'shared-ads-profile':
        return 'shares its Ads profile with {}'.format(others)
    if code == 'shared-account-no-brand-scope':
        return "no brand scope saved: its VIP Machine counts the other brand's products too"
    return alert['member_line'].rstrip('.')


def status_table(rows):
    lines = ['| Brand | Kit | Setup | VIP Machine | Last weekly review | Results due | Alerts |',
             '|---|---|---|---|---|---|---|']
    for row in rows:
        kit = row['kit']
        kit_text = '{}{}'.format(('v' + kit['version']) if kit.get('version') else 'no version',
                                 ', needs update' if kit.get('needs_update') else '')
        setup = row['setup'].get('summary') or row['setup'].get('code') or ('Deep Seed done' if row['deep_seed_done']
                                                                            else 'not checked')
        closed = parse_time(row.get('last_weekly_close'))
        due = row['results']
        due_text = 'not checked' if 'not_checked' in due else str(due.get('due') or 0)
        lines.append('| {} | {} | {} | {} | {} | {} | {} |'.format(
            row['name'].replace('|', '/'), kit_text, one_line(setup, 80).replace('|', '/'), row['vip_machine'],
            plain_date(closed) if closed else 'none yet', due_text,
            '; '.join(row['alerts']).replace('|', '/') or 'none'))
    return '\n'.join(lines)


def cmd_status(args):
    root = workspace_root(args.workspace)
    plugin = plugin_version(args.plugin_version)
    brands, skipped, alerts, saved = current_brands(root, plugin)
    scope_alerts = brand_scope_alerts(brands)
    brands = pick_brands(brands, args.brands)
    rows = [brand_status(root, brand, plugin, args.quick) for brand in brands]
    by_id = {brand['id']: brand for brand in brands}
    for alert in alerts + scope_alerts:
        for row in rows:
            if row['id'] in alert.get('brands', []) and alert['code'] not in ('kit-older', 'kit-newer'):
                row['alerts'].append(short_alert(alert, row['id'], by_id))
    flagged = [row for row in rows if row['alerts']]
    message = ('{}: {}.'.format(plural(len(rows), 'brand'), "nothing needs attention" if not flagged else
                                '; '.join('{}: {}'.format(row['name'], ', '.join(row['alerts'][:3])) for row in flagged)))
    return {'schema': SCHEMA, 'command': 'status', 'workspace': str(root), 'plugin_version': plugin, 'brands': rows,
            'alerts': alerts, 'table_markdown': status_table(rows), 'member_message': message,
            'workspace_file': WORKSPACE_FILE if saved else None}


# ---------------------------------------------------------------- plan

KIND_RANK = {'continue': 1, 'measure': 2, 'setup': 3}


def next_step(folder, seconds):
    guide = guide_folder(folder)
    program = guide / 'NEXT_STEP.py'
    if not program.is_file():
        return None, "this brand's kit has no NEXT_STEP.py (it's older than Caiman 0.3.6); update the kit first"
    code, out, err, failed = run_program([python(), '-B', str(program), '--project-root', str(folder)], folder, seconds)
    data = json_from(out)
    if failed:
        return None, 'NEXT_STEP.py ' + failed
    if not data or data.get('status') != 'NEXT_STEP_READY':
        return None, 'NEXT_STEP.py needs attention: ' + one_line((data or {}).get('error') or err or out, 300)
    return data, None


def plan_step(brand, item, position):
    kind = item.get('kind') or 'work'
    rank = KIND_RANK.get(kind, 4)
    if kind == 'measure' and item.get('overdue'):
        rank = 1.5
    return {'brand': brand['id'], 'brand_name': brand['name'], 'folder': brand['folder'], 'position': position,
            'kind': kind, 'class': rank, 'title': item.get('title'), 'why': item.get('why'),
            'workflow': item.get('workflow'), 'family': item.get('family'), 'goal': item.get('goal'),
            'what_you_get': item.get('what_you_get'), 'needs_from_member': item.get('needs_from_member') or [],
            'agent_command': item.get('agent_command')}


def brand_scope_step(alert, brands):
    """A plan step for a VIP brand that shares its account and has no brand scope saved (brand_scope_alerts): after
    kit updates, before each brand's own steps, because its weekly review counts every product in the account."""
    brand = next(item for item in brands if item['id'] == alert['brands'][0])
    return {'brand': brand['id'], 'brand_name': brand['name'], 'folder': brand['folder'], 'position': 0,
            'kind': 'brand-scope', 'class': 0.5, 'title': "Save {}'s brand scope".format(brand['name']),
            'why': alert['member_line'], 'workflow': None, 'family': None, 'goal': None,
            'what_you_get': ("{}'s VIP Machine works on its own products only: its proposals, totals and TACoS leave the "
                             "other brand's products out.").format(brand['name']),
            'needs_from_member': ["Confirm which product families are {}'s".format(brand['name'])], 'agent_command': None,
            'how': alert['next_step']}


def plan_scope(root, brand, folder):
    """For the plan (Caiman 0.3.17): a brand whose VIP Machine has a brand scope in force while the business view its
    plan was made from (NEXT_STEP.py's last-plan.json) covers the whole seller account or an earlier list of its
    products: {'covers', 'note', 'members', 'families' (family ID -> its ASINs)}. None otherwise."""
    scope = scope_in_force(root, brand)
    if (scope or {}).get('mode') != 'brand_in_account':
        return None
    last = as_dict(read_json(folder / '.caiman' / 'plan' / 'last-plan.json', 16 * 1024 * 1024))
    if not last.get('view'):
        return None
    covers, note = view_covers(scope, view_scope(folder, last), [], brand['name'])
    if covers not in ('whole account', 'earlier scope'):
        return None
    families = {}
    for family in as_dict(last.get('families')).get('families') or []:
        if isinstance(family, dict) and text_value(family.get('id')):
            families[str(family['id'])] = {item for item in family.get('asins') or [] if isinstance(item, str)}
    return {'covers': covers, 'note': note, 'members': scope['members'], 'families': families}


def scoped_items(brand, items, stale, left_out):
    """A brand's plan items without the ones for a product family wholly outside its brand scope (added to left_out
    with the reason). Items with no family, or a family the scope covers even in part, stay."""
    kept = []
    for item in items:
        family = text_value(item.get('family'))
        asins = stale['families'].get(family) if family else None
        if asins and not asins & stale['members']:
            left_out.append({'brand': brand['id'], 'brand_name': brand['name'], 'title': item.get('title'),
                             'family': family,
                             'why': ("its products aren't {}'s: they're outside its brand scope, and the business view "
                                     'the plan used was built before the scope was saved').format(brand['name'])})
            continue
        kept.append(item)
    return kept


def brand_scope_view_step(brand, folder, stale):
    """A plan step to refresh a brand's business view with its brand scope (plan_scope): before the brand's own steps,
    right after kit updates and saving brand scopes."""
    program = guide_folder(folder) / 'REFRESH_OPERATING_VIEW.py'
    command = command_line([str(program), '--project-root', str(folder)]) if program.is_file() else None
    return {'brand': brand['id'], 'brand_name': brand['name'], 'folder': brand['folder'], 'position': 0,
            'kind': 'brand-scope-view', 'class': 0.6,
            'title': "Refresh {}'s business view for just its own products".format(brand['name']),
            'why': stale['note'], 'workflow': None, 'family': None, 'goal': None,
            'what_you_get': ("{}'s plan and figures from its own products only, without the other products in its seller "
                             'account.').format(brand['name']),
            'needs_from_member': [], 'agent_command': command,
            'how': (("In {}'s folder, run REFRESH_OPERATING_VIEW.py (agent_command): it builds the business view again from "
                     'the reports already saved, with the brand scope, and reads nothing new. Then run its NEXT_STEP.py '
                     'again for its plan.').format(brand['name']) if command else
                    ("{}'s kit has no REFRESH_OPERATING_VIEW.py: update its kit with kit-sync, then refresh the business "
                     'view.').format(brand['name']))}


def cmd_plan(args):
    root = workspace_root(args.workspace)
    plugin = plugin_version(args.plugin_version)
    brands, skipped, alerts, saved = current_brands(root, plugin)
    picked = pick_brands(brands, args.brands)
    scope_alerts = [alert for alert in brand_scope_alerts(brands) if alert['brands'][0] in {b['id'] for b in picked}]
    brands = picked
    order = {brand['id']: index for index, brand in enumerate(brands)}
    steps, waiting, problems, stages, left_out = [], [], [], {}, []
    older = [brand for brand in brands if brand.get('kit_vs_plugin') == 'older']
    duplicates = {item: alert for alert in alerts if alert['code'] == 'same-brand-two-folders' for item in alert['brands']}
    for brand in brands:
        folder = root / brand['folder'] if brand['folder'] != '.' else root
        if brand['id'] in duplicates:
            # Like a run, the plan leaves out a brand set up in two folders: a step could send work to the wrong one.
            problems.append({'brand': brand['id'], 'brand_name': '{} ({})'.format(brand['name'], brand['folder']),
                             'why': duplicates[brand['id']]['member_line'] + ' Ask the member which folder is the '
                                    'current one; until then neither is planned.'})
            continue
        data, why = next_step(folder, args.timeout)
        if data is None:
            problems.append({'brand': brand['id'], 'brand_name': brand['name'], 'why': why})
            continue
        stages[brand['id']] = data.get('stage')
        items = ([data['next']] if isinstance(data.get('next'), dict) else []) + [
            item for item in data.get('queue') or [] if isinstance(item, dict)]
        # Caiman 0.3.17: a business view built before the brand's scope covers the whole seller account.
        stale = plan_scope(root, brand, folder)
        if stale:
            items = scoped_items(brand, items, stale, left_out)
            steps.append(brand_scope_view_step(brand, folder, stale))
        for position, item in enumerate(items[:args.per_brand]):
            step = plan_step(brand, item, position)
            if stale:
                step['figures_cover'] = 'whole seller account'
            steps.append(step)
        for item in data.get('waiting_on_member') or []:
            if isinstance(item, dict):
                waiting.append({'brand': brand['id'], 'brand_name': brand['name'], 'title': item.get('title'),
                                'since': item.get('since'), 'ask': item.get('ask'), 'stale': bool(item.get('stale'))})
    steps += [brand_scope_step(alert, brands) for alert in scope_alerts]
    steps.sort(key=lambda step: (step['position'] > 0, step['position'], step['class'], order[step['brand']]))
    if older:
        steps.insert(0, {'brand': None, 'brand_name': 'All brands', 'folder': '.', 'position': 0, 'kind': 'kit-update',
                         'class': 0, 'title': 'Update the kit in {}'.format(names([brand['name'] for brand in older])),
                         'why': "Their kits are older than this Caiman plugin, and each workflow runs on the brand's kit.",
                         'workflow': 'kit-update', 'family': None, 'goal': 'Update all my brands.',
                         'what_you_get': 'Each brand on the current kit, with every file you made kept.',
                         'needs_from_member': [], 'agent_command': None})
    waiting.sort(key=lambda item: (not item['stale'], item.get('since') or '', order[item['brand']]))
    for rank, step in enumerate(steps, 1):
        step['rank'] = rank
    moment = now()
    plan = {'schema': PLAN_SCHEMA, 'created_at': stamp(moment), 'workspace': str(root), 'brands': [
        {'id': brand['id'], 'name': brand['name'], 'folder': brand['folder'], 'stage': stages.get(brand['id'])}
        for brand in brands], 'steps': steps, 'waiting_on_member': waiting, 'not_planned': problems,
        'ordering': ('Kit updates first, then each brand\'s own next step (unfinished work, then results that are due, then '
                     'setup, then new work; brands in workspace order within each), then each brand\'s later steps in the '
                     'same way.' + (' A brand that shares its seller account and has no brand scope saved comes right '
                                    'after the kit updates.' if scope_alerts else ''))}
    view_steps = [step for step in steps if step['kind'] == 'brand-scope-view']
    if view_steps:
        plan['ordering'] += (" A brand whose business view was built before its brand scope gets a step to refresh it "
                             'first, and its steps for products outside the scope are left out.')
    if left_out:
        plan['left_out_by_brand_scope'] = left_out
    lines = ["# What's next across your brands", '', 'Worked out on {}, for {}.'.format(
        plain_time(moment), plural(len(brands), 'brand')), '']
    if waiting:
        lines += ['## Waiting on you', '']
        lines += ['- **{}**: {}{}{}'.format(item['brand_name'], item['title'] or 'a decision',
                                            ' (since {})'.format(plain_date(parse_time(item['since'])))
                                            if parse_time(item.get('since')) else '',
                                            ': ' + item['ask'] if item.get('ask') else '') for item in waiting]
        lines.append('')
    first = [step for step in steps if step['position'] == 0]
    later = [step for step in steps if step['position'] > 0]
    if first:
        lines += ['## Next, brand by brand', '']
        lines += ['{}. **{}**: {}{}'.format(step['rank'], step['brand_name'], step['title'],
                                            ' ({})'.format(one_line(step['why'], 220)) if step.get('why') else '')
                  for step in first]
        lines.append('')
    if later:
        lines += ['## After that', '']
        lines += ['{}. **{}**: {}'.format(step['rank'], step['brand_name'], step['title']) for step in later]
        lines.append('')
    if problems:
        lines += ["## Couldn't plan", '']
        lines += ['- **{}**: {}'.format(item['brand_name'], item['why']) for item in problems]
        lines.append('')
    if left_out:
        lines += ["## Left out: products outside a brand's scope", '']
        lines += ['- **{}**: {} ({})'.format(item['brand_name'], item['title'] or 'a step', item['why']) for item in left_out]
        lines.append('')
    lines += ['How this is ordered: ' + plan['ordering'], '']
    write_json(root / PLAN_JSON, plan)
    write_atomic(root / PLAN_MD, '\n'.join(lines).encode('utf-8'))
    top = steps[0] if steps else None
    message = ('Next across your brands: {}{}.'.format(
        '{}: {}'.format(top['brand_name'], top['title']) if top else 'nothing planned yet',
        '' if not waiting else '; {} waiting on you'.format(plural(len(waiting), 'decision'))))
    if problems:
        message += " Couldn't plan {}.".format(names([item['brand_name'] for item in problems]))
    answer = {'schema': PLAN_SCHEMA, 'command': 'plan', 'workspace': str(root), 'plan_file': PLAN_MD,
              'plan_json': PLAN_JSON, 'steps': steps, 'waiting_on_member': waiting, 'not_planned': problems,
              'alerts': alerts + scope_alerts, 'member_message': message,
              'how_to_continue': ('Offer the first step in plain words. When the member says yes, work in that step\'s brand '
                                  'folder only: run its agent_command there, or for the kit update use the kit-sync skill\'s '
                                  '"Every brand in a workspace"' + ('; for saving a brand scope, follow the step\'s how in '
                                                                    'that brand\'s folder.' if scope_alerts else '.'))}
    if left_out:
        answer['left_out_by_brand_scope'] = left_out
    if view_steps:
        answer['how_to_continue'] += (" A brand's figures marked figures_cover come from a business view built for the "
                                      "whole seller account: say so, and refresh it first (its brand-scope-view step).")
    return answer


# ---------------------------------------------------------------- run: one workflow across the brands, resumable

WORKFLOW_ALIASES = {
    'dailycheck': 'advertising-daily-check', 'dailyadscheck': 'advertising-daily-check',
    'adsdailycheck': 'advertising-daily-check', 'advertisingdaily': 'advertising-daily-check',
    'weeklyreview': 'weekly-growth-review', 'growthreview': 'weekly-growth-review', 'weekly': 'weekly-growth-review',
    'adsweeklyreview': 'advertising-weekly-review', 'advertising': 'advertising-weekly-review',
    'structurereview': 'advertising-structure-review', 'setup': 'setup-check',
    'weeklyloop': 'vip-weekly-loop', 'dailybrief': 'vip-daily-brief', 'healthcheck': 'vip-health-check',
    'opportunityreview': 'vip-opportunity-review', 'dreamingloop': 'vip-opportunity-review',
}
ROUTINE_TASKS = {'vip-weekly-loop': 'weekly_loop', 'vip-daily-brief': 'daily_brief', 'vip-health-check': 'health_check',
                 'vip-opportunity-review': 'dreaming_loop'}
# All-brands scheduled tasks: workflow -> suggested timing (the VIP Machine's own suggestions for its routines).
ROUTINE_TIMING = {
    'advertising-daily-check': 'Daily, 08:00', 'weekly-growth-review': 'Weekly on Monday, 09:00',
    'advertising-weekly-review': 'Weekly on Tuesday, 09:00', 'vip-daily-brief': 'Daily, 07:00',
    'vip-health-check': 'Daily, 07:30', 'vip-weekly-loop': 'Weekly on Monday, 09:00',
    'vip-opportunity-review': 'Weekly, after the weekly review, 11:00',
}


def workflow_key(value):
    """The WORKFLOWS key that a workflow argument names (its key or its name, any case), or None."""
    key = name_key(value)
    if not key:
        return None
    for name, (label, kind, first) in WORKFLOWS.items():
        if key in (name_key(name), name_key(label)):
            return name
    return WORKFLOW_ALIASES.get(key)


def run_file(root, name):
    return root / RUNS / (name + '.json')


def run_note_file(root, name):
    return root / RUNS / (name + '.md')


def brand_summary_file(root, name, brand_id):
    return root / RUNS / name / (brand_id + '.md')


def brand_folder(root, entry):
    folder = entry.get('folder') or '.'
    return root if folder == '.' else root.joinpath(*folder.split('/'))


def read_run(path):
    data = read_json(path, 16 * 1024 * 1024)
    if isinstance(data, dict) and data.get('schema') == RUN_SCHEMA and isinstance(data.get('brands'), list):
        return data
    return None


def all_runs(root):
    """[(path, run)] newest first."""
    found = []
    try:
        paths = sorted((root / RUNS).glob('*.json'))
    except OSError:
        paths = []
    for path in paths:
        data = read_run(path)
        if data:
            found.append((path, data))
    found.sort(key=lambda item: (item[1].get('started_at') or '', item[0].name), reverse=True)
    return found


def open_runs(root):
    return [(path, data) for path, data in all_runs(root) if data.get('status') == 'open']


def find_run(root, name=None, only_one=True):
    """(path, run): the run named, else the one unfinished run, else (None, None). With more than one unfinished run
    and no name it refuses (only_one) rather than guess: another chat or a scheduled task may own the other one."""
    if name and name.strip():
        name = name.strip()
        if name.lower().endswith('.json'):
            name = name[:-5]
        name = Path(name).name
        data = read_run(run_file(root, name))
        if not data:
            known = [data.get('name') for path, data in all_runs(root)][:8]
            raise WorkspaceError('There\'s no workspace run named "{}" here.{}'.format(
                name, ' Recent runs: {}.'.format('; '.join(known)) if known else ''))
        return run_file(root, name), data
    unfinished = open_runs(root)
    if len(unfinished) > 1 and only_one:
        raise WorkspaceError('{} runs across the brands are unfinished: {}. Name the one to carry on with --run (the run '
                             'you started, or the one the member means); a scheduled task carries on with its own '
                             'run.'.format(len(unfinished), '; '.join('"{}" ({}{})'.format(
                                 data['name'], data.get('workflow_name') or data['workflow'],
                                 ', a scheduled run' if data.get('scheduled') else '') for path, data in unfinished)))
    return unfinished[0] if unfinished else (None, None)


def save_run(path, data):
    data['updated_at'] = stamp()
    write_json(path, data)


def entry_for(brand):
    keys = ('id', 'name', 'folder', 'slug', 'marketplace', 'currency', 'seller_id', 'ads_profile_id', 'tier', 'tier_name',
            'kit_version', 'kit_vs_plugin', 'vip_machine', 'vip_machine_folder')
    entry = {key: brand.get(key) for key in keys}
    entry.update({'status': 'pending', 'note': None, 'started_at': None, 'finished_at': None, 'summary_file': None,
                  'warnings': []})
    return entry


def not_for_this_run(kind, brand, alerts):
    """Why a brand is left out of a run before it starts (it is listed as skipped), or None."""
    for alert in alerts:
        if alert['code'] == 'same-brand-two-folders' and brand['id'] in alert.get('brands', []):
            return ('This brand is set up in more than one folder here, so it was left out until the member says which '
                    'folder is the current one.')
    if kind == 'routine':
        if brand.get('tier') != 'vip':
            return "The VIP Machine isn't part of GLS+, so this routine doesn't apply to this brand."
        if brand.get('vip_machine') != 'set up':
            return "This brand's VIP Machine isn't set up yet ({}), so its routines don't run yet.".format(
                brand.get('vip_machine'))
    return None


def progress(data):
    counts = {}
    for entry in data['brands']:
        counts[entry['status']] = counts.get(entry['status'], 0) + 1
    rows = []
    for entry in data['brands']:
        row = {'brand': entry['id'], 'name': entry['name'], 'status': entry['status'],
               'result': STATUS_WORDS.get(entry['status'], entry['status']), 'note': entry.get('note')}
        if entry['status'] == 'in-progress':
            # Which session has it, and since when (Caiman 0.3.17).
            row.update(session=entry.get('session'), claimed_at=entry.get('claimed_at') or entry.get('started_at'))
        rows.append(row)
    return {'counts': counts, 'brands': rows}


def progress_table(data):
    lines = ['| Brand | Result | Note |', '|---|---|---|']
    for entry in data['brands']:
        lines.append('| {} | {} | {} |'.format(entry['name'].replace('|', '/'),
                                               STATUS_WORDS.get(entry['status'], entry['status']),
                                               one_line(entry.get('note') or '', 160).replace('|', '/') or ' '))
    return '\n'.join(lines)


def new_session():
    """A short name for one session's claims in a run (a conversation, or one scheduled run)."""
    return 's-' + secrets.token_hex(3)


def claim_of(entry):
    """(session, since) a brand in progress was handed to. A run saved by an earlier plugin has no session (None) and
    its brand counts from when it was started."""
    return text_value(entry.get('session')), parse_time(entry.get('claimed_at') or entry.get('started_at'))


def claim_minutes(entry, moment):
    since = claim_of(entry)[1]
    return None if since is None else max(0, int((moment - since).total_seconds() // 60))


def claim_words(entry, moment):
    """Who has a brand in progress and since when, in plain words: "a conversation 6 minutes ago (October 12, 2026 at
    10:14 AM, session s-3f9a2c)"."""
    session, since = claim_of(entry)
    minutes = claim_minutes(entry, moment)
    if minutes is None:
        ago = 'at a time not recorded'
    elif minutes < 1:
        ago = 'less than a minute ago'
    elif minutes < 120:
        ago = plural(minutes, 'minute') + ' ago'
    elif minutes < 48 * 60:
        ago = plural(minutes // 60, 'hour') + ' ago'
    else:
        ago = plural(minutes // (24 * 60), 'day') + ' ago'
    detail = ', '.join(part for part in (plain_time(since) if since else None,
                                         'session ' + session if session else None) if part)
    return '{} {}{}'.format(entry.get('claimed_by') or 'a session', ago, ' ({})'.format(detail) if detail else '')


def claim(entry, session, data, moment):
    entry['status'] = 'in-progress'
    entry['started_at'] = entry.get('started_at') or stamp(moment)
    entry.update(session=session, claimed_at=stamp(moment),
                 claimed_by='a scheduled run' if data.get('scheduled') else 'a conversation')


def take_over(entry, session, data, moment):
    """This session takes a brand another session had, keeping a record of who had it."""
    previous = {'session': entry.get('session'), 'claimed_at': entry.get('claimed_at') or entry.get('started_at'),
                'claimed_by': entry.get('claimed_by'), 'taken_by': session, 'taken_at': stamp(moment)}
    entry['taken_over'] = (entry.get('taken_over') or []) + [previous]
    claim(entry, session, data, moment)
    return dict(previous, brand=entry['id'], name=entry['name'])


def hand_out(root, path, data, session=None, take_over_brand=None, leave=()):
    """(entry, resumed, held): the brand to work on now, whether it was handed out before, and what happened to the
    brands another session has. A brand stays with the session it was handed to until it's recorded (Caiman 0.3.17):
    that session gets it back first. Another conversation is asked first (held['ask']) unless the member chose to take
    it over (take_over_brand) or leave it to that session (leave, remembered for this session). A scheduled run leaves
    it (held['left']) unless that session has had it for CLAIM_HOLD_MINUTES or more (it most likely stopped), and then
    takes it over (held['taken_over']). A brand whose folder is gone is recorded as not finished and the run moves on."""
    moment = now()
    held = {'ask': None, 'left': [], 'taken_over': None}
    for wanted in leave or ():
        item = match_entry(data['brands'], wanted)
        if item['status'] == 'in-progress' and session not in (item.get('left_by') or []):
            item['left_by'] = (item.get('left_by') or []) + [session]
    entry, resumed = None, False
    if take_over_brand:
        entry = match_entry(data['brands'], take_over_brand)
        if entry['status'] != 'in-progress':
            raise WorkspaceError("{} isn't in progress in this run ({}), so there's nothing to take over. Run next "
                                 'without --take-over.'.format(entry['name'], STATUS_WORDS.get(entry['status'],
                                                                                                entry['status']).lower()))
        if entry.get('session') != session:
            held['taken_over'] = take_over(entry, session, data, moment)
        resumed = True
    busy = [item for item in data['brands'] if item['status'] == 'in-progress']
    if entry is None:
        entry = next((item for item in busy if session and item.get('session') == session), None)
        resumed = entry is not None
    if entry is None:
        for item in busy:
            if session in (item.get('left_by') or []):
                held['left'].append(item)
                continue
            minutes = claim_minutes(item, moment)
            if data.get('scheduled'):
                if minutes is not None and minutes < CLAIM_HOLD_MINUTES:
                    held['left'].append(item)
                    continue
                held['taken_over'] = take_over(item, session, data, moment)
                entry, resumed = item, True
                break
            held['ask'] = item
            break
    while entry is None and held['ask'] is None:
        entry = next((item for item in data['brands'] if item['status'] == 'pending'), None)
        if entry is None:
            break
        if not brand_folder(root, entry).is_dir():
            entry.update(status='failed', finished_at=stamp(),
                         note='Its business folder ({}) is no longer there (moved or renamed?).'.format(entry['folder']))
            entry = None
            continue
        claim(entry, session, data, moment)
    save_run(path, data)
    return entry, resumed, held


def command_line(argv):
    return ' '.join(quoted(part) if (not part or re.search(r'[\s"\'$&|;<>()]', part)) else part
                    for part in [python()] + [str(item) for item in argv])


def task_for(root, data, entry, resumed, session=None):
    """What to do for one brand: its folder, its account, and how this workflow starts there for its tier. With a
    session, its commands name it, so this session keeps its own brand (Caiman 0.3.17)."""
    folder = brand_folder(root, entry)
    guide = guide_folder(folder)
    label, kind, first = WORKFLOWS[data['workflow']]
    summary = brand_summary_file(root, data['name'], entry['id'])
    ids = [item['id'] for item in data['brands']]
    task = {'brand': entry['id'], 'brand_name': entry['name'], 'position': '{} of {}'.format(
                ids.index(entry['id']) + 1, len(ids)),
            'folder': str(folder), 'guide_folder': str(guide), 'tier': entry.get('tier'),
            'tier_name': entry.get('tier_name'),
            'account': {'connector_brand_slug': entry.get('slug'), 'marketplace': entry.get('marketplace'),
                        'currency': entry.get('currency'), 'seller_id': entry.get('seller_id'),
                        'ads_profile_id': entry.get('ads_profile_id')},
            'resumed': resumed, 'summary_file': str(summary), 'start': None}
    if kind in ('kit', 'request'):
        goal = first if kind == 'kit' else data.get('goal')
        if kind == 'kit' and data.get('goal'):
            goal = first + '\n' + data['goal']
        program = guide / 'CLIENT_START.py'
        if program.is_file():
            # Always a new request: a brand picked up again may never have reached CLIENT_START.py, and without
            # --new-request the goal would join whatever earlier request is still open there.
            argv = [str(program), '--project-root', str(folder), '--new-request', '--goal', goal]
            task['start'] = {'program': python(), 'argv': argv, 'shell': command_line(argv),
                             'how': ("Run it for this brand, then do the {} as CLIENT_START.py and this brand's own kit say "
                                     "(the caiman skill, sections 4 and 5), in this brand's folder only.").format(
                                 label if kind == 'kit' else 'request')}
        else:
            task['problem'] = ("This brand's kit has no CLIENT_START.py, so the workflow can't start here. Record the brand "
                               'as skipped with that reason; its kit needs updating with kit-sync.')
    elif kind == 'routine':
        machine_rel = entry.get('vip_machine_folder') or MACHINE_DIR
        machine = folder.joinpath(*machine_rel.split('/'))
        prompt = machine / 'schedules' / first
        if not prompt.is_file():
            prompt = guide / 'Operating Framework' / 'VIP Machine' / 'schedules' / first
        if prompt.is_file():
            task['start'] = {'routine_prompt': str(prompt),
                             'replace': {'{{CLIENT_PROJECT_ROOT}}': str(folder), '{{MACHINE_ROOT}}': str(machine)},
                             'how': ("Read this brand's own VIP Machine routine prompt and follow it for this brand, with "
                                     "the folders in replace put in for its placeholders. The prompt's own rules apply.")}
        else:
            task['problem'] = ("This brand's kit has no {} routine prompt. Record the brand as skipped with that reason; its "
                               'kit needs updating with kit-sync.').format(first)
    elif kind == 'setup':
        argv = [str(HERE / 'setup_check.py'), '--project-root', str(folder), '--connector', '<ok|failed|not-connected>',
                '--connector-brands-json', '@<file with the brands list_brands returned>']
        task['start'] = {'program': python(), 'argv': argv, 'shell': command_line(argv),
                         'how': ('Call list_brands once for the whole run, save its brands in a file and reuse it for every '
                                 "brand (the setup check guide, \"Every session\"). Pass on this brand's headline.")}
    own = ['--session', session] if session else []
    done_argv = [str(Path(__file__).resolve()), 'run', 'done', entry['id'], '--workspace', str(root), '--run', data['name'],
                 '--status', 'done', '--note', '<one line: what was done>', '--summary', str(summary)] + own
    task['when_done'] = command_line(done_argv)
    task['next'] = command_line([str(Path(__file__).resolve()), 'run', 'next', '--workspace', str(root), '--run',
                                 data['name']] + own)
    rules = [
        "Work only in this brand's folder ({}) and with its own account (connector brand slug {}{}). Use no other "
        "brand's account, files or numbers here.".format(entry['folder'], entry.get('slug') or 'not saved yet',
                                                       ', ' + entry['marketplace'] if entry.get('marketplace') else ''),
        "If this brand fails or needs the member's answer, record it (--status failed or needs-answer, with what is "
        'needed in --note) and go on with the next brand.',
        'When this brand is finished, save a few lines in summary_file (what was done, the numbers that matter, what '
        'needs the member), record it with when_done, and only then ask for the next brand with next (it names this '
        'run).',
    ]
    if data.get('scheduled'):
        rules.insert(1, 'This is a scheduled run: read data and prepare only. Never change an Amazon account; leave every '
                        'proposal for the member to approve in a conversation.')
    else:
        rules.insert(1, "Approvals stay per brand: any change to this brand's account needs the member's go for that exact "
                        'change, shown with this brand named.')
    for key, label in (('seller_id', 'seller account'), ('ads_profile_id', 'Ads profile')):
        sharing = [item['name'] for item in data['brands'] if item['id'] != entry['id'] and entry.get(key)
                   and item.get(key) == entry.get(key)]
        if sharing:
            rules.append("This brand shares its {} with {}: that account's reports include their products too, so read "
                         "and propose only for this brand's own products (on VIP, its VIP Machine's brand "
                         'scope).'.format(label, names(sharing)))
    reports = task_reports(root, data, entry, session)
    if reports:
        # Caiman 0.3.17: this brand's reports were asked for before the first brand; poll them, don't ask again.
        task['reports'] = reports
        rules.append(reports_rule(entry, reports))
    scope = scope_alert_now(root, entry)
    if scope:
        task['brand_scope_alert'] = scope
        rules.append(scope['member_line'] + ' Say so in this brand\'s summary. ' + scope['next_step'] + (
            ' A scheduled run only says so; saving it needs the member.' if data.get('scheduled') else ''))
    if not entry.get('slug'):
        rules.append('This folder has no connector brand slug saved yet: confirm which listed brand it is with the member '
                     'before pulling data (in a scheduled run, record it as needs-answer).')
    if entry.get('kit_vs_plugin') == 'older':
        rules.append("This brand's kit is older than this plugin. Update it first (kit-sync) unless this is a scheduled run; "
                     'then carry on with the kit it has and say so in its summary.')
    if resumed:
        rules.append('This brand was started earlier and not recorded: check its folder for what was already done and '
                     'carry on from there rather than starting over.')
    task['rules'] = rules
    return task


def scope_alert_now(root, entry):
    """The brand-scope alert saved with this brand when its run started (brand_scope_alerts), while its VIP Machine
    still has no brand scope saved; None once one is saved."""
    alert = entry.get('scope_alert')
    if not isinstance(alert, dict) or not entry.get('vip_machine_folder'):
        return None
    machine = brand_folder(root, entry).joinpath(*entry['vip_machine_folder'].split('/'))
    return alert if brand_scope_state(machine) == 'not saved' else None


def choice_command(root, data, session, flag, entry):
    return command_line([str(Path(__file__).resolve()), 'run', 'next', '--workspace', str(root), '--run', data['name'],
                         '--session', session, flag, entry['id']])


def next_answer(root, path, data, command, extra=None, session=None, take_over_brand=None, leave=()):
    session = session or new_session()
    entry, resumed, held = hand_out(root, path, data, session, take_over_brand, leave)
    moment = now()
    label = data.get('workflow_name') or data['workflow']
    answer = {'schema': RUN_SCHEMA, 'command': command, 'workspace': str(root), 'run': data['name'],
              'run_file': rel(root, path), 'workflow': data['workflow'], 'scheduled': bool(data.get('scheduled')),
              'session': session, 'progress': progress(data)}
    answer.update(extra or {})
    finish = command_line([str(Path(__file__).resolve()), 'run', 'finish', '--workspace', str(root), '--run',
                           data['name']])
    notes = []
    if held['taken_over']:
        gone = held['taken_over']
        notes.append('{} was taken over from {}, which never recorded it.'.format(gone['name'], claim_words(
            {'session': gone.get('session'), 'claimed_at': gone.get('claimed_at'), 'claimed_by': gone.get('claimed_by')},
            moment)))
    if held['left']:
        notes.append('Left to the session working on {}: {}.'.format(
            'it' if len(held['left']) == 1 else 'them',
            '; '.join('{} ({})'.format(item['name'], claim_words(item, moment)) for item in held['left'])))
    if notes:
        answer['held'] = {'taken_over': held['taken_over'], 'left': [
            {'brand': item['id'], 'name': item['name'], 'session': item.get('session'),
             'claimed_at': item.get('claimed_at') or item.get('started_at')} for item in held['left']]}
    if held['ask'] is not None:
        # Another session has this brand (Caiman 0.3.17): the member chooses before anyone works on it here.
        item = held['ask']
        stopped = (claim_minutes(item, moment) or 0) >= CLAIM_HOLD_MINUTES
        task = task_for(root, data, item, True, session)
        task['waiting_for_choice'] = True
        answer.update(
            status='brand-in-progress', task=task, finish=finish,
            claimed={'brand': item['id'], 'name': item['name'], 'session': item.get('session'),
                     'claimed_by': item.get('claimed_by'), 'claimed_at': item.get('claimed_at') or item.get('started_at')},
            choices=[{'choice': 'carry-on-here', 'words': 'Carry on with {} here'.format(item['name']),
                      'command': choice_command(root, data, session, '--take-over', item)},
                     {'choice': 'leave-it', 'words': 'Leave {} to that session and go on with the next brand'.format(
                         item['name']), 'command': choice_command(root, data, session, '--leave', item)}],
            member_message=(('{} in this {} run was handed to {} and isn\'t recorded yet; that session has most likely '
                             'stopped. Shall I carry on with it here, or leave it and go on with the next brand?')
                            if stopped else
                            ('{} in this {} run was handed to {} and isn\'t recorded yet. If that session is still '
                             'working on it, I\'ll leave it there and go on with the next brand; if it stopped, I\'ll '
                             'carry on with it here. Which would you like?')).format(
                item['name'], label, claim_words(item, moment)),
            how_to_continue=("Ask the member first (member_message) and wait for their choice; don't start this brand's "
                             'work yet. Then run that choice\'s command: carry-on-here takes the brand over for this '
                             'session, leave-it leaves it to the other session and gives the next brand.'))
        return answer
    if entry is None and held['left']:
        names_left = names([item['name'] for item in held['left']])
        scheduled = bool(data.get('scheduled'))
        answer.update(
            status='brands-in-progress-elsewhere', task=None, finish=None if scheduled else finish,
            choices=[] if scheduled else [{'choice': 'carry-on-here', 'words': 'Carry on with {} here'.format(item['name']),
                                            'command': choice_command(root, data, session, '--take-over', item)}
                                           for item in held['left']],
            member_message=('Every other brand in this {} run has a result. {} {} still being worked on in another '
                            'session ({}).').format(label, names_left, 'is' if len(held['left']) == 1 else 'are',
                                                    '; '.join(claim_words(item, moment) for item in held['left'])),
            how_to_continue=('Stop here without finishing the run: the session working on {} records it and finishes the '
                             'run. Tell the member only what this run did.'.format(names_left) if scheduled else
                             'When that session has recorded it, run finish for the combined note. If it has stopped, '
                             'carry on with it here (choices), or finish with --partial to leave it out.'))
        return answer
    if entry is None:
        answer.update(status='all-brands-done', task=None, finish=finish,
                      member_message='Every brand in this {} run has a result. Next: the combined summary.'.format(label),
                      how_to_continue='Run finish (the finish command) to write the combined note, then give the member '
                                      'its main points.')
        return answer
    task = task_for(root, data, entry, resumed, session)
    answer.update(status='brand-ready', task=task, finish=finish,
                  member_message='{} for {} ({}){}.{}'.format(label, entry['name'], task['position'],
                                                             ', carrying on where it stopped' if resumed else '',
                                                             ''.join(' ' + note for note in notes)),
                  how_to_continue=('Do task for this brand only, following task.rules; save its summary, record it with '
                                   'task.when_done, then run task.next (it names this run and this session).'))
    return answer


# ---------------------------------------------------------------- reports first, for the report-heavy workflows (0.3.17)

# Amazon can take an hour or more to make some accounts' Ads reports. For these workflows run start asks Claude to
# request every brand's reports before the first brand's work, each with that brand's own connector slug. The report IDs
# are recorded in the run file per brand (run reports), and each brand's task polls its own IDs instead of requesting
# them again; a report that failed or expired is requested again in that brand's own task.
PREFETCH_WORKFLOWS = ('advertising-daily-check', 'advertising-weekly-review', 'weekly-growth-review', 'vip-weekly-loop')
REPORT_ID_RE = re.compile(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,127}')
ADS_FORMATS = (('SP', 'Sponsored Products'), ('SB', 'Sponsored Brands'), ('SD', 'Sponsored Display'))
PREFETCH_HOW = ("Before any brand's work, request every brand's reports listed here: call each read's tool with its "
                "arguments exactly as given (each brand's own brand_slug; never one brand's slug for another), then record "
                'the report IDs the requests return with that brand\'s record command, each ID in place of <report id>. '
                "Don't wait for the reports: each brand's task polls its own IDs when its turn comes. A request that "
                'errors is recorded with --failed "<read>=<what it said>" in place of --add, and that brand\'s task asks '
                'for it again. Never record a download link: only the report_id.')


def ads_read(read, tool, slug, what, **arguments):
    return {'read': read, 'tool': tool, 'arguments': dict([('brand_slug', slug)] + sorted(arguments.items())),
            'what': what}


def machine_window(moment):
    """The VIP Machine's four weeks for a review run at this moment, as its weekly guide counts them (UTC dates): back
    14 days for the Ads attribution window, the latest complete Saturday, and the 27 days before it."""
    cutoff = moment.astimezone(dt.timezone.utc).date() - dt.timedelta(days=14)
    end = cutoff - dt.timedelta(days=(cutoff.weekday() - 5) % 7)
    return (end - dt.timedelta(days=27)).isoformat(), end.isoformat()


def prefetch_reads(workflow, brand, moment):
    """The Ads reports a run of this workflow reads for this brand: [{read, tool, arguments, what}], with the brand's
    own slug in the arguments. [] for another workflow or a brand with no connector slug saved. A VIP brand whose VIP
    Machine is set up reviews the VIP Machine's four weeks (and the last 7 complete days of search terms); other
    brands' weekly reviews read the last 30 days; the daily check reads yesterday and the last 7 days by campaign."""
    slug = text_value(brand.get('slug'))
    if workflow not in PREFETCH_WORKFLOWS or not slug:
        return []
    if workflow == 'advertising-daily-check':
        reads = []
        for code, words in ADS_FORMATS:
            reads.append(ads_read(code.lower() + '-campaigns-yesterday', 'analytics_campaign_performance', slug,
                                  words + ' by campaign, yesterday: delivery and spend', ad_product=code, lookback='yesterday'))
            reads.append(ads_read(code.lower() + '-campaigns-last-7-days', 'analytics_campaign_performance', slug,
                                  words + ' by campaign, the last 7 days: what yesterday is compared with', ad_product=code,
                                  lookback='7d'))
        return reads
    if brand.get('tier') == 'vip' and brand.get('vip_machine') == 'set up':
        start, end = machine_window(moment)
        today = moment.astimezone(dt.timezone.utc).date()
        first, last = (today - dt.timedelta(days=7)).isoformat(), (today - dt.timedelta(days=1)).isoformat()
        span = "the VIP Machine's four weeks, {} to {}".format(start, end)
        return [ads_read('sp-search-terms-4-weeks', 'analytics_search_term_report', slug,
                         'Sponsored Products search terms, ' + span, ad_product='SP', start_date=start, end_date=end),
                ads_read('sp-advertised-products-4-weeks', 'analytics_advertised_asin_report', slug,
                         'Sponsored Products by advertised product, ' + span, ad_product='SP', start_date=start,
                         end_date=end),
                ads_read('sp-campaigns-4-weeks', 'analytics_campaign_performance', slug,
                         'Sponsored Products by campaign (the totals), ' + span, ad_product='SP', start_date=start,
                         end_date=end),
                ads_read('sp-placements-4-weeks', 'analytics_placement_performance', slug,
                         'Sponsored Products by placement, ' + span, start_date=start, end_date=end),
                ads_read('sp-search-terms-last-7-days', 'analytics_search_term_report', slug,
                         'Sponsored Products search terms, the last 7 complete days, {} to {}'.format(first, last),
                         ad_product='SP', start_date=first, end_date=last)]
    if workflow == 'vip-weekly-loop':
        return []
    reads = [ads_read('sp-search-terms-30-days', 'analytics_search_term_report', slug,
                      'Sponsored Products search terms, the last 30 days', ad_product='SP', lookback='30d'),
             ads_read('sp-placements-30-days', 'analytics_placement_performance', slug,
                      'Sponsored Products by placement, the last 30 days', lookback='30d'),
             ads_read('sp-advertised-products-30-days', 'analytics_advertised_asin_report', slug,
                      'Sponsored Products by advertised product, the last 30 days', ad_product='SP', lookback='30d')]
    for code, words in ADS_FORMATS:
        reads.append(ads_read(code.lower() + '-campaigns-30-days', 'analytics_campaign_performance', slug,
                              words + ' by campaign, the last 30 days', ad_product=code, lookback='30d'))
    return reads


def reports_plan(workflow, brand, moment):
    """What a run entry keeps about its brand's reports: the reads, the IDs recorded for them, and IDs replaced later."""
    reads = prefetch_reads(workflow, brand, moment)
    return {'reads': reads, 'requested': {}, 'replaced': []} if reads else None


def task_reports(root, data, entry, session=None):
    """A brand's reports in this run, for its task: requested (with their report IDs, to poll), to_request (not asked
    for yet, or the request failed) and the command that records a new ID. None when the run asks for none ahead."""
    plan = entry.get('reports') if isinstance(entry.get('reports'), dict) else None
    if not plan or not plan.get('reads'):
        return None
    got = as_dict(plan.get('requested'))
    requested, to_request = [], []
    for read in plan['reads']:
        record = as_dict(got.get(read.get('read')))
        if record.get('status') == 'requested' and record.get('report_ids'):
            requested.append(dict(read, report_ids=list(record['report_ids']), requested_at=record.get('requested_at')))
        elif record.get('status') == 'failed':
            to_request.append(dict(read, failed=record.get('note') or 'the request failed'))
        else:
            to_request.append(dict(read))
    record = command_line([str(Path(__file__).resolve()), 'run', 'reports', entry['id'], '--workspace', str(root), '--run',
                           data['name']] + (['--session', session] if session else []) + ['--add', '<read>=<report id>'])
    return {'requested': requested, 'to_request': to_request, 'poll_with': 'get_ads_report_status', 'record': record}


def reports_rule(entry, reports):
    """The task rule for a brand whose reports were asked for ahead (prefetch_block)."""
    slug = entry.get('slug') or 'not saved yet'
    parts = []
    if reports['requested']:
        parts.append("This brand's Ads reports in task.reports.requested were requested at the start of the run: poll each "
                     'with get_ads_report_status (brand_slug {} and its report_id) and use them where this workflow '
                     "reads them; don't request them again. One that failed (FAILED, with its fatal_reason) or expired "
                     '(source_document_expired when read): request it again here with the same tool and arguments, and '
                     'record the new ID with task.reports.record. If this workflow needs other dates than a report\'s '
                     'arguments, request that one again here with the dates it needs and record its new ID the same '
                     'way.'.format(slug))
    if reports['to_request']:
        parts.append('The reads in task.reports.to_request were not requested yet, or their request failed: request them '
                     'here with this brand\'s slug and the arguments given, and record their IDs with task.reports.record.')
    return ' '.join(parts)


def prefetch_block(root, data, session):
    """The reports-first step for a run of a report-heavy workflow: for each brand still to do (pending, or in progress
    with this session), the reads not recorded yet, with the command that records their IDs. None when there is nothing
    to ask for. Another session's brand is left to it (its reports are that session's)."""
    if data.get('workflow') not in PREFETCH_WORKFLOWS:
        return None
    brands, waiting = [], []
    for entry in data['brands']:
        if entry['status'] not in ('pending', 'in-progress'):
            continue
        if entry['status'] == 'in-progress' and text_value(entry.get('session')) not in (None, session):
            continue
        plan = entry.get('reports') if isinstance(entry.get('reports'), dict) else None
        if not plan:
            if not entry.get('slug'):
                waiting.append({'brand': entry['id'], 'name': entry['name'],
                                'why': ('No connector brand slug is saved for it yet, so its reports wait for its own task '
                                        '(confirm which listed brand it is first).')})
            continue
        todo = [read for read in plan.get('reads') or [] if read.get('read') not in as_dict(plan.get('requested'))]
        if not todo:
            continue
        argv = [str(Path(__file__).resolve()), 'run', 'reports', entry['id'], '--workspace', str(root), '--run',
                data['name']] + (['--session', session] if session else [])
        for read in todo:
            argv += ['--add', read['read'] + '=<report id>']
        brands.append({'brand': entry['id'], 'name': entry['name'], 'connector_brand_slug': entry.get('slug'),
                       'reads': todo, 'record': command_line(argv)})
    if not brands and not waiting:
        return None
    return {'status': 'to-do' if brands else 'nothing-to-request', 'how': PREFETCH_HOW, 'brands': brands,
            'not_requested': waiting}


def with_prefetch(root, data, answer):
    """A run start answer with the reports-first step added, when the run has reports still to ask for."""
    block = prefetch_block(root, data, answer.get('session'))
    if block:
        answer['prefetch'] = block
        if block['brands']:
            answer['how_to_continue'] = ("First request every brand's reports and record their IDs (prefetch.how; one "
                                         'record command per brand). Then: ' + (answer.get('how_to_continue') or ''))
    return answer


def parse_read(raw, known, what):
    """(read, value) from "<read>=<value>", with the read checked against this brand's reads in the run."""
    read, sep, value = (raw or '').partition('=')
    read, value = read.strip(), value.strip()
    if not sep or not read or not value:
        raise WorkspaceError('Give each {} as "<read>=<{}>", for example "{}=<{}>".'.format(
            'report' if what == 'report id' else 'failed read', what, sorted(known)[0] if known else 'sp-campaigns-30-days',
            what))
    if read not in known:
        raise WorkspaceError('"{}" isn\'t one of this brand\'s reads in this run. Its reads are: {}.'.format(
            read, ', '.join(sorted(known)) or 'none'))
    return read, value


def cmd_run_reports(args):
    """Record (or show) one brand's report IDs in an unfinished run of a report-heavy workflow."""
    root = workspace_root(args.workspace)
    path, data = find_run(root, args.run)
    if not data:
        raise WorkspaceError("There's no unfinished run across the brands to record reports in.")
    if data.get('status') != 'open':
        raise WorkspaceError('The run "{}" is already finished.'.format(data['name']))
    entry = match_entry(data['brands'], args.brand)
    session = text_value(getattr(args, 'session', None))
    plan = entry.get('reports') if isinstance(entry.get('reports'), dict) else None
    changes = list(args.add or []) + list(args.failed or [])
    if changes:
        if not plan or not plan.get('reads'):
            raise WorkspaceError("{} has no reports to record in this {} run: its reports aren't asked for ahead (no "
                                 'connector brand slug saved, or not a report-heavy workflow).'.format(
                                     entry['name'], data.get('workflow_name') or data['workflow']))
        if entry['status'] not in ('pending', 'in-progress'):
            raise WorkspaceError('{} already has a result in this run ({}), so its reports aren\'t needed now.'.format(
                entry['name'], STATUS_WORDS.get(entry['status'], entry['status']).lower()))
        held = text_value(entry.get('session')) if entry['status'] == 'in-progress' else None
        if held and session and held != session:
            raise WorkspaceError("{} is being worked on in another session ({}), so its reports are that session's to "
                                 'record. If that session stopped, carry on with it here first (run next --take-over {}).'
                                 .format(entry['name'], claim_words(entry, now()), entry['id']))
        known = {read['read'] for read in plan['reads']}
        moment = stamp()
        requested = plan.setdefault('requested', {})
        for raw in args.add or []:
            read, value = parse_read(raw, known, 'report id')
            ids = [part.strip() for part in value.split(',') if part.strip()]
            bad = [item for item in ids if not REPORT_ID_RE.fullmatch(item)]
            if bad or not ids:
                raise WorkspaceError('"{}" doesn\'t look like a report ID. Record the report_id the request returned, '
                                     'never a download link. Nothing was recorded.'.format(one_line(bad[0] if bad else value, 80)))
            if read in requested:
                plan.setdefault('replaced', []).append(dict(requested[read], read=read, replaced_at=moment))
            requested[read] = {'report_ids': ids, 'requested_at': moment, 'session': session, 'status': 'requested',
                               'note': None}
        for raw in args.failed or []:
            read, value = parse_read(raw, known, 'what it said')
            if read in requested:
                plan.setdefault('replaced', []).append(dict(requested[read], read=read, replaced_at=moment))
            requested[read] = {'report_ids': [], 'requested_at': moment, 'session': session, 'status': 'failed',
                               'note': one_line(value, 300)}
        save_run(path, data)
    view = task_reports(root, data, entry, session)
    if view is None:
        message = "{} has no reports asked for ahead in this run.".format(entry['name'])
    else:
        message = '{}: {} of {} reports requested{}.'.format(
            entry['name'], len(view['requested']), len(view['requested']) + len(view['to_request']),
            '' if not view['to_request'] else '; still to request: ' + ', '.join(read['read'] for read in view['to_request']))
    return {'schema': RUN_SCHEMA, 'command': 'run reports', 'workspace': str(root), 'run': data['name'],
            'run_file': rel(root, path), 'brand': entry['id'], 'name': entry['name'], 'status': entry['status'],
            'reports': view, 'member_message': message,
            'how_to_continue': ("Record the next brand's report IDs, or, when every brand's are recorded, start the first "
                                "brand's task: it polls these IDs (task.reports) instead of requesting them again.")}


def cmd_run_start(args):
    root = workspace_root(args.workspace)
    plugin = plugin_version(args.plugin_version)
    workflow = workflow_key(args.workflow)
    if not workflow:
        raise WorkspaceError('"{}" isn\'t a workflow a workspace run takes. Use one of: {}.'.format(
            args.workflow, ', '.join(sorted(name for name in WORKFLOWS if WORKFLOWS[name][1] != 'kit-update'))))
    label, kind, first = WORKFLOWS[workflow]
    if kind == 'kit-update':
        raise WorkspaceError('Kit updates across the brands use workspace.py update (the kit-sync skill, "Every brand in a '
                             'workspace"), not a run.')
    goal = ' '.join((args.goal or '').split()) or None
    if kind == 'request' and not goal:
        raise WorkspaceError('A run of the member\'s own request needs it in --goal, in their words.')
    brands, skipped, alerts, saved = current_brands(root, plugin)
    if not brands:
        deeper = deeper_business_folders(root)
        raise WorkspaceError(deeper_words(root, deeper) if deeper else (
            "There are no Caiman business folders in {} (Claude looked several levels down), so there's nothing to "
            'run.'.format(root)))
    chosen = pick_brands(brands, args.brands)
    today = now().date().isoformat()
    closed = []
    for path, data in open_runs(root):
        if data.get('workflow') != workflow:
            continue
        # Carry on only with a run of the same brands (every brand here when none are named), started the same way
        # (a scheduled task never takes over a conversation's run, nor the other way round), and not left from an
        # earlier day (daily workflows) or week (the others).
        run_ids, chosen_ids = {item['id'] for item in data['brands']}, {brand['id'] for brand in chosen}
        same_brands = run_ids == chosen_ids if args.brands else chosen_ids <= run_ids
        same_kind = bool(data.get('scheduled')) == bool(args.scheduled)
        started = parse_time(data.get('started_at'))
        stale = (not data['name'].startswith(today)) if workflow in DAILY else bool(
            started and (now() - started).days >= STALE_DAYS)
        if stale:
            period = 'day' if workflow in DAILY else 'week'
            for entry in data['brands']:
                if entry['status'] in ('pending', 'in-progress'):
                    entry.update(status='not-run', note="A new {}'s run started before this brand was done.".format(
                        period))
            data.update(status='closed', finished_at=stamp(), closed_because="a new {}'s run started".format(period))
            save_run(path, data)
            closed.append(data['name'])
        elif not args.new and same_brands and same_kind and data.get('goal') == goal:
            return with_prefetch(root, data, next_answer(root, path, data, 'run start', {
                'resumed_run': True, 'note': 'An unfinished {} run from {} carries on at the next brand.'.format(
                    label, data['name'][:10])}, session=getattr(args, 'session', None)))
    base = '{} {}'.format(today, workflow)
    name, number = base, 2
    while run_file(root, name).exists() or (root / RUNS / name).exists():
        name, number = '{} {}'.format(base, number), number + 1
    entries = []
    scope_flags = {alert['brands'][0]: alert for alert in brand_scope_alerts(brands)}
    flagged = []
    run_moment = now()
    for brand in chosen:
        entry = entry_for(brand)
        why = not_for_this_run(kind, brand, alerts)
        if why:
            entry.update(status='skipped', note=why, finished_at=stamp())
        elif brand['id'] in scope_flags:
            # Caiman 0.3.17: a VIP brand sharing its account with no brand scope saved is flagged in the run.
            entry['scope_alert'] = {key: scope_flags[brand['id']][key] for key in ('code', 'member_line', 'next_step')}
            flagged.append(scope_flags[brand['id']])
        plan = None if why else reports_plan(workflow, brand, run_moment)
        if plan:
            entry['reports'] = plan   # Caiman 0.3.17: this brand's reports, asked for before the first brand
        entries.append(entry)
    moment = stamp()
    data = {'schema': RUN_SCHEMA, 'name': name, 'workflow': workflow, 'workflow_name': label, 'kind': kind,
            'goal': goal, 'scheduled': bool(args.scheduled), 'status': 'open', 'started_at': moment, 'updated_at': moment,
            'finished_at': None, 'plugin_version': plugin, 'note_file': None, 'closed_runs': closed, 'brands': entries,
            'about': ("One {} across this workspace's brands, one brand at a time, each in its own business folder with "
                      "its own account. workspace.py run next carries on at the next brand; run finish writes the "
                      'combined note.').format(label)}
    path = run_file(root, name)
    save_run(path, data)
    (root / RUNS / name).mkdir(parents=True, exist_ok=True)
    extra = {'resumed_run': False}
    if closed:
        extra['note'] = 'Closed the unfinished run from earlier: {}.'.format(names(closed))
    if flagged:
        extra['alerts'] = flagged
    answer = next_answer(root, path, data, 'run start', extra, session=getattr(args, 'session', None))
    if flagged:
        answer['member_message'] += ' ' + ' '.join(alert['member_line'] for alert in flagged)
    return with_prefetch(root, data, answer)


def cmd_run_next(args):
    root = workspace_root(args.workspace)
    path, data = find_run(root, args.run)
    if not data:
        recent = [item.get('name') for path, item in all_runs(root)][:5]
        return {'schema': RUN_SCHEMA, 'command': 'run next', 'workspace': str(root), 'status': 'no-open-run',
                'recent_runs': recent, 'member_message': "There's no unfinished run across your brands.",
                'how_to_continue': 'Start one with run start <workflow> when the member asks for work across brands.'}
    others = [item.get('name') for item_path, item in open_runs(root) if item.get('name') != data['name']]
    return next_answer(root, path, data, 'run next', {'other_open_runs': others} if others else None,
                       session=getattr(args, 'session', None), take_over_brand=getattr(args, 'take_over', None),
                       leave=getattr(args, 'leave', None) or ())


def match_entry(entries, wanted):
    key = name_key(wanted)
    hits = [entry for entry in entries if key and key in (
        name_key(entry['id']), name_key(entry['name']), name_key(entry['folder']), name_key(entry.get('slug')),
        name_key(Path(entry['folder']).name))]
    if len(hits) != 1:
        raise WorkspaceError('{} "{}" in this run. Its brands are: {}.'.format(
            'More than one brand matches' if hits else 'No brand matches', wanted,
            '; '.join('{} ({})'.format(entry['name'], entry['id']) for entry in entries)))
    return hits[0]


def inside_folder(path, folder):
    try:
        path.relative_to(folder)
        return True
    except ValueError:
        return False


def summary_source(root, data, entry, given):
    """(path, text) of the brand's summary file, or (None, None) when none was given and the usual one isn't there."""
    if given:
        candidate = Path(os.path.expanduser(given))
        if not candidate.is_absolute():
            candidate = root / candidate
    else:
        candidate = brand_summary_file(root, data['name'], entry['id'])
        if not candidate.is_file():
            return None, None
    candidate = Path(os.path.abspath(str(candidate)))
    if not inside_folder(candidate, root):
        raise WorkspaceError('The summary file has to be inside the workspace folder ({}). Save it at {}.'.format(
            root, brand_summary_file(root, data['name'], entry['id'])))
    own = Path(os.path.abspath(str(brand_summary_file(root, data['name'], entry['id']))))
    if candidate != own and (inside_folder(candidate, Path(os.path.abspath(str(root / RUNS)))) or (
            candidate.parent == Path(os.path.abspath(str(root))) and entry.get('folder') != '.')):
        # Another brand's summary in a run's folder, or one of the workspace's own files (CLAUDE.md, the plan...).
        raise WorkspaceError("That file isn't {}'s summary. Save {}'s summary at {} and record it with that.".format(
            entry['name'], entry['name'], own))
    for other in data['brands']:
        other_folder = brand_folder(root, other)
        if other['id'] != entry['id'] and other['folder'] != '.' and inside_folder(candidate, other_folder) and not \
                inside_folder(brand_folder(root, entry), other_folder):
            raise WorkspaceError("That summary file is in {}'s business folder, not {}'s. One brand's files never go into "
                                 "another's: save {}'s summary at {}.".format(
                                     other['name'], entry['name'], entry['name'],
                                     brand_summary_file(root, data['name'], entry['id'])))
    if not candidate.is_file():
        raise WorkspaceError("There's no summary file at {}. Save the brand's summary there first, or leave --summary "
                             'out.'.format(candidate))
    return candidate, read_text(candidate, 2 * 1024 * 1024) or ''


def mixed_accounts(text, entry, entries):
    """Lines naming another brand's connector slug, seller ID or Ads profile ID in this brand's summary."""
    found = []
    for other in entries:
        if other['id'] == entry['id']:
            continue
        for key, label in (('slug', 'connector brand slug'), ('seller_id', 'seller ID'),
                           ('ads_profile_id', 'Ads profile ID')):
            value = other.get(key)
            if not value or len(str(value)) < 4 or value in (entry.get('slug'), entry.get('seller_id'),
                                                             entry.get('ads_profile_id')):
                continue
            if re.search(r'(?<![\w-]){}(?![\w-])'.format(re.escape(str(value))), text or ''):
                found.append("{}'s summary names {}'s {} ({}). Check that this brand's work used only its own "
                             'account.'.format(entry['name'], other['name'], label, value))
    return found


def cmd_run_done(args):
    root = workspace_root(args.workspace)
    path, data = find_run(root, args.run)
    if not data:
        raise WorkspaceError("There's no unfinished run across the brands to record that in. Start one with run start.")
    if data.get('status') != 'open':
        raise WorkspaceError('The run "{}" is already finished.'.format(data['name']))
    entry = match_entry(data['brands'], args.brand)
    summary, text = summary_source(root, data, entry, args.summary)
    session = text_value(getattr(args, 'session', None))
    held_by = text_value(entry.get('session')) if entry['status'] == 'in-progress' else None
    other_session = (("{} was handed to {}; this result was recorded from session {}. Check that the two sessions "
                      "didn't both work on it.").format(entry['name'], claim_words(entry, now()), session)
                     if session and held_by and held_by != session else None)
    entry['status'] = args.status
    entry['finished_at'] = stamp()
    if args.note:
        entry['note'] = one_line(args.note, 600)
    entry['summary_file'] = rel(root, summary) if summary else None
    warnings = mixed_accounts(text, entry, data['brands']) if text else []
    if args.status == 'done' and not summary:
        warnings.append("No summary file was saved for {}; the combined note will have only its one-line note.".format(
            entry['name']))
    if other_session:
        warnings.append(other_session)
    entry['warnings'] = warnings
    save_run(path, data)
    left = [item for item in data['brands'] if item['status'] in ('pending', 'in-progress')]
    label = data.get('workflow_name') or data['workflow']
    message = '{}: {} recorded as {}.'.format(label, entry['name'], STATUS_WORDS.get(args.status, args.status).lower())
    message += ' Next: {}.'.format(left[0]['name']) if left else ' Every brand has a result; next is the combined note.'
    return {'schema': RUN_SCHEMA, 'command': 'run done', 'workspace': str(root), 'run': data['name'],
            'run_file': rel(root, path), 'recorded': {'brand': entry['id'], 'name': entry['name'], 'status': args.status,
                                                      'note': entry.get('note'), 'summary_file': entry['summary_file']},
            'warnings': warnings, 'next_brand': left[0]['id'] if left else None, 'progress': progress(data),
            'member_message': message,
            'how_to_continue': ('Run next for the next brand.' if left else 'Run finish for the combined note.') + (
                ' Check the warnings first.' if warnings else '')}


def cmd_run_status(args):
    root = workspace_root(args.workspace)
    path, data = find_run(root, args.run, only_one=False)
    runs = [{'run': item.get('name'), 'workflow': item.get('workflow'), 'status': item.get('status'),
             'started_at': item.get('started_at'), 'finished_at': item.get('finished_at'),
             'note_file': item.get('note_file')} for item_path, item in all_runs(root)[:10]]
    if not data:
        message = ("There's no unfinished run across your brands." + (' The last one was {} ({}).'.format(
            runs[0]['run'], runs[0]['status']) if runs else ''))
        return {'schema': RUN_SCHEMA, 'command': 'run status', 'workspace': str(root), 'status': 'no-open-run',
                'runs': runs, 'member_message': message}
    counts = progress(data)['counts']
    finished = sum(counts.get(key, 0) for key in DONE_STATUSES + ('not-run',))
    message = '{} ({}): {} of {} brands have a result.'.format(
        data.get('workflow_name') or data['workflow'], data['name'][:10], finished, len(data['brands']))
    others = [item.get('name') for item_path, item in open_runs(root) if item.get('name') != data['name']]
    if others and not args.run:
        message += ' Also unfinished: {}.'.format('; '.join(others))
    return {'schema': RUN_SCHEMA, 'command': 'run status', 'workspace': str(root), 'run': data['name'],
            'run_file': rel(root, path), 'status': data.get('status'), 'progress': progress(data),
            'table_markdown': progress_table(data), 'runs': runs, 'member_message': message}


def demoted(text):
    """A brand's summary inside the combined note: its headings sit below the brand's own heading."""
    lines = []
    for line in (text or '').strip().splitlines():
        if re.match(r'^\s{0,3}#{1,6}\s', line):
            line = '#### ' + line.strip().lstrip('#').strip()
        lines.append(line.rstrip())
    return '\n'.join(lines)


def run_note(root, data, moment):
    label = data.get('workflow_name') or data['workflow']
    started = parse_time(data.get('started_at'))
    lines = ['# {}: all brands, {}'.format(label, plain_date(moment)), '',
             '{}. Started {}, finished {}.{}'.format(
                 plural(len(data['brands']), 'brand'), plain_time(started) if started else 'earlier', plain_time(moment),
                 ' A scheduled run: nothing in any Amazon account was changed.' if data.get('scheduled') else ''), '']
    if data.get('goal'):
        lines += ['The request: "{}"'.format(data['goal']), '']
    lines += [progress_table(data), '']
    needs = [entry for entry in data['brands'] if entry['status'] in ('failed', 'needs-answer', 'not-run')]
    warned = [entry for entry in data['brands'] if entry.get('warnings')]
    scoped = [entry for entry in data['brands'] if scope_alert_now(root, entry)]
    if needs or warned or scoped:
        lines += ['## Needs you', '']
        for entry in needs:
            lines.append('- **{}**: {}{}'.format(entry['name'], STATUS_WORDS.get(entry['status'], entry['status']),
                                                 ': ' + entry['note'] if entry.get('note') else ''))
        for entry in warned:
            lines += ['- **{}**: {}'.format(entry['name'], warning) for warning in entry['warnings']]
        for entry in scoped:
            lines.append('- **{}**: {}'.format(entry['name'], entry['scope_alert']['member_line']))
        lines.append('')
    for entry in data['brands']:
        lines += ['## {}'.format(entry['name']), '',
                  '_{}{}_'.format(STATUS_WORDS.get(entry['status'], entry['status']),
                                  ': ' + entry['note'] if entry.get('note') else ''), '']
        text = None
        if entry.get('summary_file'):
            path = root.joinpath(*entry['summary_file'].split('/'))
            text = read_text(path, 2 * 1024 * 1024)
        if text and text.strip():
            body = demoted(text)
            if len(body) > SUMMARY_CHARS:
                body = body[:SUMMARY_CHARS].rsplit('\n', 1)[0] + '\n\n(Shortened; the whole summary is in `{}`.)'.format(
                    entry['summary_file'])
            lines += [body, '']
        elif entry['status'] == 'done':
            lines += ['No summary was saved for this brand.', '']
        lines += ['Business folder: `{}`'.format(entry['folder']), '']
    return '\n'.join(lines)


def cmd_run_finish(args):
    root = workspace_root(args.workspace)
    path, data = find_run(root, args.run)
    if not data:
        raise WorkspaceError("There's no unfinished run across the brands to finish.")
    if data.get('status') != 'open' and not args.run:
        raise WorkspaceError('The run "{}" is already finished.'.format(data['name']))
    left = [entry for entry in data['brands'] if entry['status'] in ('pending', 'in-progress')]
    if left and not args.partial:
        raise WorkspaceError('{} still {} no result: {}. Carry on with run next, or finish with --partial to write the '
                             'note without {}.'.format(plural(len(left), 'brand'), 'has' if len(left) == 1 else 'have',
                                                       names([entry['name'] for entry in left]),
                                                       'it' if len(left) == 1 else 'them'))
    for entry in left:
        entry.update(status='not-run', note=entry.get('note') or 'The run was finished before this brand was done.')
    for entry in data['brands']:
        # A summary file written over after its brand was recorded is checked again before it goes in the note.
        if entry.get('summary_file'):
            text = read_text(root.joinpath(*entry['summary_file'].split('/')), 2 * 1024 * 1024) or ''
            fresh = [line for line in mixed_accounts(text, entry, data['brands'])
                     if line not in (entry.get('warnings') or [])]
            entry['warnings'] = (entry.get('warnings') or []) + fresh
    moment = now()
    note_path = run_note_file(root, data['name'])
    write_atomic(note_path, run_note(root, data, moment).encode('utf-8'))
    data.update(status='finished', finished_at=stamp(moment), note_file=rel(root, note_path))
    save_run(path, data)
    counts = progress(data)['counts']
    label = data.get('workflow_name') or data['workflow']
    needs = [entry for entry in data['brands'] if entry['status'] in ('failed', 'needs-answer', 'not-run')]
    message = '{} finished for {} of {} brands.'.format(label, counts.get('done', 0), len(data['brands']))
    if needs:
        message += ' Needs you: {}.'.format('; '.join('{} ({}{})'.format(
            entry['name'], STATUS_WORDS.get(entry['status'], entry['status']).lower(),
            ': ' + one_line(entry['note'], 140).rstrip('.') if entry.get('note') else '') for entry in needs))
    skipped = [entry['name'] for entry in data['brands'] if entry['status'] == 'skipped']
    if skipped:
        message += ' Skipped: {}.'.format(names(skipped))
    return {'schema': RUN_SCHEMA, 'command': 'run finish', 'workspace': str(root), 'run': data['name'],
            'run_file': rel(root, path), 'note_file': rel(root, note_path), 'progress': progress(data),
            'member_message': message,
            'how_to_continue': ('Give the member the main points from the combined note ({}): what needs their decision, '
                                'brand by brand, and anything that failed.').format(rel(root, note_path))}


# ---------------------------------------------------------------- summary: one page across the brands

MONEY_KEYS = (('ordered_product_sales_usd', 'Sales'), ('ad_spend_usd', 'Ad spend'), ('ad_sales_usd', 'Ad sales'))


def money(value, currency):
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    return '{} {:,.0f}'.format(currency or '', value).strip()


def share(part, whole):
    if isinstance(part, (int, float)) and isinstance(whole, (int, float)) and whole:
        return '{:.0f}%'.format(100.0 * part / whole)
    return None


def business_view_numbers(folder):
    """The brand's latest business view as its plan last read it (.caiman/plan/last-plan.json, from NEXT_STEP.py)."""
    last = as_dict(read_json(folder / '.caiman' / 'plan' / 'last-plan.json', 16 * 1024 * 1024))
    card, view = as_dict(last.get('families')), as_dict(last.get('view'))
    if not card and not view:
        return None
    window = as_dict(card.get('window'))
    families = [item for item in card.get('families') or [] if isinstance(item, dict)]
    ad_sales = sum(item['ad_sales'] for item in families if isinstance(item.get('ad_sales'), (int, float)))
    return {'currency': card.get('currency'), 'window_start': window.get('start'), 'window_end': window.get('end'),
            'sales': card.get('brand_sales'), 'ad_spend': card.get('brand_ad_spend'),
            'acos': share(card.get('brand_ad_spend'), ad_sales) if ad_sales else None,
            'tacos': share(card.get('brand_ad_spend'), card.get('brand_sales')),
            'target_acos': card.get('target_acos'), 'family_count': card.get('family_count'),
            'top_families': [{'label': item.get('label'), 'sales': item.get('sales'), 'share': item.get('share')}
                             for item in families[:3]],
            'saved_at': view.get('saved_at'), 'plan_made_at': last.get('created_at')}


def vip_dashboard_numbers(folder, machine_rel):
    if not machine_rel:
        return None
    machine = folder.joinpath(*machine_rel.split('/'))
    for name in ('caiman-weekly-dashboard', 'voltage-weekly-dashboard'):
        data_path = machine / 'outputs' / name / 'latest' / 'dashboard.json'
        data = read_json(data_path, 64 * 1024 * 1024)
        if isinstance(data, dict):
            totals = as_dict(data.get('totals'))
            numbers = {label: totals[key] for key, label in MONEY_KEYS if isinstance(totals.get(key), (int, float))}
            period = as_dict(data.get('period'))
            return {'generated_at': data.get('generated_at'), 'period_start': period.get('start'),
                    'period_end': period.get('end'), 'numbers': numbers,
                    'acos': share(totals.get('ad_spend_usd'), totals.get('ad_sales_usd')),
                    'tacos': share(totals.get('ad_spend_usd'), totals.get('ordered_product_sales_usd')),
                    'proposals': data.get('recommendation_count'),
                    'page': rel(folder, data_path.with_name('dashboard.html')),
                    'scope_sha256': as_dict(data.get('brand_scope')).get('scope_sha256')}
    return None


def what_works(folder, limit=3):
    text = read_text(folder / 'outputs' / 'WHAT WORKS HERE.md', 1024 * 1024) or ''
    lines = [line.strip()[2:].strip() for line in text.splitlines() if line.strip().startswith(('- ', '* '))]
    return [one_line(line.replace('**', ''), 220) for line in lines if line][:limit]


def latest_run_notes(root, brand_id, limit=2, folder=None):
    """The brand's results in the latest finished runs. Given its business folder, runs are matched by that folder
    (Caiman 0.3.17): an ID can pass to another folder when folders are added or renamed, so a demo folder and the real
    one never get each other's notes."""
    notes = []
    for path, data in all_runs(root):
        if data.get('status') != 'finished':
            continue
        entry = next((item for item in data['brands'] if (item.get('folder') == folder if folder is not None
                                                          else item.get('id') == brand_id)), None)
        if entry:
            notes.append({'run': data.get('name'), 'workflow': data.get('workflow_name'),
                          'result': STATUS_WORDS.get(entry['status'], entry['status']), 'note': entry.get('note')})
        if len(notes) >= limit:
            break
    return notes


def summary_markdown(cards, alerts, moment):
    lines = ['# Your brands', '', 'Made on {} from each brand\'s own saved files. It changes nothing; ask Claude here to '
             'refresh it.'.format(plain_time(moment)), '']
    if alerts:
        lines += ['## Across the workspace', ''] + ['- ' + alert['member_line'] for alert in alerts] + ['']
    for card in cards:
        lines += ['## {} ({})'.format(card['name'], card['tier_name']), '']
        view = card.get('business_view')
        if view:
            figures = [part for part in (
                'sales {}'.format(money(view['sales'], view['currency'])) if money(view['sales'], view['currency']) else None,
                'ad spend {}'.format(money(view['ad_spend'], view['currency']))
                if money(view['ad_spend'], view['currency']) else None,
                'ACoS {}'.format(view['acos']) if view.get('acos') else None,
                'TACoS {}'.format(view['tacos']) if view.get('tacos') else None) if part]
            window = ' ({} to {})'.format(view['window_start'], view['window_end']) if view.get('window_start') else ''
            lines.append('- **Business view{}{}:** {}.'.format(window, covers_label(view),
                                                              ', '.join(figures) if figures else 'no figures yet'))
            lines += ['  - ' + line for line in scope_lines(card, view)]
            if view.get('top_families'):
                lines.append('- **Top families{}:** {}.'.format(
                    " (this brand's)" if view.get('top_families_brand_only') else '', '; '.join(
                    '{}{}'.format(item.get('label') or '?', ' ({})'.format(money(item['sales'], view['currency']))
                                  if money(item.get('sales'), view['currency']) else '')
                    for item in view['top_families'])))
        else:
            lines.append("- **Business view:** none saved yet (Deep Seed builds it; the plan reads it).")
        board = card.get('vip_dashboard')
        if board:
            figures = ['{} {}'.format(label.lower(), money(value, 'USD')) for label, value in board['numbers'].items()]
            if board.get('acos'):
                figures.append('ACoS ' + board['acos'])
            lines.append('- **VIP weekly dashboard{}{}:** {}{}.'.format(
                ' ({} to {})'.format(board['period_start'], board['period_end']) if board.get('period_start') else '',
                covers_label(board), ', '.join(figures) or 'no totals', ', {} proposals'.format(board['proposals'])
                if isinstance(board.get('proposals'), int) else ''))
            lines += ['  - ' + line for line in scope_lines(card, board)]
        due = card.get('results') or {}
        if 'not_checked' in due:
            lines.append("- **Results due:** not checked ({}).".format(due['not_checked']))
        else:
            lines.append('- **Results due:** {}{}.'.format(due.get('due') or 0, ', {} overdue'.format(due['overdue'])
                                                            if due.get('overdue') else ''))
        if card.get('what_works'):
            lines.append('- **What works here:** ' + ' / '.join(card['what_works']))
        if card.get('waiting_on_member'):
            lines.append('- **Waiting on you:** ' + '; '.join(card['waiting_on_member']))
        if card.get('alerts'):
            lines.append('- **Alerts:** ' + '; '.join(card['alerts']))
        for note in card.get('recent_runs') or []:
            lines.append('- **{} ({}):** {}{}'.format(note['workflow'], note['run'][:10], note['result'],
                                                      ': ' + one_line(note['note'], 160) if note.get('note') else ''))
        lines += ['- Business folder: `{}`'.format(card['folder']), '']
    return '\n'.join(lines)


SUMMARY_CSS = """
:root{--bg:#f7f6f2;--card:#fff;--ink:#1d1f23;--muted:#5d636d;--line:#dedbd2;--accent:#1f6f5c;--warn:#9a5b00;--bad:#a33a2b}
@media (prefers-color-scheme:dark){:root{--bg:#15171a;--card:#1e2125;--ink:#ebe9e4;--muted:#a5abb3;--line:#33373d;
--accent:#5fc2a4;--warn:#e0a54b;--bad:#ef8a7a}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 -apple-system,BlinkMacSystemFont,
"Segoe UI",Roboto,Helvetica,Arial,sans-serif}main{max-width:1080px;margin:0 auto;padding:28px 16px 48px}
h1{font-size:26px;margin:0 0 4px}.sub{color:var(--muted);margin:0 0 20px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:14px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px}
.card h2{font-size:18px;margin:0}.tier{color:var(--muted);font-size:13px;margin:2px 0 10px}
.fig{display:flex;flex-wrap:wrap;gap:8px 18px;margin:8px 0}.fig div{min-width:90px}
.fig b{display:block;font-size:18px;font-variant-numeric:tabular-nums}.fig span{color:var(--muted);font-size:12px}
ul{margin:6px 0 0;padding-left:18px}li{margin:2px 0}.label{color:var(--muted);font-size:12px;text-transform:uppercase;
letter-spacing:.04em;margin-top:10px}.alert{color:var(--warn)}.bad{color:var(--bad)}.ws{border-left:3px solid var(--warn);
padding:8px 12px;margin:0 0 16px;background:var(--card)}code{font-size:12px;color:var(--muted);word-break:break-all}
"""


def summary_html(cards, alerts, moment):
    esc = html.escape

    def figure(value, label):
        return '<div><b>{}</b><span>{}</span></div>'.format(esc(value), esc(label)) if value else ''

    parts = ['<!doctype html><html lang="en"><head><meta charset="utf-8">',
             '<meta name="viewport" content="width=device-width, initial-scale=1">',
             '<title>Your brands</title><style>{}</style></head><body><main>'.format(SUMMARY_CSS),
             '<h1>Your brands</h1><p class="sub">Made on {} from each brand\'s own saved files. Read-only: it changes '
             'nothing.</p>'.format(esc(plain_time(moment)))]
    if alerts:
        parts.append('<div class="ws"><div class="label">Across the workspace</div><ul>{}</ul></div>'.format(
            ''.join('<li>{}</li>'.format(esc(alert['member_line'])) for alert in alerts)))
    parts.append('<div class="grid">')
    for card in cards:
        parts.append('<section class="card"><h2>{}</h2><div class="tier">{} &middot; kit {}</div>'.format(
            esc(card['name']), esc(card['tier_name']), esc(card.get('kit_version') or '?')))
        view = card.get('business_view')
        if view:
            parts.append('<div class="label">Business view{}</div><div class="fig">{}{}{}{}</div>'.format(
                esc((' ({} to {})'.format(view['window_start'], view['window_end']) if view.get('window_start') else '')
                    + covers_label(view)),
                figure(money(view['sales'], view['currency']), 'Sales'),
                figure(money(view['ad_spend'], view['currency']), 'Ad spend'),
                figure(view.get('acos'), 'ACoS'), figure(view.get('tacos'), 'TACoS')))
            parts += ['<p class="alert">{}</p>'.format(esc(line)) for line in scope_lines(card, view)]
            if view.get('top_families'):
                parts.append('<ul>{}</ul>'.format(''.join('<li>{}{}</li>'.format(
                    esc(item.get('label') or '?'), esc(' ({})'.format(money(item['sales'], view['currency'])))
                    if money(item.get('sales'), view['currency']) else '') for item in view['top_families'])))
        else:
            parts.append('<div class="label">Business view</div><p>None saved yet.</p>')
        board = card.get('vip_dashboard')
        if board:
            parts.append('<div class="label">VIP weekly dashboard{}</div><div class="fig">{}{}</div>'.format(
                esc(covers_label(board)),
                ''.join(figure(money(value, 'USD'), label) for label, value in board['numbers'].items()),
                figure(board.get('acos'), 'ACoS')))
            parts += ['<p class="alert">{}</p>'.format(esc(line)) for line in scope_lines(card, board)]
        due = card.get('results') or {}
        due_text = ('not checked' if 'not_checked' in due else '{}{}'.format(
            due.get('due') or 0, ', {} overdue'.format(due['overdue']) if due.get('overdue') else ''))
        parts.append('<div class="label">Results due</div><p>{}</p>'.format(esc(due_text)))
        for key, label, css in (('what_works', 'What works here', ''), ('waiting_on_member', 'Waiting on you', ''),
                                ('alerts', 'Alerts', 'alert')):
            if card.get(key):
                parts.append('<div class="label">{}</div><ul class="{}">{}</ul>'.format(
                    label, css, ''.join('<li>{}</li>'.format(esc(item)) for item in card[key])))
        parts.append('<div class="label">Business folder</div><code>{}</code></section>'.format(esc(card['folder'])))
    parts.append('</div></main></body></html>')
    return '\n'.join(parts)


# ---------------------------------------------------------------- brand scope in the all-brands views (0.3.17)

# The first business view says it covers just the brand when it was built with the VIP Machine's brand scope
# (operating_sources.prepare puts a 'brand_scope' entry first in its coverage, with this wording).
VIEW_SCOPE_COUNT_RE = re.compile(r"Just this brand's (\d+) product")
VIEW_SCOPE_SAVED_RE = re.compile(r"brand scope, saved (\d{4}-\d{2}-\d{2})")


def scope_in_force(root, brand):
    """The VIP Machine's brand scope in force for this brand, from its own files (state/brand_scope.json as
    change-settings saved it; a VIP Machine still being set up counts too): None without a VIP Machine or a saved
    choice; {'mode': 'whole_account'}; {'mode': 'brand_in_account', 'members' (ASINs and parent ASINs), 'count',
    'saved_at', 'sha256' (as the VIP Machine hashes it)}; or {'mode': 'unreadable'} when a choice is recorded but its
    file can't be read here (the VIP Machine's check-health says why)."""
    if not brand.get('vip_machine_folder'):
        return None
    machine = brand_folder(root, brand).joinpath(*brand['vip_machine_folder'].split('/'))
    state = brand.get('brand_scope') or brand_scope_state(machine)
    if state == 'not saved':
        return None
    if state == 'whole account':
        return {'mode': 'whole_account'}
    saved = as_dict(read_json(machine / 'state' / 'brand_scope.json'))
    scope = as_dict(saved.get('scope'))
    asins = sorted({item for item in scope.get('asins') or [] if isinstance(item, str)})
    if state != 'brand' or scope.get('mode') != 'brand_in_account' or not asins:
        return {'mode': 'unreadable'}
    import hashlib   # the same canonical JSON the VIP Machine hashes (brand_scope.scope_sha256)
    canonical = json.dumps(scope, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    parents = {item for item in scope.get('parent_asins') or [] if isinstance(item, str)}
    return {'mode': 'brand_in_account', 'members': set(asins) | parents, 'count': len(asins),
            'saved_at': text_value(saved.get('changed_at')),
            'sha256': hashlib.sha256(canonical.encode('utf-8')).hexdigest()}


def folder_file(folder, relative):
    """A file named by a path relative to the business folder, or None (absolute, outside it, or missing)."""
    relative = text_value(relative)
    if not relative or relative.startswith(('/', '\\')) or ':' in relative:
        return None
    parts = [part for part in relative.replace('\\', '/').split('/') if part not in ('', '.')]
    if not parts or '..' in parts:
        return None
    path = folder.joinpath(*parts)
    return path if path.is_file() else None


def view_scope(folder, last):
    """Which products the business view the plan read last (last-plan.json's view) was built for, from the coverage
    its prepared inputs saved: {'with_scope': True, 'count', 'saved_on'} (either may be None) when it was built with a
    brand scope, {'with_scope': False} when it wasn't, None when it can't be told."""
    path = folder_file(folder, as_dict(last.get('view')).get('model'))
    if path is None:
        return None
    if path.name == 'dashboard.json':   # the read-only review outside US dollars: no VIP Machine, no brand scope
        return {'with_scope': False}
    coverage = None
    receipt = as_dict(read_json(path.with_name('view-receipt.json'), 1024 * 1024))
    manifest = folder_file(folder, as_dict(receipt.get('input_manifest')).get('path'))
    if manifest is not None:
        value = as_dict(read_json(manifest, 4 * 1024 * 1024)).get('coverage')
        coverage = value if isinstance(value, list) else None
    if coverage is None:
        value = as_dict(read_json(path, 256 * 1024 * 1024)).get('coverage')
        coverage = value if isinstance(value, list) else None
    if coverage is None:
        return None
    entry = next((item for item in coverage if isinstance(item, dict) and item.get('slot') == 'brand_scope'), None)
    if entry is None:
        return {'with_scope': False}
    note = str(entry.get('note') or '')
    count, saved = VIEW_SCOPE_COUNT_RE.search(note), VIEW_SCOPE_SAVED_RE.search(note)
    return {'with_scope': True, 'count': int(count.group(1)) if count else None,
            'saved_on': saved.group(1) if saved else None}


def sharing_names(brand, brands):
    """The other brands here that save the same seller account or Ads profile as this one."""
    found = []
    for key in ('seller_id', 'ads_profile_id'):
        found += [item['name'] for item in brands if item['id'] != brand['id'] and brand.get(key)
                  and item.get(key) == brand.get(key) and item['name'] not in found]
    return found


def view_covers(scope, built, sharing, name):
    """(covers, note) for a brand's saved business view: covers is 'this brand' (built for the brand scope in force),
    'whole account' (built for the whole seller account while a brand scope is in force, or while the account is
    shared with another brand here), 'earlier scope' (built for another list of the brand's products), 'unknown', or
    None (nothing to say); note says it plainly for the member."""
    mode = (scope or {}).get('mode')
    if mode == 'brand_in_account':
        if built is None:
            return 'unknown', ("Claude couldn't tell whether this view covers just {}'s products: its saved inputs couldn't "
                               'be read. Refresh its business view to be sure.').format(name)
        if built['with_scope']:
            if built.get('count') in (None, scope['count']) and built.get('saved_on') in (None, (scope.get('saved_at') or '')[:10]):
                return 'this brand', None
            return 'earlier scope', ("This view was built for an earlier list of {}'s products. Refresh its business view "
                                     'to match the brand scope saved now.').format(name)
        return 'whole account', ("These figures cover the whole seller account: the view was built before {}'s brand scope "
                                 "was saved, so it includes products that aren't {}'s. Refresh its business view to see "
                                 "just {}'s numbers.").format(name, name, name)
    if mode == 'unreadable':
        return 'unknown', ("{}'s brand scope can't be read here, so Claude can't tell what these figures cover (the VIP "
                           "Machine's check-health says why).").format(name)
    if built and built.get('with_scope'):
        return 'earlier scope', ("This view was built for just {}'s products, but its VIP Machine now covers the whole "
                                 'seller account. Refresh its business view.').format(name)
    if sharing:
        return 'whole account', 'These figures cover the whole seller account, which {} shares with {}.'.format(
            name, names(sharing))
    return None, None


def board_covers(scope, board_sha, sharing, name):
    """(covers, note) for a brand's VIP weekly dashboard, as view_covers says it, judged by the brand scope its
    scorecard was built with (the dashboard's brand_scope.scope_sha256)."""
    mode = (scope or {}).get('mode')
    if mode == 'brand_in_account':
        if board_sha == scope['sha256']:
            return 'this brand', None
        if board_sha:
            return 'earlier scope', ("This dashboard was built for an earlier list of {}'s products; the next weekly review "
                                     'builds it for the brand scope saved now.').format(name)
        return 'whole account', ("This dashboard was built before {}'s brand scope was saved, so it covers the whole seller "
                                 "account. The next weekly review builds it for just {}'s products.").format(name, name)
    if mode == 'unreadable':
        return 'unknown', ("{}'s brand scope can't be read here, so Claude can't tell what these figures cover (the VIP "
                           "Machine's check-health says why).").format(name)
    if board_sha:
        return 'earlier scope', ("This dashboard was built for just {}'s products, but its VIP Machine now covers the whole "
                                 'seller account; the next weekly review builds it that way.').format(name)
    if sharing:
        return 'whole account', 'These figures cover the whole seller account, which {} shares with {}.'.format(
            name, names(sharing))
    return None, None


def scoped_families(last, members):
    """From the business view the plan read last: the families wholly inside the brand scope, when every family is
    wholly inside or outside it ({'sales' (None when any is unknown), 'families', 'left_out', 'top'}); None when a
    family straddles the scope or has no products listed (it can't be told apart)."""
    card = as_dict(last.get('families'))
    inside, outside = [], []
    for family in [item for item in card.get('families') or [] if isinstance(item, dict)]:
        asins = {item for item in family.get('asins') or [] if isinstance(item, str)}
        if not asins:
            return None
        if asins <= members:
            inside.append(family)
        elif not asins & members:
            outside.append(family)
        else:
            return None
    if not inside:
        return None
    sales = [family.get('sales') for family in inside]
    total = None if any(not isinstance(value, (int, float)) or isinstance(value, bool) for value in sales) else sum(sales)
    return {'sales': total, 'families': len(inside), 'left_out': len(outside),
            'top': [{'label': family.get('label'), 'sales': family.get('sales'), 'share': None} for family in inside[:3]]}


def scope_figures(root, brand, brands, folder, view, board):
    """Says what each saved figure on a brand's summary card covers (Caiman 0.3.17): its business view and VIP weekly
    dashboard get 'covers' and 'covers_note'; a business view built for the whole seller account while the brand's
    scope is in force also gets the sales of the brand's own families in it (when they can be told apart), and its top
    families are the brand's own. Returns (the card's brand_scope, short alerts)."""
    scope = scope_in_force(root, brand)
    sharing = sharing_names(brand, brands) if (scope or {}).get('mode') != 'brand_in_account' else []
    alerts = []
    if view is not None:
        last = as_dict(read_json(folder / '.caiman' / 'plan' / 'last-plan.json', 16 * 1024 * 1024))
        covers, note = view_covers(scope, view_scope(folder, last), sharing, brand['name'])
        view.update(covers=covers, covers_note=note)
        if covers == 'this brand':
            view['covers_count'] = scope['count']
        if covers in ('whole account', 'earlier scope') and (scope or {}).get('mode') == 'brand_in_account':
            split = scoped_families(last, scope['members'])
            if split:
                view['brand_products'] = {key: split[key] for key in ('sales', 'families', 'left_out')}
                view['top_families'] = split['top']
                view['top_families_brand_only'] = True
            alerts.append('business view built before its brand scope: its figures cover the whole seller account'
                          if covers == 'whole account' else 'business view built for an earlier brand scope')
    if board is not None:
        covers, note = board_covers(scope, board.get('scope_sha256'), sharing, brand['name'])
        board.update(covers=covers, covers_note=note)
        if covers == 'this brand':
            board['covers_count'] = scope['count']
        if covers in ('whole account', 'earlier scope') and (scope or {}).get('mode') == 'brand_in_account':
            alerts.append('VIP weekly dashboard built before its brand scope: it covers the whole seller account'
                          if covers == 'whole account' else 'VIP weekly dashboard built for an earlier brand scope')
    if scope is None:
        return None, alerts
    if scope['mode'] == 'brand_in_account':
        return {'mode': 'brand', 'products': scope['count'], 'saved_at': scope.get('saved_at')}, alerts
    return {'mode': 'whole account' if scope['mode'] == 'whole_account' else 'unreadable'}, alerts


def scope_lines(card, item):
    """The plain lines under a figure group on the summary: what its figures cover, and in a business view built for
    the whole seller account, what the brand's own products sold in it."""
    lines = [item['covers_note']] if item.get('covers_note') else []
    split = item.get('brand_products')
    if split and split.get('sales') is not None and money(split['sales'], item.get('currency')):
        lines.append("{}'s own products sold {} in it ({}{}).".format(
            card['name'], money(split['sales'], item.get('currency')), plural(split['families'], 'family', 'families'),
            '; {} other {} left out'.format(split['left_out'], 'family' if split['left_out'] == 1 else 'families')
            if split.get('left_out') else ''))
    return lines


def covers_label(item):
    """The words after a figure group's name on the summary: what it covers."""
    covers = item.get('covers')
    if covers == 'this brand':
        count = item.get('covers_count')
        return ", just this brand's {}".format(plural(count, 'product')) if count else ", just this brand's products"
    if covers == 'whole account':
        return ', whole seller account'
    if covers == 'earlier scope':
        return ", an earlier list of this brand's products"
    return ''


def cmd_summary(args):
    root = workspace_root(args.workspace)
    plugin = plugin_version(args.plugin_version)
    brands, skipped, alerts, saved = current_brands(root, plugin)
    scope_alerts = brand_scope_alerts(brands)
    everyone = brands
    brands = pick_brands(brands, args.brands)
    if not brands:
        raise WorkspaceError('There are no Caiman business folders here to summarize.')
    cards = []
    by_id = {brand['id']: brand for brand in brands}
    for brand in brands:
        folder = brand_folder(root, brand)
        row = brand_status(root, brand, plugin, quick=args.quick)
        row['alerts'] += [short_alert(alert, brand['id'], by_id) for alert in alerts + scope_alerts if brand['id'] in
                          alert.get('brands', []) and alert['code'] not in ('kit-older', 'kit-newer')]
        view = business_view_numbers(folder)
        board = vip_dashboard_numbers(folder, brand.get('vip_machine_folder'))
        # Caiman 0.3.17: say what each figure covers when a brand scope is saved or the account is shared.
        scope, scope_notes = scope_figures(root, brand, everyone, folder, view, board)
        cards.append({'id': brand['id'], 'name': brand['name'], 'folder': brand['folder'], 'tier': brand['tier'],
                      'tier_name': brand['tier_name'], 'kit_version': brand.get('kit_version'),
                      'business_view': view, 'vip_dashboard': board, 'brand_scope': scope,
                      'results': row['results'], 'what_works': what_works(folder),
                      'waiting_on_member': row.get('waiting_on_member') or [], 'alerts': row['alerts'] + scope_notes,
                      'recent_runs': latest_run_notes(root, brand['id'], folder=brand['folder'])})
    workspace_alerts = [alert for alert in alerts if alert['code'] not in ('kit-older', 'kit-newer')]
    moment = now()
    write_atomic(root / SUMMARY_MD, summary_markdown(cards, workspace_alerts, moment).encode('utf-8'))
    write_atomic(root / SUMMARY_HTML, summary_html(cards, workspace_alerts, moment).encode('utf-8'))
    flagged = [card for card in cards if card['alerts'] or card['waiting_on_member']]
    message = 'One page for {}: {}.'.format(plural(len(cards), 'brand'), SUMMARY_HTML)
    if flagged:
        message += ' Needs a look: {}.'.format(names([card['name'] for card in flagged]))
    how = 'Open WORKSPACE SUMMARY.html for the member and give the few points that need them.'
    stale = [card['name'] for card in cards if (card.get('brand_scope') or {}).get('mode') == 'brand' and any(
        (card.get(key) or {}).get('covers') in ('whole account', 'earlier scope') for key in ('business_view', 'vip_dashboard'))]
    if stale:
        how += (" {}'s figures marked whole seller account (or an earlier list) aren't just the brand's: say so in those "
                "words, never as the brand's own. Offer to refresh that brand's business view in its own folder "
                '(REFRESH_OPERATING_VIEW.py --project-root <its folder>; it reads no new data); its VIP weekly dashboard '
                'follows at the next weekly review.').format(names(stale))
    return {'schema': SCHEMA, 'command': 'summary', 'workspace': str(root), 'summary_html': SUMMARY_HTML,
            'summary_md': SUMMARY_MD, 'brands': cards, 'alerts': workspace_alerts, 'member_message': message,
            'how_to_continue': how}


# ---------------------------------------------------------------- kit updates for every brand

def kit_status_with(program, folder, seconds=SHORT_SECONDS):
    code, out, err, failed = run_program([python(), '-B', str(program), 'status', '--folder', str(folder), '--json'],
                                         folder, seconds)
    data = json_from(out)
    if failed or not data or data.get('status') in (None, 'error'):
        return None, failed or one_line((data or {}).get('message') or err or out, 200)
    return data, None


NO_INSTALL = ('current', 'newer', 'skills-blocked', 'skills-locked', 'missing', 'other-tier')


LIVE_RELEASE = re.compile(r'\b\d{4}-\d{2}-\d{2}-(vip|gls-plus)-v(\d+)\b')


def live_kits(values):
    """{tier: (release, number)} from --live-kit values: the release get_kit_download named, or @ and a file holding
    its result. Only the release name is kept."""
    found = {}
    for value in values or []:
        text = (value or '').strip()
        if text.startswith('@'):
            try:
                with open(os.path.expanduser(text[1:].strip()), 'r', encoding='utf-8-sig') as handle:
                    text = handle.read(2 * 1024 * 1024)
            except OSError:
                continue
        match = LIVE_RELEASE.search(text)
        if match:
            found[match.group(1)] = (match.group(0), int(match.group(2)))
    return found


def behind_live(brand, lives):
    """The release members get now for this brand's membership, when it's newer than the brand's kit."""
    live = lives.get(brand.get('tier'))
    try:
        have = int(re.sub(r'^v', '', str(brand.get('kit_version') or '')))
    except ValueError:
        return None
    return live[0] if live and live[1] > have else None


def update_rows(root, brands, plugin, program, lives=None):
    rows = []
    for brand in brands:
        folder = brand_folder(root, brand)
        data, why = kit_status_with(program, folder) if program else (None, 'kit-sync is not next to the caiman skill')
        verdict = (data or {}).get('status') or brand.get('kit_vs_plugin')
        newer = behind_live(brand, lives or {})
        if newer and verdict in ('current', 'newer'):
            verdict = 'update_due'
        rows.append({'id': brand['id'], 'name': brand['name'], 'folder': brand['folder'], 'tier': brand['tier'],
                     'tier_name': brand['tier_name'], 'kit_version': brand.get('kit_version'),
                     'kit_core_version': brand.get('kit_core_version'), 'plugin_version': plugin, 'kit_status': verdict,
                     'needs_update': verdict not in NO_INSTALL and verdict != 'unknown', 'live_kit': newer,
                     'kit_sync_message': one_line((data or {}).get('message'), 400) if data else None,
                     'checked_by': 'kit-sync status' if data else 'versions only: ' + (why or '')})
    return rows


def cmd_update_plan(args):
    root = workspace_root(args.workspace)
    plugin = plugin_version(args.plugin_version)
    brands, skipped, alerts, saved = current_brands(root, plugin)
    brands = pick_brands(brands, args.brands)
    program = given_kit_sync(args.kit_sync) if args.kit_sync else kit_sync_program()
    rows = update_rows(root, brands, plugin, program if program and program.is_file() else None,
                       live_kits(getattr(args, 'live_kit', None)))
    need = [row for row in rows if row['needs_update']]
    tiers = sorted({row['tier'] for row in need if row['tier']})
    lines = ['| Brand | Membership | Kit | Plugin | Kit check |', '|---|---|---|---|---|']
    for row in rows:
        lines.append('| {} | {} | {} | {} | {} |'.format(row['name'].replace('|', '/'), row['tier_name'],
                                                          'v' + row['kit_version'] if row['kit_version'] else '?',
                                                          plugin or '?', row['kit_status']))
    steps = []
    if need:
        for tier in tiers:
            steps.append("Call the Caiman connector's get_kit_download for {} once, save its result, and download the zip "
                         'straight away with kit-sync: kit_sync.py download --descriptor "<saved result>" --out "{}".'.format(
                             tier, root / RUNS / 'kits'))
        steps.append('Then: {} update --workspace {} {}'.format(me(), quoted(root), ' '.join(
            '--zip "<{} kit zip>"'.format(tier) for tier in tiers)))
    message = ('Every brand\'s kit is current.' if not need else '{} need{} a kit update: {}.'.format(
        plural(len(need), 'brand'), 's' if len(need) == 1 else '', names([row['name'] for row in need])))
    blocked = [row for row in rows if row['kit_status'] in ('skills-blocked', 'skills-locked')]
    if blocked:
        message += " {}: the kit is current, but its skills can't be checked (kit-sync's guide).".format(
            names([row['name'] for row in blocked]))
    return {'schema': SCHEMA, 'command': 'update-plan', 'workspace': str(root), 'plugin_version': plugin, 'brands': rows,
            'tiers_needed': tiers, 'steps': steps, 'table_markdown': '\n'.join(lines), 'member_message': message}


def zip_info(path):
    """(tier, kit version, core version) of a kit zip, from its own RELEASE_MANIFEST.json or ENTITLEMENTS.json."""
    try:
        with zipfile.ZipFile(str(path)) as archive:
            markers = sorted((info for info in archive.infolist() if not info.is_dir()
                              and info.filename.rsplit('/', 1)[-1] in ('RELEASE_MANIFEST.json', 'ENTITLEMENTS.json')
                              and '__macosx' not in info.filename.lower() and '/.claude/' not in '/' + info.filename),
                             key=lambda info: (info.filename.count('/'), info.filename))
            manifest, entitlements = {}, {}
            for info in markers:
                if info.file_size > 8 * 1024 * 1024:
                    continue
                try:
                    value = as_dict(json.loads(archive.read(info).decode('utf-8-sig')))
                except (ValueError, UnicodeError):
                    continue
                if info.filename.endswith('RELEASE_MANIFEST.json') and not manifest:
                    manifest = value
                elif info.filename.endswith('ENTITLEMENTS.json') and not entitlements:
                    entitlements = value
    except (zipfile.BadZipFile, OSError) as error:
        raise WorkspaceError("{} isn't a complete kit zip ({}). Download it again.".format(Path(path).name, error))
    tier = norm_tier(manifest.get('kit')) or norm_tier(manifest.get('tier')) or norm_tier(entitlements.get('plan_tier'))
    return tier, text_value(manifest.get('version')), text_value(manifest.get('core_version'))


def zip_is_newer(brand, zips):
    """The given kit zip for this brand's membership is newer than the brand's kit (a kit the server serves now that
    matches neither the brand's kit nor this plugin)."""
    chosen = zips.get(brand.get('tier'))
    try:
        return bool(chosen) and int(str(chosen['version']).lstrip('v')) > int(str(brand.get('kit_version') or '').lstrip('v'))
    except ValueError:
        return False


def cmd_update(args):
    root = workspace_root(args.workspace)
    plugin = plugin_version(args.plugin_version)
    zips = {}
    for value in args.zip or []:
        path = Path(os.path.abspath(os.path.expanduser(value)))
        if not path.is_file():
            raise WorkspaceError("There's no kit zip at {}.".format(path))
        tier, version, core = zip_info(path)
        if not tier:
            raise WorkspaceError("{} doesn't look like a Caiman kit zip (it says no membership).".format(path.name))
        if tier in zips:
            raise WorkspaceError('Two {} kit zips were given ({} and {}). Give one zip per membership.'.format(
                TIER_NAMES[tier], zips[tier]['path'].name, path.name))
        zips[tier] = {'path': path, 'version': version, 'core_version': core}
    if not zips:
        raise WorkspaceError('Give the kit zip for each membership in the workspace with --zip (update-plan says which).')
    program = given_kit_sync(args.kit_sync) if args.kit_sync else kit_sync_program()
    if not program or not program.is_file():
        raise WorkspaceError("kit-sync's kit_sync.py isn't next to the caiman skill, so the brands can't be updated from "
                             'here. Pass its path with --kit-sync.')
    brands, skipped, alerts, saved = current_brands(root, plugin)
    brands = pick_brands(brands, args.brands)
    duplicates = {item for alert in alerts if alert['code'] == 'same-brand-two-folders' for item in alert['brands']}
    results = []
    for brand in brands:
        folder = brand_folder(root, brand)
        result = {'brand': brand['id'], 'name': brand['name'], 'folder': brand['folder'], 'tier': brand['tier'],
                  'kit_before': brand.get('kit_version'), 'status': None, 'note': None, 'kit_sync_message': None}
        state, why = kit_status_with(program, folder)
        verdict = (state or {}).get('status')
        if brand['id'] in duplicates:
            result.update(status='skipped', note='Set up in more than one folder here; ask the member which folder is the '
                                                 'current one before updating it.')
        elif state is None:
            result.update(status='failed', note="kit-sync couldn't check this folder: {}".format(why))
        elif verdict in ('current', 'newer') and not args.all and not zip_is_newer(brand, zips):
            result.update(status='skipped', note='Already current.' if verdict == 'current' else
                          'Its kit is newer than this plugin; the plugin needs an update. The kit stays.')
        elif verdict in ('skills-blocked', 'skills-locked'):
            result.update(status='needs-answer', note=one_line(state.get('message'), 400),
                          kit_sync_message=state.get('message'))
        elif brand['tier'] not in zips:
            result.update(status='skipped', note='No {} kit zip was given, so this brand was left as it is.'.format(
                brand['tier_name']))
        else:
            chosen = zips[brand['tier']]
            argv = [python(), '-B', str(program), 'install', '--folder', str(folder), '--zip', str(chosen['path']),
                    '--json'] + (['--dry-run'] if args.dry_run else [])
            code, out, err, failed = run_program(argv, folder, args.timeout)
            data = json_from(out)
            if failed:
                result.update(status='failed', note='kit-sync ' + failed + '. Run the update again; it picks up where it '
                                                                             'stopped.')
            elif not data:
                result.update(status='failed', note='kit-sync stopped without an answer: ' + one_line(err or out, 300))
            elif data.get('status') == 'needs-confirmation':
                result.update(status='needs-answer', note=one_line(data.get('message'), 400),
                              kit_sync_message=data.get('message'))
            elif data.get('status') == 'error' or code:
                result.update(status='failed', note=one_line(data.get('message'), 400),
                              kit_sync_message=data.get('message'))
            else:
                result.update(status='done', note='Dry run: nothing changed.' if args.dry_run else 'Updated to the {} kit '
                              '{}.'.format(brand['tier_name'], chosen['version'] or ''),
                              kit_sync_message=data.get('message'), kit_sync_status=data.get('status'))
        results.append(result)
    moment = now()
    run_name = None
    if not args.dry_run:
        base = '{} kit-update'.format(moment.date().isoformat())
        run_name, number = base, 2
        while run_file(root, run_name).exists():
            run_name, number = '{} {}'.format(base, number), number + 1
        entries = []
        for brand, result in zip(brands, results):
            entry = entry_for(brand)
            entry.update(status=result['status'], note=result['note'], finished_at=stamp(moment))
            if result.get('kit_sync_message'):
                summary = brand_summary_file(root, run_name, brand['id'])
                write_atomic(summary, (result['kit_sync_message'].strip() + '\n').encode('utf-8'))
                entry['summary_file'] = rel(root, summary)
            entries.append(entry)
        data = {'schema': RUN_SCHEMA, 'name': run_name, 'workflow': 'kit-update', 'workflow_name': 'Kit update',
                'kind': 'kit-update', 'goal': None, 'scheduled': False, 'status': 'open', 'started_at': stamp(moment),
                'finished_at': None, 'plugin_version': plugin, 'note_file': None, 'closed_runs': [], 'brands': entries,
                'zips': {tier: {'file': item['path'].name, 'version': item['version']} for tier, item in zips.items()}}
        note_path = run_note_file(root, run_name)
        write_atomic(note_path, run_note(root, data, moment).encode('utf-8'))
        data.update(status='finished', finished_at=stamp(moment), note_file=rel(root, note_path))
        save_run(run_file(root, run_name), data)
    done = [item for item in results if item['status'] == 'done']
    needs = [item for item in results if item['status'] in ('failed', 'needs-answer')]
    message = ('{}: {} of {} brands {}.'.format('Dry run' if args.dry_run else 'Kit update', len(done), len(results),
                                               'would be updated' if args.dry_run else 'updated'))
    if needs:
        message += ' Needs you: {}.'.format('; '.join('{} ({})'.format(item['name'], one_line(item['note'], 160).rstrip(
            '.')) for item in needs))
    return {'schema': SCHEMA, 'command': 'update', 'workspace': str(root), 'dry_run': bool(args.dry_run),
            'plugin_version': plugin, 'results': results, 'run': run_name,
            'note_file': rel(root, run_note_file(root, run_name)) if run_name else None, 'member_message': message,
            'how_to_continue': ("Pass on each brand's kit-sync summary in plain words (kit_sync_message), brand by brand, "
                                'as the kit-sync skill says, and deal with anything that needs the member.')}


# ---------------------------------------------------------------- all-brands scheduled tasks

def routine_prompt(root, workflow):
    label, kind, first = WORKFLOWS[workflow]
    shown = portable_path(root)        # each run of the task is a new session: never this session's own mount path
    lines = ['# All brands: {}'.format(label), '',
             'Workspace folder: `{}`. This scheduled task covers every brand in this workspace, one brand at a time, '
             'each in its own business folder with its own Amazon account. It runs only after the member approved its '
             'timing, this folder and its notifications.'.format(shown), '']
    if shown != str(root):
        lines += ['`$HOME` is the home folder of the session the task runs in: the Claude app mounts the connected folder '
                  '`{}` at `$HOME/mnt/{}` in every session.'.format(shown.split('/')[2], shown.split('/')[2]), '']
    lines += ["Use the caiman skill and its workspace guide (`references/workspace.md`). `workspace.py` is in the caiman "
              "skill's `scripts` folder; below it is `<workspace.py>`. On Windows, use `py -3` where it says `python3`.", '']
    root = shown
    steps = ['Start this run, or pick up today\'s if it stopped: `python3 "<workspace.py>" run start {} --workspace '
             '"{}" --scheduled`. Keep the run name it gives (`run`): every later command names it with `--run`, so '
             'this task never works on another run.'.format(workflow, root)]
    if workflow in PREFETCH_WORKFLOWS:
        # Caiman 0.3.17: every brand's reports are asked for first, each with that brand's own slug.
        steps.append("Before any brand's work, request every brand's reports if `run start` lists them (`prefetch`): for "
                     "each brand there, call each read's tool with its arguments exactly as given (that brand's own "
                     "`brand_slug`), and record the report IDs with that brand's `record` command. Don't wait for the "
                     "reports: each brand's task polls its own (`task.reports`). A request that errors is recorded with "
                     "`--failed` and that brand's task asks for it again.")
    if kind == 'routine':
        steps.append("For the brand it gives (`task`), read that brand's own VIP Machine routine prompt "
                     "(`task.start.routine_prompt`) and follow it for that brand, with the folders in `task.start.replace` "
                     'put in for its placeholders. Brands without a VIP Machine are already listed as skipped.')
    else:
        steps.append("For the brand it gives (`task`), run `task.start` (CLIENT_START.py in that brand's own kit) and do "
                     'the {} as that brand\'s kit says, in its folder and with its account only (`task.account`).'.format(
                         label))
    steps += [
        'This is a scheduled run: read data and prepare only. Never change an Amazon account, never treat this run as '
        'approval, and leave every proposal for the member.',
        "When the brand is finished, save a few lines in `task.summary_file` (what was done, the numbers that matter, "
        'what needs the member), then record it with `task.when_done`. If the brand fails or needs the member, record '
        '`--status failed` or `--status needs-answer` with what is needed, and go on. Never carry one brand\'s data, '
        "files or account into another's.",
        'Run `task.next` (`python3 "<workspace.py>" run next --workspace "{}" --run "<run>" --session "<session>"`, '
        'with the session `run start` gave) for the next brand, until it says every brand has a result. A brand '
        'another session is still working on is left to it: carry on with the others, and if it says only such brands '
        'are left, stop there without finishing (that session finishes the run).'.format(root),
        'Finish with `python3 "<workspace.py>" run finish --workspace "{}" --run "<run>"` (add `--partial` if a brand '
        'couldn\'t be reached). Tell the member only what they need to act on, from the combined note it writes, brand '
        'by brand.'.format(root)]
    lines += ['{}. {}'.format(number, step) for number, step in enumerate(steps, 1)]
    return '\n'.join(lines) + '\n'


def cmd_routine(args):
    root = workspace_root(args.workspace)
    plugin = plugin_version(args.plugin_version)
    brands, skipped, alerts, saved = current_brands(root, plugin)
    if args.action == 'prompt':
        workflow = workflow_key(args.workflow or '')
        if workflow not in ROUTINE_TIMING:
            raise WorkspaceError('An all-brands scheduled task can run: {}.'.format(', '.join(sorted(ROUTINE_TIMING))))
        label, kind, first = WORKFLOWS[workflow]
        covers = [brand for brand in brands if not not_for_this_run(kind, brand, alerts)]
        return {'schema': SCHEMA, 'command': 'routine prompt', 'workspace': str(root), 'workflow': workflow,
                'name': 'All brands: ' + label, 'suggested_timing': ROUTINE_TIMING[workflow],
                'covers': [brand['name'] for brand in covers], 'prompt': routine_prompt(root, workflow),
                'member_message': 'One scheduled task, "All brands: {}", would cover {}. It stays off until you approve '
                                  'its timing, this folder and who is told.'.format(label, names(
                                      [brand['name'] for brand in covers]) or 'no brand yet'),
                'how_to_continue': ('Only after the member approves the timing and time zone, this folder and who is '
                                    'told: create the task with this prompt as printed (it finds workspace.py in the '
                                    'caiman skill when it runs), read it back, and follow the workspace guide\'s '
                                    '"Scheduled tasks" for the VIP Machine routines\' approval records.')}
    rows = []
    for workflow, timing in sorted(ROUTINE_TIMING.items()):
        label, kind, first = WORKFLOWS[workflow]
        rows.append({'workflow': workflow, 'name': 'All brands: ' + label, 'suggested_timing': timing,
                     'covers': [brand['name'] for brand in brands if not not_for_this_run(kind, brand, alerts)]})
    own = []
    for brand in brands:
        if brand.get('vip_machine_folder'):
            folder = brand_folder(root, brand)
            config = as_dict(read_json(folder.joinpath(*brand['vip_machine_folder'].split('/')) / 'config' / 'brand.json'))
            tasks = as_dict(as_dict(config.get('schedule')).get('tasks'))
            on = [task for task, item in sorted(tasks.items()) if as_dict(item).get('enabled') is True]
            plan = as_dict(read_json(folder / 'SCHEDULE_PLAN.json'))
            own.append({'brand': brand['id'], 'name': brand['name'], 'vip_machine_routines_on': on,
                        'schedule_approved': plan.get('member_approved') is True})
    return {'schema': SCHEMA, 'command': 'routine list', 'workspace': str(root), 'routines': rows,
            'brand_routines': own,
            'member_message': 'Each all-brands routine is one scheduled task that covers every brand it applies to. None '
                              'is on until you approve it.'}


# ---------------------------------------------------------------- one Caiman Dashboard over every brand (0.3.17)

DASHBOARD_SECONDS = 600


def dashboard_program(folder):
    """The brand's own kit DASHBOARD.py (in its guide folder), or None when its kit is older than the dashboard."""
    path = guide_folder(folder) / 'DASHBOARD.py'
    return path if path.is_file() else None


def cmd_dashboard(args):
    """Build each brand's Caiman Dashboard with that brand's own kit (DASHBOARD.py in its business folder), then merge
    them into <workspace>/outputs/dashboard/<date>/: one dashboard with "All brands" and each brand. It reads only
    each brand's saved files, never contacts Amazon and never changes an account."""
    root = workspace_root(args.workspace)
    plugin = plugin_version(args.plugin_version)
    brands, skipped, alerts, saved = current_brands(root, plugin)
    if not brands:
        raise WorkspaceError("There are no Caiman business folders in {} (Claude looked three levels down), so there's no "
                             'dashboard to build. Run workspace.py find to see what is here.'.format(root))
    chosen = pick_brands(brands, args.brands)
    results, built = [], []
    for brand in chosen:
        folder = brand_folder(root, brand)
        entry = {'brand': brand['id'], 'name': brand['name'], 'folder': brand['folder'], 'tier': brand.get('tier')}
        why = not_for_this_run('kit', brand, alerts)
        program = dashboard_program(folder)
        if why:
            entry.update({'status': 'skipped', 'note': why})
        elif program is None:
            entry.update({'status': 'needs-kit-update', 'note': "This brand's kit is older than the Caiman Dashboard (it has "
                                                                 'no DASHBOARD.py). Update it with kit-sync ("Update all '
                                                                 'my brands"), then build the dashboard again.'})
        else:
            argv = [python(), str(program), '--project-root', str(folder)]
            if args.today:
                argv += ['--today', args.today]
            code, out, err, failed = run_program(argv, folder, args.timeout)
            data = json_from(out) or {}
            if failed or code != 0 or data.get('status') != 'built':
                entry.update({'status': 'failed', 'note': one_line(
                    data.get('member_message') or failed or err or 'its DASHBOARD.py gave no result', 400)})
            else:
                entry.update({'status': 'built', 'dashboard_folder': rel(root, Path(data.get('folder') or folder)),
                              'fallback': rel(root, Path(data['fallback'])) if data.get('fallback') else None,
                              'missing': len(data.get('missing') or []), 'next_read': data.get('next_read'),
                              'note': one_line(data.get('member_message'), 400)})
                built.append((brand, folder, program))
        results.append(entry)
    merged = None
    if built:
        def kit_rank(item):
            number = re.sub(r'\D', '', str(item[0].get('kit_version') or ''))
            return (parse_version(item[0].get('kit_core_version') or '') or (0, 0, 0), int(number) if number else 0)
        merger = max(built, key=kit_rank)[2]
        argv = [python(), str(merger), '--merge'] + [str(folder) for _, folder, _ in built] + ['--out-root', str(root)]
        if args.today:
            argv += ['--today', args.today]
        code, out, err, failed = run_program(argv, root, args.timeout)
        data = json_from(out) or {}
        if failed or code != 0 or data.get('status') != 'merged':
            merged = {'status': 'failed', 'note': one_line(data.get('member_message') or failed or err or
                                                           'the merge gave no result', 400)}
        else:
            merged = {'status': 'merged', 'folder': rel(root, Path(data['folder'])),
                      'fallback': rel(root, Path(data['fallback'])), 'page': rel(root, Path(data['page'])),
                      'brands': [item.get('brand') for item in data.get('brands') or []],
                      'note': one_line(data.get('member_message'), 600),
                      'publish_plan_command': 'python3 {} --project-root {} --publish-plan'.format(quoted(merger),
                                                                                                quoted(root))}
    done = [entry for entry in results if entry['status'] == 'built']
    others = [entry for entry in results if entry['status'] != 'built']
    if merged and merged['status'] == 'merged':
        message = 'Built one Caiman Dashboard over {}: {}.'.format(plural(len(done), 'brand'), names(
            [entry['name'] for entry in done]))
    elif done:
        message = "Built {}'s dashboard{}, but couldn't put them together: {}".format(
            names([entry['name'] for entry in done]), 's' if len(done) > 1 else '', (merged or {}).get('note'))
    else:
        message = "No brand's dashboard could be built."
    if others:
        message += ' Not in it: {}.'.format('; '.join('{} ({})'.format(entry['name'], entry['note'].rstrip('.'))
                                                      for entry in others))
    return {'schema': SCHEMA, 'command': 'dashboard', 'workspace': str(root), 'plugin_version': plugin,
            'status': 'built' if merged and merged['status'] == 'merged' else ('partial' if done else 'failed'),
            'brands': results, 'merged': merged, 'member_message': message,
            'how_to_continue': ("Open the merged dashboard: publish it as one Claude Dashboard artifact with the publish "
                                "plan (merged.publish_plan_command; the kit's CAIMAN DASHBOARD.md, \"Several brands\"), "
                                'or give the member merged.fallback, the offline copy. For a brand that needs a kit '
                                'update or failed, say so plainly and carry on with the others.')}


# ---------------------------------------------------------------- the command line

def build_parser():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest='command')

    def common(sub):
        sub.add_argument('--workspace', '--folder', '--project-root', dest='workspace', default='.',
                         help='The folder that holds the brand folders (default: the current folder).')
        sub.add_argument('--plugin-version', help="The Caiman plugin's version, for a copy of this file run away from "
                                                  'the plugin.')
        return sub

    common(commands.add_parser('find', help='List the business folders here and what each one is.'))
    common(commands.add_parser('init', help='Write CAIMAN WORKSPACE.json, the CLAUDE.md section and START HERE.'))
    status = common(commands.add_parser('status', help='One table across the brands.'))
    status.add_argument('--brands', help='Only these brands (IDs, names, folders or slugs, separated by commas).')
    status.add_argument('--quick', action='store_true', help="Read files only; don't run the kits' scripts.")
    plan = common(commands.add_parser('plan', help="Merge each brand's NEXT_STEP.py into one ranked plan."))
    plan.add_argument('--brands')
    plan.add_argument('--timeout', type=int, default=STEP_SECONDS, help='Seconds each brand\'s NEXT_STEP.py may take.')
    plan.add_argument('--per-brand', type=int, default=3, help='Steps per brand in the plan (default 3).')
    run = commands.add_parser('run', help='A resumable run of one workflow across the brands.')
    run_commands = run.add_subparsers(dest='run_command')
    start = common(run_commands.add_parser('start', help='Start a run (or pick up an unfinished one).'))
    start.add_argument('workflow', help='The workflow: ' + ', '.join(sorted(
        name for name in WORKFLOWS if WORKFLOWS[name][1] != 'kit-update')))
    start.add_argument('--brands')
    start.add_argument('--goal', help="The member's request in their words (needed for the workflow \"request\").")
    start.add_argument('--scheduled', action='store_true', help='A scheduled task: read and prepare only.')
    start.add_argument('--new', action='store_true', help='Start a new run even if one for this workflow is unfinished.')
    session_help = "This session's name from an earlier answer (session), so it keeps its own brand."
    start.add_argument('--session', help=session_help)
    nxt = common(run_commands.add_parser('next', help='The next brand in the unfinished run.'))
    nxt.add_argument('--run', help='The run (its file name without .json); default: the newest unfinished one.')
    nxt.add_argument('--session', help=session_help)
    nxt.add_argument('--take-over', dest='take_over', metavar='BRAND',
                     help='Carry on here with a brand another session had (the member chose it).')
    nxt.add_argument('--leave', action='append', metavar='BRAND',
                     help='Leave a brand to the session that has it and go on with the next one (the member chose it).')
    done = common(run_commands.add_parser('done', help="Record one brand's result."))
    done.add_argument('brand')
    done.add_argument('--run')
    done.add_argument('--status', required=True, choices=DONE_STATUSES)
    done.add_argument('--note', help='One line: what was done, or what is needed.')
    done.add_argument('--summary', help="The brand's summary file (inside the workspace folder).")
    done.add_argument('--session', help=session_help)
    reports = common(run_commands.add_parser('reports', help="Record (or show) one brand's report IDs in the run."))
    reports.add_argument('brand')
    reports.add_argument('--run')
    reports.add_argument('--session', help=session_help)
    reports.add_argument('--add', action='append', metavar='READ=ID',
                         help='A read and the report ID its request returned (several IDs separated by commas).')
    reports.add_argument('--failed', action='append', metavar='READ=WHY',
                         help='A read whose request failed, and what it said; that brand\'s task asks for it again.')
    run_status = common(run_commands.add_parser('status', help='Where the run stands.'))
    run_status.add_argument('--run')
    run_status.add_argument('--session', help=session_help)
    finish = common(run_commands.add_parser('finish', help='Write the combined note and close the run.'))
    finish.add_argument('--run')
    finish.add_argument('--partial', action='store_true', help='Finish even though some brands have no result.')
    finish.add_argument('--session', help=session_help)
    summary = common(commands.add_parser('summary', help='One read-only page across the brands.'))
    summary.add_argument('--brands')
    summary.add_argument('--quick', action='store_true', help="Read files only; don't run the kits' scripts.")
    update_plan = common(commands.add_parser('update-plan', help="Each brand's kit against this plugin."))
    update_plan.add_argument('--brands')
    update_plan.add_argument('--kit-sync', help='kit_sync.py, when it is not next to the caiman skill.')
    update_plan.add_argument('--live-kit', action='append', help="The release the Caiman connector's get_kit_download "
                                                                 'names for a membership (once per membership), or @ '
                                                                 'and the file holding its result.')
    update = common(commands.add_parser('update', help='Update every brand whose kit needs it, one at a time.'))
    update.add_argument('--zip', action='append', help='A kit zip; give one for each membership in the workspace.')
    update.add_argument('--brands')
    update.add_argument('--dry-run', action='store_true', help='Show what would change without changing anything.')
    update.add_argument('--all', action='store_true', help='Install even where the kit is already current.')
    update.add_argument('--kit-sync', help='kit_sync.py, when it is not next to the caiman skill.')
    update.add_argument('--timeout', type=int, default=900, help='Seconds one brand\'s install may take.')
    routine = common(commands.add_parser('routine', help='All-brands scheduled tasks: list them, or print one prompt.'))
    routine.add_argument('action', choices=('list', 'prompt'))
    routine.add_argument('workflow', nargs='?')
    dashboard = common(commands.add_parser('dashboard', help="Build each brand's Caiman Dashboard and merge them into "
                                                             'one.'))
    dashboard.add_argument('--brands', help='Only these brands (IDs, names, folders or slugs, separated by commas).')
    dashboard.add_argument('--today', help="The day to build (YYYY-MM-DD); default: today in each account's time zone.")
    dashboard.add_argument('--timeout', type=int, default=DASHBOARD_SECONDS,
                           help="Seconds each brand's DASHBOARD.py may take.")
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    handlers = {'find': cmd_find, 'init': cmd_init, 'status': cmd_status, 'plan': cmd_plan, 'summary': cmd_summary,
                'update-plan': cmd_update_plan, 'update': cmd_update, 'routine': cmd_routine}
    run_handlers = {'start': cmd_run_start, 'next': cmd_run_next, 'done': cmd_run_done, 'status': cmd_run_status,
                    'finish': cmd_run_finish, 'reports': cmd_run_reports}
    handlers['dashboard'] = cmd_dashboard
    if args.command == 'run':
        handler = run_handlers.get(getattr(args, 'run_command', None))
    else:
        handler = handlers.get(args.command)
    if handler is None:
        parser.print_help()
        return 2
    try:
        result = handler(args)
    except WorkspaceError as error:
        print(json.dumps({'schema': SCHEMA, 'command': ' '.join(part for part in (
            args.command, getattr(args, 'run_command', None)) if part), 'status': 'error',
            'member_message': str(error)}, indent=2, ensure_ascii=True))
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
