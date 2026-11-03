"""Usage statistics off for every child process UNI MATE starts (0.438.0).

Why. Skills from the store run third-party scripts. Owner's review 03/11/2026: `unimate.hyperframes` 1.0.1
(`skills/media-use/scripts/lib/telemetry.mjs`) now sends the HeyGen e-mail and username ($identify, $set traits) to
the author's PostHog when the user is signed in to HeyGen. The store never edits a byte of a pack (theo-goc rule), so
UNI MATE turns the statistics off from the outside, with the switches the script itself honours:

- `DO_NOT_TRACK=1`: the common opt-out (consoledonottrack.com), read by many CLIs and SDKs, not only this one.
- `HYPERFRAMES_NO_TELEMETRY=1`: the pack's own switch.

Set, not defaulted: the owner decided UNI MATE always runs with statistics off, so a `0` inherited from the shell does
not switch them back on.

Where it applies. `apply()` runs on `os.environ` when `main` is imported, before anything starts a child, so every
child that inherits the server's environment gets it: the engines (Claude Code, Codex, Grok Build, Antigravity), the
shell of an owner chat, MCP servers, skill scripts, the dashboard terminal. The few places that build an environment
from scratch call `apply(env)` themselves (`coding_terminal.env_sach` for `unimate_terminal`, `run_command._env_sach` for
`unimate_run_command`), and the Docker image sets both in `ENV` for anything started outside the server (`docker exec`,
the host panel terminal).

Not here on purpose: the improvement-trial workers (`improvement_sandbox.worker_environment`, the native protocol's
`_ENV_FIXED`). Their environment is an audited, pinned contract checked key by key, and they run against empty brains
(`empty-brains`, `empty-brain`), so no store skill and no pack script ever runs in them.
"""
from __future__ import annotations

import os
from typing import MutableMapping

VARS = {"DO_NOT_TRACK": "1", "HYPERFRAMES_NO_TELEMETRY": "1"}


def apply(env: MutableMapping[str, str] | None = None) -> MutableMapping[str, str]:
    """Put the switches into `env` (default: this process's environment) and return it."""
    target = os.environ if env is None else env
    target.update(VARS)
    return target
