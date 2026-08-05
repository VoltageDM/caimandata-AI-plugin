---
name: kit-sync
description: Use when a Caiman member's project folder needs their subscription kit installed or brought up to date — on the first session in a new project folder, when the member asks to "sync", "update my kit", "get the latest skills", or when a Caiman skill or template the member refers to is missing from the folder.
---

# Caiman kit sync

Installs and updates the Caiman kit for the member's subscription into their
project folder. The kit is the member-facing library — skills, templates,
reference material — and it lives on the Caiman server, gated by their subscription.

Two tools do the work, both on the `caiman-amazon` connector:

- `get_kit_manifest` — which kit(s) they're entitled to, the version, and every
  file with its `sha256`
- `get_kit_file` — one file's contents

**The manifest is the source of truth for what belongs to the kit.** Any file
in the project folder that is not in the manifest belongs to the member. Never
modify or delete those, no matter what they look like.

## Run the sync

### 1. Read the local sync record

Look for `.caiman/kit-state.json` in the project folder. If present it looks
like this:

```json
{
  "kit": "vip",
  "version": 2,
  "synced_at": "2026-08-04T18:22:11Z",
  "files": { "START HERE.md": "9f7a…", "Skills/brand-kit/SKILL.md": "3c11…" }
}
```

That `files` map is what the last sync **wrote**. It is how you tell a stale
kit file (safe to replace) from one the member has edited (must not be silently
overwritten). If the file is absent, treat this as a first sync.

### 2. Get the manifest

Call `get_kit_manifest`.

- **Zero kits** — their subscription includes no kit. Say so plainly and stop.
  Do not treat it as an error and do not retry.
- **One kit** — proceed.
- **More than one kit** — see *Multiple kits* below before writing anything.

If the manifest version matches `.caiman/kit-state.json` and every local hash
matches the record, the kit is current. Say so and stop — do not refetch.

### 3. Work out what to change

For each manifest file, compare the manifest `sha256` against the local file's
actual SHA-256 (hash the raw bytes on disk):

| Local state | Action |
|---|---|
| Missing | **Fetch and write.** |
| Hash matches manifest | Already current. Skip. |
| Hash matches the sync record but not the manifest | Ours, and now stale. **Fetch and overwrite.** |
| Hash matches neither | **Member-edited.** Back it up, then overwrite, and list it in the report. |
| No sync record exists and file is present | Treat as member-edited: back up, then overwrite. |

Then handle removals: any path in the sync record that is **not** in the new
manifest was dropped from the kit. If the local file still matches the recorded
hash, move it to the backup directory and delete it. If it doesn't match, the
member changed it — leave it alone and mention it in the report.

### 4. Back up anything you are about to overwrite or remove

Before the first write, create `.caiman/backups/<UTC-timestamp>/` and copy each
affected file there, preserving its relative path. Never overwrite a
member-edited file without a backup on disk first.

### 5. Fetch and write

For each file to fetch, call `get_kit_file` with the kit slug and the exact
path from the manifest.

- **Chunking.** Responses cap at 768 KB. While `has_more` is true, call again
  with `offset` set to `next_offset`, and **concatenate every `content` string
  in order before doing anything else.**
- **Encoding.** `encoding: "base64"` means binary — concatenate all chunks
  first, then base64-decode the complete string. Decoding chunk-by-chunk
  corrupts the file. `encoding: "utf-8"` is written verbatim.
- **Verify.** After writing, hash the file on disk and confirm it matches the
  manifest `sha256` (which is over the raw bytes, so check after decoding). If
  it doesn't match, delete the partial file, report it, and keep going with the
  rest — do not leave a corrupt file in place.
- **Paths.** Use the manifest path exactly. Several contain spaces (for example
  `START HERE.md`). Create parent directories as needed. Reject and report any
  path containing `..` or starting with `/` rather than writing outside the
  project folder.
- Fetch sequentially. This is a background chore; steady progress beats
  hammering the connector.

### 6. Update the sync record

Write `.caiman/kit-state.json` with the kit slug, the manifest version, the
current UTC timestamp, and the full path→sha256 map **as installed**. Do this
even on a partial sync, recording only the files that verified — otherwise the
next run cannot tell your writes from the member's edits.

### 7. Report

Tell the member briefly:

- kit slug and version, and the version they came from
- counts: added, updated, unchanged, removed
- **every member-edited file that was overwritten**, with its backup path
- anything skipped or failed, and why

Call out the overwritten-edits list explicitly even when it's empty — that's
the thing a member needs to be able to trust.

## Multiple kits

If the manifest returns more than one kit, they may share paths with different
content, so writing them in sequence would silently produce a hybrid folder.

Apply highest tier first: **`vip` outranks `gls-plus`.** Build one merged file
set — take every file from the higher-tier kit, then add only those paths from
the lower-tier kit that the higher tier does not contain — and sync that. In
the report, name every kit that contributed and every path where the lower-tier
version was dropped in favour of the higher.

If the manifest returns two kits whose precedence is not covered by that rule,
stop before writing, explain what you found, and tell the member to contact
support@caimandata.com. A wrong merge is worse than no sync.

## Never do these

- Touch a file that is not in the manifest or the sync record.
- Delete a member-edited file.
- Overwrite anything before its backup is on disk.
- Write outside the project folder.
- Retry a `403`. It means the subscription does not include that kit. Say so
  and stop.
- Report success for files that failed verification.
