# NOTICE

UNI MATE
Copyright (c) 2026 U.N.I SERVICE AND TRADING CO., LTD.

UNI MATE is a product of UNI TECH, a brand of U.N.I SERVICE AND TRADING CO., LTD.
Website: https://tech.unihq.vn/unimate/
Source code: https://github.com/U-N-I-MATE/UNI-MATE
U.N.I: https://unihq.vn

## Licence

UNI MATE is dual-licensed:

1. **GNU Affero General Public License v3.0 only** (`AGPL-3.0-only`), full text in `LICENSE`.
   Anyone may use, modify and redistribute UNI MATE under the AGPL. If you run a modified version
   for users over a network, you must offer those users the source code of your version.
2. **A commercial licence** from U.N.I SERVICE AND TRADING CO., LTD., for anyone who wants to use
   UNI MATE without the AGPL obligations. Contact U.N.I through https://unihq.vn.

## Third-party components

These parts are not covered by the copyright above. Each keeps its own licence, and its notice
stays with it as that licence requires.

| Component | Where | Licence | Notice |
|---|---|---|---|
| Harness² prompt definitions (Google LLC), https://github.com/google-research/harness2 | `third_party/harness2/`, adapted in `server/improvement_harness2_compose.py` | Apache-2.0 | `third_party/harness2/LICENSE`, `third_party/harness2/PROVENANCE.md` |
| UNI Sans font (U.N.I), derived from Be Vietnam Pro (The Be Vietnam Pro Project Authors) | `dashboard/fonts/` | SIL Open Font License 1.1 | `dashboard/fonts/OFL.txt` |
| CMU Pronouncing Dictionary (Carnegie Mellon University) | `server/data_phien_am/` | BSD-style | `server/data_phien_am/LICENSE-cmudict` |
| flag-icons, Copyright (c) 2013 Panayiotis Lipiridis | `docs/assets/flags/` | MIT | `docs/assets/flags/README.md` |
| acorn 8.14.0 (tests only, not shipped in the app) | `tests/js/vendor/` | MIT | `tests/js/vendor/acorn-LICENSE` |

Python and JavaScript packages installed at build or run time (see `requirements*.txt` and the
Dockerfile) keep their own licences in their packages.

Zalo features use **unimate-zalo** (https://github.com/U-N-I-MATE/unimate-zalo), a separate
program with its own `NOTICE.md`.
