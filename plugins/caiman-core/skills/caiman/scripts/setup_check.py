#!/usr/bin/env python3
"""Caiman's setup check: is everything ready to work in this business folder?

  python3 setup_check.py --project-root "<business folder>" \\
      --connector ok|failed|not-connected --connector-brands "<slug,slug,...>" \\
      [--connector-error "<text>"] [--no-write] [--plugin-version <version>]

Before it runs, Claude calls the Caiman connector's list_brands and passes what it got: ok and the brand
slugs it returned ("" when it returned none), failed and the error text, or not-connected when no Caiman
connector tools are listed.

It checks, in this order, and reports each one as ok, attention (works, but something is due) or problem
(blocks work): commands and Python, the business folder, the kit, the connector, Deep Seed and, on VIP,
the VIP Machine, with its star-ratings reading when the VIP Machine records ratings.

It prints JSON for Claude, and saves CAIMAN STATUS.md in the business folder in plain words for the member
(not with --no-write). It changes nothing else and never uses the network. It exits 0, or 2 when the
arguments are wrong. A copy of this file run away from the plugin (for example on the member's computer)
can't read the plugin's version: pass it with --plugin-version.

Standard-library Python 3.8+ in one file. It also starts on older Python 3, so it can say that Python is
too old for the kit.
"""
import argparse
import datetime as dt
import json
import os
import platform
import re
import subprocess
import sys
from pathlib import Path

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
                 'VIP Machine': 'the VIP Machine', 'Star ratings': 'the star ratings'}


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


def plain_date(moment):
    """'October 9, 2026', in the computer's local time."""
    local = moment.astimezone()
    return '{} {}, {}'.format(MONTHS[local.month - 1], local.day, local.year)


def plain_time(moment):
    """'Saturday, October 10, 2026 at 11:45 AM', in the computer's local time."""
    local = moment.astimezone()
    return '{}, {} at {}:{:02d} {}'.format(WEEKDAYS[local.weekday()], plain_date(local), local.hour % 12 or 12,
                                         local.minute, 'AM' if local.hour < 12 else 'PM')


def zone_label(moment):
    """'MDT, UTC-6', or 'UTC'."""
    offset = moment.utcoffset() or dt.timedelta(0)
    minutes = int(offset.total_seconds() // 60)
    sign, minutes = ('+' if minutes >= 0 else '-'), abs(minutes)
    utc = 'UTC' if not minutes else 'UTC{}{}{}'.format(
        sign, minutes // 60, ':{:02d}'.format(minutes % 60) if minutes % 60 else '')
    name = moment.tzname()
    return utc if not name or name == utc or name.upper() in ('UTC', 'GMT') else '{}, {}'.format(name, utc)


def days_ago(moment, now):
    """'today', 'yesterday' or 'N days ago', by the computer's calendar."""
    days = max(0, (now.astimezone().date() - moment.astimezone().date()).days)
    return 'today' if days == 0 else ('yesterday' if days == 1 else '{} days ago'.format(days))


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
                      'plugin and starts a new task.'.format(said, details.get('kit_core_version'), plugin),
            member_next='Update the Caiman plugin in the Claude app (usually under Customize, then Plugins), then '
                        'start a new task.',
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
                member_next=KIT_UPDATE_NEXT, short="the kit's version file can't be read", details=details)
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
            short="the full kit check didn't run", details=result['details'])
    result['next_step'] += " (kit-sync status didn't run, so this compares versions only: {})".format(why)
    return result


