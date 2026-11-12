# Swarm Consolidation Plan - 2026-11-12
**Agent:** Ollama-Claude
**Status:** Baseline Architecture (Lead)

## 🎯 Goal
Consolidate fragmented swarm systems across `findtorontoevents_antigravity.ca` and `FREELLM` into a single, deployable orchestration layer in `SWARM_CONSOLIDATED`. This ensures a single source of truth for AI coordination logic while maintaining a clean separation between "Orchestration Logic" and "Domain Knowledge."

## 🏗️ Proposed Architecture

### 1. The "Core Library" (SWARM_CONSOLIDATED)
This repo will host the a-priori generic tools that can be used by any project.
- **Transport Layer**: `api_consult.py` $\rightarrow$ `core/transport.py` (Unified API routing).
- **Worker Layer**: `worker_runner.py` $\rightarrow$ `core/worker.py` (Universal agent adapter).
- **Coordination Primitives**: 
    - `CombineTeam` (Consensus aggregation).
    - `DebateTeam` (Adversarial pressure-testing).
    - `FileTeam` (Distributed file processing).
- **Meta-Orchestration**: `meta_swarm_orchestrator.py` $\rightarrow$ `core/meta_orchestrator.py` (Self-improvement, Thompson sampling, quality scoring).
- **Proxy Management**: `litellm_config.yaml` and proxy start scripts to manage `localhost:4000/v1`.

### 2. The "Domain Layer" (Project Repos, e.g., antigravity.ca)
Project-specific logic remains in the project repo to avoid bloating the core library.
- **Personas**: `agent_personas/` (Specialist definitions).
- **Task Files**: `tasks/` or `prompts/` (What the swarm actually does).
- **Project-Specific Logic**: `.ruflo/orchestrator.py` (Domain-specific wrappers).

### 3. The "Infrastructure" (Global Service)
The LiteLLM proxy remains a local service. The consolidated repo provides the configuration, and the project repos consume it as a stable endpoint.

## 🌍 Deployability & Cross-PC Compatibility

To ensure this swarm works on any PC without conflicting with the existing LiteLLM deployments:

### A. Environment Agnostic Paths
- **No Hardcoded Homes**: Replace all `/home/eaguiar2015/` or `/home/zerou/` paths with dynamic resolution:
    - Use `pathlib.Path.home()` for `~/dbpasses.txt`.
    - Use `os.getcwd()` or a `REPO_ROOT` environment variable for relative project paths.
- **Portable Configuration**: Use `.env` files for machine-specific paths (like the `HERMES_BIN` location) rather than hardcoding them in Python.

### B. Non-Conflicting Proxy Integration
To avoid conflicts with the `LITELLM` GitHub repo and the live `:4000` endpoint:
- **Client-Server Separation**: The consolidated swarm acts as a **Client** to the proxy. It will not attempt to manage the proxy's internal state or overwrite its running config.
- **Endpoint Standard**: All swarms will use a configurable `PROXY_URL` (defaulting to `http://localhost:4000/v1`). This allows a user to move the proxy to a different port or machine without changing the swarm code.
- **Configuration Sync**: Provide a `litellm_config.example.yaml` that allows new users to set up their own proxy to match the "Consolidated" expectations without breaking their existing proxy deployments.

### C. Zero-Touch Installation
- **Dependency Isolation**: Provide a clean `requirements.txt` and a `setup.py` so the core library can be installed via `pip install -e .` in any project.
- **Standardized Key Pool**: Maintain the `~/dbpasses.txt` convention across all PCs so that "deploying" a swarm only requires moving one text file of keys.

## 🛠️ Technical Implementation Details

### Config & Path Mapping
- **Key Source**: Standardize on `~/dbpasses.txt` as the authoritative source.
- **Proxy Endpoint**: All swarms route through `http://localhost:4000/v1`.
- **Sourcing**: Project repos will import the core library via git submodule or local python path injection.

### Execution Roadmap

#### Phase 1: Extraction (The "Harvest")
- [x] Migrate `api_consult.py` and `worker_runner.py` from `antigravity.ca` $\rightarrow$ `SWARM_CONSOLIDATED`.
- [ ] Migrate `CombineTeam` and `DebateTeam` from `FREELLM` $\rightarrow$ `SWARM_CONSOLIDATED`.
- [ ] Migrate `meta_swarm_orchestrator.py` and V2 core from `antigravity.ca` $\rightarrow$ `SWARM_CONSOLIDATED`.

#### Phase 2: Standardization
- [ ] Unify the API key loading mechanism (Standardize on `~/dbpasses.txt` and environment variables).
- [ ] Create a single, clean CLI entry point in `SWARM_CONSOLIDATED` to launch any of the swarm types.

#### Phase 3: Wiring & Integration
- [ ] Update `antigravity.ca` tools to import the consolidated library.
- [ ] Fix `.ruflo/orchestrator.py` (update `HERMES_BIN` path to `eaguiar2015` home).
- [ ] Enhance `AI_MENU` in `antigravity.ca` with a "Swarm Picker" goal-based matrix.

## ⚠️ Constraints & Risks
- **Proxy Stability**: Must ensure that moving the config doesn't break the `localhost:4000` routing.
- **Dependency Hell**: Must maintain a clean `requirements.txt` in `SWARM_CONSOLIDATED` that doesn't conflict with project-specific deps.
