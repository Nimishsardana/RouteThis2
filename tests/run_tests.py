#!/usr/bin/env python3
"""
Standalone test runner — no pytest, no external dependencies required.
Mocks out the Azure AI inference modules so tests run without the packages installed.
"""

import sys, os, json, types, traceback
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ── Mock the Azure modules BEFORE any project imports ──────────────────
_mock_azure = types.ModuleType("azure")
_mock_azure_ai = types.ModuleType("azure.ai")
_mock_azure_ai_inference = types.ModuleType("azure.ai.inference")
_mock_azure_ai_inference_models = types.ModuleType("azure.ai.inference.models")
_mock_azure_core = types.ModuleType("azure.core")
_mock_azure_core_credentials = types.ModuleType("azure.core.credentials")

class _MockMessage:
    def __init__(self, content=""):
        self.content = content

class _MockResponse:
    def __init__(self):
        self.choices = [types.SimpleNamespace(message=_MockMessage("test response"))]

class _MockClient:
    def __init__(self, **kw): pass
    def complete(self, **kw): return _MockResponse()

class _MockCredential:
    def __init__(self, *args, **kw): pass

# Setup message classes
_mock_azure_ai_inference_models.SystemMessage = _MockMessage
_mock_azure_ai_inference_models.UserMessage = _MockMessage
_mock_azure_ai_inference_models.AssistantMessage = _MockMessage

_mock_azure_ai_inference.ChatCompletionsClient = _MockClient
_mock_azure_core_credentials.AzureKeyCredential = _MockCredential

sys.modules["azure"] = _mock_azure
sys.modules["azure.ai"] = _mock_azure_ai
sys.modules["azure.ai.inference"] = _mock_azure_ai_inference
sys.modules["azure.ai.inference.models"] = _mock_azure_ai_inference_models
sys.modules["azure.core"] = _mock_azure_core
sys.modules["azure.core.credentials"] = _mock_azure_core_credentials

# ── Tiny harness ──────────────────────────────────────────────────────────
_passed, _failed, _suite = [], [], ""

def suite(name):
    global _suite
    _suite = name
    print(f"\n{'='*60}\n  {name}\n{'='*60}")

def run(name, fn):
    label = f"{_suite} :: {name}"
    try:
        fn()
        _passed.append(label)
        print(f"  ✅  {name}")
    except AssertionError as e:
        _failed.append((label, str(e)))
        print(f"  ❌  {name}\n      {e}")
    except Exception:
        tb = traceback.format_exc()
        _failed.append((label, tb))
        print(f"  💥  {name}")
        for line in tb.strip().splitlines()[-3:]:
            print(f"      {line}")

def eq(a, b, m=""): assert a == b, m or f"Expected {b!r}, got {a!r}"
def has(needle, container, m=""): assert needle in container, m or f"{needle!r} not found"
def none(v): assert v is None, f"Expected None, got {v!r}"
def notnone(v): assert v is not None, "Expected non-None"
def true(v, m=""): assert v, m or f"Expected truthy"
def gt(a, b, m=""): assert a > b, m or f"{a} not > {b}"

# ── Imports under test ────────────────────────────────────────────────────
from src.state_machine import State, RebootDecision, create_session
from src.manual_service import (
    load_manual, get_reboot_method, get_reboot_step,
    get_total_steps, get_all_reboot_methods_summary,
    get_when_to_reboot_guidance, get_router_lights_info,
)


# ════════════════════════════════════════════════════════════════════════
# SUITE 1 — State Machine
# ════════════════════════════════════════════════════════════════════════
suite("State Machine")

def sm01():
    eq(create_session("s1").state, State.DIAGNOSIS)
run("Initial state is DIAGNOSIS", sm01)

def sm02():
    s = create_session("s2"); s.add_message("user", "hi")
    eq(s.total_turns, 1)
run("User message increments total_turns", sm02)

def sm03():
    s = create_session("s3"); s.add_message("assistant", "hi")
    eq(s.total_turns, 0)
run("Assistant message does NOT increment total_turns", sm03)

def sm04():
    s = create_session("s4")
    s.add_message("user", "msg1")
    eq(s.diagnosis_turn_count, 1)
    s.transition_to(State.REBOOT_GUIDE)
    s.add_message("user", "done")          # not in DIAGNOSIS
    eq(s.diagnosis_turn_count, 1)
    eq(s.total_turns, 2)
run("diagnosis_turn_count only increments in DIAGNOSIS", sm04)

