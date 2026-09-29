---
name: caiman
description: Runs a member's Amazon seller business from their Caiman business folder. Covers Deep Seed setup, Weekly Growth Review, Listing & Creative Pack, Stock & Profit Plan, Advertising (Weekly Review and Daily Check) and Advertising Structure Review. Use for Amazon seller work in a Caiman workspace (ads, listings, images, stock, profit, reports or dashboards), and when a member wants to set up or resume their Caiman business folder.
---

# Caiman

Caiman helps an Amazon seller run their business from one folder, their business folder. The member has **Caiman VIP** or **Caiman GLS+**. Their kit says which (`plan_tier` in the business folder's `ENTITLEMENTS.json`), and it carries that membership's skills.

Before using tools, tell the member in a sentence what you're about to do. Do the local steps yourself, and ask only for facts or decisions you actually need.

## 1. Deep Seed comes first

A new business starts with **Deep Seed**. After that, the member can ask for any of the other workflows, in any order. The six workflows:

1. **Deep Seed**: first setup. A short interview about the brand, gathering the sales, ads and stock history that's available, and a first view of the business with its real gaps and a next step.
2. **Weekly Growth Review**: the broad weekly look at sales, traffic, conversion, ads, stock and profit, ending in a short action list.
3. **Listing & Creative Pack**: listing copy and image or video proposals for the products the member picks.
4. **Stock & Profit Plan**: stock cover, reorder timing and profit by product.
5. **Advertising**, in two cadences: the **Weekly Review** prepares one coherent set of ad changes for the member to approve, and the **Daily Check** follows that plan for exceptions and measurements that are due. "Run Advertising" on its own means the Weekly Review.
6. **Advertising Structure Review**: maps the campaign structure to what shoppers search for. It needs usable Search Query Performance (SQP) data for the account, products and period. Search-term reports can't stand in for SQP. Without SQP, say what's missing and how to get it.

The kit's `OUTCOME WORKFLOWS.md` and `PROMPT LIBRARY.md` describe each workflow in detail. When a member comes back and asks "what next?", continue their saved work instead of starting over.

## 2. Find or create the business folder

- Keep one business per folder. Use the folder the member names or has attached. If it's unclear which folder is theirs, ask. Don't search the home folder or guess.
- The folder may be on the member's computer, reached through the device bridge (the host's tools for running commands and reading files on that computer). Then run the kit's scripts on that computer and keep the business files there. A copy in this session's own workspace is not the business folder.
- For a new business, create a folder named for it, after the member agrees to the name and place.

## 3. Install or update the kit when needed

