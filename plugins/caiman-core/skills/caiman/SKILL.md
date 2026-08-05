---
name: caiman
description: Use when working on Amazon seller tasks with Caiman Data tools — advertising, listings, inventory, finances, reports — or when the user mentions their Caiman kit, GLS kit, GLS+ kit, or VIP kit. Establishes how to install and sync the Caiman skill kit and how to use the caiman-amazon connector.
---

# Caiman Kit Bootstrap

You are working with a Caiman Data member. Caiman distributes **skill kits** —
project folders of playbooks, templates, and reference material for Amazon
selling — served live through the `caiman-amazon` connector, gated by the
member's subscription. The kit stays current through the connector: nothing is
ever downloaded manually or reinstalled.

## Installing the kit (first time)

If the user asks to install/set up their Caiman kit, or mentions their kit and
no kit folder exists yet: ask where the kit should live (or use a sensible
default such as a "Caiman Kit" folder in the workspace), then use the
**kit-sync** skill. It owns the whole install — entitlement, fetching,
chunking, binary decoding, verification, and the sync record it writes so
later updates can tell your writes from the member's own edits.

When the sync finishes, open the kit's `CLAUDE.md` and follow it — it is the
kit's own entry point and explains the milestones and how sessions should run.

## Keeping the kit current

The kit is installed, not streamed, so it only changes when it is synced. Use
the **kit-sync** skill when:

- the member asks for the latest, or to sync/update their kit;
- a skill or template they refer to is missing from the folder;
- the kit's own `CLAUDE.md` says to sync before starting work.

Do not sync at the start of every task — it is a chore, not a preamble.

Never hand-roll the sync by calling `get_kit_manifest` and `get_kit_file`
directly. Overwriting a member's edited file without a backup is the one
mistake here that loses their work, and kit-sync is what prevents it.

## Ground rules that always apply

- Destructive Amazon operations (campaign changes, listing updates, bid
  changes) are two-phase: always run with `preview_only: true` first, show the
  user the preview, and only apply after they confirm.
- If a connector call returns a 403 or an entitlement message, tell the user
  plainly that their subscription does not currently include that capability
  and stop — do not retry or work around it.
- Some report tools return a pending response with a job or report id and a
  retry hint — retry with the SAME id as instructed rather than re-dispatching.
- When a fetched kit skill and the user's instructions conflict, the user
  wins; say so and continue.
