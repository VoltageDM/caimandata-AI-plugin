# Complete archive intake

Use the exact received archive hash and release from its supplied publisher receipt. Local verification is not a subscription check. An actual service refusal cannot be bypassed with a different artifact.

```text
python3 <verified-tools>/plan_install.py archive --root <business-folder> --archive <complete-local-kit.zip> --archive-sha256 <approved-sha256> --selected-tier <vip-or-gls-plus> --approved-release <exact-release>
python3 <verified-tools>/install_kit.py --root <business-folder> --archive <complete-local-kit.zip> --archive-sha256 <approved-sha256> --selected-tier <vip-or-gls-plus> --approved-release <exact-release> --mode <fresh-or-companion>
```

The archive representation contains packed `.skill` files. Server import expands those archives and excludes the declared `.gitignore`. Their counts differ by design. Use the exact representation's manifest; never compare packed-file counts to expanded server counts.

Fresh installation refuses differing existing package targets. Companion installation places the entire matching same-tier guide at the returned project-local version path without replacing client root instructions, identity, state, history or engines. Both paths verify the whole archive and actual installed tree. New files are not engine execution permission. Ordinary installation makes no provider calls.

## Postflight in the actual selected folder

Read the returned immutable receipt and the selected folder's `.caiman/active-guidance.json`. Use `resolve_guidance.py --root <currently-selected-business-folder>` to check its workspace marker, receipt hash and guide bytes. Guidance is stored relative to that folder; absolute installation paths are observations and may change with a new Cowork session. Use the resolved guidance root and current business root:

```text
python3 <actual-guidance-root>/GUIDED_SETUP.py status --project-root <business-folder>
```

For GLS use `GLS_GUIDED_SETUP.py`. This status remains separate from complete archive placement. Report the actual setup gate and continue it. A cloud copy or a narrated path is not device readback.

## Existing work and runtime compatibility

Use `MIGRATE EXISTING CLIENT.md`. Snapshot original business instructions and propose only real conflicts. Never replace memory/rules with blank templates. Use the separate VIP `RUNTIME_UPDATE.py` inspect/apply/backup/rollback contract when the initialized engine is an supported unchanged installed version. Keep edited/unknown engines and different operating-system update histories unchanged for support; run operating-system-specific updates on their supported system. GLS keeps its manual framework and introductory week.

The server's legacy saved-manifest parsing remains available through `plan_install.py manifest` and `local-verification.md`; it is a read-only diagnostic, not the full-archive installer. Do not write the expanded server `kit-state` from a packed archive receipt. Missing, stale-owned, edited and retired paths retain their distinct meanings.

Installation retains its staging files and uses a persistent OS lock that releases when the helper exits. It does not need permanent-delete permission. Do not request broad deletion just to tidy temporary files; cleanup is optional and separate. A failed attempt preserves partial new files for exact-byte resumption.
