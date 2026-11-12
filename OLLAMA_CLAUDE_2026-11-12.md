# Swarm Consolidation Plan - 2026-11-12
**Agent:** Ollama-Claude
**Status:** Proposed Architecture

## 🎯 Goal
Consolidate fragmented swarm systems across `findtorontoevents_antigravity.ca` and `FREELLM` into a single, deployable orchestration layer in `SWARM_CONSOLIDATED`. This ensures a single source of truth for AI coordination logic while maintaining a clean separation between "Orchestration Logic" and "Domain Knowledge."

## 🏗️ Proposed Architecture

### 1. The "Core Library" (SWARM_CONSOLIDATED)
This repo will host the a-priori generic tools that can be used by any project.
- **Transport Layer**: `api_consult.py` (Unified API routing).
- **Worker Layer**: `worker_runner.py` (Universal agent adapter).
- **Coordination Primitives**: 
    - `CombineTeam` (Consensus aggregation).
    - `DebateTeam` (Adversarial pressure-testing).
    - `FileTeam` (Distributed file processing).
- **Meta-Orchestration**: `meta_swarm_orchestrator.py` (Self-improvement, Thompson sampling, quality scoring).
- **Proxy Management**: `litellm_config.yaml` and proxy start scripts to manage `localhost:4000/v1`.

### 2. The "Domain Layer" (Project Repos, e.g., antigravity.ca)
Project-specific logic remains in the project repo to avoid bloating the core library.
- **Personas**: `agent_personas/` (Specialist definitions).
- **Task Files**: `tasks/` or `prompts/` (What the swarm actually does).
- **Project-Specific Logic**: `ruflo/orchestrator.py` (Domain-specific wrappers).

### 3. The "Infrastructure" (Global Service)
The LiteLLM proxy remains a local service. The consolidated repo provides the configuration, and the project repos consume it as a stable endpoint.

## 🛠️ Execution Roadmap

### Phase 1: Extraction (The "Harvest")
- [ ] Migrate `api_consult.py` and `worker_runner.py` from `antigravity.ca` -> `SWARM_CONSOLIDATED`.
- [ ] Migrate `CombineTeam` and `DebateTeam` from `FREELLM` -> `SWARM_CONSOLIDATED`.
- [ ] Migrate `meta_swarm_orchestrator.py` and V2 core from `antigravity.ca` -> `SWARM_CONSOLIDATED`.

### Phase 2: Standardization
- [ ] Unify the API key loading mechanism (Standardize on `~/dbpasses.txt` and environment variables).
- [ ] Create a single, clean CLI entry point in `SWARM_CONSOLIDATED` to launch any of the swarm types.

### Phase 3: Wiring & Integration
- [ ] Update `antigravity.ca` tools to import the consolidated library (via git submodule or local path).
- [ ] Verify that the lauchers in `antigravity.ca` now use the consolidated core.

## ⚠️ Constraints & Risks
- **Proxy Stability**: Must ensure that moving the config doesn't break the `localhost:4000` routing.
- **Dependency Hell**: Must maintain a clean `requirements.txt` in `SWARM_CONSOLIDATED` that doesn't conflict with project-specific deps.
