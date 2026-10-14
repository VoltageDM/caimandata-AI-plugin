#!/usr/bin/env python3
"""Caiman's free trial week: does it apply in this business folder, and what comes next in it?

  python3 trial_week.py check     --project-root "<business folder>" --connector-brands-json @<list_brands answer file>
                                  [--brand-slug <slug>]
  python3 trial_week.py start     --project-root "<business folder>" --connector-brands-json @<list_brands answer file>
                                  [--brand-slug <slug>]
  python3 trial_week.py bind      --project-root "<business folder>" --connector-brands-json @<list_brands answer file>
                                  --brand-slug <slug> [--not-on-trial]
  python3 trial_week.py milestone --project-root "<business folder>" --name <milestone> [--details-json '<JSON>' | @file]
  python3 trial_week.py milestone --project-root "<business folder>" --name <milestone> --sent
  python3 trial_week.py milestone --project-root "<business folder>" --name <milestone> --not-sent "<why>"
  python3 trial_week.py recap     --project-root "<business folder>" --saved "<the saved recap, inside the folder>"
  python3 trial_week.py reporting --project-root "<business folder>" --off | --on
  python3 trial_week.py stop      --project-root "<business folder>"

The trial week is only for a member the Caiman server shows on Caiman's free trial: list_brands' membership has
status "trialing", free_trial true and a trial end date, and the brand is the member's own (relationship "owner"
when list_brands gives one). It starts only in a business folder where Deep Seed hadn't started and whose kit wasn't
installed before the trial began. For everyone else `check` answers "none" and nothing is written. Once a trial week
has started in a folder it carries on until the trial ends or the member stops it, and it never starts again there.

Pass list_brands' whole answer, as it came back (it carries the membership), not a list trimmed to slugs and names.
When the login shows several brands, only each brand's own membership counts: the answer's top-level one doesn't say
which brand is on the trial. When the brand isn't known yet (Amazon not connected, or several brands listed), the trial
week starts without one and `bind` ties it to the brand once the member has confirmed it. `start` and `bind` say when
to send the opening message ("announce"): with several brands listed, only once the brand is confirmed.

`check` never fails: a problem answers "none" with reason "check_failed". It only reads, except that it keeps a
running trial week's dates current when the server changes them. `start`, `bind`, `milestone`, `recap`, `reporting`
and `stop` write one file, .caiman/trial-week.json. `milestone` prints the exact call for the Caiman connector's
record_trial_milestone tool from an allowlist (no ASINs, SKUs, account IDs, links or free-form data) and never calls
anything itself: this script never uses the network.

It prints JSON and exits 0, 1 when it refused (with "error"), or 2 when the arguments are wrong.
Standard-library Python 3.8+ in one file.
"""
import argparse
import datetime as dt
import hashlib
import json
import math
import os
import re
import sys
import tempfile
from pathlib import Path

SCHEMA = 'caiman.trial-week.v1'
CHECK_SCHEMA = 'caiman.trial-week-check.v1'
RECORD = Path('.caiman') / 'trial-week.json'
TOOL = 'record_trial_milestone'
RECAP_WINDOW_HOURS = 48           # the recap is due once the trial has this little time left (after the first view)
LATE_GRACE = dt.timedelta(days=2)  # milestones and the recap can still be recorded this long after the trial ends
KIT_CLOCK_SLACK = dt.timedelta(hours=6)   # a kit installed this long before the trial began means an existing folder
MAX_RECORD_BYTES = 256 * 1024
MAX_REVIEW_FOLDERS = 20000

# NEXT_STEP.py's workflow names, plus "advertising" (its short name for the Weekly Review).
WORKFLOWS = ('deep-seed', 'weekly-growth-review', 'listing-creative-pack', 'stock-profit-plan', 'advertising',
             'advertising-weekly-review', 'advertising-daily-check', 'advertising-structure-review')
PLANS = {'vip': 'vip', 'gls_plus': 'gls_plus', 'gls-plus': 'gls_plus', 'glsplus': 'gls_plus', 'gls+': 'gls_plus'}
# Each milestone and the only details it may carry. Kinds are checked in details().
MILESTONES = {
    'first_view_ready': {'first_workflow': 'workflow'},
    'action_list_ready': {'open_fix_count': 'count', 'wasted_spend_30d': 'money', 'harvest_count': 'count',
                          'listing_findings_count': 'count',
                          'currency': 'currency', 'period_start': 'date', 'period_end': 'date',
                          'top_nonads_finding': 'text', 'money_finder_estimate': 'estimate'},
    'first_fix_approved': {},
    'creative_pack_ready': {},
    'vip_machine_ready': {},
    'week_one_complete': {},
}
REQUIRED = {'first_view_ready': ('first_workflow',), 'action_list_ready': ('open_fix_count',)}
ORDER = ('first_view_ready', 'action_list_ready', 'first_fix_approved', 'creative_pack_ready', 'vip_machine_ready',
         'week_one_complete')
ESTIMATE_KEYS = {'monthly_amount': 'money', 'period_start': 'date', 'period_end': 'date', 'method': 'text', 'label': 'label'}

# Signs that Deep Seed (or other Caiman work on this business) already started in the folder. Left out on purpose,
# because they appear before Deep Seed: the setup check's CAIMAN STATUS.md, the kit itself (RELEASE_MANIFEST.json,
# .claude/skills, .caiman bookkeeping), the starter notes (CLIENT_RULES.md, MEMORY.md), and NEXT_STEP.py's plan
# before a business view exists (CAIMAN PLAN.md, a plan state with only settings).
STARTED_FILES = (
    'FIRST_WEEK_STATE.json',                          # Deep Seed's history plan, a dashboard or a review saved progress
    '.caiman/active-source-index.json',               # reports registered for the business view
    '.caiman/local-files.json',
    'GLS_PLUS_CONFIG.json',                           # GLS+ account details saved
    'Operating Framework/VIP Machine/config/brand.json',   # a VIP Machine set up in place
)
STARTED_FOLDERS = (
    'VIP Machine',                                    # a VIP Machine copied out of the kit
    'Operating Framework/VIP Machine/state',
)
STARTED_NONEMPTY_FOLDERS = (
    'Reports/raw',                                    # reports Caiman saved
    'GLS Plus Workspace/evidence',
    '.caiman/setup-inputs',                           # account reads saved during setup
)
VIEW_FILES = ('operating-view.json', 'review-receipt.json')   # a business view or read-only review under Reviews/

