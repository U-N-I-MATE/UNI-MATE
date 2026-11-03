/* A table of 4+ columns gets the full chat width; prose around it keeps 72ch.

       node tests/js/test_bang_rong.js

   Before: every answer bubble was capped at 72ch, so a five-column comparison table sat in a
   narrow reading column and had to be scrolled sideways even on a wide screen. */
const fs = require("fs");
const path = require("path");
const { mdToHtml } = require("../../dashboard/chat-render.js");

const CSS = fs.readFileSync(path.join(__dirname, "..", "..", "dashboard", "style.css"), "utf8");
const fails = [];
const check = (name, cond) => { console.log((cond ? "ok   " : "FAIL ") + name); if (!cond) fails.push(name); };

const row = n => "| " + Array.from({ length: n }, (_, i) => "c" + i).join(" | ") + " |";
const sep = n => "|" + "---|".repeat(n);
const table = n => [row(n), sep(n), row(n)].join("\n");

check("4 columns are marked wide", mdToHtml(table(4)).includes('class="md-tablewrap md-tablewrap-wide"'));
check("6 columns are marked wide", mdToHtml(table(6)).includes("md-tablewrap-wide"));
check("3 columns stay in the reading column", !mdToHtml(table(3)).includes("md-tablewrap-wide"));
check("2 columns stay in the reading column", !mdToHtml(table(2)).includes("md-tablewrap-wide"));

const mixed = mdToHtml("Intro.\n\n" + table(5) + "\n\nOutro.");
check("the wide table is a direct child next to the prose (the CSS relies on it)",
  /<p>Intro\.<\/p>\s*<div class="md-tablewrap md-tablewrap-wide">/.test(mixed) && /<\/div>\s*<p>Outro\.<\/p>/.test(mixed));

check("the bubble widens only when it holds a wide table",
  /\.msg-unimate \.bubble:has\(\.md-tablewrap-wide\)\s*\{\s*max-width:\s*100%/.test(CSS));
check("prose next to a wide table keeps the 72ch line length",
  /\.msg-unimate \.bubble:has\(\.md-tablewrap-wide\)\s*>\s*:not\(\.md-tablewrap-wide\)\s*\{\s*max-width:\s*72ch/.test(CSS));
check("the default bubble is still 72ch", CSS.includes(".msg-unimate .bubble { max-width: min(72ch, 100%); }"));
check("the wide table still scrolls sideways when it outgrows the screen",
  /\.md-tablewrap, \.jv-dataview \.dv-tablewrap \{[^}]*overflow-x:\s*auto/.test(CSS));

if (fails.length) { console.error("\nFAIL - test_bang_rong: " + fails.length); process.exit(1); }
console.log("\nOK - test_bang_rong: all pass");
