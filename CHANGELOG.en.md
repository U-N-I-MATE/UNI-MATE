# Changelog

*[Tiếng Việt](CHANGELOG.md) · **English***

UNI MATE release history, newest first. You can also read it inside the app under **Settings → Updates**.

Format: each release is a `## [x.y.z] - date` block, with changes grouped under `### Added / Fixed / Improved / Security`.

## [0.429.4] - 2026-11-01
### Improved
- **Fewer false alarms from the automatic tests:** a test that normally takes seconds and hangs once in a while is run again once, and the log shows where it hung.

## [0.429.3] - 2026-11-01
### Added
- **A "Send now" button on a message sent while UNI MATE works:** it stops the work in progress so UNI MATE reads that message first, weighs it against what was done, then carries on or asks you.
- **The Partners page lists switched-off workflows too, with an On/Off switch on the row.** Workflows created from chat start off, so before you could not find them to switch on.

### Fixed
- **Stop now stops for good:** messages still waiting do not run by themselves afterwards, and a workflow running in the chat stops with it instead of carrying on in the background.

## [0.429.2] - 2026-11-01
### Fixed
- **The chat now shows progress while a workflow runs:** each step and command appears in the chat, and tapping the summary line lists them all. Before there was only one status line.
- **Reopening a running chat no longer shows an empty bubble** or loses the steps block.
- **Brain folder picker: paste a path and press Enter**, and the folder list always scrolls on short screens.
- **Closing the "Vault structure incomplete" banner is remembered** for that brain.
- **The pack install dialog no longer says "data only"** for a code pack switched on from the Connections page.
- **Creating or editing an agent with the UNI MATE colour or shape no longer says "That avatar colour is not valid".** The server did not yet accept the new Tech Purple colour and mascot shape.

### Improved
- **UNI MATE's default port is now 8688** on new installs, Docker, install scripts and docs. A machine with its own port in `.env` keeps that port.
- **The auto-start card, the mic hint and the voice test page show the port actually in use** instead of a fixed address.
- **ChatGPT Live voice samples now introduce themselves as Uni.** All 9 samples were re-recorded.
- **UNI MATE home page: tech.unihq.vn/unimate.** The "by UNI TECH" line, the author label on AI images and the commercial licence contact use the U.N.I domain.

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
