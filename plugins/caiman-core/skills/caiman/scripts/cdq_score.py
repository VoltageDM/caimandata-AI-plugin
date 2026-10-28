#!/usr/bin/env python3
"""Caiman's CDQ score for one listing, for the free trial week only (references/trial-week.md, "CDQ score").

    python3 cdq_score.py score  --project-root "<business folder>" --grades <grades.json> --listing <listing.json>
                                [--label current|proposed] [--out <cdq.json>]
    python3 cdq_score.py report --project-root "<business folder>" --scores <cdq.json> [<cdq.json> ...]
                                [--out <file.html>]

CDQ = round(50% COSMO + 30% shopper questions + 20% listing health). A break of Amazon's copy rules (guarantee,
ratings or reviews, promotional words, links, banned symbols and the like) caps it at 49; a field over its limit, the
format rules and a claim that only needs its fact on file cost listing-health points instead.
Bands: Strong 80+, Adequate 50 to 79, Needs Work under 50. Caiman's listing score, built on Amazon's
published shopping-intent research. Not an Amazon metric.

--grades   Claude's grades for this listing, by alexa-audit's rubric (meaning, specificity and placement, never
           keyword counting):
           {"asin": "B0...", "sku": "...", "product": "short name",
            "relations": {"used_for_func": {"grade": 2, "evidence": "..."}, ... all 15 ...},
            "questions": [{"question": "...", "source": "review|qa|cosmo|search", "grade": 2|1|0,
                           "evidence": "..."}],
            "health": {"attributes_filled": true|false, "variation_consistent": true|false|null,
                       "title_attributes_agree": true|false},
            "breaks": [{"field": "bullet_2", "what": "..."}]}
           A grade is 2, 1, 0 or "NA" (N/A leaves the denominator); a 2 or 1 needs its evidence. A health check
           set to null doesn't apply and leaves the denominator; "backend_populated": null (or "fields_within_limits":
           null) says that part of the listing can't be seen, as with another seller's listing, and leaves it out too. "breaks" adds rule breaks the listing check's
           words can't see (a claim reworded to dodge the banned word); it may be empty.
--listing  The listing the grades are for, in any shape listing_check.py --draft reads: a saved get_listing read,
           or {"title", "bullets", "description", "backend"} (GLS+: from the member's Category Listings Report;
           proposed copy: the Listing & Creative Pack's draft). The listing check runs on it here.
--check    Instead of running the check: a saved listing_check.py --json result for the same listing.
--label    "current" (the live listing, the default) or "proposed" (the pack's copy before it goes live).

Never stores or prints listing copy beyond the evidence snippets in the grades. Standard library only; Python 3.8+.
Exit 0 on a score, 1 when the grades or listing can't be used (the message says what to fix).
"""
import argparse
import datetime as dt
import html
import importlib.util
import json
import math
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True

LINE = "Caiman's listing score, built on Amazon's published shopping-intent research. Not an Amazon metric."
WEIGHTS = {"cosmo": 0.50, "questions": 0.30, "health": 0.20}
CAP = 49

