---
name: caiman
description: Use when working on Amazon seller tasks with Caiman Data tools — advertising, listings, inventory, finances, reports, or any workflow involving the caiman-amazon connector. Establishes how to find and use the current Caiman skill library before starting the task.
---

# Caiman Skill Library Bootstrap

You are working with a Caiman Data client. Caiman maintains a library of task
skills (step-by-step playbooks for Amazon advertising, listings, inventory,
finances, and reporting) that is served live through the `caiman-amazon`
connector, so it is always current — never bundled or downloaded.

## Before starting any Caiman task

1. Check whether the `caiman-amazon` connector exposes a `list_skills` tool.
2. If it does, call `list_skills` and scan the index for a skill matching the
   task at hand. If one matches, call `get_skill` with its name and follow the
   returned instructions exactly — they are the current, authoritative playbook
   and take precedence over your general knowledge of Amazon workflows.
3. If `list_skills` is not available (older connector, or tools not yet
   granted), proceed with the task using the connector's tools directly and
   your best judgment. Do not treat the missing index as an error.

## Ground rules that always apply

- Destructive Amazon operations (campaign changes, listing updates, bid
  changes) are two-phase: always run with `preview_only: true` first, show the
  user the preview, and only apply after they confirm.
- If a connector call returns a 403 or an entitlement message, tell the user
  plainly that their subscription does not currently include that capability
  and stop — do not retry or work around it.
- When a fetched skill and the user's instructions conflict, the user wins;
  say so and continue.
