#!/usr/bin/env python3
"""Install or update the Caiman workspace kit in a member's business folder.

  python3 kit_sync.py status     --folder "<business folder>"
  python3 kit_sync.py install    --folder "<business folder>" --zip "<kit zip>"
  python3 kit_sync.py install    --folder "<business folder>" --descriptor "<saved get_kit_download result>"
  python3 kit_sync.py download   --descriptor "<saved get_kit_download result>" --out "<folder>"
  python3 kit_sync.py move-aside --folder "<business folder>" --path ".claude/skills/<name>"

What it keeps: everything the member made. CLIENT_RULES.md, MEMORY.md, memory/,
knowledge/, data, reports, outputs and every other file that isn't part of the
kit stay exactly as they are.

What it replaces: kit files. Before a kit file is replaced, the old copy is moved
to _previous-kit/<date>/ inside the business folder, so nothing is deleted. The
summary names every file the member had changed and says where their version is.
CLAUDE.md is merged: only the section between the CAIMAN KIT START and CAIMAN KIT
END lines is replaced, and the member's own notes outside it stay as they are.

The membership's skills come with the kit and are installed in .claude/skills/,
where Claude finds them. An older copy of a kit skill there is saved in
_previous-kit/<date>/ first; the summary names it when the member had changed it.
Other old skill copies (.agents/skills, .caiman-tools, the retired Skills/ folder,
and renamed copies) move aside only when they are unchanged copies an earlier
Caiman release shipped. A copy with changes stays where it is, and the summary says
so; move-aside moves it later if the member wants Caiman's version instead.

On VIP, an install also brings the business's VIP Machine up to the new kit with
the kit's RUNTIME_UPDATE.py: replaced machine files are backed up first, and a
routine that is switched on without a schedule the member approved is switched off.

Downloads use this computer's HTTPS_PROXY / HTTP_PROXY / NO_PROXY settings. A
checksum is checked only when the Caiman server (or --sha256) provides one.

Standard-library Python 3.8+ in one file. The same program ships inside every kit
as "Install tools/install_kit.py", so a kit on the member's computer can update
itself.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import http.client
import json
import os
import re
import shutil
import socket
import ssl
import stat
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zipfile
from pathlib import Path

sys.dont_write_bytecode = True

PROGRAM_VERSION = '0.3.8'
TIER_NAMES = {'vip': 'Caiman VIP', 'gls-plus': 'Caiman GLS+'}
DOWNLOAD_HOST = 'tools.caimandata.ai'
DOWNLOAD_PATH_PREFIX = '/api/kit-download/'
PREVIOUS_DIR = '_previous-kit'
PLUGIN_OWN_SKILLS = ('caiman', 'kit-sync')
MAX_ZIP_BYTES = 1024 * 1024 * 1024
MAX_EXPANDED_BYTES = 2 * 1024 * 1024 * 1024
MAX_SKILL_COPY_FILES = 5000

# Top-level names a kit zip never writes into the business folder: the member's
# own records and Caiman's bookkeeping folders.
MEMBER_OWNED_TOP = {
    'client_rules.md', 'memory.md', 'memory', 'knowledge', 'caiman_current.md',
    '.caiman', '.claude', '.agents', '.git', PREVIOUS_DIR.lower(),
    'vip machine', 'gls plus workspace', 'gls_plus_config.json', 'first_week_state.json',
}
JUNK_FILES = {'.ds_store', 'thumbs.db', 'desktop.ini'}
JUNK_DIRS = {'__macosx', '__pycache__'}
# Kit parts retired in 0.3.0. Older business folders can have them even when no
# install record lists them.
RETIRED_TOP = ('Job controls', 'JOB CONTROLS.md')
# Where older kits and agents left skill copies. Caiman reads none of them now.
SKILL_COPY_FOLDERS = ('.claude/skills', '.agents/skills')
# Where the kit's own skills go (0.3.1 and later). The rest of .claude/ belongs to the member.
KIT_SKILLS = '.claude/skills'
TOOLS_CACHE = '.caiman-tools'
OLD_SKILLS_FOLDER = 'Skills'

# The business's VIP Machine and the kit's template of it.
MACHINE_DIR = 'VIP Machine'
MACHINE_TEMPLATE = 'Operating Framework/VIP Machine'
ROUTINES = (('daily_brief', 'Daily brief'), ('weekly_loop', 'Weekly review'),
            ('dreaming_loop', 'Opportunity review'), ('health_check', 'Health check'))

CLAUDE_FILE = 'CLAUDE.md'
CLAUDE_MOVED = 'CLAUDE.md as it was before this update'
BLOCK_START = ('<!-- CAIMAN KIT START: kit-sync replaces this section when the kit is updated. '
               'Keep your own notes outside it. -->')
BLOCK_END = '<!-- CAIMAN KIT END -->'
START_RE = re.compile(r'<!--\s*CAIMAN[\s_-]*KIT[\s_-]*(?:START|BEGIN)\b.*?-->', re.I | re.S)
END_RE = re.compile(r'<!--\s*CAIMAN[\s_-]*KIT[\s_-]*END\b.*?-->', re.I | re.S)
# The section older installers added to CLAUDE.md. It is replaced by the new one.
OLD_START_RE = re.compile(r'<!--\s*CAIMAN[\s_-]*CURRENT[\s_-]*GUIDE[\s_-]*BEGIN\s*-->', re.I)
OLD_END_RE = re.compile(r'<!--\s*CAIMAN[\s_-]*CURRENT[\s_-]*GUIDE[\s_-]*END\s*-->', re.I)
CURRENT_NOTE = 'CAIMAN_CURRENT.md'
GENERATED_NOTE_MARKER = '<!-- CAIMAN_GENERATED_CURRENT_GUIDE -->'

# What happened to each item that was moved into _previous-kit (the "kind" in results).
KIND_OLDER = 'older kit files'
KIND_EDITED = 'kit files you had changed'
KIND_UNRECORDED = 'files already here under a kit file name'
KIND_IN_WAY = 'items in the way of kit files'
KIND_IN_WAY_FOLDER = 'files in the way of kit folders'
KIND_RETIRED = 'kit parts no longer in the kit'
KIND_RETIRED_EDITED = 'kit parts no longer in the kit that you had changed'
KIND_SIDE = 'older side-by-side kit copies'
KIND_SKILLS = 'unchanged skill copies from earlier Caiman kits'
KIND_ASIDE = 'skill copies moved aside at your request'
KIND_SKILL_CHANGED = 'skill copies you had changed'
KIND_RETIRED_ADDED = 'files you had added to kit parts no longer in the kit'
KIND_TIER_STATE = 'first-week progress from the other membership'
# Kinds that can hold the member's own work. Each one is named on its own in the summary.
PERSONAL_KINDS = (KIND_EDITED, KIND_UNRECORDED, KIND_IN_WAY, KIND_IN_WAY_FOLDER, KIND_RETIRED_EDITED,
                  KIND_SKILL_CHANGED, KIND_RETIRED_ADDED, KIND_TIER_STATE)
# Tier-specific progress that the other membership's guide can't read. Moved aside on a tier switch.
TIER_STATE_FILES = ('FIRST_WEEK_STATE.json',)

# Fingerprints of the skill copies earlier Caiman releases shipped (Core 0.2.22 to 0.2.33,
# VIP kits 23, 26 and 33 to 37 and GLS+ kits 17, 20 and 27 to 31: every kit on file, Sep 2026). kit-sync uses them only to recognize
# an unchanged old copy, so the member isn't told a copy is theirs when it isn't. Nothing
# is ever refused or blocked because of this list.
#   SHIPPED_SKILL_TREES: SHA-256 over the sorted lines "<path>\0<file SHA-256>\n" of every
#                        file in the skill folder (system junk such as __pycache__ left out).
#   SHIPPED_SKILL_MD:    SHA-256 of SKILL.md, for a copy that holds only SKILL.md.
# BEGIN SHIPPED SKILL FINGERPRINTS
SHIPPED_SKILL_TREES = {
    'advertising-agent': ('24633902d4c854275d39385ea250cde025a43c660e7687ab13eb32bc524f3ce6', '347493f2ca2de9db499642599955a3dbc380620de7a4eb8a8f98731dd805b520', '54928396ad8324820b486c172dc8329b8f762184953f8147b6363ba09624fb17', '5e7cf7d863d3c1bbd3df77b9c1087146ebe160691cb7d17392012f63475709a8', '674433f23f875e2c01922f9be79af31258597ae0e5862d69ef0a71a79a07961e', '6aba3c530418d880ae4674b42798b57f37b056b5a71cfc104fbf48a3208b62db', 'ba64d608ade8ae13f8419512a5e36b11dbc70a6b8a1c49b81142cb397239d9d1', 'cb2627e9709756c516390f0aab6d3fd2a73db21a557f88afa3914066c73d3964',),
    'alexa-audit': ('166ff0b929c710b25d82123488801a992e5dbeb23c87673690237f1bb03c7927', 'bc4500a1bbc13cbdeb020535e5c8d620a4ed952d49af058773f3b20130d03513', 'd622cdeade54aa7082779b14f7fcbac8097a9b27fe1b85ee769b125cab373f15', 'e6ffa25622c633b7997f8d082a3136b16a79c6f16786bb79eed7336a0d0aa187',),
    'amazon-ab-testing': ('7c35f854c0af65a0624e76a700d6203eb9a459fef79190e6c50257e3fb204d06', 'b32c133bd4f04e52d7a5e0eceef2a5c63b6cf40d914ca8d613c7944689e845d0', 'f0ce265a41114da256f370dbc5551de2e92848cd298e37d7af963c538ac9985f', 'fe432a02835c9b0cbf991575e010ff519da148ff87efc85ad6c20f880957c880',),
    'amazon-listing-optimizer': ('0ebb3c6dff46896c3b091312d5e68f2882e73f76f28ebe2035c618f693827604', '8bf0d6a6538ad87bdaf152679e43e5692b41bc5d42dd2579de22b80d28a6266a', '978b3f0aaa79465d388c2baf5df21a2f39938df3c4ecd59b133f2c1e6d4ce9e8', 'a1f2f881835d321d4deda67736fd926b6f6121c2ee9e0a6c496a2c406be070a0', 'ded7dc50fe9a7124b3491607ab5c8a4a2c89715d52985fde5120efe941470a28', 'fc8ee92c9e13dbfe33329f3c7edf932c488ca8d7a372ed400e4a57015c8fc165',),
    'amazon-url-video-ad': ('08dbd4e4b17aaa8dee659ca9f78d142b517e42be926350bdc5cf1ba62cca4370',),
    'brand-defense-audit': ('20956f07f66a232d2ccc1d26b1ce3491083da01ce4164c76ce7ab0e4870e75b2', '3c188ab9abce157018d18c0696c8a5cd147373dad990708a7aa0bfeb6188f115', '3c86a025a6142e7c769d7291f289d73939bdc0895167e62e9c97806ea8ed5c0c', '531fc53efbdbfe4c5ca02878b43f60a8d5ae69aeb4d35cdbb2c29847828e3967', '81c7634f5406a2c0c7123028d9322f2d3aefb5a0a32aa0c73e96d99dd0dbf152', '9f77674f5aa4815f407815cd330a89001723b107d262f734439cbe3f35e5a270',),
    'brand-kit': ('b9d312bb80ae4aba9441ccafb73b9cce46273ba9bad77a9f26aa42c5750f86e4', 'bd9b8dcedb9104765386bb90863df40ab29c6839136dfd43937e0a080321f313', 'c3f403425811c90bc810855b5d8b467d972b4e2c7d0c86fbeecd0eb15fa5e02b', 'de7aeeaf12feb053f7f698e2b89a1f9ac884e33412a65bd7484e3296d3c16e57',),
    'bulk-bid-optimizer': ('02db1efac717847619e219356d3d7912d47cf2753accf3b643e36707c63f6088', '3da1d0800adfd9faeba2098e9fc72f9c1930e3ff3e91eeda382e2573b00273f5', '87f30436010233640037d002ed994cb912352b0f0f7af669c388268e5d1ccc01', 'd1a03e06d32f054b1937a818cded4f982df038b8b2bc11db997e810cc473bfe7',),
    'caiman': ('3f979024c08c4d9aef4f5e9b7ac6bbf22fc88c44770dfc4285b29b83082b63d3', '7cf572afdc1a0104688e8d85bedff946802a78f9f8a439910f8a926ed50f3f0f', '7f75596f2c7a18379d52debe4699afcb60ceec179b96f9e261cc1b25183b17d4', '87fb0dfcb0055971eea235e69c551387258cf813274c3759daca836dfd17976f', '9763e235573a8607a9baa9f97986c1b383f072235e9235734f09100c2581cd31', 'a33f50e848a3705885588b008857dc901ab59ad9cff65bbc1409122a0ec25cfc',),
    'canvas-design': ('c587873950149371786da437e6de987fda27d651c7d9e8c7b693e1281c44a3fd',),
    'consolidate-memory': ('f9557435a1e6263606542625dd49f32d4e7b8bcc763bafc1da9ad7c159b26981',),
    'dayparting': ('3a6b4e76d48cd888943ba5554cc23b93e801828aef795a834e71c6d4f1afffbd', '55d0f7fdc07e4dc8ea4b8abcdbc46d6eba984b4e9e73f4a6885886677f8fe51b', '8e5324c1c7400984ccfce9f9db3be6c1ce95dcb7e5cd9ddb02909d3242b313ef', 'a52cd8df7114493dc877efbaac64e3ee972cb8702637eb1e2b871347b2890403', 'efb06451c10b9a27c3dbc59a3f2f5316f00d2a8b185d2ba22c4b028af582b752',),
    'docx': ('3d0157b32bbd4177797ff70a7232164f3f21c0bcb31395574863754a51a48ef9', 'e586e82bc9933902435060f809ec31af3875daff451aaaa8720aabb0f94be7fe',),
    'higgsfield-generate': ('0e327a06eeeb5e946421d4684bdc252fc99623d989824f3d70613aa506375743', '1b877a33c0f8e19266f397cbf295b4b8a0d9222e87aa9a404b28b30e517e9098',),
    'higgsfield-marketplace-cards': ('eaf580e088ae57904e5bc96b9039959b68ec016fe984cd01c3ddd591583e0b81',),
    'higgsfield-product-photoshoot': ('01ae10dbc7cf4127aeeb517136b0e9b3cb59609610df572f8c4ec4a5ca2a760c',),
    'higgsfield-soul-id': ('69ea930556fc9f11c6893fd5c1e07e878ff850a9908ebad591d420ecdd3c889a',),
    'image-stack-engine': ('17819b3424acaf4430ce2dcbd215f67c3305ef179e31db051a911be7f6eb010c', '436195102c1dce613b6019d2b3aa7a9be1529c4ea3bbe180549ee6b2d0a902ff', '50df74eed047d77db4555d20945d9c5ad9209f9593c9c50b5e598a5fc065a622', '597392e67237dee0b46075f683071e460b84c6e8da861dacd65fe8a69e2abbfa', '8a35bf35a056e33eab95198d48cb603c61051b0f789b40aef4cf79a34192d66c', 'd40fc1850f68f8901b99c6e44e2bcb7dbf224633d9e8c76dab221b3c85256686', 'da5a09df1a2028307764398184c5d4c7c2be9d83ab077c895fd3b5bc9f274fef', 'f4b92cacb466da7982b7cce90d71c41f5cdb65185428979d6edce5dc1fa01689',),
    'intent-sbv-builder': ('0a7906460a5c9a8af25d1b8820078ae4a4dff591b3905ebbeb62176409291f82', '319d2a1704b973609bf82bc04d17e1e922503c9b161254acc286b59e086b17d8', '32f0c1f5b3c0a237316e2616f6917445a8aff548a13490598f3b68ac904ca7b7', '3e6b5b2a851b1a8f5fadb49ff411f6add6cbe8c46c20811457b664355d879275', '9e823d07e8037b51aff122369b2c97813304b480ea9b2096c078aaacf457bae1', 'f4dbfaf99c8464f36e2f285d044830a3a16135fe8a9e5cca5d532a6171bdb3d9',),
    'inventory-planning': ('00a7e508b01ea8f668806d88b357fd44be7cc4b04eb11ef46dd62543c7483f41', '1979f1e8d0f5290e2885b80ad2700e7b4fe4608c4a58b69e4baf6fdc5f3cdd0e', '2751e119e8d8b8f701e75d06787e96eea8b01216f9595ede9f16e8f277c7bcee', '881ae6c722c37eb637ed7b11ff6a2e46f389745d941a7b8c0d67f68153c8f49b', 'b29b2c259009d49551dd6c51355d4d91067d993b4068282eed40ad3e2e11a079', 'e11d9558248f29df00512a3b28739cc54d74b82b307f47d0ecd62cb5bc81fd42',),
    'keyword-research': ('1781cd4ce6600731eb9ad9a8b79d69ba4d16c5e7597e7411f7943e95a28aed51', '6cab13accffd789b4fe20e85d3ff6cd25b26cf0015173b3b4ea54aad1ffdc6fb', 'c88fa96e650a6fa3cd00fb3b1c53042a4108d278f6a82939ddd3e75d11a56258',),
    'kit-sync': ('18801356d7cb8441b34b31608b89759f7a5d2e129c27e94055c3e34b607bad55', '85d3116acf2bdaf799f9cc992555098da948301856679c9860a69580193e6c02', 'ae2ffacb018351d3809cf7df90fb389035cf279a579a6b0007998ce36190eef6', 'afe656f7131a7ea7ed8ada60c796ef6bcf2a76f43ed2abb0affa90bd44780647', 'ee08a2405cecae19d43d0bac69020c504fff7f608bd79a98e99f2b89f9096aaf', 'f6d310b642f0b851980ef60dfa71fdae8f752b855f35060636194976b8ff3106',),
    'kw-harvester-negator': ('47515f9aa024081727d4a99ed8dd8b889c278159b3f1ed57bafd549e07ea07c7', '7fdf27ed009ae878198fbdf7fa2eda33794515b2520863fa8ec0f1ceabee319a', 'a0af1d8644fee87a98107da810dff4bb847fa49a376af414382ec0252ffad0ab', 'c2fd748f724225ed663c3213e73a2bb4b8d42bbdd598717d5a17ed53038abec9',),
    'listing-autotune': ('30ee5df7a31f66a2498eabe1c09d5698b95556840cac33e0122e50b51d2e91e9', '986b0ca7d2c31fbfd5f6287faff80c7d90f67663f0ae8a41ca4b1e0ea07535fc', 'a7670dae3446eda79c25dfab06fee5396d786e844b95df2cd3e400242d5599a0', 'def16694ce40e9c1e8f55afae116a5b10d4517e0e62c3975aaad9057e6d2e1e4', 'e38b3ca48fff7b8ae6c640eb8799b0376bb193f05b93c97942bbf65020278253', 'e5d52cf81168c7212ddf910bbff1ddf4671adfcec01ca867fc9a31a2ebbc0603',),
    'margin-hunter': ('87a97dbf075a58b7a8c07413fb81d2e1010058d4b51aef3d42b16089c5f88bf8', '9d4314d80933f1de719dd4bf213669adbb3f9d6c91e05a75b2accc17334d99b6', 'c6496b0ad92caf3ee816b4997ef8d272421782bacf3075dc830011e78ab3907c',),
    'market-research': ('1b03bd563bfa2807aabe53ab7bb3a2b6d2e81467d8a12bf88be12a6d0630dcd6', '3fad7c73dd331db4c1239b1d31f93be4cdabd76dc67c9c32b10e2b13a153a176', '9cd88674b66956d96237bd94f2c57ed1ba3f597699147b2012191597dc511286', 'fc308d988e76ce6fdfb1af73955161afceefa30fa18a15c6084e7117d549d8a6',),
    'motion-graphics-promo': ('b022d310e299f100a2cb2f8422446fd8efb6b00c5e49c484186d6fbe5f6cd079',),
    'ngram-analysis': ('9d7cc38e5b06a72886f3589c3745c6cc2ed5c5434254ecc8453984207c839431', 'f2b2357fe7d201d4861d474992d58d55ed64de740ac4a1d5b44310d10607b3bb',),
    'okf-bundler': ('0a792469782685ff39f66e683f6a5245d32646f2fcd01d4ace0139f9de0ec372', '702cca73b794bf748e5cb73614723ae2619e753a7712f708592a522127e5b874',),
    'owned-audience-email': ('63477b661f835a488a4074062160aa4a8e8527894aca05a4b0d4d54953f08c01',),
    'pdf': ('f3cf190fe5d7dd3ac2382c6636c64a950aeeace461282216609c1ee324d89ef3',),
    'pixar-storyboard': ('83c825d9227a39fd289b086035d1425a4b0d37471526735412d05854ced8c8d1', '94c2bc45d56bb5115e342eab442d6a598373fe7b2e3ee1cd52cb2dae71e5a0c3', 'fa8fd3252f5470ab4733a06b8957b381788e8ae1a30b06c25588a61b1204fa5e',),
    'ppc-cheat-sheet': ('62485fada34441c4a372ccf12bd7b949c1bc1e987e559683a4516cb5dd3a0c65', '641c8b9859c99a4311d72c43d30a6a98c665731ebe93e64eb5006148b842a54b', 'aaf951721cdc1786e2c118b8f4ef69bed991937443f8ddece88d9c778268eea3', 'e248b91fc998cdc57800cda26fc15385c6ef47266865b162c1bbb95582b0803c',),
    'pptx': ('bc177d82a9a46de1e8184565c0cbcb53205e16992297f49c1b0865b100dea1d4',),
    'price-point-optimizer': ('c120d4a16c3a4bc7d8f7eda192496fd5530815fe0017750364ba553b362d1869', 'c5db28eb1913da546cbd4593f331bba22c6c14f3d0660feb751a0b0182f737d0',),
    'restock-radar': ('16de81bc4244cf5a9f8a8482e7d0522242bfe6414887d018037080660399276e', '827c2cf6d4f3427b24a2ec7c88f936c06c2a1aeb7f68a307980ebd94a2f6d9c6', '8eb328c866bf5f1974a999afb0db00737169a4b28a53fc62938b4ef1a7071ea7', 'd435f09fda022037cf2a2a5173b1b7bb1c17354ecc523c89ccc217fe0d71d092',),
    'schedule': ('717ae0e44ec4f142f869e978fa12db8db1054a8cf919b0a74260cea365e2358f', '9bd2ff5a531e940afc021a5220fdd62f214e4c6547133976175ba5636138ff5d',),
    'search-term-dashboard': ('5338a3a6cc35f4e77c95c5df4243d93a0a1429adfa1ceb3c8413e27e8118d903', 'ee2d0144294a1c942f4d17fee80da3371d21c775af8ae6c76c31a129110816c5',),
    'seedance-ugc-ads': ('469317a112c4c741900838cd14496ec7d4fbb7ec058a20599b8d1bde5d9af7ed', '48c4a7d4354c3e041b12db072dae636ae8039898e4b94125ae8394d827b7ab6a', 'c9c04367b4b65c8704f3a3d709050dcd278235ab3c68573f3df397a2fa19e7c1',),
    'self-check': ('d5a2ce1c0e42f994fd8a4c30cc5446869b9e39919e691a8c3cf9a2fd3b2b1c24',),
    'skill-creator': ('1781b2b9b7cf849b8b803c5ff30612d6771da5fdf85e90f9e9fe8e2af11f50af', 'dccf877959554ce04bb0f2490a473ed9b1c9ca3a4c150c0a1cd9062f81e74986',),
    'sku-scorecard': ('00e63f4a7c76872fb3cfad7acacbf1c9e2ecfcbe0070faed989b221040f23725', '3f29a8e1eb41053af8f0cdf59681c6653e4181875c79417733493af97b62b43e', '750f3d0247f808a8f8919c04344a3d89983e74e91f6d7dedac65d4f0f0242a2a', 'bbb59b18fb5633e69ca2891a492cdf3a5327f4e3fc0c566e68071d1f42348530',),
    'sp-campaign-builder': ('4ad988f64ac43c1985650bf1b4637b33b8af614aecf1ae455595ada95f095eb3', '6a0e64839527e7c3cc2cfe34e50b416b7661db7ee2e85b74dddc85076bff6539', '8e81f9eefe7ed104f5064923eba0f9b3a9a54b0fcb8acf2421f3b63332ecb495', 'c0fa389c0967109594778c742f8e2a579860ed37e5b60ef024b6ec6b1e990ad0', 'd06e9eb310560e1ef8677fd717803edb6097a4e29a1ae98f716352f74a8eae26', 'df6636fee84fbd04533be8b936e5a83d465b367af8e1ddc52f0533b0541d200b',),
    'sqp-ctr-cvr-benchmarker': ('71f4918a0ae8f5fc871ceb1fddd6bf9186b8ce04bb4ddb16b351b838f4fca89b', 'c41d7ab7ccef1981684e5f42c59574f2f1dca73d414b1000d7c78c95f82d1520',),
    'vip-machine': ('55a839286cb3589b1c3bb95ce77fb7ba0350017da2c6503dd801dc7c5d938b45', 'a3d0b7271fc5a725677c878712236c9eef70cdb25cf80b65f58b90fe4c907f52', 'c5e8bb4691a0ced75c9a0d096cad488ef74c11e226a0570e461d8d874ee85648',),
    'virtual-bundle-builder': ('8d635b9c03c11db88dd0babf4c75f503742e02956a4cb68f08631e1e82b033a8', '9da4daae1a5ee84bf9c2fd5c3a8d9160473dfcfd00463919339fac64658baaee',),
    'voltage-creative-pipeline': ('9c33cbe4a8bdf09ad5d4702584e0d2bf60a473c5079bd39dc92f4ec56f32e1b0', 'a15dce21f70548525bc3273b3ef9f2958250790fd1eb53f23a7fe387dfbd6bd1', 'cadae20e03975d7ebb4dd61f1f3f4ea55233b567509038f46d5ed052e29d80a5', 'f359e5ad3f44e982a2f33368d18698a18c02220557d09823bb954028afc694e2',),
    'voltage-ppc-master': ('14b9b4734a34f8f5f5817c3756312a34aa5eebdcb850e49de337c60ab8d4e538', '21e9097de0c5393a7878f18e2aefa884eb5a6e2205d252a8c7c808e85e2b86c6', '4c48b0138e5b36e94bdb40d470364e18666b68676cde53cc7fa9e63df6bb9a1b', '5b504b9d21e8dfbcb1934edfe56edb694a95c426fb809b29973bb6f3cf7026f6', '87688a14b9c39484152e1653093e2fa78384b37c73578e02b9a493bc4dd3f135', 'bd51426dfaf459c89d3f39ef3e7a20ea9debe256538f45e73cf39bcb75928261', 'ef06c6a60d504b68d800f98339463dd02f87ee7ace7b3f5b69ae48223ea9978d', 'f4aa3e229c516008ac3b286954334b8ca9bde49df990581dcb7bb667d016c339',),
    'voltage-setup': ('91184c9d8c33780b630cd641d1acc9b1696f90d107be3f31179129a0f3228a67', '9d3b3ac8d543097f7aea9d4b491352dda8c487813883632a7e9549b6f0c22bf4', 'f196aa3ecbe6e39b00d61fefdb880e6bf4f3dc1bfd5a2fc1cc81f43edd3c5dd7',),
    'voltage-weekly-dashboard': ('2f57c3fc3040308cab6a07fc4f3df8ad384d9b728aec2f42094a5a8b741f5ecf', '61713c4eba8bdfc504779806e96f6acbe2aca2c5e0bb8e8914d647d93bef9df1', '6b2b81a887115c87f12c511340cf5d1e8420fae744fa63983f36cfd95089421b', '801f7194bdc4996f61307f96f0f710595e2867b40fd88b8563959a66ee640460',),
    'weekly-amazon-audit': ('1b26f603271f50c002869148c0bc90b092ea5966dd543952023c0e88c56163da', '3b9a6c5a934405039fa9530d985b4f9471fe2147ecc56ef51d8697ab2b69bb88', '97293580a5287ca15393db48ba78b6be04ab35c5874a8640e90e53b50f6d1db6', 'b41ce95ef817e5f309fca45be04fa2dce7a998d254d715921a052292de20ff5b', 'bba529586e22e976ba7265bf7a4b6fb2bd2cd67f00c05655f3c398b8526bafeb',),
    'xlsx': ('56be7c794a8e39472fbbb5cc597375de5f20f5a7f45417c2d975496a67819bfd',),
}
SHIPPED_SKILL_MD = {
    'advertising-agent': ('05726c0b8db329ff1794a472458ed3f412a8263a817bf33711284e6aacb26a9f', '2f20aa4ed6b7faf427e972b732f7d95e7c7f927c28b4fa30b6ae9ada0ee54f4e', '6d6b57b6392a7a619dc9967f3da7e072dd7f8c0d3d359c1da670f83cf6bf81a4', 'bfebd7cc17343fe0ad690d1a685f72d15471eb2476b15f58de3b0bdc5abb359b', 'eb19fc9d0fdb05bf83a1abafa9e5fcca592f8cb495f7b6e6a609a98dac04a83c',),
    'alexa-audit': ('351cb7f2d7f9159911000b5292ed265b4dab8a24a3876844dc8e900b38d0fc49', '7877999cbbe54a2b2b45f161fa0b6082494e4e3abcd39e4668ea6b07ccd2729e', '7fcec2ab33ff7e4ca00b03db060391b76900ee0ba2c9c92d5198fcdfef29d748', 'bc1a151849b8ff3cf985bbb3f173ba554e9e41c000158cc9fe94c4babcde8211',),
    'amazon-ab-testing': ('8064c46b8509152f9826163821a80d3810cf5bae90c4239c10ca88185e91954d', 'ac4cec615ffa71ff9c81a69b9bd8bf2848634eee51e3b24b37f30fa74df3164b',),
    'amazon-listing-optimizer': ('14802a97fbc9bd75e791a684d45596b1b03aa4117062841d7fbd682373b5e110', '24377ee825038a9dd94557dc911724da5c25694a9ede4572ee8496e2464ac321', '3ac33aa7c39cb47c53963151fdc9633b8861f6de18ca1355b559565c83c15983', 'd4a221b34cdee9183eec4d33c48da48bdf230deabf5708ef51f9178f2ef48be1',),
    'amazon-url-video-ad': ('4dbcc7b4c1448e5d5b3f1eec243291b95141707687c99a295718c125d34010df',),
    'brand-defense-audit': ('84168e51d18edb054bf12c364ab8b2c052d24a54b12d8dbf1fb283f96bfa406a', 'e377435dc6b86d58a8845af5566aa08db53dea4b267a9a1522cdd5975975bc81',),
    'brand-kit': ('38189de0b938f6c4b9b04012e61552251e7b4d45935f25723386e96910a95807', 'aa163bc93a58bdb86ce741ddb006b02edeca17dd26d6ef40f4b2af6801f6eced',),
    'bulk-bid-optimizer': ('1cffa79ea401c459c6edd9b62ba9b878eb1749a2582822fbf460ec016bbca9b0', 'fd8f68045c49d3948611a577c0302d0137d57625cfd2a14a7456d2b275ec97a5',),
    'caiman': ('059293c7a61ce0b3177bd7b7da103d29a09427d73cbf6a8e442fa6b9ac79b3f8', '19b2d3df7ae7f1a72e4e3437ad7ceec559dd8351f18145a12d35e00e87e416b7', '6a03b6d41d814122057f1d23c1d29bb7b780c4d5aebe502b6ee43749b38cd772', '8e313f41aff9f3341d814c06d86483c35356510fa519acb591998d2155ca942c', 'c8967d2e8f4e5d78f22cf618aefed8a374d15c58735a5a8648b335e30bc01b19',),
    'canvas-design': ('cabbe1c20f31f20637b8ea41280034251898ff6d85eb1fa638fc64724d7d798d',),
    'consolidate-memory': ('7edd3cadeefc6461dfc487338bf751ae8f905e7c2dbf0b2eab13000d3659d132',),
    'dayparting': ('3bd2fa50829141c3a47bae58acffeb319b44b4cfdc59d29aa174a937122b4d6c', 'b595b627ee3b48aafab9106d8146a3f9afc9ce5dbe336b122e3dcc3179e287a0', 'f9a479ffb783f48b27b6cfd32322e3ff1ade25d143eb73d23fdc169a0c57dff1',),
    'docx': ('b069f12e6adfd28dc6d9eae739c925f82b378006cc2e060060cce53fe018daf5', 'b8100ad9ca151751fce52944a30a60f983f8c66c282e5a7542f731a80f9e0bbc',),
    'higgsfield-generate': ('c475e10410a0cff876d97d93ae4b7feea7dcd5fbb1fdadf693920260d707ee1e',),
    'higgsfield-marketplace-cards': ('897d51d8f907e717568c798c0ff326b55c9963554e33be5a8af39c25c36bb6a0',),
    'higgsfield-product-photoshoot': ('c87eb136b2e7b634766521c0df67c9cfd8971f61b332887578f87cb19f54149c',),
    'higgsfield-soul-id': ('3cf005fed0b6895739be6cacafa263b23667120cc94d05e62418684c0ec90b52',),
    'image-stack-engine': ('5264224d6f07ba109d8e5ae44e763523d83ac2e417cf2eabfcf94f5216bd9cb7', '61b1b073de4aab62811daa964ce2243139ced3ed1ef6ae3c6dbd193c6aa5749e', '6feea30715f26e89bcd2506dce22416504c79f1dcb09354e9248e240926e4d02', '8e811c6114a8852349004bcd3fe1b79d582fb0ea6a444cdfd8ab821d81bc517e', 'a98bff5cf832015843b428611115ee47df54b6f2854998c7bee5ae79ea965b8e', 'f7f95eaebc621984674a7099e69c28773ab47ad48ecc5cbca1d5ceabd5d5302e',),
    'intent-sbv-builder': ('15a3fbc7c0f49a419df26c4de4eec6742cbfc6b627234912fd56989a46d3aa37', '21a9933cb04af1588f1d800039a6bf8acbd71a757511e59c0947cb7d74bbbb0f', 'd0241f17e099899fc4ad94c323edab95f94c11e3923bd8a7a01df2a6af9eb2da', 'f682a5aefb63022f956afbf824f9574cf6caa310d9f568bad0f934e7ee4cbd08',),
    'inventory-planning': ('41da1b16c71ee468f4cceae59058ef97b6c56daaf62019290a181275e9f4fabb', '9ceb970df95d691677df1d93b7431ce33b16fd05e09d956b0ad7d81998f2bb5f', 'cc3c645f92bbc5460176967f39fe624fe80d6d2cb6cd6de09e2cd1ca29d97104', 'e1392f317d8708e6ba2f57594badd52538a405ff18a62ad1ec8af30d3b46cf4f',),
    'keyword-research': ('09c331cf7b52437b491f3e8e6dbcac114a8155178f3ee11918d82c2adf50b4e1', '1f7a64483fa341adb502296da81ddbf3c59ca7d4f11d16af4255a29338f5dbf8', '798c46678815fc0f604668bf06bded0d1f6f94d0a08978e5612bec42b7370276',),
    'kit-sync': ('01a244fc2c4ab7cca81549b38d3e872b5de765548167c7c2405920337e8cef76', '195fd37765064e7f53f369e88f82f04b6748e0dc1fb121055127dfd198cd5c31', '3a7714cd536c24c30bfbe29e68f3470868ed4304107fcd2ccaf801b751c7089c',),
    'kw-harvester-negator': ('1548e522efa3324c89fb69d902d52912c5de012b8177be5706691fb875095620', 'c2ba22eca54e8770992249daf2ebe983b89104db9e04963965817e4c41f601e8',),
    'listing-autotune': ('52ebbbd771dc544bd7818a47ebb2e5b8813d1e21949871f02389c8a51e6db4bf', '97b0f857ce2bee2cff537a387f5ac1830dfbaeaaa578fb06c009b547b707cbb5', 'a59aca29990d26d2254c29d366b6b0a7831a7f094a64ee7a6a683df1fab1bab3', 'd7e775351e97690a3e5d3974a26efa84e9e8a95f8b493fa5bbf07990523005de',),
    'margin-hunter': ('5577f4bc5bf7c4a6f6c29367bc102e007dfb42bef14f9ec9b11ed453681b065a',),
    'market-research': ('508bc6c0338119ff58bb5da21630dffdcde74f6e48ebd38ab5f02e429ea70d2e', 'e43b02f4e948b19e6badac925f31b6c9713bf2a796ad4b0072890dab09207f56',),
    'motion-graphics-promo': ('2f6fc2449ec0984b3fc8603e147a8fef20c104dc76cd2d0affed16eedaa53f87',),
    'ngram-analysis': ('e5fd3a476d4a1854145679b128be989750e2e25389df8a97b664e1fede54a7a0', 'f8ebd0ed3102f28d2873afe3e2220f9f75ee9767266c899e618b399f95dd30a6',),
    'okf-bundler': ('0e2182de4235f04a5932fdd397ca6cb5737e10206401bdba206751ced225863f', 'e8ba892f5c996bb5936306b5cf2ae3b9c24fc62dc0df038355281cf2942377c8',),
    'owned-audience-email': ('dcaa347fcb9401391ce5dcd97fbbeab13d8812012bc715e65e6871aada1a90c2',),
    'pdf': ('9f78b8359fbd4943ad260a7a1e436e5a96503406d6c34e99f69223d647d85b9c',),
    'pixar-storyboard': ('57bf8dc75d601d62399de591eb15ec4990c6f66701f329a3948648c383375384', 'da7a86698b80ecd1934c5da14ed3e2004f3976193ec90388750d8932f14c7976',),
    'ppc-cheat-sheet': ('2aedfe0a557a1e7eea299e8027aa71df7c33a52088520a12f6996084cf9a8ff8', 'efd7442d8339794d2011704b874a40e3757335c060d9a98549dfbef63dfde8f7',),
    'pptx': ('4a2b85ac99c6f2fba3fd89949136dc750978ea7570a4d3fe684e4511ec6ffed5',),
    'price-point-optimizer': ('5bba685b23d6b9d0f217de6c04e890c4d7f0d96f08e96b7e5c79ff58727ed488', 'd9b0eeb2fdb42f22b1c920840d5bed86edba19476474c64193ec65ceaab27843',),
    'restock-radar': ('0f2d0ca1d2735fa66479904818740945aee696385a132ca2fe049f43e078a2ce', 'a8dc14f1d82e6559b294e62ceb454cbf02a113009c915512e175af30c77e1d72', 'ab46466550b107a240971c5d1b759d6ffac8435ad53bec3522e7c77effe2a88c',),
    'schedule': ('1645577a02c7907052bd875c5b3650e384ae9505956267e5652f700a94507c07', '6c7fa470f64eb5045ba0a9b2ff27e3d6b836994e9138247ad001bea57705de15',),
    'search-term-dashboard': ('6c305682b0a7924e7e990c2c65b50e8623d034d0b0158c463dd3018389f4257f', '9a3087fd0d7a98602889ff42e51bb183b41bd616c18249379732c1fbf7cdfcbd',),
    'seedance-ugc-ads': ('518ae79cffbf405ef797f70509300a5f5f147c5e4762927c3aae513f0ae8be9e', '5e036df138194342ab5c70800004d6b500375f484aaa190e6f467d1eb6ba39ff',),
    'self-check': ('60ab1eb9496e0fa9ed4f368878e85be1d54a77152406b7d825d5e9fe3d8fe72b',),
    'skill-creator': ('96fef0082a8cfd00077e3517809ff6522a4ea21b8d779cf6c6497aeb84e51e8f', 'dcd4803e61e913e6fc27294184cd3a71f09f5e924ff20c8a9a20173e7b3c2bcf',),
    'sku-scorecard': ('ba68c739d6c9474cdf67cb6a224ae2c6540983b0551d77b2d6dfcd1fa70cbf68', 'c1c461f9739f1f9415dbbf26023905982daad6ff2b3adfb9a27554b484a4c1b6',),
    'sp-campaign-builder': ('01b9bbbc90a9fd723c7071b4ee90b43ac41c7e0cb99b7b47dc16c8d720c2380c', '6e032786431bc2d67d5d886bfe4763736e7d7ebf449bdb0208d13de0f7fb8371', '944e2700ee7722a26396a341b1a3eec1eafa8fc0ec3b26152c482d5c2b4df79c', 'dbc8af37f0901042365cad0c21480fc989b7a8d444a6e7d7d4eaaac0b7fb053a',),
    'sqp-ctr-cvr-benchmarker': ('97bc31d1c1ca08763fba578c556c78268d0bb6dd5ec41d01cd744953a2a462b8', 'b2f9be9319df0609e3ac6a087e39222a778ac941707f2f29b22ab6bcc77d17b7',),
    'vip-machine': ('3102ffbae2b9af32ee7ffc8c907b657417e56c80de424151911dd6e2cda7844a', '59d1232029936c6a8f5501e00a85fc77ab3827ca64a5f26386dd2ad296f9aa7a', '7261c7f07919b4dbfaae45c7637af06fc3d7ea6b17ea0b64a458e104f410cb9d',),
    'virtual-bundle-builder': ('22be6d7b6d586deb2365e2439a115d53eeaa502a0debb2338dfdc8b8b298dfc0', '8a3b572e61f222dcd2c0a3c37aaef500ff4202ce053c42cfd44d6410322794d3',),
    'voltage-creative-pipeline': ('668c065ef7864922090463f395c451b4ee90ba84327d20c167da7b456759eb53', '7eedf8f03da16cbcf473fdb4ac2218ce5e7a84081cade584fa6f108591d9bc6c',),
    'voltage-ppc-master': ('142da91bbc962db76e645a4a4c779b68e85d51089184cd13c3e8fd1114afb9b0', '1e327794553170868445e1d7d8018d9b567c26555d6bd82f370ebfbe45718ee9', '2c4834043f2893135b138e14052e09c8f651ed371cff1e02e058fe3e8852578f', '40852fddbd761a4dd8f59b7420bc1adf857ab16ef7632f9f0ef9f35689e63d0f', 'e1d678354568fb6195946729ae9d904723e958d302053626a93e2009fee8f2d3',),
    'voltage-setup': ('01c02001c54b2cd4986592f5dabff668cf97e97809e7ab0e2f20e0925dc66301', '22e783f7e812098cc0df3e775c95b7a94eae71599a7ec1d3b660edd9e7198542', 'd2d94fc90bb5aef13d77580adf6b3ae88a416931ff25406c9139677409031020',),
    'voltage-weekly-dashboard': ('96becaf0db2a0bb1b7148da553e0102975dbf420ead39cf0304a4222dc422e0c', 'b5df8ed723218231b464eb172f8ba9d811871c9230fe88442aa672dedb581e81', 'dfac2ac7d365f975f895e1dd511ffc422b8b29e45d8b257992652470a8e9f304', 'ea2381b44b7d826be666540235cba63bb952f15783fb14f185217404cf8977d4',),
    'weekly-amazon-audit': ('2ee96963a0c633f6752f28bf51bbaf1913c0bc05d73d26092d3ff461594ca1af', 'a03ee440c63f13391a067c25a708d16d9c2a0f432672940761e6bd4a2b9f5afc', 'e034f59b4f7da9ff930dc0dd4a8e592c682073532d34b11e17ef1c42d2bcfa1b',),
    'xlsx': ('db910caebd31fd6871876f098ec940dc0c3008855219615139faad9ac360241a',),
}
# END SHIPPED SKILL FINGERPRINTS

# CLAUDE.md as earlier kits shipped it (a whole kit file then). An unchanged one is old kit text, not the
# member's notes, even when no install record says so (for example a kit someone unzipped by hand).
SHIPPED_CLAUDE_MD = (
    '325bbbb160784b71f8848f7ab43dc28b28b8961053eac2a96b726b813ab53f8d',
    '38b2458cee494e4ab9dd5e103046def0b773788e66bcd917ce5925d7e82d6b47',
    '8ce99ae37d5770a9fd28236062cf7a142d208b07bd6adc78a38af498e7e0d3e4',
    '8d92178126040829f258a7ff6f0190be94ff728f116af749497fb712cbf302fc',
    'ad4ec00423e050d4d881e99f2b9142ac5bae3331506fd2a3d495825c584a412b',
    'e932239cf85c5260bd42e20306c59a7cb9eae84bb778b1f45219ffed4c2197ab',
    'ef47b26242dcd6598063b5604884232cd7e13925c2b9a6285444aac46ec21380',
)
# Files of kit parts that are no longer shipped (RETIRED_TOP), as earlier kits shipped them.
SHIPPED_RETIRED_FILES = {
    'JOB CONTROLS.md': ('84876dde5ff91beda8064112709bd5cd3fd5ae3eeed0679c6ad0f7f2baae46b8', 'd1637e1b64bcc5ec4bf518defaaddb319070c510e5c784372d7790fd5187109c',),
    'Job controls/amazon_policy.py': ('95f02b224eff688a9121a4706298d9e48adbf158c713593a944acb9521ef96a1',),
    'Job controls/job_engine.py': ('6cc258a884670981b0d878764d5542b086b7481c06552df5d3a8abc01202d4e3',),
    'Job controls/portable-bundle.json': ('e9e18f44daf0e1b3dce56387067a4e88b24dcce1876d3d0f65714bba62272a6e',),
    'Job controls/portable-policy.json': ('8840a55f1b936470d0fb3c10392338a5198608088f11c7b064b5fbc6996d72b9',),
    'Job controls/portable_context.py': ('5251b002afcc569a660c8b68ceba6ef853e55eb81b1f2230618ce83374f4f886',),
    'Job controls/portable_guard.py': ('96ebfb0b709ed0aa1cb973ef58b9a3e87b4ebfb6391c737a8d8fdf8eb7911d8a',),
}


class KitSyncError(Exception):
    """A problem, explained in plain language, with what to do next."""
    exit_code = 1


class NeedsConfirmation(KitSyncError):
    """The member has to agree before this install can go ahead."""
    exit_code = 3


# ---------------------------------------------------------------- small helpers

def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path):
    """Parsed JSON from a file, or None when it is missing or unreadable."""
    try:
        with open(path, 'r', encoding='utf-8-sig') as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return None


def as_dict(value):
    return value if isinstance(value, dict) else {}


def json_bytes(value):
    return (json.dumps(value, indent=2, ensure_ascii=False) + '\n').encode('utf-8')


def norm_tier(value):
    """'vip' or 'gls-plus' from the spellings kits and servers use, else None."""
    if not isinstance(value, str):
        return None
    key = re.sub(r'[\s_]+', '-', value.strip().lower())
    return {'vip': 'vip', 'gls-plus': 'gls-plus', 'glsplus': 'gls-plus', 'gls+': 'gls-plus'}.get(key)


def tier_name(tier):
    return TIER_NAMES.get(tier, 'Caiman')


def parse_version(value):
    if isinstance(value, str):
        match = re.fullmatch(r'\s*v?(\d+)\.(\d+)(?:\.(\d+))?\s*', value)
        if match:
            return tuple(int(part or 0) for part in match.groups())
    return None


def now_utc():
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def stamp():
    return dt.datetime.now().strftime('%Y%m%d-%H%M%S')


def clean_rel(name):
    """A safe relative path using '/' separators, or None when the path is unsafe."""
    if not isinstance(name, str):
        return None
    name = name.replace('\\', '/')
    if not name or name.startswith('/') or '\x00' in name:
        return None
    parts = [part for part in name.split('/') if part not in ('', '.')]
    if not parts or '..' in parts or re.match(r'^[A-Za-z]:', parts[0]):
        return None
    if any(ord(ch) < 32 for part in parts for ch in part):
        return None
    return '/'.join(parts)


def is_junk(rel):
    parts = rel.split('/')
    return (any(part.lower() in JUNK_DIRS for part in parts[:-1])
            or parts[-1].lower() in JUNK_FILES or parts[-1].lower() in JUNK_DIRS or parts[-1].endswith('.pyc'))


def member_owned(rel):
    if rel.startswith(KIT_SKILLS + '/'):
        return False                  # the kit's skills live here; the rest of .claude/ is the member's
    return rel.split('/')[0].lower() in MEMBER_OWNED_TOP


def kit_skill_dirs(files):
    """Names of the skills a kit (relative path -> data) installs in .claude/skills/."""
    lead = KIT_SKILLS + '/'
    return sorted({rel[len(lead):].split('/', 1)[0] for rel in files if rel.startswith(lead) and rel.count('/') >= 3})


def exists(path):
    return path.exists() or path.is_symlink()


def unique_path(path):
    """path itself if it is free, otherwise 'name (2).ext', 'name (3).ext', ..."""
    if not exists(path):
        return path
    counter = 2
    while True:
        candidate = path.with_name('{} ({}){}'.format(path.stem, counter, path.suffix))
        if not exists(candidate):
            return candidate
        counter += 1


def write_new(path, data):
    """Create a new file. Never overwrites: some synced folders refuse overwrites."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'xb') as handle:
        handle.write(data)