# The 15 relations of the COSMO paper's Table 2, in alexa-audit's order, with the question each answers.
# alexa-audit keeps the paper's spelling xIntersted_in; xInterested_in is read as the same relation.
RELATIONS = [
    ("used_for_func", "What it does for you", "what job does it do?"),
    ("used_for_eve", "The occasion or activity", "what event or activity is it for?"),
    ("used_for_aud", "Who it's for", "who is it for?"),
    ("capable_of", "What it can do", "what is it capable of (specs and limits)?"),
    ("used_to", "The task it finishes", "what task does it help you finish?"),
    ("used_as", "Other ways to use it", "what else can it be used as?"),
    ("is_a", "What kind of product it is", "what product type is it?"),
    ("used_on", "When it's used", "when in the year or day does it fit?"),
    ("used_in_loc", "Where it's used", "where is it used?"),
    ("used_in_body", "Body part", "what part of the body does it involve?"),
    ("used_with", "What it's used with", "what does it pair or work with?"),
    ("used_by", "Who uses it", "who uses it day to day?"),
    ("xIntersted_in", "The buyer's interests", "what is the buyer interested in?"),
    ("xIs_a", "Who the buyer is", "who is the buyer, as a kind of person?"),
    ("xWant", "What the buyer wants to do", "what does the buyer want to achieve?"),
]
ALIASES = {"xInterested_in": "xIntersted_in", "xinterested_in": "xIntersted_in"}
SOURCES = ("review", "qa", "cosmo", "search")
SOURCE_NAMES = {"review": "reviews", "qa": "Q&A", "cosmo": "COSMO gap", "search": "searches"}
HEALTH = [
    ("attributes_filled", "Structured attributes filled"),
    ("fields_within_limits", "Title, bullets, description and backend within their limits"),
    ("variation_consistent", "Variations belong to this product and share its structure"),
    ("title_attributes_agree", "Title, attributes and bullets agree"),
    ("backend_populated", "Backend search terms filled, not blank or short"),
    ("claims_supported", "Every claim that needs proof has its fact on file"),
    ("copy_rules", "Copy follows Amazon's format rules (bullet count, capitals, repeated words)"),
]
GRADED_HEALTH = ("attributes_filled", "variation_consistent", "title_attributes_agree")
# Listing-check rule findings that are Caiman's own house style, not something Amazon disallows: no cap.
# Listing-check rule findings that cost points instead of capping the score (Jonah, Oct 28: a field over its limit
# "isn't catastrophic"): lengths and counts, Caiman's house style, the backend's temporary words ("new" in "new york")
# and a claim that only needs its fact on file. They show in listing health and the fixes. Everything else the check
# calls a rule (guarantee, ratings or reviews, promotional or subjective words, links, ASINs, banned symbols, pesticide
# or medical claims, other brands, wrong facts) caps the score at 49.
NO_CAP = {"over_limit", "too_many", "too_few", "missing", "too_short", "capital", "word_repeats", "banned_words"}


def caps(finding):
    code = str(finding.get("code") or "")
    return not (code in NO_CAP or code.startswith("unsupported_claim:"))
FIELD_NAMES = {"title": "Title", "item_highlights": "Item Highlights", "bullets": "Bullets",
               "description": "Description", "backend": "Backend search terms", "listing": "Listing"}


class Problem(Exception):
    pass


def emit(payload, code=0):
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return code


def read_json(path, what):
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError:
        raise Problem("{} not found: {}".format(what, path))
    except ValueError as exc:
        raise Problem("{} isn't valid JSON ({}): {}".format(what, exc, path))


def find_listing_check(root):
    """The kit's listing_check.py: the business folder's skills first, then a plugin with the skills built in."""
    places = [root, Path(__file__).resolve().parents[3], os.environ.get("CLAUDE_PLUGIN_ROOT")]
    for base in places:
        if not base:
            continue
        for rel in (".claude/skills/listing-autotune/scripts/listing_check.py",
                    "skills/listing-autotune/scripts/listing_check.py"):
            path = Path(base) / rel
            if path.is_file():
                spec = importlib.util.spec_from_file_location("_cdq_listing_check", str(path))
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                return module
    raise Problem("The kit's listing check (.claude/skills/listing-autotune/scripts/listing_check.py) isn't in this "
                  "business folder. Update the kit with kit-sync, then score again.")


def unwrap(data):
    """A saved read wrapped in a record ({"tool": ..., "rows": [answer]}, {"response": answer}, {"listing": answer})."""
    for _ in range(3):
        if isinstance(data, dict) and isinstance(data.get("rows"), list) and len(data["rows"]) == 1 \
                and isinstance(data["rows"][0], dict):
            data = data["rows"][0]
        elif isinstance(data, dict) and isinstance(data.get("response"), dict) and "attributes" not in data:
            data = data["response"]
        elif isinstance(data, dict) and len(data) == 1 and isinstance(data.get("listing"), dict):
            data = data["listing"]
        else:
            break
    return data


def run_check(root, listing_path, check_path):
    if check_path:
        result = read_json(check_path, "The listing check result")
    else:
        module = find_listing_check(root)
        data = unwrap(read_json(listing_path, "The listing file"))
        tmp = None
        try:
            import tempfile
            handle, tmp = tempfile.mkstemp(prefix="cdq-listing-", suffix=".json")
            with os.fdopen(handle, "w", encoding="utf-8") as out:
                json.dump(data, out, ensure_ascii=False)
            result, _spec = module.run(tmp, require_search_data=False)
        except Problem:
            raise
        except Exception as exc:  # the check's own InputError and anything else it can't read
            raise Problem("The listing check couldn't read {}: {}".format(listing_path, exc))
        finally:
            if tmp and os.path.exists(tmp):
                os.remove(tmp)
    listings = result.get("listings") or []
    if len(listings) != 1:
        raise Problem("Score one listing at a time: the listing file holds {}. Put each product's listing (or draft) in "
                      "its own file.".format(len(listings)))
    codes = {(f.get("field"), f.get("code")) for f in listings[0].get("findings") or []}
    if ("title", "missing") in codes and ("bullets", "missing") in codes:
        raise Problem("The listing file has no title or bullets the check can read: {}. Use the saved get_listing read "
                      "itself, or write it as {{\"title\", \"bullets\", \"description\", \"backend\"}}.".format(listing_path))
    return listings[0]


