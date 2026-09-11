# Complete local intake before transfer

First complete [local helper delivery](local-helpers.md). In the commands below, `<verified-local-tools>` is the actual directory returned by local bootstrap/readback on the same device as the selected project, never the cloud plugin folder. Use these commands only for an install/update or a required missing managed resource. Ordinary business requests use the local guide and selected skill. The planner never downloads, extracts, replaces client files, writes sync state, runs kit code, initializes a machine or installs schedules.

## A manifest already saved by the host

Do not paste or print the tool-result file. Run one local command:

```text
python3 <verified-local-tools>/plan_install.py manifest --root <selected-project> --source <exact-saved-response.json> --selected-tier <actual-requested-vip-or-gls-plus> --normalized-out <separate-existing-staging-folder/manifest.json>
```

The helper accepts the documented local verification object and the observed agent-saved object with `retrieved_at`, `source`, `note`, and `kits`. Reported kits have `kit`, `version`, `files[]`, and `superseded_file_count`; file metadata has `path`, `sha256`, `size_bytes`, and `is_binary`. It also unwraps that known payload from the observed SDK array of text content blocks without assuming an array position. The original raw SDK payload was not preserved in the native evidence; a reconstructed carrier test is not proof of those original bytes. It requires one unambiguous object, strict fields/hashes, bounded input and safe membership. Unknown fields or pagination stop for a supported mapping. The normalized file remains in staging. Only compact counts, source hash and a few exception paths go into context. An explicit requested VIP selection from the observed combined response retains all 597 VIP rows and none of the lower-tier rows. The eight reported GLS rows are an overlap-deduplicated projection with 459 superseded rows, not evidence that GLS customers receive eight files. A GLS request from that projection stops pending its complete effective membership. Retain the original source and other-kit metadata; do not silently merge tiers or reconstruct missing lower-tier hashes.

A locally parsed manifest does not establish current server authorization. Retain the original response and its hash in the receipt, along with the actual authorized selected tier, release and observation time. A full response already exposed to the model has already incurred that context cost. This helper prevents repeated parsing/content expansion; it does not make the existing server response smaller.

`BULK_TRANSFER_UNAVAILABLE` means do not fetch file-content chunks. The next route must be an actually available direct transfer outside model context or an explicitly supplied approved complete archive. `EXISTING_RUNTIME_UPDATER_REQUIRED` uses the installed project's compatible updater; a full kit must not replace an initialized client's runtime. `CURRENT` and `COMPLETE_STATE_UPDATE_REQUIRED` retain the existing verifier's exact meanings.

## An explicitly supplied complete local archive

Use the exact archive path, raw SHA-256, release and selected tier from the approved package receipt. Do not calculate a new hash and pretend it was an independently supplied trusted hash. This is a local/pre-release fallback when so declared; it does not prove current live serving or authenticate subscription access. A server 403 cannot be bypassed this way.

```text
python3 <verified-local-tools>/plan_install.py archive --root <selected-project> --archive <supplied-complete.zip> --archive-sha256 <approved-raw-sha256> --selected-tier <vip-or-gls-plus> --approved-release <exact-release>
```

The planner verifies the complete archive checksum, its single package root, safe regular members and the existing full-kit release tree/count. It compares every member against the selected project, including engines and skill archives; there is no omit-files or docs-only option. It reports counts and compact exceptions. It does not print archive bodies or create a second project.

- `COMPLETE_ARCHIVE_COPY_PLAN_READY`: all archive bytes verified; missing target files can be copied only within existing user authorization. Use a normal local file-copy facility to copy the entire package tree, preserving the selected folder. Read the existing project and plan before any write. No file selection, implicit overwrite or engine execution follows from this status.
- `EXISTING_FILES_REVIEW_REQUIRED`: existing conflicting files need their explicit backup/replacement plan. Preserve them; this helper does not authorize replacement.
- `EXISTING_RUNTIME_UPDATER_REQUIRED`: preserve the original runtime and use its compatible updater or an explicit same-tier guidance companion.
- `COMPLETE_VERIFIED_COPY`: every archive member matches. This proves the supplied complete local package copy only. It does not prove live entitlement, live release freshness, an installer state record, machine initialization, connection success or any completed operating step.