def put_bookkeeping(path, data, history):
    """Write a small .caiman bookkeeping file. An older copy is renamed into history first."""
    if exists(path):
        try:
            if path.read_bytes() == data:
                return False
        except OSError:
            pass
        history.mkdir(parents=True, exist_ok=True)
        os.rename(path, unique_path(history / '{}-{}{}'.format(path.stem, stamp(), path.suffix)))
    write_new(path, data)
    return True


def frontmatter_name(skill_md):
    try:
        with open(skill_md, 'r', encoding='utf-8-sig', errors='replace') as handle:
            head = handle.read(8192)
    except OSError:
        return None
    head = head.replace('\r\n', '\n')
    if not head.startswith('---\n'):
        return None
    block = head[4:].split('\n---', 1)[0]
    match = re.search(r'^name:\s*["\']?([^"\'\n]+?)["\']?\s*$', block, re.M)
    return match.group(1).strip() if match else None


def plural(count, word, many=None):
    return '{} {}'.format(count, word if count == 1 else (many or word + 's'))


def listing(items, limit=6):
    items = list(items)
    shown = ', '.join(items[:limit])
    return shown + (', and {} more'.format(len(items) - limit) if len(items) > limit else '')


def names_in_words(names):
    names = list(names)
    if len(names) <= 1:
        return ''.join(names)
    return ', '.join(names[:-1]) + ' and ' + names[-1]


