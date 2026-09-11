# Local helpers before installation

The three implementation helpers can be in the cloud plugin while the selected folder is on the member’s device. Resolve that boundary before reading their source. Use only exact paths supplied by the host, the current task or the approved delivery receipt; do not search private application caches or unrelated folders.

1. If the current install receipt names an existing helper directory on the same device as the selected folder, check its three file hashes against [helper-carrier.json](helper-carrier.json). Matching bytes can be invoked directly by local path. A receipt alone is not fresh file verification or permission to execute code.
2. Otherwise, check for the exact approved local carrier supplied with the selected kit. The known compatible Core0.2.5 ZIP and three pinned member hashes are recorded in the contract. Core0.2.8 reuses those unchanged helper implementations; do not load the older carrier’s skill instructions or register it as a second plugin.
3. If the carrier is absent, use a provider/host’s actual documented direct file or artifact transfer when available. Do not infer that cloud attachment access also grants device access. If no route exists, stop this setup path with `LOCAL_HELPER_TRANSPORT_UNAVAILABLE`: “Place the approved Core/helper ZIP from this delivery beside the selected kit in your chosen folder, then continue.” Name its real supplied filename and hash; never invent a download URL. Existing authorized local work can continue.

## Bounded bootstrap

Once the approved carrier exists on the device and local file preparation is authorized, run the small `scripts/bootstrap_local_helpers.py` through the host’s supported local code tool. If the bootstrap file itself is cloud-only, read **only this bootstrap** (under 4 KiB) and submit that exact reviewed launcher once to the existing local Python execution facility with the arguments below. This is the only small source launcher needed; do not read, encode, paste, reconstruct or relay `plan_install.py`, `verify_kit.py` or `postflight_install.py`. If local code execution is unavailable or refused, retain the transport/permission gap; encoding is not an alternative authority route.

```text
python3 <bootstrap-location>/bootstrap_local_helpers.py --archive <actual-device-carrier.zip> --archive-sha256 <independently-approved-carrier-sha256> --staging-parent <existing-authorized-local-directory>
```

For a host tool that accepts source plus arguments, use those actual supported fields; do not invent them. A shell-based device tool can run Python from literal standard input, so no bootstrap file needs to exist on the device:

```text
python3 - --archive '<actual-device-carrier.zip>' --archive-sha256 '<approved-sha256>' --staging-parent '<authorized-local-directory>' <<'CAIMAN_BOOTSTRAP'
<exact contents of bootstrap_local_helpers.py only>
CAIMAN_BOOTSTRAP
```

Use proper shell quoting for the real argument values. Keep the delimiter literal and the reviewed launcher unchanged. This example is a local Python invocation, not an assumed connector tool schema. Do not interpolate archive paths or user text into Python source. Running a short launcher is separate from running the copied helpers.

The bootstrap verifies the bounded archive hash, rejects unsafe/duplicate/link/special members, verifies the three pinned bytes, then copies only those allowlisted helper members into one new `caiman-local-helpers-*` directory. It never overwrites an existing directory, registers a plugin, installs the client kit or runs helper/engine/account/schedule code. Partial write failures remain STOP with the new partial staging path; existing files stay untouched.

`LOCAL_HELPERS_READY` returns the actual local directory and hashes and saves `LOCAL_HELPERS.json` there. Keep that small reference in the normal install receipt so later updates can verify and reuse it. Only paths, hashes and compact results enter context. Now read the needed intake section and invoke `<verified-local-tools>/plan_install.py`, with the member’s actual selected project as `--root`. The other two helpers are siblings so imports resolve locally.

Copying the tools does not authorize their execution. Preserve actual existing approval for local planning and the postflight’s explicit SIM/status permission, real code restrictions, actual 403 responses and all engine/account/schedule gates. Do not ask for permission again when its exact scope is already established. A local carrier does not prove the current served kit release or live subscription entitlement.
