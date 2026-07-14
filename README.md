# Caiman Data — Claude Plugin Marketplace

The official [Caiman Data](https://tools.caimandata.ai) plugin marketplace for
Claude (Cowork and Claude Code). One install connects Claude to your Caiman
Amazon tools and keeps your skills current automatically — no downloads, no
zip files, nothing to reinstall.

## Install (Claude Cowork)

1. Open the **Customize** menu → **Plugins**.
2. Under **Personal plugins**, click **+** → **Add marketplace** → **Add from a
   repository**, and enter:

   ```
   VoltageDM/caimandata-AI-plugin
   ```

3. Install **Caiman Core**, and turn on auto-update for the marketplace.
4. The first time a Caiman tool runs, your browser opens a Caiman Data login —
   sign in and click **Allow**. That's it.

## Install (Claude Code)

```
claude plugin marketplace add VoltageDM/caimandata-AI-plugin
claude plugin install caiman-core@caimandata
```

## What's inside

| Plugin | What it does |
|---|---|
| `caiman-core` | Connects the Caiman Amazon tools (`mcp-amazon.caimandata.ai`) and teaches Claude to use the live Caiman skill library, gated by your subscription. |

Your subscription controls what the tools and skill library return — this
repository contains no credentials and nothing customer-specific.

*Questions? support@caimandata.com*
