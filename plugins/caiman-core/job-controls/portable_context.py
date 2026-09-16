"""Project-local host context for the paired plugin/kit.

This validates host event continuity and declared source bindings. It does not
authenticate a remote seller, create entitlement, or replace host permissions.
"""
from __future__ import annotations
import json
from pathlib import Path
import sqlite3
import time

from job_engine import Ledger, Refusal, require, digest, canonical


class PortableContext:
    def __init__(self, path, workspace_id, binding_sha, *, now=time.time):
        self.db = sqlite3.connect(str(path), timeout=1.5, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.workspace_id, self.binding_sha, self.now = workspace_id, binding_sha, now
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS host_prompts (
          session_id TEXT NOT NULL, prompt_id TEXT NOT NULL, source_sha TEXT NOT NULL,
          created REAL NOT NULL, active INTEGER NOT NULL, source_basis TEXT NOT NULL,
          PRIMARY KEY(session_id,prompt_id)
        );
        CREATE TABLE IF NOT EXISTS host_agents (
          agent_id TEXT PRIMARY KEY, session_id TEXT NOT NULL, prompt_id TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS host_job_links (
          session_id TEXT NOT NULL, prompt_id TEXT NOT NULL, root_id TEXT NOT NULL,
          root_sha TEXT NOT NULL, root_basis TEXT NOT NULL,
          PRIMARY KEY(session_id,prompt_id)
        );
        CREATE TABLE IF NOT EXISTS host_session_jobs (
          session_id TEXT PRIMARY KEY, root_id TEXT NOT NULL,
          root_sha TEXT NOT NULL, root_basis TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS host_job_selections (
          request_sha TEXT PRIMARY KEY, session_id TEXT NOT NULL, prompt_id TEXT NOT NULL,
          mode TEXT NOT NULL, previous_root TEXT NOT NULL, selected_root TEXT NOT NULL,
          prompt_source_sha TEXT NOT NULL, source_ref_json TEXT NOT NULL, at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS host_job_owners (
          root_id TEXT PRIMARY KEY, session_id TEXT NOT NULL
        );
        -- Preserve each pre-upgrade root; never retroactively merge reservations.
        INSERT OR IGNORE INTO host_job_links
          SELECT session_id,prompt_id,session_id||':'||prompt_id,source_sha,source_basis FROM host_prompts;
        INSERT OR IGNORE INTO host_session_jobs
          SELECT p.session_id,l.root_id,l.root_sha,l.root_basis
          FROM host_prompts p JOIN host_job_links l USING(session_id,prompt_id)
          WHERE (SELECT count(DISTINCT l2.root_id) FROM host_job_links l2 WHERE l2.session_id=p.session_id)=1
          AND p.rowid=(SELECT p2.rowid FROM host_prompts p2
            WHERE p2.session_id=p.session_id ORDER BY p2.created DESC,p2.rowid DESC LIMIT 1);
        INSERT OR IGNORE INTO host_job_owners
          SELECT l.root_id,COALESCE((SELECT s.session_id FROM host_job_selections s
            WHERE s.selected_root=l.root_id ORDER BY s.at DESC,s.rowid DESC LIMIT 1),l.session_id)
          FROM host_job_links l WHERE l.root_id!='' AND l.rowid=(SELECT min(l2.rowid)
            FROM host_job_links l2 WHERE l2.root_id=l.root_id);
        ''')

    def close(self):
        self.db.close()

    def register_prompt(self, event):
        require(not event.get('agent_id'), 'GENERATED_PROMPT_NOT_ROOT',
                'A worker cannot establish a new original job.')
        session, prompt = event.get('session_id'), event.get('prompt_id')
        require(all(isinstance(x, str) and 0 < len(x) <= 200 for x in (session, prompt)),
                'HOST_PROMPT_ID_UNAVAILABLE', 'The host must provide exact session and prompt IDs.')
        text = event.get('prompt')
        require(isinstance(text, str) and len(text.encode()) <= 262144,
                'HOST_PROMPT_UNAVAILABLE', 'The bounded original host prompt is required.')
        source_sha = digest({'session_id': session, 'prompt_id': prompt, 'prompt': text})
        self.db.execute('BEGIN IMMEDIATE')
        try:
            prior = self.db.execute('SELECT * FROM host_prompts WHERE session_id=? AND prompt_id=?', (session, prompt)).fetchone()
            if prior:
                require(prior['source_sha'] == source_sha and prior['active'] == 1,
                        'HOST_PROMPT_REPLAY', 'An old or changed prompt cannot be reactivated.')
            else:
                self.db.execute('UPDATE host_prompts SET active=0 WHERE session_id=?', (session,))
                self.db.execute('INSERT INTO host_prompts VALUES(?,?,?,?,1,?)',
                                (session, prompt, source_sha, self.now(), 'HOST_PROMPT_HASH'))
            self._link_current(session,prompt)
            self.db.execute('COMMIT')
        except BaseException:
            self.db.execute('ROLLBACK'); raise
        link=self.db.execute('SELECT root_id FROM host_job_links WHERE session_id=? AND prompt_id=?',(session,prompt)).fetchone()
        return {'recorded':True,'source_sha256':source_sha,
                'job_key':Ledger.job_key(self.workspace_id,{'id':link['root_id']}) if link['root_id'] else None}

    def bind_initial_turn(self, event):
        """Enrollment may occur after UserPromptSubmit in the same first request.

        Bind the host's IDs only, without inventing an original prompt hash. This
        is available once per session and cannot revive an older recorded turn.
        """
        require(not event.get('agent_id'), 'UNBOUND_HOST_WORKER', 'A worker cannot bootstrap the original turn.')
        session, prompt = event.get('session_id'), event.get('prompt_id')
        require(all(isinstance(x,str) and 0<len(x)<=200 for x in (session,prompt)),
                'HOST_PROMPT_ID_UNAVAILABLE','The host must supply the exact current turn IDs.')
        self.db.execute('BEGIN IMMEDIATE')
        try:
            require(self.db.execute('SELECT 1 FROM host_prompts WHERE session_id=? LIMIT 1',(session,)).fetchone() is None,
                    'HOST_PROMPT_NOT_ACTIVE','Only the first enrollment can bind a turn without its prompt event.')
            self.db.execute('INSERT INTO host_prompts VALUES(?,?,?,?,1,?)',
                            (session,prompt,digest({'session_id':session,'prompt_id':prompt}),self.now(),'HOST_TURN_IDS_ONLY'))
            self._link_current(session,prompt)
            self.db.execute('COMMIT')
        except BaseException:
            self.db.execute('ROLLBACK');raise

    def _link_current(self, session, prompt):
        row=self.db.execute('SELECT * FROM host_prompts WHERE session_id=? AND prompt_id=?',
                            (session,prompt)).fetchone()
        selected=self.db.execute('SELECT * FROM host_session_jobs WHERE session_id=?',(session,)).fetchone()
        old_roots=self.db.execute('SELECT DISTINCT root_id FROM host_job_links WHERE session_id=?',(session,)).fetchall()
        root=(selected['root_id'],selected['root_sha'],selected['root_basis']) if selected else (
              ('','','JOB_SELECTION_REQUIRED') if len(old_roots)>1 else
              (session+':'+prompt,row['source_sha'],row['source_basis']))
        if root[0]:
            self.db.execute('INSERT OR IGNORE INTO host_session_jobs VALUES(?,?,?,?)',(session,*root))
            self.db.execute('INSERT OR IGNORE INTO host_job_owners VALUES(?,?)',(root[0],session))
        self.db.execute('INSERT OR IGNORE INTO host_job_links VALUES(?,?,?,?,?)',(session,prompt,*root))

    def select_job(self, event, mode, job_key, policy_sha, ledger_path, source_ref):
        """An explicit coordinator selection before admission; never reset a ledger.

        Host context and ledger are locked together so admission cannot race a
        handover. Classification of a genuinely new task remains the coordinator's
        responsibility, recorded against the actual current host prompt hash.
        """
        require(not event.get('agent_id'),'GENERATED_PROMPT_NOT_ROOT','Only the coordinator selects an original job.')
        require(mode in ('new','resume'),'INVALID_JOB_SELECTION','Choose new or resume explicitly.')
        self.db.execute('ATTACH DATABASE ? AS job_ledger',(str(ledger_path),))
        try:
            self.db.execute('BEGIN IMMEDIATE')
            try:
                row=self._prompt(event)
                link=self.db.execute('SELECT * FROM host_job_links WHERE session_id=? AND prompt_id=?',
                                     (row['session_id'],row['prompt_id'])).fetchone()
                old={'id':link['root_id'],'sha256':link['root_sha']}
                run_id=int(digest(row['session_id']+':'+row['prompt_id'])[:15],16)
                request_sha=digest(source_ref)
                prior=self.db.execute('SELECT * FROM host_job_selections WHERE request_sha=?',(request_sha,)).fetchone()
                if prior:
                    require(prior['session_id']==row['session_id'] and prior['prompt_id']==row['prompt_id']
                            and prior['selected_root']==old['id'],'JOB_SELECTION_SUPERSEDED','This selection was superseded.')
                    self.db.execute('COMMIT')
                    return {'selected':True,'reused':True,'job_key':Ledger.job_key(self.workspace_id,old)}
                require(self.db.execute('SELECT 1 FROM job_ledger.runs r JOIN job_ledger.jobs j USING(job_key) '
                        'WHERE j.room=? AND r.run_id=? LIMIT 1',(self.workspace_id,run_id)).fetchone() is None,
                        'PROMPT_ALREADY_ADMITTED','Keep this admitted prompt attached to its original job.')
                if mode=='new':
                    require(job_key is None and row['source_basis']=='HOST_PROMPT_HASH',
                            'ORIGINAL_PROMPT_REQUIRED','A new task needs its actual saved host prompt, not enrollment IDs.')
                    root=(row['session_id']+':'+row['prompt_id'],row['source_sha'],row['source_basis'])
                else:
                    job=self.db.execute('SELECT * FROM job_ledger.jobs WHERE job_key=?',(job_key,)).fetchone()
                    require(job is not None and job['room']==self.workspace_id and job['policy_sha']==policy_sha,
                            'JOB_SELECTION_MISMATCH','Resume a recorded job under the same workspace and identity policy.')
                    require(self.db.execute('SELECT 1 FROM host_prompts p JOIN host_job_links l USING(session_id,prompt_id) '
                            'WHERE l.root_id=? AND p.active=1 AND p.session_id=(SELECT session_id FROM host_job_owners WHERE root_id=l.root_id) AND (p.session_id!=? OR p.prompt_id!=?) LIMIT 1',
                            (str(job['source_id']),row['session_id'],row['prompt_id'])).fetchone() is None,
                            'ORIGINAL_JOB_ACTIVE','Wait for the prior host prompt to stop before resuming its job here.')
                    original=self.db.execute('SELECT root_basis FROM host_job_links WHERE root_id=? AND root_sha=? LIMIT 1',
                                             (str(job['source_id']),job['source_sha'])).fetchone()
                    require(original is not None,'ORIGINAL_PROMPT_REQUIRED','The original host source must remain recorded.')
                    root=(str(job['source_id']),job['source_sha'],original['root_basis'])
                self.db.execute('UPDATE host_job_links SET root_id=?,root_sha=?,root_basis=? WHERE session_id=? AND prompt_id=?',
                                (*root,row['session_id'],row['prompt_id']))
                self.db.execute('INSERT OR REPLACE INTO host_session_jobs VALUES(?,?,?,?)',(row['session_id'],*root))
                self.db.execute('INSERT OR REPLACE INTO host_job_owners VALUES(?,?)',(root[0],row['session_id']))
                self.db.execute('INSERT INTO host_job_selections VALUES(?,?,?,?,?,?,?,?,?)',
                    (request_sha,row['session_id'],row['prompt_id'],mode,old['id'],root[0],row['source_sha'],canonical(source_ref),self.now()))
                self.db.execute('COMMIT')
            except BaseException:
                self.db.execute('ROLLBACK');raise
        finally:self.db.execute('DETACH DATABASE job_ledger')
        return {'selected':True,'mode':mode,'job_key':Ledger.job_key(self.workspace_id,{'id':root[0]}),
                'prior_job_key':Ledger.job_key(self.workspace_id,old) if old['id'] else None,'history_preserved':True,
                'counters_reset':False,'business_authority_granted':False}

    def status(self):
        return [{'session_id':r['session_id'],'prompt_id':r['prompt_id'],'source_sha256':r['source_sha'],
                 'source_basis':r['source_basis'],'active':bool(r['active']),
                 'job_key':Ledger.job_key(self.workspace_id,{'id':r['root_id']}) if r['root_id'] else None}
                for r in self.db.execute('SELECT p.*,l.root_id FROM host_prompts p JOIN host_job_links l USING(session_id,prompt_id) '
                                         'ORDER BY p.created DESC,p.rowid DESC LIMIT 20')]

    def register_agent(self, event):
        agent = event.get('agent_id')
        require(isinstance(agent, str) and 0 < len(agent) <= 200,
                'HOST_WORKER_ID_UNAVAILABLE', 'The host worker ID is required.')
        root = self._prompt(event, allow_agent=False)
        prior = self.db.execute('SELECT * FROM host_agents WHERE agent_id=?', (agent,)).fetchone()
        require(prior is None or (prior['session_id'], prior['prompt_id']) == (root['session_id'], root['prompt_id']),
                'WORKER_CONTEXT_CHANGED', 'A worker cannot move to another original prompt.')
        self.db.execute('INSERT OR IGNORE INTO host_agents VALUES(?,?,?)', (agent, root['session_id'], root['prompt_id']))
        return {'recorded': True}

    def _prompt(self, event, allow_agent=True):
        session, prompt = event.get('session_id'), event.get('prompt_id')
        if event.get('agent_id') and allow_agent:
            agent = self.db.execute('SELECT * FROM host_agents WHERE agent_id=?', (event['agent_id'],)).fetchone()
            require(agent is not None, 'UNBOUND_HOST_WORKER', 'This worker has no recorded original prompt.')
            require(prompt is None or prompt == agent['prompt_id'], 'STALE_HOST_WORKER', 'This worker belongs to an earlier prompt.')
            session, prompt = agent['session_id'], agent['prompt_id']
        require(isinstance(session, str) and isinstance(prompt, str),
                'HOST_PROMPT_ID_UNAVAILABLE', 'Exact host prompt continuity is required for business tools.')
        row = self.db.execute('SELECT * FROM host_prompts WHERE session_id=? AND prompt_id=?', (session, prompt)).fetchone()
        require(row is not None and row['active'] == 1, 'HOST_PROMPT_NOT_ACTIVE',
                'The tool belongs to an absent or completed host prompt.')
        return row

    def resolve(self, event):
        row = self._prompt(event)
        ident = row['session_id'] + ':' + row['prompt_id']
        link=self.db.execute('SELECT * FROM host_job_links WHERE session_id=? AND prompt_id=?',
                             (row['session_id'],row['prompt_id'])).fetchone()
        require(link is not None and link['root_id'],'ORIGINAL_JOB_UNBOUND','The prompt needs its recorded original job.')
        owner=self.db.execute('SELECT session_id FROM host_job_owners WHERE root_id=?',(link['root_id'],)).fetchone()
        require(owner is not None and owner['session_id']==row['session_id'],'JOB_HANDOFF_REQUIRED',
                'This job moved to another host conversation; use an explicit settled handoff to resume it here.')
        return {'room': self.workspace_id, 'member_id': row['session_id'],
                'run_id': int(digest(ident)[:15], 16),
                'attempt_sha': digest({'source': row['source_sha'], 'binding': self.binding_sha}),
                'native_session': row['session_id'], 'profile_id': self.binding_sha,
                'roots': [{'id': link['root_id'], 'sha256': link['root_sha']}], 'depth': 0,
                'source_basis': link['root_basis']}

    def revalidator(self, event, binding_check):
        def revalidate(ctx):
            binding_check()
            require(self.resolve(event) == ctx, 'HOST_CONTEXT_CHANGED',
                    'The selected workspace or original host prompt changed.')
        return revalidate

    def stop(self, event):
        if event.get('agent_id'):
            return {'recorded': False, 'reason': 'worker stop does not close the original prompt'}
        self.db.execute('UPDATE host_prompts SET active=0 WHERE session_id=? AND prompt_id=?',
                        (event.get('session_id'), event.get('prompt_id')))
        return {'recorded': True, 'task_completion': 'NOT_DETERMINED'}
