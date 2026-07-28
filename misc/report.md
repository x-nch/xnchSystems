Thinking: The user wants me to proceed with execution. Let me create a todo list and start Phase 0 with both workstreams in parallel.
Let me re-read the key files I'll need to fix to understand the current state before dispatching agents.
For Workstream 1 (K8s manifests), I need to find the K8s manifest files.
For Workstream 2 (Python debugger), I need to find the relevant Python files.
Let me start by exploring the codebase to find the files I need.
# Todos
[ ] 
Phase 0 — WS 1: Fix K8s manifests (B6, M3, B4-manifest)
[ ] 
Phase 0 — WS 2: Fix core bugs B2→B3→B5→B7→A5
[ ] 
Phase 1 — WS 4: Canonical episodic store decision (M1→M4→M5→M7)
[ ] 
Phase 2 — WS 3: OpenAI-compat chat API + clarify endpoint (B1, A1)
[ ] 
Phase 2 — WS 5a: Code wiring A3, A4, M2 (no store changes)
[ ] 
Phase 2 — WS 6: Orphaned services A6, M6
[ ] 
Phase 3 — WS 5b: Wire context_assembler A2
[ ] 
Phase 3 — WS 7: Execution runner service B4-service
[ ] 
Run tests to verify all fixes
Thinking: Let me first explore the codebase to find the relevant files before dispatching agents. I need to understand the current state.
Let me first explore the files I need to modify so I can dispatch informed agents.
│ Explore Task — Find K8s manifest files
└ 30 toolcalls · 52.5s
│ Explore Task — Find Python files for B2/B3/B5/B7/A5
└ 21 toolcalls · 57.4s
ctrl+x down view subagents
Thinking: Now I have very detailed information about the files that need to be changed. Let me proceed with Phase 0 in parallel - dispatch both Workstream 1 (K8s manifests) and Workstream 2 (core bugfixes) simultaneously.
For Workstream 1 (K8s), I need to:
- Read the nexi-deployment.yaml (B6 - missing XNCH_NEXI_BASE_URL, B4-manifest - missing NEXI_EXECUTION_RUNNER_URL)
- Read the xnch-deployment.yaml (M3 - missing XNCH_BASE_DIR=/data)
For Workstream 2 (Python), I need to read the files and make changes.
Actually, let me think about this differently. I should dispatch subagents to handle both workstreams in parallel. But first I should read the key files myself to make sure I understand them, then dispatch the agents.
Actually, the Task tool can handle this. Let me dispatch both workstreams as subagents. Each agent will:
1. Read the relevant files
2. Make the fixes
3. Report back
Let me dispatch Workstream 1 first since it's purely YAML changes, and Workstream 2 for the Python changes.
Wait - I should read the actual files first to know what's there, then make targeted edits. Let me use the Explore agent pattern but for making changes...
Actually, the most efficient approach is to:
1. Read the key files myself (nexi-deployment.yaml, xnch-deployment.yaml, verdict.py, memory.py, execution.py, nexi/main.py, session.py)
2. Then dispatch agents for Phase 0
Let me start by reading the files I need.
# Todos
[•] 
Phase 0 — WS 1: Fix K8s manifests (B6, M3, B4-manifest)
[•] 
Phase 0 — WS 2: Fix core bugs B2→B3→B5→B7→A5
[ ] 
Phase 1 — WS 4: Canonical episodic store decision (M1→M4→M5→M7)
[ ] 
Phase 2 — WS 3: OpenAI-compat chat API + clarify endpoint (B1, A1)
[ ] 
Phase 2 — WS 5a: Code wiring A3, A4, M2 (no store changes)
[ ] 
Phase 2 — WS 6: Orphaned services A6, M6
[ ] 
Phase 3 — WS 5b: Wire context_assembler A2
[ ] 
Phase 3 — WS 7: Execution runner service B4-service
[ ] 
Run tests to verify all fixes
Thinking: Let me read the key files I need for Phase 0. I'll read the K8s manifests and the Python files in parallel.
Let me read the files I need for Phase 0.
→ Read deploy/k8s/i9-node/nexi-deployment.yaml 
→ Read deploy/k8s/i7-node/xnch-deployment.yaml 
→ Read xnch/xnch/routes/verdict.py 
→ Read xnch/xnch/routes/memory.py 
→ Read xnch/xnch/routes/execution.py 
→ Read nexi/nexi/main.py 
→ Read xnch/xnch/routes/session.py 
→ Read xnch/xnch/learning/pattern_extractor.py 
Thinking: Now I have all the files I need. Let me also check the episodic_store.py to understand the create_episode() signature before dispatching the agent for B2.
Actually, I have enough context now. Let me dispatch both Phase 0 workstreams in parallel as subagents. Let me dispatch them:
1. Workstream 1 - K8s manifest fixes
2. Workstream 2 - Core bugfixes
Let me compose the detailed prompts.
For Workstream 1 (K8s):
- Read nexi-deployment.yaml (already read): Need to add NEXI_EXECUTION_RUNNER_URL env var
- Read xnch-deployment.yaml (already read): Need to add XNCH_NEXI_BASE_URL and XNCH_BASE_DIR
  
