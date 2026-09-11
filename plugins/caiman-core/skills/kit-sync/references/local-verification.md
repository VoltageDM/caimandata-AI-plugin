# Local verification input and result

Establish the [verified local helper directory](local-helpers.md) on the selected device first. Run this helper only for an explicit install/update or missing managed resource. It reads files and emits one compact JSON result. It performs no network request, transfer, install, chmod, deletion, state write, or account action.

```text
python3 <verified-local-tools>/verify_kit.py --root <selected-project> --manifest <saved-local-manifest>
```

The default state path is `<selected-project>/.caiman/kit-state.json`. `--state` can name another file inside the selected project. `--max-items` limits reported exception paths (default 10); counts remain complete. Exit 0 means `CURRENT` **against the supplied local manifest**. Exit 2 retains `INCOMPLETE`, `COMPLETE_STATE_UPDATE_REQUIRED`, or `STOP`; inspect the status, not only the exit code. Provider freshness and entitlement are not verified by this helper.

## Normalize an actually received manifest

This is a local helper format, not a claimed server schema or tool argument. Use `plan_install.py` and [the intake procedure](install-intake.md) to convert only supported observed fields into a saved local file; do not hand-parse the response in repeated shell calls. Preserve every path and hash and the contributing kit/version. If the server response cannot be mapped unambiguously, stop; do not invent paths, versions, permission, or metadata. Keep the original response/hash in the install receipt outside conversation content.

```json
{
  "schema": "caiman.kit-verification-manifest.v1",
  "kits": [
    {
      "kit": "vip",
      "version": 4,
      "files": {
        "AGENT_START.md": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
      }
    }
  ]
}
```

The example hash is illustrative. Each `files` value is a raw SHA-256 string, or a metadata object containing its `sha256`; the wrapper itself has exactly `schema` and `kits`. Kit entries have exactly `kit`, `version`, and `files`. The known tier order remains VIP above GLS+. Unknown or repeated tiers stop. Every effective path is verified. Lower-tier-only skills, operating-framework/runtime, or entrypoint/entitlement-control files stop for support review; unique non-capability documents are reported. The local selected-tier entitlement, when present, must match the effective tier.

## State coverage

The helper reads the legacy single-kit format with string hashes and hash metadata objects. It also accepts the proposed complete state shape:

```json
{
  "schema": "caiman.kit-state.v2",
  "status": "complete",
  "kits": {"vip": 4},
  "manifest_sha256": "<the helper's effective manifest digest>",
  "files": {"AGENT_START.md": "<verified raw SHA-256>"}
}
```

A supported installer owns writing this record after verified installation. This helper never writes it. The effective digest covers the complete merged file map and every contributing kit/version. In a partial state, retain an explicit partial status and truthful ownership for files already written; no-op is forbidden until full current manifest coverage is independently proven. Existing partial/old-format state is not silently upgraded.

`CURRENT` requires all expected bytes, a complete matching state map and kit versions, matching effective digest when recorded, and no unresolved retired owned files. All bytes present but incomplete state returns `COMPLETE_STATE_UPDATE_REQUIRED`, permitting a state repair without unnecessary download. Missing or mismatching current files and retired owned files remain `INCOMPLETE`. Retired member-edited files stay untouched and are named for preservation; the supported installer reconciles ownership before declaring current.

Return only the summary and a few relevant exception paths to the member. Raw manifests, local file bodies and base64 do not belong in the conversation.