# ---------------------------------------------------------------- old skill copies

def tree_digest(entries):
    """SHA-256 over the sorted '<path>\\0<file SHA-256>\\n' lines of a skill copy."""
    digest = hashlib.sha256()
    for rel, value in sorted(entries):
        digest.update(rel.encode('utf-8') + b'\0' + value.encode('ascii') + b'\n')
    return digest.hexdigest()


def skill_folder_entries(folder):
    """(relative path, SHA-256) for every file in a skill folder, or None if it holds links or is huge."""
    entries = []
    for path in sorted(folder.rglob('*')):
        rel = path.relative_to(folder).as_posix()
        if is_junk(rel):
            continue
        if path.is_symlink():
            return None
        if path.is_file():
            entries.append((rel, sha256_file(path)))
            if len(entries) > MAX_SKILL_COPY_FILES:
                return None
    return entries


def skill_zip_entries(path):
    """(relative path, SHA-256) for every file in a packed .skill archive, without its top folder."""
    with zipfile.ZipFile(path) as archive:
        infos = [info for info in archive.infolist() if not info.is_dir()]
        if len(infos) > MAX_SKILL_COPY_FILES:
            return None
        rels = [clean_rel(info.filename) for info in infos]
        if any(rel is None for rel in rels):
            return None
        tops = {rel.split('/', 1)[0] for rel in rels}
        strip = len(tops) == 1 and all('/' in rel for rel in rels)
        entries = []
        for info, rel in zip(infos, rels):
            sub = rel.split('/', 1)[1] if strip else rel
            if not is_junk(sub):
                entries.append((sub, sha256_bytes(archive.read(info))))
        return entries