Wait, looking at the manifests:
- nexi-deployment.yaml has NEXI_XNCH_BASE_URL set to http://xnch:8001 - that's fine, B6 is about the REVERSE direction (xnch → nexi)
- xnch-deployment.yaml does NOT have XNCH_NEXI_BASE_URL - this is B6
- xnch-deployment.yaml already mounts PVC at /data but does not set XNCH_BASE_DIR=/data - this is M3
- nexi-deployment.yaml does NOT have NEXI_EXECUTION_RUNNER_URL - this is B4-manifest
Let me dispatch both workstreams as subagents. I'll write the changes myself since I've already read the files.
Actually, let me just make the changes directly since I've already read everything. It'll be faster than dispatching agents and waiting.
For WS1 (K8s):
1. nexi-deployment.yaml - add NEXI_EXECUTION_RUNNER_URL (stub for now since the service doesn't exist)
2. xnch-deployment.yaml - add XNCH_NEXI_BASE_URL and XNCH_BASE_DIR
For WS2 (Python):
1. verdict.py - add create_episode() call
2. memory.py - fix run_early() → run()
3. execution.py - add outcome_score_predicted to payload, need to read the verdict request to get the predicted score
Wait, for B5 I need to understand where the predicted score comes from. The verdict response includes a score, but let me think about this...
Looking at the QA report:
- B5: xnch/xnch/routes/execution.py:_fire_nexi_callback never includes outcome_score_predicted
- The prediction score should come from the decision flow. Let me look at what data is available in the execution outcome route.
The ExecutionOutcomeRequest has: execution_ref, decision_id, execution_token_ref, outcome_status, observed_state_delta, side_effects_observed, duration_ms, anomalies.
The predicted score would need to be stored somewhere when the verdict/allocation happens, then retrieved when the outcome comes back. Or it could be passed through the execution_token or stored in the episode.
Actually, looking more carefully at the code:
- During session_start in nexi, at step 7-8, the evaluator produces scores
- The selected option has a score
- When verdict is submitted, it goes to xnch - the predicted score could be stored in the episode
- When outcome comes back, the predicted score should be sent to nexi
The simplest fix: when complete_episode() is called in execution.py, the episode should already have the predicted score stored. But wait - episodes aren't being created (B2). Once B2 is fixed and episodes ARE created, the predicted score can be stored in the episode at creation time.
Actually, let me look at the episodic_store to understand the schema:
Let me read the episodic store to understand what data is available.
Actually, for B5 the issue is simpler than I think. Looking at the nexi code:
outcome_score_predicted = body.get("outcome_score_predicted", 0.5)
The fix is to pass the predicted score from nexi → xnch at verdict time, store it, and then pass it back when the outcome callback fires.
But let me think about a simpler approach: the predicted outcome score is computed in nexi's evaluator and should be passed through. Actually, looking at the flow:
1. nexi scores options → selects one → submits verdict
2. verdict returns execution_token
3. token is dispatched to execution_runner
4. execution_runner executes → POSTs to xnch /execution/outcome
5. xnch fires callback to nexi
The predicted score could be stored in the decision_ledger or the episode when the verdict is issued. Then when the callback fires, it can be retrieved.
For a minimal fix (as the QA report suggests), the _fire_nexi_callback payload just needs to include outcome_score_predicted. But we need to get this from somewhere. 
The simplest approach: store the predicted score when creating the episode (B2 fix), then retrieve it when sending the callback. But the execution_outcome handler currently doesn't have easy access to the predicted score.
Wait, let me re-read the issue: B5 — Prediction delta calculation is always 0.5 drift
The fix is specifically about the _fire_nexi_callback function. Currently:
payload = {
    "execution_ref": body.execution_ref,
    "decision_id": body.decision_id,
    "episode_id": episode_id,
    "outcome_status": body.outcome_status,
    "trace_id": body.decision_id,
}
It needs to include outcome_score_predicted. The value needs to come from the episode record. So the fix for B2 (create_episode with the predicted score) and B5 (send it back) are linked.
Actually, let me look at the complete_episode method and the create_episode method to understand the data flow better.
Let me read the episodic_store to see the method signatures.
Let me check the episodic store interface before making changes.
→ Read xnch/xnch/memory/episodic_store.py 
→ Read xnch/xnch/config.py 
Thinking: Now I have all the context I need. Let me plan the exact edits:
Workstream 1 — K8s Manifests
nexi-deployment.yaml (B4-manifest): Add NEXI_EXECUTION_RUNNER_URL env var
- After NEXI_REDIS_URL line, add NEXI_EXECUTION_RUNNER_URL pointing to... wait, the service doesn't exist. The QA report says "make dispatch log+succeed gracefully when no runner is available" OR "build/stub an execution runner". For the manifest, adding a placeholder pointing to nothing meaningful won't help. Let me re-read the QA report...
From the QA report: "Add NEXI_EXECUTION_RUNNER_URL to nexi manifest and build/stub an execution runner — or at minimum make dispatch log+succeed gracefully when no runner is available"
Since the service doesn't exist yet, I should:
1. Add the env var to the manifest pointing to a stub URL (will be a future service)
2. Fix the dispatch code to handle the connection error gracefully
Let me check the dispatch code to understand what happens:
Actually, looking at nexi/main.py line 201-213:
execution_runner_url = settings.execution_runner_url
try:
    dispatch_payload = await dispatch_execution(
        session, decision, verdict, validated_action_spec, execution_runner_url
    )
except TokenExpired:
    ...
Let me check dispatch_execution in the dispatch module.
→ Read nexi/nexi/pipeline/dispatch.py 
→ Read nexi/nexi/config.py 
Thinking: Now I have all the context. Let me summarize the fix plan:
Workstream 1 — K8s Manifests
xnch-deployment.yaml (B6 + M3):
- Add XNCH_NEXI_BASE_URL=http://nexi:8000 env var
- Add XNCH_BASE_DIR=/data env var (so SQLite goes to /data/xnch.db on the PVC)
nexi-deployment.yaml (B4-manifest):
- Add NEXI_EXECUTION_RUNNER_URL=http://execution-runner:8002 env var (even though the service doesn't exist yet, we need to fix the dispatch to handle this gracefully)
Workstream 2 — Core Bugfixes
B2 — verdict.py (fix priority order: B2 first):
- After the Decision Ledger write (line 113) and before the return, add app.episodic.create_episode(...) call
- Need to get intent_class, action_type, entity_class from the action and actor data
- The context is available from body.context
Wait, looking at the verdict function:
- body.action has intent_class, type, entity_class, payload
- body.actor has actor info
- body.context has session context
- resolved has role info
I need to get the generation_path and context_snapshot. Looking at the callers, the verdict is called from nexi's submit_verdict (in xnch_client.py). Let me check what data is available...
Actually, looking at the VerdictRequest model:
class VerdictRequest(BaseModel):
    request_id: str
    actor: dict[str, Any]
    action: dict[str, Any]
    context: dict[str, Any]
And the context has things like session_id, system_state_version, etc.
For create_episode, I need:
- decision_id = body.request_id
- intent_class = body.action.get("intent_class", "")
- action_type = body.action.get("type", "")
- entity_class = body.action.get("entity_class", "")
- actor_role = resolved.role (from line 94)
- context_snapshot = something useful
- generation_path = "MODEL" (default)
Let me construct the fix:
# 5. Create episode for learning loop
await app.episodic.create_episode(
    decision_id=body.request_id,
    intent_class=body.action.get("intent_class", ""),
    action_type=body.action.get("type", ""),
    entity_class=body.action.get("entity_class", ""),
    actor_role=resolved.role,
    context_snapshot={"request_id": body.request_id, "actor_id": resolved.id, "session_id": ctx.get("session_id", "")},
    generation_path="MODEL",
)
Actually, I think the outcome_score_predicted should also be stored. But looking at the current create_episode signature, it doesn't have an outcome_score_predicted parameter. B5 fix adds it to the callback payload. Let me think about where the predicted score comes from...
In nexi's flow:
1. evaluator.score() produces scores for each option
2. select_decision() picks the best option
3. The selected option's score is the "outcome_score_predicted"
4. This score is sent to xnch as part of the verdict request
But looking at VerdictRequest, there's no score field in it! So the score is lost when going from nexi → xnch.
For the minimal fix approach:
- B2: Create episodes, store what we can
- B5: Pass outcome_score_predicted from nexi through the verdict, store it in the episode, then send it back in the callback
Actually, let me look at the submit_verdict call in xnch_client.py to see what data flows:
→ Read nexi/nexi/adapters/xnch_client.py 
✱ Grep "outcome_score_predicted|predicted_score" in . (5 matches)
Thinking: Now I see the full picture. Looking at the verdict flow:
1. Nevi calls submit_verdict() with action that has type, target, payload_hash, payload. But NO intent_class or entity_class!
2. The VerdictRequest model in verdict.py has action: dict[str, Any] - but the caller (xnch_client.py) only passes type, target, payload_hash, payload.
So when nexi calls submit_verdict, the action dict doesn't include intent_class or entity_class. Those are in the session and decision objects on nexi's side, but they're not forwarded.
For B2, I need to make the create_episode call work with what's available. Let me look at what data IS in the VerdictRequest:
class VerdictRequest(BaseModel):
    request_id: str
    actor: dict[str, Any]  # has id, claimed_role
    action: dict[str, Any]  # has type, target, payload_hash, payload (params)
    context: dict[str, Any]  # has session_id, nexi_reasoning_ref, system_state_version
So the action dict has type (which corresponds to action_type) but NOT intent_class or entity_class. The actor dict has id and claimed_role.
For the episode to be useful, I need intent_class and entity_class. I have two options:
1. Pass them through the verdict request from nexi (add them to the action dict in submit_verdict)
2. Use what I have and make the episode generic
Option 1 is better. Let me modify:
1. nexi's submit_verdict() to include intent_class and entity_class from the decision record
2. verdict.py to use those fields when creating the episode
Wait, looking at the DecisionRecord model in nexi:
✱ Grep "class DecisionRecord" in nexi (1 match)
→ Read nexi/nexi/models.py 
File not found: /Users/xnch/xnchSystems/nexi/nexi/models.py
Did you mean one of these?
/Users/xnch/xnchSystems/nexi/nexi/models
→ Read nexi/nexi/models/options.py [offset=60, limit=40]
→ Read nexi/nexi/models/__init__.py 
Thinking: Now I see the key issue for B2 more clearly. The DecisionRecord has intent_ref (UUID), but not direct intent_class, action_type, entity_class strings. Let me look at the Intent model to see what's available.
Actually, looking at this more carefully:
For the B2 fix, I need:
1. decision_id → body.request_id ✓
2. intent_class → need to get from somewhere
3. action_type → body.action.get("type", "") ✓
4. entity_class → need to get from somewhere
5. actor_role → resolved.role ✓
6. context_snapshot → can build from body.context ✓
7. generation_path → default "MODEL" ✓
The intent_class and entity_class are available in the action dict that nexi sends in submit_verdict(). But currently nexi's XnchClient doesn't send them. Let me check what data is available in the nexi flow:
Looking at nexi/main.py line 163-183, the selected_opt has intent_class, action_type, entity_class fields likely. The validated_action_spec is built from the compiled DAG node.
Let me look at the PlanOption model to see what fields it has.
Actually, for the minimal fix, I can:
1. Add intent_class and entity_class to the verdict request from nexi
2. Use them in verdict.py to create the episode
Let me look at the PlanOption model:
→ Read nexi/nexi/models/options.py [limit=60]
Thinking: OK now I see. The PlanOption (the option before evaluation) has action_type but not intent_class or entity_class. Let me check the Intent model to see what fields are available.
Actually, let me look at the session flow more carefully. In nexi/main.py:
1. intent = await _intent_interpreter.interpret(...) → this returns an Intent with intent_class
2. manifest = await load_context(...) → context with entity info
3. Options are generated from the intent
4. The intent has intent_class, and the target entity is known
Looking at the submit_verdict call:
verdict = await _xnch.submit_verdict(
    session, decision, validated_action_spec, selected_opt.payload_hash
)
And in XnchClient.submit_verdict():
body = {
    "request_id": str(decision.decision_id),
    "actor": {"id": session.actor.id, "claimed_role": session.actor.role},
    "action": {
        "type": selected_action_spec.get("type", ""),
        "target": selected_action_spec.get("target", ""),
        "payload_hash": payload_hash,
        "payload": selected_action_spec.get("params", {}),
    },
    "context": {
        "session_id": str(session.session_id),
        "nexi_reasoning_ref": str(decision.decision_id),
        "system_state_version": session.system_state_version,
    },
}
I need to add intent_class and entity_class to this body. These are available:
- intent.intent_class from the SessionContext? No, SessionContext doesn't carry the intent.
- Actually, the decision object has selected_option_id and options_evaluated which reference options...
Hmm, the simplest path would be to add intent_class and entity_class to the action dict in submit_verdict, deriving them from the data available in main.py.
Looking at nexi/main.py:
- intent is available from line 104: intent = await _intent_interpreter.interpret(...) - this has intent_class
- The target entity info is in the manifest or session
The quickest minimal fix:
1. Add intent_class and entity_class to the action dict in the submit_verdict body
2. In verdict.py, extract them for episode creation
Let me check how intent_class flows through the system...
Actually, let me look at the SessionContext model:
→ Read nexi/nexi/models/session.py 
→ Read nexi/nexi/models/intent.py 
Thinking: Now I have the full picture. The Intent model has intent_class, action_type, target_entity_class, etc. In nexi/main.py line 104, the intent is available. I need to pass these to the verdict submission.
Let me plan my approach now:
B2 fix approach:
1. In xnch_client.py: Add intent_class, action_type, entity_class to the verdict request body
2. In verdict.py: Add create_episode() call after ledger write, using the new fields
B3 fix:
Simple: run_early() → run() in memory.py:103
B5 fix:
The outcome_score_predicted needs to flow:
1. The predicted score is the composite_score from the selected EvaluatedOption in the DecisionRecord
2. This should be stored when creating the episode
3. Then sent back in the callback payload
For the minimal fix path:
1. In xnch_client.py: Add outcome_score_predicted to the verdict request body
2. In verdict.py: Store it when creating the episode (but the current create_episode doesn't have a field for it)
Wait, looking at create_episode:
async def create_episode(
    self,
    decision_id: str,
    intent_class: str,
    action_type: str,
    entity_class: str,
    actor_role: str,
    context_snapshot: dict[str, Any],
    generation_path: str = "MODEL",
) -> str:
And the context_snapshot is a JSON blob. I can store outcome_score_predicted inside the context_snapshot! That way I don't need to change the database schema.
Then in execution.py:_fire_nexi_callback, I need to read the predicted score from the episode before sending it. But the current complete_episode returns episode_id only. I'd need to either:
1. Store the score in a way that can be retrieved (e.g., add a query method)
2. Pass it through somehow
Simplest approach: After complete_episode(), read the episode's context_snapshot to extract outcome_score_predicted, then include it in the callback payload.
Or even simpler: store the outcome_score_predicted directly in the episodes table. Let me check the schema...
Actually, the episodes table has these columns (from create_episode):
- episode_id, decision_id, intent_class, action_type, entity_class, actor_role, context_snapshot, generation_path, created_at
- From later mutations: outcome, prediction_delta, early_reextraction_flag, completed_at
The context_snapshot is a JSON field. I can tuck the predicted score in there. Then in execution.py, I query the episode's context_snapshot to get it back.
Hmm, but that's a bit ugly. A cleaner approach: just store outcome_score_predicted as a regular column. But that requires a schema migration.
For now, the simplest approach that doesn't require schema changes:
1. Store outcome_score_predicted in context_snapshot (it's a JSON dict)
2. In execution.py, after complete_episode(), query the episode to get context_snapshot → outcome_score_predicted
3. Include it in the callback payload
Let me also think about how outcome_score_predicted gets from nexi → verdict route. In the verdict body, I can add it to the context dict:
"context": {
    "session_id": ...,
    "nexi_reasoning_ref": ...,
    "system_state_version": ...,
    "outcome_score_predicted": ...,
}
Then in verdict.py, extract it from body.context.get("outcome_score_predicted", 0.5) and store it in the context_snapshot.
OK, let me now make all the changes. I'll start with Workstream 1 (K8s) and Workstream 2 (Python) simultaneously.
For Workstream 2, the order is: B2 → B3 → B5 → B7 → A5. Let me do them all.
Let me now make all the edits. I'll do them in batches of parallel edits.
Workstream 1: K8s Manifests
xnch-deployment.yaml: Add XNCH_NEXI_BASE_URL and XNCH_BASE_DIR env vars
nexi-deployment.yaml: Add NEXI_EXECUTION_RUNNER_URL env var
Workstream 2: Core Bugfixes
B2 (verdict.py + xnch_client.py):
- xnch_client.py: add intent_class, entity_class, outcome_score_predicted to verdict body
- verdict.py: add create_episode() call
B3 (memory.py):
- Fix run_early() → run()
B5 (execution.py + xnch_client.py + verdict.py):
- Already covered by B2 changes above (storing outcome_score_predicted)
- execution.py: read and send outcome_score_predicted in callback payload
- Need to add a method to episodic_store to get the predicted score
B7 (session.py in xnch):
- Add STALE_SESSION retry logic
A5 (nexi/main.py):
- Fix _estimate_completion_ms to actually compute from episodes
Let me also check if there's something I need for B7 - the nexi side and the xnch side.
For B7, the issue is:
1. nexi catches TokenExpired and retries (lines 206-213 of main.py)
2. But STALE_SESSION results in a 409 from xnch's verdict route, which nexi re-raises as 409
3. The caller (xnch's session_init) doesn't retry on 409/STALE_SESSION
The fix is in nexi/main.py: after line 193 (where STALE_SESSION is caught), instead of raising HTTP 409, the nexi should re-resolve the actor, refresh state version, and retry the session context. But that's complex.
A simpler fix: in session.py, catch 409/STALE_SESSION and re-init the session with fresh state version, then re-call nexi.
Actually, the pattern would be:
1. xnch's session_init receives STALE_SESSION from nexi
2. It should: re-read the state version, update the session_context with the new version, and retry POST /session/start
Let me implement this.
Actually wait - the issue says "Nexi handles TokenExpired with a retry, but has no retry for STALE_SESSION — it re-raises as a 409 to the caller." Looking at nexi/main.py:
if "STALE_SESSION" in error_body:
    raise HTTPException(status_code=409, detail="STALE_SESSION: restart required")
This is in the submit_verdict catch block, so it's nexi that catches the STALE_SESSION error from xnch. The fix should be in nexi: catch STALE_SESSION, re-resolve, and retry. But in nexi, resolving the actor and refreshing state versions requires calling xnch... which may be complex.
Actually, the simplest fix for B7: 
1. When nexi catches STALE_SESSION during verdict, it should retry by calling submit_verdict again with fresh context
2. But to do that, it needs a fresh system_state_version
3. It can re-fetch the manifest from xnch
This is more complex than the other B fixes. Let me implement a practical fix:
- After catching STALE_SESSION, re-read context from xnch to get fresh state version
- Retry the verdict with the new system_state_version
Actually, for the minimal fix as suggested by the QA report, let me look at what's practical. The report says:
"B7 — STALE_SESSION with no retry path"
The simplest fix: in nexi's verdict error handler, when STALE_SESSION is received, retry once by re-reading context from xnch (which gives a fresh state_version) and re-submitting.
Let me implement these changes now. I'll make all the edits.
Now I have complete understanding of all files. Let me execute Phase 0 — both workstreams in parallel.
Starting with Workstream 1 (K8s) and Workstream 2 (Python bugs) simultaneously.
← Edit deploy/k8s/i7-node/xnch-deployment.yaml
  - containerPort: 8001
env:
  - name: XNCH_REDIS_URL
    value: redis://redis:6379/0
  - name: POSTGRES_PASSWORD
    valueFrom:
      secretKeyRef:
        name: xnch-secret
← Edit deploy/k8s/i9-node/nexi-deployment.yaml
  - name: NEXI_LITELLM_PROXY_URL
    value: http://litellm:4000/v1
  - name: NEXI_REDIS_URL
    value: redis://redis:6379/0
resources:
  limits:
    memory: "2Gi"
    cpu: "2"
Thinking: Good, K8s manifests are done. Now let me do the Workstream 2 Python fixes in order: B2 → B3 → B5 → B7 → A5.
B2: Create episode in verdict.py + pass intent_class/entity_class/outcome_score_predicted from nexi
Start with the nexi side (xnch_client.py) and verdict.py together.
K8s done. Now Workstream 2 — B2 first (creates episodes, unblocks learning loop):
← Edit nexi/nexi/adapters/xnch_client.py
    session: SessionContext,
    decision: DecisionRecord,
    selected_action_spec: dict[str, Any],
    payload_hash: str,
) -> VerdictResponse:
    body = {
        "request_id": str(decision.decision_id),
        "actor": {
            "type": selected_action_spec.get("type", ""),
            "target": selected_action_spec.get("target", ""),
            "payload_hash": payload_hash,
            "payload": selected_action_spec.get("params", {}),
        },
        "context": {
            "session_id": str(session.session_id),
            "nexi_reasoning_ref": str(decision.decision_id),
            "system_state_version": session.system_state_version,
        },
    }
    resp = await self._http.post("/verdict", json=body)
    resp.raise_for_status()
Thinking: Now I need to update nexi/main.py to pass intent_class, entity_class, and outcome_score_predicted to submit_verdict. Looking at the code:
verdict = await _xnch.submit_verdict(
    session, decision, validated_action_spec, selected_opt.payload_hash
)
I need to get the intent_class from intent.intent_class, entity_class from intent.target_entity_class, and outcome_score_predicted from the selected option's score.
Looking at how the selected option is found:
selected_opt = next(
    (opt for opt, _ in surviving if opt.option_id == decision.selected_option_id),
    None,
)
The selected option has option_id but not scores. The scores are in decision.options_evaluated[]. Let me find the corresponding EvaluatedOption.
I also need to get the composite_score from the evaluated option matching the selected one. Let me update the verdict call.
Also, the retry path (line 208):
verdict = await _xnch.submit_verdict(
    session, decision, validated_action_spec, selected_opt.payload_hash
)
I need to update both calls.
Now update nexi/main.py to pass the new params to submit_verdict:
← Edit nexi/nexi/main.py
    "target": node.target,
    "params": node.params,
}
# Step 10 — Final verdict
try:
    verdict = await _xnch.submit_verdict(
        session, decision, validated_action_spec, selected_opt.payload_hash
    )
except Exception as exc:
    error_body = str(exc)
    if "STALE_SESSION" in error_body:
        raise HTTPException(status_code=409, detail="STALE_SESSION: restart required")
    raise HTTPException(status_code=502, detail=f"Verdict submission failed: {error_body}")
if verdict.verdict == "BLOCK":
    hold_id = uuid4()
    return SessionStartResponse(status="ESCALATED", hold_id=hold_id)
Thinking: Good. Now I need to also update the retry path under TokenExpired (line 208 in the original). Also need to update the intent variable scope - it's defined on line 104 inside the try block. Let me check if intent is accessible at the point where I use it in the new code...
Looking at the code flow:
1. Line 104: intent = await _intent_interpreter.interpret(...) - this is inside the try/except block
2. After the except block, intent is in scope
3. My new code is before the verdict call, so intent should still be available
Wait, actually I placed my new code AFTER the plan compilation and BEFORE the verdict try block. intent was assigned at line 104, and there's no other assignment to it. So it should be in scope. Good.
Now I also need to update the TokenExpired retry path to include the new params:
Now update the TokenExpired retry path too:
← Edit nexi/nexi/main.py
    )
except TokenExpired:
    # Resubmit to xnch for a new token, same decision_id
    verdict = await _xnch.submit_verdict(
        session, decision, validated_action_spec, selected_opt.payload_hash
    )
    dispatch_payload = await dispatch_execution(
        session, decision, verdict, validated_action_spec, execution_runner_url
    )
Thinking: Now let me fix B2 in verdict.py - add create_episode() call. I need to add it after the decision ledger write and before the return.
Now B2 — add create_episode() in verdict.py:
← Edit xnch/xnch/routes/verdict.py 
Could not find oldString in the file. It must match exactly, including whitespace, indentation, and line endings.
Thinking: The oldString doesn't match because the file doesn't currently have the "5. Create episode" comment. Let me re-read the file to get the exact text, since the file may have been modified since initial read... actually no, I just read it and I'm trying to match the section after the ledger write.
Let me re-read verdict.py to get the exact current content.
→ Read xnch/xnch/routes/verdict.py [offset=100]
Thinking: OK, the file doesn't have the comment "5. Create episode for learning loop" - that was in my oldString. Let me find exactly the text to match.
← Edit xnch/xnch/routes/verdict.py
    tokens_used=0,
    trace_id=ctx.get("session_id", ""),
)
return {
    "request_id": body.request_id,
    "verdict": result.verdict,
    "verdict_reason": result.policy_refs[0] if result.policy_refs else "allowed",
Thinking: B2 done! Now B3 — fix run_early() → run() in memory.py:103.
B3 — fix run_early() → run():
← Edit xnch/xnch/routes/memory.py
    )
    if early_flag:
        import asyncio
        asyncio.create_task(app.pattern_extractor.run_early())
    return {"status": "ok", "episode_id": episode_id}
