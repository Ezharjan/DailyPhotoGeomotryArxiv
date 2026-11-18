/*!
 * Photo Geometry arXiv Daily — site script.
 *  - instant filtering of the paper tables (progressive enhancement: every
 *    paper is in the HTML and visible without JavaScript);
 *  - the Paper Explorer (searches the full JSON archive);
 *  - a floating "back to top" button.
 * No content is ever hidden while the page loads.
 */
(function () {
  "use strict";

  var doc = document;
  var PAGE_SIZE = 50;

  function onReady(fn) {
    if (doc.readyState === "loading") {
      doc.addEventListener("DOMContentLoaded", fn);
    } else {
      fn();
    }
  }

  function debounce(fn, wait) {
    var timer = null;
    return function () {
      var args = arguments;
      var self = this;
      clearTimeout(timer);
      timer = setTimeout(function () { fn.apply(self, args); }, wait);
    };
  }

  /* Lower-case and strip diacritics so "muller" also finds "Müller". */
  function fold(text) {
    var s = String(text || "").toLowerCase();
    if (s.normalize) {
      s = s.normalize("NFKD").replace(/[\u0300-\u036f]/g, "");
    }
    return s;
  }

  function tokens(query) {
    return fold(query).split(/\s+/).filter(Boolean);
  }

  function matchesAll(haystack, needles) {
    for (var i = 0; i < needles.length; i++) {
      if (haystack.indexOf(needles[i]) === -1) { return false; }
    }
    return true;
  }

  function fmt(n) {
    try { return Number(n).toLocaleString("en-US"); } catch (e) { return String(n); }
  }

  function plural(n, word) {
    return fmt(n) + " " + word + (n === 1 ? "" : "s");
  }

  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function safeUrl(url) {
    return /^https?:\/\//i.test(String(url || "")) ? String(url) : "";
  }

  function getParams() {
    try { return new URLSearchParams(window.location.search); } catch (e) { return null; }
  }

  /* ---------------------------------------------------------------------------
   * Table filters (home page and topic pages)
   * ------------------------------------------------------------------------- */
  function initTableFilters() {
    var boxes = doc.querySelectorAll(".pg-filter[data-pg-filter]");
    var params = getParams();
    var initialQuery = params ? (params.get("q") || "") : "";

    Array.prototype.forEach.call(boxes, function (box, index) {
      var tableId = box.getAttribute("data-pg-filter");
      var table = doc.getElementById(tableId);
      if (!table || !table.tBodies.length) { return; }
      var input = box.querySelector(".pg-filter-input");
      var codeOnly = box.querySelector("[data-pg-code-only]");
      var counter = box.querySelector(".pg-filter-count");
      var noMatch = doc.querySelector('[data-pg-no-match="' + tableId + '"]');
      var rows = Array.prototype.slice.call(table.tBodies[0].rows);
      var texts = rows.map(function (row) { return fold(row.textContent); });
      var total = rows.length;

      function apply() {
        var needles = tokens(input.value);
        var onlyCode = codeOnly && codeOnly.checked;
        var shown = 0;
        for (var i = 0; i < rows.length; i++) {
          var visible = (!onlyCode || rows[i].getAttribute("data-code") === "1") && matchesAll(texts[i], needles);
          if (rows[i].hidden === visible) { rows[i].hidden = !visible; }
          if (visible) { shown++; }
        }
        counter.textContent = (shown === total ? "" : fmt(shown) + " of ") + plural(total, "paper");
        if (noMatch) { noMatch.hidden = shown !== 0; }
      }

      input.addEventListener("input", debounce(apply, 80));
      input.addEventListener("keydown", function (event) {
        if (event.key === "Escape" && input.value) {
          input.value = "";
          apply();
        }
      });
      if (codeOnly) { codeOnly.addEventListener("change", apply); }
      box.hidden = false;
      if (index === 0 && initialQuery) {
        input.value = initialQuery;
        apply();
      }
    });
  }

  /* "/" focuses the first search box on the page (like many code hosts). */
  function initShortcut() {
    doc.addEventListener("keydown", function (event) {
      if (event.key !== "/" || event.ctrlKey || event.metaKey || event.altKey) { return; }
      var target = event.target;
      var tag = target && target.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || (target && target.isContentEditable)) { return; }
      var field = doc.querySelector("#pg-x-q, .pg-filter:not([hidden]) .pg-filter-input");
      if (field) {
        event.preventDefault();
        field.focus();
        if (field.select) { field.select(); }
      }
    });
  }

  /* ---------------------------------------------------------------------------
   * Paper Explorer
   * ------------------------------------------------------------------------- */
  function initExplorer() {
    var root = doc.getElementById("pg-explorer");
    if (!root) { return; }
    var form = root.querySelector(".pg-explorer-controls");
    var qInput = doc.getElementById("pg-x-q");
    var topicSelect = doc.getElementById("pg-x-topic");
    var sortSelect = doc.getElementById("pg-x-sort");
    var codeBox = doc.getElementById("pg-x-code");
    var status = root.querySelector(".pg-explorer-status");
    var list = doc.getElementById("pg-x-results");
    var more = doc.getElementById("pg-x-more");
    var topicsBase = root.getAttribute("data-topics-base") || "topics/";
    var papers = [];
    var topicNames = {};
    var results = [];
    var rendered = 0;

    if (form) {
      form.addEventListener("submit", function (event) { event.preventDefault(); });
    }

    function readUrl() {
      var params = getParams();
      if (!params) { return; }
      qInput.value = params.get("q") || "";
      var topic = params.get("topic") || "";
      if (topic && topicSelect.querySelector('option[value="' + topic.replace(/["\\]/g, "") + '"]')) {
        topicSelect.value = topic;
      }
      sortSelect.value = params.get("sort") === "oldest" ? "oldest" : "newest";
      codeBox.checked = params.get("code") === "1";
    }

    function writeUrl() {
      if (!window.history || !window.history.replaceState) { return; }
      var parts = [];
      if (qInput.value.trim()) { parts.push("q=" + encodeURIComponent(qInput.value.trim())); }
      if (topicSelect.value) { parts.push("topic=" + encodeURIComponent(topicSelect.value)); }
      if (sortSelect.value === "oldest") { parts.push("sort=oldest"); }
      if (codeBox.checked) { parts.push("code=1"); }
      var url = window.location.pathname + (parts.length ? "?" + parts.join("&") : "") + window.location.hash;
      window.history.replaceState(null, "", url);
    }

    function timeHtml(day) {
      return '<time datetime="' + escapeHtml(day) + '">' + escapeHtml(day) + "</time>";
    }

    /* "submitted from <oldest> to <newest>" for a list sorted by date (either direction). */
    function spanHtml(list) {
      var a = list[0].published;
      var b = list[list.length - 1].published;
      var oldest = a < b ? a : b;
      var newest = a < b ? b : a;
      return oldest === newest ? "submitted on " + timeHtml(newest)
        : "submitted from " + timeHtml(oldest) + " to " + timeHtml(newest);
    }

    function authorsText(p) {
      var authors = p.authors || [];
      var total = Math.max(p.n_authors || 0, authors.length);
      return authors.slice(0, 3).join(", ") + (total > 3 ? " et al." : "");
    }

    function cardHtml(p) {
      var id = escapeHtml(p.id);
      var abs = "https://arxiv.org/abs/" + encodeURI(p.id);
      var pdf = "https://arxiv.org/pdf/" + encodeURI(p.id);
      var meta = '<time datetime="' + escapeHtml(p.published) + '">' + escapeHtml(p.published) + "</time>" +
        '<span class="pg-id">arXiv:' + id + "</span>";
      if (p.primary_category) { meta += '<span class="pg-cat">' + escapeHtml(p.primary_category) + "</span>"; }
      if (p.journal_ref) { meta += '<span class="pg-venue">' + escapeHtml(p.journal_ref) + "</span>"; }
      if (p.comment) { meta += '<span class="pg-comment">' + escapeHtml(p.comment) + "</span>"; }
      var tags = (p.topics || []).filter(function (slug) { return topicNames[slug]; }).map(function (slug) {
        return '<a class="pg-tag" href="' + escapeHtml(topicsBase + slug + ".html") + '">' + escapeHtml(topicNames[slug]) + "</a>";
      }).join(" ");
      var buttons = '<a class="pg-btn" href="' + escapeHtml(pdf) + '" target="_blank" rel="noopener">PDF</a>';
      var code = safeUrl(p.code);
      var project = safeUrl(p.project);
      if (code) { buttons += '<a class="pg-btn pg-btn-code" href="' + escapeHtml(code) + '" target="_blank" rel="noopener">Code</a>'; }
      if (project) { buttons += '<a class="pg-btn" href="' + escapeHtml(project) + '" target="_blank" rel="noopener">Project</a>'; }
      var allAuthors = (p.authors || []).join(", ");
      return '<li class="pg-result">' +
        '<a class="pg-title-link" href="' + escapeHtml(abs) + '" target="_blank" rel="noopener">' + escapeHtml(p.title) + "</a>" +
        '<div class="pg-meta">' + meta + "</div>" +
        '<div class="pg-authors" title="' + escapeHtml(allAuthors) + '">' + escapeHtml(authorsText(p)) + "</div>" +
        (tags ? '<div class="pg-tags"><span class="pg-tags-label">Topics:</span> ' + tags + "</div>" : "") +
        '<div class="pg-btns">' + buttons + "</div></li>";
    }

    function renderMore() {
      var next = results.slice(rendered, rendered + PAGE_SIZE);
      list.insertAdjacentHTML("beforeend", next.map(cardHtml).join(""));
      rendered += next.length;
      more.hidden = rendered >= results.length;
      if (!more.hidden) {
        more.textContent = "Show more (" + fmt(results.length - rendered) + " remaining)";
      }
    }

    function update() {
      var needles = tokens(qInput.value);
      var topic = topicSelect.value;
      var onlyCode = codeBox.checked;
      results = papers.filter(function (p) {
        if (topic && (p.topics || []).indexOf(topic) === -1) { return false; }
        if (onlyCode && !safeUrl(p.code)) { return false; }
        return matchesAll(p._text, needles);
      });
      if (sortSelect.value === "oldest") { results.reverse(); }
      list.innerHTML = "";
      rendered = 0;
      if (!results.length) {
        status.textContent = papers.length
          ? "No papers match these filters (" + plural(papers.length, "paper") + " in the archive)."
          : "No papers yet. The first run of the daily workflow fills the archive.";
        more.hidden = true;
      } else {
        var count = results.length === papers.length ? plural(papers.length, "paper") + " "
          : fmt(results.length) + " of " + plural(papers.length, "paper") + (results.length === 1 ? " matches, " : " match, ");
        status.innerHTML = escapeHtml(count) + spanHtml(results);
        renderMore();
      }
      writeUrl();
    }

    function load(data) {
      (data.topics || []).forEach(function (t) { topicNames[t.slug] = t.name; });
      papers = Object.keys(data.papers || {}).map(function (key) { return data.papers[key]; })
        .filter(function (p) { return (p.topics || []).some(function (slug) { return topicNames[slug]; }); });
      papers.forEach(function (p) {
        p._text = fold([p.title, (p.authors || []).join(" "), p.id, "arxiv:" + p.id, p.comment,
          p.journal_ref, (p.categories || []).join(" ")].join(" "));
      });
      papers.sort(function (a, b) {
        if (a.published !== b.published) { return a.published < b.published ? 1 : -1; }
        return a.id < b.id ? 1 : (a.id > b.id ? -1 : 0);
      });
      readUrl();
      var debounced = debounce(update, 120);
      qInput.addEventListener("input", debounced);
      qInput.addEventListener("keydown", function (event) {
        if (event.key === "Escape" && qInput.value) { qInput.value = ""; update(); }
      });
      topicSelect.addEventListener("change", update);
      sortSelect.addEventListener("change", update);
      codeBox.addEventListener("change", update);
      more.addEventListener("click", renderMore);
      update();
    }

    var src = root.getAttribute("data-src");
    if (!src || !window.fetch) {
      status.textContent = "Your browser cannot load the paper archive. Please use the topic pages instead.";
      return;
    }
    fetch(src, { credentials: "same-origin" })
      .then(function (response) {
        if (!response.ok) { throw new Error("HTTP " + response.status); }
        return response.json();
      })
      .then(load)
      .catch(function (error) {
        status.textContent = "Could not load the paper archive (" + error.message + "). Please reload the page.";
      });
  }

  /* ---------------------------------------------------------------------------
   * Back to top
   * ------------------------------------------------------------------------- */
  function initBackToTop() {
    var button = doc.createElement("a");
    button.className = "pg-top";
    button.href = "#top";
    button.setAttribute("aria-label", "Back to top");
    button.setAttribute("title", "Back to top");
    button.textContent = "\u2191";
    doc.body.appendChild(button);
    var ticking = false;
    function refresh() {
      ticking = false;
      var visible = (window.pageYOffset || doc.documentElement.scrollTop) > 600;
      button.classList.toggle("pg-top-visible", visible);
    }
    window.addEventListener("scroll", function () {
      if (!ticking) {
        ticking = true;
        window.requestAnimationFrame(refresh);
      }
    }, { passive: true });
    refresh();
  }

  onReady(function () {
    var steps = [initTableFilters, initShortcut, initExplorer, initBackToTop];
    for (var i = 0; i < steps.length; i++) {
      try { steps[i](); } catch (error) {
        if (window.console && console.error) { console.error("photogeo:", error); }
      }
    }
  });
})();