def copy_state(path, names, current=None):
    """'unchanged' when path is exactly a copy an earlier Caiman release (or this plugin, through current:
    name -> SHA-256 values) shipped for one of names; 'link' for a link; otherwise 'changed' (it may hold the
    member's own edits)."""
    if path.is_symlink():
        return 'link'
    try:
        if path.is_dir():
            entries = skill_folder_entries(path)
        elif path.is_file() and path.name.endswith('.skill'):
            entries = skill_zip_entries(path)
        else:
            return 'changed'
    except (OSError, zipfile.BadZipFile, ValueError, RuntimeError):
        return 'changed'
    if not entries:
        return 'changed'
    tree = tree_digest(entries)
    for name in names:
        if tree in SHIPPED_SKILL_TREES.get(name, ()) or tree in (current(name) if current else ()):
            return 'unchanged'
        if len(entries) == 1 and entries[0][0] == 'SKILL.md' and entries[0][1] in SHIPPED_SKILL_MD.get(name, ()):
            return 'unchanged'
    return 'changed'


def plugin_skill_trees(plugin_root):
    """name -> fingerprint of this plugin's own copy of that skill, worked out when first asked for."""
    found = {}

    def lookup(name):
        if name not in found:
            folder = Path(plugin_root) / 'skills' / name if plugin_root else None
            try:
                entries = skill_folder_entries(folder) if folder is not None and folder.is_dir() else None
            except OSError:
                entries = None
            found[name] = (tree_digest(entries),) if entries else ()
        return found[name]
    return lookup


def find_skill_copies(root, plugin_names, plugin_root=None, kit_dirs=()):
    """Old skill copies: which ones to move aside (unchanged copies an earlier Caiman release or this plugin
    shipped) and which ones stay because they have changes. The kit's own skill folders in .claude/skills
    (kit_dirs) are left to the install. Nothing here changes the folder."""
    plugin_names = set(plugin_names)
    kit_dirs = set(kit_dirs)
    current = plugin_skill_trees(plugin_root)
    watch = plugin_names | set(SHIPPED_SKILL_TREES)
    move, kept = [], []
    for base in SKILL_COPY_FOLDERS:
        folder = root / base
        if folder.is_symlink() or not folder.is_dir():
            continue
        try:
            children = sorted(folder.iterdir(), key=lambda p: p.name)
        except OSError:
            continue
        for child in children:
            if is_junk(child.name):
                continue
            rel = base + '/' + child.name
            if base == KIT_SKILLS and child.name in kit_dirs:
                continue                              # the kit's own skill folder: the install handles it
            names = {child.name[:-6] if child.name.endswith('.skill') else child.name}
            if child.is_dir() and not child.is_symlink():
                named = frontmatter_name(child / 'SKILL.md')
                if named:
                    names.add(named)
            if not names & watch:
                continue                              # the member's own skill: not Caiman's business
            state = copy_state(child, names, current)
            if state == 'unchanged':
                move.append({'path': rel, 'dest': 'skills/' + child.name})
            elif names & plugin_names:
                kept.append({'path': rel, 'name': sorted(names & plugin_names)[0], 'state': state,
                             'shadows_plugin_skill': True})
    move_tools, kept_tools = tools_cache_copies(root)
    return {'move': move + move_tools, 'kept': kept + kept_tools}


def tools_cache_copies(root):
    """.caiman-tools/<skill>/<id>/ holds copies the Sep 28 kit unpacked. Unchanged ones move aside
    (the whole folder when everything in it is unchanged); changed or unknown items stay."""
    tools = root / TOOLS_CACHE
    if not exists(tools):
        return [], []
    if tools.is_symlink() or not tools.is_dir():
        return [], [{'path': TOOLS_CACHE, 'name': None, 'state': 'link' if tools.is_symlink() else 'unrecognized',
                     'shadows_plugin_skill': False}]
    move, kept = [], []
    try:
        name_dirs = sorted(tools.iterdir(), key=lambda p: p.name)
    except OSError:
        return [], []
    for name_dir in name_dirs:
        if is_junk(name_dir.name):
            continue
        name_rel = TOOLS_CACHE + '/' + name_dir.name
        if name_dir.is_symlink() or not name_dir.is_dir():
            kept.append({'path': name_rel, 'name': None, 'state': 'unrecognized', 'shadows_plugin_skill': False})
            continue
        subs = [p for p in sorted(name_dir.iterdir(), key=lambda p: p.name) if not is_junk(p.name)]
        unchanged, other = [], []
        for sub in subs:
            sub_rel = name_rel + '/' + sub.name
            if sub.is_dir() and not sub.is_symlink() and copy_state(sub, {name_dir.name}) == 'unchanged':
                unchanged.append(sub_rel)
            else:
                state = 'changed' if (sub.is_dir() and (sub / 'SKILL.md').is_file()) else 'unrecognized'
                other.append({'path': sub_rel, 'name': name_dir.name, 'state': state, 'shadows_plugin_skill': False})
        if other:
            move += [{'path': rel, 'dest': 'caiman-tools/' + rel[len(TOOLS_CACHE) + 1:]} for rel in unchanged]
            kept += other
        else:
            move.append({'path': name_rel, 'dest': 'caiman-tools/' + name_dir.name})
    if not kept:
        return [{'path': TOOLS_CACHE, 'dest': 'caiman-tools'}], []
    return move, kept


def old_skills_folder(root, retire, kit_files, left):
    """Packed (.skill) and unpacked copies in the retired Skills/ folder that no install record lists.
    Unchanged copies Caiman shipped are retired; anything else stays and is noted in left."""
    folder = root / OLD_SKILLS_FOLDER
    if folder.is_symlink() or not folder.is_dir():
        return []
    covered = set(retire)
    found = []
    for child in sorted(folder.iterdir(), key=lambda p: p.name):
        rel = OLD_SKILLS_FOLDER + '/' + child.name
        if is_junk(child.name) or rel in kit_files or rel in covered:
            continue
        if child.is_dir() and not child.is_symlink():
            inside = [p.relative_to(root).as_posix() for p in child.rglob('*') if p.is_file() or p.is_symlink()]
            if inside and all(item in covered or is_junk(item) for item in inside):
                continue                              # already retired through an install record
            names = {child.name}
        elif child.is_file() and child.name.endswith('.skill'):
            names = {child.name[:-6]}
        else:
            continue                                  # not a skill copy (a member note, for example)
        if copy_state(child, names) == 'unchanged':
            found.append(rel)
        else:
            left.append({'path': rel, 'why': 'Skills folder'})
    return found


# ---------------------------------------------------------------- plugin and kit facts

def find_plugin(explicit_root=None):
    """The Caiman plugin's facts (version, skill names, and the tier when tier.json names one), or None when
    this program isn't running from the plugin. The member plugin names no tier: the membership's kit decides."""
    here = Path(__file__).resolve().parent
    candidates = []
    if explicit_root:
        candidates.append(Path(explicit_root).expanduser())
    candidates.append(here.parent.parent.parent)          # <plugin>/skills/kit-sync/scripts/
    if os.environ.get('CLAUDE_PLUGIN_ROOT'):
        candidates.append(Path(os.environ['CLAUDE_PLUGIN_ROOT']))
    candidates.append(here)                              # tier.json copied next to this file
    for root in candidates:
        data = as_dict(read_json(root / 'tier.json'))
        manifest = as_dict(read_json(root / '.claude-plugin' / 'plugin.json'))
        tier = norm_tier(data.get('tier'))
        if not tier and manifest.get('name') != 'caiman-core':
            continue
        skills_dir = root / 'skills'
        names = []
        if skills_dir.is_dir():
            names = sorted(p.name for p in skills_dir.iterdir() if (p / 'SKILL.md').is_file())
        version = data.get('version') or manifest.get('version')
        return {'root': str(root), 'tier': tier, 'version': version if isinstance(version, str) else None,
                'kit_folder': data.get('kit_folder'), 'kit_zip': data.get('kit_zip'), 'skills': names}
    if explicit_root:
        raise KitSyncError('There is no Caiman plugin in {} (no .claude-plugin/plugin.json named caiman-core). '
                           'Point --plugin-root at the Caiman plugin folder, or leave it out.'.format(explicit_root))
    return None


def _kit_facts(folder, pointer=None):
    manifest = as_dict(read_json(folder / 'RELEASE_MANIFEST.json'))
    entitlements = as_dict(read_json(folder / 'ENTITLEMENTS.json'))
    has_start = (folder / 'CLIENT_START.py').is_file()
    tier = (norm_tier(manifest.get('kit')) or norm_tier(manifest.get('tier'))
            or norm_tier(entitlements.get('plan_tier')) or norm_tier(as_dict(pointer).get('tier')))
    if tier is None and has_start:
        if (folder / 'GUIDED_SETUP.py').is_file():
            tier = 'vip'
        elif (folder / 'GLS_GUIDED_SETUP.py').is_file():
            tier = 'gls-plus'
    version = manifest.get('version') if isinstance(manifest.get('version'), str) else None
    release = manifest.get('release') if isinstance(manifest.get('release'), str) else None
    return bool(manifest or entitlements or has_start), tier, version, release


def core_version_of(manifest):
    """The Caiman plugin version a kit goes with (0.3.0 and later record it), or None."""
    value = manifest.get('core_version') or as_dict(manifest.get('plugin')).get('version')
    return value if isinstance(value, str) and parse_version(value) else None


def side_by_side_kit(root, pointer):
    """A kit an older installer put beside the business files (.caiman/kit-versions/<name>), or None."""
    candidates = []
    relative = pointer.get('guidance_relative')
    if isinstance(relative, str) and relative not in ('', '.'):
        rel = clean_rel(relative)
        if rel:
            candidates.append(rel)
    versions = root / '.caiman' / 'kit-versions'
    if versions.is_dir() and not versions.is_symlink():
        candidates += ['.caiman/kit-versions/' + p.name for p in sorted(versions.iterdir(), key=lambda p: p.name)
                       if p.is_dir() and not p.is_symlink()]
    for rel in dict.fromkeys(candidates):
        folder = root / rel
        if folder.is_symlink() or not folder.is_dir():
            continue
        present, tier, version, release = _kit_facts(folder, pointer)
        if present:
            return {'guide': rel, 'tier': tier, 'version': version, 'release': release}
    return None


def installed_kit(root):
    """What kit, if any, is already in the business folder."""
    pointer = as_dict(read_json(root / '.caiman' / 'active-guidance.json'))
    present, tier, version, release = _kit_facts(root, pointer)
    result = {'present': present, 'tier': tier, 'version': version, 'release': release,
              'core_version': core_version_of(as_dict(read_json(root / 'RELEASE_MANIFEST.json'))) if present else None,
              'layout': 'in-folder' if present else None, 'guide': '.' if present else None}
    named = pointer.get('guidance_relative')
    if not present or (isinstance(named, str) and named not in ('', '.')):
        side = side_by_side_kit(root, pointer)
        if side:
            result.update(present=True, tier=side['tier'], version=side['version'], release=side['release'],
                          layout='side-by-side', guide=side['guide'])
    return result


class Kit:
    def __init__(self, source, files, tier, version, release, skills, notes, core_version=None, executables=()):
        self.source = source
        self.files = files            # relative path -> bytes
        self.tier = tier
        self.version = version
        self.release = release
        self.skills = skills
        self.notes = notes
        self.core_version = core_version
        self.executables = set(executables)    # kit files that ship executable

    @property
    def label(self):
        number = self.version
        if not number and self.release:
            match = re.search(r'-v(\d+)$', self.release)      # older kits name only a release, e.g. ...-vip-v37
            number = match.group(1) if match else None
        return '{} kit {}'.format(tier_name(self.tier), number or self.release or '(no version)')


def read_kit_zip(zip_path, hint_folder=None):
    path = Path(zip_path).expanduser()
    if not path.is_file():
        raise KitSyncError("I couldn't find the kit zip at {}. Check the file name and where it was saved.".format(path))
    try:
        if path.stat().st_size > MAX_ZIP_BYTES:
            raise KitSyncError('{} is far larger than a Caiman kit, so I stopped. Use the kit zip from your '
                               'Caiman membership downloads.'.format(path.name))
        with zipfile.ZipFile(path) as archive:
            return _read_kit(archive, path, hint_folder)
    except zipfile.BadZipFile:
        raise KitSyncError("{} isn't a complete zip file. It may still be downloading or be damaged. "
                           "Download it again, then retry.".format(path.name)) from None
    except OSError as error:
        raise KitSyncError("I couldn't read {} ({}). If it's in a cloud-synced folder, make it available "
                           "offline or copy it somewhere local first.".format(path.name, error.strerror or error)) from None


def _read_kit(archive, path, hint_folder):
    notes = []
    entries = []
    for info in archive.infolist():
        if info.is_dir():
            continue
        rel = clean_rel(info.filename)
        if rel is None:
            raise KitSyncError("The kit zip contains a file path that points outside its folder ({!r}), so I didn't "
                               "install it. Download the kit again from your Caiman account.".format(info.filename))
        if is_junk(rel):
            continue
        if stat.S_ISLNK(info.external_attr >> 16):
            notes.append('Skipped a link inside the zip: ' + rel)
            continue
        entries.append((rel, info))
    markers = [rel for rel, _ in entries
               if rel.rsplit('/', 1)[-1] in ('RELEASE_MANIFEST.json', 'ENTITLEMENTS.json', 'CLIENT_START.py')]
    roots = sorted({m.rsplit('/', 1)[0] if '/' in m else '' for m in markers},
                   key=lambda r: (0 if not r else r.count('/') + 1, r))
    if not roots:
        raise KitSyncError("{} doesn't look like a Caiman kit: it has no ENTITLEMENTS.json, RELEASE_MANIFEST.json "
                           "or CLIENT_START.py. Use the kit zip from your Caiman membership downloads.".format(path.name))
    if hint_folder and hint_folder in roots:
        prefix = hint_folder
    else:
        depth = 0 if not roots[0] else roots[0].count('/') + 1
        shallow = [r for r in roots if (0 if not r else r.count('/') + 1) == depth]
        if len(shallow) > 1:
            raise KitSyncError('{} holds more than one kit ({}). Use the single kit zip for this '
                               'membership.'.format(path.name, ', '.join(shallow)))
        prefix = shallow[0]
    lead = prefix + '/' if prefix else ''
    files, folded, total, outside = {}, {}, 0, 0
    executables = set()
    for rel, info in entries:
        if lead and not rel.startswith(lead):
            outside += 1
            continue
        sub = rel[len(lead):]
        if sub.lower() in folded:
            raise KitSyncError('The kit zip has two files whose names differ only in capital letters ({} and {}). '
                               'Download the kit again from your Caiman account.'.format(folded[sub.lower()], sub))
        folded[sub.lower()] = sub
        total += info.file_size
        if total > MAX_EXPANDED_BYTES:
            raise KitSyncError('{} unpacks to far more than a Caiman kit, so I stopped. Use the kit zip from your '
                               'Caiman membership downloads.'.format(path.name))
        files[sub] = archive.read(info)
        if (info.external_attr >> 16) & 0o111:
            executables.add(sub)
    if outside:
        notes.append('Ignored {} in the zip outside the kit folder.'.format(plural(outside, 'file')))

    def parsed(name):
        try:
            return as_dict(json.loads(files[name].decode('utf-8-sig'))) if name in files else {}
        except (ValueError, UnicodeError):
            return {}

    manifest = parsed('RELEASE_MANIFEST.json')
    entitlements = parsed('ENTITLEMENTS.json')
    tier = (norm_tier(manifest.get('kit')) or norm_tier(manifest.get('tier'))
            or norm_tier(entitlements.get('plan_tier')))
    if tier is None and 'CLIENT_START.py' in files:
        tier = 'vip' if 'GUIDED_SETUP.py' in files else ('gls-plus' if 'GLS_GUIDED_SETUP.py' in files else None)
    if tier is None:
        raise KitSyncError("I couldn't tell which membership {} is for (VIP or GLS+). Use the kit zip from your "
                           "Caiman membership downloads.".format(path.name))
    skills = entitlements.get('skills')
    if not isinstance(skills, list):
        skills = [item.get('name') for item in parsed('CAPABILITY_INDEX.json').get('skills') or []
                  if isinstance(item, dict)]
    version = manifest.get('version') if isinstance(manifest.get('version'), str) else None
    release = manifest.get('release') if isinstance(manifest.get('release'), str) else None
    return Kit(path.name, files, tier, version, release,
               sorted({s for s in skills if isinstance(s, str) and s}), notes, core_version_of(manifest), executables)


