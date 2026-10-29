#!/usr/bin/env python3
"""Caiman's setup check: is everything ready to work in this business folder?

  python3 setup_check.py --project-root "<business folder>" \\
      --connector ok|failed|not-connected --connector-brands "<slug,slug,...>" \\
      [--connector-brands-json '<brands as JSON>'] [--connector-error "<text>"] [--no-write] \\
      [--plugin-version <version>] [--live-kit <release> | --live-kit @<saved get_kit_download result>] \\
      [--download-site ok|blocked [--download-error "<text>"]]
  python3 setup_check.py --project-root "<business folder>" --flags-only [--plugin-version <version>]

Before it runs, Claude calls the Caiman connector's list_brands and passes what it got: ok and the brand
slugs it returned ("" when it returned none), failed and the error text, or not-connected when no Caiman
connector tools are listed. With ok, --connector-brands-json can carry the brands list_brands returned, each
with its slug, display_name and marketplace_id (a JSON list, list_brands' own answer, or @ and a file that
holds it); it can stand in for --connector-brands. With the names, a folder saved under an older account name
of a listed brand is reported as attention rather than as a problem. With its sp_api_authorized and
ads_authorized, a connection this business's membership needs that is off (Seller Central or Amazon Ads on VIP,
Amazon Ads on GLS+) is reported with the click only the member can make.

With --live-kit (the release the connector's get_kit_download gives for this folder's membership, for example
2026-10-14-vip-v56), the kit check also compares the folder's kit with the one members get now, so a newer kit is
found even when the plugin is older than it. The answer's kit_report is the call for the connector's
record_kit_state tool (the plugin and kit versions only), for Claude to make when the connector lists that tool. Its
arguments_with_folder_ids is the same call with each folder's ID (the one kit-sync keeps in .caiman/workspace-id.json),
whether Deep Seed is done and the connector brand slug the folder works on (Caiman 0.3.33, for the Caiman portal's setup
checks): Claude sends it instead only once the tool lists folder_id, since the tool refuses fields it doesn't list.
Its arguments_with_next_step (Caiman 0.3.38) adds each folder's next_step, the kind of step it waits for (reports_due,
kit_update, plugin_update, deep_seed, vip_machine_setup, connect_ads, connect_seller_central, other, or none), so the portal can say which
step rather than "needs a step"; Claude sends it only once the tool's folders entries list next_step as well.

The answer's flag_reports (Caiman 0.3.36) is there when the business folder's outputs/flags.md has lines the member said
yes to sending to the Caiman team that haven't gone yet (they end with [to send]): one call per line for the connector's
report_flag tool, carrying the line itself (links, tokens, emails and order IDs taken out), its date, kind and where
part, and the folder's versions, ID, store, setup check result and runtime. Claude makes them once the connector lists
that tool and marks each line sent. --flags-only gives just those calls, from the folder's saved
files and without the checks, for the moment the member says yes.

With --download-site (Caiman 0.3.32: what Claude's test of Caiman's download site, tools.caimandata.ai, found where the
kit's scripts run), a refusal is a problem line with the member's one click (Claude's network setting for code), and the
Kit and VIP Machine lines say what waits for it instead of promising an update or a refresh that can't run. A VIP Machine
set up but with no scorecard yet says so, with the day its setup finished: until the weekly review builds the scorecard it
tracks no proposals or changes.

It checks, in this order, and reports each one as ok, attention (works, but something is due) or problem
(blocks work): commands and Python, the business folder, the kit, skills named like the kit's that load from outside
the business folder (attention only, and only when this computer shows some: an account's synced skills, Claude
Code's personal skills folder, the account folders a cloud session mounts), the connector, Deep Seed and, on VIP,
the VIP Machine, with its star-ratings reading when the VIP Machine records ratings.

It prints JSON for Claude, and saves CAIMAN STATUS.md in the business folder in plain words for the member
and, when the folder has a .caiman folder, the same result for the kit's scripts in .caiman/setup-check.json
(the checks' statuses and this business's Amazon connections; NEXT_STEP.py asks the member for a connection
that's off). Neither with --no-write. The status shows the computer's local time; on a computer whose clock is
set to UTC (the Claude app's Linux workspace, a cloud task) it shows the member's or the Amazon account's time
zone when the folder records one, else says UTC. It changes nothing else and never uses the network. It exits
0, or 2 when the arguments are wrong. A copy of this file run away from the plugin (for example on the
member's computer) can't read the plugin's version: pass it with --plugin-version.

A workspace (a folder without a kit of its own that holds two or more business folders, up to three levels down,
or one with CAIMAN WORKSPACE.json): each brand is checked in its own business folder as above, each saving its own
CAIMAN STATUS.md, and the answer has one headline for all of them, the brands with their checks under "brands", and a
short CAIMAN STATUS.md in the workspace folder.

Standard-library Python 3.8+ in one file. It also starts on older Python 3, so it can say that Python is
too old for the kit.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path

try:
    import zoneinfo as _zoneinfo                    # Python 3.9 and later; without zone data the status shows UTC
except ImportError:
    _zoneinfo = None

sys.dont_write_bytecode = True

HERE = Path(__file__).resolve().parent              # <plugin>/skills/caiman/scripts
MIN_PYTHON = (3, 8)
STATUS_FILE = 'CAIMAN STATUS.md'
MACHINE_DIR = 'VIP Machine'
# An older kit set the VIP Machine up inside its template folder; MACHINE_ROOT_GUARD.py still accepts it there.
NESTED_MACHINE_DIR = 'Operating Framework/VIP Machine'


MACHINE_FILES = ('engine/vip_machine.py', 'config/brand.json', 'state/workspace.json')


def machine_folder(root):
    """(folder, name) of the business's VIP Machine: the usual place, else the older nested one when it is set up.

    A usual-place folder with no engine, settings or state (only reports skills saved before setup) doesn't count."""
    usual = root / MACHINE_DIR
    nested = root / NESTED_MACHINE_DIR
    usual_is_machine = usual.is_dir() and any((usual / name).exists() for name in MACHINE_FILES)
    if not usual_is_machine and (nested / 'config' / 'brand.json').is_file() and (nested / 'state' / 'workspace.json').is_file():
        return nested, NESTED_MACHINE_DIR
    return usual, MACHINE_DIR
RATINGS_SOURCE = 'product_ratings_current'
RATINGS_COMMAND = 'record-ratings'
RATINGS_MAX_DAYS = 30
KIT_SYNC_SECONDS = 60
PREFLIGHT_SECONDS = 90
MAX_REVIEW_FOLDERS = 20000
TIER_NAMES = {'vip': 'Caiman VIP', 'gls-plus': 'Caiman GLS+'}
OK, ATTENTION, PROBLEM = 'ok', 'attention', 'problem'
MARKS = {OK: '\u2705', ATTENTION: '\u26a0\ufe0f', PROBLEM: '\u274c'}
MONTHS = ('January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October',
          'November', 'December')
WEEKDAYS = ('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday')
KIT_UPDATE_NEXT = ('Claude updates the kit. Kit files it replaces are saved in the _previous-kit folder, and your '
                   'own files stay as they are.')
CHECKED_THING = {'Commands and Python': 'commands and Python', 'Business folder': 'the business folder',
                 'Kit': 'the kit', 'Caiman connector': 'the Caiman connector', 'Deep Seed': 'Deep Seed',
                 'VIP Machine': 'the VIP Machine', 'Star ratings': 'the star ratings',
                 'Old skill copies': 'the old skill copies', "Caiman's download site": "Caiman's download site"}


# ---------------------------------------------------------------- small helpers

def read_json(path):
    """Parsed JSON from a file, or None when it is missing or unreadable."""
    try:
        with open(str(path), 'r', encoding='utf-8-sig') as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return None


def as_dict(value):
    return value if isinstance(value, dict) else {}


def text_value(value):
    """The text without surrounding spaces when it isn't empty, else None."""
    return value.strip() if isinstance(value, str) and value.strip() else None


def norm_tier(value):
    """'vip' or 'gls-plus' from the spellings kits use, else None."""
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


def parse_time(value):
    """A UTC datetime from an ISO 8601 timestamp such as 2026-10-10T15:00:00Z, else None."""
    if not isinstance(value, str):
        return None
    match = re.fullmatch(r'\s*(\d{4})-(\d\d)-(\d\d)(?:[Tt ](\d\d):(\d\d)(?::(\d\d)(?:\.\d+)?)?)?\s*'
                         r'(Z|z|[+-]\d\d:?\d\d)?\s*', value)
    if not match:
        return None
    year, month, day, hour, minute, second, zone = match.groups()
    try:
        moment = dt.datetime(int(year), int(month), int(day), int(hour or 0), int(minute or 0), int(second or 0))
    except ValueError:
        return None
    offset = dt.timedelta(0)
    if zone and zone not in ('Z', 'z'):
        digits = zone[1:].replace(':', '')
        offset = dt.timedelta(hours=int(digits[:2]), minutes=int(digits[2:]))
        if zone[0] == '-':
            offset = -offset
    return (moment - offset).replace(tzinfo=dt.timezone.utc)


def in_zone(moment, zone=None):
    """moment in the time zone the status shows (shown_zone's 'zone'), else in the computer's own."""
    found = zone_at(moment, zone) if zone else None
    if found is None:
        return moment.astimezone()
    minutes, name = found
    return moment.astimezone(dt.timezone(dt.timedelta(minutes=minutes), name or utc_words(minutes)))


def plain_date(moment, zone=None):
    """'October 9, 2026', in the computer's local time (or the zone given)."""
    local = in_zone(moment, zone)
    return '{} {}, {}'.format(MONTHS[local.month - 1], local.day, local.year)


def plain_time(moment, zone=None):
    """'Saturday, October 10, 2026 at 11:45 AM', in the computer's local time (or the zone given)."""
    local = in_zone(moment, zone)
    return '{}, {} {}, {} at {}:{:02d} {}'.format(WEEKDAYS[local.weekday()], MONTHS[local.month - 1], local.day, local.year,
                                                 local.hour % 12 or 12, local.minute, 'AM' if local.hour < 12 else 'PM')


