#!/usr/bin/env python3
"""Caiman workspace: one member's brands, each in its own business folder, under one folder.

  python3 workspace.py find        --workspace "<folder>"
  python3 workspace.py init        --workspace "<folder>"
  python3 workspace.py status      --workspace "<folder>" [--brands "<brand>,<brand>"] [--quick]
  python3 workspace.py plan        --workspace "<folder>" [--brands "<brand>,<brand>"] [--timeout 180]
                                   [--max-seconds 150] [--session "<session>"]
  python3 workspace.py run start   <workflow> --workspace "<folder>" [--brands ...] [--goal "<request>"] [--scheduled] [--new]
                                   [--session "<session>"]
  python3 workspace.py run next    --workspace "<folder>" [--run "<run>"] [--session "<session>"]
                                   [--brand <brand>] [--take-over <brand> | --leave <brand>]
  python3 workspace.py run done    <brand> --workspace "<folder>" --status done|skipped|failed|needs-answer --note "..."
                                   [--summary <file>] [--run "<run>"] [--session "<session>"]
  python3 workspace.py run reports <brand> --workspace "<folder>" --run "<run>" [--session "<session>"]
                                   [--add "<read>=<report id>" ...] [--failed "<read>=<what it said>" ...]
  python3 workspace.py run status  --workspace "<folder>" [--run "<run>"]
  python3 workspace.py run finish  --workspace "<folder>" [--partial] [--run "<run>"] [--session "<session>"]
  python3 workspace.py summary     --workspace "<folder>" [--brands ...] [--quick]
  python3 workspace.py update-plan --workspace "<folder>" [--live-kit <release> ...]
  python3 workspace.py update      --workspace "<folder>" --zip "<kit zip>" [--zip "<other tier's kit zip>"] [--dry-run]
  python3 workspace.py routine     list|prompt [<workflow>] --workspace "<folder>"
  python3 workspace.py puller      --workspace "<folder>" [--on [--by "<who>"] | --off]
  python3 workspace.py handoff     --workspace "<folder>" [--session "<session>"]

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
             WORKSPACE PLAN.json. Caiman's own unfinished work across the brands (a run that stopped partway, brands a
             run was finished without) comes first after kit updates, to carry on without asking; a run another session
             is still working through is left to it and said so. Each brand's answer is kept as it arrives
             (.caiman/workspace-plan-partial.json, Caiman 0.3.58), so a call that is cut off is carried on by the next:
             the same command again asks only the brands not answered in the last 30 minutes. --max-seconds N stops
             asking in time to answer (in_progress, with the brands left) and leaves the plan on disk as it is.
run          a resumable run of one workflow across the brands: start writes workspace-runs/<date> <workflow>.json with
             each brand pending; next names the next brand, its folder and account and how to start the workflow there;
             done records a brand's result (and its handoff, saved in the task's handoff_file); finish writes one
             combined note from each brand's summary, ending with one handoff: what's done, the account changes waiting
             for the member's go numbered across the brands, what Caiman needs from the member and what's next. An
             unfinished run continues with next. Brands a run was finished without stay to do: the next start of the
             same workflow, next or plan carries them on first. A brand handed to one session stays with it until it's
             recorded: another session leaves it and moves on, and takes it over (saying so; --leave gives it back)
             only once that session has most likely stopped (30 minutes for a conversation, three hours for a scheduled
             run or a brand handed out by name with --brand; each time that session records its report IDs with run
             reports counts it alive again). A VIP brand that shares its account with another brand and has no brand scope saved is flagged.
             For the report-heavy workflows (the Advertising Daily Check, both weekly reviews and the VIP
             Machine's weekly loop) start first asks for every brand's Ads reports, each with that brand's own slug;
             reports records their IDs per brand, and each brand's task polls its own instead of requesting them again.
             The daily check's Sponsored Products read is the one the brand's own STOP_LINES.py due asks for, when that
             covers its days, so it is asked for and saved once.
summary      one read-only page across the brands from their latest saved outputs: WORKSPACE SUMMARY.html and .md.
             With a VIP Machine brand scope, figures built for the whole seller account are said to be so.
update-plan  each brand's kit against this plugin, and how to update them all.
update       updates every brand whose kit needs it, one folder at a time, with kit-sync and the kit zip for that
             brand's own membership; one result per brand. It never switches a brand to the other membership.
routine      the all-brands scheduled tasks: list says which brands each would cover; prompt prints the prompt for
             one, to create only after the member approves it.
puller       (Caiman 0.3.58) the report puller's one switch for this workspace, or for one business folder (CAIMAN
             OPERATOR.json, the file 0.3.57's operator command wrote; operator --name "<who>" still switches it on).
             With it on, work that needs no go is done before the handoff, never offered, and Next holds only what waits
             on a date, a person or a go; plan, run finish and the setup check say so (report_puller). --off takes it
             back. Every account change waits for its go either way.

Workflows a run takes: deep-seed, weekly-growth-review, listing-creative-pack, stock-profit-plan,
advertising-weekly-review, advertising-daily-check, advertising-structure-review (each brand's own CLIENT_START.py),
setup-check, request (the member's own words, --goal), the VIP Machine's routines vip-weekly-loop,
vip-daily-brief, vip-health-check and vip-opportunity-review (each VIP brand's own routine prompt), and (Caiman 0.3.57)
suite, the day across the brands ("daily checks"): every brand, in order, the Advertising Daily Check, and on Monday
the week too (the VIP week's close, the Weekly Growth Review and what last week's changes did); Tuesday to Friday
whatever of the week is still open, worked out from each brand's own files, and what the last suite left open first.
Its run start asks Amazon for the week's slowest report with the day's reads and the rest of the week's in rounds after
them, so they are made while the daily checks are worked; each brand's weekly close collects them last. Every run's
finish rebuilds WORKSPACE PLAN.md (Caiman 0.3.57).

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
import time
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
# Caiman 0.3.58 (FLAGS F157; Jonah, Nov 24: "the intent is more of a pre emptive worker that gets all those files and
# reports called on and done so you don't have to wait on read work ... the report puller is already built so the operator
# switch I guess just needs to be merged to that"): the report puller is one feature with one switch, included in the
# membership. With it on, work that needs no go is done, never offered ("say next"), and Next holds only what waits on a
# date, a person or a go. The switch is the file 0.3.57's operator command wrote (FLAGS F148: "operator mode", an agency's
# workspace), under the puller's name in every word a member reads; where the puller pulls from is the puller's own
# matter (today PULL_REPORTS.py on the owner's computer; hosted by the Caiman team once the connector has it).
OPERATOR_FILE = 'CAIMAN OPERATOR.json'
OPERATOR_SCHEMA = 'caiman.operator.v1'
PULLER_DEFAULT_BY = 'the owner'
PULLER_WORDS = ("The report puller is on for this workspace{}: work that needs no go (a read, a pull, a run's brands not "
                "reached, a review) is done now, before the handoff, never offered with \"Say next\". The handoff's Next "
                'holds only what waits on a date, a person or a go, each saying what it waits on. Every account change '
                'still waits for its go.')
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
PLAN_WORKERS = 4                    # brands whose NEXT_STEP.py runs at once in plan (Caiman 0.3.57)
# Caiman 0.3.58 (FLAGS P374): plan keeps each brand's answer as it arrives, so a call that is cut off (a session that may
# run a command only about three minutes, with a dozen brands on a synced drive) is carried on by the next one. One
# workspace's WORKSPACE PLAN.md went 39 days without a rebuild because the command never finished in one go.
PLAN_PARTIAL = '.caiman/workspace-plan-partial.json'
PLAN_PARTIAL_SCHEMA = 'caiman.workspace-plan-partial.v1'
PLAN_PICKUP_MINUTES = 30            # how long a brand's kept answer stands in for asking the brand again
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
    # Caiman 0.3.57 (FLAGS F147): the day across the brands in one run. Every brand, in order: the Advertising Daily
    # Check, and on Monday the week too (the VIP week's close, the Weekly Growth Review and what last week's changes did);
    # other days the daily check and what of the week is still open. Its steps are worked out from each brand's files.
    'suite': ('The daily suite', 'suite', None),
}
# Runs of these start fresh each day: yesterday's unfinished run is closed rather than continued.
DAILY = ('advertising-daily-check', 'vip-daily-brief', 'vip-health-check', 'setup-check', 'suite')
# An unfinished run of the other workflows this many days old is closed, not continued, when a new one starts.
STALE_DAYS = 6
DONE_STATUSES = ('done', 'skipped', 'failed', 'needs-answer')
STATUS_WORDS = {'pending': 'Not started', 'in-progress': 'In progress', 'done': 'Done', 'skipped': 'Skipped',
                'failed': "Didn't finish", 'needs-answer': 'Needs your answer', 'not-run': 'Not run'}
# The search for business folders looks at no more folders than this (as the setup check does): a home, Documents or
# Dropbox folder opened by mistake isn't searched through (Caiman 0.3.17).
DISCOVER_MAX_FOLDERS = 3000
# A brand handed to one session stays that session's until it's recorded (Caiman 0.3.17). Caiman 0.3.34: another
# conversation leaves it to that session while the claim is newer than CONVERSATION_HOLD_MINUTES and goes on with the
# next brand (when only such brands are left, it asks whether that session stopped); an older claim it carries on
# without asking, and says so. A scheduled run leaves it unless that session has had it CLAIM_HOLD_MINUTES or more (it
# most likely stopped). Two sessions never do one brand at once.
CLAIM_HOLD_MINUTES = 180
CONVERSATION_HOLD_MINUTES = 30


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


# Caiman 0.3.58 (FLAGS P372): the time a workspace's own pages show. Until then every time here came from the clock
# of the computer the command ran on, which in a cloud session linked to the member's computer is UTC: on Nov 24 the plan
# across 16 brands said "6:31 PM" at 11:31 am Mountain time, and a run started in the evening took the next day's name.
# Now, on a computer whose clock is UTC, the pages show the time zone most of the brands have saved (the rule each brand's
# own CAIMAN STATUS.md follows, setup_check.py's shown_zone), with the zone's name beside every time; a computer with a
# zone of its own keeps its time, with that zone's name beside it. page_zone sets it once a command, from the brands'
# folders (current_brands, find_run).
_PAGE = {}
_SETUP_CHECK = []


def setup_check_rules():
    """This skill's setup_check.py, loaded once: the one home of the time zone rules a status page follows. None when it
    can't be loaded (the pages then keep the computer's own time, as before 0.3.58)."""
    if not _SETUP_CHECK:
        module = None
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location('_caiman_workspace_setup_check', str(HERE / 'setup_check.py'))
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        except Exception:
            module = None
        _SETUP_CHECK.append(module)
    return _SETUP_CHECK[0]


# Caiman 0.3.58 (FLAGS F158, the files; the owner, Nov 24, 2026: "rules and things we're working on, like being forgotten
# somehow, and work getting lost"): a workspace's two named homes, named once, in the setup check. The owner's rules for
# every brand are written by a kit's CLIENT_RULES.py set --workspace; the page of work in flight is written here
# (write_flight) when a run finishes and when a session hands off (the handoff command), and the setup check reads both
# at the start of the next session.
RULES_FILE = getattr(setup_check_rules(), 'WORKSPACE_RULES_FILE', None)
FLIGHT_FILE = getattr(setup_check_rules(), 'WORK_IN_FLIGHT_FILE', None)
FLIGHT_SCHEMA = getattr(setup_check_rules(), 'FLIGHT_SCHEMA', 'caiman.work-in-flight.v1')
FLIGHT_RECENT_DAYS = 14                 # a finished run's go lines and asks stay on the page this long
FLIGHT_DUE_SOON_DAYS = 14               # a brand's dated to-do is listed from this many days before it
FLIGHT_LINES = 25                       # at most this many lines a part; the rest are counted, with where they are
FLIGHT_RULES = 8
DUE_LINE = re.compile(r'^\s*(?:[-*+]\s+|\d+[.)]\s+)?(?:\*\*|__)?\s*DUE\s+([^:]{6,40}?)\s*:\s*(.*)$')     # STOP_LINES.py's
BLOCK = re.compile(r'<!--\s*CAIMAN\s+RULES\s+START\b.*?<!--\s*CAIMAN\s+RULES\s+END\s*-->', re.I | re.S)


def page_zone(root, folders, moment=None):
    """Works out and keeps the time zone this workspace's own pages show: {'zone': its name or None, 'utc': True when
    it is UTC for want of a saved zone, 'words': what stands beside every time ('Mountain time', 'UTC', 'MST'), 'note':
    the page's one sentence about it, or None}. folders: the brands' business folders."""
    moment = moment or dt.datetime.now().astimezone()
    rules = setup_check_rules()
    page = {'zone': None, 'utc': False, 'words': None, 'note': None}
    try:
        if rules is None or not rules.utc_clock(moment):
            local = moment.astimezone()             # the computer has a zone of its own: its time, named
            name = local.tzname() or ''
            minutes = int((local.utcoffset() or dt.timedelta(0)).total_seconds() // 60)
            page['words'] = name if re.fullmatch(r'[A-Za-z]{2,5}', name) else (rules.utc_words(minutes) if rules else None)
        else:
            found = rules.workspace_zone([Path(folder) for folder in folders], moment)
            if found:
                name = rules.zone_name(found['zone'])
                label = rules.zone_label(rules.in_zone(moment, found['zone']))
                whose = ('your time zone' if found['whose'] == 'member' else "your Amazon account's time zone") \
                    if found['brands'] == found['of'] else 'the time zone {} of your {} brands have saved'.format(
                        found['brands'], found['of'])
                page.update(zone=found['zone'], words=name,
                            note='Times here are in {} ({}), {}.'.format(name, label, whose))
            else:
                page.update(utc=True, words='UTC', note='Times here are in UTC: no brand here has a time zone saved.')
    except Exception:                               # the pages never stop on this: the computer's own time, as before
        page = {'zone': None, 'utc': False, 'words': None, 'note': None}
    _PAGE.clear()
    _PAGE.update(page)
    return page


def at_page(moment):
    """moment in the zone the workspace's pages show (page_zone), else in the computer's own."""
    if _PAGE.get('zone'):
        rules = setup_check_rules()
        if rules is not None:
            return rules.in_zone(moment, _PAGE['zone'])
    if _PAGE.get('utc'):
        return moment.astimezone(dt.timezone.utc)
    return moment.astimezone()


def now():
    return at_page(dt.datetime.now().astimezone())


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
    local = at_page(moment)
    return '{} {}, {}'.format(MONTHS[local.month - 1], local.day, local.year)


def plain_day(day):
    """'November 30, 2026' for a calendar day as it is written (a DUE line's day): never moved by a time zone."""
    return '{} {}, {}'.format(MONTHS[day.month - 1], day.day, day.year)


def plain_time(moment):
    """'November 24, 2026 at 11:31 AM Mountain time': in the zone the pages show, with its name beside it (page_zone)."""
    local = at_page(moment)
    return '{} at {}:{:02d} {}{}'.format(plain_date(local), local.hour % 12 or 12, local.minute,
                                         'AM' if local.hour < 12 else 'PM',
                                         ' ' + _PAGE['words'] if _PAGE.get('words') else '')


def one_line(text, limit=300):
    text = ' '.join(str(text or '').split())
    return text if len(text) <= limit else text[:limit - 3] + '...'


def plural(count, one, many=None):
    return '{} {}'.format(count, one if count == 1 else (many or one + 's'))


def unique(values):
    """values without repeats, in their order."""
    out = []
    for value in values:
        if value not in out:
            out.append(value)
    return out


def names(items):
    items = [item for item in items if item]
    if len(items) <= 1:
        return ''.join(items)
    return ', '.join(items[:-1]) + ' and ' + items[-1]


def write_atomic(path, data):
    """Write bytes to path through a temporary file beside it, so a stopped write never leaves half a file (Caiman
    0.3.43, C8: written in place where the folder refuses replacing)."""
    write_whole(path, data)


def write_whole(path, data):
    """Caiman 0.3.43 (build list C8): a file this script may rewrite, written whole. The same function is in every kit
    script and engine file that rewrites a file (tests/v343_writers checks the copies match). `data` is bytes or text
    (written as UTF-8). The bytes go to a hidden temporary file beside the file, which then replaces it in one step, so a
    reader never sees half a file. Where the folder refuses that (the member's computer driven from a Cowork or cloud
    session won't let a file be replaced or deleted; some mounted or synced folders), the file is written in place from
    the temporary copy (a file that isn't there yet is simply written) and the copy is removed, or emptied where removing
    is refused, so no non-empty twin is ever left beside the file. Any other failure lets the copy go and raises, and the
    earlier file is kept as it was. Returns the path."""
    import os
    import tempfile
    from pathlib import Path
    path = Path(path)
    raw = data.encode('utf-8') if isinstance(data, str) else bytes(data)
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix='.' + path.name + '.', suffix='.tmp', dir=str(path.parent))
    try:
        with os.fdopen(handle, 'wb') as out:
            out.write(raw)
            out.flush()
            try:
                os.fsync(out.fileno())
            except OSError:
                pass
        try:   # the file keeps its mode, and a new one is readable (mkstemp makes the copy private)
            os.chmod(temporary, (os.stat(str(path)).st_mode & 0o777) if path.is_file() else 0o644)
        except OSError:
            pass
    except BaseException:
        let_go(temporary)
        raise
    put_in_place(temporary, path)
    return path


def put_in_place(temporary, path):
    """The second half of write_whole, for a writer that streams its output to a temporary file beside the target first:
    the copy replaces the target in one step, or, where the folder refuses replacing (EPERM, EACCES, EXDEV, EBUSY), the
    target is written in place from the copy; the copy is then removed, or emptied where removing is refused. Any other
    failure lets the copy go and raises."""
    import errno
    import os
    import shutil
    temporary, path = str(temporary), str(path)
    try:
        os.replace(temporary, path)
        return
    except OSError as error:
        if error.errno not in (errno.EPERM, errno.EACCES, errno.EXDEV, errno.EBUSY):
            let_go(temporary)
            raise
    try:
        with open(temporary, 'rb') as source, open(path, 'wb') as out:
            shutil.copyfileobj(source, out, 1024 * 1024)
    finally:
        let_go(temporary)


def let_go(path):
    """A temporary file no longer needed: removed where removing is allowed, else emptied so it holds nothing (silent)."""
    import os
    try:
        os.remove(str(path))
        return
    except OSError:
        pass
    try:
        if os.path.isfile(str(path)):
            with open(str(path), 'wb'):
                pass
    except OSError:
        pass


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


def id_parts(brand):
    return brand['folder'].split('/') if brand['folder'] != '.' else [brand.get('name') or 'this-folder']


def brand_ids(brands):
    """A short, stable ID for each brand: its folder's name, made unique with its parent folders when needed. Caiman
    0.3.41 (FLAGS P109): a folder name more than one brand has (caiman-business in brand-a/caiman-business and
    brand-b/caiman-business) is no brand's ID: each takes its parent folders too, so no ID is another's."""
    taken = {}
    for brand in brands:
        parts = id_parts(brand)
        for size in range(1, len(parts) + 1):
            candidate = slugify('-'.join(parts[-size:]))
            shared = any(other is not brand and slugify('-'.join(id_parts(other)[-size:])) == candidate for other in brands)
            if candidate not in taken and not shared:
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


# Caiman 0.3.58 (FLAGS P371): what this script writes in the workspace's own files (WORKSPACE PLAN.json) and every
# command line and path it hands a session start at the workspace's own folder, never at the absolute path of the session
# that ran the command. On Nov 24 one workspace's plan held /sessions/<id>/mnt/... in 179 places, and 365 files under it
# held such a path: the notes, briefs and scripts sessions had saved from the lines they were handed. No later session and
# no Terminal on the computer has that path. A brand's own kit still answers with absolute paths (NEXT_STEP.py's
# agent_command); they are rewritten here. A scheduled task's prompt is the exception (routine prompt): it starts in no
# folder, so it keeps the 0.3.24 rule, $HOME/mnt/... (portable_path).
RUN_FROM = ("Every command line, folder and file here starts at the workspace's own folder (the folder given as "
            "--workspace). Run each command line from that folder: cd there first, and --workspace . is that folder. When "
            "you save one in a note, a brief or a script, save it as it is here, never with this session's own path: a "
            "later session, or the Terminal on the same computer, reaches the folder by another one.")
RUN_FROM_FILE = ("Every command line, folder and file in this file starts at the workspace's own folder, the folder this "
                 'file is in: run each command line from there.')
HANDS_COMMANDS = ('plan', 'run', 'dashboard', 'update-plan', 'handoff')
_PATH_BEFORE = r'(?<![\w.\-/\\])'         # not in the middle of a longer path, nor after a URL's slashes


def beside(root, place):
    """A place outside the workspace's folder as a command line names it: from the workspace's own folder (../...)
    when the two share a folder above them, so it holds on the same computer whatever session reaches it; else as
    portable_path gives it."""
    root_text, text = str(root), str(place)
    try:
        common = os.path.commonpath([root_text, text])
    except ValueError:                              # another drive, or one of them isn't absolute
        common = ''
    if common and common != os.path.dirname(common):
        return os.path.relpath(text, root_text)
    return portable_path(text)


def own_places(root, here=None):
    """[(pattern, what stands in its place)] for from_workspace: the workspace's folder itself, and this script's own
    folder when that is somewhere else (here: for a test)."""
    root_text = str(root)
    places = [(re.compile(_PATH_BEFORE + re.escape(root_text) + r'[\\/]+(?=[^\s"\'\\/])'), ''),
              (re.compile(_PATH_BEFORE + re.escape(root_text) + r'[\\/]*(?=$|["\'\s,;)])'), '.')]
    here_text = str(here if here is not None else HERE)
    if here_text != root_text and not here_text.startswith(root_text.rstrip('\\/') + os.sep):
        shown = beside(root, here_text)
        if shown != here_text:
            places.append((re.compile(_PATH_BEFORE + re.escape(here_text) + r'(?=$|[\\/"\'\s])'), shown))
    return places


def from_workspace(root, value, places=None):
    """value (a path, a command line, or lists and dicts holding them) as the workspace's own files and the command
    lines handed to a session write it: a path under the workspace's folder from that folder ('.' for the folder itself),
    and this script's own place by beside(). Everything else is left as it is."""
    if places is None:
        places = own_places(root)
    if isinstance(value, dict):
        return {key: from_workspace(root, item, places) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [from_workspace(root, item, places) for item in value]
    if not isinstance(value, str) or not value:
        return value
    for pattern, shown in places:
        value = pattern.sub(lambda match, shown=shown: shown, value)
    return value


def handed(command, result):
    """A command's answer as it is printed (main): for the commands that hand out command lines, every path from the
    workspace's own folder, 'workspace' as '.', and run_from saying where the lines run."""
    if command not in HANDS_COMMANDS or not isinstance(result, dict):
        return result
    given = result.get('workspace')
    if not isinstance(given, str) or not os.path.isabs(given):
        return result
    out = {}
    for key, item in from_workspace(Path(given), result).items():
        out[key] = item
        if key == 'workspace':
            out['workspace'], out['run_from'] = '.', RUN_FROM
    return out


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
        # Caiman 0.3.41 (FLAGS P109): a saved ID that is a folder name several brands have is replaced
        shared = shared_folder_names(brands)
        used = set()
        for brand in brands:
            if known.get(brand['folder']) and known[brand['folder']] not in used \
                    and name_key(known[brand['folder']]) not in shared:
                old_id, new_id = brand['id'], known[brand['folder']]
                brand['id'] = new_id
                for alert in alerts:
                    alert['brands'] = [new_id if item == old_id else item for item in alert.get('brands', [])]
            used.add(brand['id'])
    page_zone(root, [root / brand['folder'] if brand['folder'] != '.' else root for brand in brands])     # FLAGS P372
    return brands, skipped, alerts, saved


def shared_folder_names(items):
    """The folder names (as name_key gives them) more than one brand's folder ends in."""
    counts = {}
    for item in items:
        key = name_key(Path(item['folder']).name)
        counts[key] = counts.get(key, 0) + 1
    return {key for key, n in counts.items() if n > 1}


def brand_hits(items, raw):
    """The brands (or a run's entries) a name picks (Caiman 0.3.41, FLAGS P109): the one whose ID it is, exactly; else
    those whose name, folder or connector slug it is, or whose folder's own name it is when no other folder has that
    name. Never a part of a name."""
    key = name_key(raw)
    if not key:
        return []
    exact = [item for item in items if name_key(item['id']) == key]
    if exact:
        return exact
    shared = shared_folder_names(items)
    return [item for item in items if key in (name_key(item['name']), name_key(item['folder']), name_key(item.get('slug')))
            or (key == name_key(Path(item['folder']).name) and key not in shared)]


def pick_brands(brands, wanted):
    """The brands a --brands list names (ID, name, folder or connector slug, any case), in workspace order."""
    if not wanted:
        return list(brands)
    chosen = []
    for raw in [part.strip() for part in re.split(r'[,;\n]', wanted) if part.strip()]:
        hits = brand_hits(brands, raw)
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
                                                                                               WORKSPACE_FILE)]
    if RULES_FILE and FLIGHT_FILE:
        # Caiman 0.3.58 (FLAGS F158): the workspace's two named homes, where a session's first minute looks
        lines.append(
            "- **The owner's rules and the work in flight.** `{rules}` holds the owner's rules for every brand (a brand's own "
            "rule beats one of them for that brand), and `{flight}` is the one page of what is in flight across the brands. "
            "The setup check says both at the start. Save a rule the owner says for every brand in that same reply (a "
            "brand's `CLIENT_RULES.py set --workspace`), and end a session that worked across the brands with "
            "`workspace.py handoff`, which writes `{flight}` again.".format(rules=RULES_FILE, flight=FLIGHT_FILE))
    lines.append(SECTION_END)
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

