/* stream-paint.js - paint streamed answer text at most once per frame, never per chunk.

   Pure module: no DOM of its own. app.js hands it a paint function and pushes the latest
   text on every stream frame; the painter keeps only the newest job and runs it on the next
   animation frame.

   Why: a stream frame used to re-render the WHOLE answer (markdownToHtml + innerHTML +
   scroll) synchronously. A fast engine sends many frames per second, and each render grows
   with the answer, so a long reply cost O(n^2) and the tab froze until the turn ended.

   Rules:
     1. Coalesce: many pushes before the next frame become ONE paint of the newest text.
     2. Back off on slow renders: after a paint that took `cost` ms, the next one waits at
        least min(maxGapMs, 2 * cost) ms. Rendering then never takes more than about a third
        of the main thread, however long the answer gets.
     3. cancel() drops the pending job, so a late frame never overwrites the final render.
        flush() paints the pending job right now (used when the turn errors out).

   Note: never use the em dash character in this file. */
(function () {
  "use strict";

  var MAX_GAP_MS = 400;

  function make(paint, opts) {
    opts = opts || {};
    var root = typeof window !== "undefined" ? window : {};
    var raf = opts.raf || (root.requestAnimationFrame ? root.requestAnimationFrame.bind(root)
      : function (cb) { return setTimeout(cb, 16); });
    var later = opts.setTimeout || setTimeout;
    var clock = opts.now || function () {
      return (root.performance && root.performance.now) ? root.performance.now() : Date.now();
    };
    var maxGap = opts.maxGapMs == null ? MAX_GAP_MS : opts.maxGapMs;

    var pending = null, scheduled = false, lastCost = 0, lastEnd = -Infinity, paints = 0;

    function draw(job) {
      var t0 = clock();
      try { paint(job); } finally {
        lastEnd = clock();
        lastCost = lastEnd - t0;
        paints++;
      }
    }

    function run() {
      scheduled = false;
      if (pending === null) return;            // cancelled or already flushed
      var wait = Math.min(maxGap, 2 * lastCost) - (clock() - lastEnd);
      if (wait > 0) {
        scheduled = true;
        later(function () { raf(run); }, wait);
        return;
      }
      var job = pending;
      pending = null;
      draw(job);
    }

    return {
      push: function (job) {
        pending = job;
        if (!scheduled) { scheduled = true; raf(run); }
      },
      flush: function () {
        if (pending === null) return;
        var job = pending;
        pending = null;
        draw(job);
      },
      cancel: function () { pending = null; },
      hasPending: function () { return pending !== null; },
      paints: function () { return paints; }
    };
  }

  var api = { make: make, MAX_GAP_MS: MAX_GAP_MS };
  if (typeof window !== "undefined") window.UniMateStreamPaint = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})();