def grade_value(raw, where):
    if isinstance(raw, str) and raw.strip().upper() in ("NA", "N/A"):
        return None
    if isinstance(raw, bool) or raw not in (0, 1, 2):
        raise Problem("{}: grade must be 2, 1, 0 or \"NA\", not {!r}.".format(where, raw))
    return raw


def read_relations(grades):
    given = {}
    for key, value in (grades.get("relations") or {}).items():
        given[ALIASES.get(key, key)] = value
    unknown = sorted(set(given) - {r[0] for r in RELATIONS})
    if unknown:
        raise Problem("Unknown relations in the grades: {}. Use alexa-audit's 15.".format(", ".join(unknown)))
    missing = [r[0] for r in RELATIONS if r[0] not in given]
    if missing:
        raise Problem("Grade all 15 relations (N/A where one doesn't apply). Missing: {}.".format(", ".join(missing)))
    rows = []
    for key, name, question in RELATIONS:
        entry = given[key] if isinstance(given[key], dict) else {"grade": given[key]}
        points = grade_value(entry.get("grade"), key)
        evidence = str(entry.get("evidence") or "").strip()
        if points and not evidence:
            raise Problem("{}: a grade of {} needs its evidence snippet.".format(key, points))
        rows.append({"relation": key, "name": name, "question": question, "points": points,
                     "grade": "NA" if points is None else points, "evidence": evidence,
                     "priority": entry.get("priority")})
    return rows


def read_questions(grades):
    rows = []
    for i, entry in enumerate(grades.get("questions") or []):
        if not isinstance(entry, dict):
            raise Problem("Question {}: write it as {{\"question\", \"source\", \"grade\", \"evidence\"}}.".format(i + 1))
        text = str(entry.get("question") or "").strip()
        if not text:
            continue
        points = grade_value(entry.get("grade"), "question {}".format(i + 1))
        if points is None:
            raise Problem("Question {}: grade it 2 (answered), 1 (partly) or 0 (unanswered).".format(i + 1))
        source = str(entry.get("source") or "").strip().lower()
        source = {"reviews": "review", "q&a": "qa", "question": "qa", "searches": "search", "gap": "cosmo"}.get(
            source, source)
        if source not in SOURCES:
            raise Problem("Question {}: source must be one of {}.".format(i + 1, ", ".join(SOURCES)))
        rows.append({"question": text, "source": source, "points": points,
                     "evidence": str(entry.get("evidence") or "").strip()})
    if not rows:
        raise Problem("No shopper questions graded. List the real ones (reviews, then Q&A, then COSMO gaps, then "
                      "searches) and grade each against the copy.")
    return rows


def check_health(grades, finding_rows, fields):
    given = grades.get("health") or {}
    rows = []
    for key, name in HEALTH:
        if key in ("fields_within_limits", "backend_populated") and key in given and given[key] is None:
            ok, note = None, "not visible for this listing"   # a public listing's backend can't be read
        elif key == "fields_within_limits":
            over = [f for f in finding_rows if f.get("code") == "over_limit"]
            ok = not over
            note = "; ".join(f["message"] for f in over)
        elif key == "claims_supported":
            unproven = [f for f in finding_rows if str(f.get("code") or "").startswith("unsupported_claim:")]
            ok = not unproven
            note = "; ".join(f["message"] for f in unproven)
        elif key == "copy_rules":
            style = [f for f in finding_rows if f.get("severity") == "rule" and f.get("code") in NO_CAP
                     and f.get("code") != "over_limit"]
            ok = not style
            note = "; ".join(f["message"] for f in style)
        elif key == "backend_populated":
            state = (fields.get("backend") or {}).get("state")
            ok = state not in (None, "empty", "under")
            note = "" if ok else "backend search terms {}".format("empty" if state in (None, "empty") else "short")
        else:
            if key not in given:
                raise Problem("Grade the health check {} (true, false, or null when it doesn't apply).".format(key))
            ok = given[key]
            if ok is not None and not isinstance(ok, bool):
                raise Problem("Health check {}: true, false or null.".format(key))
            note = ""
        rows.append({"check": key, "name": name, "ok": ok, "note": note})
    return rows