After an authorized complete copy, run the same archive plan once to verify all copied bytes. Preserve its result with the supplied archive receipt and the copy action's actual file counts. Then load the selected package's `AGENT_START.md`, which names the tier-appropriate helper. Resolve real setup status and continue the member's task. Do not skip engine files merely because live actions are unapproved: inert copying and running code are separate actions. Engine/bootstrap/data/account/schedule work still follows its own guide and actual authorization.

## Release mismatch and an authorized SIM source

Different paths or hashes between a newer supplied archive and an older authenticated service inventory mean the releases differ. The old inventory cannot verify the new release. Do not infer a subscription denial solely because new guide files are absent from an old inventory. Preserve an actual 403 or code-protection restriction and stop that service route.

An already authorized vendor/pre-release local test can use its own exact archive checksum, release, selected tier and source of that local test authorization. Keep the scope **SIMULATION_ONLY**. Do not represent this separate permission as service entitlement, use it to retrieve protected code from a refused tool, or perform live business/account/schedule work. If local code execution is restricted, respect that restriction too; copying does not remove it.

Save this small provenance record in the task's local staging. Its values come from the actual supplied package receipt and existing authorization, never a guessed hash or newly invented approval. This is a local helper format, not a server schema:

```json
{
  "schema": "caiman.local-simulation-source.v1",
  "scope": "SIMULATION_ONLY",
  "source_kind": "authorized_vendor_pre_release",
  "archive_sha256": "<exact hash from supplied approved package receipt>",
  "tier": "vip",
  "release": "<exact approved release>",
  "authorization_reference": "<actual user/vendor local-test authorization source>",
  "read_only_status_authorized": false
}
```

The record binds provenance but does not authenticate a person or service. Set the last field true only when running the existing read-only guide status is actually within the authorized local test; never use a record you wrote to expand permission.

## Postflight in the actual selected folder

Use the exact selected folder/mount shown by the host, not a similarly named cloud working directory. Re-read that folder through the host's actual local file facility; match the returned root, expected files and hashes. A download artifact is an output artifact until its contents have actually been placed and verified there. If the host-to-selected-folder mapping is unobserved, retain `LOCAL_PLACEMENT_UNVERIFIED` rather than claiming installation.

For an approved local SIM archive, run the dedicated postflight. Without the explicit status flag or corresponding actual permission, it reports the complete copy but leaves guide status pending:

```text
python3 <verified-local-tools>/postflight_install.py --root <actual-selected-project> --archive <supplied-complete.zip> --archive-sha256 <approved-sha256> --selected-tier <vip-or-gls-plus> --approved-release <exact-release> --simulation-provenance <saved-provenance.json> --run-read-only-status
```

It first checks every package member against that root. If incomplete, it runs no code. Only after complete bytes and explicit local status permission does it run the archive-bound `GUIDED_SETUP.py status` or `GLS_GUIDED_SETUP.py status`. It verifies the guide's declared hash, exact result root/schema/read-only state, concrete next action and package hashes afterward. It never runs initialization, an operating engine command, an account action or a schedule installer. Those remain separate guided steps. For a live served installation, use the complete normalized-manifest verifier and the same installed guide's authorized read-only status; the SIM provenance is not a substitute for live serving/entitlement evidence.

A passing postflight says **complete local copy; setup pending at the returned gate**. The existing guide always supplies the actual next step. It does not establish full setup, host scheduler installation, verified identity or a successful business operation. Report real framework/engine evidence for those later milestones. A reference-only package, manual demo report, `template_mode: true`, `identity_bound: false`, cloud-only memory or fabricated metric defaults cannot replace the full kit or its workflow. Retain missing values as unknown. Use the existing kit dashboard/templates unchanged and their intended workflow; do not build a substitute UI merely to produce a finished-looking report.
