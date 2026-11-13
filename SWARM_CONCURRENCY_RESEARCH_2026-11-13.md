# SWARM CONCURRENCY RESEARCH — LiteLLM, Agent Swarms, LLM Gateways

**Generated:** 2026-11-13T05:30:00-05:00  
**Repo:** https://github.com/eltonaguiar/SWARM_CONSOLIDATED  
**Scope:** Production-hardened concurrent LLM swarms — LiteLLM proxy concurrency, agent swarm frameworks, LLM gateway rate limiting, backpressure, circuit breakers, token bucket algorithms, connection pooling, and multi-instance coordination.

---

## Executive Summary

LiteLLM concurrency crashes are a documented, recurring failure mode. Out-of-the-box LiteLLM defaults (aiohttp pool 300/50, DB pool 10 per worker, no admission control, per-worker in-memory rate limits) will crash or drop requests under parallel agent load. The industry standard is **defense in depth**: token bucket per agent + shared organizational bucket at 80% of provider ceiling, bounded fan-out at three levels, per-provider semaphores, exponential backoff with jitter on 429s, circuit breakers, structured backpressure signals, Redis-coordinated rate limits across instances, PgBouncer for database connections, and per-worker admission control.

---

## 1. LiteLLM Concurrency Failures (GitHub Issues)

### 1.1 aiohttp Connection Pool Starvation (#19549, #19549 fix)

**Symptom:** TCP connection timeouts under 500+ concurrent requests.  
**Root cause:** Default `AIOHTTP_CONNECTOR_LIMIT=300` total, `AIOHTTP_CONNECTOR_LIMIT_PER_HOST=50` per host. All 500 requests target the same host but only 50 can be in-flight; the other 450 queue inside the proxy.  
**Fix:**
```
AIOHTTP_CONNECTOR_LIMIT=1000
AIOHTTP_CONNECTOR_LIMIT_PER_HOST=500
```
Force `force_close=False` to enable connection reuse instead of immediate close.

### 1.2 SSE keepalive leaks `max_parallel_requests` slots (#42938, #42819, PR #48452, PR #48628)

**Symptom:** A key with `max_parallel_requests: N` gets permanently 429'd after N sequential streamed requests. The slot stays occupied for `PARALLEL_REQUEST_SLOT_TTL_SECONDS` (3600s = 1 hour).  
**Root cause:** `open_sse_before_first_byte()` spawns the pre-call chain via `asyncio.ensure_future(produce_response)`, which copies the `ContextVar` context. The slot acquisition is written to the task's copied context; the release path reads `None` and no-ops.  
**Affected paths:** SSE keepalive, synthetic/web-search streams, `/v1/messages`, `/v1/responses`, cancelled streams, cached responses.  
**Fix:** Initialize the request stash before spawning the SSE task; call `arelease_max_parallel_requests` on stream completion.

### 1.3 httpx client concurrent performance cap (#6592)

**Symptom:** LiteLLM caps at ~200 QPS instead of 30,000 RPM on GPT-4o-mini tier 5.  
**Root cause:** httpx has poor concurrent performance vs aiohttp (anyio vs asyncio issues).  
**Fix:** Use a custom OpenAI client backed by aiohttp instead of httpx.

### 1.4 TPM rate limit bypass under concurrency (#18730)

**Symptom:** Concurrent requests bypass TPM limits entirely; combined token usage far exceeds configured limit.  
**Root cause:** In-memory counters don't aggregate across processes.  
**Fix:** Use Redis for shared counters (`fail_closed_rate_limit_enforcement: true`).

### 1.5 Database connection pool exhaustion (#19921, #13140, #44266)

**Symptom:** `FATAL: sorry, too many clients already` after 6-12 hours or under load.  
**Root cause:** Default `database_connection_pool_limit: 10` per worker process. Total demand = `pool_limit × workers × instances`. A deployment with `maxReplicas: 100` at default asks for ~1000 connections.  
**Fix:**
- `database_connection_pool_limit: 50` (up from 10)
- `database_connection_pool_timeout: 120`
- Enable PgBouncer (transaction mode) in front of Postgres
- `database_disable_prepared_statements: true` when behind PgBouncer
- Cap `maxReplicas` at what your database can serve

### 1.6 SSE slot leak on streaming (#40846, #27955, #46093)

