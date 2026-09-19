---
name: kit-sync
description: Install or update a Caiman VIP or GLS+ workspace from one complete verified kit. Use when setup or an update is requested, or a required local resource is missing. Preserve existing business instructions and data.
---

# Install the Caiman kit

Explain the next local step briefly, then perform it. Use the selected business folder, membership tier and connector. Do not ask the member to type commands or choose skills.

1. Inspect the supplied files once. Identify the complete selected-tier ZIP, its download metadata and any business reports. Reuse a complete supplied kit when its exact release, size and hash are available; a few copied documents are not a kit.
2. With no connector, use the matching complete kit and publisher descriptor supplied through the member's download. If these are missing, explain this exact dependency; do not call an Amazon tool, invent a URL or switch sources. For an available authorized connection, otherwise use the authenticated service's actual `get_kit_download` tool. Save its small descriptor and download one complete ZIP with the verified downloader. Check the size, hash, tier and exact release. Stop an entitlement refusal. A release/hash mismatch requires a consistent download from the publisher; do not rename values to suppress the check.
3. Follow [local helpers](references/local-helpers.md) to use the shipped `Install tools/` on the selected device. Keep downloads and complete command results in that workspace; return compact progress to the member.
4. Follow [archive installation](references/install-intake.md). Run the shipped planner and installer with the same exact archive hash, tier and release. Use fresh mode for a new workspace and companion mode when the business already has a same-tier workspace. Preserve authored files and data.
5. Read the installation receipt and `.caiman/active-guidance.json`. Resolve the guide in the actual selected folder. Run its read-only status using `GUIDED_SETUP.py` for VIP or `GLS_GUIDED_SETUP.py` for GLS+.
6. Continue `AGENT_START.md`. For no-connector/files-only work, follow LOCAL FILE WORKFLOW.md to save scoped memory and create the requested product review; connected identity and historical intake remain separate. Show the actual output and one useful next step. Do not stop at downloading or copying files.

For an initialized VIP workspace, follow the kit's runtime-update workflow and preserve its backup. Unknown edited files need reconciliation; do not overwrite them. GLS+ keeps its manual Seller Central workflow and does not gain VIP scheduling.

Use normal host permission prompts when required. Do not bypass a network, filesystem or entitlement refusal. Preserve partial new files for a verified resume. Installation does not require deleting old data, and it does not create schedules or authorize account changes.