# ---------------------------------------------------------------- downloading

class HttpsOnlyRedirects(urllib.request.HTTPRedirectHandler):
    """Follow the server's redirects, but never to a non-secure address."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urllib.parse.urlsplit(newurl).scheme.lower() != 'https':
            raise KitSyncError('The Caiman server sent the download to a non-secure address, so I stopped. '
                               'Get a fresh download link and try again.')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def make_opener():
    """An opener that uses the computer's proxy settings (HTTPS_PROXY, HTTP_PROXY, NO_PROXY)."""
    context = ssl.create_default_context()
    extra = [os.environ.get(name) for name in ('SSL_CERT_FILE', 'REQUESTS_CA_BUNDLE', 'CURL_CA_BUNDLE')]
    try:
        import certifi  # optional; helps Python installs that ship without certificates
        extra.append(certifi.where())
    except ImportError:
        pass
    for cafile in extra:
        if cafile and os.path.isfile(cafile):
            try:
                context.load_verify_locations(cafile=cafile)
            except (OSError, ssl.SSLError):
                pass
    return urllib.request.build_opener(
        urllib.request.ProxyHandler(urllib.request.getproxies()),
        urllib.request.HTTPSHandler(context=context),
        HttpsOnlyRedirects())


def proxy_in_use(url):
    host = urllib.parse.urlsplit(url).hostname or ''
    proxy = urllib.request.getproxies().get(urllib.parse.urlsplit(url).scheme or 'https')
    if not proxy:
        return None
    try:
        if urllib.request.proxy_bypass(host):
            return None
    except Exception:
        pass
    parts = urllib.parse.urlsplit(proxy if '://' in proxy else 'http://' + proxy)
    return '{}:{}'.format(parts.hostname, parts.port) if parts.port else str(parts.hostname)


def redact(text):
    """Keep signed download links out of messages."""
    return re.sub(r'(https?://[^/\s?#]+)[^\s]*', r'\1/...', str(text))


def network_message(url, reason):
    proxy = proxy_in_use(url)
    route = ' through the proxy {} (from HTTPS_PROXY)'.format(proxy) if proxy else ''
    detail = redact(reason)
    if re.search(r'\b407\b', detail):
        return http_message(407, 'Proxy Authentication Required')
    if isinstance(reason, ssl.SSLCertVerificationError) or 'CERTIFICATE_VERIFY_FAILED' in detail:
        return ("The secure connection to the Caiman server{} couldn't be verified ({}). If this network uses a "
                "proxy that inspects HTTPS, set SSL_CERT_FILE to that proxy's certificate file. On a Mac with "
                "Python from python.org, run 'Install Certificates.command' once. You can also download the kit "
                "zip from your Caiman account and use it instead.".format(route, detail))
    if isinstance(reason, (socket.timeout, TimeoutError)) or 'timed out' in detail.lower():
        return ('The connection to the Caiman server{} timed out. Check the internet connection and try again, '
                'or use the kit zip from your Caiman account.'.format(route))
    if proxy:
        return ("I couldn't reach the Caiman server through the proxy {} ({}). Check the HTTPS_PROXY setting "
                "(it may need a user name and password), or use the kit zip from your Caiman account.".format(proxy, detail))
    return ("I couldn't reach the Caiman server ({}). Check the internet connection. If this computer must use a "
            "proxy, set HTTPS_PROXY (for example HTTPS_PROXY=http://proxy.example.com:8080) and try again. You can "
            "also download the kit zip from your Caiman account and use it instead.".format(detail))


def http_message(code, reason):
    if code in (401, 403):
        return ('The Caiman server refused the download (HTTP {}). The link may have expired (links last about two '
                "minutes), or this membership may not include this kit. Get a fresh link with the Caiman "
                "connector's get_kit_download tool and run the install right away.".format(code))
    if code in (404, 410):
        return ('The download link has expired or was not found (HTTP {}). Get a fresh link with the Caiman '
                "connector's get_kit_download tool and run the install right away.".format(code))
    if code == 407:
        return ('The network proxy asked for a login (HTTP 407). Put the proxy user name and password in '
                'HTTPS_PROXY (http://user:password@proxy:port), or use the kit zip from your Caiman account.')
    if code >= 500:
        return ('The Caiman server had a problem (HTTP {}). Try again in a few minutes, or use the kit zip from '
                'your Caiman account.'.format(code))
    return 'The Caiman server answered HTTP {} ({}). Get a fresh download link and try again.'.format(code, reason)


def load_descriptor(value):
    """Find the download details (download_url, sha256, ...) in a saved get_kit_download result."""
    text = value.strip()
    if text[:1] not in ('{', '['):
        path = Path(value).expanduser()
        try:
            text = path.read_text(encoding='utf-8-sig')
        except OSError as error:
            raise KitSyncError("I couldn't read the saved download details at {} ({}). Save the full result of the "
                               "Caiman connector's get_kit_download tool to that file.".format(path, error.strerror or error)) from None
    try:
        data = json.loads(text)
    except ValueError:
        data = None
    if data is None:
        # The tool's result is a sentence followed by the details as JSON. Read the first JSON object in it.
        decoder = json.JSONDecoder()
        for match in re.finditer(r'[{\[]', text):
            try:
                candidate, _ = decoder.raw_decode(text, match.start())
            except ValueError:
                continue
            if _find_download(candidate, 0):
                data = candidate
                break
    if data is None:
        raise KitSyncError("The saved download details aren't readable. Save the full result of the Caiman "
                           "connector's get_kit_download tool to a file and try again.")
    found = _find_download(data, 0)
    if not found:
        raise KitSyncError("The saved download details have no download link (download_url). Save the full result "
                           "of the Caiman connector's get_kit_download tool and try again.")
    return found


def _find_download(value, depth):
    if depth > 8:
        return None
    if isinstance(value, dict):
        url = value.get('download_url') or value.get('downloadUrl')
        if isinstance(url, str) and url.strip():
            return value
        children = value.values()
    elif isinstance(value, list):
        children = value
    elif isinstance(value, str) and value.strip()[:1] in ('{', '['):
        try:
            return _find_download(json.loads(value), depth + 1)
        except ValueError:
            return None
    else:
        return None
    for child in children:
        found = _find_download(child, depth + 1)
        if found:
            return found
    return None


def check_download_url(url):
    parts = urllib.parse.urlsplit(url.strip())
    try:
        port = parts.port
    except ValueError:
        port = -1
    if (parts.scheme != 'https' or (parts.hostname or '').lower() != DOWNLOAD_HOST
            or parts.username or parts.password or port not in (None, 443)
            or not parts.path.startswith(DOWNLOAD_PATH_PREFIX)):
        raise KitSyncError("That download link doesn't point at the Caiman kit service (https://{}{}...), so I "
                           "didn't use it. Get a fresh link with the Caiman connector's get_kit_download tool, or "
                           "use the kit zip from your Caiman account.".format(DOWNLOAD_HOST, DOWNLOAD_PATH_PREFIX))


def _discard(path):
    """Remove this program's own failed or incomplete download."""
    try:
        os.unlink(path)
    except OSError:
        pass


def fetch(url, dest, expected_sha256=None, expected_bytes=None, opener=None):
    """Save url to dest. Checks size and checksum only when they were provided."""
    opener = opener or make_opener()
    request = urllib.request.Request(url, headers={
        'Accept': 'application/zip, application/octet-stream;q=0.9, */*;q=0.5',
        'User-Agent': 'caiman-kit-sync/' + PROGRAM_VERSION})
    digest, size = hashlib.sha256(), 0
    try:
        with opener.open(request, timeout=60) as response, open(dest, 'wb') as out:
            for chunk in iter(lambda: response.read(1024 * 1024), b''):
                size += len(chunk)
                if size > MAX_ZIP_BYTES:
                    raise KitSyncError('The download is far larger than a Caiman kit, so I stopped. Get a fresh '
                                       'download link and try again.')
                digest.update(chunk)
                out.write(chunk)
    except KitSyncError:
        _discard(dest)
        raise
    except urllib.error.HTTPError as error:
        _discard(dest)
        raise KitSyncError(http_message(error.code, error.reason)) from None
    except urllib.error.URLError as error:
        _discard(dest)
        raise KitSyncError(network_message(url, error.reason)) from None
    except (socket.timeout, TimeoutError, ssl.SSLError) as error:
        _discard(dest)
        raise KitSyncError(network_message(url, error)) from None
    except http.client.HTTPException as error:
        _discard(dest)
        raise KitSyncError('The download was cut off before it finished ({}). Get a fresh download link and try '
                           'again.'.format(type(error).__name__)) from None
    except OSError as error:
        _discard(dest)
        raise KitSyncError("The download couldn't be saved ({}). Check that there is free disk space and try "
                           "again.".format(error.strerror or error)) from None
    problem = None
    if isinstance(expected_bytes, int) and not isinstance(expected_bytes, bool) and expected_bytes > 0 \
            and size != expected_bytes:
        problem = 'is {:,} bytes, but the Caiman server said it would be {:,} bytes'.format(size, expected_bytes)
    elif expected_sha256 and digest.hexdigest() != expected_sha256.strip().lower():
        problem = "doesn't match the checksum the Caiman server gave for it"
    if problem:
        _discard(dest)
        raise KitSyncError('The downloaded kit {}, so I did not install it. The download was probably cut off or '
                           'changed on the way. Nothing in the business folder was changed. Get a fresh download '
                           'link and try again.'.format(problem))
    return {'path': str(dest), 'bytes': size, 'sha256': digest.hexdigest()}


def download_kit(descriptor=None, url=None, sha256=None, out_dir=None, expected_tier=None, file_name=None):
    details = load_descriptor(descriptor) if descriptor else {}
    link = url or details.get('download_url') or details.get('downloadUrl')
    if not isinstance(link, str) or not link.strip():
        raise KitSyncError("There's no download link. Pass --descriptor with the saved result of the Caiman "
                           "connector's get_kit_download tool, or --zip with a kit zip.")
    check_download_url(link)
    offered = norm_tier(details.get('tier') or details.get('kit'))
    if expected_tier and offered and offered != expected_tier:
        raise KitSyncError('The Caiman server offered the {} kit, but this plugin is {}. Ask the connector for the '
                           '{} kit (get_kit_download with kit "{}").'.format(tier_name(offered), tier_name(expected_tier),
                                                                            tier_name(expected_tier), expected_tier))
    checksum = sha256 or details.get('sha256')
    if checksum is not None and not (isinstance(checksum, str) and re.fullmatch(r'[0-9a-fA-F]{64}', checksum.strip())):
        checksum = None
    size = details.get('bytes', details.get('size_bytes'))
    folder = Path(out_dir).expanduser() if out_dir else Path(tempfile.mkdtemp(prefix='caiman-kit-'))
    folder.mkdir(parents=True, exist_ok=True)
    name = file_name or 'caiman-{}-kit.zip'.format(offered or expected_tier or 'caiman')
    dest = unique_path(folder / name)
    result = fetch(link.strip(), dest, checksum, size if isinstance(size, int) else None)
    result['checksum_checked'] = bool(checksum)
    return result


# ---------------------------------------------------------------- CLAUDE.md merge

def _spans(text, start_re, end_re):
    """(start, end) of each complete section. A START without its own END is left alone."""
    starts = list(start_re.finditer(text))
    ends = list(end_re.finditer(text))
    spans = []
    for index, start in enumerate(starts):
        limit = starts[index + 1].start() if index + 1 < len(starts) else len(text)
        end = next((e for e in ends if start.end() <= e.start() < limit), None)
        if end:
            spans.append((start.start(), end.end()))
    return spans


def kit_section(kit_text):
    body = kit_text
    for pattern in (START_RE, END_RE, OLD_START_RE, OLD_END_RE):
        body = pattern.sub('', body)
    return '{}\n{}\n{}'.format(BLOCK_START, body.strip('\n').rstrip(), BLOCK_END)


def _hash_forms(text):
    forms = {text, text.lstrip('\n'), text.strip('\n') + '\n', text.strip()}
    return {sha256_bytes(form.encode('utf-8', 'surrogateescape')) for form in forms if form}


def without_old_kit_text(text, old_kit_hashes):
    """text without an unchanged older kit CLAUDE.md at its start or end, or None if there is none.

    Older kits installed CLAUDE.md as a whole kit file. A member who added notes to it
    kept the old kit rules too; the install record's checksum of that file tells the
    unchanged kit text apart from the member's own additions, which stay.
    """
    if not old_kit_hashes or not text.strip():
        return None
    cuts = sorted({0, len(text)} | {index + 1 for index, char in enumerate(text) if char == '\n'})
    for cut in cuts[1:]:
        if _hash_forms(text[:cut]) & old_kit_hashes:
            return text[cut:]
    for cut in cuts[:-1]:
        if _hash_forms(text[cut:]) & old_kit_hashes:
            return text[:cut]
    return None


def merge_claude_md(existing, kit_text, old_kit_hashes=()):
    """Return (new text, what happened). Only the Caiman section is replaced.

    The section is found by its START/END lines, so edits or extra spaces inside it
    never stop an update. Text outside the section is the member's and is kept.
    """
    section = kit_section(kit_text)
    if existing is None:
        return section + '\n', 'created'
    spans = []
    for start, end in sorted(_spans(existing, START_RE, END_RE) + _spans(existing, OLD_START_RE, OLD_END_RE)):
        if spans and start < spans[-1][1]:
            spans[-1] = (spans[-1][0], max(end, spans[-1][1]))
        else:
            spans.append((start, end))
    rest, cursor = [], 0
    for start, end in spans:
        rest.append(existing[cursor:start])
        cursor = end
    rest.append(existing[cursor:])
    rest = ''.join(rest)

    def unchanged_old_kit(text):
        forms = {text, text.lstrip('\n'), text.strip('\n') + '\n', text.strip()}
        return any(sha256_bytes(form.encode('utf-8', 'surrogateescape')) in old_kit_hashes for form in forms if form)

    if not rest.strip() or (old_kit_hashes and unchanged_old_kit(rest)):
        # Nothing of the member's outside the Caiman section(s), or only an untouched older kit CLAUDE.md.
        merged = section + '\n'
        if merged == existing:
            return existing, 'unchanged'
        return merged, ('replaced the previous kit version' if rest.strip() else 'updated the Caiman section')
    member_text = without_old_kit_text(rest, set(old_kit_hashes))
    if member_text is not None:
        # An older kit CLAUDE.md with the member's notes added to it: the old kit rules are
        # replaced by the Caiman section, and the member's notes stay below it.
        member_text = member_text.strip('\n')
        merged = section + '\n' + ('\n' + member_text + '\n' if member_text.strip() else '')
        if merged == existing:
            return existing, 'unchanged'
        return merged, ('replaced the previous kit version; your own notes are kept below the Caiman section'
                        if member_text.strip() else 'replaced the previous kit version')
    if not spans:
        separator = '' if existing.startswith('\n') else '\n'
        return section + '\n' + separator + existing, 'added the Caiman section above your notes'
    pieces, cursor = [], 0
    for index, (start, end) in enumerate(spans):
        pieces.append(existing[cursor:start])
        if index == 0:
            pieces.append(section)
        elif existing[end:end + 1] == '\n':
            end += 1                      # drop the line break left by a duplicate section
        cursor = end
    pieces.append(existing[cursor:])
    merged = ''.join(pieces)
    if merged == existing:
        return existing, 'unchanged'
    return merged, 'updated the Caiman section; your notes outside it are unchanged'


