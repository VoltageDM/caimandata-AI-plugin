# Free trial week

A new member's first seven days, when the Caiman server shows them on Caiman's free trial. It is the normal first run ([operator playbook](operator-playbook.md)) at full speed, plus four things: no waiting between steps, the CDQ score for their top products (section 8), short progress reports that Caiman's trial emails follow, and a recap before the first charge. Nothing here applies to any other member or folder, or to scheduled and routine runs: it's for sessions with the member.

## 1. Every session: is there a trial week here?

The setup check saves `list_brands`' whole answer to a file, exactly as it came back or as its download holds it (with the kit's `SAVE_CONNECTOR_ANSWERS.py` when the folder's kit is 0.3.34 or later; [setup check](setup-check.md), "Every session"). This check reads the same file: the `membership` parts of the answer are what it goes on. Right after the setup check, before `CLIENT_START.py` or any other work, run it in the business folder:

```bash
python3 "<this skill's folder>/scripts/trial_week.py" check --project-root "<business folder>" --connector-brands-json @<list_brands answer file>
```

Add `--brand-slug <slug>` only when you know which listed brand this folder is for. In a workspace (several brands' folders), run it in each brand's own folder; a trial week belongs to one brand.

What `trial_week` says:

- **`none`**: there's no trial week here. Carry on exactly as the rest of this skill says, and don't mention a trial week. This covers members who aren't on the free trial or already have another Caiman membership, staff and agency logins, folders where Deep Seed or other Caiman work had already started, a trial week that ended or was stopped, and accounts the server gives no trial status for. It also covers a check that couldn't finish (`check_failed`): that isn't a problem to report. One reason needs a step: `whole_answer_needed` means the file held only a list of brands, so save `list_brands`' whole answer and run the check again.
- **`start`**: start it now, before anything else but a kit update the setup check says is due, with the same command and `start` in place of `check`. When `start` answers `announce: true`, add the opening message (section 2) to your first reply, after the setup check's line. With `announce: false` (the login shows several brands), the opening message waits until the brand is tied (below).
- **`active`**: follow this guide on top of everything else. `next` says what comes next; when `recap_due` is true, the recap comes before anything else (section 5). While `announced` is false, the opening message hasn't gone out yet: don't mention the trial week until `bind` says to announce.

**Tying it to the brand.** When `needs_brand` is true, the trial week isn't tied to a brand yet: Amazon wasn't connected when it started, or the login shows several brands. `brand_candidate`, when there is one, is the brand the server shows on the free trial. Once the member has confirmed which brand this folder is for (operator playbook, step 3), run:

```bash
python3 "<this skill's folder>/scripts/trial_week.py" bind --project-root "<business folder>" --connector-brands-json @<list_brands answer file> --brand-slug <slug>
```

- **`ok` with `announce: true`:** the trial week is tied to the brand and hasn't been announced yet. Add the opening message (section 2) to this reply.
- **`brand_not_on_trial`:** the folder is for a brand that isn't on the free trial. The trial week stops here; carry on as usual without mentioning it.
- **Refused:** nothing changed, and the message says why.
  - Another listed brand is the one on the free trial, or this brand has no membership of its own: check with the member which brand this folder is for. If it's the trial brand, bind that one. If it really is this brand, run `bind` again with `--not-on-trial`; the trial week then stops here.
  - `list_brands` doesn't show which brand is on the trial: carry on, and try `bind` again next session. Milestones wait until the trial week is tied to a brand.
  - Otherwise, fix what the message names (use a slug `list_brands` shows, or pass its whole answer) and run `bind` again.

Never start a trial week any other way, never start one again in a folder that had one, and never edit `.caiman/trial-week.json` by hand.

## 2. The opening message

Two or three sentences, in your own words, with the dates from the check:

- what the week gets them. Before Amazon has connected, for example: "Once Amazon finishes connecting (usually overnight), I'll pull your sales, ads and stock, show you your business view and your plan, and have your first changes ready for your go. You'll also get your CDQ score for your top products, with what to change to raise it. Then new listing copy and images for your top product family, scored again so you see the change, your stock and profit plan, and a recap before your free week ends on {date}."
- the progress line, always: "While the free week runs, I let Caiman know when you reach each step, with a few headline numbers such as ad spend on searches with no orders, so your emails match where you are. Never product IDs or account numbers. Say 'don't send my progress' any time to turn that off."

## 3. The pace

The trial week is the operator playbook's first run without gaps. Never hold work for a day: when a step finishes, hand it over with its Next in the same reply ("Say next to start it"; the caiman skill, "Close").

1. **Before Amazon is live** (usually the signup day): setup check, kit install and the Deep Seed interview (playbook steps 1-4). Ask for the product-cost sheet in the interview: without landed costs, profit stays unknown all week. Remind them to book the onboarding call from their welcome email. If Amazon is still authorizing, say it usually finishes overnight, that you'll start pulling as soon as it's live, and work from any files they have.
2. **As soon as Amazon is live:** confirm the account and `bind` the brand if the check said `needs_brand`. Then run Deep Seed straight through (playbook steps 5-8). Request the reports first, build the first business view without waiting for the full history, then run `NEXT_STEP.py`. On VIP, Deep Seed sets the VIP Machine up from what it saved (step 6; it takes minutes, and nothing is asked again). Deep Seed's closing summary includes the CDQ score for the plan's first product family (section 8). Then offer the plan's first workflow in the same session, and on a yes, run it to the changes it proposes. Approved changes are applied exactly and read back, as always. The first time an approved change goes live, in this step or a later one, record `first_fix_approved` (section 4).
3. **Next: the Listing & Creative Pack** for the plan's first product family, or the one the member picks. It scores its proposed copy with the CDQ score and shows each product's score now and after (section 8). If the Caiman connector lists its image tools and `get_image_credits` shows credits, the pack can make the images. Otherwise deliver the image briefs and say that making the images needs image credits.
4. **Then the plan's next steps**, one at a time (`NEXT_STEP.py`), each offered as soon as the last one is done.
5. **Each new day:** at the first session of the day, offer the Advertising Daily Check. Only a due recap comes before it.
6. **VIP:** Deep Seed sets up the VIP Machine from what it saved and finishes its first sources (playbook step 6). When `complete-bootstrap` succeeds, offer the routines; they stay off until the member approves them.
7. **History** keeps filling in the background. Never make the member wait for it.

## 4. Milestones

Record each one when it happens, once the trial week is tied to a brand:

| Milestone | When | Details |
|---|---|---|
| `first_view_ready` | Deep Seed's first business view and `CAIMAN PLAN.md` are saved | `first_workflow`: the plan's first workflow, as `NEXT_STEP.py` names it (`weekly-growth-review`, `listing-creative-pack`, `stock-profit-plan`, `advertising-weekly-review`, `advertising-daily-check`, `advertising-structure-review`, `advertising` or `deep-seed`) |
| `action_list_ready` | the first workflow's changes are ready for the member's go | `open_fix_count` (always; 0 when the review found nothing to change), plus the optional fields below |
| `first_fix_approved` | a change the member gave their go to is live for the first time: applied and read back, or, for a change the member makes themselves (Seller Central on GLS+), once they say it's done | none |
| `creative_pack_ready` | the first Listing & Creative Pack is ready for the member's go | none |
| `vip_machine_ready` | VIP only: `complete-bootstrap` succeeded | none |
| `week_one_complete` | the recap is saved and recorded (section 5) | none |

Optional `action_list_ready` details:

- **`wasted_spend_30d` and `harvest_count`:** from the kit's kw-harvester-negator summary on the last 30 days of complete search-term data. `wasted_spend_30d` is its `total_wasted_spend`; `harvest_count` is `harvest_keywords` plus `harvest_asins`. Send them with `currency` and with `period_start` and `period_end` (YYYY-MM-DD). `currency` is the three-letter code from the Ads profile (`currency_code`), not the summary's symbol. Leave them out when that summary wasn't made.
- **`listing_findings_count`:** how many products or product families the first workflow says need a listing change (title, Item Highlights, bullets, description, backend search terms, attributes, images or A+), each counted once. Send 0 when it checked the listings and found nothing to change; leave it out when it didn't look at the listings (an Advertising review, for example).
- **`top_nonads_finding`:** the top non-Ads priority's title, in plain words, at most 120 characters. Name a product family in words: no ASINs, SKUs, product codes, account numbers or links. The script refuses text that looks like one.
- **`money_finder_estimate`:** only a projected monthly figure from the review, as `{"monthly_amount": …, "period_start": …, "period_end": …, "method": "<how it was worked out, in words>", "label": "estimate"}`. Leave it out otherwise.

To send a milestone:

1. Run `trial_week.py milestone --project-root "<business folder>" --name <milestone> --details-json '<details>'`. If the quotes are awkward, use `@<file>`. It checks the details against its allowlist and refuses anything else.
2. If its answer has `"send": true`, and the Caiman connector lists `record_trial_milestone`, call that tool with exactly the `call.arguments` it printed. Then run the same command with `--sent`.
3. If the tool isn't listed, or the call fails, run the command with `--not-sent "<why>"`. Never retry it, never send the details any other way, and don't bring it up with the member unless they ask.

With `"send": false` (already recorded, or the member turned reports off) there's nothing to call. If a check lists a milestone under `unconfirmed`, its call was prepared but never confirmed: run `--sent` if you made the call, otherwise `--not-sent`.

## 5. The recap

When `recap_due` is true (the free week has 48 hours or less left and the first business view exists), the recap comes first in that session. Save one page in the business folder as `Reviews/free-week-recap-<YYYY-MM-DD>.md`, and show it to the member:

- **What's live:** each change applied and read back, from the VIP Machine's records, `MEMBER_DIRECTED_LOG.py` and the plan.
- **What's waiting** for the member's go.
- **When results are due** for each change, from the VIP Machine and the plan. An ad change is measured about four weeks after it's made, and a listing change on four weeks of sales. Claim no results.
- **The business** in three to five numbers from the business view, with their dates.
- **The CDQ score:** each product scored, now and after the proposed copy (section 8), and which of its fixes are live.
- **Next week's plan**, from `NEXT_STEP.py`.
- **What's still missing,** and who can supply it.
- **The dates:** when the free week ends, and the billing date from the check, after which the membership carries on. Say they can manage their membership in their Caiman account.

Then run `trial_week.py recap --project-root "<business folder>" --saved "Reviews/free-week-recap-<YYYY-MM-DD>.md"`, and record `week_one_complete`.

## 6. Turning it off

- **"Don't send my progress":** run `trial_week.py reporting --project-root "<business folder>" --off` and confirm it's off. `--on` turns it back on.
- **"Stop the free-week extras":** run `trial_week.py stop --project-root "<business folder>"`. From then on, Caiman runs here as usual.

## 7. What stays the same

- **Account changes:** every one still needs a preview, the member's go for that exact change, the change applied exactly as approved, and a read-back (the caiman skill, section 5).
- **Dollar figures:** a projected figure is an estimate with its period and method, never "savings". Measured numbers are worded as what happened ("spent with no orders").
- **No results inside the trial week.** Nothing is measured before its window ends.
- **Missing stays missing.**
- **Milestone details never carry** product IDs, SKUs, account numbers, emails or links.
- **Deep Seed is never run again** for a member who has done it, work is never held for a day label, and the trial week is never mentioned where the check says `none`.
- **GLS+:** Seller Central data comes from the member's downloads (ask for the two the first view needs in one message), there's no VIP Machine (so none of its routines), and `vip_machine_ready` is never sent.

## 8. The CDQ score

The free week's listing score: one number from 0 to 100 per product, with what to change to raise it. It is Caiman's score, not Amazon's. Wherever you show it, in chat or a file, say it in these words: "Caiman's listing score, built on Amazon's published shopping-intent research. Not an Amazon metric." Never call it Amazon's score or a ranking, and never say a higher score raises rank or sales.

CDQ = 50% COSMO (the 15 shopping-intent relations from the COSMO paper's Table 2, the same rubric as the kit's `alexa-audit`) + 30% shopper questions answered + 20% listing health. A break of Amazon's copy rules (guarantee or refund wording, ratings or reviews in the copy, promotional or subjective words, links, banned symbols, pesticide or medical claims, other brands' names) caps it at 49. A field over its limit, the format rules and a claim that only needs its fact on file cost listing-health points instead, and show in the fixes. Bands: Strong 80+, Adequate 50 to 79, Needs Work under 50. `scripts/cdq_score.py` does the arithmetic, runs the kit's listing check for the rule breaks, orders the top 3 fixes and builds the report; you do the grading.