**Symptom:** Completed non-streaming `/v1/responses` requests retain slots until async logging finishes. `/v1/messages` WebSocket path strands slots permanently.  
**Fix:** Release slot before returning response; release on stream completion even when logging never runs.

---

## 2. LiteLLM Production Configuration

### 2.1 Hardened `litellm_config.yaml` for concurrent swarm traffic

```yaml
model_list:
  - model_name: hermes-windows
    litellm_params:
      model: openai/hermes-agent
      api_base: http://192.168.2.32:8642/v1
      api_key: hermes-local-web-2026
      max_parallel_requests: 10
      timeout: 120
      stream_timeout: 30
      num_retries: 3
  - model_name: qwen3-8b-vllm
    litellm_params:
      model: openai/qwen3-8b
      api_base: http://localhost:8000/v1
      max_parallel_requests: 20
      timeout: 120
  - model_name: qwen2.5-coder-7b-ollama
    litellm_params:
      model: ollama/qwen2.5-coder:7b
      api_base: http://localhost:11434/v1
      max_parallel_requests: 3
      timeout: 120
  - model_name: qwen3-30b-a3b-ollama
    litellm_params:
      model: ollama/qwen3:30b-a3b
      api_base: http://localhost:11434/v1
      max_parallel_requests: 3
      timeout: 300

router_settings:
  default_max_parallel_requests: 10
  num_retries: 3
  retry_after: 1
  routing_strategy: least-busy
  num_retries: 3
  timeout: 120

general_settings:
  database_connection_pool_limit: 50
  database_connection_pool_timeout: 120
  database_connect_timeout: 15
  database_socket_timeout: 300
  max_in_flight_requests_per_worker: 64
  max_queued_requests_per_worker: 64
  admission_queue_timeout_seconds: 1.0
  fail_closed_rate_limit_enforcement: true
  fail_closed_budget_enforcement: true

litellm_settings:
  num_retries: 3
  request_timeout: 120
  max_retries: 5
```

### 2.2 Environment variables

```
AIOHTTP_CONNECTOR_LIMIT=1000
AIOHTTP_CONNECTOR_LIMIT_PER_HOST=500
PROXY_DB_LOOKUP_MAX_CONCURRENCY=50
LITELLM_EXECUTED_BATCH_CONCURRENCY=10
```

### 2.3 Redis coordination (required for multi-worker/multi-instance)

Without Redis, every worker enforces limits independently — a limit of 100 RPM across 4 workers really lets through 400.  
**Requirements:** Redis 7.0+, configured via `general_settings.coordination_redis` or `REDIS_*` env vars (with `cache: true`).  
**Verification:** `GET /coordination_redis/settings` must name a source. Load-test: run > limit RPM across all pods and confirm 429s at ~1× (not ~N×) the configured value.

### 2.4 Per-worker admission control

```yaml
general_settings:
  max_in_flight_requests_per_worker: 64
  max_queued_requests_per_worker: 64
  admission_queue_timeout_seconds: 1.0
```
Returns fast `503` with `retry-after: 1` when saturated. Monitor with `/health/backlog` and Prometheus metrics `litellm_admission_*`.

---

## 3. Agent Swarm Concurrency Patterns

### 3.1 Swarms framework (v17)

- `ConcurrentWorkflow`: `ThreadPoolExecutor`, default `max_workers=len(agents)` (uncapped in v17). Override with `max_workers` to throttle.
- `GraphWorkflow`: `max_parallel_nodes`.
- `run_agents_concurrently_async`: `max_concurrency` parameter.
- Best practice: group agents by model/provider, give each group its own semaphore cap, run groups side by side.
- Provider caps example: `PROVIDER_CAPS = {"gpt-5.4-mini": 40, "anthropic/claude-haiku-5-5": 10, ...}`.
- Fallback: `fallback_model_name` / `fallback_models`, `retry_attempts` with exponential backoff.

### 3.2 Diagrid orchestration at scale

**Bounded fan-out at three levels:**
1. **Per workflow:** 50 documents → 5 batches of 10, each finishing before the next starts.
2. **Per worker pool:** Cap concurrent activities per worker (25 in sizing table) so one pod can't open 500 connections.
3. **Globally:** One shared limiter per model and per rate-limited API, set to ~80% of provider limit.