# Caiman 0.3.36: a request started more than a week ago (offer_continue) ranks with unfinished work, as a question.
KIND_RANK = {'continue': 1, 'offer_continue': 1, 'measure': 2, 'setup': 3}


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


def plan_partial(root, plugin, moment):
    """The brands' NEXT_STEP.py answers an unfinished plan kept (PLAN_PARTIAL), by brand ID: only those kept within
    PLAN_PICKUP_MINUTES, under this plugin version; {} when there is none to pick up."""
    saved = as_dict(read_json(root / PLAN_PARTIAL))
    if saved.get('schema') != PLAN_PARTIAL_SCHEMA or saved.get('plugin') != plugin or saved.get('finished_at'):
        return {}
    kept = {}
    for brand_id, entry in as_dict(saved.get('brands')).items():
        entry = as_dict(entry)
        at = parse_time(entry.get('at'))
        if at is None or not isinstance(entry.get('data'), dict):
            continue
        age = (moment - at).total_seconds() / 60
        if 0 <= age <= PLAN_PICKUP_MINUTES:
            kept[brand_id] = entry
    return kept


def keep_plan_partial(root, plugin, kept, started):
    """Write the answers kept so far (every path from the workspace's own folder, as the plan itself is saved). Never
    stops the plan: a folder that refuses the file only means the next call asks every brand again."""
    try:
        (root / PLAN_PARTIAL).parent.mkdir(parents=True, exist_ok=True)
        write_json(root / PLAN_PARTIAL, {'schema': PLAN_PARTIAL_SCHEMA, 'plugin': plugin, 'started_at': started,
                                         'updated_at': stamp(), 'run_from': RUN_FROM_FILE,
                                         'brands': from_workspace(root, kept)})
    except OSError:
        pass


def close_plan_partial(root, plugin, started):
    """The plan is written whole: nothing is left to pick up (the file stays, emptied, as a record of when)."""
    if not (root / PLAN_PARTIAL).is_file():
        return
    try:
        write_json(root / PLAN_PARTIAL, {'schema': PLAN_PARTIAL_SCHEMA, 'plugin': plugin, 'started_at': started,
                                         'finished_at': stamp(), 'brands': {}})
    except OSError:
        pass


