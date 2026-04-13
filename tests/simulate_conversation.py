#!/usr/bin/env python3
"""
End-to-end conversation simulator.
Exercises the full state machine with realistic user inputs,
using the actual PDF knowledge base, with LLM calls mocked to be
deterministic so the flow is reproducible and testable.

Shows three scenarios:
  A) Full reboot flow → resolved
  B) Reboot not appropriate (single-device issue)
  C) Full reboot flow → not resolved → exit with next steps
"""

import sys, os, types, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ── Mock anthropic ────────────────────────────────────────────────────────────
_mock = types.ModuleType("anthropic")
class _MC:
    def __init__(self, **kw): pass
_mock.Anthropic = _MC
sys.modules["anthropic"] = _mock

from src.state_machine import State, create_session
import src.chat_handler as _ch
import src.llm_service as _llm
from src.manual_service import get_reboot_step, get_total_steps

# ── Pretty printer ────────────────────────────────────────────────────────────
W = 68

def header(title):
    print(f"\n{'━'*W}")
    print(f"  {title}")
    print(f"{'━'*W}")

def bot(text):
    print(f"\n  🤖  \033[0;36m{text}\033[0m")

def user(text):
    print(f"\n  👤  \033[0;33m{text}\033[0m")

def state_line(s):
    colors = {
        "DIAGNOSIS":    "\033[0;32m",
        "REBOOT_GUIDE": "\033[0;34m",
        "POST_CHECK":   "\033[0;35m",
        "EXIT":         "\033[0;31m",
    }
    c = colors.get(s.state.value, "")
    print(f"\n       ↳ state={c}{s.state.value}\033[0m  turn={s.total_turns}  "
          f"method={s.reboot_method or '—'}  step={s.reboot_step_index}")

def step(msg):
    print(f"\n  ⚙   {msg}")

OPENING = (
    "Hi! I'm your WiFi troubleshooting assistant for the Linksys EA6350. "
    "Let's figure out what's going on. Can you describe what's happening with your WiFi?"
)

def run_conversation(title, script):
    """
    script is a list of (user_msg, llm_stub) tuples.
    llm_stub is a dict of function → return_value to patch for that turn.
    """
    header(title)
    sess = create_session("sim")
    sess.add_message("assistant", OPENING)
    bot(OPENING)
    state_line(sess)

    handler = _ch.ChatHandler()

    for user_msg, stubs in script:
        # Install stubs
        for fn_name, retval in stubs.items():
            setattr(_llm, fn_name, retval)

        user(user_msg)
        reply = handler.process(sess, user_msg)
        bot(reply)
        state_line(sess)

    print()
    resolved_str = {True: "✅ RESOLVED", False: "❌ NOT RESOLVED", None: "—"}.get(sess.resolved)
    print(f"  Final outcome: {resolved_str}")
    print(f"  Total turns:   {sess.total_turns}")
    print(f"  Reboot used:   {sess.reboot_method or 'none'}")
    return sess


# ══════════════════════════════════════════════════════════════════════════════
# Build the actual reboot-step delivery mock — uses real manual content
# ══════════════════════════════════════════════════════════════════════════════

def make_step_presenter():
    """Returns a handle_reboot_step mock that presents real manual steps."""
    def present(msgs, step_text, step_num, total_steps):
        return (f"Step {step_num} of {total_steps}:\n"
                f"        {step_text}\n\n"
                f"        Please let me know when you've done that! ✓")
    return present


# ══════════════════════════════════════════════════════════════════════════════
# SCENARIO A — Full reboot (power cord method) → resolved
# ══════════════════════════════════════════════════════════════════════════════

step("Building Scenario A: internet unavailable, all devices, reboot → resolved")

total_soft = get_total_steps("soft_reboot")

# Per-turn stubs. Each tuple is: (user_message, {fn_name: callable})
scenario_a = [
    (
        "My internet isn't working. I can't load any websites.",
        {"handle_diagnosis": lambda m: (
            "I'm sorry to hear that! Does this affect all devices in your home, or just one specific device?",
            "need_more_info"
        )}
    ),
    (
        "All devices — my phone, laptop, and tablet.",
        {"handle_diagnosis": lambda m: (
            "Got it, all devices are affected. What does the power light on your Linksys router look like right now?",
            "need_more_info"
        )}
    ),
    (
        "It's blinking slowly.",
        {"handle_diagnosis": lambda m: (
            "A slowly blinking power light means the router is still booting up or a firmware upgrade may be in progress. "
            "Has it been doing that for more than 5 minutes?",
            "need_more_info"
        )}
    ),
    (
        "Yes, it's been like that for about 20 minutes. That doesn't seem right.",
        {
            "handle_diagnosis": lambda m: (
                "You're right — 20 minutes is too long. It should only blink during boot or firmware updates for a couple of minutes. "
                "Given that all devices are affected and the light has been blinking abnormally long, a reboot is the right next step.",
                "reboot_appropriate"
            ),
            "classify_reboot_method": lambda s: "soft_reboot",
            "handle_reboot_step": make_step_presenter(),
        }
    ),
    # Steps 2–4 of soft_reboot (step 0 was delivered automatically on transition)
    ("Done, I've disconnected both.", {"handle_reboot_step": make_step_presenter()}),
    ("Modem looks good, its light stopped blinking.", {"handle_reboot_step": make_step_presenter()}),
    ("Router light stopped blinking, it's solid now.", {"handle_reboot_step": make_step_presenter()}),
    # After last step → POST_CHECK
    (
        "Waited 2 minutes, going to try connecting now.",
        {
            "handle_post_check": lambda m: (
                "Wonderful! Were you able to connect to the internet successfully?",
                "unclear"
            )
        }
    ),
    (
        "Yes! Everything is working perfectly now.",
        {
            "handle_post_check": lambda m: ("Great to hear!", "resolved"),
            "handle_exit": lambda msgs, resolved: (
                "Excellent! The power cycle cleared whatever was causing the issue. "
                "Your Linksys EA6350 is back up and running. Have a great day! 🎉"
            ),
        }
    ),
]

