# Several brands: the workspace

Many members run more than one brand, more than one Amazon account, or both. Each brand keeps its own business folder (its kit, its files, its Amazon account), and nothing moves. The **workspace** is the folder that holds those business folders. The member opens it, and one message, or one scheduled task, works through every brand (or the ones they name), one brand at a time, and ends with one combined summary.

`scripts/workspace.py` in this skill's folder does the bookkeeping. It reads each brand's own files, never the connector, and never changes an Amazon account. Every command prints JSON with `member_message` in plain words. On Windows, use `py -3` where it says `python3` (the caiman skill, "Which Python command").

```
python3 "<caiman skill folder>/scripts/workspace.py" find        --workspace "<folder>"
python3 "<caiman skill folder>/scripts/workspace.py" init        --workspace "<folder>"
python3 "<caiman skill folder>/scripts/workspace.py" status      --workspace "<folder>"
python3 "<caiman skill folder>/scripts/workspace.py" plan        --workspace "<folder>"
python3 "<caiman skill folder>/scripts/workspace.py" run start   <workflow> --workspace "<folder>" [--brands "<brand>,<brand>"] [--goal "<request>"]
python3 "<caiman skill folder>/scripts/workspace.py" run next    --workspace "<folder>" --run "<run>"
python3 "<caiman skill folder>/scripts/workspace.py" run done    <brand> --workspace "<folder>" --run "<run>" --status done|skipped|failed|needs-answer --note "..." --summary "<file>"
python3 "<caiman skill folder>/scripts/workspace.py" run status  --workspace "<folder>"
python3 "<caiman skill folder>/scripts/workspace.py" run finish  --workspace "<folder>" --run "<run>" [--partial]
python3 "<caiman skill folder>/scripts/workspace.py" summary     --workspace "<folder>"
python3 "<caiman skill folder>/scripts/workspace.py" update-plan --workspace "<folder>"
python3 "<caiman skill folder>/scripts/workspace.py" update      --workspace "<folder>" --zip "<kit zip>" [--zip "<other membership's kit zip>"]
python3 "<caiman skill folder>/scripts/workspace.py" routine     list|prompt [<workflow>] --workspace "<folder>"
```

A brand can be named by its ID (from `find`), its name, its folder or its connector brand slug.

## Recognize a workspace

- The folder you work in is a workspace when it has `CAIMAN WORKSPACE.json`, or when it has no kit of its own (no `RELEASE_MANIFEST.json` or `ENTITLEMENTS.json`) and holds two or more business folders, up to three levels down. Business folders deeper than that aren't part of it: when `find` (or the setup check) says they are further down, the workspace is the folder that holds them (for example `handoffs/2026-09-12-v1/brands`, or the folder above it): ask the member to open it, or use it as `--workspace`. Never install a kit in the folder you were given just because no business folder was found there. `find` says for sure (`is_workspace`) and lists each brand: its name, folder, connector brand slug, marketplace, saved seller ID and Ads profile ID, membership, kit version and VIP Machine. It skips `_previous-kit`, `_archive…`, `_retired` and backup folders.
- The workspace folder itself has no kit and needs none: never install a kit there, and don't treat it as a new business. Each brand's kit is in its own folder.
- The first time, run `init` (one sentence to the member first). It writes `CAIMAN WORKSPACE.json` (the brands, with their folders and accounts), a workspace section in the folder's `CLAUDE.md` between its own `CAIMAN WORKSPACE START` and `END` lines (the member's own text outside them stays exactly as it was; the file is created if it's missing) and `START HERE - all brands.md` with the messages to use. Run `init` again when a brand folder is added, moved or renamed: it picks up new brand folders and lists the ones it no longer finds.
- **The setup check** at a workspace checks every brand: run `setup_check.py` with the workspace folder as `--project-root` (one `list_brands` call covers them all). Each brand is checked in its own folder and keeps its own `CAIMAN STATUS.md`; the answer has one headline for all of them, with each brand's checks under `brands`. Open with that headline, and deal with each brand's items in that brand's folder.
- `find` flags what needs care. **Two folders bound to the same brand**: ask the member which folder is the current one; runs leave that brand out until then, and never merge or move folders without their OK. **Brands that share a seller account or Ads profile**: the account's reports include every brand's products, so each brand's work uses only its own products; on VIP, each brand's VIP Machine needs its brand scope before its weekly review counts results: `vip_machine.py brand-scope-check` with that brand's `list_brand_asins`, the member confirms or corrects the list, then `change-settings --brand-scope <file> --reason "<their words>"` (or `--whole-account`); the VIP Machine's README, "Brand scope". Until a choice is saved, its weekly review counts every product in the account. **Kits older than this plugin**: update them (below).