def rule_breaks(listing, grades):
    found = []
    for f in listing.get("findings") or []:
        if f.get("severity") == "rule" and caps(f):
            found.append({"field": f.get("field"), "code": f.get("code"), "what": f.get("message"),
                          "from": "listing check"})
    for entry in grades.get("breaks") or []:
        what = str((entry or {}).get("what") or "").strip()
        if what:
            found.append({"field": entry.get("field") or "listing", "code": "grader", "what": what, "from": "grader"})
    return found


def half_up(value):
    """Rounds .5 up, as the CDQ page's Math.round does (Python's round() rounds .5 to even)."""
    return int(math.floor(value + 0.5))


def field_fixes(listing):
    """Rule findings that cost points but don't cap: one fix each (a claim's fields together)."""
    fixes, claims = [], {}
    for f in listing.get("findings") or []:
        if f.get("severity") != "rule" or caps(f):
            continue
        code = str(f.get("code") or "")
        if code.startswith("unsupported_claim:"):
            claims.setdefault(code, []).append(f)
            continue
        do = "Cut it to the limit." if code == "over_limit" else "Fix it."
        if code == "over_limit" and f.get("field") == "backend":
            do = "Cut it to the limit: Amazon reads only the first 249 bytes."
        fixes.append({"kind": "field", "title": f["message"].rstrip(". "), "fix": do})
    for code, rows in claims.items():
        where = ", ".join(r["message"].split(":")[0] for r in rows)
        quote = rows[0]["message"]
        quote = quote[quote.find("("):quote.find(")") + 1] if "(" in quote else ""
        fixes.append({"kind": "claim", "title": "Claim with no proof on file {} ({})".format(quote, where).replace("  ", " "),
                      "fix": "Put the fact behind it on file (a test report or certificate), or take the words out."})
    # Most money first: a backend past 249 bytes (Amazon reads none of the rest), then unproven claims, then the rest.
    order = {"backend": 0, "claim": 1, "field": 2}
    fixes.sort(key=lambda f: order["backend"] if f["title"].startswith("Backend search terms:") and "limit" in f["title"]
               else order[f["kind"]])
    return fixes


def percent(points, most):
    return half_up(100.0 * points / most) if most else None


def top_fixes(breaks, relations, questions, quick=()):
    """Rule breaks first, then Missing relations, then Needs work, with the biggest unanswered shopper question
    always given a place among the three when there is one and rule breaks don't fill all three."""
    def rank(row):
        return (0 if row.get("priority") in ("high", True, "P0") else 1)
    def break_fix(b):
        code = str(b.get("code") or "")
        if code == "over_limit":
            do = "Cut it to the limit."
        elif code.startswith("unsupported_claim:"):
            do = "Put the fact behind it on file (a test report or certificate), or take the words out."
        else:
            do = "Take it out."
        return do + " Until then the score can't go above {}.".format(CAP)
    fixes = [{"kind": "rule_break", "title": "Breaks a rule: " + b["what"].replace(" Add the fact or take the words out.", "").rstrip(". "),
              "fix": break_fix(b)}
             for b in breaks]
    missing = sorted([r for r in relations if r["points"] == 0], key=rank)
    vague = sorted([r for r in relations if r["points"] == 1], key=rank)
    relation_fixes = [{"kind": "missing", "title": "Missing: " + r["name"],
                       "fix": "Answer it in the title, first two bullets or a structured attribute: " + r["question"]}
                      for r in missing]
    relation_fixes += [{"kind": "needs_work", "title": "Needs work: " + r["name"],
                        "fix": "Make it specific and move it into the title, first two bullets or a structured "
                               "attribute."} for r in vague]
    unanswered = [q for q in questions if q["points"] == 0] or [q for q in questions if q["points"] == 1]
    unanswered.sort(key=lambda q: (SOURCES.index(q["source"]), q["points"]))
    question_fix = None
    if unanswered:
        q = unanswered[0]
        question_fix = {"kind": "question", "title": "Shopper question not answered: " + q["question"].rstrip(". "),
                        "fix": "Answer it in a bullet with the specific fact (from {}).".format(
                            SOURCE_NAMES[q["source"]])}
    ordered = fixes[:3]
    rest = list(quick[:1]) + relation_fixes   # the first field or claim fix, then the relations
    if question_fix and len(ordered) < 3:
        room = 3 - len(ordered)
        ordered += rest[:room - 1] + [question_fix]
    else:
        ordered += rest
    return ordered[:3]


