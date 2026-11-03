# Changelog

*[Tiếng Việt](CHANGELOG.md) · **English***

UNI MATE release history, newest first. You can also read it inside the app under **Settings → Updates**.

Format: each release is a `## [x.y.z] - date` block, with changes grouped under `### Added / Fixed / Improved / Security`.

## [0.437.0] - 2026-11-03
### Improved
- **New Claude Code chats use less of your plan allowance.** The instructions sent along (about 43,000 characters) used to differ between chats only by the clock, the chat id and today's usage, so Claude loaded them from scratch for every new chat. They now stay identical and are read back from the prompt cache.
- The current time still rides on every message; the chat id and today's usage ride on the first message of the chat, so UNI MATE knows as much as before.

## [0.436.0] - 2026-11-03
### Improved
- **Teams retry a passing engine error on their own.** An overload, 503, 429 or dropped connection mid-step now reruns the step up to 2 times after a few seconds, instead of waiting for you to press Run again. The team chat shows "Temporary engine error, retrying on its own" meanwhile.
- **Never a second send or post.** A step with tools that already reached the model is not rerun, since it may have sent a message, posted or written a file. It stops with a note so you can check first.
- A plan limit, a login error or a bad request is not retried: a few more seconds will not fix it.

## [0.435.0] - 2026-11-03
### Fixed
- **Long answers no longer freeze the page while they stream in.** Every chunk used to redraw the whole answer, so the longer it got the more it stuttered, then stalled. Text now paints at most once per frame and backs off on very long answers; voice calls get the same fix.

## [0.434.0] - 2026-11-03
### Improved
- **Tables with 4 or more columns use the full chat width** instead of a narrow reading column that had to be scrolled sideways on a big screen. Text around the table keeps its readable width; a table wider than the screen still scrolls sideways.

## [0.433.0] - 2026-11-03
### Added
- **Pick a time zone in Settings → Language.** Vietnam (UTC+7) by default; when the device is in another zone, a button uses the device zone. A mistyped zone is rejected instead of saved silently.

### Fixed
- **"Today" follows the chosen time zone, not the server clock.** On a VPS running UTC, UNI MATE thought it was still yesterday between 00:00 and 07:00: daily caps of partners and Teams, ticked habits, logs and printed clocks were all seven hours off. They now share one day boundary.

## [0.432.0] - 2026-11-03
### Fixed
- **Claude's "You've hit your 5-hour limit" is now recognised as a plan limit.** The English line used to show up as the answer with no retry card; chat now says the 5-hour window is used up and schedules the retry for when it reopens. The weekly limit message is also tied to the Claude plan.
- **The reset time follows the time zone in Settings**, not the server clock. On a VPS the notice used to say 08:00 for a reset at 15:00 Vietnam time; a reset on another day now shows the date.

## [0.431.0] - 2026-11-03
### Added
- **Scheduled jobs can use the server's own Chrome.** Each schedule has a "Use the server's own Chrome" switch (off by default, full level only). When on, the AI uses only the server's Chrome at run time and never touches the Chrome on your computer.
- **Chat uses the Chrome on your computer automatically**, with no "which browser?" question when two browsers are connected.
- **Set both browser ids on the Claude Code card (Models page)**: one for chat, one for schedules. Changing machines only means editing these two fields. With no schedule id set, no schedule can use Chrome.
- Note: anyone who can open the dashboard can drive the signed-in Chrome, so keep the dashboard password safe. Customer bots and schedules made by a bot never get Chrome.

## [0.430.3] - 2026-11-03
### Improved
- **Dashboard chat can drive your real Chrome** when Claude Code runs on a subscription plan. Install the Claude in Chrome extension, open Claude Code once, type `/chrome` and pick Enabled by default; from the next chat turn the AI opens tabs, reads pages, clicks and fills forms for you. Background jobs, customer bots and API key mode never get Chrome.

## [0.430.2] - 2026-11-02
### Changed
- **The browser pane (globe button) is removed.** Google blocks automated browsers, so the pane could not do its main job of reaching Google. On the first start after updating, UNI MATE closes the background browser and deletes the pane's sign-in profile; the brain's `downloads` folder is kept.

### Improved
- **The Google Workspace card can download Gmail attachments** (for example a daily Excel report) to save them to Google Drive.

## [0.430.1] - 2026-11-02
### Improved
- **The browser button (globe) is on every screen except the Graph**, right next to Notifications. Clicking it opens the browser as a column on the right of the screen you are on: on the Chat screen the chat stays left and the browser sits on the right. Drag the pane's left edge to resize it.

### Fixed
- **The browser no longer closes right after opening** when several tabs were already open (for example the tabs restored from last time) and the pane changed size.

## [0.430.0] - 2026-11-02
### Added
- **A browser pane right next to the chat.** Open pages, switch tabs, type an address, click and type directly; the AI browses in this same browser, so you see what it is doing and can take over when needed. Sign in once and it remembers, the same on your own computer and on a VPS.

## [0.429.7] - 2026-11-02
### Fixed
- **Clicking the UNI MATE icon on Windows while it is already open brings the open window to the front** (restoring it if minimised) instead of opening another one. However many times you click, there is only one window.

## [0.429.6] - 2026-11-02
### Fixed
- **After the brain timelapse you can zoom the graph out again.** It used to stay locked at the close-up level of the first few notes.
- **The GitHub sync status line shows your local time**, not UTC, when UNI MATE runs on a VPS.
- **Syncing a brain between two machines no longer adds a `.conflict-*` file every round** for the operations index `UniMate/index.md`: each machine builds its own.

## [0.429.5] - 2026-11-01
### Improved
- **Brain sync with GitHub can run as often as every 15 minutes** (the field takes 0.25 hours). Home computer and VPS stay closer in step; the shortest used to be 1 hour.

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
