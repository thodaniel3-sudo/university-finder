// ============================================================
// University Finder — base JavaScript
// Loaded on every page via base.html.
// Keep this file small; page-specific scripts go in their own files.
// ============================================================

(function () {
    "use strict";

    // Log once so we can confirm the file loaded during development.
    console.log("[University Finder] main.js loaded");

    // Auto-dismiss success/info alerts after 5 seconds.
    // Error and warning alerts stay until the user closes them.
    document.addEventListener("DOMContentLoaded", function () {
        var alerts = document.querySelectorAll(".alert-success, .alert-info");
        alerts.forEach(function (alert) {
            setTimeout(function () {
                if (typeof bootstrap !== "undefined" && bootstrap.Alert) {
                    var instance = bootstrap.Alert.getOrCreateInstance(alert);
                    instance.close();
                }
            }, 5000);
        });
    });
})();