def in_root(root, path):
    """A relative path is the business folder's, wherever the shell is."""
    if not path:
        return path
    p = Path(path).expanduser()
    return str(p if p.is_absolute() else root / p)


def score(args):
    root = Path(args.project_root).expanduser()
    if not root.is_dir():
        raise Problem("Business folder not found: {}".format(root))
    args.grades, args.listing, args.check, args.out = (in_root(root, x) for x in
                                                       (args.grades, args.listing, args.check, args.out))
    grades = read_json(args.grades, "The grades file")
    if args.label not in ("current", "proposed"):
        raise Problem("--label is current or proposed.")
    relations = read_relations(grades)
    questions = read_questions(grades)
    listing = run_check(root, args.listing, args.check)
    graded, read = str(grades.get("asin") or "").strip().upper(), str(listing.get("asin") or "").strip().upper()
    if graded and read and graded != read:
        raise Problem("The grades are for {} but the listing is {}: score each product with its own listing.".format(
            graded, read))
    findings = listing.get("findings") or []
    health = check_health(grades, findings, listing.get("fields") or {})
    breaks = rule_breaks(listing, grades)

    applicable = [r for r in relations if r["points"] is not None]
    cosmo = percent(sum(r["points"] for r in applicable), 2 * len(applicable))
    asked = percent(sum(q["points"] for q in questions), 2 * len(questions))
    checked = [h for h in health if h["ok"] is not None]
    health_pct = percent(sum(1 for h in checked if h["ok"]), len(checked))
    if cosmo is None:
        raise Problem("Every relation is N/A; at least one has to apply.")
    parts = {"cosmo": cosmo, "questions": asked, "health": health_pct if health_pct is not None else 0}
    raw = half_up(sum(WEIGHTS[k] * parts[k] for k in WEIGHTS))
    cdq = min(raw, CAP) if breaks else raw
    band = "Strong" if cdq >= 80 else "Adequate" if cdq >= 50 else "Needs Work"
    result = {
        "schema": "caiman.cdq-score.v1", "label": args.label, "scored_at": dt.datetime.now(dt.timezone.utc)
        .replace(microsecond=0).isoformat(), "asin": str(grades.get("asin") or ""), "sku": str(grades.get("sku") or ""),
        "product": str(grades.get("product") or ""), "cdq": cdq, "raw": raw, "capped": bool(breaks) and raw > CAP,
        "band": band, "cosmo": cosmo, "questions": asked, "health": parts["health"],
        "applicable_relations": len(applicable), "rule_breaks": breaks, "relations": relations,
        "shopper_questions": questions, "health_checks": health,
        "top_fixes": top_fixes(breaks, relations, questions, field_fixes(listing)), "field_fixes": field_fixes(listing),
        "line": LINE,
        "formula": "CDQ = 50% COSMO + 30% shopper questions + 20% listing health; a break of Amazon's copy rules caps it "
                   "at 49 (lengths, format and claims that need proof cost points instead).",
    }
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    summary = {"ok": True, "label": args.label, "asin": result["asin"], "cdq": cdq, "band": band, "raw": raw,
               "capped": result["capped"], "cosmo": cosmo, "questions": asked, "health": parts["health"],
               "rule_breaks": [b["what"] for b in breaks], "top_fixes": [f["title"] for f in result["top_fixes"]],
               "saved": args.out or None, "line": LINE}
    return emit(summary)


# ------------------------------------------------------------------------------------------------ report

