# Product launch

Start launch work only when the member asks to launch a product (with or without an ASIN yet). Low sales on an existing product are not a reason to start one.

## Caiman VIP

To see saved launch drafts and the next step, run:

```
python3 "<business folder>/LAUNCH_WORKFLOW.py" status --project-root "<business folder>"
```

The Launch Cockpit page in the kit's `Launch Cockpit/` folder can be opened as a local preview for planning. It doesn't connect to Amazon by itself, so say so when you show it. Save launch work in the business folder, then go back to the member's usual workflows.

## Caiman GLS+

There is no Launch Cockpit on GLS+. Help with the launch using the market research, listing and creative skills, with the member's own Seller Central exports as the evidence.

## Both tiers

Any change to the Amazon account during a launch follows the usual approval rule: show the exact object, the current and proposed values and the evidence, wait for the member's go, apply it, then read it back and report what changed.

### Launch ads

A launching product has no ad history of its own (under 30 ad clicks), so its bids can't come from its own numbers, and never from an assumed conversion rate. Its campaign plan (`sp-campaign-builder`, step 2) takes every bid from the bid calculator's `starting-bids`:

- Each keyword and target starts at Amazon's suggested median bid. One Amazon gives no median for (a competitor's product, a category, a keyword its suggestions leave out) starts at the median of the suggested medians in its ad group, else its campaign; a brand term doesn't, and one with neither has no bid, which the plan says.
- These are the launch week's bids. A bid is capped only where its search group converts too little across the market to pay it at twice the launch's ACoS limit: the group's conversion in the saved Search Query Performance x the product's price today x 2 x its ACoS limit. A keyword whose group has no saved conversion isn't capped, and the plan says so.
- From day 7 the product's own numbers take over, through the Daily Check and the weekly review: the plan writes that day as each launch campaign's stop line date.
- Every campaign keeps dynamic bids, down only, and reach limited to Amazon. The member approves the build before anything is created.
