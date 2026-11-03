/* Streamed answers paint at most once per frame, with backoff on slow renders.

       node tests/js/test_stream_paint.js

   Before: every stream frame re-rendered the WHOLE answer synchronously (markdownToHtml +
   innerHTML + scroll). A long, fast reply cost O(n^2) and froze the tab until it ended. */
const fs = require("fs");
const path = require("path");
const SP = require("../../dashboard/stream-paint.js");

const fails = [];
const check = (name, cond) => { console.log((cond ? "ok   " : "FAIL ") + name); if (!cond) fails.push(name); };

// A fake clock and frame queue, so the test controls time exactly.
function rig(costMs) {
  const st = { now: 0, frames: [], timers: [], painted: [] };
  const painter = SP.make(job => { st.painted.push(job); st.now += costMs(job); }, {
    now: () => st.now,
    raf: cb => st.frames.push(cb),
    setTimeout: (cb, ms) => st.timers.push({ at: st.now + ms, cb }),
  });
  st.frame = () => { const q = st.frames.splice(0); q.forEach(cb => cb()); };
  st.advance = ms => {
    st.now += ms;
    const due = st.timers.filter(t => t.at <= st.now);
    st.timers = st.timers.filter(t => t.at > st.now);
    due.forEach(t => t.cb());
  };
  return { st, painter };
}

{
  const { st, painter } = rig(() => 1);
  for (let i = 1; i <= 50; i++) painter.push("t" + i);
  check("50 chunks before a frame paint nothing yet", st.painted.length === 0);
  check("only one frame is requested for them", st.frames.length === 1);
  st.frame();
  check("the frame paints once", st.painted.length === 1);
  check("and paints the newest text", st.painted[0] === "t50");
  st.frame();
  check("no new chunk, no extra paint", st.painted.length === 1);
}

{
  // A render that costs 100ms must not run again for 200ms.
  const { st, painter } = rig(() => 100);
  painter.push("a"); st.frame();
  painter.push("b"); st.frame();
  check("a slow render is not repeated on the very next frame", st.painted.length === 1);
  check("it is rescheduled after a backoff", st.timers.length === 1 && st.timers[0].at - st.now >= 199);
  painter.push("c");
  st.advance(200); st.frame();
  check("after the backoff the newest text is painted", st.painted.length === 2 && st.painted[1] === "c");
}

{
  // The backoff is capped so the text still moves on a huge answer.
  const { st, painter } = rig(() => 5000);
  painter.push("a"); st.frame();
  painter.push("b"); st.frame();
  check("the wait is capped at MAX_GAP_MS", st.timers.length === 1 && st.timers[0].at - st.now <= SP.MAX_GAP_MS);
}

{
  const { st, painter } = rig(() => 1);
  painter.push("partial"); painter.cancel();
  st.frame();
  check("cancel: a late frame never overwrites the final render", st.painted.length === 0);
  painter.push("next"); st.frame();
  check("the painter still works after a cancel", st.painted.length === 1 && st.painted[0] === "next");
}

{
  const { st, painter } = rig(() => 1);
  painter.push("words so far");
  painter.flush();
  check("flush paints the pending text at once", st.painted.length === 1 && st.painted[0] === "words so far");
  st.frame();
  check("and the queued frame does not paint it twice", st.painted.length === 1);
}

{
  // A throwing paint must not wedge the painter.
  let n = 0;
  const frames = [];
  const p = SP.make(() => { n++; if (n === 1) throw new Error("boom"); }, { raf: cb => frames.push(cb), now: () => 0 });
  p.push(1);
  try { frames.splice(0).forEach(cb => cb()); } catch (e) {}
  p.push(2); frames.splice(0).forEach(cb => cb());
  check("a paint that throws does not stop later paints", n === 2);
}

// app.js wiring.
const APP = fs.readFileSync(path.join(__dirname, "..", "..", "dashboard", "app.js"), "utf8");
const HTML = fs.readFileSync(path.join(__dirname, "..", "..", "dashboard", "index.html"), "utf8");
const streamBlock = APP.slice(APP.indexOf('data.type === "stream"'), APP.indexOf('data.type === "stream"') + 1500);
check("the stream frame no longer renders markdown inline", !/innerHTML = markdownToHtml\(t\.text/.test(streamBlock));
check("the stream frame queues a paint", streamBlock.includes("queueStreamPaint(t, t.bubble, t.text)"));
check("the live voice transcript queues a paint too", APP.includes("queueStreamPaint(_livePaint, _liveUniMateBubble, _liveUniMateText)"));
const doneAt = APP.indexOf("const shownText = finalText");
check("the done frame drops the pending paint before the final render",
  doneAt > 0 && APP.indexOf("stopStreamPaint(t)", doneAt) > doneAt && APP.indexOf("stopStreamPaint(t)", doneAt) < APP.indexOf("veKhoiBuoc(t, false);   // het luot", doneAt));
check("the error frame keeps the words that arrived", /data\.type === "error"\) \{[\s\S]{0,200}flushStreamPaint\(t\)/.test(APP));
check("a paint skips a bubble that left the screen", /function paintStreamJob[\s\S]{0,120}isConnected/.test(APP));
check("stream-paint.js loads before app.js", HTML.indexOf("/static/stream-paint.js?v=") > 0 && HTML.indexOf("/static/stream-paint.js?v=") < HTML.indexOf("/static/app.js?v="));

if (fails.length) { console.error("\nFAIL - test_stream_paint: " + fails.length); process.exit(1); }
console.log("\nOK - test_stream_paint: all pass");
