// ============================================================
// Facebook connection card for the search page.
//
// - On page load, GET /facebook/status
// - Show the correct buttons based on the response
// - "Connect Facebook" links to /facebook/connect
// - "Disconnect" POSTs to /facebook/disconnect with CSRF token
// ============================================================

(function () {
    "use strict";

    var card = document.getElementById("facebook-card");
    if (!card) return;

    var statusText = document.getElementById("fb-status-text");
    var actionsBox = document.getElementById("fb-actions");

    // Get the CSRF token from any form on the page (Flask-WTF renders one
    // in every form via csrf_token()). If none is present, we generate
    // one on demand by hitting a lightweight page. In practice the search
    // form on this page has one.
    function getCsrfToken() {
        var input = document.querySelector('input[name="csrf_token"]');
        return input ? input.value : "";
    }

    function renderDisconnected() {
        if (statusText) {
            statusText.textContent = "Status: not connected";
            statusText.className = "small mb-0 text-muted";
        }
        if (actionsBox) {
            actionsBox.innerHTML =
                '<a href="/facebook/connect" class="btn btn-primary">' +
                  '<i class="bi bi-facebook me-1"></i>Connect Facebook' +
                '</a>';
        }
    }

    function renderConnected(data) {
        var pagesText = data.pages_count === 1
            ? "1 Page"
            : (data.pages_count + " Pages");

        var names = (data.pages || [])
            .slice(0, 3)
            .map(function (p) { return p.name; })
            .join(", ");
        var more = data.pages_count > 3 ? " +" + (data.pages_count - 3) + " more" : "";

        if (statusText) {
            statusText.innerHTML =
                '<span class="text-success fw-bold">' +
                  '<i class="bi bi-check-circle-fill me-1"></i>Connected' +
                '</span>' +
                ' · ' + pagesText +
                (names ? ' · ' + escapeHtml(names) + escapeHtml(more) : '');
            statusText.className = "small mb-0";
        }

        if (actionsBox) {
            actionsBox.innerHTML =
                '<button type="button" id="fb-disconnect-btn" class="btn btn-outline-danger btn-sm">' +
                  '<i class="bi bi-x-circle me-1"></i>Disconnect Facebook' +
                '</button>';

            var btn = document.getElementById("fb-disconnect-btn");
            if (btn) {
                btn.addEventListener("click", function () {
                    if (!confirm("Disconnect Facebook? Your Pages will no longer appear in searches.")) return;
                    btn.disabled = true;
                    btn.textContent = "Disconnecting…";
                    fetch("/facebook/disconnect", {
                        method: "POST",
                        headers: { "X-CSRFToken": getCsrfToken() }
                    })
                    .then(function (r) { return r.json(); })
                    .then(function () {
                        renderDisconnected();
                    })
                    .catch(function () {
                        btn.disabled = false;
                        btn.textContent = "Disconnect Facebook";
                        alert("Could not disconnect. Please try again.");
                    });
                });
            }
        }
    }

    function escapeHtml(s) {
        return String(s == null ? "" : s)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    // ---- On page load: fetch status ----
    fetch("/facebook/status")
        .then(function (r) { return r.json(); })
        .then(function (data) {
            if (!data.configured) {
                if (statusText) {
                    statusText.textContent = "Facebook is not configured on this server.";
                    statusText.className = "small mb-0 text-muted";
                }
                if (actionsBox) actionsBox.innerHTML = "";
                return;
            }
            if (data.connected) {
                renderConnected(data);
            } else {
                renderDisconnected();
            }
        })
        .catch(function () {
            if (statusText) {
                statusText.textContent = "Could not reach the Facebook status endpoint.";
                statusText.className = "small mb-0 text-danger";
            }
        });
})();