**When:**

- **Deep Seed's close** (section 3, step 2): score the plan's first product family: its best seller, plus up to two more of its best sellers by the business view's last four weeks (one per variation family). Each product's score, band and top 3 fixes go in Deep Seed's closing summary, with the report.
- **The Listing & Creative Pack** (section 3, step 3): grade the pack's proposed copy the same way (`--label proposed`, with each product's draft in its own file as the listing, its facts copied in) and show each product's score now and after. "After" is what the proposed copy scores, not a result: nothing is measured inside the week.
- **Again** when the member asks, or once approved copy is live and read back (score the read).

**How, for each product:**

1. **The listing.** VIP: the saved `get_listing` read (when Deep Seed didn't save one, read it with `download_link: true` and save it with the kit's `SAVE_CONNECTOR_ANSWERS.py save --tool get_listing --brand <slug> --arg sku=<SKU> --out <file>`; `search_listings` by ASIN finds the SKU). GLS+: the product's row in the member's Category Listings Report (ask for it in the same message as Deep Seed's two downloads), written as `{"asin", "title", "bullets", "description", "backend"}`. Add the product's confirmed facts from the business folder (`CLIENT_RULES.md` and its listing facts) as `"facts": [...]` in a copy of the read, so a claim backed by a fact on file isn't a break. Never make a fact up.
2. **The 15 relations.** Grade each 2, 1, 0 or `"NA"` by alexa-audit's rubric (`.claude/skills/alexa-audit/references/cosmo-paper-dimensions.md`), with an evidence snippet from the copy for every 2 or 1. Grade by meaning, specificity and placement, never by matching words: 2 is a specific statement in the title or the first two bullets, or a populated structured attribute; 1 is vague, lower down, or only in the backend search terms; 0 is missing. Word lists, keyword stuffing and one-word fragments answer nothing and score 0. N/A only where the relation can't apply to the product. Add `"priority": "high"` to the relations the product's review topics weigh most.
3. **Shopper questions.** 8 to 12 real questions for this product, sourced in this order: its review topics (`get_review_topics` for the ASIN, then its browse node from `get_item_browse_node`; GLS+: the reviews on the member's own product page when they want them), then the questions on its product page (when a browser tool can read them; otherwise skip this source), then alexa-audit's question stubs (`references/question-stubs.md`) for relations under 2, then buying questions from the searches that convert (the saved Search Query Performance and search terms). Grade each 2 (the copy answers it with a specific fact), 1 (partly) or 0 (not), with the source `review`, `qa`, `cosmo` or `search`. There's no fixed question bank. Never ask a question whose answer would be a rating, a review, a warranty or a price claim: those don't belong in listing copy.
4. **Health.** `attributes_filled`: the structured attributes that map to the 15 relations are populated (compare the read with `get_category_attributes` for its product type). `variation_consistent`: its variations belong to it and share its structure (`null` when it has none). `title_attributes_agree`: the title, attributes and bullets don't contradict each other. The script checks the field limits and the backend fill itself.
5. **Breaks.** The listing check finds the rule breaks and the field fixes itself. Add a break under `"breaks"` only when the copy makes a disallowed claim in words the check doesn't catch; otherwise leave it `[]`.
6. **Score and report.** Save the grades as `outputs/cdq/<YYYY-MM-DD>/<ASIN>-<label>-grades.json`, then run:

```bash
python3 "<this skill's folder>/scripts/cdq_score.py" score --project-root "<business folder>" --grades <grades file> --listing <listing file> --label current --out "outputs/cdq/<YYYY-MM-DD>/<ASIN>-current.json"
python3 "<this skill's folder>/scripts/cdq_score.py" report --project-root "<business folder>" --scores <each score file>
```

The report is `Reviews/cdq-score-<YYYY-MM-DD>.html`, one card per product, now and after side by side once the pack's copy is scored. If `score` answers `ok: false`, fix what its `problem` names and run it again.

**Grade the proposed copy the way you graded the live listing.** Same rubric, same strictness, the same questions. The point is an honest before and after, never a bigger number.

**In chat,** one line per product, for example: "Your CDQ score: 56, Adequate (COSMO 61, shopper questions 45, listing health 60). Top fixes: ...". Rule breaks come first, in plain words ("2 things that break Amazon's listing rules"). Then the line above, word for word. The fixes' exact copy comes with the Listing & Creative Pack, for the member's go like any listing change.

CDQ details never go in a milestone: the milestone details stay as section 4 lists them.
