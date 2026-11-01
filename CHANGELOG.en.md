# Changelog

*[Tiếng Việt](CHANGELOG.md) · **English***

UNI MATE release history, newest first. You can also read it inside the app under **Settings → Updates**.

Format: each release is a `## [x.y.z] - date` block, with changes grouped under `### Added / Fixed / Improved / Security`.

## [0.429.2] - 2026-11-01
### Improved
- **UNI MATE's default port is now 8688** on new installs, Docker, install scripts and docs. A machine with its own port in `.env` keeps that port.
- **The auto-start card, the mic hint and the voice test page show the port actually in use** instead of a fixed address.
- **ChatGPT Live voice samples now introduce themselves as Uni.** All 9 samples were re-recorded.

### Fixed
- **The warning about call and reading voices of different genders gains a "Keep as is, don't remind me" button.** If you chose that on purpose, the screen stops nagging.

## [0.429.1] - 2026-11-01
### Added
- **UNI MATE 01: the first release of UNI MATE.** A self-hosted AI assistant by UNI TECH, U.N.I SERVICE AND TRADING CO., LTD.
- **Open source under the GNU AGPL-3.0**, with a commercial licence from U.N.I for anyone who wants to use it without the AGPL obligations. See `LICENSE` and `NOTICE.md`.
- **The voice wake name is "Uni"**, the display name is "UNI MATE". The ear fixes common mishearings such as "Diu ni", "Yu ni" and "U ni met".
- **A new UNI MATE mascot, which is also the logo and app icon.** Purple body, gold dot, pink cheeks, big white-eyed look. No mouth by default; the mouth shows only while reading an answer aloud, when a job finishes, when you heart a reply and when the mic catches your voice. When background work returns a result, the gold dot pops up above its head.
- **The look follows the UNI TECH brand:** tech-purple accent, gold secondary accent, a cool light background; the brand typeface UNI Sans ships inside the app (no Google Fonts call).
- **Its own pack store `unimate-store`** (377 packs) and **its own Zalo tool `unimate-zalo`**.
