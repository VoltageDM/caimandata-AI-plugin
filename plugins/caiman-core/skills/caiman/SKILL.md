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
no kit folder exists yet:

1. Call `get_kit_manifest` on the `caiman-amazon` connector. It returns the
   kit(s) this member's subscription includes (e.g. `gls-plus` or `vip`), each
   with a version and a file list (paths + sha256 hashes).
2. Create a project folder for the kit (ask where, or use a sensible default
   like a "Caiman Kit" folder in the workspace).
3. Fetch every file with `get_kit_file {kit, path}` and write it to the folder
   at its relative path. Large files arrive in chunks — keep fetching with the
   returned `next_offset` while `has_more` is true, concatenating before
   decoding. Files flagged binary are base64 — decode before writing.
4. When done, open the kit's `CLAUDE.md` and follow it — it is the kit's own
   entry point and explains the milestones and how sessions should run.

## Keeping the kit current (every session)

When working inside a kit folder, follow the sync instructions at the top of
the kit's `CLAUDE.md`: call `get_kit_manifest`, compare hashes against local
files, and re-fetch only what changed before starting work. If the manifest
call returns an authorization error, tell the user plainly that their
subscription does not currently include kit access and stop — do not retry or
work around it.

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