ASIN = re.compile(r'\b[Bb]0[0-9A-Za-z]{8}')
DOMAIN = re.compile(r'\b[A-Za-z0-9-]+\.[A-Za-z]{2,}\b')
CONTACT = re.compile(r'@|https?:|www\.', re.IGNORECASE)
TOKEN = re.compile(r'[A-Za-z0-9]+')
JOINED = re.compile(r'[A-Za-z0-9]+(?:[-_/][A-Za-z0-9]+)+')
PHONE = re.compile(r'(?<!\d)(?:\+?\d{1,2}[\s.-]?)?\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}(?!\d)')
# Words that mix letters and digits but aren't codes: an amount with a unit of two or more letters (1000mg, 250ml,
# 4000mAh, 100pcs) and a size (60x80, 2x4ft). Anything else, such as iPhone15 or 1000W, is refused: written with a
# space or a hyphen ("iPhone 15", "1000-watt") it passes.
HARMLESS = re.compile(r'\d+(?:\.\d+)?(?:mg|mcg|kg|oz|lbs?|ml|cl|ft|in|inch|cm|mm|pcs?|pk|pack|ct|count|kw|'
                      r'mah|ah|wh|hz|khz|gb|mb|tb|qt|gal|yd|sqft|ply|th|st|nd|rd)'
                      r'|\d+x\d+(?:ft|in|cm|mm|m)?', re.IGNORECASE)


class Refused(Exception):
    """The command can't do what was asked; nothing was written."""


# ------------------------------------------------------------------------------------------------ small helpers

def now_utc(text=None):
    if text:
        value = parse_time(text)
        if value is None:
            raise Refused('--now is not a readable date and time.')
        return value
    return dt.datetime.now(dt.timezone.utc)


def parse_time(value):
    """A timezone-aware UTC datetime from an ISO 8601 text (a date alone counts as its midnight UTC), else None.
    Takes Z, +HH:MM, +HHMM and +HH offsets, comma or point fractions and the basic format (20261019T170000Z)."""
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if re.fullmatch(r'\d{4}-\d{2}-\d{2}', text):
        try:
            day = dt.date(int(text[:4]), int(text[5:7]), int(text[8:10]))
        except ValueError:
            return None
        return dt.datetime(day.year, day.month, day.day, tzinfo=dt.timezone.utc)
    basic = re.fullmatch(r'(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})([.,]\d+)?(.*)', text)
    if basic:
        text = '{}-{}-{}T{}:{}:{}{}{}'.format(*(part or '' for part in basic.groups()))
    text = text.replace(' ', 'T', 1)
    text = re.sub(r'[,.](\d+)', lambda m: '.' + (m.group(1) + '000000')[:6], text, count=1)
    if text[-1:] in ('Z', 'z'):
        text = text[:-1] + '+00:00'
    offset = re.search(r'([+-])(\d{2})(?::?(\d{2}))?$', text)
    if offset and 'T' in text and offset.start() > text.index('T'):
        text = text[:offset.start()] + '{}{}:{}'.format(offset.group(1), offset.group(2), offset.group(3) or '00')
    try:
        moment = dt.datetime.fromisoformat(text)
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=dt.timezone.utc)
    return moment.astimezone(dt.timezone.utc)