# ---------------------------------------------------------------- the install

class PreviousKit:
    """_previous-kit/<date>/ for this run, created only when something is moved."""

    def __init__(self, root, dry_run):
        self.root = root
        self.dry_run = dry_run
        self.folder = None
        self.moved = []

    def _folder(self):
        if self.folder is None:
            base = self.root / PREVIOUS_DIR
            day = dt.date.today().isoformat()
            name, counter = day, 1
            while exists(base / name):
                counter += 1
                name = '{}-{}'.format(day, counter)
            self.folder = base / name
            if not self.dry_run:
                self.folder.mkdir(parents=True)
        return self.folder

    @property
    def relative(self):
        return self.folder.relative_to(self.root).as_posix() if self.folder else None

    def move(self, rel, kind, dest_rel=None):
        source = self.root / rel
        dest = unique_path(self._folder() / (dest_rel or rel))
        if not self.dry_run:
            dest.parent.mkdir(parents=True, exist_ok=True)
            try:
                os.rename(source, dest)
            except OSError as error:
                raise KitSyncError("I couldn't move {} into {} ({}). If it's open in another program, close it "
                                   "and run the install again.".format(rel, PREVIOUS_DIR, error.strerror or error)) from None
        self.moved.append({'kind': kind, 'path': rel, 'moved_to': dest.relative_to(self.root).as_posix()})


def recorded_kit_files(root):
    """Files earlier installs placed directly in the business folder: path -> the SHA-256 values they had."""
    found = {}
    folder = root / '.caiman' / 'kit-installations'
    if not folder.is_dir():
        return found
    for record_path in sorted(folder.glob('*.json')):
        record = as_dict(read_json(record_path))
        if record.get('guidance_relative', '.') not in ('.', '', None):
            continue                      # an older side-by-side copy; handled with .caiman/kit-versions
        for name, value in as_dict(record.get('files')).items():
            rel = clean_rel(name)
            if not rel:
                continue
            digest = value.get('sha256') if isinstance(value, dict) else value
            hashes = found.setdefault(rel, set())
            if isinstance(digest, str) and re.fullmatch(r'[0-9a-fA-F]{64}', digest):
                hashes.add(digest.lower())
    return found


def known_kit_versions(root, recorded):
    """path -> SHA-256 values of the copies Caiman put at that path: install records, plus the
    entry-point forwarders older installers wrote (.caiman/entrypoint-history)."""
    known = {rel: set(hashes) for rel, hashes in recorded.items() if hashes}
    folder = root / '.caiman' / 'entrypoint-history'
    if folder.is_dir() and not folder.is_symlink():
        for path in sorted(folder.glob('*.json')):
            record = as_dict(read_json(path))
            rel = clean_rel(record.get('entrypoint'))
            digest = record.get('after_sha256')
            if rel and isinstance(digest, str) and re.fullmatch(r'[0-9a-fA-F]{64}', digest):
                known.setdefault(rel, set()).add(digest.lower())
    return known


def replaced_kind(rel, path, known):
    """Why the file at rel is being replaced: an older kit copy, one the member changed, or one with no record."""
    hashes = known.get(rel)
    if not hashes:
        return KIND_UNRECORDED
    try:
        digest = sha256_file(path)
    except OSError:
        return KIND_UNRECORDED
    return KIND_OLDER if digest in hashes else KIND_EDITED


def ensure_workspace_id(root, dry_run):
    path = root / '.caiman' / 'workspace-id.json'
    data = as_dict(read_json(path))
    try:
        if data.get('schema') == 'caiman.workspace-id.v1':
            return str(uuid.UUID(str(data.get('id'))))
    except ValueError:
        pass
    new_id = str(uuid.uuid4())
    if not dry_run:
        put_bookkeeping(path, json_bytes({'schema': 'caiman.workspace-id.v1', 'id': new_id}),
                        root / '.caiman' / 'history')
    return new_id


def current_note(kit):
    return ('{}\n# Caiman kit in this folder\n\n'
            '{}, installed {}.\n\n'
            'Guide folder: . (this business folder)\n\n'
            'The kit files live directly in this business folder. Caiman work starts with the caiman skill, which '
            "runs CLIENT_START.py from this folder with the member's request.\n\n"
            'Kit updates never change your own files: CLIENT_RULES.md, MEMORY.md, memory/, knowledge/, and your '
            'data, reports and outputs. Kit files that an update replaces are kept in {}/.\n'
            ).format(GENERATED_NOTE_MARKER, kit.label, dt.date.today().isoformat(), PREVIOUS_DIR).encode('utf-8')


def restore_execute_bits(root, rels):
    """Kit files that ship executable but lost the execute bit get it back (their bytes were already right)."""
    for rel in rels:
        try:
            os.chmod(root / rel, 0o755)
        except OSError:
            pass


def _placed_by_kit_sync(folder, rel, recorded):
    """True when an earlier kit-sync install placed files in this skill folder. Such a folder is updated file by
    file: kit files are replaced (changed ones saved and named), and files the member added stay."""
    lead = rel + '/'
    return any(name.startswith(lead) for name in recorded)


def install(folder, kit, plugin=None, tier=None, switch_tier=False, dry_run=False, source_label=None):
    root = Path(folder).expanduser()
    if not root.is_dir():
        raise KitSyncError("I can't find the business folder {}. Check the path, or create the folder first "
                           "(with the member's OK on its name and place).".format(root))
    root = root.resolve()
    want = tier or (plugin or {}).get('tier')
    if want and kit.tier != want:
        expected_zip = (plugin or {}).get('kit_zip') if want == (plugin or {}).get('tier') else None
        raise KitSyncError('This zip is the {} kit, but this plugin is {}. Use the {} kit zip{} from the Caiman '
                           'membership downloads.'.format(tier_name(kit.tier), tier_name(want), tier_name(want),
                                                          ' ({})'.format(expected_zip) if expected_zip else ''))
    current = installed_kit(root)
    have_core = parse_version(current.get('core_version') or '')
    new_core = parse_version(kit.core_version or '')
    if current['present'] and have_core and (not new_core or new_core < have_core):
        raise KitSyncError("The kit in this business folder goes with Caiman {}, and {} goes with {}, so I didn't "
                           'install it. Nothing in the business folder was changed. Use a kit that goes with Caiman {} '
                           'or later.'.format(current['core_version'], kit.label,
                                              'Caiman ' + kit.core_version if new_core else 'an older Caiman',
                                              current['core_version']))
    if current['present'] and current['tier'] and current['tier'] != kit.tier and not switch_tier:
        raise NeedsConfirmation(
            'This business folder has the {} kit, and this install is the {} kit. Switching keeps all of the '
            "member's own files and moves the {} kit files to {}/. Ask the member to confirm the switch, then run "
            'the install again with --switch-tier.'.format(tier_name(current['tier']), tier_name(kit.tier),
                                                            tier_name(current['tier']), PREVIOUS_DIR))
    notes = list(kit.notes)
    plugin_version = (plugin or {}).get('version')
    # A kit must go with this Caiman or a newer one. Without a plugin (the kit's own Install tools copy),
    # this program's version sets the floor.
    floor, who = PROGRAM_VERSION, 'this installer (Caiman {})'.format(PROGRAM_VERSION)
    if parse_version(plugin_version or '') and parse_version(plugin_version) >= parse_version(PROGRAM_VERSION):
        floor, who = plugin_version, 'this plugin ({})'.format(plugin_version)
    if not kit.core_version or not parse_version(kit.core_version) or parse_version(kit.core_version) < parse_version(floor):
        raise KitSyncError('This kit ({}) goes with an older Caiman than {}, so I didn\'t install it. Nothing in the '
                           'business folder was changed. The Caiman server may not have the new kits yet: try again '
                           'later, or use the kit zip that goes with Caiman {}.'.format(kit.label, who, floor))
    if plugin_version and kit.core_version and parse_version(plugin_version) \
            and parse_version(kit.core_version) != parse_version(plugin_version):
        notes.append('This kit goes with Caiman {} and the Caiman plugin here is {}. They work best when they '
                     'match.'.format(kit.core_version, plugin_version))
    if current['present'] and parse_version(current['version'] or '') and parse_version(kit.version or '') \
            and parse_version(kit.version) < parse_version(current['version']):
        notes.append('This replaces a newer kit ({}) with {}.'.format(current['version'], kit.version))

    skill_names = set((plugin or {}).get('skills') or []) | set(kit.skills) | set(PLUGIN_OWN_SKILLS)
    recorded = recorded_kit_files(root)
    known = known_kit_versions(root, recorded)
    previous = PreviousKit(root, dry_run)
    counts = {'added': 0, 'updated': 0, 'unchanged': 0}
    skipped = []
    changes = []     # (action, rel, data or kind); run after the plan is complete
    exec_fixes = []  # unchanged kit files that ship executable but lost the execute bit
    planned_moves = set()

    # 0. The kit's skills go in .claude/skills/<name>. A copy already there that no kit-sync install placed
    #    (an older kit's copy, or one the member made or changed) moves to _previous-kit as a whole folder,
    #    so the kit's version goes into a clean folder. Unchanged Caiman copies are recognized by content.
    skill_dirs = kit_skill_dirs(kit.files)
    folder_moves = []
    for name in skill_dirs:
        rel = KIT_SKILLS + '/' + name
        path = root / rel
        if not exists(path):
            continue
        if path.is_dir() and not path.is_symlink() and _placed_by_kit_sync(path, rel, recorded):
            continue                                  # placed by kit-sync: updated file by file below
        state = copy_state(path, {name})
        kind = KIND_SKILLS if state == 'unchanged' else (KIND_IN_WAY if state == 'link' else KIND_SKILL_CHANGED)
        folder_moves.append((rel, kind))
    moved_folders = tuple(rel + '/' for rel, _ in folder_moves)

    # 1. What the new kit changes.
    for rel in sorted(kit.files):
        data = kit.files[rel]
        if rel == CLAUDE_FILE:
            continue
        if member_owned(rel):
            skipped.append(rel)
            continue
        if rel.startswith(moved_folders):
            changes.append(('write', rel, data))      # its folder moves aside first (step 0)
            counts['updated'] += 1
            continue
        parts = rel.split('/')
        for depth in range(1, len(parts)):
            ancestor = '/'.join(parts[:depth])
            path = root / ancestor
            if ancestor in planned_moves:
                break
            if path.is_symlink():
                raise KitSyncError('"{}" in the business folder is a link to another place, so I stopped before '
                                   'changing anything. Replace the link with a normal folder, then run the install '
                                   'again.'.format(ancestor))
            if path.exists() and not path.is_dir():
                changes.append(('move', ancestor, KIND_IN_WAY_FOLDER))
                planned_moves.add(ancestor)
                break
        target = root / rel
        if target.is_symlink() or target.is_dir():
            changes.append(('move', rel, KIND_IN_WAY))
            changes.append(('write', rel, data))
            counts['updated'] += 1
        elif target.exists():
            try:
                same = target.stat().st_size == len(data) and target.read_bytes() == data
            except OSError:
                same = False
            if same:
                counts['unchanged'] += 1
                if rel in kit.executables and not os.access(str(target), os.X_OK):
                    exec_fixes.append(rel)
            else:
                changes.append(('move', rel, replaced_kind(rel, target, known)))
                changes.append(('write', rel, data))
                counts['updated'] += 1
        else:
            changes.append(('write', rel, data))
            counts['added'] += 1

    # 2. Kit parts that are no longer shipped, older side-by-side kit copies, and old skill copies.
    retire = [rel for rel in RETIRED_TOP if rel not in kit.files and exists(root / rel)]
    retire_edited = []
    retire_added = []
    for top in retire:
        base = root / top
        inside = [base] if base.is_file() else sorted(p for p in base.rglob('*') if p.is_file() and not p.is_symlink())
        for path in inside:
            rel = path.relative_to(root).as_posix()
            if is_junk(rel):
                continue
            digests = set(recorded.get(rel) or ()) | set(SHIPPED_RETIRED_FILES.get(rel, ()))
            if not digests:
                retire_added.append(rel)
                continue
            try:
                if sha256_file(path) not in digests:
                    retire_edited.append(rel)
            except OSError:
                pass
    for rel, digests in sorted(recorded.items()):
        if rel in kit.files or rel == CLAUDE_FILE or member_owned(rel):
            continue
        if any(rel == top or rel.startswith(top + '/') for top in RETIRED_TOP):
            continue
        path = root / rel
        if path.is_file() and not path.is_symlink():
            retire.append(rel)
            try:
                if digests and sha256_file(path) not in digests:
                    retire_edited.append(rel)
            except OSError:
                pass
    left_in_place = []
    retire += old_skills_folder(root, retire, kit.files, left_in_place)
    retire = whole_folders(root, retire, kit.files)
    folder_roots = [rel for rel, _ in folder_moves]
    retire = [rel for rel in retire if not any(rel == f or rel.startswith(f + '/') for f in folder_roots)]
    side_copies = root / '.caiman' / 'kit-versions'
    move_side_copies = side_copies.is_dir() and not side_copies.is_symlink() and any(side_copies.iterdir())
    copies = find_skill_copies(root, skill_names, (plugin or {}).get('root'), skill_dirs)

    def _overlaps(a, b):
        return a == b or a.startswith(b + '/') or b.startswith(a + '/')
    planned = retire + folder_roots
    copies['move'] = [item for item in copies['move'] if not any(_overlaps(item['path'], rel) for rel in planned)]
    tier_state = []
    if current['present'] and current['tier'] and current['tier'] != kit.tier:
        tier_state = [rel for rel in TIER_STATE_FILES if (root / rel).is_file() and not (root / rel).is_symlink()]

    # 3. CLAUDE.md: replace only the Caiman section.
    claude_plan = None
    if CLAUDE_FILE in kit.files:
        target = root / CLAUDE_FILE
        existing = None
        if target.is_file():
            existing = target.read_bytes().decode('utf-8', 'surrogateescape')
        old_hashes = set(recorded.get(CLAUDE_FILE) or ()) | set(SHIPPED_CLAUDE_MD)
        kit_text = kit.files[CLAUDE_FILE].decode('utf-8', 'replace')
        merged, how = merge_claude_md(existing, kit_text, old_hashes)
        if how != 'unchanged':
            claude_plan = (merged.encode('utf-8', 'surrogateescape'), how, existing is not None or exists(target))

    # 4. Is there anything to do at all?
    plan_empty = (not changes and not retire and not move_side_copies and not copies['move'] and not folder_moves
                  and not tier_state and claude_plan is None)
    pointer = as_dict(read_json(root / '.caiman' / 'active-guidance.json'))
    same_version = (current['present'] and current['layout'] == 'in-folder' and current['tier'] == kit.tier
                    and current['version'] == kit.version)
    bookkeeping_ok = pointer.get('guidance_relative') == '.' and (root / '.caiman' / 'workspace-id.json').is_file()
    result = {'folder': str(root), 'tier': kit.tier, 'version': kit.version, 'release': kit.release,
              'kit': kit.label, 'source': source_label or kit.source, 'dry_run': dry_run, 'counts': counts,
              'skipped_member_paths': skipped, 'notes': notes, 'skill_copies_kept': copies['kept'],
              'left_in_place': left_in_place, 'skills_installed': len(skill_dirs), 'skills_folder': KIT_SKILLS}
    if plan_empty and same_version and bookkeeping_ok:
        if not dry_run:
            restore_execute_bits(root, exec_fixes)
        result.update(status='current', moved=[], claude_md='unchanged', previous_kit_folder=None, your_files=[],
                      retired_files_that_were_edited=[])
        result['vip_machine'] = vip_machine_step(root, kit, dry_run)
        result['message'] = _summary(result, current, kit, dry_run, already_current=True)
        return result

    # 5. Do it. Only renames into _previous-kit and new files: nothing is deleted or overwritten in place.
    written = []
    try:
        for rel in retire:
            previous.move(rel, KIND_RETIRED_EDITED if rel in retire_edited else KIND_RETIRED)
        if move_side_copies:
            previous.move('.caiman/kit-versions', KIND_SIDE, 'kit-versions')
        for item in copies['move']:
            previous.move(item['path'], KIND_SKILLS, item['dest'])
        for rel, kind in folder_moves:
            previous.move(rel, kind, 'skills/' + rel.rsplit('/', 1)[1])
        for rel in tier_state:
            previous.move(rel, KIND_TIER_STATE)
        for action, rel, payload in changes:
            if action == 'move':
                previous.move(rel, payload)
            else:
                if not dry_run:
                    write_new(root / rel, payload)
                    if rel in kit.executables:
                        try:
                            os.chmod(root / rel, 0o755)
                        except OSError:
                            pass
                written.append(rel)
        if not dry_run:
            restore_execute_bits(root, exec_fixes)
        claude_how = 'unchanged'
        if claude_plan is not None:
            data, claude_how, had_file = claude_plan
            if had_file:
                previous.move(CLAUDE_FILE, CLAUDE_MOVED)
            if not dry_run:
                write_new(root / CLAUDE_FILE, data)
        workspace_id = ensure_workspace_id(root, dry_run)
        record_rel = None
        if not dry_run:
            record_rel = _record_install(root, kit, workspace_id, previous.relative, source_label)
            put_bookkeeping(root / '.caiman' / 'active-guidance.json',
                            json_bytes({'schema': 'caiman.active-guidance.v1', 'tier': kit.tier,
                                        'workspace_id': workspace_id, 'guidance_relative': '.',
                                        'install_record': {'path': record_rel}}),
                            root / '.caiman' / 'history')
            note_path = root / CURRENT_NOTE
            note_text = None
            if note_path.is_file():
                try:
                    note_text = note_path.read_text(encoding='utf-8', errors='replace')
                except OSError:
                    note_text = None
            if note_text is None or note_text.startswith(GENERATED_NOTE_MARKER):
                put_bookkeeping(note_path, current_note(kit), root / '.caiman' / 'history')
            else:
                notes.append('{} has your own notes in it, so I left it as it is.'.format(CURRENT_NOTE))
    except KitSyncError as error:
        done = ''
        if previous.moved or written:
            done = (' Part of the kit was already installed; anything moved is in {}/. Run the same install again '
                    'to finish. It picks up where it stopped.'.format(previous.relative or PREVIOUS_DIR))
        raise KitSyncError('{}{}'.format(error, done)) from None
    except OSError as error:
        raise KitSyncError("a file couldn't be written ({}), so only part of the kit was installed. Anything moved "
                           'is in {}/. Fix the cause (for example free disk space or folder permissions) and run the '
                           'same install again; it picks up where it stopped.'.format(
                               error.strerror or error, previous.relative or PREVIOUS_DIR)) from None

    result.update(status='planned' if dry_run else 'installed', moved=previous.moved,
                  previous_kit_folder=previous.relative, claude_md=claude_how,
                  retired_files_that_were_edited=retire_edited, install_record=record_rel)
    result['your_files'] = personal_items(previous.moved, retire_edited, retire_added)
    result['vip_machine'] = vip_machine_step(root, kit, dry_run)
    result['message'] = _summary(result, current, kit, dry_run)
    return result