def sm05():
    s = create_session("s5"); s.transition_to(State.REBOOT_GUIDE)
    eq(s.state, State.REBOOT_GUIDE)
run("State transition works", sm05)

def sm06():
    s = create_session("s6")
    for st in (State.REBOOT_GUIDE, State.POST_CHECK, State.EXIT):
        s.transition_to(st); eq(s.state, st)
run("Full sequence DIAGNOSIS→REBOOT_GUIDE→POST_CHECK→EXIT", sm06)

def sm07():
    s = create_session("s7"); s.transition_to(State.REBOOT_GUIDE)
    s.reboot_method = "soft_reboot"
    d = s.to_dict()
    eq(d["state"], "REBOOT_GUIDE"); eq(d["reboot_method"], "soft_reboot")
    eq(d["session_id"], "s7"); none(d["resolved"])
run("to_dict serializes correctly", sm07)

def sm08():
    s1 = create_session("a"); s2 = create_session("b")
    assert s1 is not s2
    s1.transition_to(State.EXIT)
    eq(s2.state, State.DIAGNOSIS)
run("Sessions are independent objects", sm08)

def sm09():
    s = create_session("s9")
    s.add_message("user", "hello"); s.add_message("assistant", "hi"); s.add_message("user", "ok")
    eq(len(s.messages), 3); eq(s.messages[1]["content"], "hi")
run("Message history appended in order", sm09)

def sm10():
    s = create_session("s10"); none(s.reboot_decision)
    s.reboot_decision = RebootDecision.REBOOT_APPROPRIATE
    eq(s.reboot_decision, RebootDecision.REBOOT_APPROPRIATE)
run("reboot_decision field stores enum correctly", sm10)


# ════════════════════════════════════════════════════════════════════════
# SUITE 2 — Manual Service
# ════════════════════════════════════════════════════════════════════════
suite("Manual Service (PDF Grounding)")

def ms01(): notnone(load_manual())
run("Manual loads from JSON file", ms01)

def ms02(): has("EA6350", load_manual()["router_model"])
run("Router model is EA6350", ms02)

def ms03(): has("linksys", load_manual()["manual_source"].lower())
run("Source URL references linksys.com", ms03)

def ms04():
    ids = [m["method_id"] for m in load_manual()["reboot_methods"]]
    for mid in ("soft_reboot", "web_ui_reboot", "factory_reset"): has(mid, ids)
run("All three reboot methods present", ms04)

def ms05():
    m = get_reboot_method("soft_reboot"); notnone(m); has("steps", m); gt(len(m["steps"]), 0)
run("get_reboot_method: soft_reboot returns valid dict", ms05)

def ms06(): none(get_reboot_method("not_a_method"))
run("get_reboot_method: unknown returns None", ms06)

def ms07():
    step = get_reboot_step("soft_reboot", 0); notnone(step); gt(len(step), 15)
run("get_reboot_step: step 0 is non-trivial", ms07)

def ms08(): none(get_reboot_step("soft_reboot", 9999))
run("get_reboot_step: out-of-bounds returns None", ms08)

def ms09(): none(get_reboot_step("soft_reboot", -1))
run("get_reboot_step: negative index returns None", ms09)

def ms10():
    for mid in ("soft_reboot", "web_ui_reboot", "factory_reset"):
        gt(get_total_steps(mid), 0, f"{mid} must have >0 steps")
run("get_total_steps: all methods > 0", ms10)

def ms11(): eq(get_total_steps("invalid"), 0)
run("get_total_steps: unknown returns 0", ms11)

def ms12():
    for mid in ("soft_reboot", "web_ui_reboot", "factory_reset"):
        for i in range(get_total_steps(mid)):
            s = get_reboot_step(mid, i)
            notnone(s); gt(len(s.strip()), 5, f"{mid}[{i}] too short")
run("All steps accessible sequentially", ms12)

def ms13():
    s = get_all_reboot_methods_summary()
    for tok in ("soft_reboot", "web_ui_reboot", "factory_reset", "EA6350"): has(tok, s)
run("Summary contains all method IDs and router model", ms13)

def ms14():
    g = get_when_to_reboot_guidance()
    gt(len(g["when_to_reboot"]), 0); gt(len(g["when_not_to_reboot"]), 0)
run("when_to_reboot guidance has both lists", ms14)

def ms15():
    info = get_router_lights_info(); gt(len(info), 50); has("power", info.lower())
run("router_lights_info is non-empty and mentions 'power'", ms15)

