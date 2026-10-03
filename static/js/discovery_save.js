// ============================================================
// Adds "Save to database" buttons to result cards on the search page.
//
// Behaviour:
//   - On page load, checks /discoveries/lookup for each card's URL.
//     If the URL is already in the catalog, shows "Already in database".
//   - On click, POSTs to /discoveries/save. The backend is idempotent
//     on URL, so repeat clicks bump saved_count instead of duplicating.
// ============================================================

(function () {
    "use strict";

    function detectSourceType(card) {
        var badge = card.querySelector(".badge");
        if (!badge) return "web";
        var t = badge.textContent.toLowerCase();
        if (t.indexOf("youtube") >= 0) return "youtube";
        if (t.indexOf("facebook") >= 0) return "facebook";
        if (t.indexOf("university") >= 0) return "university_official";
        if (t.indexOf("catalog") >= 0) return "discovery";
        return "web";
    }

    function markAsSaved(btn) {
        btn.disabled = true;
        btn.className = "btn btn-sm btn-success";
        btn.innerHTML = '<i class="bi bi-check2 me-1"></i>Saved';
    }

    function markAsAlreadyInDb(btn) {
        btn.disabled = true;
        btn.className = "btn btn-sm btn-success";
        btn.innerHTML = '<i class="bi bi-check2-all me-1"></i>Already in database';
    }

    function attachButtons() {
        var cards = document.querySelectorAll(".card");
        cards.forEach(function (card) {
            if (card.querySelector("[data-save-button]")) return;
            if (card.id === "facebook-card") return;

            var link = card.querySelector("a[target='_blank']");
            if (!link) return;
            var url = link.getAttribute("href") || "";
            if (!url || url.indexOf("http") !== 0) return;

            var titleEl = card.querySelector("h6");
            var title = titleEl ? titleEl.textContent.trim() : "";
            if (!title) title = "Untitled";

            var description = "";
            var paragraphs = card.querySelectorAll("p.small");
            if (paragraphs.length) {
                description = paragraphs[paragraphs.length - 1].textContent.trim();
            }

            var source_type = detectSourceType(card);

            var btn = document.createElement("button");
            btn.type = "button";
            btn.setAttribute("data-save-button", "1");
            btn.className = "btn btn-sm btn-outline-success";
            btn.innerHTML = '<i class="bi bi-database-add me-1"></i>Save to database';

            // ---- Pre-check: is this URL already in the catalog? ----
            fetch("/discoveries/lookup?url=" + encodeURIComponent(url))
                .then(function (r) { return r.json(); })
                .then(function (data) {
                    if (data && data.discovered) {
                        markAsAlreadyInDb(btn);
                    }
                })
                .catch(function () {
                    // silent — button stays clickable
                });

            // ---- On click ----
            btn.addEventListener("click", function () {
                if (btn.disabled) return;

                btn.disabled = true;
                var original = btn.innerHTML;
                btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Saving…';

                fetch("/discoveries/save", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        url: url,
                        title: title,
                        description: description,
                        source_type: source_type,
                        source_domain: (function () {
                            try { return new URL(url).hostname.replace("www.", ""); }
                            catch (e) { return ""; }
                        })()
                    })
                })
                .then(function (r) {
                    if (!r.ok) throw new Error("HTTP " + r.status);
                    return r.json();
                })
                .then(function (data) {
                    if (data.saved_count && data.saved_count > 1) {
                        markAsAlreadyInDb(btn);
                    } else {
                        markAsSaved(btn);
                    }
                })
                .catch(function () {
                    btn.disabled = false;
                    btn.className = "btn btn-sm btn-outline-danger";
                    btn.innerHTML = original + " (retry)";
                });
            });

            var actions = card.querySelector(".d-flex.flex-wrap.gap-2");
            if (actions) {
                actions.appendChild(btn);
            } else {
                var body = card.querySelector(".card-body");
                if (body) body.appendChild(btn);
            }
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", attachButtons);
    } else {
        attachButtons();
    }
})();