---
name: kit-sync
description: Installs or updates the member's Caiman kit (guides, scripts, templates and the membership's skills) in their business folder, keeping everything the member made. Use when a business folder has no Caiman kit yet, when its kit is older than this plugin, when skills are missing, when the membership changed tier, or when the member asks to install, repair or update their Caiman kit.
---

# Install or update the Caiman kit

The kit is the set of guides, scripts and templates the Caiman workflows run, plus the membership's skills, for the member's tier (Caiman VIP or Caiman GLS+). It lives directly in the member's business folder; its skills go in the folder's `.claude/skills/`, where Claude finds them. This skill puts it there or updates it.

**What an install never touches:** the member's own files. CLIENT_RULES.md, MEMORY.md, memory/, knowledge/, data, reports, outputs and anything else that isn't a kit file stay exactly as they are. The exceptions all move to `_previous-kit/<date>/`, and the summary names each one:

- a file of the member's with the same name as a kit file;
- a file the member added inside a part of an older kit that the current kit no longer has;
- on a switch to the other membership, the old guide's first-week progress (`FIRST_WEEK_STATE.json`), which the new guide can't read.

**What it changes:**

- Kit files are added or replaced. Before a kit file is replaced, the old copy is moved to `_previous-kit/<date>/` in the business folder. Nothing is deleted. The summary names every kit file the member had changed and where their version is saved ("You had changed PROMPT LIBRARY.md; your version is saved at ..."), and any file that was already there under a new kit file's name.
- CLAUDE.md is merged. Only the section between the `CAIMAN KIT START` and `CAIMAN KIT END` lines is replaced, even if someone edited inside it. The member's notes outside it stay, and the previous CLAUDE.md is kept in `_previous-kit/<date>/`.
- A kit from before 0.3.0 installed CLAUDE.md as a whole kit file. If it is unchanged apart from notes the member added before or after it, the old kit text is replaced by the Caiman section and the member's notes stay below it. If the member edited the old kit text itself, all of it stays and the Caiman section is added above it.
- The kit's skills are installed in `.claude/skills/<name>/`. An older copy already there is saved in `_previous-kit/<date>/skills/` first; when it wasn't an unchanged Caiman copy (the program recognizes those by content), the summary names it, because it may have the member's changes. Skills a kit-sync install put there are updated file by file like other kit files, so a skill file the member edited is saved and named too. Changes the member wants to keep across updates belong in CLIENT_RULES.md, which updates never touch.
- Other old skill copies (in `.agents/skills/`, `.caiman-tools/`, the retired `Skills/` folder, or renamed copies in `.claude/skills/`) move to `_previous-kit/<date>/` only when they are unchanged copies an earlier Caiman kit shipped. A copy the member changed stays where it is, and the summary says so.
- Parts of older kits that the current kit no longer has move to `_previous-kit/<date>/` as well, including a kit an older installer put in `.caiman/kit-versions/`.
- **VIP:** the program then updates the VIP Machine in the business folder with the kit's `RUNTIME_UPDATE.py`: its code, guides and templates, with every replaced file backed up in `VIP Machine/.caiman-runtime-updates/`. A routine stays on only when a schedule the member approved shows it (`SCHEDULE_PLAN.json`); any other routine that was on is switched off, and the summary says which. The member's records and settings otherwise stay as they are.

Tell the member in one sentence what you're about to do, then do it.

## The program

`scripts/kit_sync.py` in this skill's folder does the work. It is one standard-library Python file. It reads this plugin's version from `.claude-plugin/plugin.json` in the plugin's root folder, two levels above this skill's folder. The kit itself says which membership it is for.

```
python3 "<this skill's folder>/scripts/kit_sync.py" status  --folder "<business folder>"
python3 "<this skill's folder>/scripts/kit_sync.py" install --folder "<business folder>" --zip "<kit zip>"
python3 "<this skill's folder>/scripts/kit_sync.py" install --folder "<business folder>" --descriptor "<saved download details>"
```