def utc_words(minutes):
    """'UTC', 'UTC-6' or 'UTC+5:30' for an offset from UTC in minutes."""
    sign, size = ('+' if minutes >= 0 else '-'), abs(minutes)
    return 'UTC' if not size else 'UTC{}{}{}'.format(sign, size // 60, ':{:02d}'.format(size % 60) if size % 60 else '')


def zone_label(moment):
    """'MDT, UTC-6', or 'UTC'."""
    offset = moment.utcoffset() or dt.timedelta(0)
    utc = utc_words(int(offset.total_seconds() // 60))
    name = moment.tzname()
    return utc if not name or name == utc or name.upper() in ('UTC', 'GMT') else '{}, {}'.format(name, utc)


def days_ago(moment, now, zone=None):
    """'today', 'yesterday' or 'N days ago', by the computer's calendar (or the zone given)."""
    days = max(0, (in_zone(now, zone).date() - in_zone(moment, zone).date()).days)
    return 'today' if days == 0 else ('yesterday' if days == 1 else '{} days ago'.format(days))


# ---------------------------------------------------------------- the time zone CAIMAN STATUS.md shows

# A computer whose clock is set to UTC (the Claude app's Linux workspace, a cloud task) doesn't show the member's time. The
# status file then shows its times in a zone the business folder records (Caiman 0.3.24; before, it said "the computer's
# local time: UTC"): the member's own (a "Time zone" line in CLIENT_RULES.md, or the zone of the routines they approved in
# SCHEDULE_PLAN.json), else the Amazon account's (the saved Ads profile read, else the zone Amazon uses for the
# marketplace's Ads profiles, as the kit counts the account's days, else a zone saved in the VIP Machine's settings or the
# history intake). Otherwise it says UTC, and doesn't call that the member's local time.

# The zone of each marketplace's Ads profiles, as Amazon documents it (the same table as the kit's change_results.py).
MARKET_ZONES = {
    'US': 'America/Los_Angeles', 'CA': 'America/Los_Angeles', 'MX': 'America/Los_Angeles', 'BR': 'America/Sao_Paulo',
    'UK': 'Europe/London', 'DE': 'Europe/Paris', 'FR': 'Europe/Paris', 'IT': 'Europe/Paris', 'ES': 'Europe/Paris',
    'NL': 'Europe/Amsterdam', 'BE': 'Europe/Brussels', 'SE': 'Europe/Stockholm', 'PL': 'Europe/Warsaw', 'TR': 'Europe/Istanbul',
    'AE': 'Asia/Dubai', 'SA': 'Asia/Riyadh', 'EG': 'Africa/Cairo', 'IN': 'Asia/Kolkata', 'JP': 'Asia/Tokyo',
    'SG': 'Asia/Singapore', 'AU': 'Australia/Sydney', 'IE': 'Europe/Dublin', 'ZA': 'Africa/Johannesburg'}
ZONE_WORDS = {'America/Los_Angeles': 'Pacific time', 'US/Pacific': 'Pacific time', 'America/Denver': 'Mountain time',
              'America/Boise': 'Mountain time', 'US/Mountain': 'Mountain time', 'America/Phoenix': 'Arizona time',
              'US/Arizona': 'Arizona time', 'America/Chicago': 'Central time', 'US/Central': 'Central time',
              'America/New_York': 'Eastern time', 'America/Detroit': 'Eastern time', 'America/Toronto': 'Eastern time',
              'US/Eastern': 'Eastern time', 'America/Anchorage': 'Alaska time', 'Pacific/Honolulu': 'Hawaii time',
              'Europe/London': 'UK time', 'Europe/Dublin': 'Irish time'}
ZONE_NAME = re.compile(r'\b(?:[A-Z][A-Za-z]+/[A-Za-z_]+(?:/[A-Za-z_]+)?|UTC)\b')


def zone_at(moment, zone):
    """(offset from UTC in minutes, abbreviation or None) of a time zone at a moment, or None when this Python has no zone
    data for it (Python 3.8, or Windows without the tzdata package): the status then says UTC, plainly."""
    if not isinstance(zone, str) or not re.fullmatch(r'[A-Za-z]+(?:/[A-Za-z_+-]+){0,2}', zone):
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=dt.timezone.utc)
    if _zoneinfo is not None:
        try:
            local = moment.astimezone(_zoneinfo.ZoneInfo(zone))
            name = local.tzname()
            return int(local.utcoffset().total_seconds() // 60), (name if name and name[0].isalpha() else None)
        except Exception:                           # no zone data for it on this computer
            pass
    return None


def utc_clock(now):
    """True when the computer's own clock is set to UTC: its zone's name is UTC or GMT at no offset, in a zone with no
    summer time (Caiman 0.3.25: a computer in London in winter shows GMT at no offset too, and that is the member's own
    time)."""
    return (not now.utcoffset() and (now.tzname() or 'UTC').upper() in ('UTC', 'GMT', 'UCT', 'Z', 'ZULU', 'UNIVERSAL')
            and not time.daylight)


def shown_zone(root, now):
    """{'zone', 'whose' ('member' or 'account'), 'from'} for the times this folder's status shows when the computer's clock
    is UTC, or None when the folder records no zone this computer can show."""
    def usable(value):                              # a zone this computer can show, other than UTC itself
        value = text_value(value)
        return value if value and value.upper() not in ('UTC', 'ETC/UTC', 'GMT', 'ETC/GMT', 'UCT', 'UNIVERSAL', 'ZULU') \
            and zone_at(now, value) is not None else None

    rules = root / 'CLIENT_RULES.md'
    try:
        text = rules.read_text(encoding='utf-8-sig', errors='replace') if rules.is_file() and \
            rules.stat().st_size <= 4 * 1024 * 1024 else ''
    except OSError:
        text = ''
    for label, rest in re.findall(r'^\s*[-*]\s+\*\*([^*\n]*time ?zone[^*\n]*)\*\*:?\s*([^\n]*)', text, re.I | re.M):
        for name in ZONE_NAME.findall(rest):
            if usable(name):
                account = re.search(r'account|amazon|marketplace|report|ads', label, re.I)
                return {'zone': name, 'whose': 'account' if account else 'member', 'from': 'CLIENT_RULES.md'}
    plan = as_dict(read_json(root / 'SCHEDULE_PLAN.json'))
    if plan.get('member_approved') is True and usable(plan.get('timezone')):
        return {'zone': plan['timezone'].strip(), 'whose': 'member', 'from': 'SCHEDULE_PLAN.json'}
    reads, places = [], []
    folder = root / '.caiman' / 'setup-inputs'
    try:
        files = sorted((p for p in folder.glob('*.json') if p.is_file() and not p.is_symlink()),
                       key=lambda p: (p.stat().st_mtime, p.name), reverse=True)[:50] if folder.is_dir() else []
    except OSError:
        files = []
    for path in files:
        value = as_dict(read_json(path))
        result = as_dict(value.get('result'))
        for read in (value, result, as_dict(value.get('profile')), as_dict(result.get('profile'))):
            if read.get('profile_id') or read.get('currency_code') or read.get('country_code'):
                if usable(read.get('timezone')):
                    return {'zone': read['timezone'].strip(), 'whose': 'account',
                            'from': '.caiman/setup-inputs/' + path.name}
                reads.append((market_code(read.get('country_code')) or market_code(read.get('marketplace_id')),
                              '.caiman/setup-inputs/' + path.name))
        places.append((as_dict(value.get('marketplace')), '.caiman/setup-inputs/' + path.name))
    machine, machine_name = machine_folder(root)
    places.append((as_dict(as_dict(read_json(machine / 'config' / 'brand.json')).get('marketplace')),
                   machine_name + '/config/brand.json'))
    markets = reads + [(market_code(place.get('country_code')) or market_code(place.get('id')), where) for place, where in places]
    markets.append((market_code(as_dict(as_dict(read_json(root / 'GLS_PLUS_CONFIG.json')).get('identity')).get('marketplace')),
                    'GLS_PLUS_CONFIG.json'))
    markets += [(market_code(identity.get('marketplace')) or market_code(identity.get('marketplace_id')), where)
                for identity, where in saved_identities(root)]
    for code, where in markets:
        if code in MARKET_ZONES and usable(MARKET_ZONES[code]):
            return {'zone': MARKET_ZONES[code], 'whose': 'account', 'from': where}
    saved = [(place.get('timezone'), where) for place, where in places]
    saved.append((as_dict(read_json(root / 'HISTORY_INTAKE.json')).get('timezone'), 'HISTORY_INTAKE.json'))
    for value, where in saved:
        if usable(value):
            return {'zone': value.strip(), 'whose': 'account', 'from': where}
    return None


def checked_words(now, shown):
    """'Checked on ... (...).' for CAIMAN STATUS.md: in the computer's own time, or when its clock is UTC in the zone the
    folder records (shown), else plainly in UTC."""
    if shown:
        local = in_zone(now, shown['zone'])
        name = ZONE_WORDS.get(shown['zone']) or '{} time'.format(shown['zone'].rsplit('/', 1)[-1].replace('_', ' '))
        whose = 'your time zone' if shown['whose'] == 'member' else "your Amazon account's time zone"
        return 'Checked on {} ({}, {}: {}).'.format(plain_time(now, shown['zone']), whose, name, zone_label(local))
    if utc_clock(now):
        return 'Checked on {} UTC.'.format(plain_time(now.astimezone(dt.timezone.utc), 'UTC'))
    return "Checked on {} (the computer's local time: {}).".format(plain_time(now), zone_label(now))


def one_line(text, limit=300):
    text = ' '.join(str(text or '').split())
    return text if len(text) <= limit else text[:limit - 3] + '...'


def redact(text, limit=400):
    """Error text with each link cut to its host and token-like values hidden."""
    text = ' '.join(str(text or '').split())
    text = re.sub(r'(?i)\b(https?://)(?:[^\s/@]+@)?([^\s/?#]+)\S*', r'\1\2/...', text)
    text = re.sub(r'(?i)\b(bearer|basic)\s+[^\s",;()\[\]]+', r'\1 [hidden]', text)
    text = re.sub(r'(?i)\b(access[_-]?token|refresh[_-]?token|token|authorization|api[_-]?key|secret|password|'
                  r'signature)(\s*[:=]\s*)("?)(?!bearer\b|basic\b)[^\s",;&()\[\]]+', r'\1\2\3[hidden]', text)
    text = re.sub(r'[A-Za-z0-9+/_=-]{40,}', '[hidden]', text)
    return one_line(text, limit)


def plural(count, one, many):
    return one if count == 1 else many


def run_program(command, cwd, seconds):
    """(exit code, stdout, stderr, None), or (None, '', '', why) when it couldn't start or didn't finish in time.

    Children run with -B and PYTHONDONTWRITEBYTECODE, so they leave no __pycache__ in the member's folder."""
    env = dict(os.environ)
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    env['PYTHONIOENCODING'] = 'utf-8'
    try:
        done = subprocess.run(command, cwd=str(cwd), env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, timeout=seconds)
    except subprocess.TimeoutExpired:
        return None, '', '', 'it did not finish within {} seconds'.format(seconds)
    except OSError as error:
        return None, '', '', 'it could not start ({})'.format(error)
    return done.returncode, done.stdout.decode('utf-8', 'replace'), done.stderr.decode('utf-8', 'replace'), None


def json_from(text):
    """The JSON object a program printed, or None."""
    text = (text or '').strip()
    if not text:
        return None
    try:
        value = json.loads(text)
    except ValueError:
        start = text.find('{')
        if start <= 0:
            return None
        try:
            value = json.loads(text[start:])
        except ValueError:
            return None
    return value if isinstance(value, dict) else None


def python_command():
    return sys.executable or 'python3'


def make_check(check_id, label, status, member_line, next_step=None, member_next='', short='', details=None):
    return {'id': check_id, 'label': label, 'status': status, 'member_line': member_line,
            'member_next': member_next if status != OK else '',
            'next_step': next_step or 'Nothing to do.', 'short': short, 'details': details or {}}


def guarded(check_id, label, function, *arguments):
    """Run one check. If the check itself fails, say so instead of stopping the others."""
    try:
        return function(*arguments)
    except Exception as error:                      # one broken check must not hide the rest
        return make_check(
            check_id, label, ATTENTION, "Claude couldn't finish checking this.",
            next_step='setup_check.py stopped in this check ({}: {}). Check it by hand from the files (the setup '
                      'check guide, "Every session") and say that this part was checked by hand.'.format(
                          type(error).__name__, one_line(error, 200)),
            member_next='Claude checks this by hand and tells you what it finds.',
            short="Claude couldn't finish checking {}".format(CHECKED_THING.get(label, label)),
            details={'error': '{}: {}'.format(type(error).__name__, one_line(error, 300))})


# ---------------------------------------------------------------- facts from the plugin and the folder

def plugin_version(explicit):
    """(version, where) of the Caiman plugin this file belongs to, or (None, None)."""
    if explicit:
        return explicit.strip(), '--plugin-version'
    candidates = [HERE.parent.parent.parent]
    if os.environ.get('CLAUDE_PLUGIN_ROOT'):
        candidates.append(Path(os.environ['CLAUDE_PLUGIN_ROOT']))
    for root in candidates:
        manifest = as_dict(read_json(root / '.claude-plugin' / 'plugin.json'))
        version = text_value(manifest.get('version'))
        if version and manifest.get('name') == 'caiman-core':
            return version, str(root / '.claude-plugin' / 'plugin.json')
    return None, None


def find_kit_sync():
    path = HERE.parent.parent / 'kit-sync' / 'scripts' / 'kit_sync.py'
    return path if path.is_file() else None


def folder_tier(root):
    """The membership the folder's kit is for: plan_tier in ENTITLEMENTS.json, else the kit's manifest."""
    tier = norm_tier(as_dict(read_json(root / 'ENTITLEMENTS.json')).get('plan_tier'))
    if tier:
        return tier
    manifest = as_dict(read_json(root / 'RELEASE_MANIFEST.json'))
    return norm_tier(manifest.get('kit')) or norm_tier(manifest.get('tier'))


def inside(root, relative):
    """root/relative when relative is a plain path inside the folder, else None."""
    if not isinstance(relative, str) or not relative.strip():
        return None
    parts = [part for part in relative.replace('\\', '/').split('/') if part not in ('', '.')]
    if not parts or relative.startswith(('/', '\\')) or '..' in parts or any(':' in part for part in parts):
        return None
    return root.joinpath(*parts)


def saved_identities(root):
    """(identity, where) for each account record the kit's scripts saved, the active one first."""
    found = []
    pointer = as_dict(read_json(root / '.caiman' / 'active-source-index.json'))
    if pointer:
        if isinstance(pointer.get('identity'), dict):
            found.append((pointer['identity'], '.caiman/active-source-index.json'))
        target = inside(root, pointer.get('path'))
        if target is not None:
            found.append((as_dict(as_dict(read_json(target)).get('identity')), pointer.get('path')))
        if text_value(pointer.get('account_id')):
            found.append(({'account_id': pointer['account_id']}, '.caiman/active-source-index.json'))
    found.append((as_dict(as_dict(read_json(root / 'SOURCE_CAPTURES.json')).get('identity')), 'SOURCE_CAPTURES.json'))
    summary = as_dict(as_dict(read_json(root / 'FIRST_WEEK_STATE.json')).get('support_summary'))
    inputs = inside(root, as_dict(summary.get('operating_inputs')).get('path'))
    if inputs is not None:
        found.append((as_dict(as_dict(read_json(inputs)).get('identity')),
                      as_dict(summary.get('operating_inputs')).get('path')))
    return [(identity, where) for identity, where in found if identity]


def slug_shaped(value):
    """True for an ID shaped like a list_brands slug (lowercase letters, digits and hyphens, not all digits)."""
    return bool(re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', value or '')) and not value.isdigit()


def saved_account(root, tier):
    """(slug, brand name, where) of the Amazon account this business folder is set up for.

    VIP: brand.slug in the VIP Machine's settings. Both tiers: the account the kit saved with the source list
    (source_brand_slug, else account_id, which is the list_brands slug)."""
    name = None
    if tier != 'gls-plus':
        machine, machine_name = machine_folder(root)
        brand = as_dict(as_dict(read_json(machine / 'config' / 'brand.json')).get('brand'))
        slug = text_value(brand.get('slug'))
        if slug:
            return slug, text_value(brand.get('name')), machine_name + '/config/brand.json'
    if tier != 'vip':
        identity = as_dict(as_dict(read_json(root / 'GLS_PLUS_CONFIG.json')).get('identity'))
        name = text_value(identity.get('brand_name'))
        if name and name.startswith('REPLACE_'):
            name = None
    identities = saved_identities(root)
    for identity, where in identities:
        slug = text_value(identity.get('source_brand_slug')) or text_value(identity.get('account_id'))
        if slug:
            labels = [text_value(item.get('account_label')) for item, _ in identities]
            return slug, name or next((label for label in labels if label), None), where
    return None, name, None


# ---------------------------------------------------------------- 1. commands and Python

def check_python():
    shown = '{}.{}.{}'.format(*sys.version_info[:3])
    details = {'version': shown, 'executable': sys.executable, 'system': platform.system()}
    if tuple(sys.version_info[:2]) < MIN_PYTHON:
        return make_check(
            'python', 'Commands and Python', PROBLEM,
            "Claude can run commands, but Python {} is too old for Caiman's tools (they need Python 3.8 or "
            "newer).".format(shown),
            next_step='Install Python 3.8 or newer (on Windows, the caiman skill\'s "Which Python command"; '
                      'elsewhere python.org), then run the setup check again with it. Until then the kit\'s '
                      'scripts can\'t run: say so, and don\'t do their work by hand.',
            member_next="Claude installs a newer Python, or asks you to install it from python.org if it can't.",
            short="Python is too old for Caiman's tools", details=details)
    return make_check('python', 'Commands and Python', OK,
                      'Claude can run commands, and Python {} works.'.format(shown), details=details)


# ---------------------------------------------------------------- 2. the business folder

def check_folder(root, no_write):
    details = {'path': str(root)}
    if not root.exists():
        return make_check(
            'business_folder', 'Business folder', PROBLEM, "Claude can't find your business folder at {}.".format(root),
            next_step="The folder doesn't exist. Ask the member where their business folder is (setup check "
                      'guide, section 1); don\'t search the home folder or guess. For a new business, create it '
                      'with their OK on its name and place. Then run the setup check again.',
            member_next='Tell Claude where your business folder is, or let Claude create one for a new business.',
            short="Claude can't find your business folder", details=details)
    if not root.is_dir():
        return make_check(
            'business_folder', 'Business folder', PROBLEM,
            '{} is a file, not a folder, so it can\'t be your business folder.'.format(root),
            next_step='--project-root names a file. Ask the member which folder is the business folder (setup '
                      'check guide, section 1), then run the setup check again.',
            member_next='Tell Claude which folder is your business folder.',
            short="the business folder Claude was given isn't a folder", details=details)
    if no_write:
        details['write_test'] = 'skipped (--no-write)'
        return make_check('business_folder', 'Business folder', OK, 'Claude can open your business folder.',
                          details=details)
    details['write_test'] = 'passed: ' + STATUS_FILE
    return make_check('business_folder', 'Business folder', OK,
                      'Claude can open your business folder and save files in it.', details=details)


def write_status(root, text):
    """(True, None, None) when CAIMAN STATUS.md was saved; else (False, why, kind), kind 'busy', 'in-the-way' or
    'refused'. The save is the test that Claude can write in the business folder."""
    target = root / STATUS_FILE
    try:
        if target.is_symlink() or (target.exists() and not target.is_file()):
            return False, 'something that is not a normal file is already named {}'.format(STATUS_FILE), 'in-the-way'
        with open(str(target), 'wb') as handle:
            handle.write(text.encode('utf-8'))
        return True, None, None
    except OSError as error:
        why = '{} ({})'.format(error.strerror or error, type(error).__name__)
        return False, why, 'busy' if getattr(error, 'winerror', None) in (32, 33) else 'refused'


def folder_write_failed(folder_check, why, kind):
    details = dict(folder_check['details'], write_test='failed: ' + why)
    if kind == 'busy':
        return make_check(
            'business_folder', 'Business folder', ATTENTION,
            "Claude couldn't update {} because another program has it open.".format(STATUS_FILE),
            next_step='{} is open in another program, so it was not updated ({}). Ask the member to close it; the '
                      'next setup check updates it. Other files can still be saved.'.format(STATUS_FILE, why),
            member_next='Close {} if you have it open; Claude updates it next time.'.format(STATUS_FILE),
            short="the status file couldn't be updated", details=details)
    if kind == 'in-the-way':
        return make_check(
            'business_folder', 'Business folder', ATTENTION,
            'Something that isn\'t a normal file is named {} in your business folder, so this summary couldn\'t be '
            'saved there.'.format(STATUS_FILE),
            next_step='{} in the business folder is a folder or a link, so the setup check did not write through '
                      'it. Ask the member before moving it.'.format(STATUS_FILE),
            member_next='Claude asks you what to do with the item named {}.'.format(STATUS_FILE),
            short="the status file couldn't be saved", details=details)
    return make_check(
        'business_folder', 'Business folder', PROBLEM,
        "Claude can't save files in your business folder, so Caiman can't keep its records there.",
        next_step='Saving {} failed: {}. The app may have given read-only access, or the folder\'s permissions keep '
                  'Claude out: ask for folder access again (setup check guide, section 1). Kit installs, Deep Seed and '
                  'the VIP Machine all need to save files here.'.format(STATUS_FILE, why),
        member_next="Claude asks the Claude app for access to save files in your folder; you approve it.",
        short="Claude can't save files in your business folder", details=details)


# ---------------------------------------------------------------- 3. the kit

def compare_versions(core, plugin):
    have, need = parse_version(core or ''), parse_version(plugin or '')
    if have is None:
        return 'older'                              # kits from before 0.3.1 have no core_version
    if need is None:
        return 'plugin-version-unknown'
    return 'older' if have < need else ('newer' if have > need else 'current')


def kit_name(tier, number):
    return '{} kit'.format(TIER_NAMES.get(tier, 'Caiman')) + (' (version {})'.format(number) if number else '')


def kit_result(verdict, tier, number, plugin, details, leftovers=None, locked=None):
    """The kit check for a kit-sync status (or the same verdict worked out from the files)."""
    name = kit_name(tier, number)
    details = dict(details, kit_verdict=verdict)    # Caiman 0.3.38: the folder's next step for the portal reads it
    said = 'kit-sync status: {}'.format(verdict) if details.get('source') == 'kit-sync status' else (
        'From the files ({}): {}'.format(details.get('source'), verdict))
    if verdict == 'current' and not leftovers:
        return make_check('kit', 'Kit', OK, 'Your {} is up to date.'.format(name), details=details)
    if verdict == 'current':
        return make_check(
            'kit', 'Kit', ATTENTION,
            'Your {} is up to date, but files from earlier kits are still in the folder. Claude tidies them up with a '
            'kit update (nothing is deleted).'.format(name),
            next_step='{} with leftovers from earlier kits ({}). Run the kit-sync install again (get_kit_download, '
                      'then install): it moves them to _previous-kit/.'.format(said, ', '.join(sorted(leftovers))),
            member_next=KIT_UPDATE_NEXT, short='old kit files need tidying up', details=details)
    if verdict == 'missing':
        return make_check(
            'kit', 'Kit', PROBLEM,
            "There's no Caiman kit in this folder yet, so Caiman's guides and tools aren't here.",
            next_step='{}. Install the kit with kit-sync (the caiman skill, section 3); for a new business, Deep Seed '
                      'starts with it.'.format(said),
            member_next='Claude installs the kit. It never touches your own files.',
            short="there's no Caiman kit in this folder yet", details=details)
    if verdict == 'newer':
        return make_check(
            'kit', 'Kit', ATTENTION,
            'Your {} is newer than the Caiman plugin in the Claude app. Everything works; the plugin needs an '
            'update.'.format(name),
            next_step='{} (kit {}, plugin {}). The kit can stay; suggest the member updates the Caiman '
                      'plugin and starts a new task. If Update says Caiman is already current, the Claude app may be holding '
                      'an old copy of the Caiman marketplace (it sometimes happens with a marketplace added from GitHub): the '
                      'kit\'s TROUBLESHOOTING.md, "The Caiman plugin won\'t update", has the steps (remove the marketplace, '
                      'quit and reopen Claude, add VoltageDM/caimandata-AI-plugin again, install Caiman from it).'.format(
                          said, details.get('kit_core_version'), plugin),
            member_next='Update the Caiman plugin in the Claude app (usually under Customize, then Plugins), then '
                        'start a new task. If it says it\'s already up to date, Claude walks you through refreshing the '
                        'Caiman marketplace.',
            short='the Caiman plugin needs an update', details=details)
    if verdict == 'other-tier':
        return make_check(
            'kit', 'Kit', ATTENTION, "This folder has the {}, which isn't the one for your membership.".format(name),
            next_step="{}. Switching keeps the member's files; with their OK, run the kit-sync install with "
                      "--switch-tier (kit-sync's guide, \"Switching tiers\").".format(said),
            member_next='Claude switches the kit once you say so. Your files stay as they are.',
            short='the kit is for the other membership', details=details)
    if verdict == 'skills-blocked':
        return make_check(
            'kit', 'Kit', ATTENTION,
            "The Claude app doesn't let Claude look inside the skills folder in your business folder, so it can't "
            "check your kit's skills.",
            next_step="{}. Check that Claude lists the kit's skills (for example vip-machine on VIP); if it doesn't, "
                      "the setup check guide, section 4, has the one step the member does by hand.".format(said),
            member_next="If Caiman's skills don't show up, Claude walks you through copying them in (one step by "
                        "hand).",
            short="Claude can't check the kit's skills", details=details)
    if verdict == 'skills-locked':
        return make_check(
            'kit', 'Kit', ATTENTION,
            'Some skill folders in your business folder are open in another program or locked, so Claude can\'t '
            'check them.',
            next_step="{} ({}). kit-sync's guide, \"If a skill folder is locked\": the member closes the program "
                      "or fixes the permissions, then run status again.".format(said, ', '.join(locked or []) or
                                                                               'see details'),
            member_next="Close the program that has them open (or fix the folder's permissions); Claude then checks "
                        "again.",
            short='some skill folders are locked', details=details)
    if verdict == 'plugin-version-unknown':
        return make_check(
            'kit', 'Kit', ATTENTION,
            "Your {} is installed, but this check couldn't tell whether it's the latest.".format(name),
            next_step="Couldn't compare the kit (core_version {}) with the plugin: neither kit-sync nor the plugin's "
                      ".claude-plugin/plugin.json was reachable from where setup_check.py ran. Run it again with "
                      "--plugin-version <the plugin's version>, or compare core_version by hand.".format(
                          details.get('kit_core_version')),
            member_next='Claude checks the kit version another way.',
            short="the kit's version couldn't be checked", details=details)
    lines = {
        'older': 'Your {} needs an update. Claude does it for you and keeps everything you made.'.format(name),
        'skills-missing': "Some of your kit's skills are missing. Claude puts them back with a kit update.",
        'skills-older': "Some of your kit's skills aren't the kit's version. Claude updates them and saves the old "
                        "copies.",
        'vip-machine-older': "Your VIP Machine's program is older than your kit. Claude updates it; your VIP Machine "
                             "records and settings stay as they are.",
        'claude-md-older': "Your CLAUDE.md still has an earlier kit's instructions. Claude replaces them with a kit "
                           "update and keeps your own notes.",
        'rules-older': "Your CLIENT_RULES.md doesn't have this kit's block of Caiman's rules yet. Claude adds it with a "
                       "kit update and keeps your own rules as they are.",
    }
    how = {
        'vip-machine-older': 'Run the kit-sync install again (or RUNTIME_UPDATE.py update from the business folder).',
    }.get(verdict, 'Update it with kit-sync (get_kit_download, then install), as the caiman skill, section 3, says.')
    return make_check(
        'kit', 'Kit', ATTENTION,
        lines.get(verdict, 'Your kit needs attention. Claude takes care of it with a kit update.'),
        next_step='{}{}. {} Then run the setup check again.'.format(
            said, '' if verdict in lines else " (a status this check doesn't know; read kit-sync's message)", how),
        member_next=KIT_UPDATE_NEXT, short='the kit needs an update', details=details)


def kit_from_status(data, tier, plugin):
    verdict = text_value(data.get('status')) or 'unknown'
    installed = as_dict(data.get('installed'))
    tier = tier or norm_tier(installed.get('tier'))
    number = text_value(installed.get('version'))
    core = text_value(installed.get('core_version'))
    plugin = text_value(data.get('plugin_version')) or plugin
    details = {'source': 'kit-sync status', 'kit_sync_status': verdict, 'tier': tier, 'kit_version': number,
               'kit_core_version': core, 'plugin_version': plugin, 'kit_sync_message': data.get('message')}
    if verdict == 'current' and not text_value(data.get('plugin_version')):
        verdict = compare_versions(core, plugin)    # kit-sync couldn't see the plugin, so it didn't compare
        details['compared_by'] = 'setup_check.py'
    leftovers = []
    for key, one, many in (('earlier_kit_files', 'file from the July to September 2026 kits',
                            'files from the July to September 2026 kits'),
                           ('old_skill_copies', 'unchanged skill copy from earlier kits',
                            'unchanged skill copies from earlier kits'),
                           ('retired_parts', 'retired kit part', 'retired kit parts')):
        if data.get(key):
            count = len(data[key]) if isinstance(data[key], list) else 1
            leftovers.append('{} {}'.format(count, plural(count, one, many)))
            details[key] = data[key]
    for key in ('missing_skills', 'older_skills', 'locked_skills'):
        if data.get(key):
            details[key] = data[key]
    return kit_result(verdict, tier, number, plugin, details, leftovers, data.get('locked_skills'))


def kit_from_files(root, tier, plugin, why):
    """The fallback: compare core_version in RELEASE_MANIFEST.json with the plugin's version."""
    details = {'source': 'RELEASE_MANIFEST.json', 'tier': tier, 'plugin_version': plugin,
               'kit_sync': "kit-sync status didn't run: {}".format(why)}
    manifest_path = root / 'RELEASE_MANIFEST.json'
    manifest = read_json(manifest_path)
    if not isinstance(manifest, dict):
        versions = root / '.caiman' / 'kit-versions'
        try:
            side = versions.is_dir() and any(
                (child / 'RELEASE_MANIFEST.json').is_file() or (child / 'CLIENT_START.py').is_file()
                for child in versions.iterdir() if child.is_dir())
        except OSError:
            side = False
        if side:
            details['source'] = 'a kit an older installer put in .caiman/kit-versions/'
            return kit_result('older', tier, None, plugin, details)
        if manifest_path.exists():
            return make_check(
                'kit', 'Kit', ATTENTION, "Claude couldn't read your kit's version file, so it can't tell which kit "
                                         "you have.",
                next_step="RELEASE_MANIFEST.json is there but can't be read as JSON. Run kit-sync status; the kit-sync "
                          "install puts a good copy back.",
                member_next=KIT_UPDATE_NEXT, short="the kit's version file can't be read",
                details=dict(details, kit_verdict='manifest-unreadable'))
        return kit_result('missing', tier, None, plugin, details)
    tier = tier or norm_tier(manifest.get('kit')) or norm_tier(manifest.get('tier'))
    number = text_value(manifest.get('version'))
    core = text_value(manifest.get('core_version')) or text_value(as_dict(manifest.get('plugin')).get('version'))
    details.update(tier=tier, kit_version=number, kit_core_version=core)
    return kit_result(compare_versions(core, plugin), tier, number, plugin, details)


def check_kit(root, tier, plugin):
    program = find_kit_sync()
    why = 'kit_sync.py is not next to this script (../../kit-sync/scripts/kit_sync.py)'
    if program is not None:
        code, out, err, failed = run_program(
            [python_command(), '-B', str(program), 'status', '--folder', str(root), '--json'], root, KIT_SYNC_SECONDS)
        data = json_from(out)
        if failed:
            why = 'kit_sync.py status: ' + failed
        elif data is None or not text_value(data.get('status')):
            why = 'kit_sync.py status answered in a way this check can\'t read (exit {}): {}'.format(
                code, one_line(err or out, 300))
        elif data.get('status') in ('error', 'needs-confirmation'):
            why = 'kit_sync.py status stopped: {}'.format(one_line(data.get('message'), 300))
        else:
            return kit_from_status(data, tier, plugin)
    result = kit_from_files(root, tier, plugin, why)
    if program is not None and result['status'] == OK:
        # kit-sync is here but didn't answer: the versions match, but its fuller check (skills, VIP Machine,
        # CLAUDE.md) didn't run, so this isn't an all-clear.
        return make_check(
            'kit', 'Kit', ATTENTION,
            "Your {} looks up to date, but Claude couldn't run the full kit check.".format(
                kit_name(result['details'].get('tier'), result['details'].get('kit_version'))),
            next_step="kit-sync status didn't run ({}). The kit's core_version matches the plugin, but its skills, "
                      "VIP Machine and CLAUDE.md weren't checked. Run it yourself: python3 \"{}\" status --folder "
                      "\"<business folder>\", and act on its status (the caiman skill, section 3).".format(
                          why, program),
            member_next='Claude runs the kit check again and tells you if anything needs updating.',
            short="the full kit check didn't run", details=dict(result['details'], kit_verdict='not-checked'))
    result['next_step'] += " (kit-sync status didn't run, so this compares versions only: {})".format(why)
    return result


RELEASE_NAME = re.compile(r'\b(\d{4}-\d{2}-\d{2})-(vip|gls-plus)-v(\d+)\b')


def live_kit_from(text):
    """{'release', 'tier', 'number'} from --live-kit: a release name, or @ and a file (or JSON) holding
    get_kit_download's result. Only the release name is read from it; the download link is never kept."""
    raw = (text or '').strip()
    if raw.startswith('@'):
        try:
            with open(os.path.expanduser(raw[1:].strip()), 'r', encoding='utf-8-sig') as handle:
                raw = handle.read(2 * 1024 * 1024)
        except OSError:
            return None
    match = RELEASE_NAME.search(raw)
    if not match:
        return None
    return {'release': match.group(0), 'tier': match.group(2), 'number': int(match.group(3))}


def kit_number(value):
    match = re.fullmatch(r'v?(\d+)', text_value(value) or '')
    return int(match.group(1)) if match else None


def with_live_kit(kit, lives, unreadable, tier, connector):
    """The kit check, compared with the kit members get now (the release given for this folder's membership). A
    newer kit on the server is a kit update due now, even when the folder's kit matches this plugin."""
    details = kit['details']
    folder_tier = tier or details.get('tier')
    live = lives.get(folder_tier) if folder_tier else (next(iter(lives.values())) if len(lives) == 1 else None)
    if live is None:
        if kit['status'] != PROBLEM and (lives or unreadable or connector == 'ok'):
            details['live_kit'] = 'not checked'
            if unreadable:
                details['live_kit_note'] = "--live-kit couldn't be read ({}); a release looks like 2026-10-14-vip-v56".format(
                    ', '.join(unreadable))
            elif lives:
                details['live_kit_note'] = 'no release was given for this membership'
            kit['next_step'] = (kit.get('next_step') or '') + (
                " The kit wasn't compared with the one members get now. Next session, pass --live-kit with the release "
                "get_kit_download names for this folder's membership; if that tool isn't listed or fails, carry on "
                'without it.')
        return kit
    details['live_kit'] = live['release']
    have = kit_number(details.get('kit_version'))
    if kit['status'] == PROBLEM or have is None or have >= live['number']:
        return kit
    name = kit_name(folder_tier or live['tier'], None)
    details['kit_status'] = 'update_due'
    return make_check(
        'kit', 'Kit', ATTENTION,
        'A newer {} is out (version {}; this folder has version {}). Claude updates it now and keeps everything you '
        'made.'.format(name, live['number'], have),
        next_step='The kit members get now is {} and this folder has kit {}. Update it now, before anything else in '
                  'this session (Deep Seed and the member\'s request included): call get_kit_download for a fresh link '
                  'and run the kit-sync install (the caiman skill, section 3). If kit-sync says the new kit goes with a '
                  'newer Caiman plugin, it still installs; tell the member to update the plugin (Customize, Plugins, '
                  'Caiman, Update) and start a new task, and if Update says Caiman is already current, take them through '
                  'the kit\'s TROUBLESHOOTING.md, "The Caiman plugin won\'t update". Then run the setup check again. In a '
                  'scheduled or routine run, don\'t '
                  'update: say in the run\'s summary that a newer kit is due; the next session with the member updates it.'.format(live['release'], have),
        member_next=KIT_UPDATE_NEXT, short='a newer kit is out', details=details)


def kit_report(kit, plugin, status):
    """What record_kit_state receives: versions and statuses only, nothing about the business."""
    details = as_dict((kit or {}).get('details'))
    live = details.get('live_kit')
    state = details.get('kit_status') or {OK: 'current'}.get((kit or {}).get('status')) or (
        text_value(details.get('kit_sync_status')) or ('missing' if (kit or {}).get('status') == PROBLEM else 'attention'))
    return {'kit_tier': details.get('tier'), 'kit_version': kit_number(details.get('kit_version')),
            'live_kit_release': live if isinstance(live, str) and RELEASE_NAME.fullmatch(live) else None,
            'kit_status': state, 'setup_status': status}


WORKSPACE_ID_FILE = '.caiman/workspace-id.json'
FOLDER_ID_KEYS = ('folder_id', 'deep_seed', 'store_id')
NEXT_STEP_KEY = 'next_step'                         # Caiman 0.3.38, sent once the tool lists it
EXTRA_KEYS = FOLDER_ID_KEYS + (NEXT_STEP_KEY,)
# The kinds of step a folder can wait for, most pressing first (a problem always comes before an attention item).
NEXT_STEP_REASONS = ('kit_update', 'plugin_update', 'connect_seller_central', 'connect_ads', 'deep_seed',
                     'vip_machine_setup', 'other', 'reports_due')
# The kit check's verdicts that a kit update (kit-sync's install) puts right: kit_update. A kit newer than the plugin is a
# plugin update; the other kit lines (the other membership's kit, a skills folder Claude can't read or that is locked, a
# version that couldn't be compared, a check that broke) are other.
KIT_UPDATE_VERDICTS = ('current', 'missing', 'older', 'skills-missing', 'skills-older', 'vip-machine-older',
                       'claude-md-older', 'rules-older', 'manifest-unreadable')


def folder_id(root):
    """The folder's stable ID: the one kit-sync made when it installed the kit (.caiman/workspace-id.json, kept by every
    update). Never made here: a folder without a kit has none yet, and a damaged or unreadable file gives None."""
    try:
        data = as_dict(read_json(Path(root) / WORKSPACE_ID_FILE))
        if data.get('schema') != 'caiman.workspace-id.v1':
            return None
        return str(uuid.UUID(str(data.get('id'))))
    except Exception:                               # a file that can't be read is an unknown ID, never a stopped check
        return None


def deep_seed_state(checks):
    """'done' when the Deep Seed check is ok and its last step on VIP (the VIP Machine) isn't open, the same test as the
    Deep Seed line's "done apart from its last step"; 'not_finished' when Deep Seed or that last step is still to do; None
    when the check didn't run or broke (unknown, never "not finished")."""
    deep = next((item for item in checks if item.get('id') == 'deep_seed'), None)
    details = as_dict((deep or {}).get('details'))
    if not deep or deep.get('status') not in (OK, ATTENTION) or details.get('error'):
        return None                                 # not run, or the check broke (guarded() answers attention + error)
    if deep['status'] == ATTENTION:
        return 'not_finished'
    # deep_seed_last_step's own test, so this always agrees with the Deep Seed line in CAIMAN STATUS.md.
    open_step = 'business_view' in details and any(
        item.get('id') == 'vip_machine' and item.get('status') != OK and LAST_STEP in (item.get('member_line') or '')
        for item in checks)
    return 'not_finished' if open_step else 'done'


def store_slug(checks):
    """The connector brand slug this folder works on, as the connector check matched it: the slug a VIP Machine is linked
    to, else the folder's own saved slug, and only when list_brands returned it and the check is ok. None otherwise (no
    account chosen yet, a files-only view, an older account name still to confirm, or another brand's slug)."""
    connector = next((item for item in checks if item.get('id') == 'connector'), None) or {}
    details = as_dict(connector.get('details'))
    if details.get('connector') != 'ok':
        return None
    returned = [value for value in (details.get('brands_returned') or []) if isinstance(value, str)]
    # with_connections records the slug it matched (it runs only after a match), also when a connection the
    # membership needs is off and the check says attention or problem: the store is known, its connection isn't on.
    listed = text_value(as_dict(details.get('connections')).get('brand_slug'))
    if listed and listed in returned:
        return listed
    if connector.get('status') != OK:
        return None
    for candidate in (details.get('connector_slug'), details.get('saved_slug')):
        value = text_value(candidate)
        if value and value in returned:
            return value
    return None


def check_reason(item):
    """The kind of step one open check line waits for (Caiman 0.3.38)."""
    kind, details = item.get('id'), as_dict(item.get('details'))
    if kind == 'kit':
        verdict = details.get('kit_verdict')
        if details.get('kit_status') == 'update_due' and not details.get('error'):
            return 'kit_update'                     # a newer kit is out (--live-kit)
        if details.get('error') or verdict not in KIT_UPDATE_VERDICTS + ('newer',):
            return 'other'
        return 'plugin_update' if verdict == 'newer' else 'kit_update'
    if kind == 'connector':
        off = details.get('not_connected') or []
        if 'Seller Central' in off:
            return 'connect_seller_central'
        return 'connect_ads' if 'Amazon Ads' in off else 'other'
    if kind == 'deep_seed':
        return 'deep_seed'
    if kind == 'vip_machine':
        if LAST_STEP in (item.get('member_line') or ''):
            return 'vip_machine_setup'
        return 'reports_due' if details.get('preflight_status') == 'refresh-required' else 'other'
    if kind == 'ratings':
        return 'reports_due'                        # read again at the weekly review, like the reports
    return 'other'


def next_step_reason(checks):
    """What the folder waits for, in one word for the Caiman portal (Caiman 0.3.38): none when every line is ok, else the
    most pressing open line's kind: a problem before an attention item, then NEXT_STEP_REASONS' order. reports_due is
    last: the weekly review refreshes them on its own, so a folder whose only items are reports due is set up."""
    open_items = [item for item in checks if item.get('status') in (PROBLEM, ATTENTION)]
    if not open_items:
        return 'none'
    rank = min((0 if item['status'] == PROBLEM else 1, NEXT_STEP_REASONS.index(check_reason(item)))
               for item in open_items)
    return NEXT_STEP_REASONS[rank[1]]


def folder_fields(root, checks):
    """What record_kit_state takes once the connector lists them (Caiman 0.3.33, for the portal's setup checks; next_step
    from Caiman 0.3.38), or None if working them out failed: then only today's call is offered."""
    try:
        fields = {'folder_id': folder_id(root), 'deep_seed': deep_seed_state(checks), 'store_id': store_slug(checks)}
    except Exception:                               # these fields never stop the setup check
        return None
    try:
        fields[NEXT_STEP_KEY] = next_step_reason(checks)
    except Exception:                               # an unknown step is left out, never a stopped check
        fields[NEXT_STEP_KEY] = None
    return fields


def report_call(plugin, folders, with_ids=None):
    """The record_kit_state call. arguments is what the tool takes today (the tool refuses any field it doesn't list);
    arguments_with_folder_ids adds each folder's ID, Deep Seed and store, for once the tool lists folder_id, and
    arguments_with_next_step (Caiman 0.3.38) adds each folder's next_step as well, for once the tool lists that too. A
    field that isn't known is left out, never sent as null."""
    call = {'tool': 'record_kit_state', 'arguments': {'plugin_version': plugin, 'folders': folders},
            'then': 'Call it once after this check when the Caiman connector lists record_kit_state; skip it '
                    'otherwise. It carries version numbers only.'}
    if with_ids and len(with_ids) == len(folders):
        def entries(keys):
            return [dict(entry, **{key: value for key, value in extra.items() if key in keys and value is not None})
                    for entry, extra in zip(folders, with_ids)]
        call['arguments_with_folder_ids'] = {'plugin_version': plugin, 'folders': entries(FOLDER_ID_KEYS)}
        if any(extra.get(NEXT_STEP_KEY) is not None for extra in with_ids):
            call['arguments_with_next_step'] = {'plugin_version': plugin, 'folders': entries(EXTRA_KEYS)}
        call['then'] = ('Call it once after this check when the Caiman connector lists record_kit_state; skip it '
                        'otherwise. Only when the tool\'s folders entries list all three of folder_id, deep_seed and '
                        'store_id, send arguments_with_folder_ids exactly as given, never adding a field it leaves '
                        'out; when they list next_step as well, send arguments_with_next_step the same way instead; '
                        'otherwise send arguments exactly as given, since the tool refuses fields it '
                        'doesn\'t list. If the call with folder IDs is refused, send arguments once instead. Never retry '
                        'otherwise. It carries version numbers and statuses, each folder\'s ID, the store it works on '
                        'and the kind of step it waits for: nothing about the business.')
    return call


# ---------------------------------------------------------------- flags the member said yes to sending (Caiman 0.3.36)

# A flag's line in outputs/flags.md (the caiman skill, "Offer to send it to the Caiman team"), one line:
#   - 2026-10-27 (rule) Budget raise held for stock: <what happened, with the numbers or the error, what it costs, what
#     you'd do instead> (where: <the workflow's name, or setup, and the file name of the skill, guide or script>)
# A line with no ending hasn't been offered yet. It ends [to send] once the member says go and until it goes, then
# [sent <date>]; [not sent] when they say no, or [not sent: refused <reason>] when the tool refused what it holds. The
# where part is how the Caiman team finds the file at fault, so it travels as its own field too.
FLAGS_FILE = 'outputs/flags.md'
FLAG_TOOL = 'report_flag'
TO_SEND_MARK = '[to send]'
FLAG_BULLET = re.compile(r'^\s*[-*+]\s+(\S.*)$')
FLAG_DATE = re.compile(r'^(\d{4}-\d{2}-\d{2})\b[\s,.;:]*')
FLAG_KIND = re.compile(r'^\((rule|problem|idea)\)[\s,.;:]*', re.IGNORECASE)
FLAG_WHERE = re.compile(r'\(where:\s*((?:[^()]|\([^()]*\))*?)\s*\)', re.IGNORECASE)   # one level of (...) inside
FLAG_EMAIL = re.compile(r'\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b')
FLAG_ORDER_ID = re.compile(r'\b\d{3}-\d{7}-\d{7}\b')   # an Amazon order ID points at a buyer
MAX_FLAGS_BYTES = 512 * 1024
MAX_FLAG_LINE = 20000                               # a flag is one short line; a longer one is read cut to this
MAX_FLAG_SENDS = 20                                 # per folder and check; more_waiting counts the rest
MAX_FLAG_SUMMARY = 200
MAX_FLAG_DETAILS = 4000
MAX_FLAG_WHERE = 200
MAX_FLAG_CONTEXT = 300
FLAG_THEN = ('The member already said go to sending each of these to the Caiman team. When the Caiman connector lists '
             'report_flag, make each call once with its arguments exactly as given, then in its file change that line\'s '
             '"[to send]" to "[sent <today\'s date as YYYY-MM-DD>]" and tell the member in a line which went. When the '
             'connector doesn\'t list report_flag, leave them as they are: they go once it does. If a call is refused for '
             'now (a time-out, or the day\'s limit), leave its line [to send], say so in a line and don\'t retry it in '
             'this session; if it is refused for what it holds (a field or a value the tool doesn\'t take), end the line '
             '"[not sent: refused <the reason in a few words>]" and say so. When more_waiting is there, run '
             'setup_check.py --flags-only again after marking these, for the rest.')


def pending_flags(root):
    """([(line number, text)], note) for the lines of the folder's outputs/flags.md that end with [to send]: the member
    said go to sending them and they haven't gone yet. The text is the line without its bullet and ending. A missing file
    gives none; one that can't be read or is too big gives none and a note that says so. It never stops the check."""
    path = Path(root) / FLAGS_FILE
    try:
        if path.is_symlink() or not path.is_file():
            return [], None
        if path.stat().st_size > MAX_FLAGS_BYTES:
            return [], ('{} is over {} KB, so the flags waiting in it weren\'t read; ask the member to move older lines '
                        'out of it'.format(FLAGS_FILE, MAX_FLAGS_BYTES // 1024))
        lines = path.read_text(encoding='utf-8', errors='replace').splitlines()
    except OSError as error:
        return [], '{} couldn\'t be read: {}'.format(FLAGS_FILE, one_line(error, 200))
    found = []
    for number, line in enumerate(lines, 1):
        stripped = line.rstrip()
        if not stripped.lower().endswith(TO_SEND_MARK):
            continue
        bullet = FLAG_BULLET.match(stripped[:-len(TO_SEND_MARK)][:MAX_FLAG_LINE])
        text = bullet.group(1).rstrip() if bullet else ''
        if text:
            found.append((number, text))
    return found, None


def runtime_words():
    """Where the kit's scripts run, for the Caiman team's diagnosis: the operating system and Python, never a name or a
    path (for example "macOS 14.6.1; Python 3.12.4", "Windows 11; Python 3.13.0", "Linux 6.8.0; Python 3.11.9")."""
    system = platform.system() or 'unknown system'
    if system == 'Darwin':
        system = 'macOS ' + (platform.mac_ver()[0] or platform.release())
    elif system in ('Windows', 'Linux'):
        system = '{} {}'.format(system, platform.release())
    return one_line('{}; Python {}'.format(system.strip(), '.'.join(str(part) for part in sys.version_info[:3])), 64)


def flag_redact(text, limit):
    """What a flag sends, made safe to leave the folder: each link cut to its host, tokens, keys and passwords hidden,
    emails and Amazon order IDs hidden, on one line and cut to limit. A file path stays (it helps find the cause)."""
    text = ' '.join(str(text or '').split())
    text = re.sub(r'(?i)\b(https?://)(?:[^\s/@]+@)?([^\s/?#]+)\S*', r'\1\2/...', text)
    # A link written without https:// (tools.example.ai/d/1?sig=...) is cut to its host too; a file path has no host.
    text = re.sub(r'(?i)(?<![\w@/.:-])((?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,})(?::\d+)?[/?#]\S*', r'\1/...', text)
    text = re.sub(r'(?i)\b(bearer|basic)\s+[^\s",;()\[\]]+', r'\1 [hidden]', text)
    # A key, token or password named on its own or inside a longer name (client_secret, aws_secret_access_key).
    text = re.sub(r'(?i)(?<![A-Za-z0-9])([A-Za-z0-9_-]*(?:token|authorization|api[_-]?key|access[_-]?key|private[_-]?key|'
                  r'secret|password|passwd|credential|signature)[A-Za-z0-9_-]*|sig)(\s*[:=]\s*)("?)(?!bearer\b|basic\b)'
                  r'[^\s",;&()\[\]]+', r'\1\2\3[hidden]', text)
    text = FLAG_EMAIL.sub('[email hidden]', text)
    text = FLAG_ORDER_ID.sub('[order ID hidden]', text)
    text = re.sub(r'[A-Za-z0-9+_=-]{40,}', '[hidden]', text)     # a long token (a path's parts are shorter)
    return text if len(text) <= limit else text[:limit - 3].rstrip() + '...'


def setup_context(status, checks):
    """The setup check's result in one short line ("setup check attention: python ok, kit ok, connector attention"), so
    a flag says how the folder stood; None when unknown."""
    parts = ['{} {}'.format(key, value) for key, value in sorted((checks or {}).items(), key=lambda item: str(item[0]))
             if isinstance(key, str) and isinstance(value, str)]   # sorted: the same however the result was saved
    if not status and not parts:
        return None
    return one_line('setup check {}: {}'.format(status or 'unknown', ', '.join(parts) or 'no checks recorded'),
                    MAX_FLAG_CONTEXT)


def flag_arguments(text, plugin, tier, kit_version, folder, store, runtime=None, context=None):
    """report_flag's arguments for one flag line: its kind (rule, problem or idea, before or after the date; a line
    without one is a rule), its summary (the words before the first colon, with the where part and any date and kind
    left out), the line itself as details, where in Caiman it comes from (its "(where: ...)" part), the date it carries,
    the folder's versions, ID and store, its setup check result, where the scripts run, and client_ref: the same for the
    same line in the same folder however it's sent, so a call made twice is one report. What leaves is cleaned of links,
    tokens, emails and order IDs (flag_redact). A field that isn't known is left out, never sent as null."""
    wheres = list(FLAG_WHERE.finditer(text))
    where = one_line(wheres[-1].group(1), MAX_FLAG_WHERE) if wheres else ''
    rest = FLAG_WHERE.sub(' ', text).strip()
    flagged_on, kind = None, None
    for _ in range(2):                              # the date and the kind, in either order
        date = FLAG_DATE.match(rest)
        if date and flagged_on is None:
            rest = rest[date.end():]
            try:
                flagged_on = dt.date(*(int(part) for part in date.group(1).split('-'))).isoformat()
            except ValueError:                      # not a real day: the line still goes, without a date
                flagged_on = ''
            continue
        found = FLAG_KIND.match(rest)
        if found and kind is None:
            rest = rest[found.end():]
            kind = found.group(1).lower()
            continue
        break
    head, colon, _ = rest.partition(': ')
    summary = re.sub(r'\*\*|__|`', '', head if colon else rest).strip(' .,;:') or rest.strip() or text
    ref = hashlib.sha256('\n'.join((folder or '', text)).encode('utf-8')).hexdigest()[:32]
    values = {'kind': kind or 'rule', 'summary': flag_redact(summary, MAX_FLAG_SUMMARY),
              'details': flag_redact(text, MAX_FLAG_DETAILS), 'where': flag_redact(where, MAX_FLAG_WHERE) or None,
              'flagged_on': flagged_on or None, 'plugin_version': one_line(plugin, 32) if plugin else None,
              'kit_tier': tier, 'kit_version': kit_version, 'folder_id': folder, 'store_id': store,
              'context': context, 'runtime': runtime, 'client_ref': ref}
    return {key: value for key, value in values.items() if value is not None}


def flag_reports(root, plugin, tier, kit_version, folder, store, context=None):
    """The report_flag calls for this folder's lines marked [to send], each with its file and line number (with a note
    when the file couldn't be read), or None when there is nothing to send or say."""
    pending, note = pending_flags(root)
    if not pending and not note:
        return None
    path = str(Path(root) / FLAGS_FILE)
    try:
        runtime = runtime_words()
    except Exception:                               # an unknown runtime is left out
        runtime = None
    report = {'tool': FLAG_TOOL, 'then': FLAG_THEN, 'calls': [
        {'file': path, 'line': number,
         'arguments': flag_arguments(text, plugin, tier, kit_version, folder, store, runtime, context)}
        for number, text in pending[:MAX_FLAG_SENDS]]}
    if len(pending) > MAX_FLAG_SENDS:
        report['more_waiting'] = len(pending) - MAX_FLAG_SENDS
    if note:
        report['notes'] = ['{}: {}'.format(path, note)]
    return report


def merged_flag_reports(reports):
    """One flag_reports answer from several business folders' (a workspace), or None when none has a flag to send or a
    note."""
    reports = [item for item in reports if isinstance(item, dict) and (item.get('calls') or item.get('notes'))]
    if not reports:
        return None
    merged = {'tool': FLAG_TOOL, 'then': FLAG_THEN, 'calls': [call for item in reports for call in item['calls']]}
    more = sum(item.get('more_waiting') or 0 for item in reports)
    if more:
        merged['more_waiting'] = more
    notes = [note for item in reports for note in item.get('notes') or []]
    if notes:
        merged['notes'] = notes
    return merged


def saved_flag_fields(root):
    """(tier, kit number, folder ID, store, setup check result) from the folder's saved files, for --flags-only: the
    kit's manifest, the ID kit-sync keeps, and the store and result the last setup check saved (.caiman/setup-check.json)."""
    manifest = as_dict(read_json(Path(root) / 'RELEASE_MANIFEST.json'))
    number = kit_number(manifest.get('version'))
    if number is None and isinstance(manifest.get('kit_number'), int) and not isinstance(manifest['kit_number'], bool):
        number = manifest['kit_number']
    record = as_dict(read_json(Path(root) / RESULT_FILE))
    store = text_value(as_dict(record.get('connections')).get('brand_slug'))
    context = setup_context(text_value(record.get('status')), as_dict(record.get('checks')))
    return folder_tier(Path(root)), number, folder_id(root), store, context


def flags_only(args):
    """--flags-only: the flag_reports calls for the folder (each brand's, at a workspace), from its saved files, without
    the checks and writing nothing."""
    root = Path(os.path.abspath(os.path.expanduser(args.project_root.strip())))
    plugin = plugin_version(args.plugin_version)[0]
    folders = workspace_brands(root)
    if not (len(folders) >= 2 or (folders and (root / WORKSPACE_FILE).is_file())):
        folders = [root]
    reports = []
    for folder in folders:
        try:
            reports.append(flag_reports(folder, plugin, *saved_flag_fields(folder)))
        except Exception:                           # one folder's file breaking never hides another's
            reports.append(None)
    merged = merged_flag_reports(reports)
    answer = {'flags_only': True, 'business_folder': str(root), 'plugin_version': plugin}
    if merged:
        answer['flag_reports'] = merged
    if not merged or not merged['calls']:
        answer['note'] = 'No line in outputs/flags.md ends with [to send], so there is nothing to send.'
    return answer


# ---------------------------------------------------------------- 4. the connector

# Amazon marketplace IDs and the country codes the kit saves with a source list (as in READ_ONLY_REVIEW.py and
# the VIP Machine). UK, GB and A1F83G8C2ARO7P name the same marketplace.
MARKETPLACE_CODES = {
    'ATVPDKIKX0DER': 'US', 'A2EUQ1WTGCTBG2': 'CA', 'A1AM78C64UM0Y8': 'MX', 'A2Q3Y263D00KWC': 'BR',
    'A1F83G8C2ARO7P': 'UK', 'GB': 'UK', 'A1PA6795UKMFR9': 'DE', 'A13V1IB3VIYZZH': 'FR', 'APJ6JRA9NG5V4': 'IT',
    'A1RKKUPIHCS9HS': 'ES', 'A1805IZSGTT6HS': 'NL', 'A2NODRKZP88ZB9': 'SE', 'A1C3SOZRARQ6R3': 'PL',
    'AMEN7PMS3EDWL': 'BE', 'A28R8C7NBKEWEA': 'IE', 'A33AVAJ2PDY3EV': 'TR', 'A2VIGQ35RCS4UG': 'AE',
    'A17E79C6D8DWNP': 'SA', 'ARBP9OOSHTCHU': 'EG', 'A21TJRUUN4KGV': 'IN', 'A1VC38T7YXB528': 'JP',
    'A39IBJ37TRP1C6': 'AU', 'A19VAU5U5O7RUS': 'SG'}
MAX_VIEW_BYTES = 64 * 1024 * 1024


def brands_from_json(text):
    """[{'slug', 'name', 'marketplace'}] from --connector-brands-json: a JSON list of the brands list_brands returned,
    list_brands' own answer ({"items": [...]}), or @ and the path of a file holding either. ValueError when unreadable."""
    raw = text.strip()
    if raw.startswith('@'):
        try:
            with open(os.path.expanduser(raw[1:].strip()), 'r', encoding='utf-8-sig') as handle:
                raw = handle.read()
        except OSError as error:
            raise ValueError("the file {} can't be read ({})".format(raw[1:].strip(), error.strerror or error))
    # The connector's answer can start with a line of text ("Found 2 brand(s).") before its JSON.
    starts = [at for at in (raw.find('['), raw.find('{')) if at >= 0]
    try:
        value = json.JSONDecoder().raw_decode(raw[min(starts):])[0] if starts else json.loads(raw)
    except ValueError as error:
        raise ValueError("it isn't readable JSON ({})".format(error))
    if isinstance(value, dict):
        value = value.get('items') if isinstance(value.get('items'), list) else value.get('brands')
    if not isinstance(value, list):
        raise ValueError('it should be a list of brands')
    brands, seen = [], set()
    for item in value:
        item = as_dict(item)
        slug = text_value(item.get('slug')) or text_value(item.get('brand_slug'))
        if slug and slug not in seen:
            seen.add(slug)
            brands.append({'slug': slug, 'name': text_value(item.get('display_name')) or text_value(item.get('name')),
                           'marketplace': text_value(item.get('marketplace_id')) or text_value(item.get('marketplace')),
                           # Whether Seller Central and Amazon Ads are connected for it (None when list_brands didn't say).
                           'sp_api_authorized': item.get('sp_api_authorized') if isinstance(item.get('sp_api_authorized'), bool) else None,
                           'ads_authorized': item.get('ads_authorized') if isinstance(item.get('ads_authorized'), bool) else None})
    if value and not brands:
        raise ValueError('none of its brands has a slug')
    return brands


def market_code(value):
    """The country code of a marketplace ID or country code (GB and UK are the same), else None."""
    text = (text_value(value) or '').upper()
    return MARKETPLACE_CODES.get(text) or (text if re.fullmatch(r'[A-Z]{2}', text) else None)


def name_key(value):
    """A brand name ready to compare: lower case, without spaces or punctuation ("Acme + Outdoors" = "acme outdoors")."""
    return re.sub(r'[\W_]+', '', (text_value(value) or '').casefold())


def saved_names_and_markets(root, tier):
    """The brand names and marketplaces this folder saved: in its source lists, its latest business view and, outside
    VIP, GLS_PLUS_CONFIG.json. Template placeholders (REPLACE_...) don't count."""
    identities = [identity for identity, _ in saved_identities(root)]
    views = business_views(root)
    if views:
        view = root / views[0][1]
        try:
            small = view.stat().st_size <= MAX_VIEW_BYTES
        except OSError:
            small = False
        if small:
            identities.append(as_dict(as_dict(read_json(view)).get('identity')))
    if tier != 'vip':
        identities.append(as_dict(as_dict(read_json(root / 'GLS_PLUS_CONFIG.json')).get('identity')))
    names, markets = [], []
    for identity in identities:
        for value, found in ((identity.get('account_label'), names), (identity.get('brand_name'), names),
                             (identity.get('marketplace'), markets)):
            value = text_value(value)
            if value and not value.startswith('REPLACE_') and value not in found:
                found.append(value)
    return names, markets


def older_account_match(root, tier, brands):
    """The one listed brand this folder's saved brand name and marketplace point to, else None.

    Some older kits saved the source list under an ID shaped like a slug that isn't the brand's slug now: the
    slug from before the store was connected again, or an ID made from the brand name. It counts as that brand
    only when the folder's saved brand name matches exactly one listed brand's display_name (ignoring case,
    spaces and punctuation) and the folder's marketplace is that brand's marketplace."""
    names, markets = saved_names_and_markets(root, tier)
    keys = {name_key(name) for name in names} - {''}
    codes = {market_code(market) for market in markets}
    if not keys or len(codes) != 1 or None in codes:
        return None
    hits = [brand for brand in brands if name_key(brand['name']) in keys]
    if len(hits) != 1 or market_code(hits[0]['marketplace']) not in codes:
        return None
    key = name_key(hits[0]['name'])
    return dict(hits[0], saved_names=[name for name in names if name_key(name) == key], saved_marketplace=sorted(codes)[0])


CONNECTOR_LINK = 'state/connector_binding.json'
LINK_KEYS = {'schema_version', 'record_type', 'identity_hash', 'brand_slug', 'connector_slug', 'linked_at', 'checked_with',
             'receipts', 'source_file_sha256s', 'reason', 'replaces', 'binding_sha256'}


def canonical_sha(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'),
                                     allow_nan=False).encode('utf-8')).hexdigest()


def machine_link(root):
    """(linked slug, None), (None, why it doesn't check out) or (None, None): the connector slug the VIP Machine is linked
    to (vip_machine.py link-connector-slug, Caiman 0.3.17 on). The VIP Machine's engine checks the saved reads inside the
    link too; this checks that it belongs to this machine and that its checksum holds."""
    machine, _name = machine_folder(root)
    path = machine / CONNECTOR_LINK
    if not os.path.lexists(str(path)):
        return None, None
    config = as_dict(read_json(machine / 'config' / 'brand.json'))
    record = read_json(path) if path.is_file() and not path.is_symlink() else None
    try:
        payload = {'brand_slug': config['brand']['slug'], 'seller_id': config['account_identity']['seller_id'],
                   'profile_id': config['account_identity']['profile_id'], 'marketplace_id': config['marketplace']['id']}
    except (KeyError, TypeError):
        return None, "the VIP Machine's settings can't be read"
    if not isinstance(record, dict) or set(record) != LINK_KEYS or record.get('schema_version') != 2 \
            or record.get('record_type') != 'connector_slug_link':
        return None, "it isn't in the form the VIP Machine saves"
    if record.get('identity_hash') != canonical_sha(payload) or record.get('brand_slug') != payload['brand_slug']:
        return None, "it belongs to another VIP Machine's account"
    slug = text_value(record.get('connector_slug'))
    if not slug or not slug_shaped(slug) or slug == payload['brand_slug']:
        return None, "its linked slug isn't a connector slug"
    if canonical_sha({key: record[key] for key in LINK_KEYS - {'binding_sha256'}}) != record.get('binding_sha256'):
        return None, "its checksum doesn't match: the file was changed after it was saved"
    return slug, None


def not_connected(brand, tier):
    """The Amazon connections this membership needs that list_brands shows off for the brand: VIP needs Seller Central and
    Amazon Ads; GLS+ needs Amazon Ads (its Seller Central reports are the member's downloads). Only an explicit false
    counts: a list_brands answer without the flags says nothing about them."""
    needed = (('sp_api_authorized', 'Seller Central'), ('ads_authorized', 'Amazon Ads'))
    return [name for key, name in needed if (tier == 'vip' or key == 'ads_authorized') and as_dict(brand).get(key) is False]


def joined(names):
    return ' and '.join(names)


def with_connections(check, brands, listed, tier, root, name):
    """The connector check for a business whose store list_brands shows (as listed): unchanged when every connection the
    membership needs is on (or list_brands didn't say), else the connection that's off, which only the member can make
    (Caiman 0.3.24: one brand's Amazon Ads was never connected, and the setup check didn't say so). Blocking everything
    the membership reads (VIP: Seller Central; GLS+: Amazon Ads), or a set-up VIP Machine's weekly reports, is a
    problem; Amazon Ads before the VIP Machine is set up is attention: Deep Seed carries on from Seller Central, and the
    VIP Machine, its last step, waits for it."""
    brand = next((item for item in brands if item['slug'] == listed), None)
    if brand is None or (brand.get('sp_api_authorized') is None and brand.get('ads_authorized') is None):
        return check
    details = check['details']
    details['connections'] = {'brand_slug': listed, 'seller_central': brand.get('sp_api_authorized'),
                              'amazon_ads': brand.get('ads_authorized')}
    off = not_connected(brand, tier)
    if not off:
        return check
    details['not_connected'] = off
    machine, _name = machine_folder(root)
    set_up = tier == 'vip' and (machine / 'config' / 'brand.json').is_file()
    shown = name or brand.get('name')
    isnt, one = ("isn't", True) if len(off) == 1 else ("aren't", False)
    if tier != 'vip':                                           # GLS+: Amazon Ads is all the connector reads
        status, blocked = PROBLEM, "so Claude can't read your ads yet"
        meanwhile = ('Meanwhile work from what is saved and the member\'s own Seller Central downloads (Business Reports, FBA '
                     'inventory, Search Query Performance); nothing from Amazon Ads can be read.' if tier == 'gls-plus' else
                     'Meanwhile work from what is saved in the folder; nothing from Amazon Ads can be read.')
    elif len(off) == 2:
        status, blocked = PROBLEM, "so Claude can't read your Amazon account yet"
        meanwhile = 'Meanwhile work only from what is saved in the folder and the files the member gives you.'
    elif off == ['Seller Central']:
        status, blocked = PROBLEM, "so Claude can't read your sales, stock, listings or finances yet"
        meanwhile = 'Meanwhile work from what is saved and from Amazon Ads; nothing from Seller Central can be read.'
    elif set_up:
        status, blocked = PROBLEM, "so Claude can't read your ads, and the VIP Machine's weekly review can't refresh them"
        meanwhile = ("Meanwhile don't refresh the VIP Machine's Ads reports or prepare ad changes; work that needs only Seller "
                     'Central can go on.')
    else:
        status = ATTENTION
        blocked = ("so Claude can't read your ads yet. Deep Seed carries on from Seller Central; the VIP Machine (Deep Seed's "
                   'last step) and the advertising work wait for it')
        meanwhile = ('Meanwhile carry on with Deep Seed from Seller Central (catalog, sales, stock, finances, Search Query '
                     'Performance) and leave the VIP Machine for now: it is set up from the saved Ads account read '
                     '(list_ads_profiles), which needs Amazon Ads connected.')
    flags = ', '.join(key + ' false' for key, label in (('sp_api_authorized', 'Seller Central'), ('ads_authorized', 'Amazon Ads'))
                      if label in off)
    return make_check(
        'connector', 'Caiman connector', status,
        "The Caiman connector shows this business's Amazon store{}, but {} {} connected to it, {}.".format(
            ' ({})'.format(shown) if shown else '', joined(off), isnt, blocked),
        next_step=('list_brands shows {} with {}: {} {} connected for this business. Only the member can connect {}, in their '
                   'Caiman account (the member portal: Tools > AI & MCP > Caiman MCP > Open, then connect {}). Amazon takes '
                   'about a day to switch {} on (connect today, live tomorrow), so ask for it now, in this reply. {} Call '
                   'list_brands again next session; this clears once it shows {} on.{}').format(
                       listed, flags, joined(off), isnt, 'it' if one else 'them', joined(off), 'it' if one else 'them',
                       meanwhile, 'it' if one else 'them',
                       '' if check['next_step'] == 'Nothing to do.' else ' ' + check['next_step']),
        member_next='Connect {} in your Caiman account. Amazon takes about a day to switch {} on (connect today, live '
                    'tomorrow); Claude checks again next session.'.format(joined(off), 'it' if one else 'them'),
        short='{} {} connected{} yet'.format(joined(off), isnt, ' for {}'.format(shown) if shown else ''),
        details=details)


def check_connector(args, root, tier):
    label = 'Caiman connector'
    if args.connector == 'not-connected':
        return make_check(
            'connector', label, PROBLEM,
            "The Caiman connector isn't turned on in this chat, so Claude can't read your Amazon account.",
            next_step='No Caiman connector tools are listed. Ask the member to turn on the Caiman connector in the '
                      "app's connector settings (setup check guide, section 5), then call list_brands and run the "
                      'setup check again.',
            member_next="Turn on the Caiman connector in the Claude app's connector settings; Claude then checks "
                        "again.",
            short="the Caiman connector isn't turned on", details={'connector': 'not-connected'})
    if args.connector == 'failed':
        error = redact(args.connector_error) if text_value(args.connector_error) else '(no error text given)'
        return make_check(
            'connector', label, PROBLEM,
            "The Caiman connector didn't work when Claude checked it, so Claude can't read your Amazon account right "
            "now.",
            next_step='list_brands failed: {}. Explain it in plain words. Setup check guide, section 5: if a store '
                      'connection is off, the member connects it again in their Caiman account; if the connector '
                      'timed out or is down, call list_brands again shortly. Run the setup check again once it '
                      'answers.'.format(error),
            member_next='Claude tells you what went wrong and what fixes it.',
            short="the Caiman connector didn't work", details={'connector': 'failed', 'error': error})
    brands = list(getattr(args, 'connector_brand_list', None) or [])
    slugs = [brand['slug'] for brand in brands]
    slugs += [part for part in re.split(r'[\s,]+', args.connector_brands or '') if part and part not in slugs]
    details = {'connector': 'ok', 'brands_returned': slugs}
    if not slugs:
        what = {'vip': 'your Amazon store (Seller Central and Amazon Ads)',
                'gls-plus': 'your Amazon Ads account'}.get(tier, 'your Amazon account')
        return make_check(
            'connector', label, PROBLEM, 'The Caiman connector works, but no Amazon account is connected to it yet.',
            next_step='list_brands returned no brands. The member connects {} in their Caiman account (setup check '
                      'guide, section 5); then call list_brands and run the setup check again.'.format(
                          'Seller Central and Amazon Ads' if tier == 'vip' else 'Amazon Ads' if tier == 'gls-plus'
                          else 'their Amazon account'),
            member_next='Connect {} in your Caiman account; Claude then checks again.'.format(what),
            short='no Amazon account is connected to the Caiman connector', details=details)
    if root is None:
        return make_check('connector', label, OK, 'The Caiman connector works.',
                          next_step="Not compared with the business folder's account, because the folder wasn't "
                                    "found.", details=details)
    slug, name, where = saved_account(root, tier)
    details.update(saved_slug=slug, saved_in=where)
    if slug is None:
        return make_check(
            'connector', label, OK,
            "The Caiman connector works. This business's Amazon account hasn't been chosen yet; setup does that with "
            "you.",
            next_step='No account is saved in this business folder yet (no VIP Machine brand.slug or saved source '
                      'list). Setup chooses it with the member from the {} list_brands returned.'.format(
                          plural(len(slugs), 'brand', '{} brands'.format(len(slugs)))),
            details=details)
    shown = ' ({})'.format(name) if name else ''
    if slug in slugs:
        return with_connections(make_check('connector', label, OK,
                                           "The Caiman connector works and shows this business's Amazon account{}.".format(shown),
                                           details=details), brands, slug, tier, root, name)
    linked, link_problem = machine_link(root) if where.endswith('config/brand.json') else (None, None)
    if linked:
        # A VIP Machine set up under another name, linked to the connector's slug for the store (Caiman 0.3.17 on).
        details['connector_slug'] = linked
        if linked in slugs:
            return with_connections(make_check(
                'connector', label, OK,
                "The Caiman connector works and shows this business's Amazon account{}, connected as {}.".format(shown, linked),
                next_step='The VIP Machine is set up as {} and linked to the connector slug {} (vip_machine.py '
                          'link-connector-slug), which list_brands shows. Use {} for every connector call for this '
                          'business.'.format(slug, linked, linked),
                details=details), brands, linked, tier, root, name)
        return make_check(
            'connector', label, PROBLEM,
            "The Caiman connector works, but it doesn't show this business's Amazon account{}.".format(shown),
            next_step="The VIP Machine ({}) is linked to the connector slug {}, which list_brands no longer shows ({}). A "
                      "store that was disconnected and connected again gets a new slug. If a listed slug is this store, "
                      "link it again with the member's go: read list_ads_profiles for it, then run vip_machine.py "
                      "link-connector-slug, which checks the Ads profile, seller and marketplace IDs first (the kit's "
                      "TROUBLESHOOTING.md, \"The brand's slug changed\"). Don't pull data for another brand meanwhile, "
                      "and never change the VIP Machine's settings yourself.".format(slug, linked, ', '.join(slugs)),
            member_next='Claude works out what changed (for example a store that was connected again) and tells you '
                        'what to do.',
            short="the Caiman connector doesn't show this business's Amazon account", details=details)
    if link_problem:
        details['connector_link_problem'] = link_problem
        return make_check(
            'connector', label, PROBLEM,
            "The Caiman connector works, but the VIP Machine's link to this business's Amazon account{} needs to be made "
            "again.".format(shown),
            next_step="The VIP Machine's connector link (VIP Machine/{}) doesn't check out ({}), so only its own slug ({}) "
                      "is accepted, and list_brands doesn't show that ({}). Link the connector's slug for this store again "
                      "with fresh reads and the member's go (vip_machine.py link-connector-slug; the kit's "
                      "TROUBLESHOOTING.md, \"The brand's slug changed\"). Never edit the file.".format(
                          CONNECTOR_LINK, link_problem, slug, ', '.join(slugs)),
            member_next="Claude checks the account details with the connector and links it again with your go.",
            short="the Caiman connector doesn't show this business's Amazon account", details=details)
    if not where.endswith('config/brand.json') and slug.startswith('local-'):
        # A files-only view: its local- ID names this folder's work, not an Amazon account.
        return make_check(
            'connector', label, OK,
            "The Caiman connector works. This folder's view was built from files you saved, so no Amazon account is "
            "linked to it yet.",
            next_step="The source list ({}) names a files-only view ('{}'), not an Amazon account. When the member "
                      "wants connected data, choose the brand with them from the list_brands slugs ({}).".format(
                          where, slug, ', '.join(slugs)),
            details=details)
    if not where.endswith('config/brand.json') and not slug_shaped(slug):
        # Only the VIP Machine's brand.slug is always a list_brands slug. Older kits saved the source list under
        # another account ID (an Ads profile ID or a seller ID, for example). A slug-shaped ID that isn't listed is
        # another brand, so it stays a problem below.
        return make_check(
            'connector', label, ATTENTION,
            "The Caiman connector works. This folder's saved reports are filed under an account name the connector "
            "doesn't use; Claude checks which brand this is before pulling new data.",
            next_step="The source list ({}) names the account '{}', which isn't among the list_brands slugs ({}). Older "
                      "kits saved another account ID there, which is fine: keep using it for this folder's files. "
                      "Before pulling data, confirm with the member which brand this folder is if more than one "
                      "brand is listed.".format(where, slug, ', '.join(slugs)),
            member_next='Nothing for you to do unless Claude asks which brand this folder is for.',
            short="this folder's saved reports use an older account name", details=details)
    match = older_account_match(root, tier, brands) if not where.endswith('config/brand.json') and brands else None
    if match:
        # Only a source list: a VIP Machine's brand.slug that isn't listed stays a problem below.
        details['looks_like'] = {'slug': match['slug'], 'display_name': match['name'],
                                 'marketplace_id': match['marketplace']}
        return make_check(
            'connector', label, ATTENTION,
            "The Caiman connector works. This folder's saved reports are filed under an older account name; it looks "
            "like {}. Claude confirms that with you before pulling new data.".format(match['name']),
            next_step="The source list ({}) names the account '{}', which isn't among the list_brands slugs ({}). It's "
                      "saved under an older account name; it looks like {} ({}): this folder's saved brand name ({}) "
                      "and marketplace ({}) match that brand and no other listed one. Claude confirms with the member "
                      "before pulling data: ask whether this folder is {}. Once they say yes, read the connector with "
                      "{} and keep registering this folder's reports under '{}', as its saved files are. If they say "
                      "no, don't pull data for another brand (setup check guide, section 5).".format(
                          where, slug, ', '.join(slugs), match['name'], match['slug'],
                          ', '.join(match['saved_names']), match['saved_marketplace'], match['name'], match['slug'],
                          slug),
            member_next='Claude asks you to confirm this folder is for {} before pulling new data.'.format(match['name']),
            short="this folder's saved reports use an older account name", details=details)
    return make_check(
        'connector', label, PROBLEM,
        "The Caiman connector works, but it doesn't show this business's Amazon account{}.".format(shown),
        next_step="The account saved in this folder ({}, from {}) isn't among the slugs list_brands returned ({}). "
                  "Setup check guide, section 5: a store that was disconnected and connected again can get a new "
                  "slug{}. Don't pull data for another brand meanwhile.".format(
                      slug, where, ', '.join(slugs),
                      '' if tier == 'gls-plus' else
                      ("; and a VIP Machine set up under the business's own name never matches a listed slug. Read the "
                       "kit's TROUBLESHOOTING.md, \"The brand's slug changed\": if list_ads_profiles for a listed slug "
                       "shows the VIP Machine's Ads profile, seller and marketplace IDs, link that slug with the member's "
                       "go (vip_machine.py link-connector-slug, which checks the IDs first). Don't reconnect the store to "
                       "fix it, and never change the VIP Machine's settings yourself"
                       if where.endswith('config/brand.json') else
                       "; on VIP read the kit's TROUBLESHOOTING.md, \"The brand's slug changed\", before the member "
                       "reconnects anything, and never change the VIP Machine's settings yourself")),
        member_next='Claude works out what changed (for example a store that was connected again) and tells you '
                    'what to do.',
        short="the Caiman connector doesn't show this business's Amazon account", details=details)


# ---------------------------------------------------------------- 5. Deep Seed

def business_views(root):
    """(modified time, path relative to the folder) of each operating-view.json under Reviews/, newest first."""
    reviews = root / 'Reviews'
    found, folders = [], 0
    if not reviews.is_dir():
        return found
    for current, subfolders, files in os.walk(str(reviews)):
        folders += 1
        if folders > MAX_REVIEW_FOLDERS:
            break
        if 'operating-view.json' in files:
            path = Path(current) / 'operating-view.json'
            try:
                if path.is_file():
                    found.append((path.stat().st_mtime, path.relative_to(root).as_posix()))
            except OSError:
                continue
    return sorted(found, reverse=True)


def recorded_currency(root):
    """The business's currency as the kit recorded it, or None: what the member gave (NEXT_STEP.py set --currency), else
    the newest saved Ads profile read or setup details in .caiman/setup-inputs/ (NEXT_STEP.py reads them the same way)."""
    saved = as_dict(as_dict(read_json(root / '.caiman' / 'plan' / 'state.json')).get('settings')).get('currency')
    if isinstance(saved, str) and re.fullmatch(r'[A-Z]{3}', saved):
        return saved
    folder = root / '.caiman' / 'setup-inputs'
    try:
        files = sorted((path for path in folder.glob('*.json') if path.is_file() and not path.is_symlink()),
                       key=lambda path: path.stat().st_mtime, reverse=True)[:50] if folder.is_dir() else []
    except OSError:
        files = []
    for path in files:
        value = as_dict(read_json(path))
        result = value['result'] if isinstance(value.get('result'), dict) else value
        for code in (result.get('currency_code'), as_dict(value.get('marketplace')).get('currency')):
            if isinstance(code, str) and re.fullmatch(r'[A-Za-z]{3}', code.strip()):
                return code.strip().upper()
    return None


def read_only_reviews(root):
    """VIP outside US dollars: (saved time, path relative to the folder, currency, has sales by product) of each finished
    read-only review (READ_ONLY_REVIEW.py) under Reviews/, newest first. As in NEXT_STEP.py, such a review stands in for the
    business view: its record (review-receipt.json) names the exact model beside it (dashboard.json) and its currency isn't
    US dollars. None count on GLS+, or when the business is recorded in US dollars or has a VIP Machine set up (it is set
    up only in US dollars)."""
    import hashlib
    reviews = root / 'Reviews'
    if not reviews.is_dir() or folder_tier(root) == 'gls-plus' or recorded_currency(root) == 'USD':
        return []
    for location in (MACHINE_DIR, NESTED_MACHINE_DIR):
        market = as_dict(as_dict(read_json(root / location / 'config' / 'brand.json')).get('marketplace'))
        if text_value(market.get('currency')):
            if market['currency'].strip().upper() == 'USD':
                return []
            break
    found, folders = [], 0
    for current, subfolders, files in os.walk(str(reviews)):
        folders += 1
        if folders > MAX_REVIEW_FOLDERS:
            break
        here = Path(current)
        if 'review-receipt.json' not in files or 'dashboard.json' not in files or len(here.relative_to(reviews).parts) > 5:
            continue
        try:
            if (here / 'review-receipt.json').is_symlink() or (here / 'dashboard.json').is_symlink() \
                    or (here / 'dashboard.json').stat().st_size > 64 * 1024 * 1024:
                continue
            raw = (here / 'dashboard.json').read_bytes()
            model = as_dict(json.loads(raw.decode('utf-8')))
        except (OSError, ValueError):
            continue
        record = as_dict(read_json(here / 'review-receipt.json'))
        window = as_dict(model.get('window'))
        currency = model.get('currency')
        if record.get('schema') != 'caiman.captured-read-only-review.v1' or record.get('mode') != 'READ_ONLY_UNGRADED' \
                or hashlib.sha256(raw).hexdigest() != record.get('model_sha256') or model.get('review_mode') != 'READ_ONLY_UNGRADED' \
                or not isinstance(currency, str) or not re.fullmatch(r'[A-Z]{3}', currency) or currency == 'USD' \
                or parse_time(window.get('start')) is None or parse_time(window.get('end')) is None:
            continue
        rows = model.get('unmapped') if isinstance(model.get('unmapped'), list) else []
        products = any(isinstance(row, dict) and text_value(row.get('asin')) for row in rows)
        saved = parse_time(record.get('rendered_at')) or dt.datetime.fromtimestamp((here / 'dashboard.json').stat().st_mtime,
                                                                                   dt.timezone.utc)
        found.append((saved, (here / 'dashboard.json').relative_to(root).as_posix(), currency, products))
    return sorted(found, reverse=True)


def check_deep_seed(root, zone=None):
    views = business_views(root)
    if views:
        built = dt.datetime.fromtimestamp(views[0][0], dt.timezone.utc)
        return make_check('deep_seed', 'Deep Seed', OK,
                          'Deep Seed is done. Your latest business view is from {}.'.format(plain_date(built, zone)),
                          details={'business_view': views[0][1], 'built_at': built.isoformat(), 'views': len(views)})
    reviews = read_only_reviews(root)   # VIP outside US dollars: the read-only review stands in for the business view
    ready = [review for review in reviews if review[3]]
    if ready:
        return make_check('deep_seed', 'Deep Seed', OK,
                          'Deep Seed is done. Your business sells in {}, so your plan works from a read-only review of your '
                          'connected reports; the latest is from {}.'.format(ready[0][2], plain_date(ready[0][0], zone)),
                          details={'read_only_review': ready[0][1], 'currency': ready[0][2], 'built_at': ready[0][0].isoformat(),
                                   'reviews': len(reviews)})
    if reviews:
        return make_check(
            'deep_seed', 'Deep Seed', ATTENTION, "Deep Seed hasn't finished: your read-only review doesn't have your sales by "
                                                 "product yet, so your plan can't start.",
            next_step='The read-only review ({}) has no sales by product (the Business Report by child ASIN), so the plan '
                      "can't rank anything yet. NEXT_STEP.py names the step that adds it (the caiman skill, section 4).".format(
                          reviews[0][1]),
            member_next='Claude finishes Deep Seed with you.', short="Deep Seed hasn't finished",
            details={'read_only_review': reviews[0][1], 'currency': reviews[0][2], 'reviews': len(reviews)})
    return make_check(
        'deep_seed', 'Deep Seed', ATTENTION, "Deep Seed hasn't finished, so your plan and weekly reviews aren't "
                                             "running yet.",
        next_step='No business view yet (no operating-view.json under Reviews/). Finish Deep Seed: '
                  "NEXT_STEP.py names the step, and while its stage is DEEP_SEED, start it without waiting (the caiman "
                  "skill, section 4).",
        member_next='Claude finishes Deep Seed with you.', short="Deep Seed hasn't finished")


def machine_waits_for_connection(checks):
    """VIP (Caiman 0.3.24): while a connection the VIP Machine is set up from is off (the connector check's not_connected),
    its line says the VIP Machine waits for it rather than that Claude sets it up now."""
    connector = next((item for item in checks if item.get('id') == 'connector'), None)
    off = ((connector or {}).get('details') or {}).get('not_connected') or []
    machine = next((item for item in checks if item.get('id') == 'vip_machine' and item.get('status') != OK
                    and LAST_STEP in (item.get('member_line') or '')), None)
    if not off or machine is None:
        return
    words, verb = joined(off), 'is' if len(off) == 1 else 'are'
    machine['member_line'] = machine['member_line'].rstrip('.') + ', and it waits for {} to be connected (above).'.format(words)
    machine['member_next'] = ("Claude sets it up as Deep Seed's last step once {} {} connected, from what Deep Seed saved; "
                              "nothing you've answered is asked again.".format(words, verb))
    machine['next_step'] = ('It waits for {}: the VIP Machine is set up from the saved Ads account read and confirms the accounts '
                            'with fresh reads, and {} {} not connected yet (the connector check). Set it up once list_brands '
                            'shows the connection on. Then: {}'.format(words, words, "isn't" if len(off) == 1 else "aren't",
                                                                        machine['next_step']))
    machine['details'] = dict(machine.get('details') or {}, waits_for=off)


DOWNLOAD_HOST = 'tools.caimandata.ai'
DOWNLOAD_SETTING = ("In Claude's Settings, under Capabilities, turn on Allow network egress (under Code execution and file "
                    "creation) and choose All domains, or add {} to the list (it saves as soon as you add it; there's no Save "
                    "button); on a Team or Enterprise plan an owner changes it in Organization settings. Then ask Claude to "
                    "try again, and start a new task if it's still refused.").format(DOWNLOAD_HOST)


def check_download_site(args):
    """Caiman's download site (Caiman 0.3.32): kit updates and the VIP Machine's weekly refresh (its Ads list exports)
    download from it. This check never uses the network: Claude tests the site where the kit's scripts run (the setup
    check guide, "Every session") and passes what it found with --download-site. Only a refusal gets a line."""
    if getattr(args, 'download_site', None) != 'blocked':
        return None
    error = redact(args.download_error, 200) if text_value(getattr(args, 'download_error', None)) else None
    return make_check(
        'download_site', "Caiman's download site", PROBLEM,
        "Claude's network setting blocks Caiman's download site ({}), so kit updates and the VIP Machine's weekly refresh "
        "can't download what they need.".format(DOWNLOAD_HOST),
        next_step=('The test of {} where the kit\'s scripts run was refused{}. That is Claude\'s network setting for code, not '
                   'Caiman: ask for the member\'s click in your first reply (the setup check guide, section 3). Meanwhile a kit '
                   'update installs from the kit zip in the member\'s Caiman account (on caimandata.ai: Get Caiman, then '
                   'Advanced, then Download your kit; kit-sync --zip), and the VIP Machine\'s '
                   'Sponsored Products lists can come from an Ads console bulk file (ADS_BULK_SOURCES.py --bulk-file). Don\'t try '
                   'to reach the site another way. Run this check again in a new task once the setting is changed.').format(
                       DOWNLOAD_HOST, ' ({})'.format(error) if error else ''),
        member_next=DOWNLOAD_SETTING,
        short="Claude's network setting blocks Caiman's download site", details={'host': DOWNLOAD_HOST, 'error': error})


def download_blocked(checks):
    """While Caiman's download site is blocked, the Kit and VIP Machine lines say what waits for it instead of promising an
    update or a refresh that can't run (Caiman 0.3.32: a member's kit stayed old and their VIP Machine never built a scorecard
    from Oct 19 to 22 while each session's status said Claude would update and refresh them)."""
    if not any(item.get('id') == 'download_site' and item.get('status') == PROBLEM for item in checks):
        return
    for item in checks:
        if item.get('id') == 'kit' and item.get('status') == ATTENTION and item.get('member_next') == KIT_UPDATE_NEXT:
            item['member_line'] = (item['member_line'].replace(' Claude updates it now and keeps everything you made.', '')
                                   .rstrip('.') + ". It can't download while Caiman's download site is blocked.")
            item['member_next'] = ('Claude updates the kit once the download site is allowed, or from the kit zip in your Caiman '
                                   'account if you put it in the business folder; your own files stay as they are.')
            item['details'] = dict(item.get('details') or {}, download_blocked=True)
        if item.get('id') == 'vip_machine' and (item.get('details') or {}).get('preflight_status') == 'refresh-required':
            waits = "The weekly review can't refresh them while Caiman's download site is blocked."
            line = item['member_line']
            item['member_line'] = (line.replace(REFRESHES_FIRST, waits, 1) if REFRESHES_FIRST in line
                                   else line.rstrip('.') + '. ' + waits)
            item['member_next'] = ("Claude refreshes the VIP Machine's reports at the start of the weekly review once the "
                                   'download site is allowed.')
            item['details'] = dict(item.get('details') or {}, download_blocked=True)


def first_scorecard(machine_check, machine, zone=None):
    """A set-up VIP Machine that has never built a scorecard can't record proposals or changes (Caiman 0.3.32: a
    member's three had none from their setup on Oct 14 and 15 to Oct 22, while the status said only that reports were due):
    its line says so, with the day setup finished, so nobody reads the machine as tracking changes."""
    if machine_check.get('status') == OK or (machine / 'scorecard' / 'single_brand.json').is_file():
        return machine_check
    state = as_dict(read_json(machine / 'state' / 'workspace.json'))
    finished = parse_time(state.get('bootstrap_completed_at'))
    if state.get('bootstrap') is not False or finished is None:
        return machine_check
    machine_check['member_line'] = (machine_check['member_line'].rstrip('.') + '. It hasn\'t built its first scorecard since '
                                    'setup finished on {}, so it doesn\'t track proposals or changes yet: until the weekly '
                                    'review builds it, every change goes in the member log.'.format(plain_date(finished, zone)))
    machine_check['details'] = dict(machine_check.get('details') or {}, first_scorecard=False,
                                    bootstrap_completed_at=state.get('bootstrap_completed_at'))
    return machine_check


def deep_seed_last_step(checks):
    """VIP (Caiman 0.3.23): with a business view saved while the VIP Machine, Deep Seed's last part, is still open, the
    Deep Seed line says so rather than calling Deep Seed done just above the VIP Machine's line. Its status stays OK: the
    VIP Machine's own line carries the attention."""
    deep = next((item for item in checks if item.get('id') == 'deep_seed'), None)
    if not deep or deep.get('status') != OK or 'business_view' not in (deep.get('details') or {}):
        return
    if any(item.get('id') == 'vip_machine' and item.get('status') != OK and LAST_STEP in (item.get('member_line') or '')
           for item in checks):
        deep['member_line'] = deep['member_line'].replace(
            'Deep Seed is done. ', 'Deep Seed is done apart from its last step, the VIP Machine (below). ', 1)


# ---------------------------------------------------------------- 6. the VIP Machine

LAST_STEP = "Deep Seed's last step"

def ratings_source_known(machine, readings):
    """True when this VIP Machine records star ratings (its settings, its program or a saved reading names them)."""
    if readings:
        return True
    config = as_dict(read_json(machine / 'config' / 'brand.json'))
    for item in as_dict(config.get('lineage')).get('required_sources') or []:
        if as_dict(item).get('source_key') == RATINGS_SOURCE:
            return True
    for folder, pattern in (('engine', '*.py'), ('engine', '*.json'), ('config', '*.json')):
        for path in sorted((machine / folder).glob(pattern)):
            try:
                text = path.read_text(encoding='utf-8', errors='replace')
            except OSError:
                continue
            if RATINGS_SOURCE in text or RATINGS_COMMAND in text:
                return True
    return False


OLDEST_TIME = dt.datetime.min.replace(tzinfo=dt.timezone.utc)


def ratings_readings(machine):
    """(collected_at, manifest id) of each finalized star-ratings reading, newest first: the VIP Machine's order for a
    source's saved bundles (Caiman 0.3.28, vip_machine._manifest_order): when the read finished, then when the bundle
    was finalized, then the manifest ID, the later first each time."""
    readings = []
    for path in sorted((machine / 'feeders' / 'manifests').glob('*.json')):
        manifest = as_dict(read_json(path))
        if manifest.get('source_key') != RATINGS_SOURCE or manifest.get('status') != 'finalized':
            continue
        collected = parse_time(as_dict(manifest.get('lineage')).get('collected_at'))
        if collected is not None:
            finalized = parse_time(manifest.get('finalized_at')) or OLDEST_TIME
            readings.append((collected, finalized, text_value(manifest.get('manifest_id')) or path.stem))
    return [(collected, manifest_id) for collected, _finalized, manifest_id in sorted(readings, reverse=True)]


REFRESH_MEMBER_NEXT = 'Claude refreshes them at the start of the weekly review.'
REFRESHES_FIRST = 'The weekly review refreshes them first (WEEKLY_REFRESH.py).'


def refresh_member_line(count):
    """The VIP Machine line when reports are due (Caiman 0.3.28): the weekly review refreshes them first; it never waits
    for them."""
    return "{} of the VIP Machine's reports {} due for a refresh. {}".format(count, plural(count, 'is', 'are'), REFRESHES_FIRST)


def kit_script(root, name):
    """A kit script of this business folder: in the guide folder CAIMAN_CURRENT.md names (a kit kept beside the
    business's files), else in the business folder itself; None when neither has it."""
    root = Path(root)
    candidates = [root / name]
    try:
        text = (root / 'CAIMAN_CURRENT.md').read_text(encoding='utf-8')[:262144]
    except (OSError, UnicodeDecodeError):
        text = ''
    match = re.search(r'^\s*Guide folder:\s*`?([^`\n(]+?)`?\s*(?:\(|$)', text, re.M)
    if match:
        named = match.group(1).strip()
        parts = [part for part in named.replace('\\', '/').split('/') if part not in ('', '.')]
        if parts and '..' not in parts and not named.startswith(('/', '\\')) and ':' not in named:
            candidates.insert(0, root.joinpath(*parts) / name)
    return next((path for path in candidates if path.is_file()), None)


def refresh_next_step(root, keys):
    """What Claude does about reports that are due: WEEKLY_REFRESH.py plan in the business folder, its reads, then its
    finish command. A refresh is part of the weekly review, a scheduled one too, never a stop (Caiman 0.3.28)."""
    script = kit_script(root, 'WEEKLY_REFRESH.py')
    command = ('python3 "{}" plan --project-root "{}"'.format(script, root) if script is not None else
               "the kit's WEEKLY_REFRESH.py plan (this folder doesn't have it yet: update the kit with kit-sync)")
    return ('weekly-preflight (pre-refresh): refresh-required for {}. This is no stop, in a scheduled run too: the weekly '
            'review refreshes them first with {}, makes the connector reads it lists (the slow Amazon reports first) and '
            'saves each answer where it says, then runs its finish command until it answers ready (the VIP Machine\'s '
            'templates/vip-weekly-loop.md). Proposals wait until weekly-preflight --phase post-refresh says '
            'ready.'.format(', '.join(keys) or 'its sources', command))


def preflight(root, machine):
    """(check, preflight result or None) from the VIP Machine's read-only weekly-preflight."""
    label = 'VIP Machine'
    engine = machine / 'engine' / 'vip_machine.py'
    command = [python_command(), '-B', str(engine), 'weekly-preflight', '--root', str(machine), '--phase',
               'pre-refresh']
    by_hand = 'python3 "{}/engine/vip_machine.py" weekly-preflight --root "{}" --phase pre-refresh'.format(
        machine.relative_to(root).as_posix(), machine.relative_to(root).as_posix())
    if not engine.is_file():
        return make_check(
            'vip_machine', label, PROBLEM, 'The VIP Machine folder is incomplete, so it can\'t run.',
            next_step='VIP Machine/engine/vip_machine.py is missing. Run MACHINE_ROOT_GUARD.py --project-root '
                      '"<business folder>" and follow its next step (the kit\'s CLAUDE.md, "The VIP Machine", and '
                      'TROUBLESHOOTING.md). Don\'t copy files over the VIP Machine by hand.',
            member_next='Claude looks into it and tells you what it finds.',
            short='the VIP Machine folder is incomplete'), None
    code, out, err, failed = run_program(command, root, PREFLIGHT_SECONDS)
    if failed:
        return make_check(
            'vip_machine', label, ATTENTION, "The VIP Machine's check didn't finish, so its data wasn't checked.",
            next_step='weekly-preflight: {} (a slow or synced folder can need longer). Run it yourself with a '
                      'longer timeout: {}'.format(failed, by_hand),
            member_next="Claude runs the VIP Machine's check again with more time.",
            short="the VIP Machine's check didn't finish", details={'error': failed}), None
    data = json_from(out)
    status = text_value(as_dict(data).get('status'))
    if data is None or status is None:
        error = as_dict(json_from(err)).get('error') or one_line(err or out, 400) or 'no output'
        return make_check(
            'vip_machine', label, PROBLEM, "The VIP Machine's check couldn't run, so its data wasn't checked.",
            next_step='weekly-preflight stopped (exit {}): {}. Run MACHINE_ROOT_GUARD.py --project-root "<business '
                      'folder>" and check-health for detail, then the kit\'s TROUBLESHOOTING.md. Don\'t do the VIP '
                      'Machine\'s checks by hand and present them as its result.'.format(code, one_line(error, 400)),
            member_next='Claude looks into it and tells you what it finds.',
            short="the VIP Machine's check couldn't run",
            details={'exit_code': code, 'error': one_line(error, 600)}), None
    details = {'preflight_status': status, 'checked_at': data.get('checked_at')}
    if status == 'ready':
        return make_check('vip_machine', label, OK, "The VIP Machine's data is current.", details=details), data
    if status == 'refresh-required':
        keys = [key for key in data.get('refresh_source_keys') or [] if isinstance(key, str)]
        details.update(refresh_source_keys=keys, refresh_required=data.get('refresh_required') or [])
        count = len(keys) or len(data.get('refresh_required') or []) or 1
        return make_check(
            'vip_machine', label, ATTENTION, refresh_member_line(count),
            next_step=refresh_next_step(root, keys),
            member_next=REFRESH_MEMBER_NEXT,
            short='{} VIP Machine {} due for a refresh'.format(count, plural(count, 'report is', 'reports are')),
            details=details), data
    blockers = [one_line(item, 300) for item in data.get('hard_blockers') or []]
    details['hard_blockers'] = blockers
    accounts = blockers and all('account' in item.lower() and 'confirm' in item.lower() for item in blockers)
    if status in ('hard-blocked', 'blocked-after-refresh'):
        return make_check(
            'vip_machine', label, PROBLEM,
            "The VIP Machine's connected Amazon accounts aren't confirmed, so it can't make proposals yet."
            if accounts else
            "The VIP Machine found a problem in its saved records, so it can't make proposals until that's fixed.",
            next_step='weekly-preflight: {}: {}. {}check-health and the kit\'s TROUBLESHOOTING.md have more. Never '
                      "edit or delete the VIP Machine's records to clear a blocker.".format(
                          status, '; '.join(blockers[:3]) + (' (and {} more)'.format(len(blockers) - 3)
                                                              if len(blockers) > 3 else '') or 'no reasons given',
                          'Confirm the accounts with confirm-accounts, as the vip-machine skill says; ' if accounts
                          else 'Fix what the reasons name; '),
            member_next='Claude looks into it and tells you what it finds. Nothing on your Amazon account is affected.',
            short="the VIP Machine's accounts aren't confirmed" if accounts else
            'the VIP Machine found a problem in its records', details=details), data
    return make_check(
        'vip_machine', label, ATTENTION, "The VIP Machine's check gave an answer this check doesn't know.",
        next_step='weekly-preflight returned status "{}". Read its output yourself: {}'.format(status, by_hand),
        member_next='Claude looks into it and tells you what it finds.',
        short="the VIP Machine's check needs a look", details=details), data


def check_vip(root, now, zone=None):
    """The VIP Machine check, and the star-ratings check when this VIP Machine records ratings."""
    label = 'VIP Machine'
    machine, machine_name = machine_folder(root)
    # A folder with no engine, settings or state holds only reports skills saved before setup: not set up yet.
    if not machine.is_dir() or not any((machine / name).exists() for name in MACHINE_FILES):
        foreign = recorded_currency(root)
        if foreign is None:
            reviews = read_only_reviews(root)
            foreign = reviews[0][2] if reviews else None
        if foreign and foreign != 'USD':
            # VIP outside US dollars: NEXT_STEP.py and CLIENT_START.py run every step without the VIP Machine.
            return [make_check(
                'vip_machine', label, OK, "The VIP Machine works in US dollars only for now, so it isn't set up for your "
                                          "business in {}; your plan runs without it.".format(foreign),
                next_step='This business sells in {}. Don\'t set up the VIP Machine (it works in US dollars only for now); '
                          'NEXT_STEP.py names the next step, and every step runs without the VIP Machine.'.format(foreign),
                details={'outside_us_dollars': foreign})]
        return [make_check(
            'vip_machine', label, ATTENTION, "The VIP Machine isn't set up yet; that's Deep Seed's last step.",
            next_step='No VIP Machine in the business folder yet (a "VIP Machine" folder holding only reports saved '
                      'before setup doesn\'t count; setting up keeps them). Setting it up is Deep Seed\'s last part: run '
                      'MACHINE_ROOT_GUARD.py --project-root "<business folder>" (the kit\'s CLAUDE.md, "The VIP Machine"); '
                      'it finds a VIP Machine set up somewhere else if there is one, or says how to set it up. Set it up from '
                      'what Deep Seed saved (its answers, the saved Ads account read and its reports), asking nothing again '
                      '(the VIP Machine\'s templates/vip-deep-seed.md). The plan puts this before the first workflow.',
            member_next="Claude sets it up as Deep Seed's last step, from what Deep Seed saved; nothing you've answered is "
                        "asked again.", short="the VIP Machine isn't set up yet (Deep Seed's last step)")]
    state_path = machine / 'state' / 'workspace.json'
    if not (machine / 'config' / 'brand.json').is_file() or not state_path.is_file():
        return [make_check(
            'vip_machine', label, ATTENTION, "The VIP Machine's setup isn't finished; that's Deep Seed's last step.",
            next_step='The VIP Machine folder is there but not set up yet (no config/brand.json or '
                      'state/workspace.json). Run MACHINE_ROOT_GUARD.py --project-root "<business folder>" and follow '
                      'its next step: vip_machine.py init with the details Deep Seed saved (its answers and the saved Ads '
                      'account read; the VIP Machine\'s templates/vip-deep-seed.md).',
            member_next="Claude finishes it as Deep Seed's last step, from what Deep Seed saved.",
            short="the VIP Machine's setup isn't finished (Deep Seed's last step)", details={'initialized': False})]
    if as_dict(read_json(state_path)).get('bootstrap') is True:
        return [make_check(
            'vip_machine', label, ATTENTION, "The VIP Machine's first reports aren't all in yet; that's Deep Seed's last step.",
            next_step="VIP Machine/state/workspace.json says bootstrap: true. Finish Deep Seed as the VIP Machine's "
                      'templates/vip-deep-seed.md says: confirm the accounts, make each configured source from the reports '
                      'Deep Seed saved (pull only what they don\'t cover or what is out of date), then complete-bootstrap.',
            member_next="Claude finishes it as Deep Seed's last step, from the reports Deep Seed saved.",
            short="the VIP Machine's first reports aren't all in yet (Deep Seed's last step)", details={'bootstrap': True})]
    machine_check, data = preflight(root, machine)
    machine_check = first_scorecard(machine_check, machine, zone)
    readings = ratings_readings(machine)
    # When the VIP Machine lists ratings among its sources, weekly-preflight reports the newest reading too.
    engine_view = as_dict(as_dict(as_dict(data).get('checks')).get('sources')).get(RATINGS_SOURCE)
    if isinstance(engine_view, dict):
        collected = parse_time(engine_view.get('collected_at'))
        if collected is not None and all(collected != when for when, _ in readings):
            readings = sorted(readings + [(collected, text_value(engine_view.get('manifest_id')) or
                                           'weekly-preflight')], reverse=True)
    if not isinstance(engine_view, dict) and not ratings_source_known(machine, readings):
        machine_check['details']['ratings'] = 'not checked: this VIP Machine has no {} source'.format(RATINGS_SOURCE)
        return [machine_check]
    due_keys = [key for key in as_dict(data).get('refresh_source_keys') or [] if isinstance(key, str)]
    engine_due = RATINGS_SOURCE in due_keys
    if engine_due and machine_check['status'] == ATTENTION and machine_check['details'].get('refresh_source_keys'):
        others = [key for key in due_keys if key != RATINGS_SOURCE]   # the ratings check below reports this one
        machine_check['details']['refresh_source_keys'] = others
        if others:
            count = len(others)
            machine_check['member_line'] = refresh_member_line(count)
            machine_check['short'] = '{} VIP Machine {} due for a refresh'.format(
                count, plural(count, 'report is', 'reports are'))
            machine_check['next_step'] = machine_check['next_step'].replace(', '.join(due_keys), ', '.join(others))
        else:
            machine_check = make_check(
                'vip_machine', label, OK, "The VIP Machine's reports are current, apart from star ratings.",
                details=dict(machine_check['details'], note='only the star ratings are due'))
    details = {'source_key': RATINGS_SOURCE, 'readings': len(readings)}
    newest = readings[0][0] if readings else None
    if newest is not None:
        age = (now - newest).total_seconds() / 86400.0
        details.update(newest_collected_at=newest.isoformat().replace('+00:00', 'Z'), newest_manifest=readings[0][1],
                       age_days=round(max(age, 0.0), 1), due_in_vip_machine=engine_due)
    if newest is not None and age <= RATINGS_MAX_DAYS and not engine_due:
        return [machine_check, make_check('ratings', 'Star ratings', OK,
                                          'Star ratings were last recorded {}.'.format(days_ago(newest, now, zone)),
                                          details=details)]
    stale = newest is None or age > RATINGS_MAX_DAYS
    return [machine_check, make_check(
        'ratings', 'Star ratings', ATTENTION,
        "Star ratings haven't been recorded in the last 30 days." if stale else
        'Star ratings were last recorded {} and are due again.'.format(days_ago(newest, now, zone)),
        next_step='{}. Record them with the VIP Machine\'s {} command: no connector tool returns star ratings or '
                  'rating counts, so read them from each product\'s Amazon page with a browser tool if you have one '
                  '(the Claude app\'s built-in browser or Claude in Chrome), or ask the member for the two numbers '
                  'shown under the product title, and say which it was.'.format(
                      'No star-ratings reading yet' if newest is None else
                      'Newest star-ratings reading: {} ({} days old{})'.format(
                          details['newest_collected_at'], details['age_days'],
                          '; the VIP Machine also lists it as due' if engine_due else ''), RATINGS_COMMAND),
        member_next='Claude reads your star ratings from your product pages, or asks you for the two numbers shown '
                    'under each product title.',
        short="star ratings haven't been recorded in the last 30 days" if stale else 'star ratings are due again',
        details=details)]


# ---------------------------------------------------------------- skills named like the kit's, loaded from elsewhere

# Where a session's Claude can load skills from outside the business folder, as far as this computer shows them:
# Claude Code's personal skills folder (with the account's skills synced under synced/<id>/ and their manifest.json,
# as cloud sessions have them), and the account's and organization's skill folders a cloud session mounts. Anthropic's
# own skills (public/, examples/, a manifest source starting "anthropic") aren't Caiman's. CAIMAN_SKILL_PLACES (folders
# separated like PATH, each an account's skills folder or personal=<folder>; empty means none) replaces these, for tests.
MOUNTED_SKILLS = Path('/mnt/skills')
ANTHROPIC_SKILL_FOLDERS = ('public', 'examples')
# Names Anthropic's own skills share with Caiman's: such a copy counts only with proof it is Caiman's.
SHARED_SKILL_NAMES = ('canvas-design', 'skill-creator')
VERSION_SUFFIX = re.compile(r'\(Caiman (\d+\.\d+\.\d+)\)\s*$')
MAX_OUTSIDE_SKILLS = 500
REMOVE_ACCOUNT_SKILL = 'in Claude, Customize > Skills > the skill > Delete'


def skill_places():
    """[(folder, kind)] to look in: 'personal' (Claude Code's skills folder) or 'account' (the account's skills)."""
    given = os.environ.get('CAIMAN_SKILL_PLACES')
    if given is not None:                            # "<folder>" or "personal=<folder>"
        places = []
        for part in (item.strip() for item in given.split(os.pathsep)):
            kind, _, folder = part.partition('=') if part.startswith(('personal=', 'account=')) else ('account', '', part)
            if folder:
                places.append((Path(folder), kind))
        return places
    config = os.environ.get('CLAUDE_CONFIG_DIR')
    places = [((Path(config) if config else Path(os.path.expanduser('~')) / '.claude') / 'skills', 'personal')]
    places += [(MOUNTED_SKILLS / name, 'account') for name in ('user', 'private', 'organization')]
    return places


def skill_description(skill_md):
    """The description in a SKILL.md's frontmatter (one line, joined), or ''."""
    try:
        with open(str(skill_md), 'r', encoding='utf-8-sig', errors='replace') as handle:
            head = handle.read(16384).replace('\r\n', '\n')
    except OSError:
        return ''
    if not head.startswith('---\n'):
        return ''
    block = head[4:].split('\n---', 1)[0]
    found = re.search(r'^description:[ \t]*(.*(?:\n[ \t]+.*)*)', block, re.M)
    if not found:
        return ''
    value = ' '.join(part.strip() for part in found.group(1).split('\n')).strip()
    if value[:1] in '|>':
        value = value[1:].lstrip('+-').strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in '"\'':
        value = value[1:-1]
    return value


def synced_manifest(folder):
    """name -> {source, updatedAt} from a synced skills folder's manifest.json, or {}."""
    data = as_dict(read_json(folder / 'manifest.json'))
    found = {}
    for item in data.get('skills') or []:
        if isinstance(item, dict) and text_value(item.get('name')):
            found[item['name'].strip()] = item
    return found


def kit_skill_names(root):
    """The skills of the folder's kit (ENTITLEMENTS.json, else RELEASE_MANIFEST.json) and this plugin's own."""
    names = set()
    for name in ('ENTITLEMENTS.json', 'RELEASE_MANIFEST.json'):
        listed = as_dict(read_json(root / name)).get('skills')
        if isinstance(listed, list):
            names.update(item.strip() for item in listed if isinstance(item, str) and item.strip())
            break
    plugin_skills = HERE.parent.parent
    try:
        names.update(path.name for path in plugin_skills.iterdir() if (path / 'SKILL.md').is_file())
    except OSError:
        pass
    return names


def plugin_skill_names():
    """The skills this plugin carries itself (caiman, kit-sync): their copies are the plugin's, not the business folder's."""
    try:
        return {path.name for path in HERE.parent.parent.iterdir() if (path / 'SKILL.md').is_file()}
    except OSError:
        return set()


def plugin_roots():
    """The real folders this plugin runs from: its own skills are never outside copies."""
    roots = [HERE.parent.parent.parent] + ([Path(os.environ['CLAUDE_PLUGIN_ROOT'])]
                                           if os.environ.get('CLAUDE_PLUGIN_ROOT') else [])
    found = []
    for root in roots:
        try:
            found.append(Path(os.path.realpath(str(root))))
        except OSError:
            continue
    return found


def version_tuple(text):
    try:
        return tuple(int(part) for part in str(text).strip().split('.'))
    except (TypeError, ValueError):
        return None


def outside_skill_copies(root, names):
    """(copies, places seen): each skill named like one of names that this computer shows Claude can load from outside
    the business folder, with the date its account's manifest shows. The plugin's own folders aren't looked in, and a
    copy whose description ends with this plugin's Caiman version (or a later one) isn't old. Nothing here changes
    anything."""
    copies, seen_places, seen = [], [], set()
    try:
        inside_root = Path(os.path.realpath(str(root)))
    except OSError:
        inside_root = root
    anthropic = [Path(os.path.realpath(str(MOUNTED_SKILLS / name))) for name in ANTHROPIC_SKILL_FOLDERS]
    plugin = plugin_roots()
    running = version_tuple(plugin_version(None)[0])

    def under(path, folder):
        return path == folder or folder in path.parents

    def look(folder, kind, manifest):
        try:
            children = sorted((child for child in folder.iterdir()), key=lambda p: p.name)[:MAX_OUTSIDE_SKILLS]
        except OSError:
            return
        for child in children:
            if child.name == 'synced' and kind == 'personal':
                try:
                    buckets = sorted(p for p in child.iterdir() if p.is_dir())
                except OSError:
                    buckets = []
                for bucket in buckets:
                    look(bucket, 'account', synced_manifest(bucket))
                continue
            skill_md = child / 'SKILL.md'
            try:
                if not skill_md.is_file():
                    continue
                real = Path(os.path.realpath(str(child)))
            except OSError:
                continue
            if real in seen or under(real, inside_root) or any(under(real, folder) for folder in anthropic + plugin):
                continue
            entry = manifest.get(child.name) or {}
            if str(entry.get('source') or '').lower().startswith('anthropic'):
                continue
            name = child.name if child.name in names else None
            if name is None:
                continue
            description = skill_description(skill_md)
            version = VERSION_SUFFIX.search(description)
            if version and running and (version_tuple(version.group(1)) or ()) >= running:
                continue                            # this plugin's version or a later one: not an old copy
            if name in SHARED_SKILL_NAMES and not entry and not version and \
                    description != VERSION_SUFFIX.sub('', skill_description(root / '.claude' / 'skills' / name /
                                                                            'SKILL.md')).strip():
                continue                            # Anthropic's skill of that name, as far as this can tell
            seen.add(real)
            when = text_value(entry.get('updatedAt'))
            copies.append({'name': name, 'where': kind, 'path': str(child),
                           'date': when[:10] if when and re.match(r'\d{4}-\d\d-\d\d', when) else None,
                           'caiman_version': version.group(1) if version else None})

    for folder, kind in skill_places():
        try:
            if not folder.is_dir() or any(under(Path(os.path.realpath(str(folder))), item) for item in plugin):
                continue
        except OSError:
            continue
        seen_places.append(str(folder))
        look(folder, kind, synced_manifest(folder))
    return sorted(copies, key=lambda item: (item['name'], item['where'])), seen_places


def plain_day(value):
    try:
        day = dt.date(*(int(part) for part in value.split('-')))
    except (TypeError, ValueError):
        return None
    return '{} {}, {}'.format(MONTHS[day.month - 1][:3], day.day, day.year)


def check_outside_skills(root, names=None):
    """The old skill copies check, or None when this computer shows none (or shows no place to look). Never a
    problem: the business folder's copies are used meanwhile."""
    copies, places = outside_skill_copies(root, kit_skill_names(root) if names is None else names)
    record = {'places_seen': places, 'copies': [{key: item[key] for key in ('name', 'where', 'date', 'caiman_version')}
                                                for item in copies]}
    if not copies:
        return None, record
    shown = []
    for item in copies:
        dated = plain_day(item['date']) if item.get('date') else None
        shown.append('{}{}'.format(item['name'], ' ({})'.format(
            'Caiman ' + item['caiman_version'] if item.get('caiman_version') else 'from ' + dated) if (
                item.get('caiman_version') or dated) else ''))
    account = [item for item in copies if item['where'] == 'account']
    personal = [item for item in copies if item['where'] == 'personal']
    steps = []
    if account:
        steps.append('Remove the old {} from your Claude account: {}, once for each ({}).'.format(
            plural(len(account), 'copy', 'copies'), REMOVE_ACCOUNT_SKILL,
            ', '.join(dict.fromkeys(item['name'] for item in account))))
    if personal:
        steps.append('Delete or move out of the way the old {} in your computer\'s Claude skills folder: {}.'.format(
            plural(len(personal), 'copy', 'copies'), ', '.join(item['path'] for item in personal)))
    count = len(copies)
    own = [name for name in dict.fromkeys(item['name'] for item in copies) if name in plugin_skill_names()]
    return make_check(
        'old_skills', 'Old skill copies', ATTENTION,
        "{} {} named like your kit's skills {} from outside your business folder: {}. Claude uses the copies in your "
        "business folder{}, which every update keeps current; the outside {} won't update.".format(
            count, plural(count, 'skill', 'skills'), plural(count, 'loads', 'load'), ', '.join(shown),
            ' and the Caiman plugin' if own else '', plural(count, 'copy', 'copies')),
        next_step=("Use the business folder's .claude/skills/<name>/SKILL.md for each of these{}, even though a skill with "
                   'the same name is listed: the listed one is an older copy. Tell the member once, in this reply, that '
                   "they should remove them and how (this check's member_next); don't stop or wait for it. Kit and "
                   "plugin skills reach members only through the business folder and the plugin, so nothing needs "
                   'uploading.').format(' (for {}, the Caiman plugin\'s own skill)'.format(' and '.join(own)) if own else ''),
        member_next=' '.join(steps), short='{} old skill {} to remove'.format(count, plural(count, 'copy', 'copies')),
        details={'copies': copies, 'places_seen': places}), record


# ---------------------------------------------------------------- the result

def ordered(checks):
    rank = {PROBLEM: 0, ATTENTION: 1, OK: 2}
    return sorted(checks, key=lambda item: rank[item['status']])   # stable: check order within each status


def headline(checks):
    flagged = [item for item in ordered(checks) if item['status'] != OK]
    if not flagged:
        return "Everything's working."
    return '{} {} attention: {}.'.format(len(flagged), plural(len(flagged), 'thing needs', 'things need'),
                                         '; '.join(item['short'] or item['member_line'].rstrip('.')
                                                   for item in flagged))


def overall(checks):
    statuses = {item['status'] for item in checks}
    return PROBLEM if PROBLEM in statuses else (ATTENTION if ATTENTION in statuses else OK)


def status_text(checks, now, shown=None):
    lines = ['# Caiman status', '', '**{}**'.format(headline(checks)), '', checked_words(now, shown), '']
    for item in ordered(checks):
        lines.append('- {} **{}:** {}'.format(MARKS[item['status']], item['label'], item['member_line']))
    lines += ['', '## What happens next', '']
    steps = []
    for item in ordered(checks):
        if item['status'] != OK and item['member_next'] and item['member_next'] not in steps:
            steps.append(item['member_next'])
    lines += ['- ' + step for step in steps] if steps else ['Nothing to do. Claude carries on with your plan.']
    lines += ['', 'Claude runs this check at the start of every session and updates this file.', '']
    return '\n'.join(lines)


def parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--project-root', '--folder', '--root', dest='project_root', required=True,
                        help='The business folder.')
    parser.add_argument('--connector', choices=('ok', 'failed', 'not-connected'),
                        help='What the Caiman connector\'s list_brands gave: ok, failed, or not-connected when no '
                             'Caiman connector tools are listed. Needed for the check (not with --flags-only).')
    parser.add_argument('--flags-only', action='store_true',
                        help='Only the report_flag calls for the lines of outputs/flags.md marked [to send], from the '
                             "folder's saved files: no checks, nothing written.")
    parser.add_argument('--connector-brands', help='With ok: the brand slugs list_brands returned, separated by '
                                                   'commas ("" when it returned none).')
    parser.add_argument('--connector-brands-json', help='With ok: the brands list_brands returned, as JSON (each with '
                                                        'its slug, display_name and marketplace_id), or @ and a file '
                                                        'that holds it.')
    parser.add_argument('--connector-error', help='With failed: the error text.')
    parser.add_argument('--no-write', action='store_true',
                        help="Don't save CAIMAN STATUS.md (and skip the write test).")
    parser.add_argument('--plugin-version', help="The Caiman plugin's version, for a copy of this file run away "
                                                 'from the plugin.')
    parser.add_argument('--live-kit', action='append', help="The kit members get now: the release the Caiman "
                                                             "connector's get_kit_download gave for a membership (for "
                                                             'example 2026-10-14-vip-v56), or @ and the file holding its '
                                                             'whole result. Give it once per membership in a workspace.')
    parser.add_argument('--download-site', choices=('ok', 'blocked'),
                        help="What the test of Caiman's download site (tools.caimandata.ai), where the kit's scripts run, "
                             'found: ok (any answer from the server) or blocked (the network refused it, for example '
                             '"CONNECT tunnel failed, response 403"). Left out: not tested this session.')
    parser.add_argument('--download-error', help='With blocked: the refusal\'s text.')
    args = parser.parse_args(argv)
    if not args.project_root.strip():
        parser.error('--project-root must name the business folder.')
    if args.connector is None and not args.flags_only:
        parser.error('--connector is needed: ok, failed, or not-connected when no Caiman connector tools are listed.')
    if args.connector == 'ok' and args.connector_brands is None and args.connector_brands_json is None:
        parser.error('--connector ok needs --connector-brands with the brand slugs list_brands returned ("" when it '
                     'returned none), or --connector-brands-json with the brands it returned.')
    args.connector_brand_list = []
    if args.connector_brands_json is not None:
        try:
            args.connector_brand_list = brands_from_json(args.connector_brands_json)
        except ValueError as error:
            parser.error("--connector-brands-json can't be used: {}. Pass the brands list_brands returned, for example "
                         '[{{"slug": "acme-outdoors", "display_name": "Acme Outdoors", "marketplace_id": '
                         '"ATVPDKIKX0DER"}}], or [] when it returned none.'.format(error))
    if args.plugin_version is not None and parse_version(args.plugin_version) is None:
        parser.error('--plugin-version must be a version such as 0.3.13.')
    args.live_kits, args.live_kit_unreadable = {}, []
    for value in args.live_kit or []:
        found = live_kit_from(value)
        if found is None:
            args.live_kit_unreadable.append(one_line(value, 80))
        else:
            args.live_kits[found['tier']] = found
    return args


def run(args):
    now = dt.datetime.now().astimezone()
    now_utc = now.astimezone(dt.timezone.utc)
    root = Path(os.path.abspath(os.path.expanduser(args.project_root.strip())))
    brands = workspace_brands(root)
    if len(brands) >= 2 or (brands and (root / WORKSPACE_FILE).is_file()):
        return run_workspace(args, root, brands, now)
    plugin, plugin_from = plugin_version(args.plugin_version)
    checks = [guarded('python', 'Commands and Python', check_python)]
    folder = guarded('business_folder', 'Business folder', check_folder, root, args.no_write)
    if folder['status'] == OK and not brands:
        deeper = workspaces_further_down(root)
        if deeper:
            folder = brands_further_down(root, deeper)
    checks.append(folder)
    found = folder['status'] == OK
    tier = None
    shown = None
    if found and utc_clock(now):
        try:                                        # the zone the folder records, for the times the status shows
            shown = shown_zone(root, now)
        except Exception:                           # then they are shown in UTC, and say so
            shown = None
    zone = shown['zone'] if shown else None
    if found:
        tier = folder_tier(root)
        kit = guarded('kit', 'Kit', check_kit, root, tier, plugin)
        if kit['id'] == 'kit' and isinstance(kit.get('details'), dict):
            kit = with_live_kit(kit, args.live_kits, args.live_kit_unreadable, tier, args.connector)
        checks.append(kit)
        tier = tier or kit['details'].get('tier')
    outside_record = getattr(args, 'outside_skills_record', None)
    if found and not getattr(args, 'skip_outside_skills', False):
        try:
            outside, outside_record = check_outside_skills(root)
        except Exception as error:                  # this check never stops the others
            outside, outside_record = None, {'error': '{}: {}'.format(type(error).__name__, one_line(error, 200))}
        if outside:
            checks.append(outside)
    checks.append(guarded('connector', 'Caiman connector', check_connector, args, root if found else None, tier))
    download = check_download_site(args)
    if download:
        checks.append(download)
    if found:
        checks.append(guarded('deep_seed', 'Deep Seed', check_deep_seed, root, zone))
        if tier == 'vip':
            vip = guarded('vip_machine', 'VIP Machine', check_vip, root, now_utc, zone)
            checks += vip if isinstance(vip, list) else [vip]
            deep_seed_last_step(checks)
            machine_waits_for_connection(checks)
    download_blocked(checks)
    status_file, write_error = None, None
    if found and not args.no_write:
        saved, why, kind = write_status(root, status_text(checks, now, shown))
        if saved:
            status_file = str(root / STATUS_FILE)
        else:
            write_error = why
            checks[checks.index(folder)] = folder_write_failed(folder, why, kind)
    result = {'status': overall(checks), 'headline': headline(checks), 'checked_at': now.isoformat(),
              'business_folder': str(root), 'tier': tier, 'plugin_version': plugin, 'plugin_version_from': plugin_from,
              'checks': [{key: item[key] for key in ('id', 'label', 'status', 'member_line', 'member_next',
                                                      'next_step', 'details')} for item in checks],
              'status_file': status_file}
    if found:
        kit_check = next((item for item in checks if item['id'] == 'kit'), None)
        fields = folder_fields(root, checks)
        result['kit_report'] = report_call(plugin, [kit_report(kit_check, plugin, result['status'])],
                                           [fields] if fields is not None else None)
        try:                                        # flags the member said yes to sending (Caiman 0.3.36)
            kit_details = as_dict((kit_check or {}).get('details'))
            flags = flag_reports(root, plugin, kit_details.get('tier') or tier, kit_number(kit_details.get('kit_version')),
                                 (fields or {}).get('folder_id'), (fields or {}).get('store_id'),
                                 setup_context(result['status'], {item['id']: item['status'] for item in checks}))
        except Exception:                           # sending flags never stops the setup check
            flags = None
        if flags:
            result['flag_reports'] = flags
    if write_error:
        result['status_file_error'] = write_error
    elif args.no_write:
        result['status_file_note'] = 'not written (--no-write)'
    elif not found:
        result['status_file_note'] = 'not written: there is no business folder to save it in'
    else:
        why = save_result(root, checks, now, plugin, result['status'], outside_record)
        if why:
            result['result_file_error'] = '{} was not saved: {}'.format(RESULT_FILE, why)
    return result


RESULT_FILE = '.caiman/setup-check.json'


def save_result(root, checks, now, plugin, status, outside_skills=None):
    """Save what this check found for the kit's scripts, beside CAIMAN STATUS.md (Caiman 0.3.24): when it checked, the
    plugin's version, each check's status and this business's Amazon connections as list_brands showed them
    (NEXT_STEP.py asks the member for a connection that's off), and (0.3.28) the skills named like the kit's that load
    from outside the business folder, with the places it could look in. Only into the folder's existing .caiman folder,
    so a folder without a kit gets none. None when saved or not needed; else why it wasn't saved."""
    folder = root / '.caiman'
    if folder.is_symlink() or not folder.is_dir():
        return None
    connector = next((item for item in checks if item.get('id') == 'connector'), None) or {}
    connections = (connector.get('details') or {}).get('connections')
    record = {'schema': 'caiman.setup-check.v1', 'checked_at': now.isoformat(), 'plugin_version': plugin, 'status': status,
              'checks': {item['id']: item['status'] for item in checks},
              'connections': dict(connections, not_connected=(connector.get('details') or {}).get('not_connected') or [])
              if isinstance(connections, dict) else None,
              'outside_skills': outside_skills}
    target = root / RESULT_FILE
    try:
        if target.is_symlink() or (target.exists() and not target.is_file()):
            return 'something that is not a normal file is in its place'
        with open(str(target), 'w', encoding='utf-8') as handle:
            handle.write(json.dumps(record, indent=2, sort_keys=True) + '\n')
    except OSError as error:
        return '{} ({})'.format(error.strerror or error, type(error).__name__)
    return None


# ---------------------------------------------------------------- a workspace: several business folders under one

WORKSPACE_FILE = 'CAIMAN WORKSPACE.json'
WORKSPACE_DEPTH = 3
WORKSPACE_MAX_FOLDERS = 3000
KIT_COPY_NAMES = ('caiman vip - guided kit', 'caiman gls plus - guided kit')


def folder_has_kit(folder):
    """A Caiman kit is in this folder: its release manifest or entitlements, or an older installer's kit pointer."""
    manifest = as_dict(read_json(folder / 'RELEASE_MANIFEST.json'))
    if any(manifest.get(key) for key in ('kit', 'tier', 'core_version', 'release')):
        return True
    if as_dict(read_json(folder / 'ENTITLEMENTS.json')).get('plan_tier'):
        return True
    return (folder / '.caiman' / 'active-guidance.json').is_file()


def workspace_brands(root):
    """The business folders under root, up to three levels down, found as the caiman skill's workspace.py finds them;
    [] when root is itself a business folder (or isn't a folder), and then the check is the usual one."""
    try:
        if not root.is_dir() or folder_has_kit(root):
            return []
    except OSError:
        return []
    found, seen = [], [0]

    def walk(folder, depth):
        try:
            children = sorted((child for child in folder.iterdir() if child.is_dir() and not child.is_symlink()),
                              key=lambda path: path.name.lower())
        except OSError:
            return
        for child in children:
            seen[0] += 1
            if seen[0] > WORKSPACE_MAX_FOLDERS:
                return
            low = child.name.lower()
            if (child.name.startswith('.') or low in ('__pycache__', '__macosx', 'node_modules', 'workspace-runs')
                    or low.startswith(('_previous-kit', '_archive', '_retired')) or 'backup' in low):
                continue
            if folder_has_kit(child):
                if not (low in KIT_COPY_NAMES and not (child / '.caiman').is_dir()):
                    found.append(child)
                continue
            if depth < WORKSPACE_DEPTH:
                walk(child, depth + 1)

    walk(root, 1)
    return found


FURTHER_DEPTH = 6


def workspaces_further_down(root):
    """When root has no kit and no business folder within three levels: the folders further down (to six levels,
    looking at no more than WORKSPACE_MAX_FOLDERS folders) that hold business folders, [(folder, count)], nearest
    first. [] for a business folder, an empty folder or a folder with none further down."""
    try:
        if not root.is_dir() or folder_has_kit(root):
            return []
    except OSError:
        return []
    parents, seen = {}, [0]

    def walk(folder, depth):
        try:
            children = sorted((child for child in folder.iterdir() if child.is_dir() and not child.is_symlink()),
                              key=lambda path: path.name.lower())
        except OSError:
            return
        for child in children:
            seen[0] += 1
            if seen[0] > WORKSPACE_MAX_FOLDERS:
                return
            low = child.name.lower()
            if (child.name.startswith('.') or low in ('__pycache__', '__macosx', 'node_modules', 'workspace-runs')
                    or low.startswith(('_previous-kit', '_archive', '_retired')) or 'backup' in low):
                continue
            if folder_has_kit(child):
                if not (low in KIT_COPY_NAMES and not (child / '.caiman').is_dir()):
                    parents[child.parent] = parents.get(child.parent, 0) + 1
                continue
            if depth < FURTHER_DEPTH:
                walk(child, depth + 1)

    walk(root, 1)
    return sorted(parents.items(), key=lambda item: (len(item[0].parts), str(item[0])))


def brands_further_down(root, deeper):
    """The business folder check when the business folders are deeper than a workspace is searched."""
    where, count = deeper[0]
    total = sum(number for folder, number in deeper)
    try:
        shown = where.relative_to(root).as_posix()
    except ValueError:
        shown = str(where)
    return make_check(
        'business_folder', 'Business folder', PROBLEM,
        "This folder isn't a business folder, and your brands' business folders are further down, in {}.".format(shown),
        next_step=("This folder has no kit and no business folder within three levels, but {} business folder{} {} "
                   'further down ({} in {}). Don\'t install a kit here or start Deep Seed: work from the folder that '
                   'holds the brand folders. Ask the member to open {} in the app (or use it as --project-root and as '
                   'workspace.py\'s --workspace), then run the setup check there. Only if the member says this folder '
                   'is for a new business, set it up as usual.').format(
                       total, '' if total == 1 else 's', 'is' if total == 1 else 'are', count, where, where),
        member_next='Open the folder that holds your brand folders ({}) in Claude, and Claude works across them from '
                    'there.'.format(shown),
        short="your brands' business folders are further down, in {}".format(shown),
        details={'path': str(root), 'business_folders_further_down': [
            {'folder': str(folder), 'business_folders': number} for folder, number in deeper]})


def workspace_brand_name(folder):
    """The brand's name as workspace.py names it: the VIP Machine's brand name, else (outside VIP) the brand name in
    GLS_PLUS_CONFIG.json, else the account name the saved source list records, else the folder's name. Caiman 0.3.24: a VIP
    brand whose VIP Machine wasn't set up yet was called by its folder's name (caiman-business)."""
    values = [as_dict(as_dict(read_json(path)).get('brand')).get('name')
              for path in (folder / MACHINE_DIR / 'config' / 'brand.json', folder / NESTED_MACHINE_DIR / 'config' / 'brand.json')]
    if folder_tier(folder) != 'vip':
        values.append(as_dict(as_dict(read_json(folder / 'GLS_PLUS_CONFIG.json')).get('identity')).get('brand_name'))
    pointer = as_dict(read_json(folder / '.caiman' / 'active-source-index.json'))
    identities = [as_dict(pointer.get('identity'))]
    target = inside(folder, pointer.get('path'))
    if target is not None:
        identities.append(as_dict(as_dict(read_json(target)).get('identity')))
    identities.append(as_dict(as_dict(read_json(folder / 'SOURCE_CAPTURES.json')).get('identity')))
    values += [identity.get('account_label') for identity in identities]
    for value in values:
        value = text_value(value)
        if value and not value.startswith('REPLACE_'):
            return value
    return folder.name


def run_workspace(args, root, folders, now):
    """The check for each brand in its own business folder (each saves its own CAIMAN STATUS.md), and one answer
    and one CAIMAN STATUS.md for the workspace folder."""
    brands, reports, with_ids, flag_lists = [], [], [], []
    # Skills named like the kits' that load from outside the business folders are the session's, not one brand's:
    # checked once here, and recorded in each brand's .caiman/setup-check.json.
    names = set()
    for folder in folders:
        names |= kit_skill_names(folder)
    try:
        outside, outside_record = check_outside_skills(root, names)
    except Exception as error:                      # this check never stops the others
        outside, outside_record = None, {'error': '{}: {}'.format(type(error).__name__, one_line(error, 200))}
    for folder in folders:
        sub = argparse.Namespace(**vars(args))
        sub.project_root = str(folder)
        sub.skip_outside_skills = True
        sub.outside_skills_record = outside_record
        try:
            result = run(sub)
        except Exception as error:                  # one brand's check breaking doesn't stop the others
            result = {'status': PROBLEM, 'headline': "The setup check couldn't finish for this brand.", 'checks': [],
                      'tier': None, 'status_file': None,
                      'error': '{}: {}'.format(type(error).__name__, one_line(error, 400))}
        try:
            shown = folder.relative_to(root).as_posix()
        except ValueError:
            shown = str(folder)
        report = as_dict(result.get('kit_report'))
        entries = as_dict(report.get('arguments')).get('folders') or []
        reports.extend(entries)
        flag_lists.append(result.get('flag_reports'))
        # Each brand's folder IDs line up with its own entries; a brand without them (it broke) keeps today's fields.
        own = as_dict(report.get('arguments_with_next_step') or report.get('arguments_with_folder_ids')).get('folders') or []
        with_ids.extend(own if len(own) == len(entries) else
                        [{key: value for key, value in entry.items() if key not in EXTRA_KEYS} for entry in entries])
        brands.append({'name': workspace_brand_name(folder), 'folder': shown, 'business_folder': str(folder),
                       'status': result.get('status'), 'headline': result.get('headline'), 'tier': result.get('tier'),
                       'status_file': result.get('status_file'), 'checks': result.get('checks') or [],
                       'error': result.get('error')})
    statuses = {brand['status'] for brand in brands} | ({outside['status']} if outside else set())
    status = PROBLEM if PROBLEM in statuses else (ATTENTION if ATTENTION in statuses else OK)
    flagged = [brand for brand in brands if brand['status'] != OK]
    if not flagged:
        line = "Everything's working for all {} brands.".format(len(brands)) if not outside else \
            'All {} brands are working; {}.'.format(len(brands), outside['short'])
    else:
        line = '{} of {} brands {}: {}.'.format(len(flagged), len(brands), 'needs attention' if len(flagged) == 1
                                                else 'need attention', '; '.join(
                                                    '{}: {}'.format(brand['name'], (brand['headline'] or '').rstrip('.'))
                                                    for brand in flagged))
        if outside:
            line += ' Also: {}.'.format(outside['short'])
    result = {'status': status, 'headline': line, 'checked_at': now.isoformat(), 'workspace': str(root),
              'workspace_mode': True, 'business_folder': None, 'tier': None, 'brands': brands,
              'checks': [{key: outside[key] for key in ('id', 'label', 'status', 'member_line', 'member_next', 'next_step',
                                                        'details')}] if outside else [],
              'next_step': ('This folder holds {} business folders (a Caiman workspace), so each brand was checked in its '
                            'own folder. Open with the headline ("Setup check: ..."), then deal with each brand\'s items '
                            "in that brand's own folder and account (the caiman skill's workspace guide).").format(
                                len(brands)),
              'status_file': None}
    if reports:
        extras = [{key: entry.get(key) for key in EXTRA_KEYS} for entry in with_ids]
        # A business folder copied to start another brand keeps the first one's ID: an ID that repeats names neither.
        seen = [extra['folder_id'] for extra in extras if extra.get('folder_id')]
        for extra in extras:
            if extra.get('folder_id') and seen.count(extra['folder_id']) > 1:
                extra['folder_id'] = None
        result['kit_report'] = report_call(plugin_version(args.plugin_version)[0], reports, extras)
    flags = merged_flag_reports(flag_lists)         # each brand's own flags, with its own file, ID and store
    if flags:
        result['flag_reports'] = flags
    if args.no_write:
        result['status_file_note'] = 'not written (--no-write)'
        return result
    zones = []
    if utc_clock(now):                              # the brands' recorded zone, when they all record the same one
        for folder in folders:
            try:
                zones.append(shown_zone(folder, now))
            except Exception:
                zones.append(None)
    same = zones and all(zone is not None for zone in zones) and \
        len({(zone['zone'], zone['whose']) for zone in zones}) == 1
    lines = ['# Caiman status: all brands', '', '**{}**'.format(line), '',
             checked_words(now, zones[0] if same else None), '']
    for brand in brands:
        lines.append('- {} **{}:** {} (`{}/{}`)'.format(MARKS.get(brand['status'], ''), brand['name'],
                                                     brand['headline'] or '', brand['folder'], STATUS_FILE))
    if outside:
        lines += ['- {} **{}:** {}'.format(MARKS[outside['status']], outside['label'], outside['member_line']),
                  '', outside['member_next']]
    lines += ['', "Each brand's own CAIMAN STATUS.md, in its business folder, says what happens next for it.",
              'Claude runs this check at the start of every session and updates this file.', '']
    saved, why, kind = write_status(root, '\n'.join(lines))
    if saved:
        result['status_file'] = str(root / STATUS_FILE)
    else:
        result['status_file_error'] = why
    return result


def main(argv=None):
    args = parse_args(argv)
    if args.flags_only:
        try:
            result = flags_only(args)
        except Exception as error:                  # it always answers
            result = {'flags_only': True, 'error': '{}: {}'.format(type(error).__name__, one_line(error, 400)),
                      'next_step': "The flags to send couldn't be read. Say so, leave the lines [to send], and the "
                                   'setup check at the start of the next session finds them again.'}
        print(json.dumps(result, indent=2, ensure_ascii=True))
        return 0
    try:
        result = run(args)
    except Exception as error:                      # the check must always answer, even when it breaks
        result = {'status': PROBLEM, 'headline': "The setup check couldn't finish.", 'checks': [],
                  'status_file': None,
                  'error': '{}: {}'.format(type(error).__name__, one_line(error, 400)),
                  'next_step': 'setup_check.py stopped before it finished. Say so in your reply, and check the '
                               'business folder by hand from its files (the setup check guide, "Every session").'}
    print(json.dumps(result, indent=2, ensure_ascii=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