# ---------------------------------------------------------------- 4. the connector

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
    slugs = [part for part in re.split(r'[\s,]+', args.connector_brands or '') if part]
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
        return make_check('connector', label, OK,
                          "The Caiman connector works and shows this business's Amazon account{}.".format(shown),
                          details=details)
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
    return make_check(
        'connector', label, PROBLEM,
        "The Caiman connector works, but it doesn't show this business's Amazon account{}.".format(shown),
        next_step="The account saved in this folder ({}, from {}) isn't among the slugs list_brands returned ({}). "
                  "Setup check guide, section 5: a store that was disconnected and connected again can get a new "
                  "slug{}. Don't pull data for another brand meanwhile.".format(
                      slug, where, ', '.join(slugs),
                      '' if tier == 'gls-plus' else "; on VIP read the kit's TROUBLESHOOTING.md, \"The brand's slug "
                                                    "changed\", before the member reconnects anything, and never "
                                                    "change the VIP Machine's settings yourself"),
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


def check_deep_seed(root):
    views = business_views(root)
    if views:
        built = dt.datetime.fromtimestamp(views[0][0], dt.timezone.utc)
        return make_check('deep_seed', 'Deep Seed', OK,
                          'Deep Seed is done. Your latest business view is from {}.'.format(plain_date(built)),
                          details={'business_view': views[0][1], 'built_at': built.isoformat(), 'views': len(views)})
    return make_check(
        'deep_seed', 'Deep Seed', ATTENTION, "Deep Seed hasn't finished, so your plan and weekly reviews aren't "
                                             "running yet.",
        next_step='No business view yet (no operating-view.json under Reviews/). Offer to finish Deep Seed: '
                  "NEXT_STEP.py names the step, and while its stage is DEEP_SEED, start it (the caiman skill, "
                  "section 4).",
        member_next='Claude finishes Deep Seed with you.', short="Deep Seed hasn't finished")


# ---------------------------------------------------------------- 6. the VIP Machine

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


def ratings_readings(machine):
    """(collected_at, manifest id) of each finalized star-ratings reading, newest first."""
    readings = []
    for path in sorted((machine / 'feeders' / 'manifests').glob('*.json')):
        manifest = as_dict(read_json(path))
        if manifest.get('source_key') != RATINGS_SOURCE or manifest.get('status') != 'finalized':
            continue
        collected = parse_time(as_dict(manifest.get('lineage')).get('collected_at'))
        if collected is not None:
            readings.append((collected, text_value(manifest.get('manifest_id')) or path.stem))
    return sorted(readings, reverse=True)


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
            'vip_machine', label, ATTENTION,
            "{} of the VIP Machine's reports {} due for a refresh; the weekly review does that.".format(
                count, plural(count, 'is', 'are')),
            next_step='weekly-preflight (pre-refresh): refresh-required for {}. Refresh them in the weekly review, as '
                      "the VIP Machine's templates/vip-weekly-loop.md says; it takes recommendations only once "
                      "weekly-preflight --phase post-refresh says ready.".format(', '.join(keys) or 'its sources'),
            member_next="Claude refreshes them in the next weekly review.",
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


def check_vip(root, now):
    """The VIP Machine check, and the star-ratings check when this VIP Machine records ratings."""
    label = 'VIP Machine'
    machine, machine_name = machine_folder(root)
    # A folder with no engine, settings or state holds only reports skills saved before setup: not set up yet.
    if not machine.is_dir() or not any((machine / name).exists() for name in MACHINE_FILES):
        return [make_check(
            'vip_machine', label, ATTENTION, "The VIP Machine isn't set up yet.",
            next_step='No VIP Machine in the business folder yet (a "VIP Machine" folder holding only reports saved '
                      'before setup doesn\'t count; setting up keeps them). Run MACHINE_ROOT_GUARD.py --project-root '
                      '"<business folder>" (the kit\'s CLAUDE.md, "The VIP Machine"): it finds a VIP Machine set up '
                      'somewhere else if there is one, or says how to set it up. The plan puts this before the first '
                      'workflow.',
            member_next='Claude sets it up with you as part of setup.', short="the VIP Machine isn't set up yet")]
    state_path = machine / 'state' / 'workspace.json'
    if not (machine / 'config' / 'brand.json').is_file() or not state_path.is_file():
        return [make_check(
            'vip_machine', label, ATTENTION, "The VIP Machine's setup isn't finished.",
            next_step='The VIP Machine folder is there but not set up yet (no config/brand.json or '
                      'state/workspace.json). Run MACHINE_ROOT_GUARD.py --project-root "<business folder>" and follow '
                      'its next step: vip_machine.py init with the member\'s confirmed details.',
            member_next='Claude finishes setting it up with you.', short="the VIP Machine's setup isn't finished",
            details={'initialized': False})]
    if as_dict(read_json(state_path)).get('bootstrap') is True:
        return [make_check(
            'vip_machine', label, ATTENTION, "The VIP Machine's setup isn't finished.",
            next_step="VIP Machine/state/workspace.json says bootstrap: true. Finish the setup as the VIP Machine's "
                      'templates/vip-deep-seed.md says: confirm the accounts, collect every configured report, then '
                      'complete-bootstrap.',
            member_next='Claude finishes setting it up with you.', short="the VIP Machine's setup isn't finished",
            details={'bootstrap': True})]
    machine_check, data = preflight(root, machine)
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
            machine_check['member_line'] = ("{} of the VIP Machine's reports {} due for a refresh; the weekly review "
                                            "does that.".format(count, plural(count, 'is', 'are')))
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
                                          'Star ratings were last recorded {}.'.format(days_ago(newest, now)),
                                          details=details)]
    stale = newest is None or age > RATINGS_MAX_DAYS
    return [machine_check, make_check(
        'ratings', 'Star ratings', ATTENTION,
        "Star ratings haven't been recorded in the last 30 days." if stale else
        'Star ratings were last recorded {} and are due again.'.format(days_ago(newest, now)),
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


def status_text(checks, now):
    lines = ['# Caiman status', '', '**{}**'.format(headline(checks)), '',
             "Checked on {} (the computer's local time: {}).".format(plain_time(now), zone_label(now)), '']
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
    parser.add_argument('--connector', required=True, choices=('ok', 'failed', 'not-connected'),
                        help='What the Caiman connector\'s list_brands gave: ok, failed, or not-connected when no '
                             'Caiman connector tools are listed.')
    parser.add_argument('--connector-brands', help='With ok: the brand slugs list_brands returned, separated by '
                                                   'commas ("" when it returned none).')
    parser.add_argument('--connector-error', help='With failed: the error text.')
    parser.add_argument('--no-write', action='store_true',
                        help="Don't save CAIMAN STATUS.md (and skip the write test).")
    parser.add_argument('--plugin-version', help="The Caiman plugin's version, for a copy of this file run away "
                                                 'from the plugin.')
    args = parser.parse_args(argv)
    if not args.project_root.strip():
        parser.error('--project-root must name the business folder.')
    if args.connector == 'ok' and args.connector_brands is None:
        parser.error('--connector ok needs --connector-brands with the brand slugs list_brands returned ("" when it '
                     'returned none).')
    if args.plugin_version is not None and parse_version(args.plugin_version) is None:
        parser.error('--plugin-version must be a version such as 0.3.13.')
    return args


def run(args):
    now = dt.datetime.now().astimezone()
    now_utc = now.astimezone(dt.timezone.utc)
    root = Path(os.path.abspath(os.path.expanduser(args.project_root.strip())))
    plugin, plugin_from = plugin_version(args.plugin_version)
    checks = [guarded('python', 'Commands and Python', check_python)]
    folder = guarded('business_folder', 'Business folder', check_folder, root, args.no_write)
    checks.append(folder)
    found = folder['status'] == OK
    tier = None
    if found:
        tier = folder_tier(root)
        kit = guarded('kit', 'Kit', check_kit, root, tier, plugin)
        checks.append(kit)
        tier = tier or kit['details'].get('tier')
    checks.append(guarded('connector', 'Caiman connector', check_connector, args, root if found else None, tier))
    if found:
        checks.append(guarded('deep_seed', 'Deep Seed', check_deep_seed, root))
        if tier == 'vip':
            vip = guarded('vip_machine', 'VIP Machine', check_vip, root, now_utc)
            checks += vip if isinstance(vip, list) else [vip]
    status_file, write_error = None, None
    if found and not args.no_write:
        saved, why, kind = write_status(root, status_text(checks, now))
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
    if write_error:
        result['status_file_error'] = write_error
    elif args.no_write:
        result['status_file_note'] = 'not written (--no-write)'
    elif not found:
        result['status_file_note'] = 'not written: there is no business folder to save it in'
    return result


def main(argv=None):
    args = parse_args(argv)
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
