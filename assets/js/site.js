/* WATcalendars - client for the static calendar index.
 *
 * The .ics files live in this same repository, so GitHub Pages serves
 * them from the same origin: no CORS, no API rate limits, and the
 * subscription URL is just a relative path made absolute.
 */
(function () {
    "use strict";

    var INDEX_URL = "db/calendars/index.json";
    var STATUS_URL = "db/calendars/status.json";
    var REPO_TREE = "https://github.com/dominikx2002/WATcalendars/tree/main/db/calendars";
    var MAX_RESULTS = 40;

    // Polish counts take three forms: 1 grupa, 2-4 grupy, 5+ grup -
    // and the teens (12-14) fall back to the "many" form.
    function plural(n, one, few, many) {
        var mod10 = n % 10, mod100 = n % 100;
        if (n === 1) return one;
        if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return few;
        return many;
    }

    function groupWord(n) {
        return n + " " + plural(n, "grupa", "grupy", "grup");
    }

    function logoUrl(code) {
        return "assets/images/faculties/" + code + ".png";
    }

    // Inlined so it can inherit the button's colour; an <img> cannot.
    var ICON_APPLE = '<svg viewBox="-1.5 0 20 20" width="18" height="18" aria-hidden="true">' +
        '<path fill="currentColor" transform="translate(-46 -7279)" d="M57.5708873,7282.19296 C58.2999598,7281.34797 58.7914012,7280.17098 58.6569121,7279 C57.6062792,7279.04 56.3352055,7279.67099 55.5818643,7280.51498 C54.905374,7281.26397 54.3148354,7282.46095 54.4735932,7283.60894 C55.6455696,7283.69593 56.8418148,7283.03894 57.5708873,7282.19296 M60.1989864,7289.62485 C60.2283111,7292.65181 62.9696641,7293.65879 63,7293.67179 C62.9777537,7293.74279 62.562152,7295.10677 61.5560117,7296.51675 C60.6853718,7297.73474 59.7823735,7298.94772 58.3596204,7298.97372 C56.9621472,7298.99872 56.5121648,7298.17973 54.9134635,7298.17973 C53.3157735,7298.17973 52.8162425,7298.94772 51.4935978,7298.99872 C50.1203933,7299.04772 49.0738052,7297.68074 48.197098,7296.46676 C46.4032359,7293.98379 45.0330649,7289.44985 46.8734421,7286.3899 C47.7875635,7284.87092 49.4206455,7283.90793 51.1942837,7283.88393 C52.5422083,7283.85893 53.8153044,7284.75292 54.6394294,7284.75292 C55.4635543,7284.75292 57.0106846,7283.67793 58.6366882,7283.83593 C59.3172232,7283.86293 61.2283842,7284.09893 62.4549652,7285.8199 C62.355868,7285.8789 60.1747177,7287.09489 60.1989864,7289.62485"/></svg>';
    var ICON_GOOGLE = '<img src="assets/images/icons/google.svg" alt="" width="18" height="18">';
    var ICON_CALENDAR = '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" aria-hidden="true">' +
        '<path d="M2.8 12c0-3.4 0-5.1 1-6.2C4.9 4.8 6.6 4.8 10 4.8h4c3.4 0 5.1 0 6.2 1C21.2 6.9 21.2 8.6 21.2 12v2c0 3.4 0 5.1-1 6.2-1.1 1-2.8 1-6.2 1h-4c-3.4 0-5.1 0-6.2-1-1-1.1-1-2.8-1-6.2v-2Z" stroke="currentColor" stroke-width="1.6"/>' +
        '<path d="M7 4.8V3M17 4.8V3M2.8 9h18.4" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>';

    var el = {
        search: document.getElementById("search"),
        clear: document.getElementById("clear"),
        faculties: document.getElementById("faculties"),
        status: document.getElementById("status"),
        results: document.getElementById("results"),
        sheet: document.getElementById("sheet"),
        sheetTitle: document.getElementById("sheet-title"),
        sheetLogo: document.getElementById("sheet-logo"),
        primaryIcon: document.getElementById("primary-icon"),
        primaryLabel: document.getElementById("primary-label"),
        sheetFaculty: document.getElementById("sheet-faculty"),
        sheetMeta: document.getElementById("sheet-meta"),
        sheetClose: document.getElementById("sheet-close"),
        sheetSource: document.getElementById("sheet-source"),
        primary: document.getElementById("primary-action"),
        primaryNote: document.getElementById("primary-note"),
        altApple: document.getElementById("alt-apple"),
        altGoogle: document.getElementById("alt-google"),
        altDownload: document.getElementById("alt-download"),
        copyUrl: document.getElementById("copy-url"),
        copyBtn: document.getElementById("copy-btn"),
        footerUpdated: document.getElementById("footer-updated"),
        statusDot: document.getElementById("status-dot"),
        // One above the list and one below it: with 40 rows per page the
        // bottom control is off-screen exactly when you need it.
        pagers: Array.prototype.slice.call(document.querySelectorAll(".pager"))
    };

    var index = null;      // parsed index.json
    var entries = [];      // flattened [{id, code, faculty, events, semester}]
    var activeFaculty = null;
    var shown = [];        // entries on the current page
    var matches = [];      // every entry matching the current query
    var page = 0;
    var cursor = -1;       // keyboard position in the result list
    var lastFocus = null;

    /* ---------- platform ---------- */

    var ua = navigator.userAgent || "";
    var isApple = /iPad|iPhone|iPod|Macintosh/.test(ua) && !window.MSStream;
    var isAndroid = /Android/.test(ua);

    /* ---------- urls ---------- */

    // Directory of this page, e.g. "/WATcalendars/" on a project site.
    function basePath() {
        var path = location.pathname;
        return path.slice(0, path.lastIndexOf("/") + 1);
    }

    function relativeIcs(entry) {
        // encodeURIComponent on the filename only: group names contain
        // parentheses, dots and spaces (WIM, WLO) that would otherwise
        // produce a broken or ambiguous URL.
        return "db/calendars/" + entry.code + "_calendars/" +
               entry.code + "_calendars_" + entry.semester + "/" +
               encodeURIComponent(entry.id + ".ics");
    }

    function httpsUrl(entry) {
        return location.origin + basePath() + relativeIcs(entry);
    }

    function webcalUrl(entry) {
        return "webcal://" + location.host + basePath() + relativeIcs(entry);
    }

    function googleUrl(entry) {
        return "https://calendar.google.com/calendar/r?cid=" +
               encodeURIComponent(webcalUrl(entry));
    }

    /* ---------- data ---------- */

    function flatten(data) {
        var list = [];
        Object.keys(data.faculties).forEach(function (code) {
            var faculty = data.faculties[code];
            // Prefer the current semester; fall back to whatever exists,
            // because faculties publish the two at different times.
            var semester = faculty.semesters[data.current_semester]
                ? data.current_semester
                : Object.keys(faculty.semesters)[0];
            if (!semester) return;

            var template = (faculty.url_template || {})[semester] || "";

            faculty.semesters[semester].forEach(function (pair) {
                list.push({
                    id: pair[0],
                    events: pair[1],
                    // Row carries its own URL only when it deviates from
                    // the faculty template (WIG's Joomla download links).
                    source: pair[2] || (template ? template.replace("{group}", pair[0]) : ""),
                    code: code,
                    faculty: faculty.name,
                    semester: semester,
                    haystack: pair[0].toUpperCase()
                });
            });
        });
        return list;
    }

    /* ---------- search ---------- */

    function normalise(text) {
        // Group codes are ASCII; people type them with or without the
        // separators that appear in WML ("K-8103093") and WLO names.
        return text.toUpperCase().replace(/[\s_.-]/g, "");
    }

    function search(query) {
        var pool = activeFaculty
            ? entries.filter(function (e) { return e.code === activeFaculty; })
            : entries;

        if (!query) return pool;

        var needle = normalise(query);
        var scored = [];
        pool.forEach(function (entry) {
            var hay = normalise(entry.haystack);
            var at = hay.indexOf(needle);
            if (at === -1) return;
            // Prefix matches first, then earliest match, then shortest name.
            scored.push({ entry: entry, rank: (at === 0 ? 0 : 1), at: at });
        });

        scored.sort(function (a, b) {
            return a.rank - b.rank || a.at - b.at ||
                   a.entry.id.length - b.entry.id.length ||
                   a.entry.id.localeCompare(b.entry.id);
        });

        return scored.map(function (s) { return s.entry; });
    }

    /* ---------- rendering ---------- */

    function render(list, query) {
        var start = page * MAX_RESULTS;
        shown = list.slice(start, start + MAX_RESULTS);
        cursor = -1;
        el.results.textContent = "";
        paintPager(list.length, start);

        if (!list.length) {
            el.status.textContent = query
                ? "Brak grupy pasującej do „" + query + "”."
                : "";
            if (query) {
                var li = document.createElement("li");
                li.className = "empty";
                li.textContent = activeFaculty
                    ? "Spróbuj bez filtra wydziału albo sprawdź pisownię kodu."
                    : "Sprawdź pisownię kodu grupy lub przeglądaj po wydziale.";
                el.results.appendChild(li);
            }
            el.search.setAttribute("aria-expanded", "false");
            return;
        }

        el.status.textContent = groupWord(list.length);

        var fragment = document.createDocumentFragment();
        shown.forEach(function (entry, i) {
            var li = document.createElement("li");
            var button = document.createElement("button");
            button.type = "button";
            button.className = "result";
            button.setAttribute("role", "option");
            button.dataset.i = i;
            button.title = entry.id;

            var id = document.createElement("span");
            id.className = "result-id";
            id.textContent = entry.id;

            var tag = document.createElement("img");
            tag.className = "result-logo";
            tag.src = logoUrl(entry.code);
            tag.alt = entry.code.toUpperCase();
            tag.width = 26;
            tag.height = 26;
            tag.loading = "lazy";

            var events = document.createElement("span");
            events.className = "result-events";
            events.textContent = entry.events + " " +
                plural(entry.events, "zajęcie", "zajęcia", "zajęć");

            button.appendChild(tag);
            button.appendChild(id);
            button.appendChild(events);
            li.appendChild(button);
            fragment.appendChild(li);
        });

        el.results.appendChild(fragment);
        el.search.setAttribute("aria-expanded", "true");
    }

    function paintPager(total, start) {
        var pages = Math.ceil(total / MAX_RESULTS);
        var label = (start + 1) + "\u2013" +
            Math.min(start + MAX_RESULTS, total) + " z " + total;

        el.pagers.forEach(function (pager) {
            if (pages <= 1) {
                pager.hidden = true;
                return;
            }
            pager.hidden = false;
            pager.querySelector(".pager-label").textContent = label;
            pager.querySelectorAll(".pager-btn").forEach(function (button) {
                var step = Number(button.dataset.step);
                button.disabled = step < 0 ? page === 0 : page >= pages - 1;
            });
        });
    }

    function turnPage(delta) {
        var pages = Math.ceil(matches.length / MAX_RESULTS);
        var next = Math.min(Math.max(page + delta, 0), pages - 1);
        if (next === page) return;
        page = next;
        render(matches, el.search.value.trim());
        // Bring the top of the list into view, not the top of the page.
        el.pagers[0].scrollIntoView({ block: "start", behavior: "smooth" });
    }

    function renderFaculties() {
        var fragment = document.createDocumentFragment();
        Object.keys(index.faculties).forEach(function (code) {
            var faculty = index.faculties[code];
            var count = entries.filter(function (e) { return e.code === code; }).length;
            if (!count) return;

            var tile = document.createElement("button");
            tile.type = "button";
            tile.className = "chip";
            tile.dataset.code = code;
            tile.title = faculty.name + " \u2014 " + groupWord(count);
            tile.setAttribute("aria-pressed", "false");
            tile.innerHTML =
                '<img class="chip-logo" src="' + logoUrl(code) + '" alt="" width="34" height="34" loading="lazy">' +
                '<span class="chip-code">' + code.toUpperCase() + "</span>" +
                '<span class="chip-count">' + count + "</span>";
            fragment.appendChild(tile);
        });
        el.faculties.appendChild(fragment);
    }

    function syncChips() {
        Array.prototype.forEach.call(el.faculties.children, function (chip) {
            chip.setAttribute("aria-pressed", String(chip.dataset.code === activeFaculty));
        });
    }

    /* ---------- subscription sheet ---------- */

    function openSheet(entry) {
        lastFocus = document.activeElement;

        if (entry.source) {
            el.sheetSource.href = entry.source;
            el.sheetSource.hidden = false;
        } else {
            el.sheetSource.hidden = true;
        }

        el.sheetLogo.src = logoUrl(entry.code);
        el.sheetLogo.alt = entry.code.toUpperCase();
        el.sheetFaculty.textContent = entry.faculty;
        el.sheetTitle.textContent = entry.id;
        el.sheetMeta.textContent = entry.events + " zajęć · semestr " +
            (entry.semester === "zima" ? "zimowy" : "letni");

        var webcal = webcalUrl(entry);
        var https = httpsUrl(entry);

        el.altApple.href = webcal;
        el.altGoogle.href = googleUrl(entry);
        el.altDownload.href = relativeIcs(entry);
        el.altDownload.setAttribute("download", entry.id + ".ics");
        el.copyUrl.value = https;

        if (isAndroid) {
            el.primary.href = googleUrl(entry);
            el.primaryLabel.textContent = "Dodaj do Kalendarza Google";
            el.primaryIcon.innerHTML = ICON_GOOGLE;
            el.primary.setAttribute("target", "_blank");
            el.primary.setAttribute("rel", "noopener");
            el.primaryNote.textContent = "Otworzy się Kalendarz Google z prośbą o potwierdzenie.";
        } else {
            el.primary.href = webcal;
            el.primary.removeAttribute("target");
            el.primaryLabel.textContent = isApple
                ? "Dodaj do Kalendarza"
                : "Dodaj do kalendarza";
            el.primaryIcon.innerHTML = isApple ? ICON_APPLE : ICON_CALENDAR;
            el.primaryNote.textContent = isApple
                ? "Otworzy się aplikacja Kalendarz. Plan będzie się aktualizował sam."
                : "Otworzy się Twoja domyślna aplikacja kalendarza.";
        }

        el.sheet.hidden = false;
        document.body.style.overflow = "hidden";
        el.sheetClose.focus();

        var params = new URLSearchParams({ f: entry.code, g: entry.id });
        history.pushState({ id: entry.id, code: entry.code }, "", "?" + params.toString());
    }

    function closeSheet(pop) {
        if (el.sheet.hidden) return;
        el.sheet.hidden = true;
        document.body.style.overflow = "";
        if (lastFocus && lastFocus.focus) lastFocus.focus();
        if (!pop) history.pushState({}, "", basePath());
    }

    function findEntry(code, id) {
        for (var i = 0; i < entries.length; i++) {
            if (entries[i].code === code && entries[i].id === id) return entries[i];
        }
        return null;
    }

    /* ---------- events ---------- */

    function update(keepPage) {
        var query = el.search.value.trim();
        el.clear.hidden = !query;
        matches = search(query);
        if (!keepPage) page = 0;
        render(matches, query);
    }

    el.search.addEventListener("input", update);

    el.clear.addEventListener("click", function () {
        el.search.value = "";
        el.search.focus();
        update();
    });

    el.faculties.addEventListener("click", function (event) {
        var chip = event.target.closest(".chip");
        if (!chip) return;
        activeFaculty = activeFaculty === chip.dataset.code ? null : chip.dataset.code;
        syncChips();
        update();
    });

    el.results.addEventListener("click", function (event) {
        var button = event.target.closest(".result");
        if (button) openSheet(shown[Number(button.dataset.i)]);
    });

    // Arrow keys move through results without leaving the search box.
    el.search.addEventListener("keydown", function (event) {
        if (!shown.length) return;
        if (event.key === "ArrowDown" || event.key === "ArrowUp") {
            event.preventDefault();
            cursor += event.key === "ArrowDown" ? 1 : -1;
            if (cursor < 0) cursor = shown.length - 1;
            if (cursor >= shown.length) cursor = 0;
            Array.prototype.forEach.call(
                el.results.querySelectorAll(".result"),
                function (node, i) { node.classList.toggle("active", i === cursor); }
            );
            var active = el.results.querySelectorAll(".result")[cursor];
            if (active) active.scrollIntoView({ block: "nearest" });
        } else if (event.key === "Enter") {
            event.preventDefault();
            openSheet(shown[cursor >= 0 ? cursor : 0]);
        }
    });

    el.pagers.forEach(function (pager) {
        pager.addEventListener("click", function (event) {
            var button = event.target.closest(".pager-btn");
            if (button) turnPage(Number(button.dataset.step));
        });
    });

    el.sheetClose.addEventListener("click", function () { closeSheet(false); });

    el.sheet.addEventListener("click", function (event) {
        if (event.target === el.sheet) closeSheet(false);
    });

    document.addEventListener("keydown", function (event) {
        if (event.key === "Escape") closeSheet(false);
    });

    el.copyBtn.addEventListener("click", function () {
        var done = function () {
            el.copyBtn.textContent = "Skopiowano";
            setTimeout(function () { el.copyBtn.textContent = "Kopiuj"; }, 1600);
        };
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(el.copyUrl.value).then(done, function () {
                el.copyUrl.select();
            });
        } else {
            el.copyUrl.select();
            try { document.execCommand("copy"); done(); } catch (e) { /* user copies manually */ }
        }
    });

    window.addEventListener("popstate", function () {
        var params = new URLSearchParams(location.search);
        var id = params.get("g");
        var code = params.get("f");
        var entry = id && code ? findEntry(code, id) : null;
        if (entry) { openSheet(entry); } else { closeSheet(true); }
    });

    /* ---------- boot ---------- */

    function fail(message) {
        el.status.textContent = "";
        var box = document.createElement("div");
        box.className = "error-box";
        box.innerHTML = "<p><strong>" + message + "</strong></p>" +
            '<p>Pliki możesz pobrać bezpośrednio z <a href="' + REPO_TREE +
            '">repozytorium na GitHubie</a>.</p>';
        el.results.parentNode.insertBefore(box, el.results);
    }

    var yearNode = document.getElementById("year");
    if (yearNode) yearNode.textContent = new Date().getFullYear();

    // Health of the nightly scrape. The workflow writes this next to the
    // calendars, so reading it costs no GitHub API quota - polling their
    // API would burn the 60 requests/hour that unauthenticated callers
    // share per address. A missing file means "no run recorded yet" and
    // the dot simply stays hidden.
    function showStatus(data) {
        var ok = data.conclusion === "success";
        var dot = el.statusDot;

        dot.className = "dot " + (ok ? "ok" : "failed");
        dot.hidden = false;

        var when = (data.finished || "").replace("T", " ").replace("Z", " UTC");
        dot.title = (ok
            ? "Ostatnie pobieranie zako\u0144czy\u0142o si\u0119 powodzeniem"
            : "Ostatnie pobieranie nie powiod\u0142o si\u0119") +
            (data.detail ? " \u2014 " + data.detail : "") +
            (when ? "\n" + when : "");

        if (data.run_url) {
            dot.href = data.run_url;
        } else {
            dot.removeAttribute("href");
            dot.removeAttribute("target");
        }
    }

    fetch(STATUS_URL, { cache: "no-cache" })
        .then(function (response) { return response.ok ? response.json() : null; })
        .then(function (data) { if (data) showStatus(data); })
        .catch(function () { /* no run recorded - leave the dot hidden */ });

    el.status.textContent = "Wczytywanie listy grup…";

    fetch(INDEX_URL, { cache: "no-cache" })
        .then(function (response) {
            if (!response.ok) throw new Error("HTTP " + response.status);
            return response.json();
        })
        .then(function (data) {
            index = data;
            entries = flatten(data);
            renderFaculties();

            if (data.generated) {
                el.footerUpdated.textContent =
                    "Ostatnia aktualizacja planów: " + data.generated.slice(0, 10) + ".";
            }

            var params = new URLSearchParams(location.search);
            var entry = params.get("g") && params.get("f")
                ? findEntry(params.get("f"), params.get("g"))
                : null;

            if (entry) {
                el.search.value = entry.id;
                update();
                openSheet(entry);
            } else {
                el.status.textContent = groupWord(entries.length) + " w " +
                    Object.keys(data.faculties).length +
                    " wydziałach. Wpisz kod swojej grupy.";
                if (window.matchMedia("(min-width: 620px)").matches) el.search.focus();
            }
        })
        .catch(function (error) {
            fail("Nie udało się wczytać listy grup (" + error.message + ").");
        });
})();
