# Swarm Consolidation Plan - 2026-11-12
**Agent:** Ollama-Claude
**Status:** Phase 1 Complete $\rightarrow$ Phase 2 Starting

## 🎯 Goal
Consolidate fragmented swarm systems across `findtorontoevents_antigravity.ca` and `FREELLM` into a single, deployable orchestration layer in `SWARM_CONSOLIDATED`. 

## 🏗️ Architecture & Mapping

### 1. The "Core Library" (`SWARM_CONSOLIDATED`)
**Target Path: `/home/eaguiar2015/SWARM_CONSOLIDATED/core/`**

| Original Module | Target Consolidated Path | Purpose | Status |
| :--- | :--- | :--- | :--- |
| `tools/swarm/api_consult.py` | `core/transport.py` | Unified API routing via LiteLLM Proxy | ✅ Done |
| `tools/swarm/worker_runner.py` | `core/worker.py` | Universal agent adapter | ✅ Done |
| `tools/freellm.py` (Combine) | `core/combine_team.py` | Consensus aggregation logic | ✅ Done |
| `tools/freellm.py` (Debate) | `core/debate_team.py` | Adversarial pressure-testing | ✅ Done |
| `tools/freellm.py` (File) | `core/file_team.py` | Distributed file processing | ✅ Done |
| `tools/swarm_v2/meta_swarm_orchestrator.py` | `core/v2/meta_orchestrator.py` | Meta-Review & Thompson Sampling | ✅ Done |
| `tools/swarm_v2/swarms/core/base_orchestrator.py`| `core/v2/base_orchestrator.py`| V2 Base Logic | ✅ Done |
| `tools/swarm_v2/swarms/core/models.py` | `core/v2/models.py` | V2 Data Models | ✅ Done |
| `tools/swarm_v2/swarms/core/registry.py` | `core/v2/registry.py` | V2 Engine Registry | ✅ Done |
| `tools/swarm_v2/swarms/engines/*` | `core/v2/engines/*` | V2 Specialized Swarm Engines | ✅ Done |

### 2. The "Domain Layer" (`findtorontoevents_antigravity.ca`)
**These files will be modified to import from `SWARM_CONSOLIDATED` instead of local copies.**

- **`tools/ai_menu.sh`**: Update the `s|S` (swarm) case to launch a new `swarm_picker.py` (to be created) that uses the consolidated library.
- **`.ruflo/orchestrator.py`**: Modify imports to use `SWARM_CONSOLIDATED.core` and update `HERMES_BIN` to `Path.home() / ".hermes/hermes-agent/hermes"`.
- **`tools/swarm/swarm_run.py`**: Refactor to use `SWARM_CONSOLIDATED.core.transport`.
- **`tools/swarm_v2/swarms/core/llm_client.py`**: **DEPRECATE**. Logic will be moved to `SWARM_CONSOLIDATED.core.transport`.

## 🌍 Deployability & Cross-PC Compatibility

### A. Environment Agnostic Paths
- **Action**: Search and replace all hardcoded paths in `SWARM_CONSOLIDATED/core/` with `pathlib.Path.home()` for `~/dbpasses.txt` and `os.getcwd()` for repo roots.
- **Target**: Specifically `core/transport.py` and `core/v2/base_orchestrator.py`.

### B. Non-Conflicting Proxy Integration
- **Action**: Standardize `PROXY_URL = os.environ.get("SWARM_PROXY_URL", "http://localhost:4000/v1")` across all core modules.
- **Target**: All files in `SWARM_CONSOLIDATED/core/`.

## 🛠️ Execution Roadmap

### Phase 1: Extraction (The "Harvest") - [COMPLETED]
- [x] Migrate Basic Transport & Worker $\rightarrow$ `core/`
- [x] Migrate Coordination Primitives (Combine/Debate/File) $\rightarrow$ `core/`
- [x] Migrate V2 Core $\rightarrow$ `core/v2/`
- [x] Migrate V2 Engines $\rightarrow$ `core/v2/engines/`

### Phase 2: Standardization & Cleaning - [CURRENT]
- [ ] **Transport Unification**: Modify `core/v2/base_orchestrator.py` and all V2 engines to use `core/transport.py` for all API calls.
- [ ] **Mercury Scrub**: Verify 100% removal of `INCEPTION_API` / `mercury` references in consolidated code.
- [ ] **Dependency Manifest**: Create `SWARM_CONSOLIDATED/requirements.txt` including `rich`, `prompt_toolkit`, and `urllib3`.

### Phase 3: Wiring & User Experience (The "Final Mile")
- [ ] **Swarm Picker**: Create `SWARM_CONSOLIDATED/cli/swarm_picker.py` as a guided interface.
- [ ] **AI_MENU Integration**: Update `findtorontoevents_antigravity.ca/tools/ai_menu.sh` to invoke the new picker.
- [ ] **Verification**: Run a "Consolidated Smoke Test" (1 Combine, 1 Debate, 1 V2-Coding) using the new paths.

## ⚠️ Constraints & Risks
- **Pathing**: If `SWARM_CONSOLIDATED` is not installed as a package, project repos must use `sys.path.append` to the consolidated root.
- **Proxy Drift**: Changes in LiteLLM proxy aliases must be reflected in `core/combine_team.py` defaults.
