#!/usr/bin/env python3
"""
Swarm Picker — Guided interface for selecting the right AI orchestration tool.
Routes the user to the appropriate consolidated core module based on their goal.
"""

from __future__ import annotations
import os
import sys
import json
import urllib.request
import urllib.parse
from pathlib import Path
from typing import Optional, List, Dict, Any

# Add consolidated core to path if not installed
REPO_ROOT = Path(__file__).parent.parent
sys.path.append(str(REPO_ROOT))

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich import box
    from prompt_toolkit import prompt
    from prompt_toolkit.completion import WordCompleter
    _HAS_RICH = True
except ImportError:
    _HAS_RICH = False

con = Console() if _HAS_RICH else None

def get_proxy_models(base_url: str) -> List[str]:
    """Fetch current live aliases from the LiteLLM proxy."""
    url = base_url.rstrip("/") + "/models"
    try:
        with urllib.request.urlopen(url, timeout=5) as r:
            data = json.loads(r.read().decode("utf-8"))
            # LiteLLM /models usually returns a list of model objects with an 'id'
            models = data.get("data", [])
            return [m.get("id") for m in models if isinstance(m, dict)]
    except Exception as e:
        # Fallback to a minimal known set if proxy is down
        return ["free-mode-fast", "paid-mode", "ultra-free-cloud-fast"]

def print_picker_menu():
    if not _HAS_RICH:
        print("\n=== Swarm Picker ===\n")
        print("1: Quick Second Opinion -> swarm (CombineTeam)")
        print("2: Complex Feature/Coding -> swarmv2 (CodingSwarm)")
        print("3: Adversarial/High-Stakes -> swarm-debate (DebateTeam)")
        print("4: Deep Research -> swarm-research (ResearchSwarm)")
        print("5: Role-Specialized/Hermes -> ruflo (Ruflo Orchestrator)")
        print("6: Cheap/Free-only -> swarm-free (Auto-filtered)")
        print("\nQ: Quit")
        return

    table = Table(title="🎯 Swarm Picker: Which tool for your goal?", box=box.ROUNDED, expand=True)
    table.add_column("Option", style="cyan", justify="center")
    table.add_column("Goal", style="white")
    table.add_column("Recommended Tool", style="green")
    table.add_column("Characteristic", style="dim")

    table.add_row("1", "Quick Second Opinion", "swarm", "Fast, 3-engine consensus")
    table.add_row("2", "Complex Feature/Coding", "swarmv2", "Gen -> Review -> Test loop")
    table.add_row("3", "Adversarial/High-Stakes", "swarm-debate", "Adversarial pressure-testing")
    table.add_row("4", "Deep Research", "swarm-research", "Diverse candidates -> Synthesis")
    table.add_row("5", "Role-Specialized/Hermes", "ruflo", "Role-specialized Security Architect")
    table.add_row("6", "Cheap/Free-only", "swarm-free", "Cost-optimized / Zero-cost")

    con.print(Panel(table, border_style="blue"))

def main():
    proxy_url = os.environ.get("SWARM_PROXY_URL", "http://localhost:4000/v1")
    
    # Runtime model resolution (Requirement from Freebuff)
    live_models = get_proxy_models(proxy_url)
    
    while True:
        print("\n")
        print_picker_menu()
        
        choice = input("\nPick an option (1-6) or 'q' to quit: ").strip().lower()
        
        if choice == 'q':
            break
        
        # Map choice to a launch command or a logic flow
        # Since this is a picker, it can either:
        # 1. Execute the swarm directly using the consolidated core
        # 2. Print the command the user should run in the terminal
        
        mapping = {
            "1": ("swarm", "CombineTeam"),
            "2": ("swarmv2", "CodingSwarm"),
            "3": ("swarm-debate", "DebateTeam"),
            "4": ("swarm-research", "ResearchSwarm"),
            "5": ("ruflo", "RufloOrchestrator"),
            "6": ("swarm-free", "CombineTeam (Free)"),
        }
        
        if choice in mapping:
            tool, logic = mapping[choice]
            print(f"\n🚀 Launching {tool} using {logic} logic...")
            print(f"Using Proxy: {proxy_url}")
            print(f"Resolved {len(live_models)} live aliases from proxy.")
            # In a real implementation, this would now import from core/ and run the logic
            # For now, we provide the "guided" output.
            print(f"\n[GUIDANCE] To run this now: python3 tools/{tool}.py --query 'your query'")
        else:
            print("Invalid selection. Please choose 1-6 or 'q'.")

if __name__ == "__main__":
    main()
