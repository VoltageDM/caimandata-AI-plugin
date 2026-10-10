# Setup check: get the Claude app ready before the kit

Use this when a member sets up Caiman for the first time, when they come back to a setup that isn't finished, whenever setup stalls (a step keeps asking for approval, the folder looks empty, a download or a copy fails, or the member says they've been at it for a while), and when they ask you to check their Caiman setup. Setup usually stalls on the app's settings rather than on Caiman.

Offer to do the setup yourself, then do it, for example: "I can set this up for you. You'll see a few approval prompts; approve them and I'll do the rest." Do every step you have a tool for. Ask the member only for what needs their own click, one step at a time, and say where to click. Menus differ between app versions and plans: if the member doesn't see what you describe, ask what they see and go from there. Don't hand them a list of steps you could do yourself.

## 1. The business folder

- Check that you can see it. In Claude Code it's the folder Claude was started in. In the Claude app it's a folder added to the chat or to its project.
- If you can't see it, ask where it is (for example `C:\Users\<name>\Desktop\<Brand>` or `~/Documents/<Brand>`), then ask for access yourself with the app's folder-access tool; the member only approves the prompt. If that tool isn't available, ask them to add the folder to the chat (in the Claude app, usually from the + menu beside the message box).
- In a Claude project, the folder should belong to the project, so every chat in it can reach the files. If each new chat says no folder is connected, ask the member once to add the business folder to the project.
- The business folder holds the kit (`CLAUDE.md` and `CAIMAN_CURRENT.md`; on VIP, also the `VIP Machine` folder once setup has made it), or it's an empty folder chosen for a new business. A folder of reports or notes isn't it; those files can be brought in later.

## 2. Where commands run

