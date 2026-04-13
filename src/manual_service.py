"""
Manual service: loads and retrieves reboot instructions from the structured
data file extracted from the Linksys EA6350 user guide PDF.

This module is the ONLY source of reboot steps — the LLM is never allowed
to fabricate steps from its own knowledge.
"""

import json
import logging
from pathlib import Path
from functools import lru_cache
from typing import Optional

logger = logging.getLogger(__name__)

# Path to extracted manual data relative to project root
_DATA_FILE = Path(__file__).parent / "ea6350_reboot_instructions.json"
_DATA_FILE_FALLBACK = Path(__file__).resolve().parents[1] / "data" / "ea6350_reboot_instructions.json"


@lru_cache(maxsize=1)
def load_manual() -> dict:
    """Load and cache the manual data. Called once at startup."""
    data_file = _DATA_FILE if _DATA_FILE.exists() else _DATA_FILE_FALLBACK
    if not data_file.exists():
        raise FileNotFoundError(f"Manual data file not found: {data_file}")
    with open(data_file, "r") as f:
        data = json.load(f)
    logger.info(f"Loaded router manual: {data['router_model']} from {data['manual_source']}")
    return data


def get_reboot_method(method_id: str) -> Optional[dict]:
    """Return a specific reboot method by ID (soft_reboot, web_ui_reboot, factory_reset)."""
    manual = load_manual()
    for method in manual["reboot_methods"]:
        if method["method_id"] == method_id:
            return method
    logger.warning(f"Reboot method '{method_id}' not found in manual")
    return None


def get_reboot_step(method_id: str, step_index: int) -> Optional[str]:
    """Return a single reboot step by method and 0-based index."""
    method = get_reboot_method(method_id)
    if not method:
        return None
    steps = method["steps"]
    if 0 <= step_index < len(steps):
        return steps[step_index]
    return None


def get_total_steps(method_id: str) -> int:
    """Return the total number of steps for a given reboot method."""
    method = get_reboot_method(method_id)
    if not method:
        return 0
    return len(method["steps"])


def get_all_reboot_methods_summary() -> str:
    """Return a summary of all reboot methods for the LLM system prompt."""
    manual = load_manual()
    lines = [f"Router: {manual['router_model']}", ""]
    for method in manual["reboot_methods"]:
        lines.append(f"Method: {method['method_id']} — {method['title']}")
        lines.append(f"Description: {method['description']}")
        if "warning" in method:
            lines.append(f"WARNING: {method['warning']}")
        lines.append(f"Steps ({len(method['steps'])} total):")
        for i, step in enumerate(method["steps"], 1):
            lines.append(f"  {i}. {step}")
        lines.append("")
    return "\n".join(lines)


def get_router_lights_info() -> str:
    """Return router light indicator info as a string."""
    manual = load_manual()
    lights = manual.get("router_lights", {})
    lines = ["Router Light Indicators:"]
    for light_name, states in lights.items():
        lines.append(f"\n{light_name.upper()} light:")
        for state, meaning in states.items():
            lines.append(f"  {state.replace('_', ' ')}: {meaning}")
    return "\n".join(lines)


def get_when_to_reboot_guidance() -> dict:
    """Return the when-to-reboot and when-not-to-reboot lists."""
    manual = load_manual()
    return {
        "when_to_reboot": manual.get("when_to_reboot", []),
        "when_not_to_reboot": manual.get("when_not_to_reboot", []),
    }