def plan_step(brand, item, position):
    kind = item.get('kind') or 'work'
    rank = KIND_RANK.get(kind, 4)
    if kind == 'measure' and item.get('overdue'):
        rank = 1.5
    return {'brand': brand['id'], 'brand_name': brand['name'], 'folder': brand['folder'], 'position': position,
            'kind': kind, 'class': rank, 'title': item.get('title'), 'why': item.get('why'),
            'workflow': item.get('workflow'), 'family': item.get('family'), 'goal': item.get('goal'),
            'what_you_get': item.get('what_you_get'), 'needs_from_member': item.get('needs_from_member') or [],
            'agent_command': item.get('agent_command'),
            # Caiman 0.3.36: an old request is asked about ("Carry on with the ... you started on ...?"), not carried on.
            'offer_words': item.get('offer_words') if kind == 'offer_continue' else None,
            'started_on': item.get('started_on')}


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
    # Caiman 0.3.57 (FLAGS F149): the brands' NEXT_STEP.py run side by side (each writes only its own folder), so a run's
    # finish can rebuild the plan across a dozen brands within one command's time
    from concurrent.futures import ThreadPoolExecutor, as_completed
    import time as _time
    todo = [brand for brand in brands if brand['id'] not in duplicates]
    # Caiman 0.3.58 (FLAGS P374): each brand's answer is kept as it arrives, and a brand answered in the last
    # PLAN_PICKUP_MINUTES by a call that didn't finish isn't asked again. --max-seconds stops asking in time to answer:
    # the plan on disk stays as it is, the answer says which brands are left, and the same command again carries on.
    began = now()
    held = plan_partial(root, plugin, began)
    started = stamp(began)
    kept = {brand['id']: held[brand['id']] for brand in todo
            if brand['id'] in held and held[brand['id']].get('folder') == brand['folder']}
    answers = {brand_id: (entry['data'], None) for brand_id, entry in kept.items()}
    carried = [brand['id'] for brand in todo if brand['id'] in kept]
    limit = getattr(args, 'max_seconds', None)
    deadline = _time.monotonic() + max(0.0, float(limit)) if limit is not None else None

    def ask(brand):
        seconds = args.timeout
        if deadline is not None:
            left = deadline - _time.monotonic()
            if left < 2:
                return None, None, True
            seconds = max(1, min(int(seconds), int(left)))
        data, why = next_step(root / brand['folder'] if brand['folder'] != '.' else root, seconds)
        cut = data is None and deadline is not None and seconds < args.timeout and 'did not finish within' in str(why)
        return data, why, cut

    not_asked = []
    with ThreadPoolExecutor(max_workers=PLAN_WORKERS) as pool:
        futures = {pool.submit(ask, brand): brand for brand in todo if brand['id'] not in answers}
        for future in as_completed(futures):
            brand = futures[future]
            data, why, cut = future.result()
            if cut:
                not_asked.append(brand)
                continue
            answers[brand['id']] = (data, why)
            if data is not None:
                kept[brand['id']] = {'folder': brand['folder'], 'at': stamp(), 'data': data}
                keep_plan_partial(root, plugin, kept, started)
    if not_asked:
        left_ids = {brand['id'] for brand in not_asked}
        on_disk = as_dict(read_json(root / PLAN_JSON)).get('created_at')
        done = [brand for brand in todo if brand['id'] in answers]
        return {'schema': PLAN_SCHEMA, 'command': 'plan', 'workspace': str(root), 'status': 'in_progress',
                'plan_file': PLAN_MD, 'plan_json': PLAN_JSON, 'plan_on_disk_from': on_disk,
                'brands_answered': [brand['name'] for brand in done],
                'brands_left': [brand['name'] for brand in brands if brand['id'] in left_ids],
                'picked_up': [brand['name'] for brand in todo if brand['id'] in carried],
                'max_seconds': float(limit),
                'member_message': ('The plan across the brands is partly worked out: {} of {} answered, {} left. {} is not '
                                   'rewritten yet{}.').format(
                                       len(done), len(todo), plural(len(not_asked), 'brand'), PLAN_MD,
                                       ' (the one there is from {})'.format(plain_date(parse_time(on_disk)))
                                       if parse_time(on_disk) else ''),
                'how_to_continue': ('Run the same command again now: it keeps the brands already answered (for {} minutes) '
                                    'and asks only {}. The plan is written when every brand has answered; until then read '
                                    'no next step from {}.').format(PLAN_PICKUP_MINUTES,
                                                                    names([brand['name'] for brand in not_asked]), PLAN_MD)}
    for brand in brands:
        folder = root / brand['folder'] if brand['folder'] != '.' else root
        if brand['id'] in duplicates:
            # Like a run, the plan leaves out a brand set up in two folders: a step could send work to the wrong one.
            problems.append({'brand': brand['id'], 'brand_name': '{} ({})'.format(brand['name'], brand['folder']),
                             'why': duplicates[brand['id']]['member_line'] + ' Ask the member which folder is the '
                                    'current one; until then neither is planned.'})
            continue
        data, why = answers[brand['id']]
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
    # Caiman 0.3.34: Caiman's own unfinished work (a run that stopped partway, brands a run was finished without) comes
    # right after kit updates, to carry on without asking; a run another session is still working through is left to it.
    elsewhere = []
    unfinished = unfinished_steps(root, {brand['folder'] for brand in brands} if args.brands else None,
                                  text_value(getattr(args, 'session', None)), elsewhere)
    steps[0:0] = unfinished
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
        'ordering': ('Kit updates first, then ' + ("my own unfinished work across the brands (a run that stopped partway, "
                                                    'or brands a run was finished without), then ' if unfinished else '') +
                     'each brand\'s own next step (unfinished work, then results that are due, then '
                     'setup, then new work; brands in workspace order within each), then each brand\'s later steps in the '
                     'same way.' + (' A brand that shares its seller account and has no brand scope saved comes right '
                                    'after the {}.'.format('unfinished work' if unfinished else 'kit updates')
                                    if scope_alerts else ''))}
    view_steps = [step for step in steps if step['kind'] == 'brand-scope-view']
    if view_steps:
        plan['ordering'] += (" A brand whose business view was built before its brand scope gets a step to refresh it "
                             'first, and its steps for products outside the scope are left out.')
    if left_out:
        plan['left_out_by_brand_scope'] = left_out
    lines = ["# What's next across your brands", '', 'Worked out on {}, for {}.{}'.format(
        plain_time(moment), plural(len(brands), 'brand'), ' ' + _PAGE['note'] if _PAGE.get('note') else ''), '']
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
        lines += ['{}. **{}**: {}{}'.format(step['rank'], step['brand_name'], step.get('offer_words') or step['title'],
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
    # Caiman 0.3.58 (FLAGS P371): the file holds every path from the workspace's own folder, never this session's own
    saved = from_workspace(root, plan)
    saved['workspace'], saved['run_from'] = '.', RUN_FROM_FILE
    write_json(root / PLAN_JSON, saved)
    write_atomic(root / PLAN_MD, '\n'.join(lines).encode('utf-8'))
    close_plan_partial(root, plugin, started)
    top = steps[0] if steps else None
    message = ('Next across your brands: {}{}.'.format(
        '{}: {}'.format(top['brand_name'], top.get('offer_words') or top['title']) if top else 'nothing planned yet',
        '' if not waiting else '; {} waiting on you'.format(plural(len(waiting), 'decision'))))
    if unfinished:
        # Caiman 0.3.34: Caiman's own unfinished work is said first, in its own voice.
        parts = [steps[0]['title'] + ' first.'] if steps[0]['kind'] == 'kit-update' else []
        parts.append("{} finish what I started: {}.".format('Then I\'ll' if parts else "First I'll",
                                                            '; '.join(step['work'] for step in unfinished)))
        after = next((step for step in steps if step['kind'] not in ('kit-update',) + UNFINISHED_KINDS), None)
        if after or waiting:
            parts.append('Then: {}{}.'.format('{}: {}'.format(after['brand_name'], after.get('offer_words') or after['title']) if after else
                                              'nothing else planned yet', '' if not waiting else '; {} waiting on you'.format(
                                                  plural(len(waiting), 'decision'))))
        message = ' '.join(parts)
    for item in elsewhere:
        # Caiman 0.3.34: said, not offered: that session is most likely still working through it.
        message += ' {} is in progress in another session, handed to {}, so I leave it there.'.format(
            sentence('{} for {}'.format(item['work'], names(item['names']))).rstrip('.'), item['claimed'])
    if problems:
        message += " Couldn't plan {}.".format(names([item['brand_name'] for item in problems]))
    # Caiman 0.3.34: the first step is given as the handoff's Next; the member's "next" starts it.
    work_in = ("work in that step's brand folder only: run its agent_command (from the workspace's folder, as run_from "
               'says), or for the kit update use the kit-sync skill\'s "Every brand in a workspace"' + (
                   "; for saving a brand scope, follow the step's how in that brand's folder." if scope_alerts else '.'))
    answer = {'schema': PLAN_SCHEMA, 'command': 'plan', 'workspace': str(root), 'plan_file': PLAN_MD,
              'plan_json': PLAN_JSON, 'steps': steps, 'waiting_on_member': waiting, 'not_planned': problems,
              'alerts': alerts + scope_alerts, 'member_message': message,
              'how_to_continue': ('Give the first step as Next, in plain words with its brand, ending "Say next to '
                                  'start it." The member\'s next (or a yes to it) starts it: ' + work_in +
                                  ' A step with offer_words (a request started more than a week ago) is asked as its '
                                  'question instead; on a yes run its agent_command, and when the member doesn\'t need it '
                                  'any more run NEXT_STEP.py skip --project-root "<that brand\'s folder>" --workflow '
                                  '<its workflow> --request-only --reason "<their words>" in that folder.')}
    if elsewhere:
        answer['in_progress_elsewhere'] = elsewhere
    if carried:
        # Caiman 0.3.58 (FLAGS P374): the brands an earlier call of plan had answered, kept and not asked again
        answer['picked_up'] = [brand['name'] for brand in brands if brand['id'] in carried]
    puller = report_puller_of(root)
    if puller:
        # Caiman 0.3.57 (FLAGS F148), under the puller's name since 0.3.58 (F157): with the report puller on, the next
        # step is started, not offered, when it waits on nothing
        answer['report_puller'] = puller
        answer['how_to_continue'] = (puller['words'] + ' So start the first step now when it needs no go, no date and '
                                     'no person (' + work_in.rstrip('.') + '); give as Next only a step that waits on one '
                                     'of those, saying which. ' + answer['how_to_continue'])
    if left_out:
        answer['left_out_by_brand_scope'] = left_out
    if view_steps:
        answer['how_to_continue'] += (" A brand's figures marked figures_cover come from a business view built for the "
                                      "whole seller account: say so, and refresh it first (its brand-scope-view step).")
    if unfinished:
        answer['how_to_continue'] = (
            'Carry on with my own unfinished work first, after any kit update, without asking the member (the steps of '
            'kind unfinished-run or still-to-do): run its agent_command and follow the run flow, brand by brand, to its '
            'combined note (run next says what it does with a brand another session had). Then give the step after it '
            'as Next, ending "Say next to start it."; the member\'s next (or a yes to it) starts it: ' + work_in)
    return answer


def report_puller_of(root):
    """The report puller's switch for this workspace (Caiman 0.3.58, FLAGS F157): {'on': True, 'since',
    'switched_on_by', 'file', 'words'} from CAIMAN OPERATOR.json (the file 0.3.57's operator command wrote: its
    "operator" is who switched it on), or None when it is off."""
    data = as_dict(read_json(Path(root) / OPERATOR_FILE, 64 * 1024))
    name = text_value(data.get('operator'))
    if data.get('schema') != OPERATOR_SCHEMA or not name:
        return None
    by = '' if name == PULLER_DEFAULT_BY else ' (switched on by {})'.format(name)
    return {'on': True, 'since': data.get('set_at'), 'switched_on_by': name, 'file': OPERATOR_FILE,
            'words': PULLER_WORDS.format(by)}


def cmd_puller(args):
    """puller: switch the report puller on (--on, with --by "<who>") or off (--off) for this workspace or business
    folder; with neither, what is saved. operator --name "<who>" (Caiman 0.3.57) is the same switch."""
    root = workspace_root(args.workspace)
    path = root / OPERATOR_FILE
    if getattr(args, 'off', False):
        if path.is_file():
            write_atomic(path, (json.dumps({'schema': OPERATOR_SCHEMA, 'operator': None, 'set_at': stamp()}, indent=2)
                                + '\n').encode('utf-8'))
        return {'schema': SCHEMA, 'command': 'puller', 'workspace': str(root), 'report_puller': None,
                'member_message': 'The report puller is off for this workspace: Next offers the next step ("Say next").'}
    name = ' '.join((getattr(args, 'name', None) or getattr(args, 'by', None) or '').split())
    if len(name) > 80:
        raise WorkspaceError('Say who switches the report puller on in a few words (--by).')
    if name or getattr(args, 'on', False):
        write_atomic(path, (json.dumps({'schema': OPERATOR_SCHEMA, 'operator': name or PULLER_DEFAULT_BY,
                                        'report_puller': True, 'set_at': stamp()}, indent=2) + '\n').encode('utf-8'))
    found = report_puller_of(root)
    return {'schema': SCHEMA, 'command': 'puller', 'workspace': str(root), 'report_puller': found,
            'member_message': (found['words'] if found else 'The report puller is off for this workspace: Next offers the '
                                                            'next step ("Say next to start it"). puller --on switches it '
                                                            'on.')}


# ---------------------------------------------------------------- run: one workflow across the brands, resumable

WORKFLOW_ALIASES = {
    'dailycheck': 'advertising-daily-check', 'dailyadscheck': 'advertising-daily-check',
    'adsdailycheck': 'advertising-daily-check', 'advertisingdaily': 'advertising-daily-check',
    'weeklyreview': 'weekly-growth-review', 'growthreview': 'weekly-growth-review', 'weekly': 'weekly-growth-review',
    'adsweeklyreview': 'advertising-weekly-review', 'advertising': 'advertising-weekly-review',
    'structurereview': 'advertising-structure-review', 'setup': 'setup-check',
    'weeklyloop': 'vip-weekly-loop', 'dailybrief': 'vip-daily-brief', 'healthcheck': 'vip-health-check',
    'opportunityreview': 'vip-opportunity-review', 'dreamingloop': 'vip-opportunity-review',
    # Caiman 0.3.57 (FLAGS F147): "daily checks" means every brand's day, and on Mondays the week (Jonah, Nov 23)
    'dailychecks': 'suite', 'day': 'suite', 'theday': 'suite', 'dailysuite': 'suite', 'mondaysuite': 'suite',
    'monday': 'suite', 'thesuite': 'suite',
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


def daily_check_status(root, entry, since=None):
    """A brand's Daily Check completeness answer for this run (the kit's DAILY_CHECK.py status, Caiman 0.3.55): its day
    and what it said. since: when this run started on the brand. A list made before that is another day's check, and a
    brand with no list has nothing that says all of it was done: both are status no_list with their own line (the one
    review, Nov 19, 2026: yesterday's "complete" was counted as today's, and a brand with no list was left out of the
    count). A status taken of an earlier list of the day (the list was made again since) is not_checked."""
    base = brand_folder(root, entry) / 'Reports' / 'daily-check'
    try:
        days = sorted(d.name for d in base.iterdir() if (d / 'plan.json').is_file())
    except OSError:
        days = []
    if not days:
        return {'status': 'no_list', 'may_finish': False, 'day': None,
                'line': 'No list of the day\'s reads was made (DAILY_CHECK.py plan), so nothing says whether all of it was done.'}
    try:
        plan = json.loads((base / days[-1] / 'plan.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        plan = None
    plan = plan if isinstance(plan, dict) else {}
    made = parse_time(plan.get('made_at'))
    if since is not None and made is not None and made < since:
        return {'status': 'no_list', 'may_finish': False, 'day': days[-1],
                'line': 'No list of the day\'s reads was made in this run (the newest is of {}), so nothing says whether all '
                        'of it was done.'.format(days[-1])}
    try:
        status = json.loads((base / days[-1] / 'status.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        status = None
    if not isinstance(status, dict):
        status = {'may_finish': False, 'status': 'not_checked',
                  'line': 'Daily Check not checked: its reads were listed and DAILY_CHECK.py status was never run.'}
    elif plan.get('made_at') and status.get('plan_made_at') not in (None, plan.get('made_at')):
        status = {'may_finish': False, 'status': 'not_checked',
                  'line': 'Daily Check not checked: its list of reads was made again after DAILY_CHECK.py status was run.'}
    return dict(status, day=days[-1])


def daily_check_lines(root, data):
    """Was all of it done? One line a brand, from each brand's own DAILY_CHECK.py status, under the count. A member asked
    for "the daily checks" and got a run called finished with reads left out, said only inside each brand's note. Every
    brand the run did is counted: one with no list of this run's is not complete, and says so."""
    rows = []
    for entry in data['brands']:
        if entry.get('status') != 'done':
            continue
        since = parse_time(entry.get('carried_started_at') or entry.get('started_at') or data.get('started_at'))
        rows.append((entry['name'], daily_check_status(root, entry, since), since))
    if not rows or all(status.get('day') is None for _name, status, _since in rows):
        return []       # no brand of the run has a list at all (kits from before the list): nothing to count
    # a run with no times on it (an older record): a brand whose newest list is of an earlier day than the others'
    newest = max(status['day'] for _name, status, _since in rows if status.get('day'))
    rows = [(name, {'status': 'no_list', 'may_finish': False, 'day': status['day'],
                    'line': 'No list of the day\'s reads was made in this run (the newest is of {}), so nothing says whether '
                            'all of it was done.'.format(status['day'])}
             if since is None and status.get('day') and status['day'] < newest and status.get('status') != 'no_list' else status)
            for name, status, since in rows]
    whole = [name for name, status in rows if status.get('status') == 'complete']
    lines = ['## Was all of it done?', '',
             '{} of {} Daily Checks are complete: every read made.'.format(len(whole), len(rows)), '']
    for name, status in rows:
        if status.get('status') != 'complete':
            lines.append('- **{}**: {}'.format(name, status.get('line') or 'not complete'))
    if len(whole) != len(rows):
        lines.append('')
    return lines


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
        page_zone(root, [brand_folder(root, entry) for entry in data['brands']])      # FLAGS P372
        return run_file(root, name), data
    unfinished = open_runs(root)
    if len(unfinished) > 1 and only_one:
        raise WorkspaceError('{} runs across the brands are unfinished: {}. Name the one to carry on with --run (the run '
                             'you started, or the one the member means); a scheduled task carries on with its own '
                             'run.'.format(len(unfinished), '; '.join('"{}" ({}{})'.format(
                                 data['name'], data.get('workflow_name') or data['workflow'],
                                 ', a scheduled run' if data.get('scheduled') else '') for path, data in unfinished)))
    if unfinished:
        page_zone(root, [brand_folder(root, entry) for entry in unfinished[0][1]['brands']])      # FLAGS P372
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


def progress_table(data, still_words=False):
    """The run's brands and results as a table. still_words (the combined note, Caiman 0.3.34): a brand the run was
    finished without reads "Still to do", Caiman's own work, not "Not run"."""
    lines = ['| Brand | Result | Note |', '|---|---|---|']
    for entry in data['brands']:
        lines.append('| {} | {} | {} |'.format(entry['name'].replace('|', '/'), result_words(entry, still_words),
                                               one_line(entry.get('note') or '', 160).replace('|', '/') or ' '))
    return '\n'.join(lines)


def result_words(entry, still_words=False):
    if still_words and entry['status'] == 'not-run':
        picked = picked_up_by(entry)
        return 'Picked up in {}'.format(picked) if picked else 'Still to do'
    return STATUS_WORDS.get(entry['status'], entry['status'])


def picked_up_by(entry):
    """The run that picked up a brand this run was finished without (Caiman 0.3.34: it's handled there, not still to do
    here), or None."""
    return text_value(entry.get('picked_up_in')) if entry.get('status') == 'not-run' else None


# ---------------------------------------------------------------- brands still to do (Caiman 0.3.34)

# A brand a run is finished or closed without is Caiman's own unfinished work, never the member's problem: it keeps the
# status not-run that older plugins read, with still_to_do, and stays to do until a later run of the same workflow has
# it. The next run start of that workflow puts it first, and run next and plan carry it on first, without asking. A
# brand another session still had when its run was finished keeps that session's claim in the run that picks it up
# (for CLAIM_HOLD_MINUTES), so the usual rule applies (hand_out): it stays with that session while the claim is new, and
# is carried on here, said so, once that session has most likely stopped. A daily workflow's brand from an earlier day
# is new work in the new day's run: it goes first there, and starts fresh.
UNFINISHED_KINDS = ('unfinished-run', 'still-to-do')


def leave_to_do(entry, note, session=None):
    """A brand a run is finished or closed without: not-run as before, with still_to_do, and the claim of a session
    other than this one (held_when_finished) when it was in progress."""
    if entry.get('status') == 'in-progress' and text_value(entry.get('session')) and entry.get('session') != session:
        entry['held_when_finished'] = {'session': entry.get('session'),
                                       'claimed_at': entry.get('claimed_at') or entry.get('started_at'),
                                       'claimed_by': entry.get('claimed_by')}
    entry.update(status='not-run', note=entry.get('note') or note, still_to_do=True)


def run_day_words(name):
    """The day a run's name starts with, in words ("October 19, 2026"), else the name."""
    try:
        day = dt.date.fromisoformat(str(name)[:10])
    except ValueError:
        return str(name)
    return '{} {}, {}'.format(MONTHS[day.month - 1], day.day, day.year)


def run_is_current(data, moment=None):
    """Whether a run's work is still current, as run start counts it: a daily workflow's from today, another's started
    less than STALE_DAYS days ago."""
    moment = moment or now()
    if data.get('workflow') in DAILY:
        return (data.get('name') or '').startswith(moment.date().isoformat())
    started = parse_time(data.get('started_at'))
    return bool(started and (moment - started).days < STALE_DAYS)


def still_to_do(root, workflow=None, goal=None, current_only=False):
    """The brands earlier runs left to do, newest run first: [{'path', 'data', 'entries'}]. A brand a run was finished or
    closed without (not-run) stays to do until a later run of the same workflow has it (matched by its folder, as runs
    are elsewhere) or a run picked it up (picked_up_in); a run of the member's own request only for that request.
    current_only: only runs still current (run_is_current)."""
    found, seen = [], {}
    for path, data in all_runs(root):          # newest first
        flow = data.get('workflow')
        if flow not in WORKFLOWS or WORKFLOWS[flow][1] == 'kit-update' or (workflow and flow != workflow):
            continue
        request = WORKFLOWS[flow][1] == 'request'
        if request and workflow and data.get('goal') != goal:
            continue
        covered = seen.setdefault((flow, data.get('goal') if request else None), set())
        left = []
        if data.get('status') in ('finished', 'closed'):
            left = [entry for entry in data['brands'] if entry.get('status') == 'not-run'
                    and not entry.get('picked_up_in') and entry.get('folder') not in covered]
        covered.update(entry.get('folder') for entry in data['brands'])
        if left and (not current_only or run_is_current(data)):
            found.append({'path': path, 'data': data, 'entries': left})
    return found


def carried_first(items, chosen):
    """(chosen with the brands still to do from earlier runs first, {brand id: (their entry there, that run's path and
    record)}): the newest run's first, in its order; the other brands after them, in workspace order."""
    by_folder = {brand['folder']: brand for brand in chosen}
    first, origin = [], {}
    for item in items:
        for entry in item['entries']:
            brand = by_folder.get(entry.get('folder'))
            if brand is not None and brand['id'] not in origin:
                first.append(brand)
                origin[brand['id']] = (entry, item['path'], item['data'])
    return first + [brand for brand in chosen if brand['id'] not in origin], origin


def earlier_day(workflow, name, day):
    """Whether a daily workflow's run (by its name) is from an earlier day than day (an ISO date): its work then is that
    day's, and a new day's run starts it fresh (Caiman 0.3.34)."""
    return workflow in DAILY and bool(text_value(name)) and not str(name).startswith(day)


def carry(entry, origin, moment):
    """A new run's entry for a brand an earlier run left to do: where it comes from and, when that run's other session
    had it within CLAIM_HOLD_MINUTES, that session's claim (the usual rule then applies to it). A daily workflow's brand
    from an earlier day only goes first: it starts fresh, and no session's claim on that day's work comes with it."""
    old, path, data = origin
    entry['carried_from'] = data['name']
    if earlier_day(data.get('workflow'), data.get('name'), moment.date().isoformat()):
        return
    if old.get('started_at'):
        entry['carried_started_at'] = old['started_at']
    held = old.get('held_when_finished') if isinstance(old.get('held_when_finished'), dict) else {}
    since = parse_time(held.get('claimed_at'))
    if entry['status'] == 'pending' and text_value(held.get('session')) and since and \
            (moment - since).total_seconds() < CLAIM_HOLD_MINUTES * 60:
        entry.update(status='in-progress', session=held['session'], claimed_at=held['claimed_at'],
                     claimed_by=held.get('claimed_by'), started_at=held['claimed_at'])


def picked_up(origin, name, moment):
    """Record in each earlier run that its brands still to do were picked up by the run named."""
    runs = {}
    for old, path, data in origin.values():
        old.update(picked_up_in=name, picked_up_at=stamp(moment))
        runs[str(path)] = (path, data)
    for path, data in runs.values():
        save_run(path, data)


def unfinished_steps(root, folders=None, session=None, elsewhere=None):
    """For the plan: Caiman's own unfinished work, each as a step to carry on without asking. A conversation's run
    that stopped partway (brands pending or in progress; a scheduled task's run is left to it), and brands a current
    run was finished without (still_to_do). folders: only these brands' (the plan's --brands). A run another session
    is still working through (a brand in it handed out less than CONVERSATION_HOLD_MINUTES ago, none to this session)
    is left to it (Caiman 0.3.34: live_elsewhere), listed in elsewhere when that is a list."""
    steps = []
    moment = now()
    for path, data in open_runs(root):
        left = [entry for entry in data['brands'] if entry['status'] in ('pending', 'in-progress')
                and (folders is None or entry.get('folder') in folders)]
        if not left or data.get('scheduled') or data.get('workflow') not in WORKFLOWS:
            continue
        busy = live_elsewhere(data, session, moment)
        if busy is not None:
            if isinstance(elsewhere, list):
                elsewhere.append({'run': data['name'], 'workflow': data['workflow'], 'work': work_words(data),
                                  'brands': [entry['id'] for entry in left], 'names': [entry['name'] for entry in left],
                                  'session': busy.get('session'), 'claimed_at': busy.get('claimed_at')
                                  or busy.get('started_at'), 'claimed': claim_words(busy, moment)})
            continue
        steps.append(unfinished_step(root, data, left, 'unfinished-run'))
    for item in still_to_do(root, current_only=True):
        left = [entry for entry in item['entries'] if brand_folder(root, entry).is_dir()
                and (folders is None or entry.get('folder') in folders)]
        if left:
            steps.append(unfinished_step(root, item['data'], left, 'still-to-do'))
    return steps


def is_request(data):
    return WORKFLOWS.get(data.get('workflow'), ('', ''))[1] == 'request'


def work_words(data):
    """A run's work in a sentence (Caiman 0.3.34): "the Weekly Growth Review", or "your request" for a run of the
    member's own request."""
    if is_request(data):
        return 'your request'
    name = str(data.get('workflow_name') or WORKFLOWS.get(data.get('workflow'), (data.get('workflow'),))[0])
    # a name with its own article ("The daily suite") isn't given a second one ("the The daily suite")
    return 'the ' + (name[4:] if name.lower().startswith('the ') else name)


def run_words(data, runs=1):
    """"the Weekly Growth Review run" or "the run for your request" (Caiman 0.3.34); runs: more than one."""
    if is_request(data):
        return 'the run{} for your request'.format('s' if runs > 1 else '')
    return '{} run{}'.format(work_words(data), 's' if runs > 1 else '')


def unfinished_step(root, data, entries, kind):
    started = parse_time(data.get('started_at'))
    when = ' of {}'.format(plain_date(started)) if started else ''
    who = names([entry['name'] for entry in entries])
    work = work_words(data)
    elsewhere = [entry['name'] for entry in entries if entry['status'] == 'in-progress']
    why = ("{}{} stopped before {} {} done".format(sentence(run_words(data)).rstrip('.'), when, who,
                                                    'was' if len(entries) == 1 else 'were')
           if kind == 'unfinished-run' else
           "{}{} was finished before I got to {}".format(sentence(run_words(data)).rstrip('.'), when,
                                                        who if len(entries) > 1 else 'it'))
    if elsewhere:
        why += " ({} {} handed to another session that hasn't recorded {}: I carry {} on here once that session has " \
               "most likely stopped, and say so)".format(names(elsewhere), 'was' if len(elsewhere) == 1 else 'were',
                                                         'it' if len(elsewhere) == 1 else 'them',
                                                         'it' if len(elsewhere) == 1 else 'them')
    return {'brand': None, 'brand_name': who, 'brands': [entry['id'] for entry in entries], 'folder': '.',
            'position': 0, 'kind': kind, 'class': 0.2, 'title': 'Finish {}'.format(work),
            'work': '{} for {}'.format(work, who),
            'why': why + ': my own unfinished work, so I carry on with it without asking.',
            'workflow': data['workflow'], 'family': None, 'goal': data.get('goal'),
            'what_you_get': ("{}: your request done, then one combined note with what's done, your go and what's "
                             'next.'.format(who) if is_request(data) else
                             "{}'s {}, then one combined note with what's done, your go and what's next.".format(
                                 who, data.get('workflow_name') or WORKFLOWS[data['workflow']][0])),
            'needs_from_member': [], 'run': data['name'], 'without_asking': True,
            'agent_command': command_line([str(Path(__file__).resolve()), 'run', 'next', '--workspace', str(root), '--run',
                                           data['name']])}


def new_session():
    """A short name for one session's claims in a run (a conversation, or one scheduled run)."""
    return 's-' + secrets.token_hex(3)


def claim_of(entry):
    """(session, since) a brand in progress was handed to. A run saved by an earlier plugin has no session (None) and
    its brand counts from when it was started. Caiman 0.3.56 (FLAGS P324): since is the newer of when it was handed out
    and when its own session last recorded its report IDs (run reports: seen_at, by seen_by): that session is alive.
    Another session's call never counts for it."""
    session = text_value(entry.get('session'))
    since = parse_time(entry.get('claimed_at') or entry.get('started_at'))
    seen = parse_time(entry.get('seen_at')) if session and entry.get('seen_by') == session else None
    return session, (max(since, seen) if since and seen else since or seen)


def claim_minutes(entry, moment):
    since = claim_of(entry)[1]
    return None if since is None else max(0, int((moment - since).total_seconds() // 60))


def claim_hold(data, entry=None):
    """How long another session's claim on a brand stays with it in this run (Caiman 0.3.34): CLAIM_HOLD_MINUTES in a
    scheduled run, CONVERSATION_HOLD_MINUTES in a conversation's. Caiman 0.3.56 (FLAGS P324): CLAIM_HOLD_MINUTES too for
    a brand handed to its session by name (run next --brand: a lead giving each lane its brand), which works a brand for
    longer than half an hour."""
    if data.get('scheduled') or (entry is not None and entry.get('assigned')):
        return CLAIM_HOLD_MINUTES
    return CONVERSATION_HOLD_MINUTES


def live_elsewhere(data, session=None, moment=None):
    """(Caiman 0.3.34) The newest claim in this run when it is newer than CONVERSATION_HOLD_MINUTES and this session
    (when named) has no brand in progress in it: another session is most likely still working through the run. Else
    None."""
    moment = moment or now()
    busy = [entry for entry in data.get('brands') or [] if entry.get('status') == 'in-progress']
    if session and any(text_value(entry.get('session')) == session for entry in busy):
        return None
    recent = [entry for entry in busy if claim_minutes(entry, moment) is not None
              and claim_minutes(entry, moment) < CONVERSATION_HOLD_MINUTES]
    return max(recent, key=lambda entry: claim_of(entry)[1]) if recent else None


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


def hand_out(root, path, data, session=None, take_over_brand=None, leave=(), brand=None):
    """(entry, resumed, held): the brand to work on now, whether it was handed out before, and what happened to the
    brands another session has. A brand stays with the session it was handed to until it's recorded (Caiman 0.3.17):
    that session gets it back first. Another session leaves it (held['left']) and goes on with the next brand while that
    claim is newer than CONVERSATION_HOLD_MINUTES (a conversation, Caiman 0.3.34) or CLAIM_HOLD_MINUTES (a scheduled
    run); an older claim it takes over (held['taken_over']: that session most likely stopped), and a conversation says
    so with the choice to leave it. The member's own choice counts: take it over (take_over_brand) or leave it to the
    session that had it (leave, remembered for this session; a brand this session just took over goes back to that
    session). A brand whose folder is gone is recorded as not finished and the run moves on."""
    moment = now()
    held = {'left': [], 'taken_over': None}
    for wanted in leave or ():
        item = match_entry(data['brands'], wanted)
        if item['status'] != 'in-progress':
            continue
        last = (item.get('taken_over') or [{}])[-1]
        if session and item.get('session') == session and last.get('taken_by') == session:
            # The member says the session this one took the brand over from is still working on it: it goes back.
            item.update(session=last.get('session'), claimed_at=last.get('claimed_at'), claimed_by=last.get('claimed_by'))
            item['given_back'] = (item.get('given_back') or []) + [{'session': session, 'at': stamp(moment)}]
        if session not in (item.get('left_by') or []):
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
    if brand and take_over_brand and match_entry(data['brands'], brand) is not entry:
        raise WorkspaceError('Name one brand to hand out here: --brand {} and --take-over {} are two brands.'.format(
            brand, take_over_brand))
    if entry is None and brand:
        # Caiman 0.3.56 (FLAGS P324): the brand asked for (a lead handing each lane its brand, biggest first), never the
        # workspace's order: one still to do, or the one this session has
        entry = match_entry(data['brands'], brand)
        mine = next((item for item in busy if session and item.get('session') == session and item is not entry), None)
        if entry['status'] == 'in-progress' and session and entry.get('session') == session:
            resumed = True
        elif entry['status'] == 'in-progress':
            raise WorkspaceError('{} is being worked on in another session ({}). If that session stopped, or never '
                                 'started on it (the brand run start handed out), carry it on here with --take-over {} '
                                 'in place of --brand.'.format(entry['name'], claim_words(entry, moment), entry['id']))
        elif entry['status'] != 'pending':
            raise WorkspaceError('{} already has a result in this run ({}), so there is nothing to hand out.'.format(
                entry['name'], STATUS_WORDS.get(entry['status'], entry['status']).lower()))
        elif mine is not None:
            raise WorkspaceError('This session still has {} in progress: record it with run done first, then ask for '
                                 '{}.'.format(mine['name'], entry['name']))
        elif not brand_folder(root, entry).is_dir():
            raise WorkspaceError('{}\'s business folder ({}) is no longer there (moved or renamed?).'.format(
                entry['name'], entry['folder']))
        else:
            claim(entry, session, data, moment)
    if brand and entry is not None:
        entry['assigned'] = True        # held as long as a scheduled run's brand (claim_hold)
    if entry is None:
        entry = next((item for item in busy if session and item.get('session') == session), None)
        resumed = entry is not None
    if entry is None:
        for item in busy:
            if session in (item.get('left_by') or []):
                held['left'].append(item)
                continue
            minutes = claim_minutes(item, moment)
            if minutes is not None and minutes < claim_hold(data, item):
                # Caiman 0.3.34: a conversation too leaves a claim this new to its session (it's most likely still
                # working on it), so two sessions never do the same brand at once.
                held['left'].append(item)
                continue
            held['taken_over'] = take_over(item, session, data, moment)
            entry, resumed = item, True
            break
    while entry is None:
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


def workflow_start(root, data, entry, workflow, folder, guide):
    """How one workflow starts in one brand's folder for its tier: {"start": ...}, or {"start": None, "problem":
    ...} when its kit can't start it (task_for; Caiman 0.3.57: each step of the daily suite too)."""
    label, kind, first = WORKFLOWS[workflow]
    task = {'start': None}
    if kind in ('kit', 'request'):
        goal = first if kind == 'kit' else data.get('goal')
        if kind == 'kit' and data.get('goal'):
            goal = first + '\n' + data['goal']
        program = guide / 'CLIENT_START.py'
        if program.is_file():
            # Always a new request: a brand picked up again may never have reached CLIENT_START.py, and without
            # --new-request the goal would join whatever earlier request is still open there.
            argv = [str(program), '--project-root', str(folder), '--new-request', '--goal', goal]
            try:                                    # Caiman 0.3.42 (R1): the brand's run ledger says what started it
                takes_trigger = "'--trigger'" in program.read_text(encoding='utf-8', errors='replace')
            except OSError:
                takes_trigger = False
            if takes_trigger:                       # before --goal, so the goal stays the last argument
                argv[4:4] = ['--trigger', 'schedule' if data.get('scheduled') else 'workspace']
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
        # Caiman 0.3.40 (FLAGS F30a): the brand's own SETUP_CHECK.py when its kit is this plugin's version (the same
        # file, and it runs where the folder is, as in a task in the cloud); otherwise this plugin's, which says what to do.
        version = plugin_version()
        core = text_value(as_dict(read_json(folder / 'RELEASE_MANIFEST.json')).get('core_version'))
        copy = folder / 'SETUP_CHECK.py'
        if version and core and parse_version(core) and parse_version(core) == parse_version(version) and copy.is_file():
            argv = [str(copy), '--plugin-version', version]
        else:
            argv = [str(HERE / 'setup_check.py')]
        argv += ['--project-root', str(folder), '--connector', '<ok|failed|not-connected>',
                 '--connector-brands-json', '@<file with the brands list_brands returned>', '--where', '<cloud|computer>']
        task['start'] = {'program': python(), 'argv': argv, 'shell': command_line(argv),
                         'how': ('Call list_brands once for the whole run, save its brands in a file and reuse it for every '
                                 "brand (the setup check guide, \"Every session\"). Pass on this brand's headline.")}
    return task


def workflow_rules(root, data, entry, workflow, guide):
    """The rules of one workflow's own work in one brand (task_for; Caiman 0.3.57: each step of the daily suite
    too)."""
    rules = []
    if workflow == 'advertising-daily-check':
        # Caiman 0.3.26: the daily check catches exceptions; the weekly review decides changes. 0.3.27: the stop lines
        # come from the brand's own register, read with its kit's STOP_LINES.py. 0.3.34: the campaign reads have a row
        # for each day, and the Sponsored Products one is the stop lines' own read.
        rules.append('This is the Advertising Daily Check: list the exceptions and the stop lines the weekly plan wrote '
                     'that are crossed (read at their own level: keyword, target, placement or campaign). Read yesterday\'s '
                     'delivery and spend against the 7 days before from its campaign reads with a row for each day '
                     '(Sponsored Products, Brands and Display, in task.reports when the run asked for them first), each '
                     'saved once at its save_as with the call that started it. Note anything else the reads suggest, such '
                     'as a pause, a bid, boost or negative change, or a campaign change, under a "## For the weekly '
                     'review" heading, one "- " bullet per item with its numbers and window; it is not a proposal. Save '
                     'the check in Reviews/daily/ named for the '
                     'account\'s date (YYYY-MM-DD.md), where the weekly review reads it.')
        if (guide / 'DAILY_CHECK.py').is_file():
            # Caiman 0.3.55: the task names the list too (the one review, Nov 19, 2026: only the brand's start did)
            rules.append('A Daily Check is all of it: the day\'s reads are one numbered list (DAILY_CHECK.py plan; the '
                         'brand\'s start makes it). Make every read it numbers, then run DAILY_CHECK.py status and open '
                         'the brand\'s summary with its line as it is; done is refused while it says not complete.')
        if (guide / 'STOP_LINES.py').is_file():
            plan = entry.get('reports') if isinstance(entry.get('reports'), dict) else {}
            day = text_value(plan.get('account_date'))
            known = plan.get('account_date_known') if 'account_date_known' in plan else bool(day) and 'UTC' not in str(
                plan.get('account_date_from') or '')
            if day and not known:
                # Caiman 0.3.34: the run's reads were worked out on today's date in UTC; due works out the account's.
                how = ("--project-root this brand's folder and no --date: it works out the account's date itself (this "
                       "run's reads were asked for on {}, today's date in UTC, because the account's date couldn't be "
                       'read when the run started)').format(day)
            else:
                how = "--project-root this brand's folder and --date the account's date{}".format(
                    ' ({}, the day this run asked for its reads)'.format(day) if day else '')
            # Caiman 0.3.54 (the 0.3.53 list's "Not built"): the daily pass's reads are named under daily_reads, and
            # a run that made only the reads under reads left each brand's quiet day untold (Nov 17, 2026)
            rules.append("Read this brand's stop lines with its kit's STOP_LINES.py (in task.guide_folder): run due "
                         "with {}, request each read it names, under reads and under daily_reads (the daily pass's "
                         "keyword and targeting reports, the budget usage call late in the account's day, the whole "
                         "stock read and the others it lists there), with its tool and arguments (this brand's slug, a "
                         "row for each day) and save them as it says, then run check on them. When check's next_step "
                         "says a daily read is missing, make it and run check again before you write this brand's "
                         "summary: a quiet day not read is never a quiet day that was fine. A read due names that is already "
                         "one of this brand's reports in task.reports (its stop_lines_read, with the same tool and "
                         "arguments) was asked for at the start of the run: poll that report's ID instead of requesting "
                         "it again, and save it once, at its save_as; the daily check and the stop lines' check both read "
                         "it. Put a crossed line forward with its step for the member's exact go, and say plainly any "
                         "line due but not read: it is never taken as not crossed.".format(how))
            if (guide / 'CHANGE_READS.py').is_file():
                # Caiman 0.3.47: an ad change is read within days. The stop lines watch what someone wrote down; the
                # first reads read every ad and price change of the last three weeks from the same saved reads.
                rules.append("Then read what this brand's changes of the last three weeks have done so far, with its "
                             "kit's CHANGE_READS.py (in task.guide_folder): run read with --project-root this brand's "
                             "folder and --save, after check, on the same reads. Say its scoreboard in this brand's summary "
                             "as it is (scoreboard.words, Caiman 0.3.54: what worked, what didn't and what changed nothing, "
                             "with the money), then what came in with this read (scoreboard.new, each with its money and "
                             "its next step): the member decides from results, so the ones that worked are said too. When "
                             "it says some can't be read yet, make the read it names and run read again. Then lead with what "
                             "it flags (needs_a_look, then not_serving): a raise or a restore with no traffic a day later, "
                             "a change running hot with sales still arriving, one that did its job over its line (a "
                             "trim, never an undo), a cut that went dark. Each names its one next step for the member's "
                             "go. Say the daily reads it names as missing (reads_missing): a day not saved is a day "
                             "not read, never a zero.")
        else:
            rules.append("This brand's kit has no STOP_LINES.py yet, so its stop lines can't be read from its register: "
                         "say so in its summary (its kit needs updating with kit-sync) and read the weekly plan's own "
                         "words for them.")
        if (guide / 'WEEKLY_REFRESH.py').is_file():
            # Caiman 0.3.55 (FLAGS F122): the search weeks' own weekly step. Our own stores, Nov 18: the newest search
            # week on all 12 pages was 18 days old, since no run made the reads after the scorecard's weeks.
            rules.append("Once a week this brand's DAILY_NUMBERS.py due names the search weeks' step (search_weeks, Caiman "
                         "0.3.55; a kit before it names none). When it does, run its command (its kit's WEEKLY_REFRESH.py "
                         "search-weeks with --project-root this brand's folder) before the page is built: it gives one "
                         "Search Query Performance call for the newest weeks Amazon has posted, or, for a call asked for at "
                         "an earlier check, the get_sqp_batch check and the command that saves every finished report at "
                         "once, and it registers each week once it is whole. Record the call's ID as it says and go on: "
                         "the call queues at the connector, so never wait on it; the next check collects it. It reads "
                         "only, and changes nothing in the account.")
        if (guide / 'DASHBOARD.py').is_file():
            # Caiman 0.3.55 (FLAGS F125): the check ends with the brand's page. Our own stores, Nov 18: built after the
            # morning's checks, 11 of 12 pages had no net profit for Yesterday, Month to date or the Last 30 days,
            # since no workflow made the profit view's reads; and no run built the pages on 5 of 9 days.
            rules.append("End this brand with its Caiman Dashboard, so the page shows the day (Caiman 0.3.55). Make the "
                         "reads its kit's DAILY_NUMBERS.py due names under page_reads with the day's other reads (the "
                         "profit view's own: fees and refunds for the days not saved yet, today's orders and ad spend so "
                         "far, ad cost by product; a kit before 0.3.55 names none there: run its PROFIT.py with "
                         "--project-root this brand's folder and make its reads_now). After check and the first reads, "
                         "run the command DAILY_NUMBERS.py build --save gives under dashboard (its kit's DASHBOARD.py "
                         "with --project-root this brand's folder and no --today), last. It reads saved files only and "
                         "changes nothing in the account. Say in this brand's summary what the page still lacks, as the "
                         "build's answer says it (a figure not read is missing, never 0). The run's finish puts the "
                         "brands' pages together; publishing or deploying a page is not part of this run.")
    return rules


# ---------------------------------------------------------------- the daily suite (Caiman 0.3.57, FLAGS F147)
# Jonah, Nov 23: "Daily checks" means every brand, in order: carry over what the last run left open; yesterday's numbers
# and anything that jumped; stop lines and changes read; ad account and Seller Central health; one go list. On Mondays it
# also means the week: close each VIP week, the Weekly Growth Review, and what last week's changes did. Ours, Mon Nov 23:
# the daily check and the Monday work were separate runs and nothing tied either to the day; the VIP week was opened in
# 10 folders and closed in none.

SUITE_DONE = ('delivered', 'complete', 'applied', 'measured')
_WEEK_LOOKS = {}

SUITE_STEP_RULES = {
    'daily-check': [
        "In the daily suite the daily check comes first. Its reads were asked for at the start of the run, with the week's "
        "slowest report, so the week's reports are being made while it is worked."],
    'weekly-close': [
        "Close the VIP week after the daily check, collecting the week's reports last: the run asked Amazon for them at "
        "its start (task.reports, each marked week_read), so most are made by now. Follow the routine prompt from its "
        "step 1: WEEKLY_REFRESH.py plan names each read; record the report IDs this run already has with its requested "
        "command instead of asking again, save each report where it says, then next and finish until finish answers "
        "ready, and close the week with the review and record-week. When a report Amazon is still making holds the close "
        "past the rest of today's work, record this brand failed with \"weekly close: waiting for <the reads> (<its "
        "refresh run>)\" in the note: the next suite carries it on first. A week is never closed on partial reports."],
    'growth-review': [
        "Run the Weekly Growth Review after the week's close (on VIP it reads the closed week). Its go lines and the daily "
        "check's go through one CHANGE_BATCH.py build, so this brand has one go list today."],
    'changes-read': [
        "What last week's changes did: run its kit's MEASURE_CHANGES.py (in task.guide_folder) due --short with "
        "--project-root this brand's folder and make the reads it names that the week's refresh didn't save; then measure "
        "--all-due (on VIP add --record, so the VIP Machine keeps each result), then the start's digest. Say in this "
        "brand's summary what worked, what didn't and what is too early (with the day its result is read), each with its "
        "money, as the digest groups them; a change waiting for a report names that report."],
}
SUITE_PREFETCH_WORDS = (" In the daily suite a brand's reads put the week's slowest report first (the Search Query "
                        "Performance call, marked week_read) with the day's own reads; its next_rounds hold the rest of the "
                        "week's reports (week_read) after the stop lines' other Ads reads. Ask for each round as the one "
                        "before it finishes, so the week's reports are made while the daily checks are worked; each "
                        "brand's weekly close step collects them last.")


def week_monday(moment):
    """The Monday of this moment's week (its own date)."""
    day = moment.date()
    return day - dt.timedelta(days=day.weekday())


def brand_week(root, brand, moment):
    """Where a VIP brand's week stands (Caiman 0.3.57): its kit's WEEKLY_REFRESH.py weekly_close_due ({'status': due,
    collecting, refreshed or closed, 'week', 'due_on', 'run_id', 'words'}), loaded once a file; for a kit before it, the
    VIP Machine's own log says whether the week is closed. None for a brand with no VIP Machine set up. Never raises."""
    if brand.get('tier') != 'vip' or brand.get('vip_machine') != 'set up':
        return None
    folder = brand_folder(root, brand)
    program = guide_folder(folder) / 'WEEKLY_REFRESH.py'
    look = None
    try:
        if program.is_file() and not program.is_symlink():
            key = str(program.resolve())
            if key not in _WEEK_LOOKS:
                import importlib.util
                spec = importlib.util.spec_from_file_location('_caiman_workspace_week_{}'.format(len(_WEEK_LOOKS)), key)
                module = importlib.util.module_from_spec(spec)
                quiet = sys.dont_write_bytecode
                sys.dont_write_bytecode = True
                try:
                    spec.loader.exec_module(module)
                finally:
                    sys.dont_write_bytecode = quiet
                _WEEK_LOOKS[key] = getattr(module, 'weekly_close_due', None)
            if _WEEK_LOOKS[key]:
                look = _WEEK_LOOKS[key](folder, moment)
    except Exception:          # an older kit, or one that can't be read: the VIP Machine's log, below
        look = None
    if isinstance(look, dict) and look.get('status'):
        return look
    start, end = machine_window(moment)
    week = {'start': start, 'end': end}
    rel_machine = brand.get('vip_machine_folder') or MACHINE_DIR
    closed = None
    text = read_text(folder.joinpath(*rel_machine.split('/')) / 'runs' / 'run_receipts.jsonl', 64 * 1024 * 1024) or ''
    for line in text.splitlines():
        try:
            row = as_dict(json.loads(line))
        except ValueError:
            continue
        when = parse_time(row.get('closed_at'))
        if not when:
            continue
        # the week its scorecard was made for (the kit's weekly_close_due rule, Caiman 0.3.57's release review: a late
        # close of the week before isn't this week's), else the date in its run ID, else when it was closed
        made = parse_time(as_dict(row.get('scorecard')).get('generated_at'))
        dates = re.findall(r'20\d\d-\d\d-\d\d', str(row.get('run_id') or ''))
        last = dt.date.fromisoformat(end)
        if made is not None:
            hit = machine_window(made)[1] == end
        elif dates:
            hit = end in dates
        else:
            hit = last + dt.timedelta(days=14) <= when.astimezone(dt.timezone.utc).date() < last + dt.timedelta(days=21)
        if hit:
            closed = when
    if closed:
        return {'status': 'closed', 'week': week, 'words': 'The VIP week of {} to {} is closed.'.format(start, end)}
    return {'status': 'due', 'week': week, 'words': (
        "The VIP week of {} to {} isn't closed yet (this brand's kit is older than Caiman 0.3.57, so how far its refresh "
        'has got is read in its own folder).'.format(start, end))}


def growth_review_since(folder, monday, today):
    """'delivered' when this brand's Weekly Growth Review was saved or delivered since monday (GROWTH_REVIEW.py's
    outputs/growth-review/GROWTH REVIEW <day>.md, or the plan's record), 'put off' when the member put it off past
    today (NEXT_STEP.py skip), else None."""
    try:
        for path in (folder / 'outputs' / 'growth-review').glob('GROWTH REVIEW *.md'):
            day = path.stem[len('GROWTH REVIEW '):][:10]
            if DAY_RE.match(day) and dt.date.fromisoformat(day) >= monday:
                return 'delivered'
    except (OSError, ValueError):
        pass
    state = as_dict(read_json(folder / '.caiman' / 'plan' / 'state.json'))
    for item in as_dict(state.get('items')).values():
        item = as_dict(item)
        if item.get('workflow') != 'weekly-growth-review':
            continue
        if item.get('status') == 'skipped':
            until = text_value(item.get('skip_until'))
            if until and DAY_RE.match(until[:10]) and dt.date.fromisoformat(until[:10]) > today:
                return 'put off'
        elif item.get('status') in SUITE_DONE:
            when = parse_time(item.get('delivered_at'))
            if when and when.date() >= monday:
                return 'delivered'
    return None


def changes_read_since(folder, monday):
    """Whether what last week's changes did was read since monday: MEASURE_CHANGES.py digest --save's
    outputs/RESULTS <day>.md."""
    try:
        for path in (folder / 'outputs').glob('RESULTS *.md'):
            day = path.stem[len('RESULTS '):][:10]
            if DAY_RE.match(day) and dt.date.fromisoformat(day) >= monday:
                return True
    except (OSError, ValueError):
        pass
    return False


def suite_steps(root, brand, moment):
    """One brand's steps in the daily suite on this day, in order: [{step, workflow, name, why}]. Every day the
    Advertising Daily Check; Monday to Friday, whatever of the week isn't done yet: the VIP week's close (VIP, with its VIP
    Machine set up), the Weekly Growth Review and what last week's changes did, all worked out from the brand's own
    files, so a Monday step left open comes back the next day and one already done doesn't. A brand with no plan yet
    (setup first) gets the daily check only."""
    folder = brand_folder(root, brand)
    today = moment.date()
    monday = week_monday(moment)
    steps = [{'step': 'daily-check', 'workflow': 'advertising-daily-check', 'name': 'The Advertising Daily Check',
              'why': ("Every day: yesterday's numbers and anything that jumped, the stop lines and the changes read, the ad "
                      "account's health, and this brand's go list.")}]
    if today.weekday() > 4 or not (folder / '.caiman' / 'plan' / 'state.json').is_file():
        return steps
    when = 'today, Monday' if today == monday else 'since Monday, {} {}'.format(MONTHS[monday.month - 1], monday.day)
    week = brand_week(root, brand, moment)
    if week and week.get('status') != 'closed':
        steps.append({'step': 'weekly-close', 'workflow': 'vip-weekly-loop', 'name': "The VIP week's close",
                      'why': week.get('words') or 'The VIP week is due for its close.', 'week': week.get('week'),
                      'week_status': week.get('status')})
    if brand.get('tier') == 'vip' and brand.get('vip_machine') != 'set up':
        return steps                        # Deep Seed closes the first week and delivers the first review
    if not growth_review_since(folder, monday, today):
        steps.append({'step': 'growth-review', 'workflow': 'weekly-growth-review', 'name': 'The Weekly Growth Review',
                      'why': "This week's Weekly Growth Review is due {}.".format(when)})
    if not changes_read_since(folder, monday):
        steps.append({'step': 'changes-read', 'workflow': None, 'name': "What last week's changes did",
                      'why': "What last week's changes did is due {}: no results page saved this week.".format(when)})
    return steps


def left_open(root, brand):
    """What the last daily suite left open for this brand: {run, status, note} when its entry there was recorded failed
    or needs-answer, else None (a brand that run didn't get to is carried on first by run start, as for any run)."""
    for _path, data in all_runs(root):               # newest first
        if data.get('workflow') != 'suite':
            continue
        entry = next((item for item in data.get('brands') or [] if item.get('folder') == brand['folder']), None)
        if entry is None:
            continue
        if entry.get('status') in ('failed', 'needs-answer'):
            return {'run': data['name'], 'status': entry['status'], 'note': entry.get('note')}
        return None
    return None


def suite_reports_plan(root, brand, moment, deadline, steps):
    """A suite brand's reports: the daily check's (reports_plan), with the week's reads when a weekly step is due today:
    the week's slowest, the Search Query Performance call, goes first with the day's reads, and its Ads reports after the
    stop lines' other reads, in rounds (due_reads), so they are made while the daily check is worked; each marked
    week_read. None when the brand has no connector slug saved."""
    flows = [step['workflow'] for step in steps]
    plan = reports_plan('advertising-daily-check', brand, moment, root, deadline)
    week = []
    for flow in ('vip-weekly-loop', 'weekly-growth-review'):
        if flow in flows:
            week += prefetch_reads(flow, brand, moment, root, deadline)
    if not week:
        return plan
    if plan is None:
        plan = {'reads': [], 'requested': {}, 'replaced': []}
    have = list(plan['reads']) + list(plan.get('due_reads') or [])
    names_seen = {read.get('read') for read in have}
    keys_seen = {(read.get('tool'), json.dumps(read.get('arguments'), sort_keys=True)) for read in have}
    first, later = [], []
    for read in week:
        key = (read.get('tool'), json.dumps(read.get('arguments'), sort_keys=True))
        if read.get('read') in names_seen or key in keys_seen:
            continue
        names_seen.add(read.get('read'))
        keys_seen.add(key)
        read = dict(read, week_read=True)
        (first if read.get('tool') == 'bx_brand_view_sqp' else later).append(read)
    plan['reads'] = first + list(plan['reads'])
    if later:
        plan['due_reads'] = list(plan.get('due_reads') or []) + later
    return plan


def changes_read_start(folder, guide):
    """How "what last week's changes did" starts in one brand: its kit's MEASURE_CHANGES.py digest of the last week."""
    program = guide / 'MEASURE_CHANGES.py'
    if not program.is_file():
        return {'start': None, 'problem': ("This brand's kit has no MEASURE_CHANGES.py, so last week's changes can't be read "
                                           'here: say so in its summary; its kit needs updating with kit-sync.')}
    argv = [str(program), 'digest', '--project-root', str(folder), '--weeks', '1', '--save']
    return {'start': {'program': python(), 'argv': argv, 'shell': command_line(argv),
                      'how': ("After due --short and measure --all-due (the step's rules), run it for this brand: it saves "
                              "outputs/RESULTS <today>.md, the week's results grouped.")}}


def suite_task_steps(root, data, entry, folder, guide):
    """A suite brand's steps for its task: each with its own start (as its workflow's run would give it) and rules."""
    steps = entry.get('steps') or [{'step': 'daily-check', 'workflow': 'advertising-daily-check',
                                    'name': 'The Advertising Daily Check', 'why': None}]
    out = []
    for step in steps:
        item = {'step': step['step'], 'name': step.get('name'), 'why': step.get('why')}
        if step.get('workflow'):
            item.update(workflow_start(root, data, entry, step['workflow'], folder, guide))
            item['rules'] = SUITE_STEP_RULES.get(step['step'], []) + workflow_rules(root, data, entry, step['workflow'],
                                                                                     guide)
        else:
            item.update(changes_read_start(folder, guide))
            item['rules'] = list(SUITE_STEP_RULES.get(step['step'], []))
        out.append(item)
    return out


def suite_rules(root, data, entry):
    """The daily suite's rules for one brand (Caiman 0.3.57, FLAGS F147)."""
    names_ = [step.get('name') or step['step'] for step in entry.get('steps') or []]
    rules = []
    rules.append(("This is the daily suite: this brand's steps today are in task.steps, in order ({}). Do each with its "
                  "own start and rules, in this brand's folder only, then the next; the brand's summary says each step's "
                  'result in a line.').format('; '.join(names_) or 'the daily check'))
    rules.append("Record the brand once, after its last step: done when every step is done. A step that can't finish "
                 "today (a report Amazon is still making, an answer only the member has) is recorded with the brand: "
                 "failed (or needs-answer) with the step and why in the note, so the run note shows it open with its "
                 'reason and the next suite carries it on first. Work no step of another brand meanwhile.')
    return rules


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
            'resumed': resumed, 'summary_file': str(summary), 'start': None,
            # Caiman 0.3.34: the brand's handoff, beside its summary; run finish puts every brand's together.
            'handoff_file': str(handoff_beside(summary))}
    if text_value(entry.get('carried_from')):
        task['carried_from'] = entry['carried_from']
    if kind == 'suite':
        # Caiman 0.3.57 (FLAGS F147): the day's steps for this brand, each with its own start and rules
        task['steps'] = suite_task_steps(root, data, entry, folder, guide)
    else:
        task.update(workflow_start(root, data, entry, data['workflow'], folder, guide))
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
        'needed in --note) and go on with the next brand. A question the work goes on without (one with a default '
        "used meanwhile, or one for the member to answer later) isn't needs-answer: record the brand done, with the "
        "question in its note and its handoff's need.",
        'When this brand is finished, save a few lines in summary_file (what was done, the numbers that matter, what '
        'needs the member), record it with when_done, and only then ask for the next brand with next (it names this '
        'run).',
        # Caiman 0.3.34: the brand's part of the combined handoff (the workspace guide, "The combined handoff").
        'Save its handoff in handoff_file (there even when the summary you record is another file), as JSON: {"done": '
        '"<one line: what was done>", "go": '
        '[{"change": "<one account change waiting for the member\'s go: the exact object, its value now and after, and '
        'the number behind it>", "ref": "<where it is in this brand\'s own records, such as its proposal ID>"}], "need": '
        '[{"ask": "<a fact only the member has>", "default": "<what you use meanwhile>"}], "next": "<what Caiman does '
        'next for this brand>"}, leaving out a part with nothing in it. The combined note numbers every brand\'s go '
        'lines in one list, so the member can answer go 1 3; nothing changes until they do.',
        # Caiman 0.3.57 (FLAGS F150; the release review: the combined go list was free text, so the rule quotes the
        # batch put on a line never reached the member)
        'Each "go" item is one of this brand\'s CHANGE_BATCH.py build go lines, word for word (its your_go line: a line '
        'a rule or a logged change bears on carries "Check first" with the rule line quoted), with the batch ID and the '
        'line\'s number as its ref; never a go line written another way.',
    ]
    if not (guide_folder(brand_folder(Path(root), entry)) / 'CLIENT_RULES.py').is_file():
        rules.append("This brand's kit is older than Caiman 0.3.57, so its CHANGE_BATCH.py build doesn't check a go list "
                     'against CLIENT_RULES.md: read CLIENT_RULES.md whole before its go list, and on each go line quote '
                     'any rule line the change may go against and any change logged in the last 30 days it sets back. '
                     'The kit update (kit-sync) brings the check.')
    if kind == 'suite':
        rules += suite_rules(root, data, entry)
    else:
        rules += workflow_rules(root, data, entry, data['workflow'], guide)
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
        rules.append(reports_rule(entry, reports, data['workflow']))
    left = entry.get('left_open') if isinstance(entry.get('left_open'), dict) else None
    if kind == 'suite' and left:
        # Caiman 0.3.57 (FLAGS F147): "carry over what the last run left open" comes first
        rules.insert(0, 'The last daily suite ({}) left this brand {}: {}. Start with that: carry it on, or say in this '
                        "brand's summary why it no longer applies.".format(left.get('run'), STATUS_WORDS.get(
                            left.get('status'), left.get('status')).lower(), one_line(left.get('note') or 'no note was '
                                                                                      'recorded', 400).rstrip('.')))
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
    elif text_value(entry.get('carried_started_at')) and not earlier_day(data['workflow'], entry.get('carried_from'),
                                                                         data['name'][:10]):
        # Caiman 0.3.34: a brand an earlier run was finished without, after it had started there (a daily workflow's
        # from an earlier day is that day's work: the new day's starts fresh).
        rules.append('This brand was started in the run of {} and not recorded there: check its folder for what was '
                     'already done and carry on from there rather than starting over.'.format(
                         run_day_words(entry.get('carried_from'))))
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


def next_answer(root, path, data, command, extra=None, session=None, take_over_brand=None, leave=(), brand=None):
    session = session or new_session()
    entry, resumed, held = hand_out(root, path, data, session, take_over_brand, leave, brand=brand)
    moment = now()
    label = data.get('workflow_name') or data['workflow']
    answer = {'schema': RUN_SCHEMA, 'command': command, 'workspace': str(root), 'run': data['name'],
              'run_file': rel(root, path), 'workflow': data['workflow'], 'scheduled': bool(data.get('scheduled')),
              'session': session, 'progress': progress(data)}
    answer.update(extra or {})
    # Caiman 0.3.34: finish names this session, so a brand it had in progress is carried on without asking.
    finish = command_line([str(Path(__file__).resolve()), 'run', 'finish', '--workspace', str(root), '--run',
                           data['name'], '--session', session])
    notes = []
    if held['taken_over']:
        gone = held['taken_over']
        words = claim_words({'session': gone.get('session'), 'claimed_at': gone.get('claimed_at'),
                             'claimed_by': gone.get('claimed_by')}, moment)
        if data.get('scheduled'):
            notes.append('{} was taken over from {}, which never recorded it.'.format(gone['name'], words))
        else:
            # Caiman 0.3.34: carried on without asking; the member can still leave it to that session.
            notes.append("{} was taken over from {}, which hasn't recorded it, so I'm carrying it on here. If that "
                         "session is still working on it, say so and I'll leave it to it and go on with the next "
                         'brand.'.format(gone['name'], words))
            answer['choices'] = [{'choice': 'leave-it', 'words': 'Leave {} to that session and go on with the next '
                                                                 'brand'.format(gone['name']),
                                  'command': choice_command(root, data, session, '--leave', {'id': gone['brand']})}]
    if held['left']:
        notes.append('Left to the session working on {}: {}.'.format(
            'it' if len(held['left']) == 1 else 'them',
            '; '.join('{} ({})'.format(item['name'], claim_words(item, moment)) for item in held['left'])))
    if notes:
        answer['held'] = {'taken_over': held['taken_over'], 'left': [
            {'brand': item['id'], 'name': item['name'], 'session': item.get('session'),
             'claimed_at': item.get('claimed_at') or item.get('started_at')} for item in held['left']]}
    if entry is None and held['left']:
        # Only brands another session claimed less than claim_hold ago (or the member left to it) are left. Caiman
        # 0.3.34: the one real choice, asked only now and only in a conversation: has that session stopped (carry it on
        # here) or is it still working (it records the brand and the combined note follows)?
        names_left = names([item['name'] for item in held['left']])
        scheduled = bool(data.get('scheduled'))
        one = len(held['left']) == 1
        answer.update(
            status='brands-in-progress-elsewhere', task=None, finish=None if scheduled else finish,
            choices=[] if scheduled else [{'choice': 'carry-on-here', 'words': 'Carry on with {} here'.format(item['name']),
                                            'command': choice_command(root, data, session, '--take-over', item)}
                                           for item in held['left']],
            member_message=('Every other brand in this {} run has a result. {} {} still being worked on in another '
                            'session ({}).').format(label, names_left, 'is' if one else 'are',
                                                    '; '.join(claim_words(item, moment) for item in held['left'])) + (
                '' if scheduled else (' Has that session stopped? If it has, I\'ll finish {} here; if it\'s still working, '
                                      'it records {} and I\'ll write the combined summary then.').format(
                    names_left, 'it' if one else 'them')),
            how_to_continue=('Stop here without finishing the run: the session working on {} records it and finishes the '
                             'run. Tell the member only what this run did.'.format(names_left) if scheduled else
                             'Ask the member only this (member_message). If that session stopped, run its choice '
                             '(carry-on-here) and do the brand here. If it is still working, wait: when it has recorded '
                             'the brand, run finish for the combined note. For the summary now, finish with --partial: '
                             'the brand stays to do, and the next run, run next or plan picks it up first.'))
        return answer
    if entry is None:
        answer.update(status='all-brands-done', task=None, finish=finish,
                      member_message='Every brand in this {} run has a result. Next: the combined summary.'.format(label),
                      how_to_continue='Run finish (the finish command) to write the combined note, then give the member '
                                      'its main points.')
        return answer
    task = task_for(root, data, entry, resumed, session)
    carried = text_value(entry.get('carried_from'))
    answer.update(status='brand-ready', task=task, finish=finish,
                  member_message='{} for {} ({}){}.{}'.format(label, entry['name'], task['position'],
                                                             ', carrying on where it stopped' if resumed else (
                                                                 ", which the run of {} didn't get to".format(
                                                                     run_day_words(carried)) if carried else ''),
                                                             ''.join(' ' + note for note in notes)),
                  how_to_continue=('Do task for this brand only, following task.rules; save its summary, record it with '
                                   'task.when_done, then run task.next (it names this run and this session).'))
    return answer


# ---------------------------------------------------------------- reports first, for the report-heavy workflows (0.3.17)

# Amazon can take an hour or more to make some accounts' Ads reports. For these workflows run start asks Claude to
# request every brand's reports before the first brand's work, each with that brand's own connector slug. The report IDs
# are recorded in the run file per brand (run reports), and each brand's task polls its own IDs instead of requesting
# them again; a report that failed or expired is requested again in that brand's own task. Caiman 0.3.28: at most
# PREFETCH_OPEN_LIMIT of a brand's report requests are open at once (both kits' INITIAL HISTORY SEED.md, VIP's
# SCHEDULED OPERATIONS.md; Amazon's SQP refuses new reports while about five wait), so run start lists that many of
# its reads, the slowest first as the plan orders them, and the brand's own task asks for the rest as earlier ones
# finish (task.reports.to_request).
PREFETCH_WORKFLOWS = ('advertising-daily-check', 'advertising-weekly-review', 'weekly-growth-review', 'vip-weekly-loop',
                      'suite')
PREFETCH_OPEN_LIMIT = 4
REPORT_ID_RE = re.compile(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,127}')
ADS_FORMATS = (('SP', 'Sponsored Products'), ('SB', 'Sponsored Brands'), ('SD', 'Sponsored Display'))
PREFETCH_HOW = ("Before any brand's work, request every brand's reports listed here: call each read's tool with its "
                "arguments exactly as given (each brand's own brand_slug; never one brand's slug for another), then record "
                'the report IDs the requests return with that brand\'s record command, each ID in place of <report id> '
                '(a request that returns several: all of them, separated by commas; a Search Query Performance request '
                "answers at once with one sqp_batch_id for all its reports: record that). Don't wait for the reports: each "
                "brand's task polls its own IDs when its turn comes, with the tool its read names (poll_with: get_sqp_batch "
                "for Search Query Performance). A request that errors is recorded with --failed "
                '"<read>=<what it said>" in place of --add, and that brand\'s task asks for it again. Never record a '
                'download link: only the report_id. Each brand lists at most four reads, the slowest first: its own task '
                'asks for the rest (later) as these finish. A brand\'s next_rounds are the other Ads reads its own '
                'STOP_LINES.py due names (its keywords and targets, in due_reads with their tools and arguments): once '
                'its reads above finish, ask for a round of up to four the same way and record their IDs (next_record '
                'for the first round), so its own check polls them instead of asking again.')
SQP_PREFETCH_WORKFLOWS = ('vip-weekly-loop', 'weekly-growth-review')
REFRESH_PREVIEW_SECONDS = 60     # one brand's WEEKLY_REFRESH.py plan --preview
REFRESH_PREVIEW_BUDGET = 100     # every brand's, in one run start: a command may be cut off after 3 minutes
# The VIP Machine's reads that its weekly refresh (WEEKLY_REFRESH.py) plans under the same names and arguments when
# their sources are due, so a brand's task records the IDs there instead of asking again (Caiman 0.3.28).
REFRESH_READ_NAMES = ('sp-advertised-products-4-weeks', 'sp-campaigns-4-weeks', 'sp-placements-4-weeks',
                      'sp-search-terms-last-7-days')
# The weekly review's growth moves (GROWTH_REVIEW.py) read Sponsored Products' 7-day sales on the newest four whole
# Sunday-Saturday weeks whose last day is at least 8 days back (7-day sales are final about 8 days after each day), not
# only the VIP Machine's four weeks (Caiman 0.3.28): (read, tool, plain words, ad_product), the same tools and argument
# shapes as the VIP Machine's reads.
FRESH_DAYS_BACK = 8
FRESH_READS = (('sp-search-terms-fresh-4-weeks', 'analytics_search_term_report', 'Sponsored Products search terms', 'SP'),
               ('sp-keywords-fresh-4-weeks', 'analytics_keyword_performance', 'Sponsored Products by keyword', 'SP'),
               ('sp-targets-fresh-4-weeks', 'analytics_targeting_type_performance',
                'Sponsored Products by product and automatic target', None),
               ('sp-placements-fresh-4-weeks', 'analytics_placement_performance', 'Sponsored Products by placement',
                None),
               ('sp-campaigns-fresh-4-weeks', 'analytics_campaign_performance', 'Sponsored Products by campaign', 'SP'),
               ('sp-advertised-products-fresh-4-weeks', 'analytics_advertised_asin_report',
                'Sponsored Products by advertised product', 'SP'))


# Caiman 0.3.34: the Advertising Daily Check reads each ad type's campaigns with a row for each day, yesterday and the 7
# days before it (yesterday's delivery and spend against the 7 days before), one read each, in place of a total for
# yesterday and one for the last 7 days. The Sponsored Products one is the read the brand's own STOP_LINES.py due asks
# for (its delivery check and the daily pass's campaign days) when that covers those days, so it is asked for and saved
# once (saved reads are found by their dates). The days are the account's, as STOP_LINES.py due counts them; without
# its answer, today's date in UTC, as this file counts the other reads' days.
DAILY_CHECK_READ = '{}-campaigns-yesterday-vs-7-days-before'
DAILY_CHECK_WHY = "yesterday's delivery and spend against the 7 days before"
DUE_PREVIEW_SECONDS = 30         # one brand's STOP_LINES.py due (it reads the brand's files only and saves nothing)
STOP_LINES_READS = 'Reports/stop-lines'
DAY_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')
# Where the daily check's date came from (a run's reports.account_date_from).
DUE_DATE_WORDS = "the account's date, as its STOP_LINES.py due counts it"
UTC_DATE_WORDS = ("today's date in UTC, because the account's date couldn't be read (its STOP_LINES.py due didn't "
                  'answer)')


def ads_read(read, tool, slug, what, **arguments):
    return {'read': read, 'tool': tool, 'arguments': dict([('brand_slug', slug)] + sorted(arguments.items())),
            'what': what, 'poll_with': 'get_ads_report_status'}


def stop_lines_due(root, brand, deadline=None):
    """The brand's own STOP_LINES.py due (in its guide folder), or None: no STOP_LINES.py, it didn't answer in time or
    answered with another slug than the brand's, or the run's time for previews (deadline) is used up."""
    if root is None:
        return None
    folder = brand_folder(root, brand)
    program = guide_folder(folder) / 'STOP_LINES.py'
    if not program.is_file():
        return None
    seconds = DUE_PREVIEW_SECONDS
    if deadline is not None:
        seconds = min(seconds, deadline - time.monotonic())
        if seconds < 5:
            return None
    code, out, _err, failed = run_program([python(), '-B', str(program), 'due', '--project-root', str(folder)], folder,
                                          seconds)
    data = json_from(out)
    if failed or code != 0 or not data or data.get('status') != 'ok' or data.get('brand_slug') != brand.get('slug') \
            or not DAY_RE.match(str(data.get('date') or '')):
        return None
    return data


def due_read_covering(due, code, slug, first, last):
    """The campaign read with a row for each day that STOP_LINES.py due names for this ad product and slug and that
    covers first to last (the shortest when several do), or None."""
    found = []
    for read in list(due.get('reads') or []) + list(due.get('daily_reads') or []):
        args = read.get('arguments') if isinstance(read, dict) and isinstance(read.get('arguments'), dict) else {}
        if read.get('tool') != 'analytics_campaign_performance' or str(args.get('time_unit') or '').upper() != 'DAILY' \
                or str(args.get('ad_product') or 'SP').upper() != code or args.get('brand_slug') != slug \
                or not text_value(read.get('read')) or not text_value(read.get('save_as')):
            continue
        try:
            start, end = dt.date.fromisoformat(str(args.get('start_date'))), dt.date.fromisoformat(str(args.get('end_date')))
        except ValueError:
            continue
        if start <= first and end >= last:
            found.append(((end - start).days, read))
    return min(found, key=lambda item: item[0])[1] if found else None


def daily_check_reads(root, brand, moment, deadline=None, more=None):
    """(reads, the account's date they were worked out for, where that date came from): the Advertising Daily Check's
    campaign reads, one for each ad type, a row for each day, yesterday and the 7 days before it (Caiman 0.3.34). Each
    is saved in Reports/stop-lines/<date>/ (its save_as), where STOP_LINES.py check finds a read by its dates."""
    slug = text_value(brand.get('slug'))
    due = stop_lines_due(root, brand, deadline)
    if due:
        day, source = dt.date.fromisoformat(due['date']), DUE_DATE_WORDS
    else:
        day, source = moment.astimezone(dt.timezone.utc).date(), UTC_DATE_WORDS
    last = day - dt.timedelta(days=1)
    first = last - dt.timedelta(days=7)
    reads = []
    for code, words in ADS_FORMATS:
        name = DAILY_CHECK_READ.format(code.lower())
        same = due_read_covering(due, code, slug, first, last) if due else None
        if same:
            args = same['arguments']
            read = {'read': name, 'tool': same['tool'],
                    'arguments': dict([('brand_slug', slug)] + sorted((key, value) for key, value in args.items()
                                                                      if key != 'brand_slug')),
                    'what': ("{} by campaign, a row for each day, {} to {}: {}, and the stop lines' read of the same days "
                             '(STOP_LINES.py due names it {}): one read, saved once').format(
                        words, args['start_date'], args['end_date'], DAILY_CHECK_WHY, same['read']),
                    'poll_with': 'get_ads_report_status', 'stop_lines_read': same['read'], 'save_as': same['save_as']}
        else:
            read = ads_read(name, 'analytics_campaign_performance', slug, '{} by campaign, a row for each day, {} to {}: '
                                                                          '{}'.format(words, first.isoformat(),
                                                                                      last.isoformat(), DAILY_CHECK_WHY),
                            ad_product=code, start_date=first.isoformat(), end_date=last.isoformat(), time_unit='DAILY')
            read['save_as'] = '{}/{}/campaign-{}-{}-to-{}.json'.format(STOP_LINES_READS, day.isoformat(), code.lower(),
                                                                       first.isoformat(), last.isoformat())
        reads.append(read)
    if due and more is not None:
        # Caiman 0.3.56 (FLAGS P324): more (a list) takes the brand's other Ads reads its own STOP_LINES.py due names (its
        # keywords and targets), each by its own name, so the run asks for them in rounds and records their IDs: the
        # lead asked for them by hand and handed their IDs to the lanes in a side file
        taken = set(read.get('stop_lines_read') for read in reads if read.get('stop_lines_read'))
        for read in list(due.get('reads') or []) + list(due.get('daily_reads') or []):
            args = read.get('arguments') if isinstance(read, dict) and isinstance(read.get('arguments'), dict) else {}
            name = text_value(read.get('read')) if isinstance(read, dict) else None
            if not name or name in taken or not str(read.get('tool') or '').startswith('analytics_') \
                    or args.get('brand_slug') != slug or not text_value(read.get('save_as')) \
                    or (read.get('poll_with') or 'get_ads_report_status') != 'get_ads_report_status':
                continue
            taken.add(name)
            more.append({'read': name, 'tool': read['tool'],
                         'arguments': dict([('brand_slug', slug)] + sorted((key, value) for key, value in args.items()
                                                                           if key != 'brand_slug')),
                         'what': text_value(read.get('what')) or "an Ads read the brand's own STOP_LINES.py due names",
                         'poll_with': 'get_ads_report_status', 'stop_lines_read': name, 'save_as': read.get('save_as'),
                         'due_read': True})
    return reads, day, source


def refresh_sqp_reads(root, brand, deadline=None):
    """Caiman 0.3.28: the Search Query Performance reads a VIP brand's weekly refresh would ask for now (its kit's
    WEEKLY_REFRESH.py plan --preview, which saves nothing), so a run across brands asks Amazon for them first: the
    connector queues them (since Oct 21, 2026) and Amazon makes about 20 to 40 an hour. [] when the brand's kit has no
    WEEKLY_REFRESH.py, its VIP Machine needs no SQP refresh, the preview can't run, or the run's time for previews
    (deadline, a time.monotonic() value) is used up: the brand's own task plans them then."""
    if root is None:
        return []
    folder = brand_folder(root, brand)
    program = guide_folder(folder) / 'WEEKLY_REFRESH.py'
    if not program.is_file():
        return []
    seconds = REFRESH_PREVIEW_SECONDS
    if deadline is not None:
        seconds = min(seconds, deadline - time.monotonic())
        if seconds < 5:
            return []
    code, out, _err, failed = run_program([python(), '-B', str(program), 'plan', '--project-root', str(folder),
                                           '--preview', '--no-measure'], folder, seconds)
    data = json_from(out)
    if failed or code != 0 or not data or data.get('brand_slug') != brand.get('slug'):
        return []
    reads = []
    for group in data.get('reads') or []:
        if not isinstance(group, dict) or group.get('group') != 'sqp':
            continue
        for read in group.get('reads') or []:
            if not isinstance(read, dict) or read.get('state') == 'done' or read.get('report_ids'):
                continue
            if read.get('tool') != 'bx_brand_view_sqp' or not isinstance(read.get('arguments'), dict):
                continue
            reads.append({'read': read['id'], 'tool': read['tool'], 'arguments': read['arguments'],
                          'what': read.get('what') or 'Search Query Performance', 'poll_with': 'get_sqp_batch',
                          'refresh_run': data.get('run_id')})
    return reads


# Caiman 0.3.46 (FLAGS F46, Nov 8, 2026): a run started at 01:20 UTC asked 12 brands for "the last 7 complete days" through
# a day still running in the accounts' own time zone (6:20 pm Pacific), so the newest search-term read held a partial
# day. The days are the account's: its time zone is read in place by the brand's own kit (the engine's account_zone: the
# saved Ads profile read, else the marketplace's), as the brand's weekly refresh and dashboard count them.
ZONE_ENGINES = ('Operating Framework/VIP Machine/engine', 'Manual Operating Framework/engine', 'VIP Machine/engine')
_ZONE_RULES = {}


def account_day(root, brand, moment):
    """(the account's date at this moment, its time zone): from the brand's own kit's engine (change_results.py's
    account_zone and local_day), loaded once a file. (the date in UTC, None) when the brand has no engine here or it
    can't say, as before 0.3.46."""
    utc_day = moment.astimezone(dt.timezone.utc).date()
    if root is None:
        return utc_day, None
    folder = brand_folder(root, brand)
    places = []
    for base in (guide_folder(folder), folder):
        for relative in ZONE_ENGINES:
            candidate = base.joinpath(*relative.split('/')) / 'change_results.py'
            if candidate not in places:
                places.append(candidate)
    for candidate in places:
        try:
            if not candidate.is_file() or candidate.is_symlink():
                continue
            key = str(candidate.resolve())
            if key not in _ZONE_RULES:
                import importlib.util
                spec = importlib.util.spec_from_file_location('_caiman_workspace_zone_{}'.format(len(_ZONE_RULES)), key)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                _ZONE_RULES[key] = module
            rules = _ZONE_RULES[key]
            zone = (rules.account_zone(folder) or {}).get('zone')
            day = rules.local_day(moment.astimezone(dt.timezone.utc), zone) if zone else None
            if isinstance(day, dt.date):
                return day, zone
        except Exception:      # an older kit, or an engine that can't be read: the date in UTC, as before
            _ZONE_RULES.setdefault(str(candidate), None)
            continue
    return utc_day, None


def weeks_ending(moment, days_back):
    """Four whole Sunday-Saturday weeks (UTC dates) ending on the latest Saturday on or before the day days_back days
    before this moment: (first day, last day) as ISO dates."""
    cutoff = moment.astimezone(dt.timezone.utc).date() - dt.timedelta(days=days_back)
    end = cutoff - dt.timedelta(days=(cutoff.weekday() - 5) % 7)
    return (end - dt.timedelta(days=27)).isoformat(), end.isoformat()


def machine_window(moment):
    """The VIP Machine's four weeks for a review run at this moment, as its weekly guide counts them (UTC dates): back
    14 days for the Ads attribution window, the latest complete Saturday, and the 27 days before it."""
    return weeks_ending(moment, 14)


def fresh_window(moment):
    """Caiman 0.3.28: the newest four whole Sunday-Saturday weeks whose last day is at least 8 days back (UTC dates),
    the weeks the weekly review's growth moves read on Sponsored Products' 7-day sales. On Oct 19, 2026: Sep 13 to
    Oct 10 (the VIP Machine's: Sep 6 to Oct 3). On a Saturday the two are the same weeks."""
    return weeks_ending(moment, FRESH_DAYS_BACK)


def fresh_reads(slug, moment, asked):
    """The fresh-window Sponsored Products reads GROWTH_REVIEW.py takes (FRESH_READS), leaving out any read already in
    asked with the same tool and arguments (the VIP Machine's own, when the two windows are the same weeks)."""
    start, end = fresh_window(moment)
    have = {(read['tool'], json.dumps(read['arguments'], sort_keys=True)) for read in asked}
    reads = []
    for name, tool, words, product in FRESH_READS:
        read = ads_read(name, tool, slug, '{}, the newest four full weeks on 7-day sales (for the growth moves), {} to '
                                          '{}'.format(words, start, end),
                        start_date=start, end_date=end, **({'ad_product': product} if product else {}))
        if (tool, json.dumps(read['arguments'], sort_keys=True)) not in have:
            reads.append(read)
    return reads


REFRESH_HELD_DAYS = 8      # a refresh run updated this many days back or less still holds its reads


def refresh_held_reads(root, brand, moment):
    """{(tool, arguments as JSON): run ID} for the reads the brand's weekly refresh runs (WEEKLY_REFRESH.py, in its
    business folder's .caiman/weekly-refresh/) saved, or asked for and recorded the report IDs of, in runs updated in
    the last REFRESH_HELD_DAYS days. Never raises."""
    held = {}
    folder = brand_folder(root, brand) / '.caiman' / 'weekly-refresh'
    try:
        paths = sorted(folder.glob('*.json'))
    except OSError:
        return held
    since = moment - dt.timedelta(days=REFRESH_HELD_DAYS)
    for path in paths:
        record = read_json(path, 16 * 1024 * 1024)
        if not isinstance(record, dict) or not isinstance(record.get('reads'), list):
            continue
        try:
            updated = dt.datetime.fromisoformat(str(record.get('updated_at') or record.get('planned_at')).replace('Z', '+00:00'))
        except ValueError:
            continue
        if updated.tzinfo is None or updated < since:
            continue
        requested = record.get('requested') if isinstance(record.get('requested'), dict) else {}
        for read in record['reads']:
            if not isinstance(read, dict) or not read.get('tool') or not isinstance(read.get('arguments'), dict):
                continue
            files = [spec.get('file') for spec in read.get('files') or [] if isinstance(spec, dict) and spec.get('file')]
            saved = bool(files) and all((brand_folder(root, brand) / Path(*str(rel).split('/'))).is_file() for rel in files)
            asked = bool(((requested.get(read.get('id')) or {}) if isinstance(requested.get(read.get('id')), dict)
                          else {}).get('report_ids'))
            if saved or asked:
                held[(read['tool'], json.dumps(read['arguments'], sort_keys=True))] = record.get('run_id') or path.stem
    return held


def prefetch_reads(workflow, brand, moment, root=None, deadline=None):
    """The reports a run of this workflow reads for this brand: [{read, tool, arguments, what, poll_with}], with the
    brand's own slug in the arguments. [] for another workflow or a brand with no connector slug saved. A VIP brand whose
    VIP Machine is set up reviews the VIP Machine's four weeks (Sponsored Brands and Display by campaign too, and the last
    7 complete days of search terms), and for its weekly review (or a Weekly Growth Review) also, first, the Search
    Query Performance weeks its weekly refresh needs (one call, checked with get_sqp_batch: Caiman 0.3.33), and last the
    Sponsored Products reads of the newest four full weeks its growth moves take (Caiman 0.3.28); other brands' weekly
    reviews read the last 30 days; the daily check reads each ad type's campaigns with a row for each day, yesterday and
    the 7 days before it, the Sponsored Products one the brand's own stop lines' read when that covers those days
    (daily_check_reads, Caiman 0.3.34)."""
    slug = text_value(brand.get('slug'))
    if workflow not in PREFETCH_WORKFLOWS or not slug:
        return []
    if workflow == 'advertising-daily-check':
        return daily_check_reads(root, brand, moment, deadline)[0]
    if brand.get('tier') == 'vip' and brand.get('vip_machine') == 'set up':
        start, end = machine_window(moment)
        today, _zone = account_day(root, brand, moment)     # Caiman 0.3.46 (FLAGS F46): the account's day, not UTC's
        first, last = (today - dt.timedelta(days=7)).isoformat(), (today - dt.timedelta(days=1)).isoformat()
        span = "the VIP Machine's four weeks, {} to {}".format(start, end)
        sqp = refresh_sqp_reads(root, brand, deadline) if workflow in SQP_PREFETCH_WORKFLOWS else []
        machine = [ads_read('sp-search-terms-4-weeks', 'analytics_search_term_report', slug,
                         'Sponsored Products search terms, ' + span, ad_product='SP', start_date=start, end_date=end),
                ads_read('sp-advertised-products-4-weeks', 'analytics_advertised_asin_report', slug,
                         'Sponsored Products by advertised product, ' + span, ad_product='SP', start_date=start,
                         end_date=end),
                ads_read('sp-campaigns-4-weeks', 'analytics_campaign_performance', slug,
                         'Sponsored Products by campaign (the totals), ' + span, ad_product='SP', start_date=start,
                         end_date=end),
                # Caiman 0.3.27: the review covers Sponsored Brands and Display too (the VIP Machine reads SP only).
                ads_read('sb-campaigns-4-weeks', 'analytics_campaign_performance', slug,
                         'Sponsored Brands by campaign, ' + span, ad_product='SB', start_date=start, end_date=end),
                ads_read('sd-campaigns-4-weeks', 'analytics_campaign_performance', slug,
                         'Sponsored Display by campaign, ' + span, ad_product='SD', start_date=start, end_date=end),
                ads_read('sp-placements-4-weeks', 'analytics_placement_performance', slug,
                         'Sponsored Products by placement, ' + span, start_date=start, end_date=end),
                ads_read('sp-search-terms-last-7-days', 'analytics_search_term_report', slug,
                         'Sponsored Products search terms, the last 7 complete days, {} to {}'.format(first, last),
                         ad_product='SP', start_date=first, end_date=last)]
        if root is not None and (guide_folder(brand_folder(root, brand)) / 'WEEKLY_REFRESH.py').is_file():
            for read in machine:
                if read['read'] in REFRESH_READ_NAMES:
                    read['refresh_read'] = True
        fresh = fresh_reads(slug, moment, machine) if workflow in SQP_PREFETCH_WORKFLOWS else []
        # Caiman 0.3.41 (FLAGS P98): a read the brand's own weekly refresh already saved or asked for, with
        # the same tool and arguments, isn't asked for again (its refresh polls or reuses it)
        held = refresh_held_reads(root, brand, moment) if root is not None else {}
        return [read for read in sqp + machine + fresh
                if (read['tool'], json.dumps(read['arguments'], sort_keys=True)) not in held]
    if workflow == 'vip-weekly-loop':
        return []
    # Caiman 0.3.41 (FLAGS P98): with a row for each day (time_unit DAILY), so the review, PROFIT.py and the
    # Caiman Dashboard read one report; a total for the 30 days (SUMMARY) the dashboard can't use, and the days were
    # pulled again.
    reads = [ads_read('sp-search-terms-30-days', 'analytics_search_term_report', slug,
                      'Sponsored Products search terms, the last 30 days, a row for each day', ad_product='SP',
                      lookback='30d', time_unit='DAILY'),
             ads_read('sp-placements-30-days', 'analytics_placement_performance', slug,
                      'Sponsored Products by placement, the last 30 days, a row for each day', lookback='30d',
                      time_unit='DAILY'),
             ads_read('sp-advertised-products-30-days', 'analytics_advertised_asin_report', slug,
                      'Sponsored Products by advertised product, the last 30 days, a row for each day', ad_product='SP',
                      lookback='30d', time_unit='DAILY')]
    for code, words in ADS_FORMATS:
        reads.append(ads_read(code.lower() + '-campaigns-30-days', 'analytics_campaign_performance', slug,
                              words + ' by campaign, the last 30 days, a row for each day', ad_product=code,
                              lookback='30d', time_unit='DAILY'))
    return reads


def reports_plan(workflow, brand, moment, root=None, deadline=None):
    """What a run entry keeps about its brand's reports: the reads, the IDs recorded for them, and IDs replaced later.
    For the daily check, also the account's date its reads were worked out for (Caiman 0.3.34)."""
    if workflow == 'advertising-daily-check' and text_value(brand.get('slug')):
        more = []
        reads, day, source = daily_check_reads(root, brand, moment, deadline, more)
        plan = {'reads': reads, 'requested': {}, 'replaced': [], 'account_date': day.isoformat(),
                'account_date_from': source, 'account_date_known': source == DUE_DATE_WORDS}
        if more:
            plan['due_reads'] = more      # Caiman 0.3.56 (FLAGS P324): asked for in rounds, after the run's own reads
        return plan
    reads = prefetch_reads(workflow, brand, moment, root, deadline)
    return {'reads': reads, 'requested': {}, 'replaced': []} if reads else None


def poll_tools(reads):
    """The tool every read is polled with, or None when they differ (each read names its own poll_with). A read saved
    before Caiman 0.3.28 has no poll_with: it was an Ads report."""
    tools = {read.get('poll_with') or 'get_ads_report_status' for read in reads}
    return tools.pop() if len(tools) == 1 else None


def task_reports(root, data, entry, session=None):
    """A brand's reports in this run, for its task: requested (with their report IDs, to poll), to_request (not asked
    for yet, or the request failed) and the command that records a new ID. None when the run asks for none ahead."""
    plan = entry.get('reports') if isinstance(entry.get('reports'), dict) else None
    if not plan or not plan.get('reads'):
        return None
    got = as_dict(plan.get('requested'))
    requested, to_request = [], []
    # due_reads: Caiman 0.3.56 (FLAGS P324); own_reads: the reads a session recorded that the run didn't list (P350)
    for read in list(plan['reads']) + list(plan.get('due_reads') or []) + [
            item for item in plan.get('own_reads') or [] if isinstance(item, dict) and item.get('read')]:
        read = dict(read, poll_with=read.get('poll_with') or 'get_ads_report_status')
        record = as_dict(got.get(read.get('read')))
        if record.get('status') == 'requested' and record.get('report_ids'):
            requested.append(dict(read, report_ids=list(record['report_ids']), requested_at=record.get('requested_at')))
        elif record.get('status') == 'failed':
            to_request.append(dict(read, failed=record.get('note') or 'the request failed'))
        else:
            to_request.append(dict(read))
    record = command_line([str(Path(__file__).resolve()), 'run', 'reports', entry['id'], '--workspace', str(root), '--run',
                           data['name']] + (['--session', session] if session else []) + ['--add', '<read>=<report id>'])
    # Caiman 0.3.28: each read names the tool it is polled with (Search Query Performance: get_sqp_batch since 0.3.33,
    # get_report_status in a run started before it).
    return {'requested': requested, 'to_request': to_request,
            'poll_with': poll_tools(list(plan['reads']) + list(plan.get('due_reads') or [])) or "each read's own poll_with",
            'record': record}


def reports_rule(entry, reports, workflow=None):
    """The task rule for a brand whose reports were asked for ahead (prefetch_block)."""
    slug = entry.get('slug') or 'not saved yet'
    parts = []
    reads = list(reports['requested']) + list(reports['to_request'])
    sqp = any(read.get('tool') == 'bx_brand_view_sqp' for read in reads)
    ads = any((read.get('poll_with') or 'get_ads_report_status') == 'get_ads_report_status' for read in reads)
    if reports['requested']:
        parts.append("This brand's reports in task.reports.requested were requested at the start of the run: poll each "
                     'with the tool its read names in poll_with ({}; brand_slug {} and its recorded ID) and use them where '
                     "this workflow reads them; don't request them again. One that failed (FAILED or FATAL, with its "
                     'reason) or expired (source_document_expired when read): request it again here with the same tool '
                     'and arguments, and record the new ID with task.reports.record. If this workflow needs other dates '
                     'than a report\'s arguments, request that one again here with the dates it needs and record its new '
                     'ID the same way.'.format(
                         'get_sqp_batch for Search Query Performance, with its sqp_batch_id, every 15 minutes or so and '
                         'never its reports one by one; get_ads_report_status for Ads reports, with each report_id' if sqp
                         else 'get_ads_report_status', slug))
    if sqp or any(read.get('refresh_read') for read in reads):
        # Caiman 0.3.28: the SQP weeks the brand's weekly refresh needs were asked for first, and its four-week Ads
        # reports have the same names and arguments as the VIP Machine's reads here.
        parts.append("Its VIP weekly refresh (WEEKLY_REFRESH.py) plans reads of the same names and arguments (the "
                     'Search Query Performance weeks, and the VIP Machine\'s Ads reports when they are due): record each of '
                     'those IDs there with its requested command (--read <read> --report-id <id>; for Search Query '
                     'Performance, the sqp_batch_id) instead of asking '
                     'again, then save each report where the refresh\'s next (or plan) says.')
    if reports['to_request']:
        parts.append('The reads in task.reports.to_request were not requested yet, or their request failed: request them '
                     'here with this brand\'s slug and the arguments given, and record their IDs with task.reports.record.')
    # Caiman 0.3.56 (FLAGS P350): any other report this brand's work asks for is recorded the same way, under its own name
    parts.append('Any other report this brand\'s work asks Amazon for (a read its own plan names, a diagnosis read, a '
                 'page read) is recorded with task.reports.record too, under the read\'s own name (add --tool and '
                 '--arguments \'<JSON>\' so it can be asked for again): a session that picks this brand up finds its ID '
                 'in task.reports.requested (own: true) and polls it instead of asking again.')
    if reports['to_request'] or ads:
        # Caiman 0.3.28: run start asked for at most four of them; the rest wait here. Caiman 0.3.34: whenever the brand
        # has Ads reads, as the reports its own work asks for count too (the daily check's STOP_LINES.py due reads).
        if workflow == 'suite':
            # Caiman 0.3.57 (FLAGS F147): the day's reads, the stop lines' other Ads reads and the week's reports
            counted = ("these (the day's reads, every other Ads read its STOP_LINES.py due names and, on the week's "
                       "days, the week's reports)")
        elif workflow == 'advertising-daily-check' and any(read.get('due_read') for read in reads):
            # Caiman 0.3.56 (FLAGS P324): the run carries the other Ads reads its due names, so they are among these
            counted = "these (they include every other Ads read its STOP_LINES.py due names)"
        elif workflow == 'advertising-daily-check':
            counted = 'these and the keyword and target reads its STOP_LINES.py due names'
        else:
            counted = 'these and any other report this workflow asks for'
        parts.append("Keep at most four of this brand's report requests open at once, counting {}: ask for the next "
                     'one, in the order given, as an earlier one finishes.'.format(counted))
    return ' '.join(parts)


def prefetch_block(root, data, session):
    """The reports-first step for a run of a report-heavy workflow: for each brand still to do (pending, or in progress
    with this session), the first reads not recorded yet, so that at most PREFETCH_OPEN_LIMIT of its report requests
    are open (the ones already recorded count as open), with the command that records their IDs and the reads left for
    its own task (later). None when there is nothing to ask for. Another session's brand is left to it (its reports are
    that session's)."""
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
        recorded = as_dict(plan.get('requested'))
        todo = [read for read in plan.get('reads') or [] if read.get('read') not in recorded]
        open_now = sum(1 for record in recorded.values() if as_dict(record).get('status') == 'requested')
        now = todo[:max(0, PREFETCH_OPEN_LIMIT - open_now)]
        if not now:
            continue
        argv = [str(Path(__file__).resolve()), 'run', 'reports', entry['id'], '--workspace', str(root), '--run',
                data['name']] + (['--session', session] if session else [])
        for read in now:
            argv += ['--add', read['read'] + '=<report id>']
        item = {'brand': entry['id'], 'name': entry['name'], 'connector_brand_slug': entry.get('slug'),
                'reads': now, 'record': command_line(argv)}
        if len(todo) > len(now):
            item['later'] = [read['read'] for read in todo[len(now):]]
        # Caiman 0.3.56 (FLAGS P324): its own Daily Check's other Ads reads (STOP_LINES.py due's keywords and targets),
        # asked for in rounds of four once the reads above finish, recorded with the same command
        rounds = [read['read'] for read in plan.get('due_reads') or [] if read.get('read') not in recorded]
        if rounds:
            item['next_rounds'] = [rounds[n:n + PREFETCH_OPEN_LIMIT] for n in range(0, len(rounds), PREFETCH_OPEN_LIMIT)]
            first = [part for read in item['next_rounds'][0] for part in ('--add', read + '=<report id>')]
            item['next_record'] = command_line([str(Path(__file__).resolve()), 'run', 'reports', entry['id'], '--workspace',
                                                str(root), '--run', data['name']] + (['--session', session] if session else [])
                                               + first)
            item['due_reads'] = [read for read in plan['due_reads'] if read['read'] in rounds]
        brands.append(item)
    if not brands and not waiting:
        return None
    return {'status': 'to-do' if brands else 'nothing-to-request', 'how': PREFETCH_HOW, 'brands': brands,
            'not_requested': waiting}


def with_prefetch(root, data, answer):
    """A run start answer with the reports-first step added, when the run has reports still to ask for."""
    block = prefetch_block(root, data, answer.get('session'))
    if block and data.get('workflow') == 'suite':
        # Caiman 0.3.57 (FLAGS F147): the week's reports go first with the day's and the rest follow in rounds, so they
        # are being made while the daily checks are worked; the weekly close collects them last
        block['how'] = block['how'] + SUITE_PREFETCH_WORDS
    if block:
        answer['prefetch'] = block
        if block['brands']:
            answer['how_to_continue'] = ("First request every brand's reports and record their IDs (prefetch.how; one "
                                         'record command per brand). Then: ' + (answer.get('how_to_continue') or ''))
    return answer


# Caiman 0.3.56 (FLAGS P350): a read a lane asked for itself is recorded under its own name: a plain read name
OWN_READ_RE = re.compile(r'[A-Za-z0-9][A-Za-z0-9._:,+\[\]-]{1,159}')


def parse_read(raw, known, what, own=False):
    """(read, value) from "<read>=<value>", with the read checked against this brand's reads in the run. Caiman 0.3.56
    (FLAGS P350): with own, a read the run didn't list is taken when its name is a plain read name (OWN_READ_RE): the
    brand's own read."""
    read, sep, value = (raw or '').partition('=')
    read, value = read.strip(), value.strip()
    if not sep or not read or not value:
        raise WorkspaceError('Give each {} as "<read>=<{}>", for example "{}=<{}>".'.format(
            'report' if what == 'report id' else 'failed read', what, sorted(known)[0] if known else 'sp-campaigns-30-days',
            what))
    if read not in known and not (own and OWN_READ_RE.fullmatch(read)):
        raise WorkspaceError('"{}" isn\'t one of this brand\'s reads in this run{}. Its reads are: {}.'.format(
            one_line(read, 80), ', and it isn\'t a plain read name (letters, digits, dots, dashes and colons) to record '
            'as the brand\'s own' if own else '', ', '.join(sorted(known)) or 'none'))
    return read, value


def own_read(plan, read, ids, args, session, moment):
    """Caiman 0.3.56 (FLAGS P350): keep a read the run didn't list among the brand's own (plan.own_reads), with the tool
    it is polled with and, when given, the tool and arguments that ask for it again. Returns its record."""
    poll = text_value(getattr(args, 'poll_with', None)) or (
        'get_report_status' if ids and all(item.isdigit() for item in ids) else 'get_ads_report_status')
    record = {'read': read, 'own': True, 'poll_with': poll, 'added_at': moment, 'session': session}
    tool = text_value(getattr(args, 'tool', None))
    if tool:
        record['tool'] = tool
    raw = text_value(getattr(args, 'arguments', None))
    if raw:
        try:
            given = json.loads(raw)
        except ValueError:
            given = None
        if not isinstance(given, dict):
            raise WorkspaceError('--arguments takes the read\'s arguments as one JSON object, for example '
                                 '\'{"brand_slug": "<slug>", "start_date": "2026-11-01", "end_date": "2026-11-21"}\'. '
                                 'Nothing was recorded.')
        record['arguments'] = given
    listed = plan.setdefault('own_reads', [])
    for index, item in enumerate(listed):
        if isinstance(item, dict) and item.get('read') == read:
            listed[index] = dict(item, **record)
            return listed[index]
    listed.append(record)
    return record


def cmd_run_reports(args):
    """Record (or show) one brand's report IDs in an unfinished run of a report-heavy workflow."""
    root = workspace_root(args.workspace)
    path, data = find_run(root, args.run)
    if not data:
        raise WorkspaceError("There's no unfinished run across the brands to record reports in.")
    if data.get('status') != 'open':
        moved = carried_to(root, data, args.brand)    # Caiman 0.3.34: the run that picked the brand up
        if not moved:
            raise WorkspaceError('The run "{}" is already finished.'.format(data['name']))
        path, data = moved
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
        known = {read['read'] for read in list(plan['reads']) + list(plan.get('due_reads') or [])}   # due_reads: P324
        moment = stamp()
        requested = plan.setdefault('requested', {})
        own = []        # Caiman 0.3.56 (FLAGS P350): reads the run didn't list, recorded as the brand's own
        for raw in args.add or []:
            read, value = parse_read(raw, known, 'report id', own=True)
            ids = [part.strip() for part in value.split(',') if part.strip()]
            bad = [item for item in ids if not REPORT_ID_RE.fullmatch(item)]
            if bad or not ids:
                raise WorkspaceError('"{}" doesn\'t look like a report ID. Record the report_id the request returned, '
                                     'never a download link. Nothing was recorded.'.format(one_line(bad[0] if bad else value, 80)))
            if read in requested:
                plan.setdefault('replaced', []).append(dict(requested[read], read=read, replaced_at=moment))
            if read not in known:
                own.append(own_read(plan, read, ids, args, session, moment)['read'])
            requested[read] = {'report_ids': ids, 'requested_at': moment, 'session': session, 'status': 'requested',
                               'note': None}
        for raw in args.failed or []:
            read, value = parse_read(raw, known, 'what it said', own=True)
            if read not in known:
                own.append(own_read(plan, read, [], args, session, moment)['read'])
            if read in requested:
                plan.setdefault('replaced', []).append(dict(requested[read], read=read, replaced_at=moment))
            requested[read] = {'report_ids': [], 'requested_at': moment, 'session': session, 'status': 'failed',
                               'note': one_line(value, 300)}
        if held and session == held:
            entry.update(seen_at=moment, seen_by=session)       # Caiman 0.3.56 (FLAGS P324): its session is alive
        save_run(path, data)
    view = task_reports(root, data, entry, session)
    recorded_own = sorted(set(own)) if changes else []
    if view is None:
        message = "{} has no reports asked for ahead in this run.".format(entry['name'])
    else:
        message = '{}: {} of {} reports requested{}.'.format(
            entry['name'], len(view['requested']), len(view['requested']) + len(view['to_request']),
            '' if not view['to_request'] else '; still to request: ' + ', '.join(read['read'] for read in view['to_request']))
        if recorded_own:
            message += ' Recorded as this brand\'s own {} (the run didn\'t list {}): {}.'.format(
                'read' if len(recorded_own) == 1 else 'reads', 'it' if len(recorded_own) == 1 else 'them',
                ', '.join(recorded_own))
    return {'schema': RUN_SCHEMA, 'command': 'run reports', 'workspace': str(root), 'run': data['name'],
            'run_file': rel(root, path), 'brand': entry['id'], 'name': entry['name'], 'status': entry['status'],
            'reports': view, 'own_reads_recorded': recorded_own, 'member_message': message,
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
                    # Caiman 0.3.34: Caiman's own unfinished work: it stays to do and goes first in the new run.
                    leave_to_do(entry, "A new {}'s run started before I got to it; I'll pick it up first.".format(period),
                                text_value(getattr(args, 'session', None)))
            data.update(status='closed', finished_at=stamp(), closed_because="a new {}'s run started".format(period))
            save_run(path, data)
            closed.append(data['name'])
        elif not args.new and same_brands and same_kind and data.get('goal') == goal:
            return with_prefetch(root, data, next_answer(root, path, data, 'run start', {
                'resumed_run': True, 'note': 'An unfinished {} run from {} carries on at the next brand.'.format(
                    label, data['name'][:10])}, session=getattr(args, 'session', None)))
    # Caiman 0.3.34: brands an earlier run of this workflow was finished without go first, without asking.
    chosen, origin = carried_first(still_to_do(root, workflow, goal), chosen)
    path, data, flagged = create_run(root, workflow, chosen, brands, alerts, goal, bool(args.scheduled), plugin, origin,
                                     closed)
    extra = {'resumed_run': False}
    if closed:
        extra['note'] = 'Closed the unfinished run from earlier: {}.'.format(names(closed))
    if origin:
        extra.update(carried_over(origin))
        extra['note'] = ' '.join(part for part in (extra.get('note'), extra['carried_over']['words']) if part)
    if flagged:
        extra['alerts'] = flagged
    answer = next_answer(root, path, data, 'run start', extra, session=getattr(args, 'session', None))
    if flagged:
        answer['member_message'] += ' ' + ' '.join(alert['member_line'] for alert in flagged)
    return with_prefetch(root, data, answer)


def create_run(root, workflow, chosen, brands, alerts, goal, scheduled, plugin, origin=None, closed=(), continues=None):
    """Write a new run of this workflow for the chosen brands, in that order: (path, record, the brand-scope alerts it
    flags). origin: the brands it carries on from earlier runs (carried_first; Caiman 0.3.34), each marked picked up
    there; continues: the earlier run it was started to finish."""
    label, kind, first = WORKFLOWS[workflow]
    base = '{} {}'.format(now().date().isoformat(), workflow)
    name, number = base, 2
    while run_file(root, name).exists() or (root / RUNS / name).exists():
        name, number = '{} {}'.format(base, number), number + 1
    entries = []
    scope_flags = {alert['brands'][0]: alert for alert in brand_scope_alerts(brands)}
    flagged = []
    run_moment = now()
    previews_until = time.monotonic() + REFRESH_PREVIEW_BUDGET   # Caiman 0.3.28: the SQP previews' time, every brand
    for brand in chosen:
        entry = entry_for(brand)
        why = not_for_this_run(kind, brand, alerts)
        if why:
            entry.update(status='skipped', note=why, finished_at=stamp())
        elif brand['id'] in scope_flags:
            # Caiman 0.3.17: a VIP brand sharing its account with no brand scope saved is flagged in the run.
            entry['scope_alert'] = {key: scope_flags[brand['id']][key] for key in ('code', 'member_line', 'next_step')}
            flagged.append(scope_flags[brand['id']])
        if kind == 'suite' and not why:
            # Caiman 0.3.57 (FLAGS F147): the brand's steps today, and what the last suite left open
            entry['steps'] = suite_steps(root, brand, run_moment)
            left = left_open(root, brand)
            if left:
                entry['left_open'] = left
        if why:
            plan = None
        elif kind == 'suite':
            plan = suite_reports_plan(root, brand, run_moment, previews_until, entry['steps'])
        else:
            plan = reports_plan(workflow, brand, run_moment, root, previews_until)
        if plan:
            entry['reports'] = plan   # Caiman 0.3.17: this brand's reports, asked for before the first brand
        if origin and brand['id'] in origin:
            carry(entry, origin[brand['id']], run_moment)
        entries.append(entry)
    moment = stamp()
    data = {'schema': RUN_SCHEMA, 'name': name, 'workflow': workflow, 'workflow_name': label, 'kind': kind,
            'goal': goal, 'scheduled': bool(scheduled), 'status': 'open', 'started_at': moment, 'updated_at': moment,
            'finished_at': None, 'plugin_version': plugin, 'note_file': None, 'closed_runs': list(closed), 'brands': entries,
            'about': ("One {} across this workspace's brands, one brand at a time, each in its own business folder with "
                      "its own account. workspace.py run next carries on at the next brand; run finish writes the "
                      'combined note.').format(label)}
    if origin:
        data['carried_from'] = sorted({item[2]['name'] for item in origin.values()})
    if continues:
        data['continues'] = continues
    path = run_file(root, name)
    save_run(path, data)
    (root / RUNS / name).mkdir(parents=True, exist_ok=True)
    if origin:
        picked_up(origin, name, run_moment)
    return path, data, flagged


def carried_over(origin):
    """What a run start or run next answer says about the brands it carries on from earlier runs (Caiman 0.3.34)."""
    runs = {}
    for old, path, data in origin.values():
        runs[data['name']] = data
    who = [item[0]['name'] for item in origin.values()]
    dates = [plain_date(parse_time(data.get('started_at'))) if parse_time(data.get('started_at')) else name[:10]
             for name, data in sorted(runs.items())]
    return {'carried_over': {'brands': list(origin), 'names': who, 'from': sorted(runs), 'words': (
        "First {}, which {} of {} didn't get to.".format(names(who), run_words(next(iter(runs.values())), len(runs)),
                                                        names(dates)))}}


def carry_on(root, item, session, plugin, command='run next', also=(), brand=None):
    """A run of the same workflow for the brands an earlier run was finished without (still_to_do; Caiman 0.3.34),
    started now, with its first brand handed out: Caiman's own unfinished work, carried on without asking."""
    old = item['data']
    workflow = old['workflow']
    brands, skipped, alerts, saved = current_brands(root, plugin)
    folders = [entry.get('folder') for entry in item['entries']]
    chosen = [brand for folder in folders for brand in brands if brand['folder'] == folder]
    if not chosen:
        raise WorkspaceError("The brands {} ({}) left to do ({}) aren't in this workspace's folders any more (moved or "
                             'renamed?). Run init to refresh the brands, then start the run again.'.format(
                                 run_words(old), old['name'], names([entry['name'] for entry in item['entries']])))
    chosen, origin = carried_first([item], chosen)
    path, data, flagged = create_run(root, workflow, chosen, brands, alerts, old.get('goal'), False, plugin, origin,
                                     continues=old['name'])
    extra = {'resumed_run': False, 'continued_from': old['name']}
    extra.update(carried_over(origin))
    extra['note'] = extra['carried_over']['words']
    if also:
        extra['also_still_to_do'] = [{'run': other['data']['name'], 'workflow': other['data']['workflow'],
                                      'brands': [entry['name'] for entry in other['entries']]} for other in also]
    if flagged:
        extra['alerts'] = flagged
    answer = next_answer(root, path, data, command, extra, session=session, brand=brand)
    if flagged:
        answer['member_message'] += ' ' + ' '.join(alert['member_line'] for alert in flagged)
    return with_prefetch(root, data, answer)


def cmd_run_next(args):
    root = workspace_root(args.workspace)
    session = getattr(args, 'session', None)
    named = text_value(getattr(args, 'run', None))
    path, data = find_run(root, args.run)
    if data and named and data.get('status') != 'open' and not (getattr(args, 'take_over', None) or
                                                                 getattr(args, 'leave', None)):
        # Caiman 0.3.34: a finished run named, with brands still to do: carried on in a new run, first.
        item = next((item for item in still_to_do(root, data['workflow'], data.get('goal'))
                     if item['data']['name'] == data['name']), None) if data.get('workflow') in WORKFLOWS else None
        if item:
            return carry_on(root, item, session, plugin_version(args.plugin_version), brand=getattr(args, 'brand', None))
        # Caiman 0.3.34: its brands were picked up by a run still open: "next" carries on there, not here again.
        later = next((carried_to(root, data, entry['id']) for entry in data['brands'] if picked_up_by(entry)
                      and carried_to(root, data, entry['id'])), None)
        if later:
            path, data = later
    if not data:
        # Caiman 0.3.34: no unfinished run, but brands a current run was finished without: carried on first.
        items = still_to_do(root, current_only=True)
        if items:
            return carry_on(root, items[0], session, plugin_version(args.plugin_version), also=items[1:],
                            brand=getattr(args, 'brand', None))
        recent = [item.get('name') for path, item in all_runs(root)][:5]
        return {'schema': RUN_SCHEMA, 'command': 'run next', 'workspace': str(root), 'status': 'no-open-run',
                'recent_runs': recent, 'member_message': "There's no unfinished run across your brands.",
                'how_to_continue': 'Start one with run start <workflow> when the member asks for work across brands.'}
    others = [item.get('name') for item_path, item in open_runs(root) if item.get('name') != data['name']]
    return next_answer(root, path, data, 'run next', {'other_open_runs': others} if others else None,
                       session=session, take_over_brand=getattr(args, 'take_over', None),
                       leave=getattr(args, 'leave', None) or (), brand=getattr(args, 'brand', None))


def match_entry(entries, wanted):
    hits = brand_hits(entries, wanted)
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


def summary_source(root, data, entry, given, earlier=None):
    """(path, text) of the brand's summary file, or (None, None) when none was given and the usual one isn't there.
    earlier: the run this brand was carried from (Caiman 0.3.34), whose usual summary file for it is its own too."""
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
    if earlier and candidate == Path(os.path.abspath(str(brand_summary_file(root, earlier, entry['id'])))):
        own = candidate
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


# ---------------------------------------------------------------- each brand's handoff, and the combined one (0.3.34)

# Caiman 0.3.34: every workflow ends with one handoff: Done, Your go (the account changes waiting for the member's go),
# I need from you (facts only the member has, each with the default used meanwhile) and Next (what Caiman does next).
# Claude saves each brand's beside its summary as JSON (task.handoff_file; the workspace guide, "The combined handoff"):
#   {"done": "<one line>", "go": [{"change": "<one line>", "ref": "<its proposal or line>"}],
#    "need": [{"ask": "<one fact>", "default": "<what is used meanwhile>"}], "next": "<one line>"}
# A part may be left out; a go or need item may be a plain string. run finish puts them together at the end of the
# combined note, the go lines numbered across the brands so "go 1 3" works.
HANDOFF_SUFFIX = '.handoff.json'


def handoff_beside(summary):
    """The handoff file beside a brand's summary file: <its name without .md>.handoff.json."""
    summary = Path(summary)
    stem = summary.name[:-3] if summary.name.lower().endswith('.md') else summary.name
    return summary.with_name(stem + HANDOFF_SUFFIX)


def clean_handoff(value):
    """(the handoff as the combined note uses it, what in it couldn't be used): done and next as one line each, go items
    as {change, ref?}, need items as {ask, default?}; empty parts left out."""
    if not isinstance(value, dict):
        return {}, ["it isn't a JSON object with done, go, need and next"]
    out, problems = {}, []
    for key in ('done', 'next'):
        if value.get(key) not in (None, '') and not text_value(value.get(key)):
            problems.append('{} isn\'t one line of text'.format(key))
        elif text_value(value.get(key)):
            out[key] = one_line(text_value(value.get(key)), 600)
    for key, main, other, also in (('go', 'change', 'ref', None), ('need', 'ask', 'default', 'meanwhile')):
        raw = value.get(key)
        if raw in (None, '', []):
            continue
        items = []
        for item in raw if isinstance(raw, list) else [raw]:
            if isinstance(item, str):
                item = {main: item}
            text = text_value(item.get(main)) if isinstance(item, dict) else None
            if not text:
                problems.append('a {} item has no {}'.format(key, main))
                continue
            clean = {main: one_line(text, 600)}
            extra = text_value(item.get(other)) or (text_value(item.get(also)) if also else None)
            if extra:
                clean[other] = one_line(extra, 300)
            items.append(clean)
        if items:
            out[key] = items
    return out, problems


def read_handoff(path):
    """(handoff, problems, its text) from a brand's handoff file; ({}, [], '') when there is none."""
    if not path or not Path(path).is_file():
        return {}, [], ''
    text = read_text(path, 2 * 1024 * 1024) or ''
    try:
        value = json.loads(text.lstrip('﻿'))
    except ValueError as error:
        return {}, ["it isn't readable JSON ({})".format(error)], text
    handoff, problems = clean_handoff(value)
    return handoff, problems, text


def handoff_candidates(root, data, entry, earlier=None):
    """Where a brand's handoff may be, in order: this run's own file for it (task.handoff_file, where the task says to
    save it), the earlier run's own file when the brand is recorded through the run that picked it up (earlier), and the
    file beside the summary run done was given, when that summary is elsewhere (in the brand's own folder)."""
    found = [handoff_beside(brand_summary_file(root, data['name'], entry['id']))]
    if earlier:
        found.append(handoff_beside(brand_summary_file(root, earlier, entry['id'])))
    if entry.get('summary_file'):
        found.append(handoff_beside(root.joinpath(*entry['summary_file'].split('/'))))
    return [path for index, path in enumerate(found) if path not in found[:index]]


def handoff_path(root, data, entry, earlier=None):
    """Where a recorded brand's handoff is: the file run done found it in (handoff_file), else the first of its
    candidates that is there, else this run's own file for it (Caiman 0.3.34: task.handoff_file is read as well as the
    file beside a summary given from elsewhere)."""
    kept = text_value(entry.get('handoff_file'))
    if kept and root.joinpath(*kept.split('/')).is_file():
        return root.joinpath(*kept.split('/'))
    candidates = handoff_candidates(root, data, entry, earlier)
    return next((path for path in candidates if path.is_file()), candidates[0])


def no_handoff_warning(entry):
    """What a done brand with no handoff found is warned with (Caiman 0.3.34), as for a missing summary."""
    return ("No handoff was saved for {}; the combined handoff will have only its one-line note, with no change for "
            "the member's go and no answer it needs.".format(entry['name']))


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


def carried_to(root, data, wanted):
    """(path, record) of the open run that picked up this finished run's brand (Caiman 0.3.34: picked_up_in) and has no
    result for it yet, so a session still working on it from the earlier run records it there; else None."""
    try:
        entry = match_entry(data['brands'], wanted)
    except WorkspaceError:
        return None
    name = text_value(entry.get('picked_up_in'))
    later = read_run(run_file(root, name)) if name else None
    if later and later.get('status') == 'open' and any(
            item.get('folder') == entry.get('folder') and item['status'] in ('pending', 'in-progress')
            for item in later['brands']):
        return run_file(root, name), later
    return None


LEDGER_OUTCOMES = {'done': 'done', 'skipped': 'skipped', 'failed': 'failed', 'needs-answer': 'partial'}


def close_brand_run(root, entry, data, status):
    """Caiman 0.3.42 (R1): a brand's result closes its run in that brand's run ledger (its kit's RUN_LEDGER.py), so its
    watchdog never reports the brand's part of an all-brands run as stalled. Never stops the run."""
    try:
        folder = brand_folder(root, entry)
        program = guide_folder(folder) / 'RUN_LEDGER.py'
        outcome = LEDGER_OUTCOMES.get(status)
        if not outcome or not program.is_file():
            return None
        argv = [python(), '-B', str(program), 'finish', '--project-root', str(folder), '--workflow',
                str(data.get('workflow') or 'request'), '--outcome', outcome,
                '--note', 'Recorded by the all-brands run ' + str(data.get('name') or '')]
        return run_program(argv, folder, 30)
    except Exception:
        return None


def cmd_run_done(args):
    root = workspace_root(args.workspace)
    path, data = find_run(root, args.run)
    if not data:
        raise WorkspaceError("There's no unfinished run across the brands to record that in. Start one with run start.")
    earlier = None
    if data.get('status') != 'open':
        moved = carried_to(root, data, args.brand)
        if not moved:
            raise WorkspaceError('The run "{}" is already finished.'.format(data['name']))
        earlier, (path, data) = data['name'], moved
    entry = match_entry(data['brands'], args.brand)
    summary, text = summary_source(root, data, entry, args.summary, earlier)
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
    # Caiman 0.3.34: the brand's handoff, for the combined handoff: in its task's handoff_file, or beside the summary
    # given when that is elsewhere (handoff_candidates), looked for afresh each time the brand is recorded.
    candidates = handoff_candidates(root, data, entry, earlier)
    found = next((path for path in candidates if path.is_file()), None)
    handoff, problems, handoff_text = read_handoff(found)
    if found:
        entry['handoff_file'] = rel(root, found)
    else:
        entry.pop('handoff_file', None)
    if handoff:
        entry['handoff'] = handoff
    else:
        entry.pop('handoff', None)
    checked = '\n'.join(part for part in (text, handoff_text) if part)
    warnings = mixed_accounts(checked, entry, data['brands']) if checked else []
    if args.status == 'done' and not summary:
        warnings.append("No summary file was saved for {}; the combined note will have only its one-line note.".format(
            entry['name']))
    if args.status == 'done' and not found:
        warnings.append(no_handoff_warning(entry))
    if other_session:
        warnings.append(other_session)
    entry['warnings'] = warnings
    save_run(path, data)
    close_brand_run(root, entry, data, args.status)
    left = [item for item in data['brands'] if item['status'] in ('pending', 'in-progress')]
    label = data.get('workflow_name') or data['workflow']
    message = '{}: {} recorded as {}.'.format(label, entry['name'], STATUS_WORDS.get(args.status, args.status).lower())
    if earlier:
        message += ' It was recorded in the run that picked it up ({}), as {} was finished.'.format(data['name'], earlier)
    message += ' Next: {}.'.format(left[0]['name']) if left else ' Every brand has a result; next is the combined note.'
    answer = {'schema': RUN_SCHEMA, 'command': 'run done', 'workspace': str(root), 'run': data['name'],
              'run_file': rel(root, path), 'recorded': {'brand': entry['id'], 'name': entry['name'], 'status': args.status,
                                                        'note': entry.get('note'), 'summary_file': entry['summary_file'],
                                                        'handoff': {'go': len(handoff.get('go') or []),
                                                                    'need': len(handoff.get('need') or [])}
                                                        if handoff else None,
                                                        'handoff_file': entry.get('handoff_file')},
              'warnings': warnings, 'next_brand': left[0]['id'] if left else None, 'progress': progress(data),
              'member_message': message,
              'how_to_continue': ('Run next for the next brand.' if left else 'Run finish for the combined note.') + (
                  ' Check the warnings first.' if warnings else '')}
    if problems:
        answer['handoff_problems'] = problems
        answer['how_to_continue'] = ("Its handoff file ({}) couldn't be used in full: {}. Save it again as the task's rules "
                                     'say, then record this brand again with the same command. '.format(
                                         rel(root, handoff_path(root, data, entry)), '; '.join(problems))
                                     + answer['how_to_continue'])
    elif args.status == 'done' and not found:
        # Caiman 0.3.34: said to Claude, so a brand's go lines never drop out of the combined handoff unseen.
        answer['handoff_missing'] = rel(root, candidates[0])
        answer['how_to_continue'] = ("No handoff was found for {}: save it at {} as the task's rules say (its done "
                                     "line, each change waiting for the member's go, each answer it needs, its next), "
                                     'then record this brand again with the same command. '.format(
                                         entry['name'], rel(root, candidates[0])) + answer['how_to_continue'])
    return answer


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
    answer = {'schema': RUN_SCHEMA, 'command': 'run status', 'workspace': str(root), 'run': data['name'],
              'run_file': rel(root, path), 'status': data.get('status'), 'progress': progress(data),
              'table_markdown': progress_table(data), 'runs': runs, 'member_message': message}
    if isinstance(data.get('handoff'), dict):
        answer['handoff'] = data['handoff']   # Caiman 0.3.34: a finished run's numbered go lines, for "go 1 3" later
    return answer


def demoted(text):
    """A brand's summary inside the combined note: its headings sit below the brand's own heading."""
    lines = []
    for line in (text or '').strip().splitlines():
        if re.match(r'^\s{0,3}#{1,6}\s', line):
            line = '#### ' + line.strip().lstrip('#').strip()
        lines.append(line.rstrip())
    return '\n'.join(lines)


def sentence(text):
    """text as a sentence: its first letter capital and a full stop at the end, unless it has one."""
    text = ' '.join(str(text or '').split())
    if not text:
        return ''
    text = text[:1].upper() + text[1:]
    return text if text[-1] in '.!?)' else text + '.'


def done_line(entry, own, label):
    """One line for a brand under Done: what was done, or its result in plain words (Caiman 0.3.34)."""
    status, note = entry['status'], one_line(entry.get('note') or '', 400)
    if status == 'done':
        return sentence(own.get('done') or note or 'Done')
    if status == 'not-run' and picked_up_by(entry):
        return "Picked up in the run {}: its result is in that run's note.".format(picked_up_by(entry))
    if status == 'not-run':
        return "Not done yet: I'll pick it up next."
    if status == 'needs-answer':
        return sentence(own.get('done') or 'Waiting on your answer, below')
    reason = own.get('done') or note
    words = STATUS_WORDS.get(status, status)
    return sentence('{}: {}'.format(words, reason) if reason else words)


def reply_line(count):
    """How the member answers the numbered go lines (Caiman 0.3.34), in the words every handoff uses (the
    human-output-standard skill); with fewer than 3 lines, only numbers that are there."""
    if count == 1:
        return 'Reply go to make it, or no to skip it. Nothing changes until you reply.'
    return 'Reply go to make all of them, {} for some, or no 2 to skip one. Nothing changes until you reply.'.format(
        'go 1 3' if count >= 3 else 'go 1')


# A brand's own next step a run starts by itself where the report puller is on (Caiman 0.3.57, FLAGS F148): read-only work (a read, a pull,
# a build, a check, a review) that names no date, no person to wait on and no account change. The release review and its
# fresh read: "Read the first week on Dec 1", "the bid cut waits for your go", "Measure the coupon Dec 3", "Close the VIP
# week Monday", "After David answers ...", "Apply the 6 bid cuts in the go list" were each said as "I'm starting it now".
READ_ONLY_STEP = re.compile(r"^\s*(?:[A-Z][\w+&.' -]{0,40}:\s*)?(?:read|pull|refresh|collect|save|build|rebuild|check|review|"
                            r"look|measure|finish|run (?:the )?(?:daily check|numbers|money|setup|weekly refresh|master sheet|"
                            r"dashboard|plan)|update the (?:plan|dashboard|master sheet|sheet))\b", re.I)
WAITS = re.compile(r"\b(?:wait|waits|waiting|due|until|tomorrow|tonight|next week)\b|\byour go\b|\bthe member'?s? go\b|"
                   r"\b(?:once|when|after) (?:you|the member|they|he|she)\b|\bin \d+ days?\b|"
                   r"\b(?:mon|tues|wednes|thurs|fri|satur|sun)day\b|"
                   r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.? \d{1,2}\b|\b\d{1,2}/\d{1,2}\b", re.I)
WAITS_ON = re.compile(r"\b(?:[Aa]fter|[Oo]nce|[Ww]hen|[Uu]ntil) [A-Z][a-z]+\b|"
                      r"\b[A-Z][a-z]+ (?:answers|answered|approves|approved|says|said|replies|confirms|decides|sends)\b")
ACCOUNT_CHANGE = re.compile(r"\b(?:apply|applies|raise|raises|lower|lowers|cut|cuts|pause|pauses|enable|enables|launch|"
                            r"launches|create|creates|change|changes|increase|decrease|send|sends|publish|post|delete|archive|"
                            r"go list|go lines?)\b", re.I)


def step_waits(words):
    """Whether a brand's own next step waits on a date, a person or a go (it names one, or an account change)."""
    return bool(WAITS.search(words) or WAITS_ON.search(words) or ACCOUNT_CHANGE.search(words))


def handoff_next(root, data, own_next, session=None):
    """handoff_next_words for the run (Caiman 0.3.34). Where the report puller is on (Caiman 0.3.57, FLAGS F148) Caiman's own
    read-only work is started, not offered: do_now, and its words say it is starting. A brand's own next step that waits
    on a date, a person or a go is never started: it stays in Next (do_now false, waits); one that is neither read-only
    nor waiting is offered as before; read-only steps go first."""
    operator = report_puller_of(root)
    if operator and own_next:
        rank = lambda item: 2 if step_waits(item[1]) else 0 if READ_ONLY_STEP.search(item[1]) else 1   # noqa: E731
        own_next = sorted(own_next, key=rank)
    found = handoff_next_words(root, data, own_next, session)
    if operator:
        if found.get('starts') == 'brand' and own_next and step_waits(own_next[0][1]):
            found['words'] = found['words'].replace(' Say next to start it.', ' It waits, so it stays in Next.')
            found.update(do_now=False, waits=True)
        elif found.get('starts') == 'brand' and own_next and not READ_ONLY_STEP.search(own_next[0][1]):
            found['do_now'] = False            # not plainly read-only: offered, as in a member's own workspace
        else:
            found['words'] = found['words'].replace(' Say next to start it.', " I'm starting it now.")
            found['do_now'] = True
    return found


def handoff_next_words(root, data, own_next, session=None):
    """What Caiman does next after this run, and what starts it (Caiman 0.3.34): the brands it didn't get to (not those
    a later run picked up), else other unfinished work in the workspace (not a run another session is working through),
    else the brands' own next steps, else the plan across the brands. starts says which: a run (run next --run <run>),
    a brand's own step (in its folder) or the plan."""
    me = str(Path(__file__).resolve())
    still = [entry for entry in data['brands'] if entry['status'] == 'not-run' and not picked_up_by(entry)]
    if still:
        return {'words': "I'll do {} for {}, which this run didn't get to. Say next to start it.".format(
                    work_words(data), names([entry['name'] for entry in still])),
                'command': command_line([me, 'run', 'next', '--workspace', str(root), '--run', data['name']]),
                'brands': [entry['id'] for entry in still], 'starts': 'run', 'run': data['name']}
    other = next((step for step in unfinished_steps(root, session=session) if step['run'] != data['name']), None)
    if other:
        return {'words': "I'll finish {}, {}. Say next to start it.".format(other['work'], (
                    'which stopped partway' if other['kind'] == 'unfinished-run' else
                    "which the run of {} didn't get to".format(run_day_words(other['run'])))),
                'command': other['agent_command'], 'brands': other['brands'], 'starts': 'run', 'run': other['run']}
    if own_next:
        entry, words = own_next[0]
        later = '; '.join('{}: {}'.format(item[0]['name'], item[1].rstrip('.')) for item in own_next[1:3])
        return {'words': '{}: {}{} Say next to start it.'.format(entry['name'], sentence(words),
                                                               ' Then {}.'.format(later) if later else ''),
                'command': None, 'brands': [entry['id']], 'folder': entry['folder'], 'starts': 'brand'}
    return {'words': "I'll work out what's next across your brands and start on the first step. Say next to start it.",
            'command': command_line([me, 'plan', '--workspace', str(root)]), 'brands': [], 'starts': 'plan'}


def combined_handoff(root, data, session=None):
    """The run's one handoff (Caiman 0.3.34), from each brand's own (its handoff file, else the copy run done kept) and
    its result: done (a line for each brand, with anything to check), go (the account changes waiting for the member's
    go, numbered across the brands), need (facts only the member has, each with the default used meanwhile, and a brand
    scope still to save), next (what Caiman does next, and the command that starts it) and reply (how to answer)."""
    label = data.get('workflow_name') or data['workflow']
    its = 'your request' if is_request(data) else 'its ' + label
    done, go, need, own_next = [], [], [], []
    for entry in data['brands']:
        own = {}
        if entry['status'] != 'not-run':      # a brand still to do has no result yet: its work is picked up later
            own = read_handoff(handoff_path(root, data, entry))[0] or as_dict(entry.get('handoff'))
        done.append({'brand': entry['id'], 'name': entry['name'], 'status': entry['status'],
                     'line': done_line(entry, own, label), 'checks': list(entry.get('warnings') or [])})
        for item in own.get('go') or []:
            line = {'number': len(go) + 1, 'brand': entry['id'], 'name': entry['name'], 'folder': entry['folder'],
                    'change': sentence(item['change'])}
            if item.get('ref'):
                line['ref'] = item['ref']
            go.append(line)
        asks = list(own.get('need') or [])
        if entry['status'] == 'needs-answer' and not asks:
            asks.append({'ask': entry.get('note') or 'Your answer, so I can finish {}.'.format(its),
                         'default': '{} waits for your answer'.format(its)})
        scope = scope_alert_now(root, entry)
        if scope:
            asks.append({'ask': scope['member_line']})
        for item in asks:
            need.append(dict({'brand': entry['id'], 'name': entry['name'], 'folder': entry['folder'],
                              'ask': sentence(item['ask'])}, **({'default': item['default']} if item.get('default') else {})))
        if own.get('next'):
            own_next.append((entry, own['next']))
    return {'done': done, 'go': go, 'need': need, 'next': handoff_next(root, data, own_next, session),
            'reply': reply_line(len(go)) if go else None}


def handoff_lines(handoff):
    """The handoff at the end of the combined note: Done, Your go, I need from you and Next, each left out when empty."""
    lines = ['## Handoff', '']
    if handoff['done']:
        lines += ['**Done**', '']
        for item in handoff['done']:
            lines.append('- **{}**: {}'.format(item['name'], item['line']))
            lines += ['  - To check: {}'.format(check) for check in item.get('checks') or []]
        lines.append('')
    if handoff['go']:
        lines += ['**Your go**', '']
        lines += ['{}. **{}**: {}'.format(item['number'], item['name'], item['change']) for item in handoff['go']]
        lines += ['', handoff['reply'], '']
    if handoff['need']:
        lines += ['**I need from you**', '']
        lines += ['- **{}**: {}{}'.format(item['name'], item['ask'], ' Meanwhile: {}'.format(sentence(item['default']))
                                          if item.get('default') else '') for item in handoff['need']]
        lines.append('')
    if (handoff.get('next') or {}).get('words'):
        lines += ['**Next**', '', handoff['next']['words'], '']
    return lines


def run_note(root, data, moment, handoff=None):
    """The run's combined note. With its handoff (run finish, Caiman 0.3.34): the brands' results, the brands Caiman
    didn't get to under its own heading, each brand's summary, and the handoff at the end. Without (a kit update's
    record): the results, what needs the member, and each brand's summary, as before."""
    label = data.get('workflow_name') or data['workflow']
    started = parse_time(data.get('started_at'))
    lines = ['# {}: all brands, {}'.format(label, plain_date(moment)), '',
             '{}. Started {}, finished {}.{}'.format(
                 plural(len(data['brands']), 'brand'), plain_time(started) if started else 'earlier', plain_time(moment),
                 ' A scheduled run: nothing in any Amazon account was changed.' if data.get('scheduled') else ''), '']
    if _PAGE.get('note'):
        lines[-2] += ' ' + _PAGE['note']
    carried = [entry['name'] for entry in data['brands'] if text_value(entry.get('carried_from'))]
    if handoff is not None and carried:
        lines += ["{} came first: the run of {} didn't get to {}.".format(
            names(carried), names(sorted({run_day_words(entry['carried_from']) for entry in data['brands']
                                          if text_value(entry.get('carried_from'))})), 'it' if len(carried) == 1 else
            'them'), '']
    if data.get('goal'):
        lines += ['The request: "{}"'.format(data['goal']), '']
    lines += [progress_table(data, still_words=handoff is not None), '']
    if handoff is not None:
        # A brand a later run picked up is handled there (Caiman 0.3.34): finishing this run again never puts it back.
        still = [entry for entry in data['brands'] if entry['status'] == 'not-run' and not picked_up_by(entry)]
        if still:
            lines += ["## Still to do: I'll pick these up next", '']
            lines += ['- **{}**: {}'.format(entry['name'], sentence(entry.get('note') or "I haven't got to it yet"))
                      for entry in still]
            lines.append('')
    else:
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
                  '_{}{}_'.format(result_words(entry, handoff is not None),
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
    if data.get('workflow') == 'advertising-daily-check':
        # Caiman 0.3.55: was all of it done, brand by brand. The Advertising Daily Check's runs only: the other daily
        # workflows (the VIP daily brief, the health check, the setup check) make no list of reads, and their notes
        # read "0 of 2 Daily Checks are complete" for brands checked complete that morning (the fresh read, Nov 19).
        lines += daily_check_lines(root, data)
    if handoff is not None:
        lines += handoff_lines(handoff)   # Caiman 0.3.34: the note ends with one handoff
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
    session = text_value(getattr(args, 'session', None))
    for entry in left:
        # Caiman 0.3.34: Caiman's own unfinished work, not the member's: it stays to do, and the next run start of this
        # workflow, run next or plan carries it on first.
        leave_to_do(entry, "I didn't get to it before the run was finished; I'll pick it up next.", session)
    for entry in data['brands']:
        # A summary file (or, Caiman 0.3.34, a handoff file) written over after its brand was recorded is checked again
        # before it goes in the note.
        given = read_handoff(handoff_path(root, data, entry))[2] if entry['status'] != 'not-run' else ''
        texts = [read_text(root.joinpath(*entry['summary_file'].split('/')), 2 * 1024 * 1024) or ''
                 if entry.get('summary_file') else '', given]
        text = '\n'.join(part for part in texts if part)
        if given and no_handoff_warning(entry) in (entry.get('warnings') or []):
            # Caiman 0.3.34: saved since the brand was recorded: it's in the handoff now.
            entry['warnings'] = [line for line in entry['warnings'] if line != no_handoff_warning(entry)]
        if text:
            fresh = [line for line in mixed_accounts(text, entry, data['brands'])
                     if line not in (entry.get('warnings') or [])]
            entry['warnings'] = (entry.get('warnings') or []) + fresh
    moment = now()
    handoff = combined_handoff(root, data, session)
    note_path = run_note_file(root, data['name'])
    write_atomic(note_path, run_note(root, data, moment, handoff).encode('utf-8'))
    # Caiman 0.3.34: the record keeps the handoff for a later session ("go 1 3" there, run status) without next.command,
    # which holds this session's paths: next.starts and next.run say what starts it.
    kept = dict(handoff, next=dict((key, value) for key, value in handoff['next'].items() if key != 'command'))
    data.update(status='finished', finished_at=stamp(moment), note_file=rel(root, note_path), handoff=kept)
    save_run(path, data)
    counts = progress(data)['counts']
    label = data.get('workflow_name') or data['workflow']
    message = '{} finished for {} of {} brands.'.format(label, counts.get('done', 0), len(data['brands']))
    if handoff['go']:
        message += ' {} for your go ({}).'.format(plural(len(handoff['go']), 'change waits', 'changes wait'),
                                                 names(unique(item['name'] for item in handoff['go'])))
    if handoff['need']:
        message += ' I need {} from you ({}).'.format(plural(len(handoff['need']), 'answer'),
                                                     names(unique(item['name'] for item in handoff['need'])))
    failed = [entry for entry in data['brands'] if entry['status'] == 'failed']
    if failed:
        message += " Didn't finish: {}.".format('; '.join('{}{}'.format(
            entry['name'], ' ({})'.format(one_line(entry['note'], 140).rstrip('.')) if entry.get('note') else '')
            for entry in failed))
    still = [entry for entry in data['brands'] if entry['status'] == 'not-run' and not picked_up_by(entry)]
    if still:
        message += " Still to do: {}; I'll pick {} up next.".format(names([entry['name'] for entry in still]),
                                                                    'it' if len(still) == 1 else 'them')
    picked = {}
    for entry in data['brands']:
        if picked_up_by(entry):
            picked.setdefault(picked_up_by(entry), []).append(entry['name'])
    for later, who in sorted(picked.items()):
        message += ' Picked up in the run {}: {}.'.format(later, names(who))   # Caiman 0.3.34: handled there
    skipped = [entry['name'] for entry in data['brands'] if entry['status'] == 'skipped']
    if skipped:
        message += ' Skipped: {}.'.format(names(skipped))
    answer = {'schema': RUN_SCHEMA, 'command': 'run finish', 'workspace': str(root), 'run': data['name'],
              'run_file': rel(root, path), 'note_file': rel(root, note_path), 'progress': progress(data),
              'handoff': handoff, 'member_message': message,
              'how_to_continue': (
                  'Give the member the handoff at the end of the combined note ({}) in its own words: Done, then Your go '
                  'with its numbers and reply line, then I need from you, then Next. Nothing changes until they reply: '
                  'go makes every numbered change, go 1 3 only those, no 2 skips that one. Make each change they '
                  'approve in its own brand\'s folder with its own account (the brand on its line, handoff.go), check it '
                  'landed and record it there as that brand\'s kit says. go only approves; next only starts Next '
                  "(handoff.next: its command, or that brand's step in its own folder).{}").format(
                  rel(root, note_path), ' This was a scheduled run: it changed nothing, and its go lines wait for the '
                                        "member's reply in a conversation." if data.get('scheduled') else '')}
    puller = report_puller_of(root)
    if puller and not data.get('scheduled'):
        # Caiman 0.3.57 (FLAGS F148): with the report puller on, Next holds only what waits on a date, a person or a go
        answer['report_puller'] = puller
        answer['how_to_continue'] += (' ' + puller['words'] + ' handoff.next is Caiman\'s own work (do_now): say it is '
                                      'starting and start it right after the handoff (its command, or that brand\'s step in '
                                      'its own folder).')
    if still:
        answer['still_to_do'] = [{'brand': entry['id'], 'name': entry['name']} for entry in still]
    # Caiman 0.3.57 (FLAGS F149; ours, Nov 23: WORKSPACE PLAN.md was last built Oct 16 and still listed 20 "waiting on you"
    # items from Oct 7 to 15): the plan across the brands is rebuilt by the run that changed it
    answer['plan'] = rebuild_plan(root, session, getattr(args, 'plugin_version', None))
    # Caiman 0.3.58 (FLAGS F158): the one page of work in flight, written again by the run that changed it
    answer['work_in_flight'] = write_flight(root, 'run finish', session, getattr(args, 'plugin_version', None))
    if data['workflow'] in ('advertising-daily-check', 'suite'):
        # Caiman 0.3.55 (FLAGS F125): each brand's check built its own page; one command puts them together
        pages = dashboard_after_run(root, data)
        if pages:
            answer['dashboard'] = pages
            answer['how_to_continue'] = pages['words'] + ' Then: ' + answer['how_to_continue']
    return answer


PLAN_AT_FINISH_SECONDS = 90         # each brand's NEXT_STEP.py, when a run's finish rebuilds the plan


def rebuild_plan(root, session=None, plugin=None):
    """WORKSPACE PLAN.md and .json rebuilt from every brand's NEXT_STEP.py, as plan does (Caiman 0.3.57, FLAGS F149): run
    finish calls it, so the plan across the brands is never older than the last run. {'file', 'steps', 'waiting',
    'not_planned'}, or {'problem'} when it couldn't be rebuilt (the run is finished either way)."""
    import argparse as _argparse
    try:
        result = cmd_plan(_argparse.Namespace(workspace=str(root), plugin_version=plugin, brands=None,
                                              timeout=PLAN_AT_FINISH_SECONDS, per_brand=3, session=session))
    except Exception as error:      # the run is finished whatever happens here
        return {'problem': "WORKSPACE PLAN.md couldn't be rebuilt ({}): run plan.".format(one_line(error, 200))}
    return {'file': PLAN_MD, 'steps': len(result.get('steps') or []), 'waiting': len(result.get('waiting_on_member') or []),
            'not_planned': [item.get('brand_name') for item in result.get('not_planned') or []],
            'words': '{} rebuilt: {}, {} waiting on the member.'.format(
                PLAN_MD, plural(len(result.get('steps') or []), 'step'), len(result.get('waiting_on_member') or []))}


# ---------------------------------------------------------------- the work in flight: one page across the brands

def due_day(text):
    """A dated to-do's day (2026-12-08, Dec 8, 2026, 8 Dec 2026), as STOP_LINES.py reads it; None when it can't be read."""
    text = re.sub(r'[*_]', '', str(text or '')).strip().rstrip(',').strip()
    try:
        found = re.fullmatch(r'(\d{4})-(\d{2})-(\d{2})', text)
        if found:
            return dt.date(int(found.group(1)), int(found.group(2)), int(found.group(3)))
        months = {name[:3].lower(): number for number, name in enumerate(MONTHS, 1)}
        found = re.fullmatch(r'([A-Za-z]{3,9})\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})', text)
        if found and found.group(1)[:3].lower() in months:
            return dt.date(int(found.group(3)), months[found.group(1)[:3].lower()], int(found.group(2)))
        found = re.fullmatch(r'(\d{1,2})\s+([A-Za-z]{3,9})\.?,?\s+(\d{4})', text)
        if found and found.group(2)[:3].lower() in months:
            return dt.date(int(found.group(3)), months[found.group(2)[:3].lower()], int(found.group(1)))
    except ValueError:
        return None
    return None


def rules_text(path):
    """A rules file's own lines (Caiman's block left out), or [] when it isn't there."""
    text = read_text(path, 2 * 1024 * 1024) or ''
    return BLOCK.sub('', text).splitlines()


def brands_due(root, brands, today):
    """Each brand's dated to-dos that are due, late or due within FLIGHT_DUE_SOON_DAYS, from its own rules (a line "DUE
    <date>: <what>" in its CLIENT_RULES.md, which is where a to-do with a date lives): [{name, day, what, late}]."""
    found = []
    for brand in brands:
        for line in rules_text(brand_folder(root, brand) / 'CLIENT_RULES.md'):
            match = DUE_LINE.match(line)
            day = due_day(match.group(1)) if match else None
            if day is None or (day - today).days > FLIGHT_DUE_SOON_DAYS:
                continue
            found.append({'name': brand['name'], 'day': day, 'late': day < today,
                          'what': one_line(re.sub(r'[*_]+\s*$', '', match.group(2)).strip(), 200)})
    return sorted(found, key=lambda item: (item['day'], item['name']))


def last_rules(root):
    """The newest lines of the workspace's rules file (where a file grows: from the bottom up), at most FLIGHT_RULES."""
    if not RULES_FILE:
        return [], 0
    lines = []
    for raw in rules_text(root / RULES_FILE):
        line = raw.strip()
        if (not line or line.startswith(('#', '<!--')) or re.fullmatch(r'\*\(.*\)\*', line)
                or line.startswith("The owner's rules for every brand in this workspace") or DUE_LINE.match(line)):
            continue
        lines.append(one_line(re.sub(r'^(?:[-*+]|\d{1,3}[.)])\s+', '', line), 260))
    return list(reversed(lines))[:FLIGHT_RULES], len(lines)


def write_flight(root, why, session=None, plugin=None):
    """Caiman 0.3.58 (FLAGS F158; F123: what is next was said in six places): the workspace's one page of work in flight,
    FLIGHT_FILE, written whole from the run records, the brands' own dated to-dos and the workspace's rules: the open
    runs with how each is carried on, what waits on the owner (the changes that wait for a go and the facts only the
    owner has, from the runs finished in the last FLIGHT_RECENT_DAYS days, and each brand's DUE lines), what Caiman does
    next, and the last rules said. It is a view, not a second home: nothing typed into it is kept, and a to-do with a
    date stays in its brand's rules. Every path in it starts at the workspace's folder. why: 'run finish' or 'handoff'.
    Returns {'file', 'open_runs', 'waiting_on_owner', 'due', 'words'}, or {'problem'} when it couldn't be written."""
    if not FLIGHT_FILE:
        return {'problem': "The work-in-flight page wasn't written: this skill's setup_check.py couldn't be loaded."}
    try:
        runs = all_runs(root)
        # the brands first: reading them sets the zone the page's times are in (FLAGS P372). The release review: on a
        # computer whose clock is UTC, handoff wrote the page's days by that clock under "Times here are in Mountain time"
        try:
            brands = current_brands(root, plugin_version(plugin))[0]
        except Exception:
            brands = []
        moment = now()
        today = moment.date()
        me = str(Path(__file__).resolve())
        lines_open, lines_wait, lines_next = [], [], []
        open_now = [(path, data) for path, data in runs if data.get('status') == 'open']
        for path, data in open_now:
            counts = progress(data)['counts']
            done = sum(count for status, count in counts.items() if status not in ('pending', 'in-progress'))
            left = [entry['name'] for entry in data['brands'] if entry['status'] in ('pending', 'in-progress')]
            started = parse_time(data.get('started_at'))
            lines_open.append('- {} (run "{}"{}): {} of {} brands done{}. {}: `{}`'.format(
                data.get('workflow_name') or data['workflow'], data['name'],
                ', started ' + plain_date(started) if started else '', done, len(data['brands']),
                '; next: ' + left[0] if left else '; every brand is recorded',
                'Carry on' if left else 'Finish it (its combined note and handoff)',
                command_line([me, 'run', 'next' if left else 'finish', '--workspace', str(root), '--run', data['name']])))
        waiting = 0
        seen_workflows = set()
        for path, data in runs:                     # newest first: each workflow's newest finished run speaks for it
            if data.get('status') != 'finished' or data['workflow'] in seen_workflows:
                continue
            finished = parse_time(data.get('finished_at'))
            if finished is None or (moment - finished).days > FLIGHT_RECENT_DAYS:
                continue
            seen_workflows.add(data['workflow'])
            handoff = data.get('handoff') if isinstance(data.get('handoff'), dict) else {}
            label = data.get('workflow_name') or data['workflow']
            where = ' ({}, {}; the note: {})'.format(label, plain_date(finished), data.get('note_file') or 'not saved')
            for item in handoff.get('go') or []:
                if isinstance(item, dict) and text_value(item.get('change')):
                    waiting += 1
                    lines_wait.append('- {}, waits for your go: {}{}'.format(
                        item.get('name') or 'a brand', one_line(item['change'], 240), where))
            for item in handoff.get('need') or []:
                if isinstance(item, dict) and text_value(item.get('ask')):
                    waiting += 1
                    used = text_value(item.get('default')) or text_value(item.get('meanwhile'))
                    lines_wait.append('- {}, needs from you: {}{}{}'.format(
                        item.get('name') or 'a brand', one_line(item['ask'], 240),
                        ' (meanwhile: {})'.format(one_line(used, 160)) if used else '', where))
            following = handoff.get('next') if isinstance(handoff.get('next'), dict) else {}
            said = text_value(following.get('words')) or text_value(following.get('line')) or text_value(following.get('starts'))
            if said:
                lines_next.append('- After {} ({}): {}'.format(label, plain_date(finished), one_line(said, 260)))
        due = brands_due(root, brands, today)
        for item in due:
            waiting += 1
            lines_wait.append('- {}, {} {}: {} (a DUE line in its CLIENT_RULES.md: mark it DONE there when it is)'.format(
                item['name'], 'was due' if item['late'] else 'due', plain_day(item['day']),
                item['what']))
        said_rules, rule_count = last_rules(root)

        def part(lines, none, more_in):
            if not lines:
                return [none]
            shown = lines[:FLIGHT_LINES]
            if len(lines) > len(shown):
                shown.append('- and {} more: {}'.format(len(lines) - len(shown), more_in))
            return shown
        newest = max([text_value(data.get('updated_at')) or text_value(data.get('started_at')) or ''
                      for path, data in runs] or [''])
        meta = {'written': stamp(moment), 'by': why, 'open_runs': len(open_now), 'waiting_on_owner': waiting,
                'due': len(due), 'runs_seen': len(runs), 'newest_run_update': newest or None}
        page = ['<!-- {} {} -->'.format(FLIGHT_SCHEMA, json.dumps(meta, sort_keys=True)),
                '# Work in flight', '',
                'Written {} by workspace.py ({}).{} A view of what is in flight across the brands, built again each '
                'time from the run records ({}/), each brand\'s own rules and {}: nothing typed here is kept. A to-do '
                'with a date lives in its brand\'s rules (a line "DUE <date>: <what>" in CLIENT_RULES.md), and a rule '
                'for every brand in {}. Command lines here run from the workspace\'s own folder, the folder this '
                'file is in.'.format(plain_time(moment), 'when a run finished' if why == 'run finish' else 'at a session\'s handoff',
                                     ' ' + _PAGE['note'] if _PAGE.get('note') else '', RUNS, RULES_FILE, RULES_FILE), '',
                '## Open runs', ''] + part(lines_open, 'None: no run across the brands is unfinished.',
                                           'workspace.py run status names every one') + [
                '', '## Waiting on the owner', ''] + part(lines_wait, 'Nothing waits on the owner.',
                                                          'each run\'s combined note has them all') + [
                '', '## Next for Caiman', ''] + part(lines_next, 'Nothing is queued after the last runs: workspace.py plan '
                                                     'ranks what each brand needs next.', 'WORKSPACE PLAN.md') + [
                '', '## The last rules said', ''] + (
                    ['- ' + line for line in said_rules] + (
                        ['- and {} more in {}'.format(rule_count - len(said_rules), RULES_FILE)]
                        if rule_count > len(said_rules) else [])
                    if said_rules else ['No rule for every brand is saved yet ({}): CLIENT_RULES.py set --workspace, from '
                                        'any brand\'s folder, saves one.'.format(RULES_FILE)]) + ['']
        text_out = from_workspace(root, '\n'.join(page))
        write_atomic(root / FLIGHT_FILE, text_out.encode('utf-8'))
    except Exception as error:      # the run is finished, and the session hands off, whatever happens here
        return {'problem': "{} couldn't be written ({}): workspace.py handoff writes it.".format(FLIGHT_FILE, one_line(error, 200))}
    return {'file': FLIGHT_FILE, 'written_by': why, 'open_runs': len(open_now), 'waiting_on_owner': waiting, 'due': len(due),
            'words': ('{} written: {}, {} waiting on the owner. It is the one page of what is in flight across the '
                      'brands; the setup check reads it at the start of the next session.').format(
                          FLIGHT_FILE, plural(len(open_now), 'open run'), waiting)}


def cmd_handoff(args):
    """A session hands off (Caiman 0.3.58, FLAGS F158): the page of work in flight is written again from the records, so
    the next session, in this chat or another, starts from the same page."""
    root = workspace_root(args.workspace)
    flight = write_flight(root, 'handoff', text_value(getattr(args, 'session', None)), getattr(args, 'plugin_version', None))
    answer = {'schema': SCHEMA, 'command': 'handoff', 'workspace': str(root), 'work_in_flight': flight,
              'how_to_continue': (
                  'Say in one line that {} is written and what it holds (work_in_flight.words); it is where the next '
                  'session starts. A rule the owner said in this session that should hold for every brand goes in {} '
                  'before you hand off (CLIENT_RULES.py set --workspace, from any brand\'s folder), and a to-do with a '
                  'date in its brand\'s own rules (a DUE line).').format(FLIGHT_FILE, RULES_FILE)}
    if flight.get('problem'):
        answer['how_to_continue'] = flight['problem']
    return answer


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
        # Caiman 0.3.34: read-only work Caiman does itself, then gives the figures; nothing to offer.
        how += (" {}'s figures marked whole seller account (or an earlier list) aren't just the brand's: say so in those "
                "words, never as the brand's own. Refresh that brand's business view in its own folder "
                '(REFRESH_OPERATING_VIEW.py --project-root <its folder>; it reads no new data and changes nothing in '
                'the account), then run summary again and give its figures from the refreshed view; its VIP weekly '
                'dashboard follows at the next weekly review.').format(names(stale))
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


def newest_dashboard_day(folder):
    """The newest day a Caiman Dashboard is built for in a business folder (outputs/dashboard/<YYYY-MM-DD>/ with its
    manifest), or None."""
    base = Path(folder) / 'outputs' / 'dashboard'
    try:
        days = sorted(path.name for path in base.iterdir() if path.is_dir() and DAY_RE.match(path.name)
                      and (path / 'dashboard_manifest.json').is_file())
    except OSError:
        return None
    return days[-1] if days else None


def dashboard_after_run(root, data):
    """Caiman 0.3.55 (FLAGS F125): what a finished Advertising Daily Check run says of the brands' pages. Each brand's
    task ended by building its own Caiman Dashboard, so one command puts them together as built (dashboard --built:
    none is built again, which over a dozen brands takes longer than one call may). None when no brand of the run has a
    kit with DASHBOARD.py."""
    have = [entry for entry in data['brands'] if dashboard_program(brand_folder(root, entry))]
    if not have:
        return None
    argv = [str(Path(__file__).resolve()), 'dashboard', '--workspace', str(root), '--built']
    return {'command': command_line(argv),
            'words': ("Each brand's check ended by building its own Caiman Dashboard. Put them together now with "
                      "dashboard.command: it merges the pages as built and builds none again, and its answer names a "
                      "brand whose page is from an earlier day. Look at the merged page (its merged.fallback) before "
                      "you give it. Publishing or deploying it is the member's step, as they have it set up.")}


def cmd_dashboard(args):
    """Build each brand's Caiman Dashboard with that brand's own kit (DASHBOARD.py in its business folder), then merge
    them into <workspace>/outputs/dashboard/<date>/: one dashboard with "All brands" and each brand. It reads only
    each brand's saved files, never contacts Amazon and never changes an account. With --built (Caiman 0.3.55) it
    builds none: it merges each brand's newest page as its own Advertising Daily Check built it."""
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
        elif getattr(args, 'built', False):
            # Caiman 0.3.55 (FLAGS F125): after a Daily Check across the brands each brand's own check has built
            # its page; merge them as built and build none again
            newest = newest_dashboard_day(folder)
            if newest is None:
                entry.update({'status': 'not-built', 'note': "No Caiman Dashboard is built in this brand's folder "
                                                              'yet: its Advertising Daily Check builds one, or run '
                                                              'dashboard without --built.'})
            else:
                entry.update({'status': 'built', 'built_again': False, 'built_day': newest,
                              'dashboard_folder': rel(root, folder.joinpath('outputs', 'dashboard', newest)),
                              'note': 'As built for {} (not built again).'.format(run_day_words(newest))})
                built.append((brand, folder, program))
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
    merged, earlier, last = None, [], None
    if built:
        def kit_rank(item):
            number = re.sub(r'\D', '', str(item[0].get('kit_version') or ''))
            return (parse_version(item[0].get('kit_core_version') or '') or (0, 0, 0), int(number) if number else 0)
        merger = max(built, key=kit_rank)[2]
        argv = [python(), str(merger), '--merge'] + [str(folder) for _, folder, _ in built] + ['--out-root', str(root)]
        if args.today:
            argv += ['--today', args.today]
        elif getattr(args, 'built', False):
            # The page is of the newest day a brand's page is built for. With no day named, one brand built this
            # morning as of yesterday (Amazon hadn't posted its day: a brand that shares its seller account, every
            # morning) pulls every brand back to yesterday's pages (the merge's 0.3.42 rule); named, that brand is
            # the one from an earlier day, and the others stay today's.
            argv += ['--today', max(entry['built_day'] for entry in results if entry.get('built_day'))]
        code, out, err, failed = run_program(argv, root, args.timeout)
        data = json_from(out) or {}
        if failed or code != 0 or data.get('status') != 'merged':
            merged = {'status': 'failed', 'note': one_line(data.get('member_message') or failed or err or
                                                           'the merge gave no result', 400)}
        else:
            # Caiman 0.3.55 (BUILD ITEMS M6): a brand whose page is from an earlier day than the merged page's is
            # merged as it is; the answer says so, so its figures aren't read as that day's. The kit's own list
            # when it gives one (0.3.55 on), else each brand's day against the merged page's.
            last = str(data.get('today') or '')
            if isinstance(data.get('earlier'), list):
                earlier = [item for item in data['earlier'] if isinstance(item, dict) and item.get('brand')]
            else:
                earlier = [{'brand': item.get('brand'), 'day': str(item.get('today'))} for item in data.get('brands') or []
                           if isinstance(item, dict) and DAY_RE.match(str(item.get('today') or '')) and DAY_RE.match(last)
                           and str(item.get('today')) < last]
            merged = {'status': 'merged', 'folder': rel(root, Path(data['folder'])),
                      'fallback': rel(root, Path(data['fallback'])), 'page': rel(root, Path(data['page'])),
                      'brands': [item.get('brand') for item in data.get('brands') or []],
                      'note': one_line(data.get('member_message'), 600),
                      'publish_plan_command': 'python3 {} --project-root {} --publish-plan'.format(quoted(merger),
                                                                                                quoted(root))}
    done = [entry for entry in results if entry['status'] == 'built']
    others = [entry for entry in results if entry['status'] != 'built']
    if merged and merged['status'] == 'merged':
        if earlier:
            merged['earlier'] = earlier
        message = '{} one Caiman Dashboard over {}: {}.'.format(
            'Put together, as built,' if getattr(args, 'built', False) else 'Built', plural(len(done), 'brand'),
            names([entry['name'] for entry in done]))
        if earlier:
            message += ' From an earlier day than {}: {}.'.format(run_day_words(last), '; '.join(
                '{} ({})'.format(item['brand'], run_day_words(item['day'])) for item in earlier))
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
    puller = common(commands.add_parser('puller', help="The report puller's one switch: on, off, or what is saved "
                                                         '(Caiman 0.3.58).'))
    puller.add_argument('--on', action='store_true', help='Switch the report puller on for this workspace or folder.')
    puller.add_argument('--by', help='Who switches it on (a few words; kept with the switch).')
    puller.add_argument('--off', action='store_true', help='Switch it off.')
    operator = common(commands.add_parser('operator', help="The same switch under its 0.3.57 name (--name is puller's "
                                                             '--on --by).'))
    operator.add_argument('--name', help='Who switches the report puller on.')
    operator.add_argument('--off', action='store_true', help='Switch it off.')
    status = common(commands.add_parser('status', help='One table across the brands.'))
    status.add_argument('--brands', help='Only these brands (IDs, names, folders or slugs, separated by commas).')
    status.add_argument('--quick', action='store_true', help="Read files only; don't run the kits' scripts.")
    plan = common(commands.add_parser('plan', help="Merge each brand's NEXT_STEP.py into one ranked plan."))
    plan.add_argument('--brands')
    plan.add_argument('--timeout', type=int, default=STEP_SECONDS, help='Seconds each brand\'s NEXT_STEP.py may take.')
    plan.add_argument('--per-brand', type=int, default=3, help='Steps per brand in the plan (default 3).')
    plan.add_argument('--max-seconds', type=float,
                      help='Caiman 0.3.58: stop asking brands after this many seconds and answer in_progress with the brands '
                           'left (a command that may run only about three minutes: 100). Each brand\'s answer is kept as it '
                           'arrives, with or without this, and the same command again asks only the brands left.')
    plan.add_argument('--session', help="This session's name from a run's answer: a run it's working through is its "
                                        'own, not left to another session (Caiman 0.3.34).')
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
    nxt.add_argument('--brand', metavar='BRAND',     # Caiman 0.3.56 (FLAGS P324)
                     help='Hand out this brand (one still to do) to this session, not the next one in order.')
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
    reports.add_argument('--poll-with', help='For a read the run didn\'t list: the tool its report is polled with '
                         '(default: get_report_status for an all-digit ID, else get_ads_report_status).')
    reports.add_argument('--tool', help='For a read the run didn\'t list: the tool that asks for it again.')
    reports.add_argument('--arguments', help='For a read the run didn\'t list: its arguments, as one JSON object.')
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
    dashboard.add_argument('--built', action='store_true',
                           help="Build none: merge each brand's newest dashboard as it was built (after an Advertising "
                                'Daily Check across the brands, whose own checks built them).')
    handoff = common(commands.add_parser('handoff', help='A session hands off: write the one page of work in flight across the '
                                                         'brands (the open runs, what waits on the owner, the last rules said).'))
    if handoff is not None and not any('--session' in action.option_strings for action in handoff._actions):
        handoff.add_argument('--session', help='This session, as the run commands take it.')
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    handlers = {'find': cmd_find, 'init': cmd_init, 'status': cmd_status, 'plan': cmd_plan, 'summary': cmd_summary,
                'update-plan': cmd_update_plan, 'update': cmd_update, 'routine': cmd_routine, 'operator': cmd_puller,
                'puller': cmd_puller, 'handoff': cmd_handoff}
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
    print(json.dumps(handed(args.command, result), indent=2, ensure_ascii=True))
    return 0


def roomy_temp_folder(argv=None, need=256 * 1024 * 1024):
    """Caiman 0.3.41 (FLAGS P110): when the default temporary folder has less than `need` bytes free (a cloud session on
    the member's computer whose small temporary volume 12 sessions filled, so a workbook save crashed), temporary files
    go to the business folder's .caiman/tmp, else the system's temporary folder, for this script and every program it
    runs (TMPDIR, TEMP and TMP). Nothing changes when the default has room. Never raises."""
    import os
    import shutil as _shutil
    import sys
    import tempfile as _tempfile
    from pathlib import Path
    try:
        if _shutil.disk_usage(_tempfile.gettempdir()).free >= need:
            return None
    except OSError:
        pass
    argv = list(sys.argv[1:] if argv is None else argv)
    roots = [argv[i + 1] for i, arg in enumerate(argv[:-1]) if arg in ('--project-root', '--workspace', '--root')]
    places = [Path(root).expanduser() / '.caiman' / 'tmp' for root in roots[:1]]
    places += [Path(os.environ.get('SystemRoot') or 'C:/Windows') / 'Temp' if os.name == 'nt' else Path('/tmp'), Path('/var/tmp')]
    for place in places:
        try:
            probe = place                 # the room is checked first, so no empty .caiman/tmp is left in the folder
            while not probe.exists() and probe.parent != probe:
                probe = probe.parent
            if _shutil.disk_usage(str(probe)).free >= need:
                place.mkdir(parents=True, exist_ok=True)
                for name in ('TMPDIR', 'TEMP', 'TMP'):
                    os.environ[name] = str(place)
                _tempfile.tempdir = str(place)
                return str(place)
        except OSError:
            continue
    return None


if __name__ == '__main__':
    roomy_temp_folder()
    raise SystemExit(main())