## Route the request

1. **All brands, or several named:** use the run flow below.
2. **One brand named:** work in that brand's business folder only, exactly as for a single business (sections 1 to 5 of the caiman skill, with that folder as the business folder). The workspace changes nothing about how one brand works.
3. **A request for one brand that names none** ("run the weekly review", "how are my ads doing?"): ask once, "Which brand, or all of them?" Requests that are clearly about all brands don't need the question.
4. **"What's next across my brands?"**, or "what's next?", "hi" or "I'm back" at the workspace: run `plan`. It runs each brand's `NEXT_STEP.py` (which never contacts Amazon; it refreshes that brand's own `CAIMAN PLAN.md` as usual) and merges the steps into one ranked plan, each labeled with its brand, in `WORKSPACE PLAN.md`. Offer the first step in your own words, with its brand. When the member says yes, do it in that brand's folder (its `agent_command`), then come back to the plan.
5. **"Show me all my brands":** run `summary`. It writes `WORKSPACE SUMMARY.html` (and `.md`) from each brand's latest saved outputs: the business view or VIP weekly dashboard, results due, what has worked, proposals waiting on the member and alerts. It changes nothing. Open the page and give the few points that need the member.
6. **"Update all my brands":** the kit-sync skill, "Every brand in a workspace".
7. **"Continue"** with a run still open: `run next`. When more than one run is unfinished it lists them instead: carry on with the one the member means (`--run`), never a scheduled task's run.

`status` gives one table across the brands (kit, setup step, VIP Machine, last weekly review, results due, alerts) when you need to see where each one stands.

## The run flow

