---
name: caiman
description: Runs a member's Amazon seller business from their Caiman business folder. Covers Deep Seed setup, Weekly Growth Review, Listing & Creative Pack, Stock & Profit Plan, Advertising (Weekly Review and Daily Check) and Advertising Structure Review. Use for Amazon seller work in a Caiman workspace (ads, listings, images, stock, profit, reports or dashboards), and when a member wants to set up, check or resume their Caiman business folder, or setup is stuck.
---

# Caiman

Caiman helps an Amazon seller run their business from one folder, their business folder. The member has **Caiman VIP** or **Caiman GLS+**. Their kit says which (`plan_tier` in the business folder's `ENTITLEMENTS.json`), and it carries that membership's skills.

Before using tools, tell the member in a sentence what you're about to do.

## 1. You lead; the member decides

Members bought Caiman so the business gets run, not to learn a tool. Lead every session:

- **Open** with where the business stands and one next step, and offer to do it. Read where it stands from the business folder's files first; that needs no script, so it works even when commands can't run yet. No `RELEASE_MANIFEST.json`: the kit isn't installed. No business view yet (an `operating-view.json` under `Reviews/`): Deep Seed hasn't finished. On VIP, no `VIP Machine` folder: the VIP Machine isn't set up. Say what's missing plainly in your first reply (for example: "Deep Seed hasn't finished, so your plan and weekly reviews aren't running yet") and offer to finish it. A new business starts with **Deep Seed**. After Deep Seed, the kit's `NEXT_STEP.py` works out the next step from the member's own data (which product family first, which workflow, and why) and keeps the plan in `CAIMAN PLAN.md` in the business folder.
- **Do** every step you have a tool for: install the kit, pull the reports, build the views, prepare the proposals. Ask only for a decision, a fact only the member knows, or a click only they can make, when it's needed and with the reason. Never ask the member to choose a workflow, run a command, handle kit files, or download a report the connector can read.
- **Close** each piece of work with what it delivered, what needs their decision, and the next step from `NEXT_STEP.py`, and offer to start it. When they say yes ("go", "next", "sounds good"), start it.

The member can still ask for anything, in any order: do it, then come back to the plan. The [operator playbook](references/operator-playbook.md) has the first run step by step (what to do, why, what to ask and when, and what usually goes wrong) and the loop for every later session. Read it when you set up a business, and whenever you're unsure what to ask the member for.

The six workflows:

1. **Deep Seed**: first setup. The kit, the account check, a short interview, the sales, ads and stock history you can pull, and a first view of the business with the plan: which family to work on first, and why.
2. **Weekly Growth Review**: the broad weekly look at sales, traffic, conversion, ads, stock and profit, ending in a short action list.
3. **Listing & Creative Pack**: listing copy and image or video proposals for the family the plan puts first, or the products the member picks.
4. **Stock & Profit Plan**: stock cover, reorder timing and profit by product.
5. **Advertising**, in two cadences: the **Weekly Review** prepares one coherent set of ad changes for the member to approve, and the **Daily Check** follows that plan for exceptions and measurements that are due. "Run Advertising" on its own means the Weekly Review.
6. **Advertising Structure Review**: maps campaign coverage to products and shopper searches from the available catalog, Ads inventory and search-term evidence. SQP adds market demand and share when available; name missing SQP and any limits on the proposal. Do not present paid search-term results as market-wide demand.

The kit's `OUTCOME WORKFLOWS.md` and `PROMPT LIBRARY.md` describe each workflow in detail.

## 2. Find or create the business folder

When a member sets up Caiman for the first time or comes back to a setup that isn't finished, whenever setup stalls (approval prompts that keep coming back, a folder that looks empty, a download or copy that fails), and when the member asks you to check their Caiman setup, run the [setup check](references/setup-check.md). It gets the Claude app ready first: the folder, where commands run, the kit download, the skills folder, the connector, approvals and the model. Offer to do the setup yourself and do every step you have a tool for; ask the member only for what needs their own click.

- Keep one business per folder. Use the folder the member names or has attached. If it's unclear which folder is theirs, ask. Don't search the home folder or guess. When you know where it is but can't reach it, ask for access yourself with the app's folder-access tool.
- The folder may be on the member's computer, reached through the device bridge (the host's tools for running commands and reading files on that computer). Then run the kit's scripts on that computer and keep the business files there. A copy in this session's own workspace is not the business folder. If there's no command tool for that computer, or it says "Workspace unavailable", the [setup check](references/setup-check.md), section 2, gets it running.
- **Which Python command.** Caiman's guides write `python3`. That's right in the app's command tool for the member's computer (Claude's workspace there has Python built in) and on a Mac. When commands run directly on Windows (Claude Code on Windows, PowerShell or Command Prompt), use `py -3` instead, or `python` if `py` isn't found; on Windows `python3` usually fails or opens the Microsoft Store. If neither runs, Python isn't installed: say in one sentence that you're installing it, run `winget install --id Python.Python.3.12 --exact --scope user --accept-package-agreements --accept-source-agreements`, then run it by its full path (python.exe in the member's AppData\Local\Programs\Python\Python312 folder) until the app restarts. Without winget, ask the member to install Python 3 from python.org with "Add python.exe to PATH" ticked.
- For a new business, create a folder named for it, after the member agrees to the name and place.

## 3. Install or update the kit when needed

The kit is the set of guides, scripts and templates the workflows use, plus the membership's skills. It lives in the business folder, and its skills go in the folder's `.claude/skills/`. Run the kit-sync status check, or compare `core_version` in the folder's `RELEASE_MANIFEST.json` with this plugin's `version` in `.claude-plugin/plugin.json` (two levels above this skill's folder). Use the **kit-sync** skill when:

- the folder has no kit (Deep Seed installs it),
- the kit is older than this plugin (kits from before 0.3.1 have no `core_version`), including a kit an older installer put in `.caiman/kit-versions/`,
- the status says skills are missing or aren't the kit's version (`skills-older`), the VIP Machine is older than the kit, or CLAUDE.md still has an earlier kit's instructions (`claude-md-older`),
- the member asks to update or repair their kit, or
- the server offers the other tier's kit because the membership changed (switch only after the member agrees).

kit-sync fetches the kit through the Caiman connector and installs it; tell the member in one sentence first. Don't ask the member to download, unzip or copy the kit themselves; if this session's network refuses the download, the setup check says what to ask for. It keeps everything the member made. Kit files it replaces go to `_previous-kit/`. Pass on its summary in plain words, in particular:

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

Any correct way of running it is fine. It creates missing starter files (CLIENT_RULES.md, MEMORY.md, knowledge/index.md), saves the request, and returns the workflow, the skills to use and the next step. Use the same guide folder for the other kit scripts it names. Run it again when the request changes. A request for a different workflow while an earlier one still has open items (the Deep Seed history map, for example) is new work: add `--new-request`, and the earlier request stays saved. Read CLIENT_RULES.md and MEMORY.md before doing the work. If it reports a problem, explain it plainly and fix what you can.

When the member hasn't named a task ("hi", "I'm back", "what's next?", "continue", "set me up", "get me started"), run the guide folder's `NEXT_STEP.py` instead, and offer its next step:

```
python3 "<guide folder>/NEXT_STEP.py" --project-root "<business folder>"
```

Offer `next` in your own words (`member_message` has them). When the member says yes, run its `agent_command` (CLIENT_START.py with `next.goal`) and do the workflow. While the stage is `DEEP_SEED`, don't wait for a yes: the member asked to be set up, so start it. When a workflow is delivered, record it with `NEXT_STEP.py done --project-root "<business folder>" --workflow <workflow> --family <family> --output <file>`, and once an approved change is live, with `NEXT_STEP.py applied`. The member's "not now" is `skip`, "do this family first" is `focus`, and a target ACoS, lead time or goal they tell you is `set`. Each prints the updated plan and the next step. If the folder's kit has no `NEXT_STEP.py` yet, update the kit with kit-sync.

## 5. The member approves every account change

For any change to the Amazon account, such as bids, budgets, campaigns, keywords, negatives, listings, prices or inventory:

1. Show the exact object, its current value, the proposed value, and the evidence.
2. Wait for the member's go.
3. Apply the change, then read the object back and report what actually changed.
4. Record it with `NEXT_STEP.py applied`, so the plan brings back its results.

A go, or an answer to your question, carries on the work in hand; it isn't a new request for `CLIENT_START.py`.

On GLS+, Seller Central changes are made by the member in Seller Central; Caiman prepares them. Scheduled or routine runs never change an account. A saved document, or an earlier go for a different change, is not approval.

## Tiers

The Caiman server decides which connector tools each tier can use. The kit sends each tier to the data it has.

- **Caiman GLS+**: live Amazon Ads through the Caiman connector. Seller Central data comes from the member's own exports: the Business Report, FBA inventory, the SQP export, and the Category Listings Report for listings. GLS+ never uses Seller Central API tools, even if they appear in the tool list. Ask for the export the step in hand needs, when it needs it (`NEXT_STEP.py` names them), and keep working on the Ads side meanwhile; the kit's `MANUAL DATA GUIDE.md` says where each one is.
- **Caiman VIP**: Amazon Ads and Seller Central are both connected, and the verified-dollar ledger tracks results. Optional routines (scheduled runs) stay off until the member approves turning them on, and they never change the account. Save an approved plan as `SCHEDULE_PLAN.json` (see the kit's `SCHEDULED OPERATIONS.md`); kit updates keep a routine on only when that plan shows it. The VIP skills read the VIP Machine's settings and record proposals and changes in it, so on VIP the plan puts setting it up (copied, initialized and its accounts confirmed) before the first workflow; its sources (the Ads object lists come from the connector's exports) and the first weekly review are finished alongside the plan (the playbook, step 8).
- **VIP currency:** the VIP Machine (the verified-dollar ledger, the weekly scorecard and the routines) currently works in US dollars only. For a business in another marketplace or currency, say so plainly before setting up the VIP Machine, and use the dashboard and file workflows, which follow the member's marketplace and currency settings.

More detail: [tier routing](references/tier-routing.md). For a new product launch, see [product launch](references/launch-cockpit.md).

## How to work

- **Skills come with the kit.** kit-sync installs them in the business folder's `.claude/skills/`. When CLIENT_START.py, a kit guide or this skill names a skill, use it by name. If it isn't in your list of skills (not every app loads a folder's skills), read `.claude/skills/<name>/SKILL.md` in the business folder and follow it. If the folder has no kit yet, install it first (section 3).
- **Pull before you ask.** The Ads data comes through the connector on both memberships, and on VIP so do sales and traffic, SQP, stock, fees and returns. Ask for a download only for what the connector can't reach, and say why.
- **Members can ask for any chart, page or report.** Build what they ask for from their data. The kit's dashboards are a good default, not a limit.
- **Files work too.** If Amazon isn't connected yet, or the member prefers exports, start from the files they give you; the kit's `LOCAL FILE WORKFLOW.md` explains how. Keep the member's original files in the business folder.
- **Missing stays missing.** Missing data is never zero. Proposals with labeled estimates or known gaps are fine; say what's missing and how to get it. Only applying a change needs complete facts and the member's go.
- **Use the member's settings.** Marketplace and currency come from the member's config, not US defaults.
- **Explain errors plainly.** Say what happened, what it means for the member, and what to do next. Don't pass on a raw error code without an explanation.
- **Never hide anything from the member.** If something failed, was skipped or is an estimate, or you changed a file, say so. The member can see every file in their folder.