def ms16():
    for mid in ("soft_reboot", "web_ui_reboot", "factory_reset"):
        for i in range(get_total_steps(mid)):
            true(isinstance(get_reboot_step(mid, i), str))
run("All steps are str type", ms16)


# ════════════════════════════════════════════════════════════════════════
# SUITE 3 — PDF Guardrails
# ════════════════════════════════════════════════════════════════════════
suite("PDF Grounding & Guardrails")

def gr01():
    text = " ".join(get_reboot_method("soft_reboot")["steps"]).lower()
    true(any(w in text for w in ["unplug","power","cord","plug","wait"]), f"No physical action in: {text[:150]}")
run("Soft reboot mentions power/cord actions", gr01)

def gr02():
    text = " ".join(get_reboot_method("soft_reboot")["steps"]).lower()
    true("reset button" not in text, "Soft reboot should not mention 'reset button'")
run("Soft reboot does NOT mention Reset button", gr02)

def gr03():
    m = get_reboot_method("factory_reset")
    true("warning" in m or "caution" in m, "factory_reset must have warning or caution key")
run("Factory reset has warning/caution key", gr03)

def gr04():
    text = " ".join(get_reboot_method("web_ui_reboot")["steps"])
    true("192.168.1.1" in text or "myrouter.local" in text, "Admin URL missing from web UI steps")
run("Web UI reboot references admin URL", gr04)

def gr05():
    for mid in ("soft_reboot", "web_ui_reboot", "factory_reset"):
        text = " ".join(get_reboot_method(mid)["steps"]).lower()
        for brand in ("netgear", "asus", "tp-link", "tplink", "dlink"):
            true(brand not in text, f"Competitor '{brand}' in {mid}")
run("No steps reference competitor brands", gr05)

def gr06():
    for mid in ("soft_reboot", "web_ui_reboot", "factory_reset"):
        eq(get_total_steps(mid), len(get_reboot_method(mid)["steps"]))
run("Step count consistent between helper and raw data", gr06)

def gr07():
    text = " ".join(get_reboot_method("factory_reset")["steps"]).lower()
    has("reset", text)
run("Factory reset steps reference 'reset'", gr07)

def gr08():
    from pathlib import Path
    with open(Path(__file__).parent / "data" / "ea6350_reboot_instructions.json") as f:
        data = json.load(f)
    for key in ("router_model", "manual_source", "reboot_methods", "router_lights"):
        has(key, data, f"Missing key: {key}")
run("Manual JSON has all required top-level keys", gr08)

def gr09():
    m = get_reboot_method("factory_reset")
    warn_text = (m.get("warning", "") + m.get("caution", "")).lower()
    keywords = ["settings", "erase", "custom", "default", "wifi", "password", "configure"]
    true(any(k in warn_text for k in keywords), f"Warning doesn't mention data: '{warn_text}'")
run("Factory reset warning mentions settings/data erasure", gr09)


# ════════════════════════════════════════════════════════════════════════
# SUITE 4 — Chat Handler Routing (Stubbed LLM)
# ════════════════════════════════════════════════════════════════════════
suite("Chat Handler Routing (Stubbed LLM)")

import src.llm_service as _llm
import src.chat_handler as _ch

def _sess(state=State.DIAGNOSIS, method=None, step=0):
    s = create_session("ch"); s.state = state
    s.reboot_method = method; s.reboot_step_index = step
    s.add_message("assistant", "Opening"); return s

def ch01():
    _llm.handle_diagnosis = lambda m: ("Tell me more?", "need_more_info")
    s = _sess(); _ch.ChatHandler().process(s, "slow internet"); eq(s.state, State.DIAGNOSIS)
run("DIAGNOSIS: need_more_info keeps DIAGNOSIS", ch01)

def ch02():
    _llm.handle_diagnosis = lambda m: ("Reboot.", "reboot_appropriate")
    _llm.classify_reboot_method = lambda s: "soft_reboot"
    _llm.handle_reboot_step = lambda msgs, step_text, step_num, total_steps: f"Step {step_num}"
    s = _sess(); _ch.ChatHandler().process(s, "all down")
    eq(s.state, State.REBOOT_GUIDE); eq(s.reboot_method, "soft_reboot"); eq(s.reboot_step_index, 0)
run("DIAGNOSIS: reboot_appropriate → REBOOT_GUIDE", ch02)

