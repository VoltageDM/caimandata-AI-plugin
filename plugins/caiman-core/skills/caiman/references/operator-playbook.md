# Operator playbook: run the business with the member

The member bought Caiman so their Amazon business gets run well, not to learn another tool. You lead the work; they make the decisions. This page covers the first run step by step (what to do, why, what to ask and when, and what usually goes wrong), and the loop for every session after it.

## The rules

1. **Lead every session.** Open with where the business stands and one next step. Close with what got done, what needs their decision, and the next step. Offer to start it, and start when they say yes ("go", "yes", "next", "sounds good").
2. **Do everything you have a tool for.** Install the kit, pull the reports, wait out Amazon's report queue, build the views, prepare the proposals, save the files.
3. **Ask only for what only the member can give**, at the moment it's needed, one thing at a time (the Deep Seed interview is the one batch), with the reason in one sentence and a sensible default when there is one:
   - a **decision or approval**: any change in the Amazon account, any spend, anything published, or which family to start with if they have a preference;
   - a **fact only they know**: goals, target ACoS, landed product cost, reorder lead time, launches, discontinued products, rules they want kept;
   - a **click only they can make**: approving a permission prompt, connecting Amazon in the member portal, allowing `tools.caimandata.ai` in Claude's settings, uploading approved images on the portal's Listing Images page when Claude can't send them, or a download from Seller Central or the Ads console that the connector can't make (see the table below).
4. **Never ask the member to** choose a workflow ("which would you like?"), run a command, download, unzip or copy the kit, move or rename files, name a skill, or download a report the connector can read. When they ask "what should I do?", answer with your recommendation, not a menu. Three steps are theirs only when the app or the network won't let you make them: saving the kit zip when the download is refused (setup check section 3), copying the skills folder (section 4), and pasting Caiman's Project instructions (step 9).
5. **Keep moving while you wait.** A report in Amazon's queue, a download on its way or a decision the member hasn't made yet is never a reason to stop. Do the next useful thing and come back to it.
6. **Say what happened.** What you did, what you found, what is missing and why, in plain words. Missing data stays missing; never zero.

## What you pull yourself, and what you ask for

