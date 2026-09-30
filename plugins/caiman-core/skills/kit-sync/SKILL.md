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

Add `--dry-run` to see what would change without changing anything, and `--json` for a structured result.

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
   - **A zip from the member.** If the member attached or downloaded their kit zip (for example `Caiman-VIP-Kit-v41.zip`), use it with `--zip`.
4. **Install.** Run `install`. The program checks the checksum when the server provides one. It uses the computer's proxy settings (`HTTPS_PROXY`, `NO_PROXY`).
5. **Tell the member what happened**, from the program's summary: installed or updated, which version, that the skills are in place, and what moved to `_previous-kit/`. Name each file they had changed and where their version is saved; for a skill copy or skill file with their changes, offer to bring those changes into the kit's version, or into CLIENT_RULES.md if they should last through future updates. If a renamed or `.agents/skills` copy with their changes was left in place, say that Claude may use it instead of Caiman's skill, and offer to move it aside (`move-aside`, only with their OK). On VIP, say what happened to the VIP Machine and which routines were switched off.
   - If the summary says **the VIP Machine was not updated yet** (for example because another VIP Machine step was running), run the command on its `Next:` line (`RUNTIME_UPDATE.py update`) before any other VIP Machine work, and tell the member what it reports.
6. **Carry on** with the member's request through the caiman skill, which runs `CLIENT_START.py`.

If `status` says the kit is newer than the plugin, the kit can stay; suggest the member updates the Caiman plugin. If it says `skills-missing`, run `install` again: it puts the kit's skills back and, as always, keeps the member's files (anything it moves aside is in `_previous-kit/` and named in the summary). If it says `vip-machine-older`, the kit is current but the VIP Machine isn't: run `install` again (or `RUNTIME_UPDATE.py update` from the business folder).

## When the business folder is on the member's computer

The program has to run where the business folder is. If you reach the folder through the device bridge (the host's tools for the member's computer), run it on that computer:

- If the folder's kit goes with Caiman 0.3.1 or later (its `RELEASE_MANIFEST.json` has a `core_version`), use the copy inside it: `Install tools/install_kit.py` in the business folder is the same program. Kits from before that have a different installer; don't use that one.
- Otherwise copy `scripts/kit_sync.py` to that computer (it needs no other files) and run it there.
- Or put the kit zip on that computer, unzip it into a temporary folder, and run the `Install tools/install_kit.py` inside it with `--zip` pointing at the zip.

Download the zip on whichever side can reach tools.caimandata.ai, and move the file across with the host's file tools if needed.

## Switching tiers

If the folder has the other tier's kit (for example a GLS+ folder, and the member has since moved to VIP), the program stops and asks for the member's OK. Explain that switching keeps all of their files, moves the old kit files to `_previous-kit/`, and installs the new tier's skills. With the member's go, run the install again with `--switch-tier`.

## If something goes wrong

The program explains problems in plain words and says what to do next. Pass that on to the member. Common cases:

- **The checksum doesn't match.** The download was cut off or changed on the way. Nothing in the folder was changed. Get a fresh link and try again.
- **The server can't be reached.** Check the connection. Behind a proxy, set `HTTPS_PROXY`. Or ask the member to download the kit zip from their Caiman account and use `--zip`.
- **The server refused the download.** The link expired, or this membership doesn't include that kit. Get a fresh link for this tier.
- **The kit goes with an older Caiman than this plugin.** The Caiman server doesn't have the new kits yet. Nothing was changed; keep working with the kit the folder has and try again later.
- **The folder's kit is newer than the one offered.** Nothing was changed; the folder keeps its newer kit.
- **It stopped partway.** Run the same command again; it picks up where it stopped. Anything already moved is in `_previous-kit/`.

Installing the kit never connects an Amazon account, changes anything on Amazon, or turns a routine on. On VIP it can only switch off a routine the member never approved.