- When the folder is on the member's computer, run the kit's scripts on that computer, with the app's command tool for it. That tool runs in Claude's workspace, a small Linux virtual machine the Claude app keeps on the computer, with Python built in. In Claude Code on Windows, commands run on Windows itself; the caiman skill's "Which Python command" says what to run there.
- **If you can reach the computer's files but there's no command tool for it, or it says "Workspace unavailable",** Claude's workspace isn't running on that computer. It's a setting on the computer. Don't tell the member it's their plan or account, or that tasks in the cloud can't run commands: they can, once the workspace runs.
  - **Windows:** if `claude-workspace-fix.txt` is already in the business folder, the member has run the fix. Read it, do what it says that you can, and go to the last step if the workspace is still down. Otherwise copy `windows-workspace-fix.cmd` from this folder into the business folder as `Fix Claude Workspace.cmd`, with your file tools (in a task in the cloud, the tool that saves files to the member's computer). Copy the file itself; don't retype it. If you can't write it there, give it to the member as a file in the chat and ask them to save it in the business folder. Then ask, in one message: "Double-click Fix Claude Workspace in your business folder and click Yes when Windows asks. Do what it says at the end (usually restart your computer), then start a new task here and say: continue." It starts the Claude VM Service, turns on Virtual Machine Platform and turns the Windows hypervisor back on when that's what blocks it, and it tells the member about anything only they can do: virtualization in the BIOS, reinstalling Claude, updating Windows or freeing space. It saves what it found and did in `claude-workspace-fix.txt`.
  - **Mac:** ask the member to quit Claude completely, open it again and start a new task. If the workspace still isn't running, ask them to check that the Mac has about 20 GB free (Apple menu, System Settings, General, Storage) and to run Anthropic's readiness check (https://claude.ai/api/desktop/darwin/universal/cowork-readiness-check/latest/redirect), which names what's missing.
  - If it still won't run, tell the member plainly what the fix file or the check said, and that installing or updating the kit, Deep Seed and the VIP Machine wait until it does. Don't run them in this session's own workspace and copy the results across: an install there can't see the member's files, so a copy back could overwrite them without saving the old versions.
- **If you have no tools for the member's computer at all,** this task isn't connected to it. Ask the member to open the Claude desktop app on the computer that has the business folder, signed in, and to continue the task from there.

## 3. The kit download

kit-sync gets the kit through the Caiman connector's `get_kit_download`. If a network refuses the Caiman download server, kit-sync says so (for example "Tunnel connection failed: 403") and names the host it tried, normally `tools.caimandata.ai`. That's a network setting, not Caiman. Give the member the two ways, in this order:

1. If the download ran in this session's own workspace rather than on their computer, the member allows that host in Claude's settings, under Capabilities, where network access for code is set. On a Team or Enterprise plan an admin changes it; if the member doesn't see the setting, that may be why. With it allowed, kit-sync can download later updates itself. Then try again. If the download ran on their computer, their own network or proxy blocks the site, and whoever manages that network can allow it.
2. Or the member downloads the kit zip from their Caiman account (the membership download) and saves it, without unzipping, in the business folder. Install from that zip. On a Mac, Safari may unzip downloads by itself (Safari Settings, General, "Open safe files after downloading"); if the member ends up with a folder instead of a zip, ask them to turn that off and download again, or to use another browser.

Don't try to reach the server another way, and don't install the kit file by file through the connector.

## 4. The skills folder

The kit's skills go in `.claude/skills/` inside the business folder. Some apps don't let Claude's tools into `.claude`. kit-sync then installs or updates everything else and names the skills it couldn't install (`skills_blocked`). When its `why` is `locked`, the app isn't the cause: another program has a skill folder open, or its permissions keep kit-sync out, so the member closes that program or fixes the permissions and kit-sync runs again (kit-sync's guide, "If a skill folder is locked"). Otherwise:

- Say plainly that only the skills are left, and that this is the one step the member does by hand.
- For this session, use the skills from the kit zip. They're the same files.
- Walk the member through the copy, one step at a time:
  1. Extract the kit zip in Downloads, not in the business folder (download it again from their Caiman account if needed). **Windows:** right-click the zip and choose Extract All. **Mac:** double-click the zip; Safari may already have unzipped it into a folder, which works too.
  2. Open the extracted `Caiman VIP - Guided Kit` folder (`Caiman GLS Plus - Guided Kit` on GLS+; on Windows it's inside a folder named after the zip). It holds a `.claude` folder with a `skills` folder inside. **Mac:** press Cmd+Shift+. (period) to show folders whose names start with a dot. **Windows:** File Explorer normally shows them.
  3. Open the business folder. If it has no `.claude` folder, copy the kit's whole `.claude` folder into it. If it has `.claude` but no `skills` inside, copy the kit's `skills` folder into the business folder's `.claude`.
  4. If the business folder already has `.claude/skills`, first rename that `skills` folder to `skills-old` (add today's date if that name is taken), then copy the kit's `skills` folder into the business folder's `.claude`. Renaming keeps everything that was there, and nothing gets replaced. If the member had made skills of their own in it, they move those folders from `skills-old` back into the new `skills` folder.
  5. If the computer asks whether to replace anything, choose Stop (or Skip) and tell Claude; never choose Replace.
  6. Delete the extracted folder from Downloads, so there isn't a second copy of the kit.
- Then ask the member to start a new chat in the project, so the skills load, and run kit-sync `status`. `current` means the copy worked. `skills-older` or `skills-missing` names skills that still aren't the kit's version. `skills-blocked` means kit-sync can't look inside `.claude` to check; then check that Claude lists the Caiman skills (for example `vip-machine` on VIP).

## 5. The Caiman connector

- `list_brands` should show the member's brand with `sp_api_authorized` and `ads_authorized` true (VIP needs both; GLS+ needs Ads). Use the slug it shows now, and `diagnose_brand` to see whether each connection works.
- If the brand is missing or a connection is off, the member connects it again in their Caiman account; then call `list_brands` again. On VIP, check first whether the business folder has a `VIP Machine`: disconnecting and reconnecting a store can give the brand a new slug, and the VIP Machine is set up for the old one. If it has one, read the kit's `TROUBLESHOOTING.md`, "The brand's slug changed", before the member reconnects. The VIP Machine's setup can start over for a new slug only early in setup, before anything in the business folder is tied to the old slug; otherwise ask the member to contact Caiman support before reconnecting. Either way, never change the VIP Machine's settings yourself.
- If no Caiman connector tools are available at all, ask the member to turn on the Caiman connector in the app's connector settings, then continue.

## 6. Approvals and the model

- In Manual approval mode, the app asks before every connector call, and setup makes many read-only calls. If prompts keep coming, or "Always allow" doesn't stop them, suggest switching the approval mode from Manual to Auto for setup (in the Claude app it's usually below the message box). Say plainly what that means: in Auto, the app no longer asks before any call, including ones that change the Amazon account. Claude still waits for the member's go before an account change (the caiman skill, section 5), but the app doesn't enforce that. So suggest switching back to Manual once setup and Deep Seed are done, before ads or listing work.
- Deep Seed is long. If the chat keeps stalling, repeating steps or losing track, suggest picking the most capable model in the model menu.

## 7. Old instructions

If the member's Claude preferences, project instructions or saved memory hold old Caiman setup steps, say they're from an earlier kit and now get in the way, and offer the exact lines to remove. Signs of the old steps: "Install my 50 VIP skills", "present voltage-setup first", "click Save skill on every card", or a `Skills/` folder of `.skill` files to install one by one. The `voltage-setup` skill itself is current; only those old steps around it are out of date. Follow the kit's `CLAUDE.md` and this plugin instead.

## 8. Say where things stand

In a few lines: the business folder, the plugin and kit versions and whether both are current (kit-sync `status`), the connector, and anything the member still has to do. Then run the guide folder's `NEXT_STEP.py --project-root "<business folder>"` and offer its next step, as the caiman skill says: Deep Seed for a new business, and otherwise whatever the plan has next.
