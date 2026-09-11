# Put the verified helper on the selected device

The plugin may run in a cloud workspace while the selected folder lives on the device. Use actual host-reported paths and authorized file/command tools. Do not search private app caches or infer that a cloud path is local.

Prefer the helpers already present in the selected complete kit's `Install tools/` folder, checking the needed files against `helper-carrier.json`. Otherwise use the exact supplied complete tier ZIP or paired Core ZIP. `scripts/bootstrap_local_helpers.py` copies the pinned helper set into a new staging directory and executes none of it.

```text
python3 <bootstrap>/bootstrap_local_helpers.py --archive <actual-local-kit.zip> --archive-sha256 <approved-archive-sha256> --carrier-kind vip --staging-parent <existing-authorized-directory>
```

Use `--carrier-kind gls-plus` for GLS or `core` for the paired Core carrier. The current generated pin table is the authority for helper bytes; old version prose is not. If the bootstrap itself is cloud-only, read only that small launcher and pass its exact source and literal arguments once through the host's supported local Python tool. Do not relay the larger helpers or the kit. Respect actual execution refusals; encoding is not an alternative permission path.

`LOCAL_HELPERS_READY` returns the actual directory and hashes. Invoke the planner, installer and downloader from that directory. No SIM permission is fabricated: ordinary local installation follows the user's existing installation authorization, while account changes, engine initialization and schedules retain their separate gates. `postflight_install.py` remains a legacy simulation-only diagnostic and is **not** the production installer or production postflight.

If the complete archive or local execution facility is absent, name that exact missing prerequisite and continue existing authorized work where possible. The client should only need to supply the complete archive/select the business folder or allow the normal host prompt, not debug helper placement.