Add `--dry-run` to see what would change without changing anything, and `--json` for a structured result. These commands say `python3`; when commands run directly on Windows (Claude Code on Windows), use `py -3`, as the caiman skill's "Which Python command" explains.

To move a skill copy the member changed out of the way, **only after the member agrees**:

```
python3 "<this skill's folder>/scripts/kit_sync.py" move-aside --folder "<business folder>" --path ".claude/skills/<name>"
```

It moves that copy to `_previous-kit/<date>/skills/<name>`; nothing is deleted. It won't move the kit's own copy of a skill, since Caiman needs it.

## Steps

1. **Know the business folder.** Use the folder the caiman skill settled on. If there isn't one yet, create it with the member's OK on its name and place.
2. **Check it.** Run `status`. It says whether the kit is missing, older, current, newer than the plugin, or missing skills.
3. **Get the kit**, one of two ways:
   - **A download from the Caiman server** (the usual way). Call the Caiman connector's `get_kit_download` tool with the folder's tier (`vip` or `gls-plus`). For a folder without a kit, ask for `vip`, and if the membership doesn't include it, for `gls-plus`. Save the tool's whole result to a file and pass that file with `--descriptor`. The link lasts about two minutes, so run the install straight away. If it expires, ask the tool for a new one.
   - **A zip from the member.** If the member attached or downloaded their kit zip (for example `Caiman-VIP-Kit-v47.zip`), use it with `--zip`.
4. **Install.** Run `install`. The program checks the checksum when the server provides one. It uses the computer's proxy settings (`HTTPS_PROXY`, `NO_PROXY`).
5. **Tell the member what happened**, from the program's summary: installed or updated, which version, that the skills are in place (or, if the result has `skills_blocked`, which skills weren't installed and what finishes them; see below), and what moved to `_previous-kit/`. Name each file they had changed and where their version is saved; for a skill copy or skill file with their changes, offer to bring those changes into the kit's version, or into CLIENT_RULES.md if they should last through future updates. If a renamed or `.agents/skills` copy with their changes was left in place, say that Claude may use it instead of Caiman's skill, and offer to move it aside (`move-aside`, only with their OK). On VIP, say what happened to the VIP Machine and which routines were switched off.
   - If the summary says **the VIP Machine was not updated yet** (for example because another VIP Machine step was running), run the command on its `Next:` line (`RUNTIME_UPDATE.py update`) before any other VIP Machine work, and tell the member what it reports.
6. **Carry on** through the caiman skill: with the member's request (`CLIENT_START.py`), or, when updating the kit was the whole request, with the plan's next step (`NEXT_STEP.py`).

If `status` says the kit is newer than the plugin, the kit can stay; suggest the member updates the Caiman plugin. If it says `skills-missing`, run `install` again: it puts the kit's skills back and, as always, keeps the member's files (anything it moves aside is in `_previous-kit/` and named in the summary). If it says `vip-machine-older`, the kit is current but the VIP Machine isn't: run `install` again (or `RUNTIME_UPDATE.py update` from the business folder). If it says `claude-md-older`, the kit is current but CLAUDE.md still has an earlier kit's instructions (an older kit-sync did the update): run `install` again; it replaces them and keeps the member's notes. If it says `skills-older`, the kit is current but some of its skills in `.claude/skills/` aren't the kit's version (an older copy, or one with changes): run `install` again, which puts the kit's version in place and saves the old copy, naming any that had changes. If it says `skills-blocked`, the kit is current but the app doesn't let the program look inside `.claude` to check the skills; see "If the host won't let you write in `.claude`" below. If it says `skills-locked`, the kit is current but the program can't read some skill folders, so it can't check them (`locked_skills`); see "If a skill folder is locked" below. A folder it can read but not change is checked like any other, and the advice says when one that needs updating can't be changed. If `status` lists unchanged files from the July to September 2026 kits (`earlier_kit_files`), an older kit-sync did the last update: run `install` again, and it moves them to `_previous-kit/`.

## When the business folder is on the member's computer

The program has to run where the business folder is. If you reach the folder through the device bridge (the host's tools for the member's computer), run it on that computer:

- Put the kit zip on that computer, unzip it into a temporary folder, and run the `Install tools/install_kit.py` inside it with `--zip` pointing at the zip. That copy is always as new as the kit you're installing.
- Or copy `scripts/kit_sync.py` to that computer (it needs no other files) and run it there.
- Don't update with the business folder's own `Install tools/install_kit.py`: it came with the kit already there, so it can be older than this plugin and miss newer update fixes. Kits from before 0.3.1 have a different installer altogether.

Download the zip on whichever side can reach tools.caimandata.ai, and move the file across with the host's file tools if needed.

**If there's no command tool for that computer, or it won't start** (for example "Workspace unavailable"): Claude's workspace isn't running there. Follow the caiman skill's setup check, section 2: on Windows it puts `Fix Claude Workspace.cmd` in the business folder for the member to double-click, and the install waits until the workspace runs. Don't install into this session's own workspace and copy the files across: an install there can't see the member's files, so a copy back could overwrite them (their own `CLAUDE.md`, for example) without saving the old versions.

**If the host won't let you write in `.claude`** inside the business folder: the program notices, installs or updates everything else (the VIP Machine included), and says which kit skills it couldn't install (`skills_blocked` in the result, with `why`: `hidden` when it can't even look inside `.claude`, `read-only`, or `refused` when the app refused every change the program tried there, or the first file it wrote). Tell the member that only the skills are left, use the kit's skills from the zip for this session, and walk them through the copy step in the caiman skill's setup check (`references/setup-check.md`, section 4). Then run `status` again. Skills the member copied in from the kit count as the kit's own: once the app lets the program into `.claude`, a normal install leaves them as they are, or updates them like any older kit copy.

**If a skill folder is locked** (another program has part of it open, or its permissions keep the program out): the program installs or updates everything else and names that skill (`skills_blocked` with `why`: `locked` and the folders' names). A folder it can't read or change is left as it is; one refused partway (a file open in another program on Windows, for example) may be partly updated (`partly_updated`), with the old versions of what changed in `_previous-kit/`. A locked folder that already holds the kit's files isn't named. Don't give the member the copy step for this: tell them which skill wasn't updated, ask them to close what has it open or fix the folder's permissions, then run `install` again; it finishes that skill.

## Switching tiers

If the folder has the other tier's kit (for example a GLS+ folder, and the member has since moved to VIP), the program stops and asks for the member's OK. Explain that switching keeps all of their files, moves the old kit files to `_previous-kit/`, and installs the new tier's skills. With the member's go, run the install again with `--switch-tier`.

## If something goes wrong

The program explains problems in plain words and says what to do next. Pass that on to the member. Common cases:

- **The checksum doesn't match.** The download was cut off or changed on the way. Nothing in the folder was changed. Get a fresh link and try again.
- **The network refused the Caiman download server** ("Tunnel connection failed: 403", or the program says the network refused the connection). It's a network setting, not Caiman. If the program ran in this session's own workspace, the member allows the host it names (normally `tools.caimandata.ai`) in Claude's settings, under Capabilities, where network access for code is set (on a Team or Enterprise plan, an admin does it). If it ran on the member's computer, their network or proxy blocks the site. Either way, the kit zip from their Caiman account works with `--zip`. Don't try another way around it. A proxy answering with a 5xx error means the server or the network is down or slow: try again later.
- **The server can't be reached.** Check the connection. Behind a proxy, set `HTTPS_PROXY`. Or ask the member to download the kit zip from their Caiman account and use `--zip`.
- **The server refused the download.** The link expired, or this membership doesn't include that kit. Get a fresh link for this tier.
- **The kit goes with an older Caiman than this plugin.** The Caiman server doesn't have the new kits yet. Nothing was changed; keep working with the kit the folder has and try again later.
- **The folder's kit is newer than the one offered.** Nothing was changed; the folder keeps its newer kit.
- **It stopped partway.** Run the same command again; it picks up where it stopped. Anything already moved is in `_previous-kit/`.

Installing the kit never connects an Amazon account, changes anything on Amazon, or turns a routine on. On VIP it can only switch off a routine the member never approved.