def ch03():
    _llm.handle_diagnosis = lambda m: ("Device-specific.", "reboot_not_appropriate")
    _llm.handle_no_reboot_exit = lambda m: "Restart your device."
    s = _sess(); _ch.ChatHandler().process(s, "one phone only")
    eq(s.state, State.EXIT); eq(s.reboot_decision, RebootDecision.REBOOT_NOT_APPROPRIATE)
run("DIAGNOSIS: reboot_not_appropriate → EXIT", ch03)

def ch04():
    _llm.handle_reboot_step = lambda msgs, step_text, step_num, total_steps: f"Step {step_num}"
    s = _sess(state=State.REBOOT_GUIDE, method="soft_reboot", step=0)
    _ch.ChatHandler().process(s, "done"); eq(s.reboot_step_index, 1)
run("REBOOT_GUIDE: reply advances step_index", ch04)

def ch05():
    total = get_total_steps("soft_reboot")
    _llm.handle_reboot_step = lambda msgs, step_text, step_num, total_steps: f"Step {step_num}"
    _llm.handle_post_check = lambda m: ("Fixed?", "unclear")
    s = _sess(state=State.REBOOT_GUIDE, method="soft_reboot", step=total - 1)
    _ch.ChatHandler().process(s, "done"); eq(s.state, State.POST_CHECK)
run("REBOOT_GUIDE: after last step → POST_CHECK", ch05)

def ch06():
    _llm.handle_post_check = lambda m: ("Great!", "resolved")
    _llm.handle_exit = lambda msgs, resolved: "Goodbye!"
    s = _sess(state=State.POST_CHECK, method="soft_reboot")
    _ch.ChatHandler().process(s, "yes works!"); eq(s.state, State.EXIT); eq(s.resolved, True)
run("POST_CHECK: resolved → EXIT, resolved=True", ch06)

def ch07():
    _llm.handle_post_check = lambda m: ("Sorry.", "not_resolved")
    _llm.handle_exit = lambda msgs, resolved: "Contact support."
    s = _sess(state=State.POST_CHECK, method="soft_reboot")
    _ch.ChatHandler().process(s, "still broken"); eq(s.state, State.EXIT); eq(s.resolved, False)
run("POST_CHECK: not_resolved → EXIT, resolved=False", ch07)

def ch08():
    _llm.handle_post_check = lambda m: ("Clarify?", "unclear")
    s = _sess(state=State.POST_CHECK, method="soft_reboot")
    _ch.ChatHandler().process(s, "maybe"); eq(s.state, State.POST_CHECK)
run("POST_CHECK: unclear stays in POST_CHECK", ch08)

def ch09():
    s = _sess(state=State.EXIT); r = _ch.ChatHandler().process(s, "thanks"); gt(len(r), 0)
run("EXIT state returns non-empty fallback message", ch09)

def ch10():
    _llm.handle_diagnosis = lambda m: ("Need more", "need_more_info")
    _llm.handle_reboot_step = lambda msgs, step_text, step_num, total_steps: f"Step {step_num}"
    s = _sess(); s.diagnosis_turn_count = _ch.MAX_DIAGNOSIS_TURNS - 1
    _ch.ChatHandler().process(s, "confused"); eq(s.state, State.REBOOT_GUIDE)
run("Max diagnosis turns forces reboot transition", ch10)

def ch11():
    captured = {}
    def mock_step(msgs, step_text, step_num, total_steps):
        captured["step_text"] = step_text; return f"Step {step_num}"
    _llm.handle_diagnosis = lambda m: ("Reboot.", "reboot_appropriate")
    _llm.classify_reboot_method = lambda s: "soft_reboot"
    _llm.handle_reboot_step = mock_step
    s = _sess(); _ch.ChatHandler().process(s, "wifi down")
    eq(captured["step_text"], get_reboot_step("soft_reboot", 0),
       "Step text must come exactly from manual, not LLM imagination")
run("Reboot step text injected to LLM matches manual exactly", ch11)


# ════════════════════════════════════════════════════════════════════════
# Results
# ════════════════════════════════════════════════════════════════════════
total = len(_passed) + len(_failed)
print(f"\n{'═'*60}")
print(f"  RESULTS: {len(_passed)}/{total} passed  |  {len(_failed)} failed")
print(f"{'═'*60}")
if _failed:
    print("\n  FAILURES:")
    for name, err in _failed:
        print(f"\n  ❌  {name}")
        for line in err.strip().splitlines()[-4:]: print(f"      {line}")
print()
sys.exit(0 if not _failed else 1)