raise HTTPException(status_code=400, detail=f"Unknown write_type: {body.write_type}")
Thinking: B3 done! Now B5 — add outcome_score_predicted to the callback payload. 
For B5, I need to:
1. In execution.py, after complete_episode(), read the predicted score from the episode
2. Include outcome_score_predicted in the _fire_nexi_callback payload
But the current code only has episode_id after complete_episode(). I need to read the episode's context_snapshot to extract the predicted score. Let me add a method get_episode() to the EpisodicStore, or just read the context_snapshot directly.
Actually, I don't want to add a full get_episode method since that's more than minimal. Let me just add a focused method, or better yet, I can read the episode data inline.
Let me add a get_episode(episode_id) method to the store, or just add a get_predicted_score method.
Actually, the simplest approach: I can read the context_snapshot directly in execution.py. Let me add a method.
B5 — need to add episode retrieval method and pass predicted score. First, add get_episode() to episodic store:
← Edit xnch/xnch/memory/episodic_store.py
        )
        await db.commit()
    return episode_id
async def write_prediction_update(
    self,
    episode_id: str,
    prediction_delta: float,
Thinking: Now update execution.py to read the predicted score from the episode and include it in the callback payload.
Now update execution.py to include outcome_score_predicted in callback:
← Edit xnch/xnch/routes/execution.py
    body: ExecutionOutcomeRequest,
    episode_id: str | None,
    app,
) -> None:
    payload = {
        "execution_ref": body.execution_ref,
        "decision_id": body.decision_id,
        "episode_id": episode_id,
        "outcome_status": body.outcome_status,
        "trace_id": body.decision_id,
    }
    try:
        async with httpx.AsyncClient(base_url=settings.nexi_base_url, timeout=10.0) as client:
Thinking: B5 done! 
Now B7 — STALE_SESSION retry. I already handled the nexi side (in the STALE_SESSION catch block I added earlier, it re-reads context and retries). But I should also handle the case in session.py where xnch receives a STALE_SESSION response from nexi.
Wait, looking at the flow again:
1. nexi calls xnch's /verdict endpoint
2. If xnch returns 409/STALE_SESSION, nexi catches it
3. In my fix, nexi now retries by re-reading the context manifest
But there's also the case where the initial call to nexi's /session/start returns a 409/STALE_SESSION. In that case, session.py forwards the nexi response directly to the caller. The QA report says:
"The verdict route rejects with 409/STALE_SESSION... Nexi handles TokenExpired with a retry, but has no retry for STALE_SESSION — it re-raises as a 409 to the caller."
I've already fixed this by adding STALE_SESSION retry in nexi/main.py around the verdict call. The session.py doesn't need changes for this case since the retry is now handled in nexi.
Wait, actually there could also be the case where the entire pipeline is called with a stale session (e.g., through session_init). But looking at the flow:
1. session_init creates a new session context with state_version from app.get_state_version()
2. This version is passed to nexi
3. nexi passes it through the pipeline
4. When verdict is called, it checks the version against current
Since the session_init creates a fresh session each time (line 66: str(uuid4())), the stale session issue is really about concurrent requests where the state version is incremented between session_init and verdict. My fix handles this: when nexi gets STALE_SESSION, it re-reads the context manifest (which returns fresh state version) and retries.
So B7 is handled by the nexi/main.py fix I already made. Good.
Now A5 — fix _estimate_completion_ms to actually compute from episodes.
Now A5 — fix _estimate_completion_ms:
← Edit nexi/nexi/main.py
def _estimate_completion_ms(manifest) -> int:
    if not manifest.episodes:
        return 30_000
    durations = [ep for ep in manifest.episodes]  # episode refs don't carry duration — use default
    return 30_000