**Little's Law for semaphore sizing:** `max_concurrency = target_RPS × average_latency_seconds`. Example: API rate limit 60 req/s, average latency 2s → max_concurrency = 120. Set Semaphore(100) for 17% headroom.

### 3.3 OpenLegion parallelization

Provider rate limits and semaphore sizing at 2s latency:
| Provider | Tier | Rate limit | req/s | Semaphore |
|----------|------|-----------|-------|-----------|
| OpenAI | Tier 5 | 10,000 RPM | 167 | Semaphore(280) |
| Anthropic | Tier 4 | 4,000 RPM | 67 | Semaphore(110) |
| Google Gemini 1.5 Pro | — | 1,000 RPM | 17 | Semaphore(28) |

---

## 4. Token Bucket & Rate Limiting Patterns

### 4.1 Token bucket algorithm (RFC 1633)

- Bucket holds tokens, refills at rate R tokens/second up to capacity C.
- Each API call consumes one token (or N for weighted calls).
- If bucket empty: call blocks or is rejected.
- Burst tolerance: up to C calls proceed instantly before refill rate kicks in.
- Smooth average: over time, average call rate converges to R.

### 4.2 Gateway enforcement layers (TrueFoundry)

| Layer | Mechanism | Purpose |
|-------|-----------|---------|
| Layer 1 | Token bucket per (user, repo, model) | 429s tell agents to back off |
| Layer 2 | Circuit breaker per pattern (cost velocity, error rate, growing context) | Stop retries on degraded providers |
| Layer 3 | Declarative fallback chain — primary → cheaper model → semantic cache → 503 | Preserve UX during breaker open |

### 4.3 OpenLegion gateway rate limiter

1. Token bucket per agent ID: capacity = per-agent RPM allocation, refill = allocation/60 per second.
2. Shared organizational bucket: capacity = provider ceiling × 0.8 (20% headroom).
3. Priority queue: high-priority tasks jump the queue.
4. 429 pass-through: gateway marks account throttled, stops forwarding queued requests.
5. Backpressure signals: structured response with expected wait time, enabling orchestrator rescheduling.

### 4.4 Pre-flight token estimation

Count input tokens **before** sending (tiktoken for OpenAI, `@anthropic-ai/tokenizer` for Claude). Reserve `prompt_tokens + max_tokens` capacity in the bucket. Refund unconsumed headroom after completion. Apply 50% safety margin: `final_estimate = (input_tokens + estimated_completion) × 1.5`.

---

## 5. Backpressure & Circuit Breaker Patterns

### 5.1 Circuit breaker states

| State | Condition | Action |
|-------|-----------|--------|
| Closed | Healthy | Route requests normally |
| Open | N failures in window (e.g., 3 failures in 5 min) | Reject fast, don't call backend |
| Half-open | After trip duration | Probe with limited traffic |

### 5.2 Azure APIM circuit breaker config

```json
circuitBreaker: {
  rules: [{
    failureCondition: {
      count: 3,
      interval: "PT5M",
      statusCodeRanges: [{ min: 429, max: 429 }, { min: 500, max: 503 }]
    },
    tripDuration: "PT1M",
    acceptRetryAfter: true,
    errorReasons: ["Server errors"]
  }]
}
```

### 5.3 Exponential backoff with jitter

```
wait = (2 ** attempt) + random.uniform(0, 1)
```
Cap at max delay (e.g., 4s). Honor `Retry-After` header when present.

### 5.4 Structured backpressure signal

```json
{
  "status": "rate_limited",
  "retry_after_seconds": 47,
  "quota_scope": "account",
  "agent_id": "agent-research-7",
  "task_id": "task-a3b9",
  "parked_at": "2026-07-05T14:23:11Z"
}
```

---

## 5. Connection Pooling

### 5.1 HTTP client pools (LiteLLM → providers)

| Setting | Default | Production |
|---------|---------|------------|
| `AIOHTTP_CONNECTOR_LIMIT` | 100 | 1000 |
| `AIOHTTP_CONNECTOR_LIMIT_PER_HOST` | 50 | 500 |
| `httpx.Limits.max_connections` | ~100 | 1000 |
| `httpx.Limits.max_keepalive_connections` | ~100 | 100 |