def iso(moment):
    return moment.astimezone(dt.timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def text_value(value):
    return value.strip() if isinstance(value, str) and value.strip() else None


def as_dict(value):
    return value if isinstance(value, dict) else {}


def emit(payload, code=0):
    sys.stdout.write(json.dumps(payload, indent=2, sort_keys=False) + '\n')
    return code


def read_arg(text, what):
    """The text of an argument, or of the file it names with @."""
    raw = text.strip()
    if raw.startswith('@'):
        try:
            with open(os.path.expanduser(raw[1:].strip()), 'r', encoding='utf-8-sig') as handle:
                return handle.read()
        except OSError as error:
            raise Refused("The {} file {} can't be read ({}).".format(what, raw[1:].strip(), error.strerror or error))
    return raw


# ------------------------------------------------------------------------------------------------ the folder

def project(root_text):
    root = Path(os.path.expanduser(root_text))
    if not root.is_dir():
        raise Refused("The business folder {} doesn't exist or isn't a folder.".format(root_text))
    return root.resolve()


def is_workspace(root):
    """A folder that holds brands' business folders rather than being one: no kit of its own, and CAIMAN
    WORKSPACE.json or a kit up to three levels down."""
    if (root / 'RELEASE_MANIFEST.json').is_file():
        return False
    if (root / 'CAIMAN WORKSPACE.json').is_file():
        return True
    seen = 0
    for current, subfolders, files in os.walk(str(root)):
        depth = len(Path(current).relative_to(root).parts)
        subfolders[:] = [name for name in subfolders if not name.startswith(('.', '_')) and depth < 3]
        if depth and 'RELEASE_MANIFEST.json' in files:
            return True
        seen += 1
        if seen > 2000:
            break
    return False


def has_entries(folder):
    """True when the folder holds anything other than hidden files (.DS_Store and the like)."""
    try:
        return folder.is_dir() and any(not entry.name.startswith('.') for entry in folder.iterdir())
    except OSError:
        return True          # unreadable: count it, so an existing business is never put through this


def kit_first_installed(root):
    """When a kit was first installed in this folder, from kit-sync's install records, or None."""
    folder = root / '.caiman' / 'kit-installations'
    earliest = None
    try:
        paths = sorted(folder.glob('*.json'))[:200] if folder.is_dir() else []
    except OSError:
        paths = []
    for path in paths:
        try:
            if path.is_symlink() or path.stat().st_size > 4 * 1024 * 1024:
                continue
            moment = parse_time(as_dict(json.loads(path.read_text(encoding='utf-8'))).get('installed_at'))
        except (OSError, ValueError):
            continue
        if moment is not None and (earliest is None or moment < earliest):
            earliest = moment
    return earliest


def started_signs(root, trial_started_at=None):
    """The things in the folder that show Deep Seed (or other Caiman work on this business) already started, or that
    the folder was in use before the trial began."""
    found = []
    for rel in STARTED_FILES:
        if (root / rel).is_file():
            found.append(rel)
    for rel in STARTED_FOLDERS:
        if (root / rel).is_dir():
            found.append(rel + '/')
    for rel in STARTED_NONEMPTY_FOLDERS:
        if has_entries(root / rel):
            found.append(rel + '/')
    state_path = root / '.caiman' / 'plan' / 'state.json'
    if state_path.is_file():
        try:
            state = as_dict(json.loads(state_path.read_text(encoding='utf-8')))
        except (OSError, ValueError):
            state = {'unreadable': True}
        events = state.get('events') if isinstance(state.get('events'), list) else []
        work = [event for event in events
                if not (isinstance(event, dict) and event.get('event') in ('set', 'focus', 'focus-cleared'))]
        if state.get('first_view_on') or state.get('items') or work or state.get('unreadable'):
            found.append('.caiman/plan/state.json')
    reviews = root / 'Reviews'
    if reviews.is_dir():
        seen = 0
        for current, _subfolders, files in os.walk(str(reviews)):
            seen += 1
            hit = [name for name in VIEW_FILES if name in files]
            if hit:
                found.append((Path(current) / hit[0]).relative_to(root).as_posix())
                break
            if seen > MAX_REVIEW_FOLDERS:
                found.append('Reviews/')
                break
    installed = kit_first_installed(root)
    if installed is not None and trial_started_at is not None and installed < trial_started_at - KIT_CLOCK_SLACK:
        found.append('kit installed {} (before the trial began)'.format(iso(installed)))
    return found


def folder_plan(root):
    """The membership the folder's kit is for, when a kit is installed: plan_tier in ENTITLEMENTS.json."""
    try:
        raw = json.loads((root / 'ENTITLEMENTS.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    return norm_plan(as_dict(raw).get('plan_tier'))


def norm_plan(value):
    text = text_value(value)
    return PLANS.get(text.lower().replace(' ', '')) if text else None


# ------------------------------------------------------------------------------------------------ the record

def record_path(root):
    caiman = root / '.caiman'
    if caiman.is_symlink() or (caiman.exists() and not caiman.is_dir()):
        raise Refused('.caiman in the business folder is not an ordinary folder, so the trial week has nowhere safe to keep '
                      'its record. Nothing was written.')
    return root / RECORD


def read_record(root):
    path = record_path(root)
    if not path.exists():
        return None
    if path.is_symlink() or not path.is_file():
        raise Refused('.caiman/trial-week.json is not an ordinary file. Nothing was changed.')
    if path.stat().st_size > MAX_RECORD_BYTES:
        raise Refused('.caiman/trial-week.json is larger than expected. Nothing was changed.')
    try:
        record = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError) as error:
        raise Refused(".caiman/trial-week.json can't be read ({}). Nothing was changed.".format(error))
    if not isinstance(record, dict) or record.get('schema') != SCHEMA:
        raise Refused('.caiman/trial-week.json is not a trial-week record this script knows. Nothing was changed.')
    if not isinstance(record.get('milestones'), dict):
        record['milestones'] = {}
    return record


def write_record(root, record):
    path = record_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise Refused('.caiman/trial-week.json is a link, not a file. Nothing was written.')
    data = json.dumps(record, indent=2, sort_keys=False) + '\n'
    handle, temp = tempfile.mkstemp(prefix='.trial-week-', suffix='.json', dir=str(path.parent))
    try:
        with os.fdopen(handle, 'w', encoding='utf-8') as out:
            out.write(data)
        os.replace(temp, str(path))
    except BaseException:
        try:
            os.unlink(temp)
        except OSError:
            pass
        raise


# ------------------------------------------------------------------------------------------------ list_brands

def read_brands(text):
    """(answer dict, brands list, whole_answer) from --connector-brands-json, or (None, None, False) when not given.
    whole_answer is False when only a list of brands was passed (it has no top-level membership)."""
    if text is None:
        return None, None, False
    raw = read_arg(text, 'list_brands')
    starts = [at for at in (raw.find('['), raw.find('{')) if at >= 0]      # the answer can start with a line of text
    try:
        value = json.JSONDecoder().raw_decode(raw[min(starts):])[0] if starts else json.loads(raw)
    except ValueError as error:
        raise Refused("--connector-brands-json isn't readable JSON ({}).".format(error))
    if isinstance(value, list):
        return {}, [as_dict(item) for item in value], False
    if isinstance(value, dict):
        items = value.get('items') if isinstance(value.get('items'), list) else value.get('brands')
        return value, [as_dict(item) for item in (items if isinstance(items, list) else [])], True
    raise Refused("--connector-brands-json should be list_brands' answer.")


def slug_of(item):
    return text_value(item.get('slug')) or text_value(item.get('brand_slug'))


def facts_of(member):
    """The trial's facts from a membership dict (None values when unknown)."""
    member = as_dict(member)
    status = (text_value(member.get('status')) or '').lower() or None
    return {'status': status, 'free_trial': member.get('free_trial') is True, 'plan': norm_plan(member.get('plan')),
            'trial_started_at': parse_time(member.get('trial_started_at') or member.get('trial_start')),
            'trial_ends_at': parse_time(member.get('trial_ends_at') or member.get('trial_end')),
            'billing_date': text_value(member.get('billing_date'))}


def on_free_trial(facts):
    return bool(facts) and facts['status'] == 'trialing' and facts['free_trial']


def resolve(answer, brands, whole, slug):
    """What list_brands says about this business: {'slug', 'candidate', 'facts', 'items', 'problem'}.
    With several brands listed, only each brand's own membership counts: the answer's top-level one doesn't say which
    brand is on the trial. slug: the brand chosen, None when it isn't known yet. items: the brand items whose
    relationship matters (the chosen brand, or the brands that could be the trial's)."""
    listed = {}
    for item in brands:
        if slug_of(item):
            listed.setdefault(slug_of(item), item)
    if slug and slug not in listed:
        return problem('unknown_brand', 'list_brands shows no brand {}. Use a slug it shows.'.format(slug), slug)
    own = {s: i['membership'] for s, i in listed.items() if isinstance(i.get('membership'), dict)}
    top = answer.get('membership') if isinstance(answer.get('membership'), dict) else None
    if not whole and not own:
        return problem('whole_answer_needed', "Only a list of brands was passed. Pass list_brands' whole answer, which "
                       'carries the membership.', slug)
    several = len(listed) >= 2
    chosen = slug or (next(iter(listed)) if len(listed) == 1 else None)
    if chosen:
        member = own.get(chosen) or (None if several else top)
        if member is not None:
            return {'slug': chosen, 'candidate': None, 'facts': facts_of(member), 'items': [listed[chosen]],
                    'problem': None}
        if several and own:
            return problem('no_brand_membership', 'list_brands gives other brands a membership but not {}, so it is not '
                           'on the free trial.'.format(chosen), chosen)
        if several and top:
            return problem('brand_membership_needed', "list_brands shows several brands but doesn't say which one the "
                           'membership is for.', chosen)
        return problem('no_membership_status', 'list_brands shows no membership status for this account.', chosen)
    if not several:                                   # no brand listed yet (Amazon not connected)
        if top is None:
            return problem('no_membership_status', 'list_brands shows no membership status for this account.', None)
        return {'slug': None, 'candidate': None, 'facts': facts_of(top), 'items': [], 'problem': None}
    if not own:
        if top:
            return problem('brand_membership_needed', "list_brands shows several brands but doesn't say which one the "
                           'membership is for.', None)
        return problem('no_membership_status', 'list_brands shows no membership status for this account.', None)
    trials = [s for s, m in own.items() if on_free_trial(facts_of(m))]
    if not trials:
        return dict(problem('none_on_trial', 'None of the brands list_brands shows is on the free trial.', None),
                    facts=facts_of(next(iter(own.values()))))
    owned = [s for s in trials if not not_owner([listed[s]])]
    pool = owned or trials                            # only others' brands on the trial: not_owner says so
    return {'slug': None, 'candidate': pool[0] if len(pool) == 1 else None, 'facts': facts_of(own[pool[0]]),
            'items': [listed[s] for s in pool], 'problem': None}


def problem(code, detail, slug):
    return {'slug': slug, 'candidate': None, 'facts': None, 'items': [], 'problem': (code, detail)}


def other_memberships(brands):
    """The member's own brands whose membership isn't the free trial (a current or past subscription)."""
    found = []
    for item in brands:
        member = item.get('membership')
        if slug_of(item) and isinstance(member, dict) and not not_owner([item]) and not on_free_trial(facts_of(member)):
            found.append(slug_of(item))
    return found


def not_owner(items):
    """The relationship of a brand that isn't the member's own (staff, agency and the like), or None."""
    for item in items:
        relation = (text_value(item.get('relationship')) or '').lower()
        if relation and relation != 'owner':
            return relation
    return None


# ------------------------------------------------------------------------------------------------ check

def evaluate(root, answer, brands, whole, slug, now):
    """The trial week's state in this folder, without writing anything. Adds '_refresh' when a running trial week's
    dates or plan should be brought up to date from the server."""
    if is_workspace(root):
        return {'trial_week': 'none', 'reason': 'workspace_folder',
                'detail': "This folder holds brands' business folders. Run the check in each brand's own folder."}
    record = read_record(root)
    if record is not None:
        return evaluate_running(root, record, answer, brands, whole, slug, now)
    if answer is None:
        return {'trial_week': 'none', 'reason': 'no_connector_answer',
                'detail': 'No list_brands answer was given, so there is no trial status to go on.'}
    found = resolve(answer, brands, whole, slug)
    if found['problem']:
        code = found['problem'][0]
        return {'trial_week': 'none', 'reason': 'not_on_trial' if code in ('none_on_trial', 'no_brand_membership') else code,
                'detail': found['problem'][1]}
    facts = found['facts']
    if facts['status'] != 'trialing':
        return {'trial_week': 'none', 'reason': 'not_on_trial',
                'detail': "The Caiman server shows this account as '{}'.".format(facts['status'] or 'unknown')}
    if not facts['free_trial']:
        return {'trial_week': 'none', 'reason': 'not_a_free_trial',
                'detail': "The account is in a trial period, but not Caiman's free trial week."}
    relation = not_owner(found['items'])
    if relation:
        return {'trial_week': 'none', 'reason': 'not_owner',
                'detail': "This login is '{}' on the brand, not its owner.".format(relation)}
    if other_memberships(brands):
        return {'trial_week': 'none', 'reason': 'existing_member',
                'detail': 'This login already has another Caiman membership, so it is not a new member\'s free week.'}
    if facts['trial_ends_at'] is None:
        return {'trial_week': 'none', 'reason': 'no_trial_dates',
                'detail': 'The account is on the free trial, but list_brands gives no trial end date.'}
    if now >= facts['trial_ends_at']:
        return {'trial_week': 'none', 'reason': 'trial_over', 'trial_ends_at': iso(facts['trial_ends_at']),
                'detail': 'The free trial has already ended.'}
    signs = started_signs(root, facts['trial_started_at'])
    if signs:
        return {'trial_week': 'none', 'reason': 'already_started', 'signs': signs[:10],
                'detail': 'Caiman work on this business had already started here, so it carries on as usual.'}
    return {'trial_week': 'start', 'reason': 'new_trial', 'brand_slug': found['slug'],
            'brand_candidate': found.get('candidate'), 'needs_brand': found['slug'] is None,
            'announce': found['slug'] is not None or not any(slug_of(item) for item in brands),
            'plan': facts['plan'] or folder_plan(root), 'trial_ends_at': iso(facts['trial_ends_at']),
            'billing_date': facts['billing_date'],
            'detail': "This account is on Caiman's free trial and this folder hasn't started Deep Seed: start the trial week."}


def evaluate_running(root, record, answer, brands, whole, slug, now):
    base = {'brand_slug': record.get('brand_slug'), 'plan': record.get('plan'), 'record': RECORD.as_posix()}
    if slug and record.get('brand_slug') and slug != record['brand_slug']:
        base['note'] = 'The trial week here is for {}, not {}.'.format(record['brand_slug'], slug)
    if record.get('stopped_at'):
        return dict(base, trial_week='none', reason='stopped',
                    detail='The trial week here was stopped on {} ({}).'.format(record['stopped_at'],
                                                                             record.get('stop_reason') or 'by the member'))
    facts = None
    if answer is not None:
        found = resolve(answer, brands, whole, record.get('brand_slug'))
        if found['problem'] and found['problem'][0] == 'none_on_trial':
            return dict(base, trial_week='none', reason='trial_over',
                        detail='The Caiman server shows none of the listed brands on the free trial any more.')
        facts = found['facts'] if not found['problem'] else None
    if facts is not None and facts['status'] and not on_free_trial(facts):
        return dict(base, trial_week='none', reason='trial_over',
                    detail="The Caiman server shows this account as '{}', not on the free trial.".format(facts['status']))
    ends = (facts or {}).get('trial_ends_at') or parse_time(record.get('trial_ends_at'))
    if ends is None:
        return dict(base, trial_week='none', reason='no_trial_dates',
                    detail="Neither the Caiman server nor the record has the trial's end date.")
    if now >= ends:
        return dict(base, trial_week='none', reason='trial_over', trial_ends_at=iso(ends),
                    detail='The free trial ended on {}.'.format(iso(ends)))
    begun = (facts or {}).get('trial_started_at') or parse_time(record.get('trial_started_at')) \
        or parse_time(record.get('started_at')) or now
    out = dict(base, **progress(record, begun, ends, now))
    out['billing_date'] = (facts or {}).get('billing_date') or record.get('billing_date')
    out['needs_brand'] = not record.get('brand_slug')
    out['announced'] = bool(record.get('announced', True))
    if record.get('brand_candidate') and not record.get('brand_slug'):
        out['brand_candidate'] = record['brand_candidate']
    refresh = {}
    if facts is not None:
        if facts['trial_ends_at'] and iso(facts['trial_ends_at']) != record.get('trial_ends_at'):
            refresh['trial_ends_at'] = iso(facts['trial_ends_at'])
        if facts['billing_date'] and facts['billing_date'] != record.get('billing_date'):
            refresh['billing_date'] = facts['billing_date']
        if facts['plan'] and not record.get('plan'):
            refresh['plan'] = facts['plan']
    if not record.get('plan') and 'plan' not in refresh and folder_plan(root):
        refresh['plan'] = folder_plan(root)
    if refresh:
        out['_refresh'] = refresh
        out.update({key: value for key, value in refresh.items() if key in ('plan', 'billing_date')})
    return out


def progress(record, begun, ends, now):
    """Where a running trial week stands: its day, time left, what's been reached and what comes next."""
    day = max(0, int((now - begun).total_seconds() // 86400))
    hours_left = max(0.0, (ends - now).total_seconds() / 3600.0)
    reached = {name: as_dict(entry).get('state') for name, entry in as_dict(record.get('milestones')).items()
               if name in MILESTONES}
    recap_saved = bool(as_dict(record.get('recap')).get('path'))
    recap_due = not recap_saved and 'first_view_ready' in reached and hours_left <= RECAP_WINDOW_HOURS
    if recap_due:
        focus = 'recap'
    elif 'first_view_ready' not in reached:
        focus = 'deep_seed'
    elif 'action_list_ready' not in reached:
        focus = 'first_workflow'
    elif 'creative_pack_ready' not in reached:
        focus = 'listing_creative_pack'
    else:
        focus = 'plan_next_step'
    unconfirmed = sorted((name for name, state in reached.items() if state == 'pending'), key=ORDER.index)
    return {'trial_week': 'active', 'reason': 'in_progress', 'day': day, 'hours_left': round(hours_left, 1),
            'trial_ends_at': iso(ends), 'recap_due': recap_due, 'recap_saved': recap_saved,
            'reporting': bool(record.get('reporting', True)), 'milestones': reached, 'unconfirmed': unconfirmed,
            'next': focus}


# ------------------------------------------------------------------------------------------------ milestone details

def id_like(text):
    """Why the text looks like it holds an ID, a code, a link or a phone number, or None."""
    if ASIN.search(text):
        return 'an ASIN'
    if CONTACT.search(text) or DOMAIN.search(text):
        return 'an email or a link'
    if PHONE.search(text):
        return 'a phone number'
    for token in TOKEN.findall(text):
        letters = sum(ch.isalpha() for ch in token)
        digits = sum(ch.isdigit() for ch in token)
        if letters and digits and len(token) >= 5 and not harmless(token):
            return 'a product, SKU or account code ({})'.format(token)
        if digits >= 7:
            return 'a long number ({})'.format(token)
    for match in JOINED.finditer(text):
        parts = re.split(r'[-_/]', match.group(0))
        caps = [part for part in parts if part.isalpha() and part.isupper() and len(part) >= 2]
        has_digit = any(any(ch.isdigit() for ch in part) for part in parts)
        wordy = [part for part in parts if part.isalpha()]
        if (caps and has_digit) or len(caps) >= 4 or (len(parts) >= 3 and has_digit and len(wordy) >= 2):
            return 'a SKU ({})'.format(match.group(0))
    return None


def harmless(token):
    """A token with letters and digits that is a measurement or a size rather than a code."""
    return HARMLESS.fullmatch(token) is not None


def clean_text(value, limit, where):
    if not isinstance(value, str) or not value.strip():
        raise Refused('{} must be plain text.'.format(where))
    text = ' '.join(value.split())
    if len(text) > limit:
        raise Refused('{} is longer than {} characters; shorten it.'.format(where, limit))
    if any(ord(ch) < 32 for ch in text):
        raise Refused('{} has control characters.'.format(where))
    why = id_like(text)
    if why:
        raise Refused('{} looks like it holds {}. Write it in words only, for example "Main image clicks trail the market '
                      'on the queen sets".'.format(where, why))
    return text


def check_value(kind, value, where):
    if kind == 'count':
        if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value < 1000000:
            raise Refused('{} must be a whole number of 0 or more.'.format(where))
        return value
    if kind == 'money':
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) \
                or not 0 <= value < 1e9:
            raise Refused('{} must be an amount of 0 or more.'.format(where))
        return round(float(value), 2)
    if kind == 'currency':
        if not isinstance(value, str) or not re.fullmatch(r'[A-Z]{3}', value.strip().upper()):
            raise Refused('{} must be a three-letter currency code such as USD (the Ads profile\'s currency_code), not '
                          'a symbol.'.format(where))
        return value.strip().upper()
    if kind == 'date':
        if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value.strip()) \
                or parse_time(value.strip()) is None:
            raise Refused('{} must be a date as YYYY-MM-DD.'.format(where))
        return value.strip()
    if kind == 'workflow':
        if value not in WORKFLOWS:
            raise Refused('{} must be one of: {}.'.format(where, ', '.join(WORKFLOWS)))
        return value
    if kind == 'text':
        return clean_text(value, 120, where)
    if kind == 'label':
        if value != 'estimate':
            raise Refused('{} must be "estimate": a projected figure is only ever sent labelled as one.'.format(where))
        return value
    if kind == 'estimate':
        item = as_dict(value)
        if not item:
            raise Refused('{} must be an object.'.format(where))
        extra = sorted(set(item) - set(ESTIMATE_KEYS))
        missing = sorted(set(ESTIMATE_KEYS) - set(item))
        if extra or missing:
            raise Refused('{} needs exactly {}{}.'.format(where, ', '.join(sorted(ESTIMATE_KEYS)),
                                                         ' (not {})'.format(', '.join(extra)) if extra else ''))
        out = {key: check_value(ESTIMATE_KEYS[key], item[key], '{}.{}'.format(where, key)) for key in sorted(ESTIMATE_KEYS)}
        if out['period_start'] > out['period_end']:
            raise Refused('{} starts after it ends.'.format(where))
        return out
    raise Refused('Unknown kind {}.'.format(kind))


def details(name, raw, plan):
    allowed = MILESTONES[name]
    if raw is not None and not isinstance(raw, dict):
        raise Refused('--details-json must be a JSON object.')
    item = as_dict(raw)
    extra = sorted(set(item) - set(allowed))
    if extra:
        raise Refused('{} takes only {}; remove {}.'.format(name, ', '.join(sorted(allowed)) or 'no details',
                                                            ', '.join(extra)))
    missing = [key for key in REQUIRED.get(name, ()) if key not in item]
    if missing:
        raise Refused('{} needs {}.'.format(name, ', '.join(missing)))
    out = {key: check_value(allowed[key], item[key], key) for key in allowed if key in item}
    if 'wasted_spend_30d' in out and not all(key in out for key in ('currency', 'period_start', 'period_end')):
        raise Refused('wasted_spend_30d needs its currency, period_start and period_end.')
    if 'period_start' in out and 'period_end' in out and out['period_start'] > out['period_end']:
        raise Refused('period_start is after period_end.')
    if name == 'vip_machine_ready' and plan != 'vip':
        raise Refused('vip_machine_ready is for VIP businesses only.')
    return out


def payload_hash(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode('utf-8')).hexdigest()


# ------------------------------------------------------------------------------------------------ commands

def running_record(root, now, dated=True):
    """The record of the trial week running here (else Refused). dated: also refuse once the trial is well over."""
    record = read_record(root)
    if record is None:
        raise Refused('No trial week has started in this business folder, so there is nothing to record.')
    if record.get('stopped_at'):
        raise Refused('The trial week here was stopped on {}.'.format(record['stopped_at']))
    ends = parse_time(record.get('trial_ends_at'))
    if dated and ends is not None and now >= ends + LATE_GRACE:
        raise Refused('The free trial ended on {}; the trial week is over.'.format(iso(ends)))
    return record


def cmd_check(args, now):
    try:
        root = project(args.project_root)
        answer, brands, whole = read_brands(args.connector_brands_json)
        result = evaluate(root, answer, brands, whole, text_value(args.brand_slug), now)
    except Exception as error:          # the check never stands in the way: any problem means no trial week
        result = {'trial_week': 'none', 'reason': 'check_failed',
                  'detail': 'The check could not finish ({}), so there is no trial week this session.'.format(
                      str(error)[:300])}
    refresh = result.pop('_refresh', None)
    if refresh:
        try:
            record = read_record(root)
            record.update(refresh)
            write_record(root, record)
        except Exception as error:
            result['note'] = 'The new trial dates could not be saved ({}); they are used this session.'.format(
                str(error)[:200])
    return emit(dict({'schema': CHECK_SCHEMA, 'checked_at': iso(now)}, **result))


def cmd_start(args, now):
    root = project(args.project_root)
    answer, brands, whole = read_brands(args.connector_brands_json)
    if answer is None:
        raise Refused('start needs the list_brands answer (--connector-brands-json).')
    result = evaluate(root, answer, brands, whole, text_value(args.brand_slug), now)
    result.pop('_refresh', None)
    if result['trial_week'] == 'active':
        return emit(dict({'schema': CHECK_SCHEMA, 'checked_at': iso(now), 'started': False,
                          'note': 'The trial week was already running here.'}, **result))
    if result['trial_week'] != 'start':
        raise Refused("The trial week can't start here: {} ({}). Nothing was written.".format(
            result.get('detail', ''), result['reason']))
    found = resolve(answer, brands, whole, result['brand_slug'])
    facts = found['facts']
    record = {'schema': SCHEMA, 'brand_slug': result['brand_slug'], 'brand_candidate': result.get('brand_candidate'),
              'plan': result.get('plan'), 'started_at': iso(now),
              'trial_started_at': iso(facts['trial_started_at']) if facts['trial_started_at'] else None,
              'trial_ends_at': iso(facts['trial_ends_at']), 'billing_date': facts['billing_date'],
              'reporting': True, 'announced': bool(result.get('announce')), 'stopped_at': None, 'stop_reason': None,
              'recap': None, 'milestones': {}}
    write_record(root, record)
    out = evaluate(root, answer, brands, whole, result['brand_slug'], now)
    out.pop('_refresh', None)
    out['announce'] = bool(result.get('announce'))
    return emit(dict({'schema': CHECK_SCHEMA, 'checked_at': iso(now), 'started': True}, **out))


def cmd_bind(args, now):
    root = project(args.project_root)
    record = running_record(root, now)
    answer, brands, whole = read_brands(args.connector_brands_json)
    slug = text_value(args.brand_slug)
    if answer is None or not slug:
        raise Refused('bind needs the list_brands answer and --brand-slug.')
    if record.get('brand_slug'):
        if record['brand_slug'] == slug:
            return emit({'ok': True, 'brand_slug': slug, 'announce': False, 'note': 'Already tied to this brand.'})
        raise Refused('The trial week here is already tied to {}.'.format(record['brand_slug']))
    found = resolve(answer, brands, whole, slug)
    code = found['problem'][0] if found['problem'] else None
    if code and code != 'no_brand_membership':
        raise Refused('{} The trial week was left as it is.'.format(found['problem'][1]))
    facts = found['facts']
    listed = {slug_of(item): item for item in brands if slug_of(item)}
    relation = not_owner([listed[slug]])
    if not code and not relation and on_free_trial(facts):
        announce = not record.get('announced', True)
        record.update(brand_slug=slug, brand_candidate=None, announced=True,
                      plan=record.get('plan') or facts['plan'] or folder_plan(root))
        if facts['trial_ends_at']:
            record['trial_ends_at'] = iso(facts['trial_ends_at'])
        write_record(root, record)
        return emit({'ok': True, 'brand_slug': slug, 'plan': record['plan'], 'announce': announce})
    others = [s for s, item in listed.items() if s != slug and isinstance(item.get('membership'), dict)
              and on_free_trial(facts_of(item['membership'])) and not not_owner([item])]
    clear = bool(relation) or (not code and bool(facts['status']))      # someone else's brand, or another membership
    if not args.not_on_trial and (others or not clear):
        why = ("{} isn't on the free trial, but {} is.".format(slug, ', '.join(others)) if others else
               'list_brands shows no membership for {}.'.format(slug))
        raise Refused('{} Check with the member which brand this folder is for. If it is {}, run bind again with '
                      '--not-on-trial; the trial week then stops here. The trial week was left as it is.'.format(why, slug))
    record.update(stopped_at=iso(now), reporting=False,
                  stop_reason='the confirmed brand {} is not on the free trial'.format(slug))
    write_record(root, record)
    return emit({'ok': True, 'brand_slug': slug, 'trial_week': 'none', 'reason': 'brand_not_on_trial', 'announce': False,
                 'detail': "The confirmed brand isn't on Caiman's free trial, so the trial week stops here and Caiman "
                           'carries on as usual.'})


def cmd_milestone(args, now):
    root = project(args.project_root)
    name = args.name
    if name not in MILESTONES:
        raise Refused('Unknown milestone {}; use one of: {}.'.format(name, ', '.join(ORDER)))
    record = running_record(root, now)
    entries = record['milestones']
    entry = as_dict(entries.get(name))
    if args.sent or args.not_sent is not None:
        if entry.get('state') != 'pending':
            raise Refused('{} has no prepared call waiting to be confirmed (its state is {}).'.format(
                name, entry.get('state') or 'not reached'))
        if args.sent:
            entry.update(state='sent', sent_at=iso(now))
        else:
            entry.update(state='not_sent', reason=clean_reason(args.not_sent), noted_at=iso(now))
        entries[name] = entry
        write_record(root, record)
        return emit({'ok': True, 'milestone': name, 'state': entry['state']})
    if entry.get('state') in ('sent', 'not_sent', 'reporting_off'):
        return emit({'ok': True, 'milestone': name, 'send': False, 'state': entry['state'],
                     'note': 'Already recorded; nothing more to send for it.'})
    if not record.get('brand_slug'):
        raise Refused('The trial week here isn\'t tied to a brand yet. Once the member confirms the brand, run '
                      'trial_week.py bind --brand-slug <slug>, then record the milestone.')
    if not record.get('plan') and folder_plan(root):
        record['plan'] = folder_plan(root)
    if not record.get('plan'):
        raise Refused("The membership (VIP or GLS+) isn't known yet: list_brands gave no plan and the kit isn't installed. "
                      'Install the kit (or run the check again once list_brands shows the plan), then record the '
                      'milestone.')
    try:
        raw = json.loads(read_arg(args.details_json, 'details')) if args.details_json else None
    except ValueError as error:
        raise Refused("--details-json isn't readable JSON ({}).".format(error))
    clean = details(name, raw, record.get('plan'))
    if name == 'week_one_complete' and not as_dict(record.get('recap')).get('path'):
        raise Refused('Save the recap and record it (trial_week.py recap --saved <file>) before week_one_complete.')
    if not record.get('reporting', True):
        entries[name] = {'state': 'reporting_off', 'reached_at': iso(now)}
        write_record(root, record)
        return emit({'ok': True, 'milestone': name, 'send': False, 'state': 'reporting_off',
                     'note': 'The member turned progress reports off; the milestone is noted here only.'})
    call = {'tool': TOOL, 'arguments': {'brand_slug': record['brand_slug'], 'milestone': name, 'occurred_at': iso(now),
                                        'plan': record.get('plan'), 'details': clean}}
    digest = payload_hash(clean)
    if entry.get('state') == 'pending' and entry.get('payload_sha256') == digest:
        call['arguments']['occurred_at'] = entry.get('reached_at') or call['arguments']['occurred_at']
        write_record(root, record)
    else:
        entries[name] = {'state': 'pending', 'reached_at': iso(now), 'payload_sha256': digest}
        write_record(root, record)
    return emit({'ok': True, 'milestone': name, 'send': True, 'call': call,
                 'then': 'After the call: trial_week.py milestone --name {0} --sent; if the tool is not listed or the call '
                         'fails: --not-sent "<why>". It is never retried.'.format(name)})


def clean_reason(text):
    text = ' '.join(str(text or '').split())[:200]
    return text or 'not given'


def cmd_recap(args, now):
    root = project(args.project_root)
    record = running_record(root, now)
    saved = Path(os.path.expanduser(args.saved))
    path = (saved if saved.is_absolute() else root / saved).resolve()
    try:
        relative = path.relative_to(root).as_posix()
    except ValueError:
        raise Refused('The recap must be saved inside the business folder.')
    if not path.is_file():
        raise Refused("The recap {} doesn't exist yet. Save it first.".format(relative))
    record['recap'] = {'path': relative, 'saved_at': iso(now)}
    write_record(root, record)
    return emit({'ok': True, 'recap': record['recap'], 'then': 'Record the week_one_complete milestone next.'})


def cmd_reporting(args, now):
    root = project(args.project_root)
    record = running_record(root, now, dated=False)
    record['reporting'] = bool(args.on)
    write_record(root, record)
    return emit({'ok': True, 'reporting': record['reporting']})


def cmd_stop(args, now):
    root = project(args.project_root)
    try:
        record = read_record(root)
    except Refused:
        path = record_path(root)
        if path.is_symlink() or not path.is_file():
            raise
        aside = path.with_name('trial-week.unreadable-{}.json'.format(now.strftime('%Y%m%d-%H%M%S')))
        os.replace(str(path), str(aside))
        record = {'schema': SCHEMA, 'brand_slug': None, 'plan': None, 'started_at': None, 'trial_started_at': None,
                  'trial_ends_at': None, 'billing_date': None, 'reporting': False, 'recap': None, 'milestones': {},
                  'stopped_at': None, 'stop_reason': 'its record could not be read; kept as ' + aside.name}
    if record is None:
        raise Refused('No trial week has started in this business folder.')
    if not record.get('stopped_at'):
        record['stopped_at'] = iso(now)
        record['reporting'] = False
        record['stop_reason'] = record.get('stop_reason') or 'the member stopped it'
        write_record(root, record)
    return emit({'ok': True, 'stopped_at': record['stopped_at']})


def parser():
    top = argparse.ArgumentParser(description="Caiman's free trial week (see the trial week guide).")
    top.add_argument('--now', help=argparse.SUPPRESS)          # tests only
    commands = top.add_subparsers(dest='command')
    for name in ('check', 'start', 'bind'):
        sub = commands.add_parser(name)
        sub.add_argument('--project-root', '--folder', '--root', dest='project_root', required=True)
        sub.add_argument('--connector-brands-json', help="list_brands' whole answer as JSON, or @file")
        sub.add_argument('--brand-slug', help='The brand this business folder is for.')
        if name == 'bind':
            sub.add_argument('--not-on-trial', action='store_true',
                             help='The member confirmed this folder is for a brand that is not on the free trial.')
    sub = commands.add_parser('milestone')
    sub.add_argument('--project-root', '--folder', '--root', dest='project_root', required=True)
    sub.add_argument('--name', required=True)
    sub.add_argument('--details-json', help='The details as JSON, or @file')
    group = sub.add_mutually_exclusive_group()
    group.add_argument('--sent', action='store_true')
    group.add_argument('--not-sent', metavar='WHY')
    sub = commands.add_parser('recap')
    sub.add_argument('--project-root', '--folder', '--root', dest='project_root', required=True)
    sub.add_argument('--saved', required=True)
    sub = commands.add_parser('reporting')
    sub.add_argument('--project-root', '--folder', '--root', dest='project_root', required=True)
    group = sub.add_mutually_exclusive_group(required=True)
    group.add_argument('--off', action='store_true')
    group.add_argument('--on', action='store_true')
    sub = commands.add_parser('stop')
    sub.add_argument('--project-root', '--folder', '--root', dest='project_root', required=True)
    return top


COMMANDS = {'check': cmd_check, 'start': cmd_start, 'bind': cmd_bind, 'milestone': cmd_milestone, 'recap': cmd_recap,
            'reporting': cmd_reporting, 'stop': cmd_stop}


def main(argv=None):
    if sys.version_info < (3, 8):
        sys.stdout.write(json.dumps({'ok': False, 'error': 'Python 3.8 or newer is needed.'}) + '\n')
        return 1
    args = parser().parse_args(argv)
    if not args.command:
        parser().print_usage(sys.stderr)
        return 2
    try:
        now = now_utc(args.now)
    except Refused as error:
        return emit({'ok': False, 'error': str(error)}, 1)
    try:
        return COMMANDS[args.command](args, now)
    except Refused as error:
        return emit({'ok': False, 'error': str(error)}, 1)


if __name__ == '__main__':
    sys.exit(main())
