# Tiers: what each membership uses

The member's tier is in their kit: `plan_tier` in the business folder's `ENTITLEMENTS.json` (`vip` or `gls_plus`). The Caiman server only offers a member the kit their membership includes, and the kit carries that tier's skills. If a member changes membership (for example from GLS+ to VIP), the server offers the new tier's kit; kit-sync switches the folder after the member agrees.

| | Caiman GLS+ | Caiman VIP |
|---|---|---|
| Amazon Ads | Connected through the Caiman connector | Connected through the Caiman connector |
| Seller Central data | The member's exports: Business Report, FBA inventory, SQP export, Category Listings Report | Connected through the Caiman connector |
| Seller Central changes | Caiman prepares them; the member makes them in Seller Central | Through the connector, after the member's go |
| Optional routines (scheduled runs) | Only the Caiman dashboard's daily refresh, off until the member approves it; it never changes the account | Off until the member approves them; they never change the account |
| Verified-dollar ledger | No | Yes, in US dollars only for now (ledger, scorecard and routines) |
| Setup helper in the kit | `GLS_GUIDED_SETUP.py` | `GUIDED_SETUP.py` |

## GLS+ and the member's exports

GLS+ reads Seller Central only from files the member downloads and gives you:

- **Business Report** (sales and traffic by child ASIN) for sales, sessions and conversion.
- **FBA inventory** for stock on hand, inbound and reserved.
- **Search Query Performance (SQP) export** for market search demand and share. If it is missing, a supported advertising structure proposal can still use catalog, Ads inventory and paid search terms, with that gap named.
- **Category Listings Report** for current listing content.

The kit's `MANUAL DATA GUIDE.md` explains where to find each one. Ask for the files the step in hand needs, when it needs them (`NEXT_STEP.py` names them): one message with the exact place to click, the products and the dates. Keep working on the Ads side while the member downloads, and keep their original files in the business folder. Never use Seller Central API tools on GLS+, even if they show up in the tool list.

## VIP outside US dollars

The VIP Machine works in US dollars only for now: its ledger, scorecard and routines, and its setup refuses another currency. The connected business view on VIP (`BUILD_OPERATING_VIEW.py`) works in US dollars too: registering a report in another currency is refused. For a VIP business in another currency, say so plainly before setting anything up, and use the read-only review (`READ ONLY REVIEW.md`), which shows the connected reports in the marketplace's own currency, and the product-files workflow (`LOCAL FILE WORKFLOW.md`) for listing and image work. Don't convert amounts or edit settings to make the VIP Machine or the business view accept them. Record the currency with `NEXT_STEP.py set --currency <code>` (the Ads profile's `currency_code`); the plan then offers the read-only review instead of the VIP Machine. Say once why the VIP Machine can't be set up yet.

## When a connector tool is refused

The Caiman server enforces which tools each tier can call. If a call is refused, tell the member in plain words what couldn't be read and why, then use the export route on GLS+, or ask the member to reconnect their account on VIP. Don't repeat the refused call or switch to another connector.

## When the tier is unclear

If the business folder has no kit yet, the Caiman server settles it: ask the connector's `get_kit_download` for the `vip` kit, and if the membership doesn't include it, for `gls-plus`. If neither is offered, ask the member which membership they have and to check their account. Don't infer the tier from the tools that happen to be available.
