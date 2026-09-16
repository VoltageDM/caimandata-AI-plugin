"""Durable job admission; no model, network, credentials, or business writes.

Callers supply an authenticated native context and an immutable domain policy.
The ledger records reservations and observations, never mission acceptance.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
import sqlite3
import stat
import time


class Refusal(Exception):
    def __init__(self, code, detail, **data):
        self.result = {"allowed": False, "code": code, "detail": detail, **data}
        super().__init__(code)


def require(condition, code, detail):
    if not condition:
        raise Refusal(code, detail)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


LIMITS = {
    "runs": (1, 256), "members": (1, 64), "depth": (0, 32),
    "tools": (1, 4096), "report_dispatches": (1, 512),
    "report_polls": (1, 256), "lifetime_seconds": (30, 86400),
    "poll_interval_seconds": (0, 3600),
}


def validate_limits(limits):
    require(isinstance(limits, dict) and set(limits) == set(LIMITS),
            "INVALID_POLICY", "The complete finite job limit set is required.")
    for key, (low, high) in LIMITS.items():
        require(type(limits[key]) is int and low <= limits[key] <= high,
                "INVALID_POLICY", "A job limit is outside its permitted range.")


class Ledger:
    def __init__(self, path, *, now=time.time):
        self.path = Path(path)
        self.now = now
        require(self.path.is_absolute() and self.path.resolve() == self.path,
                "INVALID_LEDGER", "The ledger must use its canonical absolute path.")
        require(self.path.parent.is_dir() and not self.path.is_symlink(),
                "INVALID_LEDGER", "The installed ledger directory is required.")
        if self.path.exists():
            info = self.path.stat()
            require(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid()
                    and not info.st_mode & 0o077,
                    "INVALID_LEDGER", "The ledger must be a private owner-held file.")
        else:
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(fd)
        self.db = sqlite3.connect(str(self.path), timeout=1.5, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS jobs (
            job_key TEXT PRIMARY KEY, room TEXT NOT NULL, source_id INTEGER NOT NULL,
            source_sha TEXT NOT NULL, policy_sha TEXT NOT NULL, policy_json TEXT NOT NULL,
            scopes_json TEXT NOT NULL, created REAL NOT NULL, expires REAL NOT NULL,
            checkpoint_json TEXT, UNIQUE(room,source_id)
        );
        CREATE TABLE IF NOT EXISTS runs (
            job_key TEXT NOT NULL REFERENCES jobs(job_key), run_id INTEGER NOT NULL,
            member_id TEXT NOT NULL, attempt_sha TEXT NOT NULL, native_session TEXT,
            started REAL NOT NULL, PRIMARY KEY(job_key,run_id)
        );
        CREATE TABLE IF NOT EXISTS operations (
            op_key TEXT PRIMARY KEY, room TEXT NOT NULL, run_id INTEGER NOT NULL,
            member_id TEXT NOT NULL, attempt_sha TEXT NOT NULL, tool_id TEXT NOT NULL,
            tool TEXT NOT NULL, input_sha TEXT NOT NULL, kind TEXT NOT NULL,
            scope_json TEXT, dedup_sha TEXT, report_id TEXT, state TEXT NOT NULL,
            created REAL NOT NULL, completed REAL, result_sha TEXT, result_status TEXT,
            UNIQUE(room,run_id,tool_id)
        );
        CREATE TABLE IF NOT EXISTS operation_jobs (
            op_key TEXT NOT NULL REFERENCES operations(op_key),
            job_key TEXT NOT NULL REFERENCES jobs(job_key),
            PRIMARY KEY(op_key,job_key)
        );
        CREATE INDEX IF NOT EXISTS operation_dedup ON operations(dedup_sha);
        CREATE TABLE IF NOT EXISTS decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT, at REAL NOT NULL,
            room TEXT NOT NULL, run_id INTEGER NOT NULL, code TEXT NOT NULL,
            detail TEXT NOT NULL, jobs_json TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS budget_revisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT, job_key TEXT NOT NULL REFERENCES jobs(job_key),
            request_sha TEXT NOT NULL, limits_json TEXT NOT NULL, reason TEXT NOT NULL,
            source_ref_json TEXT NOT NULL, at REAL NOT NULL, UNIQUE(job_key,request_sha)
        );
        """)

    def close(self):
        self.db.close()

    def _transaction(self, callback):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            result = callback()
            self.db.execute("COMMIT")
            return result
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    @staticmethod
    def job_key(room, root):
        return digest({"room": room, "source_id": root["id"]})

    def _jobs(self, ctx, policy):
        limits = policy["limits"]
        validate_limits(limits)
        require(len(ctx["roots"]) in range(1, 17), "INVALID_LINEAGE",
                "One to sixteen exact native roots are required.")
        now = self.now()
        psha = digest(policy)
        jobs = []
        for root in ctx["roots"]:
            limits = policy['limits']
            key = self.job_key(ctx["room"], root)
            row = self.db.execute("SELECT * FROM jobs WHERE job_key=?", (key,)).fetchone()
            if row is None:
                scopes = policy["room_scopes"].get(ctx["room"], [])
                self.db.execute("INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?,NULL)",
                                (key, ctx["room"], root["id"], root["sha256"], psha,
                                 canonical(policy), canonical(scopes), now,
                                 now + limits["lifetime_seconds"]))
                row = self.db.execute("SELECT * FROM jobs WHERE job_key=?", (key,)).fetchone()
            require(row["source_sha"] == root["sha256"], "SOURCE_CHANGED",
                    "The native initiating source has changed; preserve its prior job.")
            require(row["policy_sha"] == psha, "JOB_POLICY_CHANGED",
                    "This job is bound to a different policy version.")
            revision = self.db.execute("SELECT limits_json FROM budget_revisions WHERE job_key=? ORDER BY id DESC LIMIT 1", (key,)).fetchone()
            limits = json.loads(revision[0]) if revision else policy['limits']
            validate_limits(limits)
            require(ctx["depth"] <= limits["depth"], "JOB_DEPTH_REACHED",
                    "The native descendant depth limit has been reached.")
            require(now < row["expires"], "JOB_EXPIRED",
                    "The job expired. Its checkpoint and report references are retained.")
            run = self.db.execute("SELECT * FROM runs WHERE job_key=? AND run_id=?",
                                  (key, ctx["run_id"])).fetchone()
            if run:
                require(run["member_id"] == ctx["member_id"]
                        and run["attempt_sha"] == ctx["attempt_sha"],
                        "RUN_REPLACED", "A replaced native run cannot reuse admission.")
            else:
                count = self.db.execute("SELECT count(*) FROM runs WHERE job_key=?", (key,)).fetchone()[0]
                members = {r[0] for r in self.db.execute("SELECT DISTINCT member_id FROM runs WHERE job_key=?", (key,))}
                require(count < limits["runs"], "JOB_RUN_LIMIT_REACHED",
                        "The finite native-run budget has been used.")
                embedded = self.db.execute("SELECT count(*) FROM operations o JOIN operation_jobs j ON j.op_key=o.op_key WHERE j.job_key=? AND o.kind='worker_spawn'", (key,)).fetchone()[0]
                require(ctx["member_id"] in members or len(members) + embedded < limits["members"],
                        "JOB_MEMBER_LIMIT_REACHED", "The finite worker budget has been used.")
                self.db.execute("INSERT INTO runs VALUES(?,?,?,?,?,?)",
                                (key, ctx["run_id"], ctx["member_id"], ctx["attempt_sha"],
                                 ctx.get("native_session"), now))
            jobs.append({**dict(row), 'effective_limits': limits})
        return jobs

    def _refused(self, ctx, error):
        keys = [self.job_key(ctx["room"], r) for r in ctx["roots"]]
        checkpoint = {"state": "PENDING", "reason": error.result["code"],
                      "run_id": ctx["run_id"], "member_id": ctx["member_id"],
                      "observed_at": self.now(), "completion_claimed": False}
        def record():
            self.db.execute("INSERT INTO decisions(at,room,run_id,code,detail,jobs_json) VALUES(?,?,?,?,?,?)",
                            (self.now(), ctx["room"], ctx["run_id"], error.result["code"],
                             error.result["detail"], canonical(keys)))
            for key in keys:
                self.db.execute("UPDATE jobs SET checkpoint_json=? WHERE job_key=?",
                                (canonical(checkpoint), key))
        self._transaction(record)
        return {**error.result, "jobs": keys, "checkpoint": checkpoint}

    def enter(self, ctx, policy, revalidate):
        try:
            def enter():
                revalidate(ctx)
                jobs = self._jobs(ctx, policy)
                revalidate(ctx)
                return {"allowed": True, "code": "JOB_ADMITTED",
                        "jobs": [j["job_key"] for j in jobs],
                        "run_id": ctx["run_id"], "attempt_sha": ctx["attempt_sha"],
                        "expires_at": min(j["expires"] for j in jobs)}
            return self._transaction(enter)
        except Refusal as error:
            return self._refused(ctx, error)

    def admit(self, ctx, policy, tool, tool_id, tool_input, classification, revalidate):
        require(isinstance(tool, str) and 0 < len(tool) <= 240
                and isinstance(tool_id, str) and 0 < len(tool_id) <= 200,
                "INVALID_OPERATION", "An exact bounded tool identity is required.")
        try:
            raw = canonical(tool_input)
        except (ValueError, TypeError, RecursionError):
            raise Refusal("INVALID_OPERATION", "The tool input must be finite JSON.")
        require(len(raw.encode()) <= 262144, "INPUT_TOO_LARGE", "Tool input exceeds the job-control boundary.")
        input_sha = hashlib.sha256(raw.encode()).hexdigest()
        op_key = digest({"room": ctx["room"], "run": ctx["run_id"], "id": tool_id})
        try:
            def admit():
                revalidate(ctx)
                jobs = self._jobs(ctx, policy)
                limits = policy["limits"]
                old = self.db.execute("SELECT * FROM operations WHERE op_key=?", (op_key,)).fetchone()
                if old:
                    require(old["tool"] == tool and old["input_sha"] == input_sha,
                            "TOOL_ID_REUSED", "A tool identifier was reused with different content.")
                    raise Refusal("OPERATION_ALREADY_RESERVED", "The original operation remains recorded; do not replay it.",
                                  original_operation=op_key, original_state=old["state"])
                scope = classification.get("scope")
                kind = classification["kind"]
                report_id = classification.get("report_id")
                dedup = digest({"tool": classification.get("canonical_tool", tool),
                                "input_sha": classification.get('dedup_input_sha', input_sha)}) if kind == "report_dispatch" else None
                for job in jobs:
                    key = job["job_key"]
                    limits = job['effective_limits']
                    if classification.get("requires_scope"):
                        permitted = json.loads(job["scopes_json"])
                        require(scope is not None and scope in permitted, "JOB_SCOPE_MISMATCH",
                                "This brand/marketplace is outside the native job's declared scope.")
                    counts = dict(self.db.execute("SELECT o.kind,count(*) FROM operations o JOIN operation_jobs j ON j.op_key=o.op_key WHERE j.job_key=? GROUP BY o.kind", (key,)))
                    require(sum(counts.values()) < limits["tools"], "JOB_TOOL_LIMIT_REACHED",
                            "The finite tool budget has been used; retain the checkpoint.")
                    if kind == "worker_spawn":
                        require(not classification.get("embedded_worker"), "EMBEDDED_NESTING_NOT_SUPPORTED",
                                "Nested SDK workers must use a separately bound native assignment.")
                        members = self.db.execute("SELECT count(DISTINCT member_id) FROM runs WHERE job_key=?", (key,)).fetchone()[0]
                        require(members + counts.get(kind, 0) < limits["members"], "JOB_MEMBER_LIMIT_REACHED",
                                "The finite native and embedded worker budget has been used.")
                    if kind == "report_dispatch":
                        old = self.db.execute("SELECT o.* FROM operations o JOIN operation_jobs j ON j.op_key=o.op_key WHERE j.job_key=? AND o.dedup_sha=? LIMIT 1", (key, dedup)).fetchone()
                        if old:
                            raise Refusal("REPORT_ALREADY_REQUESTED", "Reuse the recorded report reference. An uncertain response does not authorize another dispatch.",
                                          original_operation=old["op_key"], original_state=old["state"],
                                          report_id=old["report_id"], result_status=old["result_status"])
                        require(counts.get(kind, 0) < limits["report_dispatches"], "REPORT_DISPATCH_LIMIT_REACHED",
                                "The finite report-dispatch budget has been used.")
                    if kind == "report_poll":
                        known = self.db.execute("SELECT o.* FROM operations o JOIN operation_jobs j ON j.op_key=o.op_key WHERE j.job_key=? AND o.report_id=? AND o.scope_json=? AND o.kind='report_dispatch' AND o.state='OBSERVED' LIMIT 1", (key, report_id, canonical(scope))).fetchone()
                        require(known is not None or classification.get("requires_known_report") is False,
                                "REPORT_SCOPE_UNVERIFIED",
                                "This job has no recorded report reference for that scope.")
                        polls = self.db.execute("SELECT count(*),max(o.created) FROM operations o JOIN operation_jobs j ON j.op_key=o.op_key WHERE j.job_key=? AND o.kind='report_poll' AND o.report_id=?", (key, report_id)).fetchone()
                        require(polls[0] < limits["report_polls"], "REPORT_POLL_LIMIT_REACHED",
                                "The finite report-poll budget has been used; retain its pending state.")
                        require(polls[1] is None or self.now() - polls[1] >= limits["poll_interval_seconds"],
                                "REPORT_POLL_TOO_SOON", "Wait for the report's next eligible observation; do not dispatch another report.")
                revalidate(ctx)
                self.db.execute("INSERT INTO operations VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,NULL,NULL,NULL)",
                                (op_key, ctx["room"], ctx["run_id"], ctx["member_id"], ctx["attempt_sha"],
                                 tool_id, tool, input_sha, kind, canonical(scope) if scope else None,
                                 dedup, report_id, "RESERVED", self.now()))
                for job in jobs:
                    self.db.execute("INSERT INTO operation_jobs VALUES(?,?)", (op_key, job["job_key"]))
                return {"allowed": True, "code": "OPERATION_RESERVED", "operation": op_key,
                        "jobs": [j["job_key"] for j in jobs], "kind": kind}
            return self._transaction(admit)
        except Refusal as error:
            return self._refused(ctx, error)

    def observe(self, ctx, tool_id, result, failed, revalidate):
        key = digest({"room": ctx["room"], "run": ctx["run_id"], "id": tool_id})
        def observe():
            revalidate(ctx)
            row = self.db.execute("SELECT * FROM operations WHERE op_key=?", (key,)).fetchone()
            require(row is not None and row["member_id"] == ctx["member_id"]
                    and row["attempt_sha"] == ctx["attempt_sha"], "OBSERVATION_NOT_BOUND",
                    "A result must match its admitted native operation.")
            raw = canonical(result)
            require(len(raw.encode()) <= 16 * 1024 * 1024, "RESULT_TOO_LARGE",
                    "The result remains in the native transcript; no bounded observation was recorded.")
            sha = hashlib.sha256(raw.encode()).hexdigest()
            if row["state"] != "RESERVED":
                require(row["result_sha"] == sha, "RESULT_CHANGED", "The result was already recorded with different content.")
                return {"recorded": True, "reused": True, "operation": key, "state": row["state"]}
            meta = report_metadata(result)
            state = "UNKNOWN" if failed or meta["is_error"] else "OBSERVED"
            self.db.execute("UPDATE operations SET state=?,completed=?,result_sha=?,report_id=COALESCE(?,report_id),result_status=? WHERE op_key=?",
                            (state, self.now(), sha, meta["report_id"], meta["status"], key))
            return {"recorded": True, "operation": key, "state": state,
                    "report_id": meta["report_id"], "result_status": meta["status"]}
        return self._transaction(observe)

    def inspect(self, job_key):
        row = self.db.execute("SELECT * FROM jobs WHERE job_key=?", (job_key,)).fetchone()
        require(row is not None, "JOB_NOT_FOUND", "No matching durable job was recorded.")
        operations = [dict(r) for r in self.db.execute("SELECT o.op_key,o.run_id,o.tool_id,o.tool,o.kind,o.state,o.scope_json,o.report_id,o.result_status,o.created FROM operations o JOIN operation_jobs j ON j.op_key=o.op_key WHERE j.job_key=? ORDER BY o.created", (job_key,))]
        revision = self.db.execute("SELECT limits_json FROM budget_revisions WHERE job_key=? ORDER BY id DESC LIMIT 1", (job_key,)).fetchone()
        limits = json.loads(revision[0]) if revision else json.loads(row['policy_json'])['limits']
        return {"job_key": job_key, "room": row["room"], "source_id": row["source_id"],
                "scopes": json.loads(row["scopes_json"]), "expires_at": row["expires"],
                "effective_limits": limits,
                "expired": self.now() >= row["expires"],
                "checkpoint": json.loads(row["checkpoint_json"]) if row["checkpoint_json"] else None,
                "operations": operations, "task_completion": "NOT_DETERMINED",
                "business_impact_usd": None}

    def amend_budget(self, job_key, limits, reason, source_ref, *, lifetime_change_allowed=True):
        """Trusted coordinator operation: preserve scopes and all spent reservations."""
        validate_limits(limits)
        require(isinstance(reason,str) and 10 <= len(reason) <= 2000
                and isinstance(source_ref,dict) and source_ref,
                'BUDGET_REASON_REQUIRED','A bounded allocation reason and source reference are required.')
        request_sha = digest({'job':job_key,'limits':limits,'reason':reason,'source_ref':source_ref})
        def summary():
            value=self.inspect(job_key)
            value['operation_count']=len(value.pop('operations'))
            return value
        def amend():
            job = self.db.execute('SELECT * FROM jobs WHERE job_key=?',(job_key,)).fetchone()
            require(job is not None,'JOB_NOT_FOUND','No matching job can receive a budget revision.')
            old = self.db.execute('SELECT id FROM budget_revisions WHERE job_key=? AND request_sha=?',(job_key,request_sha)).fetchone()
            if old:
                return {'reused':True,'revision_id':old['id'],'request_sha256':request_sha,
                        'job':summary(),'execution_authority_granted':False}
            last = self.db.execute('SELECT limits_json FROM budget_revisions WHERE job_key=? ORDER BY id DESC LIMIT 1',(job_key,)).fetchone()
            previous = json.loads(last[0]) if last else json.loads(job['policy_json'])['limits']
            require(lifetime_change_allowed or limits['lifetime_seconds']==previous['lifetime_seconds'],
                    'ACTIVE_RUN_DEADLINE_BOUND','Change a live native deadline only after its current run reaches a checkpoint.')
            require(job['created'] + limits['lifetime_seconds'] > self.now(),
                    'BUDGET_ALREADY_EXPIRED','The revised lifetime would still be expired; no budget was changed.')
            cur = self.db.execute('INSERT INTO budget_revisions(job_key,request_sha,limits_json,reason,source_ref_json,at) VALUES(?,?,?,?,?,?)',
                                 (job_key,request_sha,canonical(limits),reason,canonical(source_ref),self.now()))
            self.db.execute('UPDATE jobs SET expires=? WHERE job_key=?',
                            (job['created']+limits['lifetime_seconds'],job_key))
            return {'reused':False,'revision_id':cur.lastrowid,'request_sha256':request_sha,
                    'job':summary(),'counters_reset':False,'scopes_changed':False,
                    'execution_authority_granted':False}
        return self._transaction(amend)

    def report_scope(self, ctx, report_id):
        values = set()
        for root in ctx["roots"]:
            key = self.job_key(ctx["room"], root)
            rows = self.db.execute("SELECT DISTINCT o.scope_json FROM operations o JOIN operation_jobs j ON j.op_key=o.op_key WHERE j.job_key=? AND o.report_id=? AND o.kind='report_dispatch' AND o.state='OBSERVED'", (key, report_id))
            scopes = {row[0] for row in rows if row[0]}
            require(len(scopes) == 1, "REPORT_SCOPE_UNVERIFIED",
                    "The report has no unique recorded scope in every initiating job.")
            values.update(scopes)
        require(len(values) == 1, "REPORT_SCOPE_UNVERIFIED", "The report scope is ambiguous.")
        return json.loads(next(iter(values)))

    def bind_source(self, room, root, scopes, policy, *, _within_transaction=False):
        """Owner-only caller; no operations may precede or be replayed by binding."""
        validate_limits(policy["limits"])
        require(isinstance(scopes, list) and 0 < len(scopes) <= 32
                and all(scope in policy["scopes"] for scope in scopes)
                and len({canonical(scope) for scope in scopes}) == len(scopes),
                "INVALID_SCOPE_BINDING", "Choose exact scopes from the installed canonical policy.")
        configured = policy["room_scopes"].get(room, [])
        require(not configured or all(scope in configured for scope in scopes),
                "ROOM_SCOPE_MISMATCH", "A job binding cannot exceed its registered room scope.")
        key, now = self.job_key(room, root), self.now()
        def bind():
            existing = self.db.execute("SELECT * FROM jobs WHERE job_key=?", (key,)).fetchone()
            if existing:
                require(existing["source_sha"] == root["sha256"] and existing["policy_sha"] == digest(policy),
                        "SOURCE_CHANGED", "The source or policy no longer matches this job.")
                require(now < existing["expires"], "JOB_EXPIRED", "Scope binding cannot renew an expired job.")
                prior = json.loads(existing["scopes_json"])
                if prior == scopes:
                    return {"bound": True, "job_key": key, "reused": True}
                count = self.db.execute("SELECT count(*) FROM operation_jobs WHERE job_key=?", (key,)).fetchone()[0]
                require(count == 0 and (not prior or all(s in prior for s in scopes)),
                        "SCOPE_ALREADY_USED", "An active or used scope cannot be widened or replaced.")
                self.db.execute("UPDATE jobs SET scopes_json=? WHERE job_key=?", (canonical(scopes), key))
            else:
                self.db.execute("INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?,NULL)",
                                (key, room, root["id"], root["sha256"], digest(policy), canonical(policy),
                                 canonical(scopes), now, now + policy["limits"]["lifetime_seconds"]))
            return {"bound": True, "job_key": key, "scopes": scopes,
                    "execution_authority_granted": False}
        return bind() if _within_transaction else self._transaction(bind)

    def bind_sources(self, room, roots, scopes, policy):
        return self._transaction(lambda: [self.bind_source(room, root, scopes, policy,
                                                          _within_transaction=True) for root in roots])


def report_metadata(result):
    """Bounded metadata extraction; no rows, credentials, or source text retained."""
    ids, statuses = set(), set()
    is_error = False
    def walk(item, depth=0):
        nonlocal is_error
        if depth > 8:
            return
        if isinstance(item, dict):
            is_error = is_error or item.get("isError") is True
            for key in ("report_id", "reportId"):
                value = item.get(key)
                if isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,255}', value):
                    ids.add(value)
            value = item.get("status")
            if isinstance(value, str) and re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,63}', value):
                statuses.add(value)
            for key in ("result", "data", "content", "text", "structuredContent"):
                if key in item:
                    walk(item[key], depth + 1)
        elif isinstance(item, list):
            for child in item[:32]:
                walk(child, depth + 1)
        elif isinstance(item, str) and len(item) <= 2 * 1024 * 1024:
            try:
                walk(json.loads(item), depth + 1)
            except (ValueError, RecursionError):
                pass
    walk(result)
    return {"report_id": next(iter(ids)) if len(ids) == 1 else None,
            "status": next(iter(statuses)) if len(statuses) == 1 else None,
            "is_error": is_error}