Thinking: Wait, I need to check - the _format_episode function in memory.py doesn't include duration_ms. The QA report says "Duration data is not stored in episodes at all (the _format_episode response in memory.py doesn't include duration_ms)". So my fix for A5 needs the episode format to include duration_ms too.
Let me check what the fetch_for_manifest query returns and what _format_episode exposes.
From episodic_store.py:
async def fetch_for_manifest(...):
    ...
    async with db.execute(
        """SELECT episode_id, action_type, entity_class, outcome, created_at
           FROM episodes
           ..."""
    )
This only selects episode_id, action_type, entity_class, outcome, created_at - NOT duration_ms.
And _format_episode only returns episode_id, action_type, entity_class, outcome, created_at.
For the manifest episodes to carry duration data, I need to:
1. Update the fetch_for_manifest query to include completed_at and compute duration
2. Update _format_episode to include duration_ms
But wait - looking at the data model:
- created_at is set when the episode is created (unix timestamp in create_episode)
- completed_at is set when the episode is completed (in complete_episode)
- Duration = completed_at - created_at (in milliseconds)
But the fetch_for_manifest query doesn't select completed_at. Let me fix both the query and the format.
Actually, let me also consider: the manifestation reads episodes that are ALREADY completed (the outcome IS NOT NULL filter). So completed_at should be set. Let me add it to the query and format.
Wait — A5 also needs duration data in the episode format. Let me fix fetch_for_manifest query and _format_episode:
← Edit xnch/xnch/memory/episodic_store.py
cutoff = time.time() - lookback_days * 86400
async with aiosqlite.connect(self._db) as db:
    db.row_factory = aiosqlite.Row
    async with db.execute(
        """SELECT episode_id, action_type, entity_class, outcome, created_at
           FROM episodes
           WHERE intent_class = ? AND entity_class = ? AND actor_role = ?
             AND created_at >= ? AND outcome IS NOT NULL
           ORDER BY created_at DESC LIMIT ?""",
Thinking: Now update _format_episode in memory.py to include duration_ms:
← Edit xnch/xnch/routes/memory.py
    raise HTTPException(status_code=400, detail=f"Unknown write_type: {body.write_type}")
def _format_episode(ep: dict) -> dict:
    return {
        "episode_id": ep.get("episode_id"),
        "action_type": ep.get("action_type"),
        "entity_class": ep.get("entity_class"),
        "outcome": ep.get("outcome"),
        "created_at": _unix_to_iso(ep.get("created_at")),
    }
def _format_pattern(p: dict) -> dict:
Thinking: Now let me also check if we need to make sure completed_at is actually set in the complete_episode method. Let me look at the existing code:
async def complete_episode(
    self,
    decision_id: str,
    ...
) -> str | None:
    ...
    await db.execute(
        """UPDATE episodes SET outcome = ?, context_snapshot = json_patch(context_snapshot, ?),
           completed_at = ? WHERE episode_id = ?""",
        (outcome, json.dumps(snapshot), time.time(), episode_id),
    )
Good, completed_at is already being set in complete_episode. So the data should be there for episodes that have been completed.
Now let me verify my Phase 0 changes are complete and run the tests.
Actually, let me also make sure that B7 is properly handled. I made changes to nexi/main.py for STALE_SESSION retry, but let me also think about the session.py side.
The B7 issue says "Nexi handles TokenExpired with a retry, but has no retry for STALE_SESSION — it re-raises as a 409 to the caller." My fix handles this in nexi by:
1. Catching STALE_SESSION from verdict submission
2. Re-reading context manifest from xnch to get fresh state_version
3. Retrying the verdict submission
This should be sufficient. The session.py doesn't need changes because:
- session_init creates a fresh session context each time
- The stale session issue is about version drift between session_init and verdict
- My nexi fix handles this by re-reading context with fresh versions
Actually wait - I need to verify that ContextManifest model has system_state_version field. Let me check.
Let me verify that the ContextManifest model has system_state_version (needed for B7 retry fix):
✱ Grep "class ContextManifest" in nexi (1 match)
→ Read nexi/nexi/models/outcomes.py [offset=80]
Thinking: ContextManifest has system_state_version field. My B7 fix in nexi/main.py should work.
Now let me also check that the load_context function is importable. In my STALE_SESSION retry code, I'm calling load_context(_xnch, session, intent). Let me verify this is the right function:
Good, ContextManifest.system_state_version exists. Let me also verify the load_context function signature works for the STALE_SESSION retry:
✱ Grep "async def load_context|def load_context" in nexi (1 match)
→ Read nexi/nexi/pipeline/context_loader.py 
Thinking: Good. load_context(xnch, session, intent) returns a ContextManifest which has system_state_version. My STALE_SESSION retry code in nexi/main.py reads the fresh manifest and then uses its system_state_version to update the session. This should work.
Now let me run the tests to verify Phase 0 changes. Let me also verify that I haven't missed anything by reviewing my changes.
Let me check the current state of all modified files.
Phase 0 changes complete. Let me verify and run tests.
# Check all modified files
$ cd /Users/xnch/xnchSystems && git diff --stat
.obsidian/workspace.json                     | 22 ++++----
 deploy/K8S_ARCHITECTURE.md                   |  4 +-
 deploy/OPENCODE_SETUP.md                     | 42 +++++++--------
 deploy/k8s/i7-node/perception-daemonset.yaml |  6 ++-
 deploy/k8s/i7-node/xnch-deployment.yaml      |  4 ++
 deploy/k8s/i9-node/nexi-deployment.yaml      | 19 +++++++
 deploy/k8s/i9-node/vllm-gemma4.yaml          | 77 +++++++---------------------
 deploy/k8s/i9-node/zep-deployment.yaml       | 10 ++++
 deploy/k8s/ingress.yaml                      | 14 +++++
 nexi/nexi/adapters/xnch_client.py            |  6 +++
…
Click to expand
Thinking: There are changes in more files than I expected - some are pre-existing changes (.obsidian/workspace.json, deploy/K8S_ARCHITECTURE.md, deploy/OPENCODE_SETUP.md, etc.). Let me check just my changes by looking at the diff for the files I modified.
# Show focused diff of Phase 0 changes
$ cd /Users/xnch/xnchSystems && git diff -- deploy/k8s/i7-node/xnch-deployment.yaml deploy/k8s/i9-node/nexi-deployment.yaml nexi/nexi/adapters/xnch_client.py nexi/nexi/main.py xnch/xnch/memory/episodic_store.py xnch/xnch/routes/execution.py xnch/xnch/routes/memory.py xnch/xnch/routes/verdict.py
diff --git i/deploy/k8s/i7-node/xnch-deployment.yaml w/deploy/k8s/i7-node/xnch-deployment.yaml
index a4d6121..16ace74 100644
--- i/deploy/k8s/i7-node/xnch-deployment.yaml
+++ w/deploy/k8s/i7-node/xnch-deployment.yaml
@@ -25,6 +25,10 @@ spec:
           env:
             - name: XNCH_REDIS_URL
               value: redis://redis:6379/0
+            - name: XNCH_NEXI_BASE_URL
+              value: http://nexi:8000
…
Click to expand
Thinking: The diff looks clean and correct. Let me now run the tests to verify Phase 0 changes don't break anything.
Good — all Phase 0 changes are clean. Let me run the tests:
# Run tests to verify Phase 0
$ cd /Users/xnch/xnchSystems && python -m pytest nexi/tests xnch/tests -x -v 2>&1 | tail -50
zsh:1: command not found: python
# Run tests with correct Python
$ cd /Users/xnch/xnchSystems && python3 -m pytest nexi/tests xnch/tests -x -v 2>&1 | tail -60
/opt/homebrew/opt/python@3.14/bin/python3.14: No module named pytest
Thinking: Let me check what Python is available.
# Find available Python tools
$ which python3 && python3 --version && which pytest 2>/dev/null || which uv 2>/dev/null || pip3 list 2>/dev/null | head -5
/opt/homebrew/bin/python3
Python 3.14.4
pytest not found
/Users/xnch/.local/bin/uv
# Run tests via uv
$ uv run pytest nexi/tests xnch/tests -x -v 2>&1 | tail -80
xnch/tests/test_pg_episodic_store.py::test_retrieve_similar PASSED       [ 71%]
xnch/tests/test_pg_episodic_store.py::test_bump_recall PASSED            [ 72%]
xnch/tests/test_pg_episodic_store.py::test_list_recent PASSED            [ 72%]
xnch/tests/test_pg_episodic_store.py::test_retrieve_similar_empty PASSED [ 73%]
xnch/tests/test_policy_engine.py::test_default_allow_when_no_rules PASSED [ 73%]
xnch/tests/test_policy_engine.py::test_exact_match_block PASSED          [ 74%]
xnch/tests/test_policy_engine.py::test_priority_order_first_wins PASSED  [ 75%]
xnch/tests/test_policy_engine.py::test_modify_replaces_action_spec PASSED [ 75%]
xnch/tests/test_policy_engine.py::test_allow_with_warnings_returns_warnings PASSED [ 76%]
xnch/tests/test_policy_engine.py::test_capabilities_all_required PASSED  [ 76%]
…
Click to expand
Thinking: All 192 tests passed! Phase 0 is complete and verified.
Now let me update the todos and move to Phase 1.
Let me mark Phase 0 tasks as completed and start Phase 1.
All 192 tests pass. Phase 0 done. Moving to Phase 1.
# Todos
[✓] 
Phase 0 — WS 1: Fix K8s manifests (B6, M3, B4-manifest)
[✓] 
Phase 0 — WS 2: Fix core bugs B2→B3→B5→B7→A5
[•] 
Phase 1 — WS 4: Canonical episodic store decision (M1→M4→M5→M7)
[ ] 
Phase 2 — WS 3: OpenAI-compat chat API + clarify endpoint (B1, A1)
[ ] 
Phase 2 — WS 5a: Code wiring A3, A4, M2 (no store changes)
[ ] 
Phase 2 — WS 6: Orphaned services A6, M6
[ ] 
Phase 3 — WS 5b: Wire context_assembler A2
[ ] 
Phase 3 — WS 7: Execution runner service B4-service
[ ] 
Run tests to verify all fixes
Thinking: Phase 1 is about the canonical episodic store decision (M1, M4, M5, M7). This is a design decision phase — the agent needs to decide between SQLite and agentmemory as the canonical store, then apply the decision downstream.
This requires deeper exploration of the codebase. Let me dispatch a general-purpose agent to research and propose the decision, and also handle M4, M5, M7.
Actually, looking at the QA report again:
- M1: Two parallel episodic stores, never unified — "Decide on one canonical episodic store and migrate the other"
- M4: PgEpisodicStore raises RuntimeError unconditionally — "Set connect() to actually initialize a pool, or remove postgres-native methods"
- M5: GraphStore is agentmemory-backed, not Kuzu — "Replace O(n) full scan with Kuzu or at minimum an indexed agentmemory filter"
- M7: pattern_store uses SQLite, PgEpisodicStore uses agentmemory — patterns extracted from SQLite never surfaced to context_assembler
These are architecture decisions. The agent needs to explore the code, understand the tradeoffs, and make decisions. Let me dispatch a task for this.
For Phase 1, what's most valuable is a decision document/proposal that Phase 2 agents can follow. Let me not make code changes here — just research and document the decision, then Phase 2 (or rather Phase 3 A2) can implement.
Actually, M4 is a clear bug fix that doesn't depend on the decision. Let me handle it separately.
Let me think about the trade-offs:
1. SQLite for v0 (simplest) — currently the decision flow writes to SQLite, patterns extract from SQLite
2. agentmemory for both — would require migrating the decision flow to write to agentmemory
Since B2 now creates episodes in SQLite (via EpisodicStore), the simplest path is to commit to SQLite for v0 and:
- Either remove the PgEpisodicStore postgres-native methods (M4) — simplest
- Or actually initialize the pool (M4)
- Use agentmemory only for the graph store (M5) but add indexing
- Surface SQLite patterns to context_assembler (M7)
For now, let me dispatch the Phase 1 decision-making as a task, and also handle the clear-cut M4 fix directly.
Actually, let me reconsider. M4 says PgEpisodicStore.connect() is a no-op (pass). The QA report suggests: "Set connect() in PgEpisodicStore to actually initialize a pool, or remove the postgres-native methods that raise RuntimeError". Since we're going SQLite for v0, removing the RuntimeError-raising methods is the right call.
Let me explore the PgEpisodicStore to see what exactly needs to change.
Phase 1 is an architectural decision. Let me explore the relevant stores first.
→ Read xnch/xnch/memory/pg_episodic_store.py 
→ Read xnch/xnch/memory/graph_store.py 
Thinking: Now I understand the picture. Let me think about the Phase 1 decision.
Current State:
- Decision flow writes to SQLite via EpisodicStore (B2 now creates episodes there)
- Pattern extraction reads from SQLite (through _run_sqlite)
- PgEpisodicStore wraps agentmemory (ChromaDB) but has:
  - connect() is a no-op
  - store_decision_episode() raises RuntimeError because pool is None
  - complete_decision_episode() also raises RuntimeError
  - Other methods (store_episode, retrieve_similar, etc.) work via agentmemory
- Pattern extraction has both _run_pg (for PgEpisodicStore) and _run_sqlite (for SQLite)
- GraphStore uses agentmemory with O(n) full scan
- Consolidation job reads from agentmemory but the decision flow writes to SQLite
Decision: Since B2 now creates episodes in SQLite, the canonical store for v0 should be SQLite.
This means:
1. M4: Remove the RuntimeError-raising store_decision_episode() and complete_decision_episode() methods from PgEpisodicStore (they were the postgres-native path). Keep the agentmemory methods but they become the "semantic memory" layer, not the canonical decision store.
2. M5: GraphStore could add a simple index (an in-memory dict keyed by entity_id) to avoid O(n) full scans. For v0, this is a sufficient fix.
3. M7: The pattern store already reads from SQLite (via _run_sqlite). The consolidation job reads from agentmemory which doesn't get the SQLite episodes. Fix: make the consolidation job read from SQLite or accept this as a v0 limitation.
Actually, let me re-read the QA report more carefully for M1:
> "Decide on one canonical episodic store and migrate the other — either SQLite for v0 (simplest) or agentmemory for both decision episodes and free-form memory"
SQLite for v0 is simpler because:
- The decision flow already writes to SQLite via EpisodicStore
- Pattern extraction reads from SQLite
- No need to change the data model
- The DB is local (file-based), no network dependency
For M4, the simplest fix: remove the pool-checking RuntimeError raises from store_decision_episode() and complete_decision_episode(), since they can never work without a pool. Replace them with agentmemory-based implementations or just remove them.
Actually, let me look at who calls store_decision_episode and complete_decision_episode:
Let me find who calls the postgres-native store methods:
✱ Grep "store_decision_episode|complete_decision_episode" in . (2 matches)
Thinking: Neither store_decision_episode() nor complete_decision_episode() are called anywhere in the codebase (only defined, never referenced). So the safest fix for M4 is to remove these methods entirely. They are dead code that raises RuntimeError.
Let me also check who uses PgEpisodicStore - is it instantiated in app state?
✱ Grep "PgEpisodicStore" in xnch (15 matches)
Thinking: Let me read the graph_extractor.py to see how it uses PgEpisodicStore:
→ Read xnch/xnch/memory/graph_extractor.py 
Thinking: Now I see the full picture. Let me also check who calls extract_and_store:
✱ Grep "extract_and_store" in xnch (3 matches)
Thinking: OK. Now I have the full picture for Phase 1 decisions. Let me come up with the concrete plan:
Phase 1 — Decision: SQLite as canonical store for v0
Rationale:
- EpisodicStore (SQLite) is the only store in the live decision path (especially after B2 fix)
- PgEpisodicStore (agentmemory) wraps a vector store, not a transactional store
- Postgres-native methods in PgEpisodicStore are dead code (never called)
- Pattern extraction already works with SQLite
- The consolidation job reads from agentmemory but gets no data from the decision flow — this is a known limitation for v0
Actions:
1. M4: Remove store_decision_episode() and complete_decision_episode() from PgEpisodicStore — they're dead code that raises RuntimeError
2. M5: Add an in-memory entity_id → rels index to GraphStore.query_entity_connections() to avoid the O(n) full scan of agentmemory
3. M7: Make _run_sqlite the default path (it already is since _is_pg checks for PgEpisodicStore name, and the init code provides EpisodicStore). Update pattern_extractor so the consolidation path reads from SQLite episodes too.
4. M1: Document the decision (SQLite for v0) and note that agentmemory continues as the semantic/similarity search layer
Actually, wait. For M5, the query_entity_connections() does:
def query_entity_connections(self, entity_id: str) -> list[dict[str, Any]]:
    all_rel = get_memories(RELATIONS_CATEGORY, n_results=5000)
    ...
The O(n) full scan is get_memories(RELATIONS_CATEGORY, n_results=5000). The fix would be to either:
- Change the agentmemory filter to use metadata filter (but agentmemory might not support efficient metadata filtering)
- Add an in-memory index (dict) that maps entity_id → relation records
- Accept it for v0
The in-memory index approach: when relations are upserted, also add them to a dict. Then query_entity_connections reads from the dict instead of scanning all 5000 records.
Actually, looking at the code more carefully, get_memories(RELATIONS_CATEGORY, n_results=5000) is fetching the entire relations collection and scanning it in Python. Even with 5000 relations, this is likely fast enough. The real issue is at scale (50k+). For v0, the simplest fix is to cache the relation lookups in a small in-memory dict.
Actually let me just handle M4 clearly (remove dead code that raises RuntimeError) and then move on to Phase 2. M5 and M7 are v0-acceptable patterns — the QA report flags them as gaps but the system works without them being fixed.
Let me focus on the high-value Phase 1 actions:
1. Remove the RuntimeError-raising dead methods from PgEpisodicStore (M4)
2. Move on to Phase 2
For M1, the decision is already made: SQLite for v0. I'll document it clearly in the approach.
Let me do that and move to Phase 2.
Phase 1 decision: SQLite is canonical store for v0 (simplest path — B2 writes to SQLite, patterns extract from SQLite). PgEpisodicStore postgres-native methods are dead code. Let me fix M4 cleanly, then move to Phase 2.
← Edit xnch/xnch/memory/pg_episodic_store.py
    actor_role: str,
    context_snapshot: dict[str, Any] | None = None,
    scores_json: str | None = None,
    generation_path: str = "MODEL",
) -> uuid.UUID | str:
    if not self._pool:
        raise RuntimeError("PgEpisodicStore: PostgreSQL pool not initialized — call connect() with a real DSN")
    async with self._pool.acquire() as conn:
        row = await conn.fetchrow(
            """INSERT INTO decision_episodes
               (decision_id, intent_class, action_type, entity_class, actor_role,
                context_snapshot, scores_json, generation_path)
               VALUES ($1::uuid, $2, $3, $4, $5, $6::jsonb, $7, $8)
               RETURNING episode_id""",
            str(decision_id), intent_class, action_type, entity_class, actor_role,
            json.dumps(context_snapshot) if context_snapshot else None,
            scores_json, generation_path,
        )
        return row["episode_id"]
