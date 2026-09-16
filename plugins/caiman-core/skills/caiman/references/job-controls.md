# Native job controls

The paired Core plugin and VIP/GLS Plus kits add a shared, local job ledger. It limits repeated work, preserves report IDs and pending/unknown states, checks declared brand/account scope, and rejects stale host contexts. It grants no remote permission or business approval.

## Setup or an explicit upgrade

Use the existing selected business folder and its verified active guide. Keep its tier and selected connector. After exact source identifiers are known, prepare the small setup plan below from saved identity/config or selected-source response files. Every value must match a JSON pointer in the hash-bound local source; do not infer a connector slug from a display name. Unknown account IDs remain absent, never fabricated.

The six paired dependency files in `Job controls/` travel with the new guide. Their versioned installation, binding and rollback are separate from the business engine updater; do not replace them with an older engine-only file list. For a returning workspace, use the new paired archive and reenroll this same business folder after the guide update.

Run the paired `Job controls/portable_guard.py install` with `--project-root`, the local `--plan`, and `--plan-sha256`. This copies a versioned helper and binds it to the same workspace. It does not replace the business engine, change credentials, create schedules or perform account actions. Use this step during requested setup/update, not on every ordinary question. General educational questions do not need onboarding.

The setup plan schema is `caiman.job-control-setup.v1`. It contains the selected `tier` (`vip` or `gls-plus`), `connector` with saved `source_key` and exact exposed `tool_prefixes`, and `fields`. Required field names are `brand_slug` and `marketplace_id`; `seller_id` and `ads_profile_id` are included when known. Each field contains its `value`, an `evidence` object (`path` relative to the business folder and `sha256`), and its exact JSON `pointer`.

Run `status --project-root` to verify installed files and the identity projection. `FILES_INSTALLED_HOST_HOOK_UNVERIFIED` and local callback records do not prove native host enforcement. Check a real host turn/callback before claiming active protection. The plugin must be enabled in that host with its paired runtime; an updated guide alone is insufficient.

## Ordinary work

Continue through the existing guided task selector. The installed plugin invokes the controls; the client does not run commands. A repeated report dispatch returns the existing operation/report reference. Read that result or poll the recorded report; do not create another report because a result is pending or a response was lost. An explicitly branded retained report may be read under its current declared scope without pretending it was created by this ledger. A report without a brand selector needs its recorded scope.

Follow-up prompts stay attached to the selected original job, while each prompt has its own run identity. After a compatible guide upgrade, reinstall the paired binding from current exact source evidence; the same business, account, source and tier retain their job and report history. Guide locations and evidence paths may move without turning the job into a new request.

Use `status --project-root` to see current host prompt IDs and original job keys. If the user starts a genuinely distinct request in the same conversation, or resumes a retained job in a different conversation, the coordinator runs `select-job` before business tools. Its hash-bound `caiman.job-selection.v1` plan contains `workspace_id`, `session_id`, `prompt_id`, `mode` (`new` or `resume`), `job_key` (the recorded key for resume, null for new), and `reason`. A new job requires the actual recorded current user prompt. A resumed job requires the source prompt to have stopped and keeps every prior reservation. Old/late workers remain fenced. Ambiguous old histories require explicit selection. Never choose new merely to evade a limit or pending report; when the user's intent is unclear, retain the current job and clarify.

A limit preserves the checkpoint. Return the exact pending state and useful completed work to the coordinator. For authorized larger work, the coordinator may run `budget` with a hash-bound `caiman.job-budget-allocation.v1` plan containing `workspace_id`, `job_key`, the complete finite `limits`, and `reason`. This records a bounded allocation without resetting counters, source scope or report references; it is not business approval. Lifetime remains measured from original creation and cannot exceed 24 hours. Do not create a new session or job to evade a limit. Changing brand/account/source or tier is not an upgrade and is refused; use the existing scope-correction process. GLS retains connected Ads plus manual Seller Central evidence and does not gain connected SP-API or VIP schedules. Existing preview, exact approval and readback rules still apply to all writes.

## Rollback and host limits

This is the first release format for these job controls. It supports compatible guide upgrades under the same runtime policy. Experimental pre-release ledgers with different policy/attempt hashes are preserved but are not silently migrated; they need a separately reviewed migration.

For the exact installation, run `rollback --project-root` with its installation receipt as `--plan` and its digest as `--plan-sha256`. Rollback restores or retires only this binding and preserves all helper versions, logs and business files. Restore the matching plugin version when rolling back a paired release.

The local plugin uses command hooks; a host can disable them, fail to launch them, or time them out. The helper has its own short deadline, but this is not a hardened security boundary or a guarantee against host failure. The Voltage native runtime separately uses SDK callbacks, which can deny when its helper is unavailable. This release requires native validation on each supported host; Windows enforcement is unverified. Remote account identity and subscription entitlement still require the selected provider's real evidence. Shared code does not make those host guarantees identical.