def whole_folders(root, retire, kit_files):
    """Move a folder in one step when everything in it is a retired kit part.

    That leaves no empty folders behind, and needs no deleting, which some synced
    folders don't allow.
    """
    retire_set = set(retire)
    kit_folders = {'/'.join(rel.split('/')[:depth]) for rel in kit_files for depth in range(1, rel.count('/') + 1)}
    candidates = sorted({'/'.join(rel.split('/')[:depth]) for rel in retire_set for depth in range(1, rel.count('/') + 1)},
                        key=lambda name: (name.count('/'), name))

    def covered(rel):
        return any(rel == item or rel.startswith(item + '/') for item in retire_set)

    chosen = []
    for name in candidates:
        if name in kit_folders or name in retire_set or any(name.startswith(c + '/') for c in chosen):
            continue
        folder = root / name
        if folder.is_symlink() or not folder.is_dir():
            continue
        inside = [p.relative_to(root).as_posix() for p in folder.rglob('*') if p.is_file() or p.is_symlink()]
        if inside and all(covered(rel) or is_junk(rel) for rel in inside):
            chosen.append(name)
    return chosen + [rel for rel in retire if not any(rel == c or rel.startswith(c + '/') for c in chosen)]


def saved_location(moved, rel):
    """Where rel ended up in _previous-kit, following a move of the file itself or of a folder holding it."""
    for item in moved:
        if rel == item['path']:
            return item['moved_to']
        if rel.startswith(item['path'] + '/'):
            return item['moved_to'] + rel[len(item['path']):]
    return None


def personal_items(moved, retire_edited, retire_added=()):
    """Everything moved that can hold the member's own work, each with where it is now."""
    items = [{'path': item['path'], 'saved_at': item['moved_to'], 'why': item['kind']}
             for item in moved if item['kind'] in PERSONAL_KINDS]
    listed = {item['path'] for item in items}
    for rel in retire_edited:
        if rel not in listed:
            items.append({'path': rel, 'saved_at': saved_location(moved, rel), 'why': KIND_RETIRED_EDITED})
    for rel in retire_added:
        if rel not in listed:
            items.append({'path': rel, 'saved_at': saved_location(moved, rel), 'why': KIND_RETIRED_ADDED})
    return items


def _record_install(root, kit, workspace_id, previous_rel, source_label):
    files = {}
    for rel in sorted(kit.files):
        if member_owned(rel):
            continue
        path = root / rel
        try:
            files[rel] = sha256_file(path) if path.is_file() else None
        except OSError:
            files[rel] = None
    record = {
        'schema': 'caiman.kit-install.v2',
        'status': 'COMPLETE_ARCHIVE_INSTALLED',
        'tier': kit.tier, 'version': kit.version, 'release': kit.release,
        'installed_at': now_utc(), 'installed_by': 'kit-sync ' + PROGRAM_VERSION,
        'source': source_label or kit.source,
        'workspace_id': workspace_id, 'guidance_relative': '.',
        'previous_kit_folder': previous_rel,
        'about': 'The kit files this install placed, for reference. Nothing checks this list, so editing kit files is fine.',
        'files': files,
    }
    folder = root / '.caiman' / 'kit-installations'
    path = unique_path(folder / '{}-{}-{}.json'.format(kit.tier, kit.version or 'unversioned', stamp()))
    write_new(path, json_bytes(record))
    return path.relative_to(root).as_posix()


# ---------------------------------------------------------------- the VIP Machine

def routines_on(machine):
    """Names of the routines switched on in the VIP Machine's settings."""
    config = as_dict(read_json(machine / 'config' / 'brand.json'))
    tasks = as_dict(as_dict(config.get('schedule')).get('tasks'))
    return [label for key, label in ROUTINES if as_dict(tasks.get(key)).get('enabled') is True]


def machine_preview(machine, template):
    """How many of the VIP Machine's kit files differ from template (relative path -> bytes), read-only."""
    differ = []
    for rel, data in sorted(template.items()):
        if is_junk(rel):
            continue
        target = machine / rel
        try:
            same = target.is_file() and target.stat().st_size == len(data) and target.read_bytes() == data
        except OSError:
            same = False
        if not same:
            differ.append(rel)
    return {'files_differ': len(differ), 'examples': differ[:5], 'routines_on': routines_on(machine)}


def folder_template(folder):
    """relative path -> bytes for the files of a machine template folder on disk."""
    files = {}
    if folder.is_dir() and not folder.is_symlink():
        for path in folder.rglob('*'):
            rel = path.relative_to(folder).as_posix()
            if path.is_file() and not path.is_symlink() and not is_junk(rel):
                try:
                    files[rel] = path.read_bytes()
                except OSError:
                    continue
    return files


def machine_command(root):
    return 'python3 "{}" update --project-root "{}"'.format(root / 'RUNTIME_UPDATE.py', root)