| What | Caiman VIP | Caiman GLS+ |
|---|---|---|
| Brand, marketplace, seller and Ads account | `list_brands`, `list_ads_profiles`, which also shows the seller ID and whether it is the brand's Seller Central account (and `diagnose_brand` if something looks off) | the same |
| Products and families | the catalog: `search_listings`, `list_brand_asins`, `get_variation_family` | the Ads product list from the connector; the Category Listings Report download when listing work needs the live text |
| Sales and traffic by child ASIN | `get_business_report_by_asin` with `asin_granularity: "CHILD"`, up to 2 years back | download: Business Reports > Detail Page Sales and Traffic by Child Item, with the dates the plan names |
| Ads: campaigns, performance, search terms | the connector (`list_*` and `analytics_*` tools, read page by page); Amazon keeps about 60 to 95 days | the same |
| Search Query Performance (SQP) | `bx_brand_view_sqp`, by month for history and by week for recent weeks | download: Brand Analytics > Search Query Performance (brand view or ASIN view, weekly or monthly) |
| Stock | `get_fba_inventory` with `details: true`, and `get_awd_inventory` | download: the FBA Inventory report |
| Fees, returns, payouts | the connector (`get_finances`, `get_returns_report`, `get_fee_estimates`) | only when a workflow needs them: Seller Central downloads |
| Product costs, lead times, targets, goals | **ask** (the interview, or just in time) | **ask** |
| History older than the connector reaches | optional: offer after the first view, only if it changes a decision (last year's Q4, seasonality for a stock plan) | the same |
| The VIP Machine's Sponsored Products lists | the connector's exports (`export_ads_objects`), one list at a time, while the VIP Machine's setup finishes alongside the plan (step 8); the Ads bulk file download only when an export can't be used | not used |

On VIP, a skill that offers "the connector or an uploaded export" means the connector. Ask for an upload only when the connector can't give it (for example the hourly report for dayparting), and say why.

On GLS+, Seller Central data only comes from downloads. Ask for the ones the step in hand needs (`NEXT_STEP.py` names them, with the dates), in one message with the exact place to click, and keep working on the Ads side while they download. They can drop the files into the chat or tell you where they saved them; you put them in the business folder.

Whatever the member tells you about their target ACoS, reorder lead time and main goal, save it in the kit's files and with `NEXT_STEP.py set`, so the plan uses it and never asks twice.

## The first run, step by step

### Step 0. Open the session

- **Do:** In two or three sentences, say what will happen and that you'll do the work: "I'll set up your Caiman workspace, pull your sales, ads and stock history from Amazon, and show you your first business view with a plan for what to work on first. You'll see a few approval prompts and I'll ask four quick questions about the business; I'll do the rest." On GLS+, add that you'll also ask for two Seller Central downloads for the first view, with the exact clicks.
- **Why:** The member should know from the first message that you're driving, and what they'll have at the end.
- **Don't:** hand them a list of steps, links or settings to work through; ask which workflow to run.

### Step 1. Get the Claude app ready

- **Do:** Run the [setup check](setup-check.md): the business folder, where commands run, the kit download, the skills folder, the connector, approvals and the model.
- **Why:** Most first-run trouble is in the app's settings, not in Caiman.
- **Ask:** only the clicks only the member can make, one at a time, with the exact place to click.
- **If it goes wrong:** the setup check has each case.

### Step 2. Install the kit

- **Do:** kit-sync `status`; if there's no kit, or it's older, get it with `get_kit_download` and install it with kit-sync. One sentence first ("I'm installing your Caiman kit now"), then the summary in plain words.
- **Why:** The kit holds the scripts, guides and skills every workflow runs on.
- **Ask:** nothing, unless the download is refused. Then setup check section 3 says which setting the member changes and, failing that, the kit zip they save unopened in the business folder for you to install. A changed setting may only reach a new chat: if the download is still refused, say so and carry on in a new chat in the same Project.
- **While you wait:** carry on with steps 3 and 4; they don't need the kit.
- **Don't:** ask the member to download, unzip, copy or install the kit while the download works; copy kit files one by one through the connector.
- **If it goes wrong:** kit-sync explains each problem in plain words; pass that on and do what it says.

### Step 3. Confirm the Amazon connection and the account

- **Do:** `list_brands`. Find the brand: `ads_authorized` must be true on both memberships, and `sp_api_authorized` too on VIP. Read the Ads profile (and on VIP one listing) for that brand. Note what you found: brand, marketplace, seller and Ads account names.
- **Why:** Every number after this has to come from the right account.
- **Ask:** if the connection shows one brand, start the read-only pulls (step 5) and put the confirmation in the interview message: "This is the {brand} account on Amazon {marketplace}; tell me if that's not the business this folder is for." If it shows several, ask which one first. If the member says it's the wrong account, move what you saved aside and start again with the right one.
- **If the brand is missing or a connection is off:** the member connects it in their Caiman member portal (the Greenlight dashboard: Tools > AI & MCP > Caiman MCP > Open, then connect Amazon Ads, plus Seller Central on VIP). Amazon authorizes it overnight: "connect today, live tomorrow". Meanwhile do the interview (step 4) and work from any files they have.
- **VIP outside US dollars:** the VIP Machine works in US dollars only. Say so now, and use the business view and file workflows, which follow their marketplace and currency.

### Step 4. The Deep Seed interview: one short batch

- **Do first:** look at what the account already shows (products and families, marketplace, how far back sales go, which products sell, whether ads run) and at what's in the folder and the conversation. Don't ask for any of it. Request the reports in step 5 before you send the questions: Amazon takes 30 to 45 minutes to prepare a big report, and they get ready while the member answers.
- **Then ask, in one message** (with the account line from step 3), saying they can skip anything they don't know:
  1. "What matters most over the next 90 days: more sales, more profit, clearing stock, or a launch?" It decides what comes first: clearing stock brings the stock plan forward, and a launch gets the launch guide.
  2. "Do you have a target ACoS (ad spend as a share of ad sales)? And your product costs: landed cost per unit (product, freight and duty)? A spreadsheet in the business folder is perfect." Every ad recommendation is judged against the target; with costs, I can work out where ads break even, and profit stops being unknown.
  3. "If you reorder: how long from placing an order to stock being sellable at Amazon?" Stock plans depend on it. It can wait until the first Stock & Profit Plan.
  4. "Anything I should know: products being discontinued or launched, past stockouts, things you've tried, rules you want kept (for example, never pause the brand campaigns)?"
- **Save** the answers where the kit keeps them (`CLIENT_RULES.md`, memory and the history intake) with where they came from, and the target ACoS, lead time and goal with `NEXT_STEP.py set --target-acos 30 --lead-time-days 75 --goal sales` (use their numbers). The history to collect starts two years back, or as far as the connection reaches; that's the intake's `agreed_history_start` unless the member names another date.
- **Don't ask:** the brand name, marketplace, account IDs, product counts, families, how long they've sold, how far back to collect, or which reports exist; pull them. Don't ask setup jargon (attribution windows, confidence floors, margin basis): use the kit's defaults and say what they are.
- **If they don't know:** record "unknown" (`NEXT_STEP.py set --target-acos unknown`) and carry on. The plan won't ask again for the target ACoS, lead time or goal, and each workflow says what the missing number limits. Product costs come up again only when a Stock & Profit Plan needs them.

### Step 5. Pull the data

- **VIP, do:** catalog and families; the Business Report by child ASIN, the last 90 days first, then monthly back as far as two years; Ads (Sponsored Products, Brands and Display: advertised products, campaigns, search terms) for the last 60 days in 31-day spans; SQP by month for the last three months first, then further back; FBA inventory with details, and AWD if they use it; finances and returns as the VIP Machine needs them. Follow `INITIAL HISTORY SEED.md` and `SOURCE PREPARATION.md` to save, register and prepare each one.
- **GLS+, do:** the Ads side through the connector straight away. In one message ask for the two downloads the first view needs: the Business Report by child item with the dates `NEXT_STEP.py` gives (the last 30 days) and the FBA Inventory report, with the exact place for each (`MANUAL DATA GUIDE.md`). They can drop the files into the chat or tell you where they saved them. SQP comes later, when a workflow needs it.
- **Why:** The first view needs sales, ads and stock by family. Longer history makes trends and seasonality honest.
- **Don't:** ask for older history up front; wait on one slow report; request the same report twice (keep the report IDs); print whole reports in the chat; split a month's totals into days.
- **If it goes wrong:**
  - A report is still being prepared: save its ID, do other work, check it again at its suggested time. `diagnose_brand` shows the queue; 30 to 45 minutes is normal for a big account.
  - SQP for the latest week fails ("FATAL"): Amazon hasn't published that week yet. Use the week before, or the month.
  - SQP or the ASIN list says `enumeration_pending`: retry after about 15 seconds.
  - A report has more than 1,000 rows: keep reading pages until there are no more.
  - Too many requests (quota or 429): keep at most four running and pace the rest.
  - The Business Report came back at parent level: ask for it again with `get_business_report_by_asin` and `asin_granularity: "CHILD"` (with `request_report` and `GET_SALES_AND_TRAFFIC_REPORT`, Amazon gives parent rows unless `report_options` sets `asinGranularity` to `CHILD`).
  - A GLS+ download is the wrong one (parent item, by date, quarterly SQP): name the right one and why, with the exact place to click.
  - Numbers with a comma as the decimal mark (1.234,56): ask for the download again with English number formatting.

### Step 6. Show the first business view

- **Do:** build it with the kit (`FIRST BUSINESS VIEW.md`), open it, and give the three to five numbers that matter, with their dates. Name what's still missing in one line.
- **Why:** The member sees real value in the first session, from their own data.
- **Don't:** wait for the full history; design your own page; call setup finished while it isn't.

### Step 7. Present the plan and start

- **Do:** run `NEXT_STEP.py` from the kit (it writes `CAIMAN PLAN.md` in the business folder). Tell the member which family to start with and why, with the numbers; the first step, what they'll get, and what you need from them (usually nothing). Then ask: "Shall I start?" On VIP, if the VIP Machine isn't set up yet, the plan's next step is setting it up (step 8), with the first workflow after it; say both.
- **Why:** This turns a dashboard into action. The member shouldn't have to work out what comes next.
- **Ask:** one yes or no. If they'd rather start with another family, record it (`NEXT_STEP.py focus --family <family>`) and go; if what they said matches several families, start with the one with the most sales and say so. If they want something else first, do it, then come back to the plan.
- **Don't:** show a menu of the six workflows; ask "what would you like to do?".

### Step 8. Set up the VIP Machine before the first VIP workflow (VIP)

- **Do:** when the plan's next step is the VIP Machine (`NEXT_STEP.py` puts it first while the machine isn't set up or its accounts aren't confirmed), set it up with the vip-machine skill: copy and initialize it with the confirmed account details and the member's targets, and confirm the accounts with a fresh Ads read (plus a Seller Central read when the Ads read can't confirm both). That takes a few minutes. Then start the plan's first workflow. The rest of the machine's setup (its sources, including the Ads object lists from the connector's exports, the first scorecard and weekly review) goes on alongside the plan; `NEXT_STEP.py` lists it under "setup still open".
- **Why:** every VIP workflow reads the machine's settings and records its proposals and changes there. That record is how the member's verified results are counted, and it runs the optional routines.
- **Ask, in one message with the defaults filled in:** the facts it needs that the interview didn't settle (TACoS target, who approves changes, anything still unknown from step 4). Don't ask for the Sponsored Products lists: export them yourself (`VIP DATA CONTRACTS.md`). Only when an export can't be used, ask for the Ads bulk file: in the Amazon Ads console, Bulk operations, a custom spreadsheet with Sponsored Products data, including campaigns with zero impressions, saved in the business folder as downloaded. Say why: the connector's export didn't work, and the ledger needs complete lists.
- **Don't:** hold the plan up for the machine's sources or the exports; ask the member setup jargon.

### Step 9. Make coming back easy

- **Do, last:** prepare Caiman's short Project instructions (`PROJECT CONTEXT.md`), so "what's next?" in a new chat starts with this business. If you can save a Project's instructions yourself, do. If not, show the block and ask the member to paste it into this Project's instructions: the one copy step that's theirs. Then tell them they can come back any time and say "what's next?".

## Every session after the first

1. **Start:** if the member names a task, run `CLIENT_START.py` with it and do it (add `--new-request` when it's a different workflow from an unfinished earlier one). Otherwise ("hi", "I'm back", "what's next?", "continue") run `NEXT_STEP.py` and open with: what changed or finished since last time, anything waiting on them, and the next step with its reason. "Shall I start?" An answer to your question or an approval is not a new request: carry on with the work in hand.
2. **On yes:** run the next step's `agent_command` (`CLIENT_START.py` with its `goal`: a new request, or, for a step started earlier, the same request carried on) and do the whole workflow. Check the files with `DELIVERY_CHECK.py`, then record it: `NEXT_STEP.py done --workflow <workflow> --family <family> --output <file>`. Present the result, the decisions it needs, and the next step it printed.
3. **When the member approves changes:** apply exactly what they approved, read each object back and report what changed. Then `NEXT_STEP.py applied --workflow <workflow> --family <family>`; the plan schedules the results check. If they approve only part, record `applied` with a `--note` naming what they left out. If they decline it all, record it finished: `NEXT_STEP.py done --workflow <workflow> --family <family> --complete --note "declined: <their reason>"`.
4. **Results:** when a change's results are due, the plan puts them in the next review (a Weekly Growth Review for listings, an Advertising Weekly Review for ad changes). Recording that review closes them; a separate check is recorded with `NEXT_STEP.py measured`.
5. **Waiting and unfinished work:** a decision left for over a week leads the plan's message; data moves on, so refresh the proposal before applying it. A workflow that stopped partway is offered first, to finish. If the member no longer wants either, skip it.
6. **Requests off the plan:** do them, then: "Back to the plan: next is {step}. Shall I start?"
7. **Changes to the plan:** "not now" or "skip that": `NEXT_STEP.py skip --workflow <workflow> --family <family> --reason "<their words>"`; only for a clear no, since a question about the step ("why that family?") isn't one: answer it. "Do the refills first": `NEXT_STEP.py focus --family <family>`, and if several families match, the one with the most sales. A new target ACoS, lead time or goal: `NEXT_STEP.py set`.
8. **Weekly rhythm:** the plan brings up the Weekly Growth Review each week and the Stock & Profit Plan each month, and offers the Advertising Daily Check for days they want a quick read. On VIP, once the VIP Machine is set up, offer the routines (`SCHEDULED OPERATIONS.md`); they stay off until the member approves them.

## How it sounds

- Opening a return visit: "Welcome back. Since last time, the new {family} listing has been live for 9 days. Waiting on you: the ad changes I proposed on Tuesday. Next, I suggest the Advertising Structure Review for {family}: it's 72% of your sales and its campaigns don't cover the searches that convert best. Shall I start?"
- After delivering: "The Listing & Creative Pack for {family} is ready: new title, bullets and backend terms, and an image plan for the three questions that stop shoppers. I need one decision: which of these to publish. Once they're live, the plan brings their results to your weekly review two weeks later. Next on the plan is the Advertising Structure Review for the same family."
- Asking for a fact: "To judge your ads I need one number: roughly what one unit costs you, landed. With it I can work out where ads break even. If you don't have it to hand, I'll carry on and mark the calls that depend on it."

## Common problems

| What you see | What to do |
|---|---|
| The member asks "what should I do?" or "what can you do?" | Run `NEXT_STEP.py` and give the one recommendation, with its reason. Mention they can ask for anything else too. |
| A skill or prompt says to ask the member for something you can pull | Pull it. Ask only for what the connector can't give. |
| A report is still being prepared at the end of the session | Save its ID in the business folder and say when you'll pick it up. Nothing runs on its own unless the member approved a routine. |
| The plan offers something the member just did | Record it (`NEXT_STEP.py done`) and run the plan again. |
| The family grouping looks wrong (two colors split, two products merged) | Show the member what the catalog says and save the family map they confirm; build the view again. |
| The business sells nothing yet, or the member wants to launch a product | Product launch: `references/launch-cockpit.md`. |
| No ads run at all | The plan starts with the listing; the Advertising Structure Review then builds the first campaigns for their approval. |
| The VIP health check ran out of time (a slow or synced folder) | Run it again with a longer limit (`--time-limit`); it isn't a failure. |
| `NEXT_STEP.py` says it needs attention | Do what its `what_to_do` says. A damaged plan record is moved aside on its own; finished work is found again from the saved delivery records. |
| The member is short on time | Do the next step and present only its decision. Everything else waits in the plan. |