sess_a = run_conversation(
    "SCENARIO A — Internet down on all devices → Reboot (power cord) → Resolved",
    scenario_a
)

assert sess_a.state == State.EXIT
assert sess_a.resolved == True
assert sess_a.reboot_method == "soft_reboot"
print("  ✅  Scenario A assertions passed")


# ══════════════════════════════════════════════════════════════════════════════
# SCENARIO B — Single device issue → no reboot → exit gracefully
# ══════════════════════════════════════════════════════════════════════════════

step("Building Scenario B: one device can't connect → reboot not appropriate")

scenario_b = [
    (
        "My laptop can't connect to WiFi but my phone is fine.",
        {"handle_diagnosis": lambda m: (
            "Interesting — if your phone is working but your laptop isn't, that points to a device-specific issue "
            "rather than a router problem. A router reboot is unlikely to help here.",
            "need_more_info"
        )}
    ),
    (
        "Yeah, I even checked and my neighbour's network is also visible on my laptop.",
        {
            "handle_diagnosis": lambda m: (
                "That confirms it — your laptop can see WiFi networks, it just can't connect to yours. "
                "This is a device-level issue, not a router issue. Rebooting the router won't fix this.",
                "reboot_not_appropriate"
            ),
            "handle_no_reboot_exit": lambda m: (
                "Since only your laptop is affected and your other devices are working fine, the issue is with "
                "your laptop's WiFi settings, not the router. Try these steps:\n\n"
                "  1. On your laptop, 'Forget' your WiFi network and reconnect with your password.\n"
                "  2. Restart your laptop's WiFi adapter (toggle Airplane mode on/off).\n"
                "  3. Restart the laptop itself.\n\n"
                "If none of that works, visit Linksys.com/support/EA6350 for more help. Good luck! 👍"
            ),
        }
    ),
]

sess_b = run_conversation(
    "SCENARIO B — Single device issue → No reboot → Graceful exit",
    scenario_b
)

assert sess_b.state == State.EXIT
assert sess_b.reboot_decision is not None
assert sess_b.resolved is None  # never got to post-check
print("  ✅  Scenario B assertions passed")


# ══════════════════════════════════════════════════════════════════════════════
# SCENARIO C — Full reboot → not resolved → exit with next steps
# ══════════════════════════════════════════════════════════════════════════════

step("Building Scenario C: reboot → not resolved → escalation")

total_web = get_total_steps("web_ui_reboot")

scenario_c = [
    (
        "My WiFi keeps dropping every few minutes. It's been happening since yesterday.",
        {"handle_diagnosis": lambda m: (
            "That intermittent dropping sounds frustrating. Does it affect all your devices simultaneously, or just one?",
            "need_more_info"
        )}
    ),
    (
        "All devices drop at the same time.",
        {
            "handle_diagnosis": lambda m: (
                "All devices dropping simultaneously points to the router losing its internet connection. "
                "This is a classic case where a reboot often clears the issue — let's try that first.",
                "reboot_appropriate"
            ),
            "classify_reboot_method": lambda s: "web_ui_reboot",
            "handle_reboot_step": make_step_presenter(),
        }
    ),
    ("I'm logged in to Linksys Smart Wi-Fi.", {"handle_reboot_step": make_step_presenter()}),
    ("I see Troubleshooting clicked.", {"handle_reboot_step": make_step_presenter()}),
    ("On the Diagnostics tab now.", {"handle_reboot_step": make_step_presenter()}),
    (
        "Clicked Reboot and then Yes. It's rebooting.",
        {
            "handle_post_check": lambda m: (
                "Great! Give it about two minutes to fully restart. Once the power light is steady, "
                "is your internet working normally now?",
                "unclear"
            )
        }
    ),
    (
        "It's still dropping. Happened again right after it came back up.",
        {
            "handle_post_check": lambda m: ("I see, the drops are continuing.", "not_resolved"),
            "handle_exit": lambda msgs, resolved: (
                "I'm sorry the reboot didn't fix the intermittent drops. Here are some next steps to try:\n\n"
                "  1. Contact your ISP and ask about outages or line quality issues in your area — "
                "intermittent drops are often caused by the connection between your ISP and your modem.\n"
                "  2. Check that all cables (especially the cable to your modem) are firmly connected.\n"
                "  3. Visit Linksys.com/support/EA6350 for additional troubleshooting guides.\n"
                "  4. If all else fails, a factory reset (hold the Reset button until the light flashes) "
                "will restore defaults — but note this will erase all your custom settings.\n\n"
                "Good luck, and don't hesitate to reach out to Linksys support for further help!"
            ),
        }
    ),
]

sess_c = run_conversation(
    "SCENARIO C — Intermittent drops → Reboot (web UI) → Not resolved → Escalation",
    scenario_c
)

assert sess_c.state == State.EXIT
assert sess_c.resolved == False
assert sess_c.reboot_method == "web_ui_reboot"
print("  ✅  Scenario C assertions passed")


# ══════════════════════════════════════════════════════════════════════════════
# Summary
# ══════════════════════════════════════════════════════════════════════════════
print(f"\n{'━'*W}")
print("  SIMULATION COMPLETE — All 3 scenarios passed ✅")
print(f"  Reboot steps sourced from: data/ea6350_reboot_instructions.json")
print(f"  Manual source: Linksys EA6350 User Guide (official PDF)")
print(f"{'━'*W}\n")
