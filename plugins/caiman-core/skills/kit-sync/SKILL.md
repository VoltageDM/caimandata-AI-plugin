---
name: kit-sync
description: Install or update a Caiman VIP or GLS+ workspace from one complete verified kit. Use when setup or an update is requested, or a required local resource is missing. Preserve existing business instructions and data.
---

# Install the Caiman kit

Explain the next local step briefly, then perform it. Use the selected business folder, membership tier and connector. Do not ask the member to type commands or choose skills.

1. Inspect the supplied files once. Identify the complete selected-tier ZIP, its download metadata and any business reports. Reuse a complete supplied kit when its publisher catalog identifies the same filename, tier, exact release, size and SHA-256 and the archive's own release manifest agrees. A few copied documents are not a kit. The publisher release number belongs to that archive; it is not the connected service's entitlement-record version.
2. Prefer that complete supplied Membership download whether or not a connector is available. When connected, use the authenticated service only to confirm that the member's entitled tier permits the selected tier. Never compare a service entitlement-record version with a publisher package release, and never replace a valid local package merely because those independent namespaces differ. An actual service refusal of the selected tier still stops installation. Use `get_kit_download` only when the matching local ZIP/catalog is missing or fails its own byte/release checks, or when the member explicitly asks for a fresh service download. Save the service descriptor and download one complete ZIP with the verified downloader. Its size, hash, tier and internal release must agree with that same service descriptor; an inconsistent service package remains refused and does not invalidate a separately valid local Membership download.
3. Follow [local helpers](references/local-helpers.md) to use the shipped `Install tools/` on the selected device. Keep downloads and complete command results in that workspace; return compact progress to the member.
4. Follow [archive installation](references/install-intake.md). For a supplied local archive, pass `approved_release` from its matching publisher catalog entry—not from the service entitlement version. Run the shipped planner and installer with the same exact archive hash, tier and release. Use fresh mode for a new workspace and companion mode when the business already has a same-tier workspace. Preserve authored files and data.
5. Read the installation receipt and `.caiman/active-guidance.json`. Resolve the guide in the actual selected folder. Run its CLIENT_START.py with the complete member request and the exact selected business root; this prepares missing foundation files and returns the applicable workflow. Installation alone does not finish onboarding.
6. Continue `AGENT_START.md`. For no-connector/files-only work, follow LOCAL FILE WORKFLOW.md to save scoped memory and create the requested product review; connected identity and historical intake remain separate. Show the actual output and one useful next step. Do not stop at downloading or copying files.

For an initialized VIP workspace, follow the kit's runtime-update workflow and preserve its backup. Unknown edited files need reconciliation; do not overwrite them. GLS+ keeps its manual Seller Central workflow and does not gain VIP scheduling.

Use normal host permission prompts when required. Do not bypass a network, filesystem or entitlement refusal. Preserve partial new files for a verified resume. Installation does not require deleting old data, and it does not create schedules or authorize account changes.
