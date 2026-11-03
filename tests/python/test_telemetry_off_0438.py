"""0.438.0: every child process UNI MATE starts runs with usage statistics off.

Owner's decision 03/11/2026: store pack `unimate.hyperframes` 1.0.1 sends the HeyGen e-mail and username to its
author's PostHog unless DO_NOT_TRACK=1 or HYPERFRAMES_NO_TELEMETRY=1. Packs are never edited (theo-goc rule), so UNI
MATE sets both switches for everything it runs. These checks pin each road a command or a skill script can take.
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SERVER = ROOT / "server"
sys.path.insert(0, str(SERVER))
os.environ.setdefault("UNIMATE_STATE_DIR", tempfile.mkdtemp(prefix="unimate-tel0438-"))
# A shell that says "track me" must not switch the statistics back on.
os.environ["DO_NOT_TRACK"] = "0"
os.environ.pop("HYPERFRAMES_NO_TELEMETRY", None)

_fails = []


def check(name, cond, info=""):
    print(("ok   " if cond else "FAIL ") + name + ("" if cond else f"  -> {str(info)[:300]}"))
    if not cond:
        _fails.append(name)


WANT = {"DO_NOT_TRACK": "1", "HYPERFRAMES_NO_TELEMETRY": "1"}


def has(env):
    return all(env.get(k) == v for k, v in WANT.items())


import telemetry_off  # noqa: E402

check("the two switches, nothing else", telemetry_off.VARS == WANT, telemetry_off.VARS)
d = telemetry_off.apply({"DO_NOT_TRACK": "0", "PATH": "/bin"})
check("apply(env) sets them over an inherited 0 and keeps the rest", has(d) and d["PATH"] == "/bin", d)

import main  # noqa: E402,F401

check("importing main turns them on for the server process (inherited by every child)", has(os.environ),
      {k: os.environ.get(k) for k in WANT})
SRC = (SERVER / "main.py").read_text(encoding="utf-8")
check("main applies them before its other imports",
      SRC.index("telemetry_off.apply()") < SRC.index("import brain_seed_i18n"))

# A real child: what an engine shell, an MCP server or a skill script inherits.
out = subprocess.run([sys.executable, "-c", "import os;print(os.environ.get('DO_NOT_TRACK'), "
                      "os.environ.get('HYPERFRAMES_NO_TELEMETRY'))"], capture_output=True, text=True).stdout.split()
check("a child process started by the server sees both", out == ["1", "1"], out)

import terminal  # noqa: E402

check("dashboard terminal (PTY) environment", has(terminal._env()))

import coding_terminal  # noqa: E402

check("unimate_terminal environment (built from scratch)", has(coding_terminal.env_sach()))

import run_command  # noqa: E402

check("unimate_run_command environment (built from scratch)", has(run_command._env_sach()))

import mcp_client  # noqa: E402

MC = (SERVER / "mcp_client.py").read_text(encoding="utf-8")
check("MCP servers start from the server environment", MC.count("env = dict(os.environ)") >= 2)

DOCKER = (ROOT / "Dockerfile").read_text(encoding="utf-8")
check("Docker image sets both for anything started outside the server",
      "DO_NOT_TRACK=1" in DOCKER and "HYPERFRAMES_NO_TELEMETRY=1" in DOCKER)

print()
if _fails:
    print(f"FAIL {len(_fails)}: {_fails}")
    sys.exit(1)
print("OK - test_telemetry_off_0438: all pass")