def vip_machine_step(root, kit, dry_run):
    """After a VIP install, bring the business's VIP Machine up to the kit with RUNTIME_UPDATE.py update."""
    if kit.tier != 'vip':
        return None
    machine = root / MACHINE_DIR
    if machine.is_symlink() or not (machine / 'engine' / 'vip_machine.py').is_file():
        return None
    command = machine_command(root)
    if dry_run:
        prefix = MACHINE_TEMPLATE + '/'
        template = {rel[len(prefix):]: data for rel, data in kit.files.items() if rel.startswith(prefix)}
        preview = machine_preview(machine, template)
        preview.update(status='planned', command=command)
        return preview
    version = parse_version(kit.core_version or kit.version or '')
    script = root / 'RUNTIME_UPDATE.py'
    if version is None or version < (0, 3, 0) or not script.is_file():
        return None                       # kits before 0.3.0 update their machine with their own steps
    detail = ''
    data = None
    try:
        proc = subprocess.run([sys.executable, str(script), 'update', '--project-root', str(root)],
                              capture_output=True, text=True, timeout=900, cwd=str(root),
                              env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
        out = (proc.stdout or '').strip()
        try:
            data = json.loads(out) if out else None
        except ValueError:
            data = None
        detail = ((proc.stderr or '').strip() or out)[-400:]
    except (OSError, subprocess.SubprocessError) as error:
        detail = str(error)
    if not isinstance(data, dict):
        return {'status': 'needs_attention', 'command': command, 'member_summary': [],
                'error': "The VIP Machine update didn't finish ({}).".format(detail or 'no result'),
                'next_step': 'Run the command below before any other VIP Machine work.'}
    runtime_status = data.get('status')
    status = {'UPDATED': 'updated', 'UP_TO_DATE': 'current', 'NO_MACHINE': 'none'}.get(runtime_status, 'needs_attention')
    return dict(data, status=status, runtime_status=runtime_status, command=command)


# ---------------------------------------------------------------- the summary

def _personal_line(item, dry_run):
    path, saved, why = item['path'], item['saved_at'] or PREVIOUS_DIR + '/', item['why']
    verb = 'would be saved' if dry_run else 'is saved'
    if why == KIND_EDITED and path.startswith(KIT_SKILLS + '/') and path.count('/') >= 3:
        name = path.split('/')[2]
        return ('You had changed {} in the {} skill; your version {} at {}. To keep a change for good, put it in '
                'CLIENT_RULES.md, which updates never touch.'.format(path, name, verb, saved))
    if why == KIND_EDITED:
        return 'You had changed {}; your version {} at {}.'.format(path, verb, saved)
    if why == KIND_RETIRED_EDITED:
        return 'You had changed {}, which the kit no longer includes; your version {} at {}.'.format(path, verb, saved)
    if why == KIND_SKILL_CHANGED:
        name = path.rsplit('/', 1)[-1]
        return ("{} differs from every copy of the {} skill Caiman shipped, so it may have your changes; it {} at {}. "
                "The kit's current {} skill is installed in its place. To keep a change for good, put it in "
                'CLIENT_RULES.md, which updates never touch.'.format(path, name, verb, saved, name))
    if why == KIND_RETIRED_ADDED:
        where = 'the folder it was in' if '/' in path else 'a file by that name'
        return ("{} isn't a file Caiman installed, and the kit no longer includes {}; it {} at "
                '{}.'.format(path, where, verb, saved))
    if why == KIND_TIER_STATE:
        return ("{} held the first-week progress for the other membership, which this kit's guide can't read; it {} "
                'at {}. The new guide starts its own.'.format(path, verb, saved))
    if why == KIND_UNRECORDED:
        return ('{} was already here, with no record of a Caiman install putting it there, so it may be yours. The '
                'kit uses that name, so this copy {} at {}.'.format(path, verb, saved))
    what = 'folder' if why == KIND_IN_WAY_FOLDER else 'file'
    return '{} was in the way of a kit {}; it {} at {}.'.format(path, what, verb, saved)


def _kept_line(item, when='done'):
    """One plain sentence about a skill copy that stays where it is: after an install ('done'), in a
    dry run ('plan'), or in a status check before an install ('status')."""
    path, name, state = item['path'], item.get('name'), item['state']
    leave = {'done': 'I left it', 'plan': 'the install would leave it', 'status': 'the install leaves it'}[when]
    if item.get('shadows_plugin_skill'):
        if state == 'link':
            return ('{} is a link to another folder, so {} as it is. Claude may use what it points to instead of '
                    "Caiman's updated {} skill. I can move the link to {}/ (nothing is deleted) so Caiman's version "
                    'is used.'.format(path, leave, name, PREVIOUS_DIR))
        return ("{} is your own edited version of the {} skill (it doesn't match any copy Caiman shipped), so {} "
                "where it is. Claude may use your version instead of Caiman's updated {} skill. I can move it to "
                "{}/ (nothing is deleted) so Caiman's version is used.".format(path, name, leave, name, PREVIOUS_DIR))
    if state == 'changed':
        return ('{} differs from the copy Caiman unpacked there, so it may have your changes; {} in place. Caiman '
                'no longer uses {}.'.format(path, leave, TOOLS_CACHE))
    return "{} isn't a copy Caiman made, so {} in place.".format(path, leave)


def _machine_lines(machine, dry_run):
    if not machine or machine.get('status') == 'none':
        return []
    if dry_run or machine.get('status') == 'planned':
        lines = []
        if machine.get('files_differ'):
            lines.append('- VIP Machine: {} of its code, guide and template files differ from this kit. The install '
                         'would update them with the kit\'s RUNTIME_UPDATE.py, keeping each replaced file in a '
                         'backup.'.format(machine['files_differ']))
        if machine.get('routines_on'):
            lines.append('- Routines switched on in the VIP Machine settings: {}. The install keeps a routine on only '
                         'when a schedule you approved shows it, and switches the others off.'.format(
                             names_in_words(machine['routines_on'])))
        return lines
    if machine.get('status') == 'needs_attention':
        return ['- VIP Machine: not updated yet. {}'.format(machine.get('error') or 'The update did not finish.')]
    return ['- VIP Machine: ' + line for line in machine.get('member_summary') or []]


def _summary(result, current, kit, dry_run, already_current=False):
    counts = result['counts']
    if already_current:
        lines = ['The {} is already installed in {} and no kit file needed changing.'.format(kit.label, result['folder'])]
    else:
        if dry_run:
            verb = 'Would install'
        elif not current['present']:
            verb = 'Installed'
        elif current.get('tier') and current['tier'] != kit.tier:
            verb = 'Switched to'
        elif current.get('version') == kit.version and current.get('layout') == 'in-folder':
            verb = 'Repaired'
        else:
            verb = 'Updated to'
        lines = ['{} the {} in {}.'.format(verb, kit.label, result['folder']),
                 '- Kit files: {} added, {} updated, {} already current.'.format(counts['added'], counts['updated'],
                                                                                   counts['unchanged'])]
        if current.get('layout') == 'side-by-side':
            lines.append('- The kit an older installer had put in {} was replaced by this kit in the business folder '
                         'itself.'.format(current['guide']))
    if result.get('skills_installed'):
        lines.append('- Skills: {} {} in {}/, where Claude finds them.'.format(
            plural(result['skills_installed'], 'Caiman skill'), 'would be' if dry_run else 'are', KIT_SKILLS))
    where = result.get('previous_kit_folder') or PREVIOUS_DIR
    moved = [item for item in result.get('moved') or [] if item['kind'] != CLAUDE_MOVED]
    grouped = [item for item in moved if item['kind'] not in PERSONAL_KINDS]
    if grouped:
        lines.append('- {} to {}/ ({}):'.format('Would move' if dry_run else 'Moved', where,
                                                'nothing would be deleted' if dry_run else 'nothing was deleted'))
        groups = {}
        for item in grouped:
            groups.setdefault(item['kind'], []).append(item['path'])
        for kind, paths in groups.items():
            lines.append('  - {}: {}'.format(kind, listing(paths)))
    unrecorded = [item for item in result.get('your_files') or [] if item['why'] == KIND_UNRECORDED]
    added_in_retired = [item for item in result.get('your_files') or [] if item['why'] == KIND_RETIRED_ADDED]
    shown_items = [item for item in result.get('your_files') or []
                   if not (item['why'] == KIND_UNRECORDED and len(unrecorded) > 8)
                   and not (item['why'] == KIND_RETIRED_ADDED and len(added_in_retired) > 8)]
    for item in shown_items:
        lines.append('- ' + _personal_line(item, dry_run))
    if len(added_in_retired) > 8:
        lines.append("- {} files that Caiman didn't install were inside kit parts the kit no longer includes: {}. "
                     'They {} in {}/.'.format(len(added_in_retired), listing([item['path'] for item in added_in_retired]),
                                              'would be saved' if dry_run else 'are saved', where))
    if len(unrecorded) > 8:
        lines.append('- {} files were already here under kit file names, with no record of a Caiman install putting '
                     'them there, so some may be yours: {}. The kit uses those names, so these copies {} in {}/.'.format(
                         len(unrecorded), listing([item['path'] for item in unrecorded]),
                         'would be saved' if dry_run else 'are saved', where))
    for item in result.get('skill_copies_kept') or []:
        lines.append('- ' + _kept_line(item, 'plan' if dry_run else 'done'))
    for item in result.get('left_in_place') or []:
        lines.append("- {} differs from what Caiman shipped, so {} in place. Caiman no longer uses the {} "
                     'folder.'.format(item['path'], 'the install would leave it' if dry_run else 'I left it',
                                      OLD_SKILLS_FOLDER))
    lines += _machine_lines(result.get('vip_machine'), dry_run)
    if result.get('claude_md', 'unchanged') != 'unchanged':
        saved = next((item['moved_to'] for item in result.get('moved') or [] if item['kind'] == CLAUDE_MOVED), None)
        lines.append('- CLAUDE.md: {}.{}'.format(result['claude_md'], ' The previous version {} kept at {}.'.format(
            'would be' if dry_run else 'is', saved) if saved else ''))
    if result.get('skipped_member_paths'):
        lines.append("- Left alone (these belong to the member, not the kit): " + listing(result['skipped_member_paths'], 10))
    for note in result.get('notes') or []:
        lines.append('- Note: ' + note)
    # CLAUDE.md holds the member's notes: when it was merged, it is one of the files named above.
    claude_merged = any(item['kind'] == CLAUDE_MOVED for item in result.get('moved') or [])
    personal = bool(result.get('your_files')) or claude_merged
    if personal:
        lines.append('- Apart from the files named above, your own files {} as they were.'.format(
            'would stay' if dry_run else 'were left'))
    else:
        lines.append('- Your own files {} as they were.'.format('would stay' if dry_run else 'were left'))
    if not dry_run:
        machine = result.get('vip_machine') or {}
        if machine.get('status') == 'needs_attention':
            lines.append('Next: update the VIP Machine before any other VIP Machine work: ' + machine['command'])
        else:
            lines.append("Next: run CLIENT_START.py from the business folder with the member's request.")
    return '\n'.join(lines)


# ---------------------------------------------------------------- status

def kit_status(folder, plugin=None, tier=None):
    root = Path(folder).expanduser()
    if not root.is_dir():
        raise KitSyncError("I can't find the business folder {}. Check the path, or create the folder first."
                           .format(root))
    root = root.resolve()
    current = installed_kit(root)
    want_tier = tier or (plugin or {}).get('tier')
    want_version = (plugin or {}).get('version')
    names = set((plugin or {}).get('skills') or []) | set(PLUGIN_OWN_SKILLS)
    listed = as_dict(read_json(root / 'ENTITLEMENTS.json')).get('skills')
    listed = sorted(name for name in listed if isinstance(name, str)) if isinstance(listed, list) else []
    names |= set(listed)
    have = parse_version(current.get('core_version') or '')
    kit_has_skills = bool(have and have >= (0, 3, 1))
    copies = find_skill_copies(root, names, (plugin or {}).get('root'), listed if kit_has_skills else ())
    retired = [rel for rel in RETIRED_TOP if exists(root / rel)]
    need = parse_version(want_version or '')
    side = current.get('layout') == 'side-by-side'
    if not current['present']:
        verdict = 'missing'
        advice = 'There is no Caiman kit in this folder yet. Install it with kit-sync.'
    elif want_tier and current['tier'] and current['tier'] != want_tier:
        verdict = 'other-tier'
        advice = ('This folder has the {} kit, but this plugin is {}. Switching keeps the member\'s files; '
                  'confirm with the member before installing with --switch-tier.'.format(tier_name(current['tier']),
                                                                                         tier_name(want_tier)))
    elif side or have is None or (need is not None and have < need):
        verdict = 'older'
        advice = ('The kit is older than this plugin. Update it with kit-sync.' if need is not None else
                  'The kit is from before Caiman 0.3.1. Update it with kit-sync from the Caiman plugin.')
        if side:
            advice = ('An older installer put this kit beside the business files in {}. Update it with kit-sync: the '
                      'current kit goes into the business folder itself, the member\'s files stay, and the older copy '
                      'moves to {}/.'.format(current['guide'], PREVIOUS_DIR))
    elif need is not None and have > need:
        verdict = 'newer'
        advice = 'The kit is newer than this plugin. Update the Caiman plugin when you can; the kit can stay.'
    else:
        verdict = 'current'
        advice = 'The kit is current.'
    missing_skills = []
    if verdict == 'current' and kit_has_skills:
        missing_skills = [name for name in listed if not (root / KIT_SKILLS / name / 'SKILL.md').is_file()]
        if missing_skills:
            verdict = 'skills-missing'
            advice = ('The kit is current, but {} of its skills {} missing from {}/ ({}). Run the kit-sync install '
                      'again to put them back.'.format(len(missing_skills), 'is' if len(missing_skills) == 1 else 'are',
                                                       KIT_SKILLS, listing(missing_skills)))
    machine = None
    machine_folder = root / MACHINE_DIR
    if current['present'] and current['tier'] == 'vip' and (machine_folder / 'engine' / 'vip_machine.py').is_file():
        if verdict == 'current':
            machine = machine_preview(machine_folder, folder_template(root / MACHINE_TEMPLATE))
            if machine['files_differ']:
                verdict = 'vip-machine-older'
                advice = ('The kit is current, but the VIP Machine is older than the kit ({} of its files differ). Run '
                          'the kit-sync install again: it updates the VIP Machine, keeping each replaced file in a '
                          'backup.'.format(machine['files_differ']))
        else:
            machine = {'files_differ': None, 'routines_on': routines_on(machine_folder)}
    if verdict == 'current' and (copies['move'] or retired):
        advice += ' Running the install again tidies up the old copies listed below.'
    if side:
        shown = ('release ' + current['release']) if current['release'] else (current['version'] or 'no version')
        kit_line = '{} ({}), installed beside the business files in {} by an older installer'.format(
            tier_name(current['tier']), shown, current['guide'])
    else:
        shown = current['version'] or (current['release'] and 'release ' + current['release']) or 'no version'
        kit_line = '{} ({})'.format(tier_name(current['tier']), shown) if current['present'] else 'none'
    lines = ['Business folder: {}'.format(root),
             'Kit in this folder: {}'.format(kit_line),
             'This plugin: {}'.format('{} {}'.format(tier_name(want_tier), want_version or '').strip() if want_tier
                                      else ('Caiman {}'.format(want_version) if want_version else 'not found')),
             advice]
    if copies['move']:
        lines.append('Unchanged skill copies from earlier Caiman kits (the install moves them to {}): {}'.format(
            PREVIOUS_DIR, ', '.join(item['path'] for item in copies['move'])))
    for item in copies['kept']:
        lines.append(_kept_line(item, 'status'))
    if not kit_has_skills and (root / KIT_SKILLS).is_dir() and not (root / KIT_SKILLS).is_symlink():
        for child in sorted((root / KIT_SKILLS).iterdir(), key=lambda p: p.name):
            if child.name in SHIPPED_SKILL_TREES and child.is_dir() and not child.is_symlink():
                if copy_state(child, {child.name}) != 'unchanged':
                    lines.append('{}/{} differs from every copy Caiman shipped, so it may have your changes. The '
                                 "install saves it in {}/ and puts the kit's version in its place.".format(
                                     KIT_SKILLS, child.name, PREVIOUS_DIR))
    if retired:
        lines.append('Retired kit parts still here (the install moves them to {}): {}'.format(
            PREVIOUS_DIR, ', '.join(retired)))
    if machine:
        if machine.get('files_differ') is None and verdict in ('older', 'other-tier'):
            lines.append('VIP Machine: the install also updates it to the new kit, keeping each replaced file in a backup.')
        if machine.get('routines_on'):
            lines.append('Routines switched on in the VIP Machine settings: {}. The install keeps a routine on only when '
                         'a schedule the member approved shows it, and switches the others off.'.format(
                             names_in_words(machine['routines_on'])))
    return {'folder': str(root), 'status': verdict, 'installed': current, 'plugin_tier': want_tier,
            'plugin_version': want_version, 'missing_skills': missing_skills,
            'old_skill_copies': [item['path'] for item in copies['move']],
            'skill_copies_kept': copies['kept'], 'retired_parts': retired, 'vip_machine': machine,
            'message': '\n'.join(lines)}


# ---------------------------------------------------------------- move-aside

ASIDE_PLACES = ('.claude/skills/', '.agents/skills/', OLD_SKILLS_FOLDER + '/')


def kit_owns_skill(root, name):
    """True when the installed kit (0.3.1 or later) ships this skill in .claude/skills/."""
    have = parse_version(core_version_of(as_dict(read_json(root / 'RELEASE_MANIFEST.json'))) or '')
    listed = as_dict(read_json(root / 'ENTITLEMENTS.json')).get('skills')
    return bool(have and have >= (0, 3, 1) and isinstance(listed, list) and name in listed)


def move_aside(folder, paths, dry_run=False):
    """Move skill copies the member no longer wants into _previous-kit/<date>/ (only after they agree)."""
    root = Path(folder).expanduser()
    if not root.is_dir():
        raise KitSyncError("I can't find the business folder {}. Check the path.".format(root))
    root = root.resolve()
    chosen = []
    for raw in paths:
        rel = clean_rel(raw)
        allowed = rel and (rel == TOOLS_CACHE or rel.startswith(TOOLS_CACHE + '/')
                           or any(rel.startswith(place) and len(rel) > len(place) for place in ASIDE_PLACES))
        if not allowed:
            raise KitSyncError('move-aside only moves old skill copies: something inside .claude/skills/, '
                               '.agents/skills/, Skills/ or .caiman-tools/. {} is not one of those, so nothing was '
                               'moved.'.format(raw))
        if not exists(root / rel):
            raise KitSyncError("There's nothing at {} in the business folder, so nothing was moved.".format(rel))
        if rel.startswith(KIT_SKILLS + '/') and rel.count('/') == 2 and kit_owns_skill(root, rel.rsplit('/', 1)[1]):
            raise KitSyncError("{} is the kit's own copy of that skill, and Caiman needs it. To use a change of your "
                               'own, put it in CLIENT_RULES.md, which updates never touch.'.format(rel))
        chosen.append(rel)
    previous = PreviousKit(root, dry_run)
    for rel in dict.fromkeys(chosen):
        if rel.startswith(('.claude/skills/', '.agents/skills/')):
            dest = 'skills/' + rel.split('/', 2)[2]
        elif rel.startswith(TOOLS_CACHE):
            dest = 'caiman-tools' + rel[len(TOOLS_CACHE):]
        else:
            dest = rel
        previous.move(rel, KIND_ASIDE, dest)
    lines = ['{} to {}/ ({}):'.format('Would move' if dry_run else 'Moved', previous.relative or PREVIOUS_DIR,
                                      'nothing would be deleted' if dry_run else 'nothing was deleted')]
    for item in previous.moved:
        lines.append('- {} -> {}'.format(item['path'], item['moved_to']))
        name = item['path'].split('/')[2] if item['path'].startswith(('.claude/skills/', '.agents/skills/')) else None
        if name:
            name = name[:-6] if name.endswith('.skill') else name
            lines.append("  Claude now uses Caiman's own {} skill.".format(name))
    return {'folder': str(root), 'status': 'planned' if dry_run else 'moved', 'moved': previous.moved,
            'previous_kit_folder': previous.relative, 'message': '\n'.join(lines)}


# ---------------------------------------------------------------- command line

def _add_common(parser):
    parser.add_argument('--tier', help='vip or gls-plus. Normally the kit decides; use this to insist on one.')
    parser.add_argument('--plugin-root', help='The Caiman plugin folder, when this file was copied elsewhere.')
    parser.add_argument('--json', action='store_true', help='Print the result as JSON.')


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest='command', required=True)

    status = commands.add_parser('status', help='Show which kit is in the business folder and whether it is current.')
    status.add_argument('--folder', '--root', '--project-root', dest='folder', required=True,
                        help='The business folder.')
    _add_common(status)

    install_cmd = commands.add_parser('install', help='Install or update the kit in the business folder.')
    install_cmd.add_argument('--folder', '--root', '--project-root', dest='folder', required=True,
                             help='The business folder.')
    source = install_cmd.add_mutually_exclusive_group(required=True)
    source.add_argument('--zip', help='A kit zip the member supplied.')
    source.add_argument('--descriptor', help="The saved result of the Caiman connector's get_kit_download tool.")
    source.add_argument('--url', help='A Caiman kit download link (use --sha256 with it when you have one).')
    install_cmd.add_argument('--sha256', help='Checksum to check the zip or download against, when you have one.')
    install_cmd.add_argument('--switch-tier', action='store_true',
                             help='Replace the other tier\'s kit in this folder (only after the member agrees).')
    install_cmd.add_argument('--dry-run', action='store_true', help='Show what would change without changing anything.')
    _add_common(install_cmd)

    download = commands.add_parser('download', help='Download the kit zip from the Caiman server without installing it.')
    group = download.add_mutually_exclusive_group(required=True)
    group.add_argument('--descriptor', help="The saved result of the Caiman connector's get_kit_download tool.")
    group.add_argument('--url', help='A Caiman kit download link.')
    download.add_argument('--sha256', help='Checksum to check the download against, when you have one.')
    download.add_argument('--out', '--staging', dest='out', help='Folder to save the zip in (default: a temporary folder).')
    _add_common(download)

    aside = commands.add_parser('move-aside', help="Move an old skill copy the member doesn't want into _previous-kit/ "
                                                   '(only after the member agrees).')
    aside.add_argument('--folder', '--root', '--project-root', dest='folder', required=True, help='The business folder.')
    aside.add_argument('--path', action='append', required=True,
                       help='The copy to move, for example ".claude/skills/advertising-agent". Repeat for more.')
    aside.add_argument('--dry-run', action='store_true', help='Show what would move without moving anything.')
    _add_common(aside)
    return parser


def _emit(result, as_json):
    if as_json:
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    else:
        print(result['message'])


def main(argv=None):
    args = build_parser().parse_args(argv)
    as_json = getattr(args, 'json', False)
    downloaded_dir = None
    keep_download = False
    stopped = {'status': 'Kit check stopped: ', 'download': 'Kit download stopped: ',
               'move-aside': 'Nothing was moved: '}.get(args.command, 'Kit install stopped: ')
    try:
        tier = None
        if args.tier:
            tier = norm_tier(args.tier)
            if not tier:
                raise KitSyncError('--tier must be vip or gls-plus.')
        if args.command == 'move-aside':
            _emit(move_aside(args.folder, args.path, args.dry_run), as_json)
            return 0
        plugin = find_plugin(args.plugin_root)
        if args.command == 'status':
            _emit(kit_status(args.folder, plugin, tier), as_json)
            return 0
        want_tier = tier or (plugin or {}).get('tier')
        file_name = (plugin or {}).get('kit_zip') if (plugin and (not tier or tier == plugin['tier'])) else None
        if args.command == 'download':
            result = download_kit(args.descriptor, args.url, args.sha256, args.out, want_tier, file_name)
            result['message'] = 'Downloaded the kit zip to {} ({:,} bytes{}).'.format(
                result['path'], result['bytes'], ', checksum matched' if result['checksum_checked'] else '')
            _emit(result, as_json)
            return 0
        if args.zip:
            zip_path, source_label = Path(args.zip).expanduser(), Path(args.zip).name
            if args.sha256:
                if not re.fullmatch(r'[0-9a-fA-F]{64}', args.sha256.strip()):
                    raise KitSyncError('--sha256 must be the 64-character SHA-256 value.')
                if zip_path.is_file() and sha256_file(zip_path) != args.sha256.strip().lower():
                    raise KitSyncError("{} doesn't match the checksum you gave, so I didn't install it. It may be "
                                       'incomplete or a different file. Nothing was changed. Download the zip again '
                                       'from the Caiman account.'.format(zip_path.name))
        else:
            downloaded_dir = Path(tempfile.mkdtemp(prefix='caiman-kit-'))
            fetched = download_kit(args.descriptor, args.url, args.sha256, downloaded_dir, want_tier, file_name)
            zip_path, source_label = Path(fetched['path']), 'Caiman server download'
        kit = read_kit_zip(zip_path, (plugin or {}).get('kit_folder'))
        try:
            result = install(args.folder, kit, plugin, tier, args.switch_tier, args.dry_run, source_label)
        except KitSyncError:
            keep_download = downloaded_dir is not None
            raise
        _emit(result, as_json)
        return 0
    except KitSyncError as error:
        message = str(error)
        if keep_download and downloaded_dir is not None:
            saved = next(downloaded_dir.glob('*.zip'), None)
            if saved:
                message += ('\nThe downloaded kit is saved at {}. To use it again without a new link, run the '
                            'install with --zip "{}".'.format(saved, saved))
        if as_json:
            print(json.dumps({'status': 'needs-confirmation' if error.exit_code == 3 else 'error',
                              'message': message}, indent=2, ensure_ascii=False))
        else:
            print(("Needs the member's OK: " if error.exit_code == 3 else stopped) + message)
        return error.exit_code
    finally:
        if downloaded_dir is not None and not keep_download:
            shutil.rmtree(downloaded_dir, ignore_errors=True)


if __name__ == '__main__':
    raise SystemExit(main())