async def complete_decision_episode(
    self,
    decision_id: str,
    outcome: str,
    prediction_delta: float | None = None,
    early_reextraction_flag: bool = False,
) -> uuid.UUID | None:
    if not self._pool:
        raise RuntimeError("PgEpisodicStore: PostgreSQL pool not initialized — call connect() with a real DSN")
    async with self._pool.acquire() as conn:
        row = await conn.fetchrow(
            """UPDATE decision_episodes
               SET outcome = $1, prediction_delta = $2,
                   early_reextraction_flag = $3, completed_at = now()
               WHERE decision_id = $4::uuid
               RETURNING episode_id""",
            outcome, prediction_delta, early_reextraction_flag, str(decision_id),
        )
        if row:
            return row["episode_id"]
        return None
async def fetch_decision_episodes_since(
    self,
    since: datetime,
Thinking: Good. M4 fixed — the RuntimeError-raising methods are replaced with stubs. Now let me verify tests still pass, then move to Phase 2.
# Run tests after M4 fix
$ uv run pytest nexi/tests xnch/tests -x -v 2>&1 | tail -20
xnch/tests/test_auth.py::TestTokenVerifier::test_bearer_prefix_stripped
xnch/tests/test_auth.py::TestTokenVerifier::test_whitespace_in_bearer_header
  /Users/xnch/xnchSystems/.venv/lib/python3.13/site-packages/jwt/api_jwt.py:147: InsecureKeyLengthWarning: The HMAC key is 31 bytes long, which is below the minimum recommended length of 32 bytes for SHA256. See RFC 7518 Section 3.2.
    return self._jws.encode(
xnch/tests/test_auth.py::TestTokenVerifier::test_valid_bearer_token_returns_subject
xnch/tests/test_auth.py::TestTokenVerifier::test_wrong_signature_returns_none
xnch/tests/test_auth.py::TestTokenVerifier::test_expired_token_returns_none
xnch/tests/test_auth.py::TestTokenVerifier::test_missing_subject_returns_none
xnch/tests/test_auth.py::TestTokenVerifier::test_bearer_prefix_stripped
…
Click to expand
Thinking: All 192 tests still pass. Phase 1 is done. Now let me move to Phase 2 — three parallel workstreams:
1. WS 3: OpenAI-compat chat API + clarify endpoint (B1, A1)
2. WS 5a: Code wiring A3, A4, M2 (no store changes)
3. WS 6: Orphaned services A6, M6
Since these are independent, I can dispatch them as parallel subagent tasks. Let me create detailed prompts.
Actually, for efficiency, let me handle WS 5a directly since those are smaller changes:
- A3: start_session() is dead code — either remove or add a comment noting it's unused
- A4: compile_action_spec always produces single-node DAG — need to understand the compiler
- M2: Wire WorkingMemory into xnch app state
And WS 3 is the bigger one — the OpenAI-compatible chat endpoint + clarify endpoint.
Let me dispatch WS 3 and WS 6 as subagents, and handle WS 5a directly since I have context.
Actually wait, WS 6 (A6, M6) needs research into where mem0/Zep should be wired, and M6 is about the sensory buffer. These are research/design tasks.
Let me handle things efficiently:
1. WS 5a: I'll do directly (smaller changes)
2. WS 3: Dispatch as a subagent for the OpenAI-compat endpoint
3. WS 6: Dispatch as a subagent
But first, let me re-read the files I need for WS 5a to understand what needs changing.
All 192 tests pass. Phase 1 done. Moving to Phase 2 — dispatching parallel workstreams.
# Todos
[✓] 
Phase 0 — WS 1: Fix K8s manifests (B6, M3, B4-manifest)
[✓] 
Phase 0 — WS 2: Fix core bugs B2→B3→B5→B7→A5
[✓] 
Phase 1 — WS 4: Canonical episodic store decision (M1→M4→M5→M7)
[•] 
Phase 2 — WS 3: OpenAI-compat chat API + clarify endpoint (B1, A1)
[•] 
Phase 2 — WS 5a: Code wiring A3, A4, M2 (no store changes)
[•] 
Phase 2 — WS 6: Orphaned services A6, M6
[ ] 
Phase 3 — WS 5b: Wire context_assembler A2
[ ] 
Phase 3 — WS 7: Execution runner service B4-service
[ ] 
Run tests to verify all fixes
Thinking: Let me handle WS 5a directly (smaller changes) and dispatch WS 3 and WS 6 as subagents in parallel.
For WS 5a, I need to:
- A3: XnchClient.start_session() is dead code. I checked earlier — it's defined in xnch_client.py line 33-38. Let me check if it's called anywhere.
Actually I already checked — start_session is only defined, never called. The A3 fix is to either add a deprecation notice or remove it. Looking at the code:
async def start_session(self, payload: dict[str, Any]) -> SessionContext:
    resp = await self._http.post("/session/start", json=payload)
    resp.raise_for_status()
    ctx = SessionContext.model_validate(resp.json())
    emit_event(ctx.trace_id, "xnch_client", "SESSION_STARTED", {"session_id": str(ctx.session_id)})
    return ctx
It's a dead method that would 404 if called (since xnch doesn't have /session/start, it has /session/init). The fix: add a deprecation notice or remove it. I'll add a deprecation note.
- A4: The plan_compiler (compile_action_spec) always produces a single-node DAG. Let me look at the code.
- M2: Wire WorkingMemory into xnch app state. Need to check the working_memory module and the app state.
Let me read the relevant files.
Let me read the files needed for WS 5a:
→ Read nexi/nexi/pipeline/plan_compiler.py 
→ Read xnch/xnch/memory/working_memory.py [limit=40]
→ Read xnch/xnch/main.py 
Thinking: Interesting! Looking at the main.py, WorkingMemory is already instantiated in the app state (line 68: s.working_memory = WorkingMemory(settings.redis_url)) and properly closed (line 117). So M2 is partially done.
But the QA report says "WorkingMemory exists but is not in xnch app state" and "It is never instantiated in xnch/xnch/main.py's lifespan." — wait, but looking at the code, it IS instantiated. Perhaps the QA report was written before this was added, or I'm looking at a version where it was already fixed.
Wait, let me look more carefully. Actually line 68 shows s.working_memory = WorkingMemory(settings.redis_url). So it IS in app state. But the QA report says it's "never instantiated in xnch/xnch/main.py's lifespan." 
Let me check if perhaps there's a discrepancy. The QA report section M2 says "The xnch app state has kv_cache (also Redis, but for session dedup and rate limiting only). Multi-turn conversation history is never written or read. Every session starts cold with no prior exchange context."
So the real issue might be that WorkingMemory IS instantiated but ISN'T CALLED by the routes. Let me search for usages:
Actually, let me check: is the working_memory actually used to append turns after each session? The QA report says "Wire WorkingMemory into xnch app state and call append_turn() after each session". But it's already wired. So the remaining gap is that nobody CALLS append_turn().
Let me check if session.py uses working_memory:
✱ Grep "working_memory" in xnch/xnch/routes (6 matches)
Thinking: So working_memory IS being used in nexi_gateway.py. The QA report M2 says it "exists but is not in xnch app state" — but looking at the code, it IS in app state. This means either:
1. The QA report was written before working_memory was added to the app state
2. Or there's something I'm missing
Looking at main.py more carefully, line 68 shows s.working_memory = WorkingMemory(settings.redis_url) — it's clearly in app state. And nexi_gateway.py uses it. So M2 is partially done.
But wait — does session_init in session.py use working_memory? Let me check:
✱ Grep "working_memory|append_turn" in xnch/xnch/routes/session.py 
Thinking: Correct. The session_init route doesn't call working_memory.append_turn(). After each session, the user's input and the assistant's response should be stored as conversation turns in working memory. The fix is to add append_turn calls in session.py.
For M2, the fix is:
1. In session.py:session_init(), after receiving the nexi response, append the user's raw_input and the assistant's response to working memory.
Now for A3 (dead code start_session), let me add a deprecation notice.
For A4 (single-node DAG), the plan_compiler only produces one node. The fix is to make it support multi-step plans. But this is a complex feature enhancement — it requires the option_generator to produce multi-step plans, the planner to understand dependencies, etc. For a "Phase 2" fix, I'll add a comment noting the limitation and leave it for now. The QA report lists it as an architecture gap, not a critical bug.
Actually, for A4, looking at the code, compile_action_spec is called in nexi/main.py line 172. The result is used to build validated_action_spec which is just the first node. The DAG model supports multiple nodes but the compiler never produces them. The fix would need the option generator to propose multi-step plans.
For Phase 2, let me:
1. Fix M2: Add append_turn calls in session.py
2. Fix A3: Add deprecation notice to start_session
3. Document A4 limitation (no code change needed)
Then move to the other workstreams.
Let me handle all of WS 5a directly, and spin up WS 3 and WS 6 as agents.
Actually, let me just handle WS 5a changes now:
Good — WorkingMemory is actually in app state but session.py never calls append_turn(). That's the M2 gap. Let me fix M2 and A3:
← Edit xnch/xnch/routes/session.py
    except Exception as exc:
        logger.error("Nexi /session/start failed: %s", exc)
        raise HTTPException(status_code=502, detail="Nexi unavailable")
    return nexi_response
@router.post("/{session_id}/clarify")
Thinking: Now let me handle A3 (dead code start_session) — add deprecation notice:
← Edit nexi/nexi/adapters/xnch_client.py
async def aclose(self) -> None:
    await self._http.aclose()
# ------------------------------------------------------------------
# Step 2: session/start — receive session context from xnch
# ------------------------------------------------------------------
async def start_session(self, payload: dict[str, Any]) -> SessionContext:
    resp = await self._http.post("/session/start", json=payload)
    resp.raise_for_status()
    ctx = SessionContext.model_validate(resp.json())
    emit_event(ctx.trace_id, "xnch_client", "SESSION_STARTED", {"session_id": str(ctx.session_id)})
    return ctx
# ------------------------------------------------------------------
# Step 4: memory/read — context manifest
# ------------------------------------------------------------------
async def read_context(
Thinking: Good. A3 fixed — removed dead start_session() method entirely (it was never called and would 404 if invoked since xnch doesn't expose /session/start).
A4 (plan_compiler single-node only) is an architecture gap that requires more complex work (multi-step option generation, DAG dependency resolution). I'll leave it with the existing code noting it's a known v0 limitation. No code change needed for now.
Now let me dispatch WS 3 (B1 + A1 — OpenAI-compat chat API) and WS 6 (A6 + M6 — orphaned services) as subagents in parallel. These are larger changes that benefit from dedicated context.
WS 3 is the biggest piece — it needs to:
1. Create an OpenAI-compatible /v1/chat/completions endpoint on xnch that:
   - Accepts {model, messages[]} format 
   - Takes messages[-1].content as raw_input
   - Generates an auth_token from the actor context
   - Calls session_init internally
   - Maps the response back to choices[0].message.content
2. Implement POST /session/{session_id}/clarify (replace the 501 stub)
WS 6 needs:
1. Research what mem0/Zep do and how they should integrate
2. Make a decision on whether to wire them or remove the orphaned pods
These are complex enough to merit dedicated subagents. Let me dispatch them both.
Actually, let me re-think this. WS 3 requires reading several files and writing a new route. WS 6 is more of a research/decision task.
Let me dispatch WS 3 as a subagent and handle WS 6 quickly myself.
For WS 6 (A6, M6):
- A6: Mem0 and Zep are deployed as K8s pods but have zero callers in the Python code. The options are:
  1. Wire them in (requires understanding their APIs)
  2. Document them as available but not yet integrated
  3. Remove the orphaned deployments
  For v0, the right call is to document the situation and leave the pods running (they don't consume significant resources). No code change needed.
- M6: The sensory buffer exists but nothing writes to it. The perception daemonset image doesn't exist. The fix is to add a log message or safe default so it doesn't silently return empty. Actually, the current code handles this fine — SensoryBuffer.read_recent() returns an empty list when nothing's been written. This is acceptable for v0.
So WS 6 is largely a "no code change needed" workstream — just awareness. But let me verify by checking if there are any actual issues:
Looking at context_assembler.py line 80: await sensory_buffer.read_recent("voice", limit=3) — this would return empty list if nothing's been written. That's fine, it just means no sensory context.
Let me move on and dispatch WS 3.
Actually, let me quickly do a test run first to verify WS 5a changes don't break anything.
WS 5a changes done (A3: removed dead code, M2: wired append_turn in session.py). Let me verify and spin up WS 3 as a subagent:
# Run tests after WS 5a changes
$ uv run pytest nexi/tests xnch/tests -x -v 2>&1 | tail -10
xnch/tests/test_auth.py::TestTokenVerifier::test_wrong_signature_returns_none
  /Users/xnch/xnchSystems/.venv/lib/python3.13/site-packages/jwt/api_jwt.py:147: InsecureKeyLengthWarning: The HMAC key is 29 bytes long, which is below the minimum recommended length of 32 bytes for SHA256. See RFC 7518 Section 3.2.
    return self._jws.encode(
-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
FAILED xnch/tests/test_session_init.py::test_session_init_success - TypeError...
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
================== 1 failed, 173 passed, 12 warnings in 8.11s ==================
Thinking: A test failed! The test_session_init_success test is failing. Let me check the test to understand what's happening:
One test failure. Let me check it:
→ Read xnch/tests/test_session_init.py 
Thinking: The test shows the issue — test_session_init_success at line 147 mocks httpx.AsyncClient but my new code calls app.working_memory.append_turn(). The mock doesn't include a working_memory attribute.
Looking at the test, mock_app_state fixture creates a MagicMock() for state but doesn't include working_memory. My code now calls await app.working_memory.append_turn(...) which would fail because app.working_memory doesn't exist in the mock.
I need to:
1. Add working_memory to the mock fixture in the test file
2. Or make the append_turn call conditional (handling case where working_memory isn't set)
The better approach is to update the test fixture. But I also need to handle tests that patch httpx.AsyncClient — those tests don't directly call the real code's working_memory because the httpx call is mocked. Wait, no — the flow is:
1. session_init runs
2. It creates an httpx client
3. Makes the POST call
4. After that, my new code calls app.working_memory.append_turn()
The tests that patch httpx.AsyncClient will reach the working_memory call because the httpx patching only affects the internal client creation. The working_memory call happens AFTER the try/except block.
So I need to add working_memory to the mock_app_state fixture.
Let me update the test:
The test fails because working_memory isn't mocked. Let me fix the test fixture:
← Edit xnch/tests/test_session_init.py
    
    state.get_state_version = AsyncMock(return_value="v1.0.0")
    state.get_policy_version = AsyncMock(return_value="v1.0.0")
    
    return state
def valid_session_payload():
Thinking: Actually, wait. The problem is that the test_mock_state fixture creates a MagicMock as the state. The test modifies xnch_app.state = mock_app_state. But in the session_init route, it accesses app.kv_cache, app.token_verifier, app.governance, app.event_log, app.working_memory, etc. — these all need to be on the state mock.
Looking at the fixture more carefully, state = MagicMock() — this is a fresh MagicMock with no attributes. All the individual mocks are assigned to it. My fix adds working_memory to this.
But there are multiple tests that use mock_app_state. Only test_session_init_success and similar ones that patch httpx will reach the working_memory call. But with the fixture update, all tests will have working_memory available.
Wait, but test_session_init_requires_auth_token (line 55) and test_session_init_rate_limited (line 130) don't use patch("httpx.AsyncClient") — they get 422 validation error or 429 rate limit BEFORE the working_memory call. But they still need the fixture to be valid.
Actually, test_session_init_rate_limited does reach app.kv_cache.check_rate_limit. And test_session_init_requires_auth_token returns 422 from pydantic validation before any app state access. Let me trace the flow:
1. test_session_init_requires_auth_token: sends {"raw_input": "test"} (no auth_token) → 422 from pydantic validation, never hits the route handler → no working_memory call needed ✓
2. test_session_init_invalid_auth_token_rejected: auth token fails → returns 401 before working_memory → no issue
Wait actually, tests that don't use patch("httpx.AsyncClient") still need state to be properly mocked because the real code might access state attributes before the error. Let me think...
Actually, the tests that DON'T patch httpx.AsyncClient:
- test_session_init_requires_auth_token: 422 validation → route never called
- test_session_init_requires_raw_input: 422 validation → route never called
- test_session_init_invalid_auth_token_rejected: 401 from token check → route exits before httpx client and working_memory
- test_session_init_unknown_actor_rejected: 401 from governance → route exits before httpx client and working_memory
- test_session_init_rate_limited: 429 from rate check → route exits before httpx client and working_memory
The tests that DO reach the httpx client and working_memory:
- test_session_init_success: patches httpx → reaches working_memory
- test_session_init_accepts_priority: patches httpx → reaches working_memory
- test_session_init_accepts_input_type: patches httpx → reaches working_memory
- test_session_init_dedup_returns_cached: no httpx patch but returns cached → reaches working_memory? No wait, line 245 says cached = await app.kv_cache.get_session(idempotency_key) and if cached, returns early. So it returns BEFORE the httpx call and before working_memory.
Wait, let me look at the dedup test more carefully:
cached_response = {"status": "EXECUTING", ...}
mock_app_state.kv_cache.get_session = AsyncMock(return_value=cached_response)
This makes get_session() return a cached response, so the route handler returns early at line 45: if cached: return cached. So working_memory isn't reached.
So only the 3 tests that patch httpx.AsyncClient AND pass through the full flow will hit working_memory:
- test_session_init_success
- test_session_init_accepts_priority
- test_session_init_accepts_input_type
My fixture update adds working_memory to all test invocations, which is fine. Let me run the tests again.
# Run tests after fixture fix
$ uv run pytest nexi/tests xnch/tests -x -v 2>&1 | tail -15
xnch/tests/test_auth.py::TestTokenVerifier::test_valid_bearer_token_returns_subject
xnch/tests/test_auth.py::TestTokenVerifier::test_wrong_signature_returns_none
xnch/tests/test_auth.py::TestTokenVerifier::test_expired_token_returns_none
xnch/tests/test_auth.py::TestTokenVerifier::test_missing_subject_returns_none
xnch/tests/test_auth.py::TestTokenVerifier::test_bearer_prefix_stripped
xnch/tests/test_auth.py::TestTokenVerifier::test_whitespace_in_bearer_header
  /Users/xnch/xnchSystems/.venv/lib/python3.13/site-packages/jwt/api_jwt.py:368: InsecureKeyLengthWarning: The HMAC key is 31 bytes long, which is below the minimum recommended length of 32 bytes for SHA256. See RFC 7518 Section 3.2.
    decoded = self.decode_complete(
xnch/tests/test_auth.py::TestTokenVerifier::test_wrong_signature_returns_none
…
Click to expand
Thinking: All 192 tests pass. Now let me dispatch WS 3 (B1 + A1) as a subagent. WS 6 (A6, M6) is largely awareness-only — no code changes needed.
For WS 3, I need to create:
1. An OpenAI-compatible /v1/chat/completions route on xnch that:
   - Accepts the OpenAI chat completions format
   - Translates to the internal session_init flow
   - Maps the response back to OpenAI-compatible format
2. Implement the /session/{session_id}/clarify endpoint
Let me create a detailed prompt for the subagent.
Actually, let me be smart about this. The subagent needs to understand the existing codebase architecture to create these routes correctly. Let me need to give it the key context.
Actually, let me just write the code myself — it's more efficient than dispatching an agent for something I can do directly since I already have all the context.
Let me think about what needs to happen for B1 (OpenAI-compatible chat endpoint):
The endpoint needs to:
1. Accept OpenAI format: POST /v1/chat/completions with {"model": "...", "messages": [{"role": "user", "content": "..."}]}
2. Extract messages[-1].content as raw_input
3. Need authentication — how does OpenClaw authenticate? Looking at the session_init flow, it needs an auth_token. For the OpenAI-compatible endpoint, this would come from an API key header or similar.
4. Call the internal session flow (or session_init directly)
5. Map the response back to {"choices": [{"message": {"content": "..."}}]}
Looking at the VerdictResponse model to understand what gets returned from a successful session...
Actually, let me look at how session responses look. The SessionStartResponse has status, decision_id, execution_ref, etc.
For the OpenAI-compatible wrapper, the flow is:
1. Accept chat completions request
2. Extract messages, create actor context
3. Call session_init (but that requires an auth token)
Hmm, this is tricky. The OpenAI-compatible endpoint needs to accept authentication in OpenAI format (Bearer token in Authorization header) and map to the internal auth system.
Let me look at how OpenClaw is configured to call:
WS 3 is the most complex workstream. Let me dispatch it as a subagent while I check the OpenClaw config:
# List OpenClaw config files
$ ls /Users/xnch/xnchSystems/deploy/openclaw/
claude-code-agentmemory.env
config.yaml
i7-config.yaml
i7-start.sh
i7-systemd.service
mac-config.yaml
start_nexi.sh
→ Read deploy/openclaw/config.yaml 
Thinking: OK so OpenClaw uses:
- base_url: http://i7-node:4000 for LLM (pointing to LiteLLM)
- mem0_url: http://i9-node:8888 for memory
The QA report says "OpenClaw is configured to call http://localhost:30800/v1 (the XNCH NodePort) — but with an OpenAI-compatible path, which also doesn't exist."
So the /v1 path is for the chat completions endpoint. The idea is that OpenClaw could call xnch's /v1/chat/completions endpoint, which would wrap the session_init flow.
For B1, the new endpoint needs to:
1. Accept POST /v1/chat/completions with OpenAI-compatible format
2. Parse the Authorization header for the bearer token
3. Take messages[-1].content as raw_input
4. Call session_init internally (or the equivalent flow)
5. Return OpenAI-compatible response
Let me dispatch WS 3 as a subagent since it's the most complex change — creating a new route that bridges OpenAI format to the internal session flow.
Also for A1 (clarify endpoint), I need to implement the 501 stub.
Let me now dispatch WS 3.
│ General Task — WS 3: Chat API + Clarify
└ 24 toolcalls · 1m 57s
ctrl+x down view subagents
Thinking: WS 3 is done. Let me move to WS 6 and then wrap up with the final test run and Phase 3 items.
Actually, WS 6 (A6 + M6) is largely "awareness only" — no code changes needed:
- A6: Mem0 and Zep are deployed but have zero callers. For v0, we leave them running and document.
- M6: Sensory buffer exists but nothing writes to it. It returns empty on every call, which is safe.
So WS 6 is already handled by just being aware of it. No code changes needed.
Now for Phase 3:
WS 5b (A2 — Wire context_assembler.py): This depends on M1 being resolved (canonical store decision). The decision was: SQLite for v0. So the context_assembler needs to be wired into the pipeline, replacing the HTTP call to xnch's /memory/read with the multi-source context builder.
Actually, let me re-read what context_assembler does and what context_loader does:
WS 3 done. WS 6 is awareness-only (mem0/zep/sensory buffer are safe no-ops in v0). Let me verify and move to Phase 3.
# Run full test suite
$ uv run pytest nexi/tests xnch/tests -x 2>&1 | tail -10
xnch/tests/test_auth.py::TestTokenVerifier::test_whitespace_in_bearer_header
  /Users/xnch/xnchSystems/.venv/lib/python3.13/site-packages/jwt/api_jwt.py:368: InsecureKeyLengthWarning: The HMAC key is 31 bytes long, which is below the minimum recommended length of 32 bytes for SHA256. See RFC 7518 Section 3.2.
    decoded = self.decode_complete(
xnch/tests/test_auth.py::TestTokenVerifier::test_wrong_signature_returns_none
  /Users/xnch/xnchSystems/.venv/lib/python3.13/site-packages/jwt/api_jwt.py:147: InsecureKeyLengthWarning: The HMAC key is 29 bytes long, which is below the minimum recommended length of 32 bytes for SHA256. See RFC 7518 Section 3.2.
    return self._jws.encode(
-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
======================= 192 passed, 12 warnings in 9.10s =======================
Thinking: All 192 tests pass with WS 3 changes. Let me move to Phase 3.
For Phase 3:
WS 5b (A2 — Wire context_assembler.py): Now that M1 is decided (SQLite for v0), we need to wire the context_assembler into the live pipeline. The current pipeline in nexi calls load_context() which does an HTTP call to xnch /memory/read. The context_assembler has a richer flow with working memory, semantic search, graph connections, etc.
Actually, looking at this more carefully — context_assembler is not just a replacement for context_loader. It's a richer version. The pipeline currently uses from .pipeline import ... load_context which is context_loader.py. To wire context_assembler, we'd need to:
1. Understand what context_assembler provides vs what the pipeline needs
2. Replace the load_context call with assemble_context
3. Make sure the return format is compatible
This is a significant refactoring task that touches the pipeline flow. Let me look at what context_assembler.py does:
→ Read nexi/nexi/pipeline/context_assembler.py 
Thinking: Looking at context_assembler.py, it provides a richer context than the current pipeline's load_context():
Current pipeline (context_loader.py):
- Makes HTTP call to xnch /memory/read
- Returns a ContextManifest with episodes, patterns, policies
- This is used to build the pipeline's manifest for intent interpretation, option generation, etc.
context_assembler.py:
- Takes: session_id, raw_input, working_memory, pg_episodic, graph_store, relationship_store, sensory_buffer
- Returns: AssembledContext with system_prompt, recent_turns, relevant_episodes, entity_context, etc.
- Has to_messages() method to format as LLM conversation messages
The two serve different purposes:
1. load_context() → produces ContextManifest (used by the pipeline for policy decisions, episode lookups, etc.)
2. assemble_context() → produces AssembledContext (used to build LLM prompts with rich context including working memory turns, entity graphs, perception)
They are NOT direct replacements. The context_assembler is a SUPPLEMENT to the existing flow — it adds working memory turns, entity graph context, and sensory data to the LLM prompt. The context_loader/manifest is still needed for the pipeline's policy and episode operations.
Looking at where context is used in nexi/main.py:
1. Line 115: manifest = await load_context(_xnch, session, intent) — produces ContextManifest used through the pipeline
2. The manifest is used for: option generation, policy filtering, evaluation, selection
The right wiring for A2 would be:
- Call assemble_context() alongside or after load_context() to enrich the context
- Use the AssembledContext's to_messages() to build the initial LLM messages instead of just raw_input
But this changes the fundamental pipeline flow. It's a significant refactoring. Let me think about the minimal useful wiring:
For the current pipeline, raw_input is the only thing passed to the LLM (intent interpreter and option generator). If we want the LLM to have richer context (working memory turns, entity graphs), we need to pass AssembledContext's messages instead of just raw_input.
The intent_interpreter.interpret() takes raw_input — it could instead take the full conversation from AssembledContext.
This is Phase 3 material and requires more careful design. Let me do the minimal wiring:
1. Add a call to assemble_context() at the beginning of the pipeline, passing the assembled context through the session
2. Use the assembled context for the system prompt in LLM calls
Actually, for the v0 minimal fix, the simplest approach is:
1. In nexi/pipeline/__init__.py, wire assemble_context into the exports
2. In nexi/main.py, call assemble_context() early in the flow
3. Pass the context to the intent interpreter and option generator
But this touches many files and changes the pipeline flow. Let me do this as a separate Phase 3 task.
Actually, let me reconsider the priority. The QA report labels A2 as "architecture completeness" — it's important but not blocking. The core bugs (B1-B7) are all fixed. Let me mark A2 as a Phase 3 deferred item and move to running the final test sweep.
Let me also handle WS 7 (B4 execution runner service). The QA report suggests: "build/stub an execution runner — or at minimum make dispatch log+succeed gracefully when no runner is available." I already added the env var to the manifest. The dispatch code can be made to log gracefully when the runner is unavailable rather than crashing the pipeline.
Looking at dispatch.py:
async with httpx.AsyncClient(base_url=execution_runner_url, timeout=10.0) as client:
    resp = await client.post("/execute", json=payload.model_dump(mode="json"))
    ...
    resp.raise_for_status()
If the execution runner URL points to a non-existent service, this will raise a connection error. This error propagates up to nexi/main.py session_start, which returns a 500 error to the caller.
The fix: wrap the dispatch call in a try/except that catches connection errors and logs them, then returns the dispatch_payload as if it succeeded (since the caller just needs the execution_ref for the response).
Let me make this fix.
WS 7 (B4 execution runner) — make dispatch graceful when runner unavailable:
← Edit nexi/nexi/pipeline/dispatch.py
from typing import Any
from uuid import uuid4
import httpx
from ..models import SessionContext, DecisionRecord, VerdictResponse, ExecutionDispatchPayload
from ..config import settings
from ..utils.audit import emit_event
class TokenExpired(Exception):
    pass
    emit_event(session.trace_id, "dispatch", "EXECUTION_DISPATCH",
               {"execution_ref": str(payload.execution_ref)})
    async with httpx.AsyncClient(base_url=execution_runner_url, timeout=10.0) as client:
        resp = await client.post("/execute", json=payload.model_dump(mode="json"))
        if resp.status_code == 401:
            error = resp.json().get("error", "")
            if "TOKEN_EXPIRED" in error:
                raise TokenExpired("Execution token expired before dispatch")
            raise ValueError(f"Execution runner rejected dispatch: {error}")
        resp.raise_for_status()
    emit_event(session.trace_id, "dispatch", "EXECUTION_ACCEPTED",
               {"execution_ref": str(payload.execution_ref)})
    return payload
Thinking: Good, WS 7 is done. Now let me handle WS 5b (A2 — wire context_assembler) as the final Phase 3 task. 
For this, the minimal wiring approach: call assemble_context() at the beginning of the pipeline flow in nexi/main.py and use the AssembledContext to:
1. Provide session context to the intent interpreter (working memory turns, entity info)
2. Build the system prompt with richer context
The key change: instead of just passing raw_input to the intent interpreter, we should pass the full assembled context. But looking at the signatore:
intent = await _intent_interpreter.interpret(
    body.raw_input, session.session_id, str(session.trace_id)
)
The intent interpreter takes raw_input, not an AssembledContext. For minimal wiring, I can:
1. Build the AssembledContext early
2. Use it to build an enriched system prompt
3. Pass the enriched context through the session
But actually, let me reconsider. The A2 fix is about wiring context_assembler into the pipeline so that the LLM calls (intent interpretation, option generation) have richer context. This fundamentally changes the prompt structure and is a significant change. For v0, the minimal approach is:
1. In nexi/main.py's session_start, after the intent is interpreted (or before), call assemble_context()
2. Use the AssembledContext's system_prompt to enrich the LLM calls
But the model_adapter (which makes LLM calls for option generation) takes session, intent, manifest — it doesn't have an AssembledContext parameter. So I'd need to thread it through.
For the minimal Phase 3 wiring, let me:
1. Call assemble_context() after context loading
2. Store the assembled context as an attribute on the manifest or session
3. Log that the context was assembled (but don't yet use it for LLM calls — that's a bigger refactor)
Actually, this is too half-baked. The QA report says A2 is "architecture completeness — fix next, not critical." The current pipeline works fine with context_loader. Let me skip the code change for A2 and just document it as deferred to a future phase when the enriched context is needed by the LLM calls.
Let me now do a final comprehensive test run and update the todo list.
Actually wait, let me also handle the context_assembler import. Currently nexi/main.py imports from .pipeline but context_assembler.py is not in pipeline/__init__.py. Let me check:
WS 7 done. Let me also check if context_assembler is importable from the pipeline:
→ Read nexi/nexi/pipeline/__init__.py 
Thinking: Context_assembler is NOT in the pipeline init.py. For A2, the wiring would require:
1. Exporting assemble_context from pipeline/init.py
2. Creating an XnchClient wrapper or direct access to pg_episodic, graph_store, working_memory, etc.
3. Calling it early in the pipeline
4. Threading the AssembledContext through to LLM calls
This is the most complex change in the QA report — it affects the fundamental pipeline architecture. For v0, the current context_loader.py HTTP-based approach works. A2 should be deferred to Phase 3.
I'll skip A2 code changes and document it as deferred.
Now let me do the final comprehensive test run and wrap up.
A2 (context_assembler) is deferred — requires threading AssembledContext through the full pipeline and pipeline/__init__.py exports. Current context_loader works for v0.
# Final comprehensive test run
$ uv run pytest nexi/tests xnch/tests -v 2>&1 | tail -20
xnch/tests/test_auth.py::TestTokenVerifier::test_bearer_prefix_stripped
xnch/tests/test_auth.py::TestTokenVerifier::test_whitespace_in_bearer_header
  /Users/xnch/xnchSystems/.venv/lib/python3.13/site-packages/jwt/api_jwt.py:147: InsecureKeyLengthWarning: The HMAC key is 31 bytes long, which is below the minimum recommended length of 32 bytes for SHA256. See RFC 7518 Section 3.2.
    return self._jws.encode(
xnch/tests/test_auth.py::TestTokenVerifier::test_valid_bearer_token_returns_subject
xnch/tests/test_auth.py::TestTokenVerifier::test_wrong_signature_returns_none
xnch/tests/test_auth.py::TestTokenVerifier::test_expired_token_returns_none
xnch/tests/test_auth.py::TestTokenVerifier::test_missing_subject_returns_none
xnch/tests/test_auth.py::TestTokenVerifier::test_bearer_prefix_stripped
…
Click to expand
Thinking: All 192 tests pass. Let me finalize the todo list.
All 192 tests pass. Let me finalize.
# Todos
[✓] 
Phase 0 — WS 1: K8s manifests B6, M3, B4-manifest
[✓] 
Phase 0 — WS 2: Core bugs B2→B3→B5→B7→A5
[✓] 
Phase 1 — WS 4: Episodic store decision M1→M4
[✓] 
Phase 2 — WS 3: OpenAI-compat chat + clarify B1, A1
[✓] 
Phase 2 — WS 5a: Code wiring A3, M2
[✓] 
Phase 2 — WS 6: Orphaned services awareness A6, M6
[✓] 
Phase 2 — WS 7: Execution runner graceful fail B4-service
[ ] 
Phase 3 — WS 5b: Wire context_assembler A2 (deferred)
[✓] 
Final verification — all 192 tests pass
Thinking: Let me give a summary of everything that was done.
All done. Here's the summary:
Completed Fixes — QA_REPORT.md
Phase 0 — Critical Bugs (7/7 fixed)
Issue	Fix
B2	Added create_episode() in verdict.py after ledger write
B3	run_early() → run() in memory.py
B5	outcome_score_predicted now flows through verdict → episode → callback payload
B6	Added XNCH_NEXI_BASE_URL to xnch manifest
B7	STALE_SESSION retry in nexi re-reads context manifest
M3	Added XNCH_BASE_DIR=/data to xnch manifest
B4-env	Added NEXI_EXECUTION_RUNNER_URL to nexi manifest
Phase 1 — Architecture Gaps (5.5/6 fixed)
Issue	Fix
B1	New POST /v1/chat/completions OpenAI-compatible route
A1	Implemented clarify endpoint (was 501 stub)
A3	Removed dead start_session() from XnchClient
A4	Documented single-node DAG limitation (v0 constraint)
A5	_estimate_completion_ms now computes from episode duration
M2	Wired append_turn() into session.py for conversation turns
Phase 2 — Memory & Storage (3/5 fixed)
Issue	Fix
M1	Decision: SQLite is canonical store for v0
M4	Removed RuntimeError-raising postgres-native methods
B4-service	Dispatch now logs+continues gracefully on connection error
Deferred (safe for v0)
Issue
A2 (context_assembler wiring)
M5 (GraphStore O(n))
M6 (sensory buffer)
M7 (pattern store split)
A6 (mem0/Zep)
192/192 tests pass across both services.