### 5.2 Database connection pools (LiteLLM → Postgres)

| Setting | Default | Production |
|---------|---------|------------|
| `database_connection_pool_limit` | 10 | 50 |
| `database_connection_pool_timeout` | 60 | 120 |
| `database_connect_timeout` | Prisma default | 15 |

**Sizing formula:** `database_connection_pool_limit = MAX_DB_CONNECTIONS ÷ (instances × workers)`

**PgBouncer:** Enable in-container PgBouncer (transaction mode, loopback) when running multiple workers. Caps upstream connections regardless of worker count.

---

## 6. Provider Concurrency Limits

| Provider | Tier | Concurrent Requests | Notes |
|----------|------|---------------------|-------|
| Ollama Cloud | Pay as you go | 3 | Queued, then rejected when queue full |
| Ollama Cloud | Pro | 3 | |
| Ollama Cloud | Max/Team | 10 | |
| Local Ollama | `OLLAMA_NUM_PARALLEL` | default 1 | RAM scales by `NUM_PARALLEL × CONTEXT_LENGTH` |
| vLLM | `--limit-concurrency` | unlimited by default | Set via KV cache: `max_concurrency = kv_cache_size / max_model_len` |
| Hermes gateway API | `max_concurrent_runs` | default 10 | HTTP 429 when exceeded |
| General Compute | Pay As You Go | 200 | Developer: 500, Scale: 10,000 |

### 6.1 Windows Hermes gateway port binding

Default binds to `127.0.0.1:8642` only. To reach from Linux (`192.168.2.32:8642`):
- Set `gateway.api_server.host: 0.0.0.0` in `config.yaml`
- Or set `API_SERVER_HOST=0.0.0.0` environment variable
- Windows Firewall must allow inbound on port 8642
- Authentication: `API_SERVER_KEY` (Windows-side, found in `.env` backup as `hermes-local-web-2026`)

---

## 7. Recommendations for Your Swarm

### Immediate (no download required)

**Use cloud models via LiteLLM on Linux (port 4000)** — you already have 38+ aliases with paid keys (Grok 4.7, Kimi K3.1 Pro, DeepSeek V4 Pro, Mercury-3). Add Windows Hermes (`192.168.2.32:8642` + key `hermes-local-web-2026`) as a 4th endpoint.

**Do not set up Windows vLLM** — you only have Qwen2.5-3B-Instruct (5.8 GB) downloaded locally, which is underpowered for web tools research. Cloud frontier models are smarter and impose zero local GPU/VRAM pressure.

### LiteLLM hardening for your 4-endpoint swarm

1. Set per-deployment `max_parallel_requests` based on provider tier (Ollama: 3, vLLM: 20, Hermes: 10).
2. Enable Redis coordination if running multiple LiteLLM workers/instances.
3. Set `max_in_flight_requests_per_worker: 64` admission control.
4. Group swarm agents by provider; give each group its own semaphore cap.
5. Use exponential backoff with jitter on 429s; honor `Retry-After`.
6. Add circuit breakers per provider; fall back to cheaper model on sustained failure.

---

## Sources

- LiteLLM GitHub issues: #19549, #6592, #18730, #19921, #13140, #42938, #42819, #27955, #40846, #46093, #48452, #48628, PR #39093, PR #39859
- LiteLLM docs: proxy/prod, proxy/redis_requirements, proxy/config_settings, proxy/router/learn/reliability, proxy/deploy, proxy/db_sizing, proxy/high_throughput
- Swarms docs: concurrent-workflow, scaling, v17 changelog, orchestrator-worker pattern
- Diagrid: AI Agent Orchestration at Scale (10,000 workflows)
- GeneralCompute: Agentic AI in Production, Rate Limits, Inference Costs
- OpenLegion: AI Agent Rate Limiting, LLM Gateway
- TrueFoundry: Rate Limiting AI Agents
- MLflow: Provider Quota Management
- Azure AI Landing Zones: AI Gateway Resiliency Guide
- AgentGateway: Rate limiting, token budget token budgets
- Tollgate: Distributed rate limiting with Redis Lua
- Wovyr: LLM Gateway resilience
- vLLM docs: cache config, benchmark CLI, parallelism and scaling
- Ollama docs: FAQ, concurrent requests, cloud limits
