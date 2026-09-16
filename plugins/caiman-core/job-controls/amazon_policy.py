"""Amazon-specific selectors and operation classes, outside the generic ledger."""
from job_engine import Refusal, require, digest


def classify(policy, tool, inputs):
    require(isinstance(inputs, dict), "INVALID_OPERATION", "Tool arguments must be an object.")
    if tool in ("Agent", "Task"):
        return {"kind": "worker_spawn", "requires_scope": False}
    short = None
    for prefix in policy["tool_prefixes"]:
        if tool.startswith(prefix):
            short = tool[len(prefix):]
            break
    if short is None:
        return {"kind": "tool", "requires_scope": False}
    rules = policy["tools"]
    rule = rules.get(short)
    # This layer never grants a new tool or authorizes a consequential write.
    # The installed adapter's existing gate remains authoritative for those.
    existing_gate = rule is None
    if rule is None:
        if not any(key in inputs for key in policy["brand_keys"]):
            return {"kind": "existing_gate", "requires_scope": False}
        rule = {"scope": "required", "operation": "existing_gate"}
    if rule["scope"] == "global":
        return {"kind": "read", "requires_scope": False}
    selectors = [inputs[k] for k in policy["brand_keys"] if k in inputs]
    require(all(isinstance(x, str) and x for x in selectors)
            and len(set(selectors)) <= 1, "BRAND_SELECTOR_CONFLICT",
            "Brand selectors must identify one exact connector slug.")
    marketplaces = [inputs[k] for k in policy["marketplace_keys"] if k in inputs]
    require(all(isinstance(x, str) and x for x in marketplaces)
            and len(set(marketplaces)) <= 1, "MARKETPLACE_SELECTOR_CONFLICT",
            "Marketplace selectors must identify one exact marketplace.")
    scope = None
    if selectors:
        choices = [x for x in policy["scopes"] if x["brand_slug"] == selectors[0]
                   and (not marketplaces or x["marketplace_id"] == marketplaces[0])]
        require(len(choices) == 1, "BRAND_SCOPE_UNRESOLVED",
                "The brand/marketplace does not resolve to one canonical connector scope.")
        scope = choices[0]
    report_ids = [inputs[k] for k in policy["report_keys"] if k in inputs and inputs[k] is not None]
    require(all(isinstance(x, str) and 0 < len(x) <= 256 for x in report_ids)
            and len(set(report_ids)) <= 1, "REPORT_SELECTOR_CONFLICT",
            "Report selectors must identify one exact report.")
    rid = report_ids[0] if report_ids else None
    kind = "existing_gate" if existing_gate else "read"
    if rule["operation"] == "report":
        kind = "report_poll" if rid else "report_dispatch"
    elif rule["operation"] == "poll":
        require(rid is not None, "REPORT_ID_REQUIRED", "An existing report identifier is required.")
        kind = "report_poll"
    require(scope is not None or kind == "report_poll", "BRAND_SCOPE_REQUIRED",
            "This read requires its exact connector brand slug.")
    signature = {k:v for k,v in inputs.items() if not (k in policy['report_keys'] and v is None)}
    return {"kind": kind, "scope": scope, "report_id": rid,
            "dedup_input_sha": digest(signature),
            "requires_known_report": not bool(selectors),
            "canonical_tool": short, "requires_scope": True}