1. **Start.** Say in one sentence what will happen ("I'll run the Weekly Growth Review for your three brands, one at a time, and then give you one summary."). Run `run start <workflow>` with the brands the member named (`--brands`), or none for all; for a request that isn't one of the workflows, use `request` with their words in `--goal`. It saves `workspace-runs/<date> <workflow>.json` with each brand pending, and gives the first brand's `task`. Workflows: `deep-seed`, `weekly-growth-review`, `listing-creative-pack`, `stock-profit-plan`, `advertising-weekly-review`, `advertising-daily-check`, `advertising-structure-review`, `setup-check`, `request`, and on VIP the VIP Machine's routines: `vip-weekly-loop`, `vip-daily-brief`, `vip-health-check`, `vip-opportunity-review`. A brand a workflow doesn't apply to (a VIP Machine routine for a GLS+ brand, or a VIP brand whose machine isn't set up yet) is listed as skipped with the reason.
2. **Do one brand.** The `task` names the brand's folder, its account (`connector_brand_slug`, marketplace, seller ID, Ads profile ID) and how the workflow starts there for its membership: `CLIENT_START.py` from that brand's own kit, or, for a VIP Machine routine, that brand's own routine prompt with its folders. Do the workflow as the caiman skill says for one business, in that folder and with that account only, following `task.rules`. The brand's kit skills live in its own `.claude/skills/`, which the app doesn't load from the workspace folder: when `CLIENT_START.py` names a skill, read `<brand folder>/.claude/skills/<name>/SKILL.md` and follow it (the caiman skill, "How to work"). Record the brand's own work there as usual (`NEXT_STEP.py done` and `applied`, the VIP Machine's records); the run's record is extra, never instead.
3. **Close the brand.** Save a few lines in `task.summary_file` (that brand's own file; `run done` refuses another brand's): what was done, the numbers that matter, and what needs the member. Then record it with `task.when_done` (`run done <brand> --run "<run>" --status done --note "..." --summary "<file>"`). A brand that failed is `--status failed`; one that needs the member's answer or approval is `needs-answer`; one that doesn't apply is `skipped`; say why in `--note`. `run done` warns when a summary names another brand's slug, seller ID or Ads profile ID: check it before going on.
4. **Next.** `task.next` (`run next --run "<run>"`) gives the next brand. Always name the run: another chat or a scheduled task may have a run of its own open. Repeat until it says every brand has a result.
5. **Finish.** `run finish --run "<run>"` writes one combined note, `workspace-runs/<date> <workflow>.md`: a table of the brands' results, what needs the member, and each brand's summary. Give the member its main points, brand by brand. If a brand can't be done now, `run finish --partial` lists it as not run.

**A stopped run picks up at the next brand.** Nothing is lost when a session ends partway: in a new session at the workspace, "continue" (or the same request again) carries on with `run next`, and a brand that was started but not recorded comes back first, with a reminder to check what was already done. `run start` carries on only with an unfinished run of the same workflow and brands, started the same way (a scheduled task never takes over a conversation's run, or the other way round). Runs of the daily workflows (the Advertising Daily Check and the VIP Machine's daily brief and health check) start fresh each day, and the others after six days; an unfinished run from earlier is closed with its remaining brands listed as not run. `run start ... --new` starts a fresh run on purpose.

**Keep the conversation small.** Finish a brand and save its summary before starting the next. Don't carry one brand's reports or tables into the next brand's work: its summary file is what carries over. In a long run, it's fine to carry on in a new chat: "continue" picks up at the next brand.

## Hard rules: never mix brands

- **Each brand's work happens in its own business folder with its own account.** Use the brand's own connector brand slug for every connector call, and its own Ads profile and seller account. Never pass one brand's slug, profile or seller ID while working on another, never save one brand's reports or files in another brand's folder, and never use one brand's numbers in another brand's proposals or summary.
- **One brand failing or needing an answer doesn't stop the others.** Record it (failed or needs-answer, with what is needed), go on with the next brand, and list it at the end.
- **Each brand's normal approvals still apply** (the caiman skill, section 5). Ask for each brand's go separately and name the brand ("Brivara Home: these four bid changes..."); a yes for one brand never covers another brand's changes. Scheduled runs never change an account.
- **Brands sharing an account** use only their own products from that account's reports (above). **Two folders for one brand** are left out of runs until the member says which is current.

## Scheduled tasks: one per routine, for every brand

One scheduled task per routine covers all the brands: for example the daily ads check, the Weekly Growth Review, and on VIP each of the VIP Machine's routines, run brand by brand. Each uses the run flow with `--scheduled`, and reuses each brand's own workflow or routine prompt.

- `routine list` shows the all-brands routines with suggested timing and which brands each would cover, and on VIP which of each brand's own VIP Machine routines are on.
- `routine prompt <workflow>` prints the prompt for one (`advertising-daily-check`, `weekly-growth-review`, `advertising-weekly-review`, `vip-daily-brief`, `vip-health-check`, `vip-weekly-loop`, `vip-opportunity-review`).
- Create a task only after the member approves its timing and time zone, the workspace folder it runs in, and its notifications. Create it with the prompt as printed: it finds `workspace.py` in the caiman skill when it runs, so a plugin update doesn't break it. Read the task back to check it was saved as agreed.
- **VIP Machine routines** still need each brand's own approval record: save it in that brand's `SCHEDULE_PLAN.json` as its `SCHEDULED OPERATIONS.md` says, with that brand's business folder, and set the routine's `enabled` in that brand's VIP Machine settings (its `schedules/README.md`, step 5). Kit updates keep a routine on only when that plan shows it.
- If a brand already has its own scheduled task for the same routine, the all-brands task replaces it: with the member's OK, remove the brand's own task so the routine doesn't run twice.

## The files

In the workspace folder: `CAIMAN WORKSPACE.json`, the workspace section of `CLAUDE.md`, `START HERE - all brands.md`, `CAIMAN STATUS.md` (the setup check for all brands), `WORKSPACE PLAN.md` and `.json`, `WORKSPACE SUMMARY.html` and `.md`, and `workspace-runs/` (each run's record, its combined note, and a folder with each brand's summary). Nothing in a brand's business folder changes except what that brand's own workflow writes there, as usual.

If the brand folders are on the member's computer, run `workspace.py` there, as kit-sync's guide says for `kit_sync.py`: copy it across (with `kit_sync.py` for `update` and `update-plan`, named with `--kit-sync`) and add `--plugin-version <this plugin's version>`, which a copy can't read for itself.