The kit is the set of guides, scripts and templates the workflows use, plus the membership's skills. It lives in the business folder, and its skills go in the folder's `.claude/skills/`. Run the kit-sync status check, or compare `core_version` in the folder's `RELEASE_MANIFEST.json` with this plugin's `version` in `.claude-plugin/plugin.json` (two levels above this skill's folder). Use the **kit-sync** skill when:

- the folder has no kit (Deep Seed installs it),
- the kit is older than this plugin (kits from before 0.3.1 have no `core_version`), including a kit an older installer put in `.caiman/kit-versions/`,
- the status says skills are missing or the VIP Machine is older than the kit,
- the member asks to update or repair their kit, or
- the server offers the other tier's kit because the membership changed (switch only after the member agrees).

kit-sync fetches the kit through the Caiman connector and installs it; tell the member in one sentence first. It keeps everything the member made. Kit files it replaces go to `_previous-kit/`. Pass on its summary in plain words, in particular:

- **Files the member had changed.** It names each one ("You had changed X; your version is saved at ...").
- **Skill copies with the member's changes.** Before installing the kit's skills in `.claude/skills/`, kit-sync saves any older copy there in `_previous-kit/`. When a copy had the member's changes, the summary names it: offer to bring those changes into the kit's version, or into CLIENT_RULES.md if they should last through future updates (updates never touch it). A renamed copy, or a copy in `.agents/skills`, that the member changed stays where it is; tell the member Claude may use it instead of Caiman's skill, and offer to move it aside. Only with their OK, run kit-sync's `move-aside` for that path.
- **The VIP Machine (VIP).** kit-sync also updates the VIP Machine, backing up every file it replaces, and switches off any routine that is on without a schedule the member approved. Tell the member which routines were switched off and that nothing was deleted.

If kit-sync, `GUIDED_SETUP.py status` or `CLIENT_START.py` says the VIP Machine still needs updating (next step `UPDATE_VIP_MACHINE`), run `python3 "<business folder>/RUNTIME_UPDATE.py" update --project-root "<business folder>"` before any other VIP Machine work, and tell the member what it reports. The kit's `RUNTIME UPDATE.md` explains it, including how to undo it.

## 4. Route the request with CLIENT_START.py

First read `CAIMAN_CURRENT.md` in the business folder. It names the guide folder: the folder whose `AGENT_START.md`, `CLIENT_START.py` and other kit scripts belong to the current kit. After a kit-sync install, the guide folder is the business folder itself. A folder set up by an older installer (a companion install) can name another folder, such as `.caiman/kit-versions/<name>`. There, a `CLIENT_START.py` at the top of the business folder may be an older kit, so don't run that copy. Such a folder has a kit from before 0.3.0, so update it with kit-sync first (section 3); until then, use the scripts in the named guide folder. If there is no `CAIMAN_CURRENT.md`, the guide folder is the business folder.

Run the guide folder's `CLIENT_START.py` with the business folder and the member's request in their own words. For example:

```
python3 "<guide folder>/CLIENT_START.py" --project-root "<business folder>" --goal "<the member's request>"
```

Any correct way of running it is fine. It creates missing starter files (CLIENT_RULES.md, MEMORY.md, knowledge/index.md), saves the request, and returns the workflow, the skills to use and the next step. Use the same guide folder for the other kit scripts it names. Run it again when the request changes. Read CLIENT_RULES.md and MEMORY.md before doing the work. If it reports a problem, explain it plainly and fix what you can.

## 5. The member approves every account change

For any change to the Amazon account, such as bids, budgets, campaigns, keywords, negatives, listings, prices or inventory:

1. Show the exact object, its current value, the proposed value, and the evidence.
2. Wait for the member's go.
3. Apply the change, then read the object back and report what actually changed.

On GLS+, Seller Central changes are made by the member in Seller Central; Caiman prepares them. Scheduled or routine runs never change an account. A saved document, or an earlier go for a different change, is not approval.

## Tiers

The Caiman server decides which connector tools each tier can use. The kit sends each tier to the data it has.

- **Caiman GLS+**: live Amazon Ads through the Caiman connector. Seller Central data comes from the member's own exports: the Business Report, FBA inventory, the SQP export, and the Category Listings Report for listings. GLS+ never uses Seller Central API tools, even if they appear in the tool list. Ask for the export instead; the kit's `MANUAL DATA GUIDE.md` says where each one is.
- **Caiman VIP**: Amazon Ads and Seller Central are both connected, and the verified-dollar ledger tracks results. Optional routines (scheduled runs) stay off until the member approves turning them on, and they never change the account. Save an approved plan as `SCHEDULE_PLAN.json` (see the kit's `SCHEDULED OPERATIONS.md`); kit updates keep a routine on only when that plan shows it.
- **VIP currency:** the VIP Machine (the verified-dollar ledger, the weekly scorecard and the routines) currently works in US dollars only. For a business in another marketplace or currency, say so plainly before setting up the VIP Machine, and use the dashboard and file workflows, which follow the member's marketplace and currency settings.

More detail: [tier routing](references/tier-routing.md). For a new product launch, see [product launch](references/launch-cockpit.md).

## How to work

- **Skills come with the kit.** kit-sync installs them in the business folder's `.claude/skills/`. When CLIENT_START.py, a kit guide or this skill names a skill, use it by name. If it isn't in your list of skills (not every app loads a folder's skills), read `.claude/skills/<name>/SKILL.md` in the business folder and follow it. If the folder has no kit yet, install it first (section 3).
- **Members can ask for any chart, page or report.** Build what they ask for from their data. The kit's dashboards are a good default, not a limit.
- **Files work too.** If Amazon isn't connected yet, or the member prefers exports, start from the files they give you; the kit's `LOCAL FILE WORKFLOW.md` explains how. Keep the member's original files in the business folder.
- **Missing stays missing.** Missing data is never zero. Proposals with labeled estimates or known gaps are fine; say what's missing and how to get it. Only applying a change needs complete facts and the member's go.
- **Use the member's settings.** Marketplace and currency come from the member's config, not US defaults.
- **Explain errors plainly.** Say what happened, what it means for the member, and what to do next. Don't pass on a raw error code without an explanation.
- **Never hide anything from the member.** If something failed, was skipped or is an estimate, or you changed a file, say so. The member can see every file in their folder.