CSS = """
:root{--navy:#0A2333;--off:#F3F3F1;--green:#13835B;--orange:#EA6C34;--line:#dfe3e1;--muted:#5b6b73;--red:#B42318}
*{box-sizing:border-box}body{margin:0;background:var(--off);color:var(--navy);
font:15px/1.55 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
.wrap{max-width:900px;margin:0 auto;padding:24px 16px}
header{background:var(--navy);color:#fff;padding:22px 16px}header .wrap{padding:0 16px}
h1{font-size:26px;margin:0 0 4px}h2{font-size:20px;margin:0 0 10px}h3{font-size:16px;margin:18px 0 8px}
.sub{color:rgba(255,255,255,.75);font-size:13px}
.card{background:#fff;border:1px solid var(--line);border-radius:12px;padding:20px;margin:16px 0}
.score{font-size:52px;font-weight:800;font-variant-numeric:tabular-nums;line-height:1}
.band{display:inline-block;margin-left:10px;padding:3px 10px;border-radius:20px;font-size:14px;font-weight:700;
vertical-align:middle;color:#fff;background:var(--green)}.band.Adequate{background:var(--orange)}
.band.Needs{background:var(--red)}.arrow{font-size:28px;color:var(--muted);margin:0 10px}
.parts{color:var(--muted);font-variant-numeric:tabular-nums;margin-top:8px}
.cap{background:#FEF3F2;border:1px solid #FDA29B;border-radius:8px;padding:10px 12px;margin-top:12px}
table{width:100%;border-collapse:collapse;font-size:14px}th,td{text-align:left;vertical-align:top;
padding:7px 6px;border-bottom:1px solid var(--line)}th{color:var(--muted);font-weight:600}
.foot{color:var(--muted);font-size:13px}
@media (prefers-color-scheme:dark){:root{--off:#0f1a20;--navy:#e9eef0;--line:#2a3a42;--muted:#9fb0b8}
.card{background:#152229}header{background:#0A2333;color:#fff}.cap{background:#3a1d1a;border-color:#7a2e26}}
"""


def esc(value):
    return html.escape("" if value is None else str(value), quote=True)


def band_class(band):
    return band.split()[0]


def relation_grade(row):
    return {None: "N/A", 2: "2 Specific", 1: "1 Needs work", 0: "0 Missing"}[row["points"]]


def render(scores):
    by_asin = {}
    for s in scores:
        key = s.get("asin") or s.get("sku") or s.get("product")
        by_asin.setdefault(key, {})[s.get("label", "current")] = s
    cards = []
    for key, pair in by_asin.items():
        now, after = pair.get("current"), pair.get("proposed")
        lead = now or after
        head = "<h2>{}</h2><div class=\"foot\">{}</div>".format(esc(lead.get("product") or key), esc(key))
        if now and after:
            big = ("<div><span class=\"score\">{}</span><span class=\"band {}\">{}</span><span class=\"arrow\">"
                   "&rarr;</span><span class=\"score\">{}</span><span class=\"band {}\">{}</span></div>"
                   "<div class=\"parts\">Now: the live listing. After: the proposed copy, once it's live. The details "
                   "below are the live listing's.</div>").format(
                esc(now["cdq"]), esc(band_class(now["band"])), esc(now["band"]), esc(after["cdq"]),
                esc(band_class(after["band"])), esc(after["band"]))
        else:
            big = "<div><span class=\"score\">{}</span><span class=\"band {}\">{}</span></div>".format(
                esc(lead["cdq"]), esc(band_class(lead["band"])), esc(lead["band"]))
        main = now or after

        def parts_of(side, label):
            return ("<div class=\"parts\">{}COSMO {} &middot; Shopper questions {} &middot; Listing health {}{}</div>"
                    ).format(esc(label), esc(side["cosmo"]), esc(side["questions"]), esc(side["health"]),
                             " &middot; Before the cap {}".format(esc(side["raw"])) if side["capped"] else "")

        def cap_of(side, label):
            if not side["rule_breaks"]:
                return ""
            n = len(side["rule_breaks"])
            items = "".join("<li>{}</li>".format(esc(b["what"])) for b in side["rule_breaks"])
            return ("<div class=\"cap\"><b>{}{} {} Amazon's listing rules.</b> A break like this caps the score "
                    "at {}, however well the rest scores.<ul>{}</ul></div>").format(
                esc(label), "1 thing that breaks" if n == 1 else "{} things that break".format(n), "", CAP, items) \
                .replace("  Amazon", " Amazon")

        if now and after:
            parts = parts_of(now, "Now: ") + parts_of(after, "After: ")
            cap = cap_of(now, "Now: ") + cap_of(after, "After: ")
        else:
            parts, cap = parts_of(main, ""), cap_of(main, "")
        fixes = "".join("<li><b>{}</b>. {}</li>".format(esc(f["title"]), esc(f["fix"])) for f in main["top_fixes"])
        fixes = "<h3>Top 3 fixes</h3><ol>{}</ol>".format(fixes or "<li>Nothing urgent: keep it as it is.</li>")
        extra = [f for f in main.get("field_fixes") or [] if f["title"] not in {t["title"] for t in main["top_fixes"]}]
        if extra:
            fixes += "<h3>Also fix</h3><ul>{}</ul>".format("".join(
                "<li><b>{}</b>. {}</li>".format(esc(f["title"]), esc(f["fix"])) for f in extra))
        rel = "".join("<tr><td>{}</td><td>{}</td><td>{}</td></tr>".format(
            esc(r["name"]), esc(relation_grade(r)), esc(r["evidence"] or "")) for r in main["relations"])
        rel = ("<h3>The 15 shopping-intent relations</h3><table><tr><th>Relation</th><th>Grade</th><th>Evidence</th>"
               "</tr>{}</table>").format(rel)
        qs = "".join("<tr><td>{}</td><td>{}</td><td>{}</td></tr>".format(
            esc(q["question"]), esc({2: "Answered", 1: "Partly", 0: "Unanswered"}[q["points"]]),
            esc(SOURCE_NAMES[q["source"]])) for q in main["shopper_questions"])
        qs = "<h3>Shopper questions</h3><table><tr><th>Question</th><th>In the copy</th><th>From</th></tr>{}</table>" \
            .format(qs)
        hl = "".join("<tr><td>{}</td><td>{}</td></tr>".format(
            esc(h["name"]), esc("Doesn't apply" if h["ok"] is None else "Pass" if h["ok"] else "Fail" +
                                (": " + h["note"] if h["note"] else ""))) for h in main["health_checks"])
        hl = "<h3>Listing health</h3><table>{}</table>".format(hl)
        cards.append("<section class=\"card\">{}{}{}{}{}{}{}{}</section>".format(head, big, parts, cap, fixes, rel,
                                                                              qs, hl))
    today = dt.date.today().isoformat()
    return ("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" "
            "content=\"width=device-width,initial-scale=1\"><title>CDQ Score</title><style>{}</style></head><body>"
            "<header><div class=\"wrap\"><h1>Your CDQ Score</h1><div class=\"sub\">Caiman &middot; {}</div></div>"
            "</header><main class=\"wrap\">{}<p class=\"foot\">CDQ = 50% COSMO (Amazon's 15 shopping-intent "
            "relations, graded by meaning, specificity and placement; N/A left out) + 30% shopper questions "
            "answered + 20% listing health. Bands: Strong 80+, Adequate 50 to 79, Needs Work under 50. Any rule "
            "break caps it at 49. {}</p></main></body></html>\n").format(CSS, esc(today), "".join(cards), esc(LINE))


def report(args):
    scores = []
    root = Path(args.project_root).expanduser()
    for path in args.scores:
        path = in_root(root, path)
        data = read_json(path, "The CDQ score")
        if data.get("schema") != "caiman.cdq-score.v1":
            raise Problem("{} isn't a CDQ score from cdq_score.py score.".format(path))
        scores.append(data)
    root = Path(args.project_root).expanduser()
    out = Path(args.out) if args.out else Path("Reviews") / "cdq-score-{}.html".format(dt.date.today().isoformat())
    if not out.is_absolute():
        out = root / out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(scores), encoding="utf-8")
    return emit({"ok": True, "saved": str(out), "listings": len({s.get("asin") or s.get("sku") for s in scores})})


def main(argv=None):
    parser = argparse.ArgumentParser(description="Caiman's CDQ score (free trial week).")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("score")
    p.add_argument("--project-root", required=True)
    p.add_argument("--grades", required=True)
    p.add_argument("--listing", required=True)
    p.add_argument("--check")
    p.add_argument("--label", default="current")
    p.add_argument("--out")
    r = sub.add_parser("report")
    r.add_argument("--project-root", required=True)
    r.add_argument("--scores", nargs="+", required=True)
    r.add_argument("--out")
    args = parser.parse_args(argv)
    try:
        return score(args) if args.command == "score" else report(args)
    except Problem as exc:
        return emit({"ok": False, "problem": str(exc)}, 1)


if __name__ == "__main__":
    sys.exit(main())
