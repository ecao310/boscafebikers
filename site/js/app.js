(function () {
  var PARTIFUL = "https://partiful.com/u/Hs47uq5mucZyXLBJZCda";
  var MONTHS = ["January", "February", "March", "April", "May", "June", "July",
    "August", "September", "October", "November", "December"];
  var DOW = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
  var schedule = document.getElementById("schedule");
  var updated = document.getElementById("updated");
  var updatedLink = document.getElementById("updated-link");
  var nextRideCard = document.getElementById("next-ride-card");

  var currentData = null;
  var currentCalendar = null;

  function el(tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) { node.className = cls; }
    if (text) { node.textContent = text; }
    return node;
  }

  function emptyState(message) {
    schedule.textContent = "";
    schedule.appendChild(el("p", "note", message));
    var link = el("a", "btn", "See all rides on Partiful");
    link.href = PARTIFUL;
    link.rel = "noopener";
    schedule.appendChild(link);
  }

  // events.json timestamps already carry an Eastern offset and the display
  // strings are precomputed in Python — never re-format with Date(), or
  // visitors outside Eastern see the wrong time.
  function stamp(iso) {
    var m = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/.exec(iso || "");
    if (!m) { return ""; }
    var hour = parseInt(m[4], 10);
    var suffix = hour < 12 ? "am" : "pm";
    var hour12 = hour % 12 === 0 ? 12 : hour % 12;
    return "Last updated " + MONTHS[parseInt(m[2], 10) - 1] + " " +
      parseInt(m[3], 10) + ", " + m[1] + " at " + hour12 + ":" + m[5] +
      " " + suffix + " ET.";
  }

  function rideCard(ev, extraClass) {
    var card = el("div", "ride" + (extraClass ? " " + extraClass : ""));
    if (ev.image) {
      // Photo banner, linked to the same RSVP target as the button below.
      var imgLink = el("a", "ride-img-link");
      imgLink.href = ev.rsvp_url || PARTIFUL;
      imgLink.rel = "noopener";
      var img = el("img", "ride-img");
      img.src = ev.image;
      img.alt = ev.title || "Café ride";
      img.loading = "lazy";
      imgLink.appendChild(img);
      card.appendChild(imgLink);
    }
    var when = [ev.date_display, ev.time_display].filter(Boolean).join(" · ");
    if (when) { card.appendChild(el("p", "when", when)); }
    card.appendChild(el("h3", null, ev.title || "Café ride"));
    if (ev.location) {
      card.appendChild(el("p", "where", ev.location));
    } else if (ev.location_hidden) {
      // Partiful hides the address until RSVP; show a friendly note instead
      // of the feed's "Location available once RSVP'd" template text.
      card.appendChild(el("p", "where", "Location shared after you RSVP"));
    }
    if (ev.description) { card.appendChild(el("p", null, ev.description)); }
    var actions = el("div", "ride-actions");
    var link = el("a", "btn", "RSVP on Partiful");
    link.href = ev.rsvp_url || PARTIFUL;
    link.rel = "noopener";
    actions.appendChild(link);
    var ics = el("button", "btn btn-ghost", "Add to calendar");
    ics.type = "button";
    ics.setAttribute("aria-label", "Download .ics for " + (ev.title || "this ride"));
    ics.addEventListener("click", function () { downloadIcs(ev); });
    actions.appendChild(ics);
    var gcal = el("a", "btn btn-ghost", "Google Calendar");
    gcal.href = googleCalUrl(ev);
    gcal.target = "_blank";
    gcal.rel = "noopener";
    actions.appendChild(gcal);
    card.appendChild(actions);
    return card;
  }

  // --- per-event .ics download ---
  // Generated in the browser from the precomputed events.json data. The start
  // ISO string already carries the Eastern offset, so its Y-M-DTHH:MM prefix IS
  // the Eastern wall-clock time — never new Date(start), mirroring the calendar.
  function icsEscape(text) {
    return String(text == null ? "" : text)
      .replace(/\\/g, "\\\\")
      .replace(/;/g, "\\;")
      .replace(/,/g, "\\,")
      .replace(/\r?\n/g, "\\n");
  }
  function foldIcsLine(line) {
    // RFC 5545: fold at 75 chars, continuation lines lead with a space. Avoid
    // splitting a surrogate pair (emoji in a café name, say).
    var out = [];
    while (line.length > 75) {
      var cut = 75;
      var c = line.charCodeAt(cut);
      if (c >= 0xD800 && c <= 0xDBFF) { cut -= 1; }
      out.push(line.slice(0, cut));
      line = " " + line.slice(cut);
    }
    out.push(line);
    return out.join("\r\n");
  }
  function pad2(n) { return n < 10 ? "0" + n : String(n); }
  function icsDateTime(iso) {
    var m = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2}))?/.exec(iso || "");
    if (!m) { return null; }
    return m[1] + m[2] + m[3] + "T" + m[4] + m[5] + (m[6] || "00");
  }
  function utcStamp() {
    var now = new Date();
    return now.getUTCFullYear() + pad2(now.getUTCMonth() + 1) + pad2(now.getUTCDate()) +
      "T" + pad2(now.getUTCHours()) + pad2(now.getUTCMinutes()) +
      pad2(now.getUTCSeconds()) + "Z";
  }
  function icsFilename(title) {
    var safe = String(title || "").toLowerCase()
      .replace(/[^\w\- ]+/g, "")
      .trim().replace(/\s+/g, "-").replace(/-+/g, "-").slice(0, 60);
    return (safe || "cafe-ride") + ".ics";
  }
  function fallbackUid(ev) {
    return "boscafebikers-" + (icsDateTime(ev.start) || "undated") + "-" +
      String(ev.title || "ride").toLowerCase().replace(/[^a-z0-9]+/g, "-");
  }
  function buildIcs(ev) {
    var lines = [
      "BEGIN:VCALENDAR",
      "VERSION:2.0",
      "PRODID:-//Boston Café Bikers//boscafebikers//EN",
      "CALSCALE:GREGORIAN",
      "METHOD:PUBLISH",
      "BEGIN:VEVENT",
      "UID:" + icsEscape(ev.uid || fallbackUid(ev)),
      "DTSTAMP:" + utcStamp()
    ];
    var start = icsDateTime(ev.start);
    if (start) { lines.push("DTSTART;TZID=America/New_York:" + start); }
    var end = icsDateTime(ev.end);
    if (end) { lines.push("DTEND;TZID=America/New_York:" + end); }
    lines.push("SUMMARY:" + icsEscape(ev.title || "Café ride"));
    if (ev.location) { lines.push("LOCATION:" + icsEscape(ev.location)); }
    var desc = ev.description || "";
    if (ev.rsvp_url) { desc = desc ? desc + "\n\n" : ""; desc += "RSVP: " + ev.rsvp_url; }
    if (desc) { lines.push("DESCRIPTION:" + icsEscape(desc)); }
    if (ev.rsvp_url) { lines.push("URL:" + ev.rsvp_url); }
    lines.push("END:VEVENT", "END:VCALENDAR");
    return lines.map(foldIcsLine).join("\r\n") + "\r\n";
  }
  function downloadIcs(ev) {
    var blob = new Blob([buildIcs(ev)], { type: "text/calendar;charset=utf-8" });
    var url = URL.createObjectURL(blob);
    var a = document.createElement("a");
    a.href = url;
    a.download = icsFilename(ev.title);
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(function () { URL.revokeObjectURL(url); }, 0);
  }

  // "Add to Google Calendar" link — mirrors the calendar export BCU offers on
  // its event detail pages, but as a static-site-friendly TEMPLATE URL. Like
  // buildIcs, it reuses the precomputed Eastern wall-clock fields (never new
  // Date(start) — see the calendar note), and ctz makes Google interpret the
  // naive times in America/New_York. end is null when the feed omits DTEND, so
  // default the block to an hour.
  function icsDateTimePlusHour(iso) {
    var dt = icsDateTime(iso);
    if (!dt) { return null; }
    // dt is YYYYMMDDTHHMMSS (Eastern wall-clock). Add an hour with Date.UTC
    // arithmetic so a near-midnight ride rolls into the next day correctly;
    // the result is still treated as a naive Eastern time by Google's ctz.
    var y = +dt.slice(0, 4), mo = +dt.slice(4, 6), d = +dt.slice(6, 8);
    var h = +dt.slice(9, 11), mi = +dt.slice(11, 13), s = dt.slice(13, 15);
    var date = new Date(Date.UTC(y, mo - 1, d, h + 1, mi));
    return date.getUTCFullYear() + pad2(date.getUTCMonth() + 1) + pad2(date.getUTCDate()) +
      "T" + pad2(date.getUTCHours()) + pad2(date.getUTCMinutes()) + s;
  }
  function googleCalUrl(ev) {
    var parts = [];
    function add(key, value) {
      if (value) { parts.push(key + "=" + encodeURIComponent(value)); }
    }
    add("action", "TEMPLATE");
    add("text", ev.title || "Café ride");
    var start = icsDateTime(ev.start);
    var end = ev.end ? icsDateTime(ev.end) : icsDateTimePlusHour(ev.start);
    add("dates", start && end ? start + "/" + end : start);
    add("location", ev.location);
    var desc = ev.description || "";
    if (ev.rsvp_url) { desc = desc ? desc + "\n\n" : ""; desc += "RSVP: " + ev.rsvp_url; }
    add("details", desc);
    add("ctz", "America/New_York");
    return "https://calendar.google.com/calendar/render?" + parts.join("&");
  }

  // --- ride detail modal ---
  // Clicking a calendar event (FullCalendar or the fallback grid) opens this
  // instead of navigating straight to the RSVP page — the BCU detail-page
  // pattern adapted for a static site. The content reuses the rideCard
  // builder, so details and the add-to-calendar exports match the featured
  // next-ride card exactly.
  var rideModal = document.getElementById("ride-modal");
  var rideModalContent = document.getElementById("ride-modal-content");
  var rideModalDialog = rideModal ? rideModal.querySelector(".modal-dialog") : null;
  var lastFocused = null;

  function openRideModal(ev) {
    lastFocused = document.activeElement;
    rideModalContent.textContent = "";
    rideModalContent.appendChild(rideCard(ev, "modal-ride"));
    if (rideModalDialog) {
      rideModalDialog.setAttribute("aria-label", ev.title || "Ride details");
    }
    rideModal.hidden = false;
    document.body.style.overflow = "hidden";
    var close = rideModal.querySelector(".modal-close");
    if (close) { close.focus(); }
  }

  function closeRideModal() {
    if (!rideModal || rideModal.hidden) { return; }
    rideModal.hidden = true;
    document.body.style.overflow = "";
    if (lastFocused && lastFocused.focus) { lastFocused.focus(); }
    lastFocused = null;
  }

  if (rideModal) {
    var modalCloseBtn = rideModal.querySelector(".modal-close");
    if (modalCloseBtn) { modalCloseBtn.addEventListener("click", closeRideModal); }
    // Clicking the backdrop (or anywhere outside the dialog) closes it.
    rideModal.addEventListener("click", function (e) {
      if (!e.target.closest(".modal-dialog")) { closeRideModal(); }
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && !rideModal.hidden) { closeRideModal(); }
    });
  }

  // --- calendar view ---
  // The start ISO string carries the Eastern offset, so its Y-M-D prefix IS
  // the Eastern wall-clock date. Building a Date whose UTC components equal
  // that date makes getUTC*() report the weekday / month length the ride
  // falls on in America/New_York, independent of the visitor's timezone.
  function easternParts(startIso) {
    var m = /^(\d{4})-(\d{2})-(\d{2})/.exec(startIso || "");
    if (!m) { return null; }
    return { y: parseInt(m[1], 10), m: parseInt(m[2], 10), d: parseInt(m[3], 10) };
  }
  function easternWeekday(y, m, d) {
    return new Date(Date.UTC(y, m - 1, d)).getUTCDay();
  }
  function daysInMonth(y, m) {
    return new Date(Date.UTC(y, m, 0)).getUTCDate();
  }

  function groupByMonth(events) {
    // events.json is already sorted by start, so both the month order and the
    // order of events inside each month come out chronological for free.
    var months = {};
    var order = [];
    events.forEach(function (ev) {
      var p = easternParts(ev.start);
      if (!p) { return; }
      var key = p.y + "-" + p.m;
      if (!months[key]) {
        months[key] = { y: p.y, m: p.m, events: [] };
        order.push(key);
      }
      months[key].events.push(ev);
    });
    return order.map(function (key) { return months[key]; });
  }

  function monthGrid(month) {
    var firstDow = easternWeekday(month.y, month.m, 1);
    var days = daysInMonth(month.y, month.m);
    var byDay = {};
    month.events.forEach(function (ev) {
      var p = easternParts(ev.start);
      if (!p) { return; }
      (byDay[p.d] = byDay[p.d] || []).push(ev);
    });

    var grid = el("div", "cal-grid");
    DOW.forEach(function (name) { grid.appendChild(el("div", "cal-dow", name)); });
    var cellCount = Math.ceil((firstDow + days) / 7) * 7;
    for (var i = 0; i < cellCount; i++) {
      var dayNum = i - firstDow + 1;
      if (dayNum < 1 || dayNum > days) {
        grid.appendChild(el("div", "cal-day empty"));
        continue;
      }
      var cell = el("div", "cal-day");
      cell.appendChild(el("span", "num", String(dayNum)));
      if (byDay[dayNum]) {
        cell.classList.add("has-ride");
        byDay[dayNum].forEach(function (ev) {
          // A button (not a link) so clicking shows the detail modal; the
          // modal carries the RSVP / add-to-calendar actions.
          var chip = el("button", "ride-chip", ev.title);
          chip.type = "button";
          chip.setAttribute("aria-label", "View details for " + (ev.title || "this ride"));
          chip.addEventListener("click", function () { openRideModal(ev); });
          cell.appendChild(chip);
        });
      }
      grid.appendChild(cell);
    }

    var wrap = el("div", "calendar");
    wrap.appendChild(el("h3", null, MONTHS[month.m - 1] + " " + month.y));
    wrap.appendChild(grid);
    return wrap;
  }

  function destroyCalendar() {
    if (currentCalendar) {
      currentCalendar.destroy();
      currentCalendar = null;
    }
  }

  // Adopted open-source calendar view: FullCalendar 6 (dayGridMonth) loaded
  // from a CDN with `defer`. It themes itself from the --fc-* custom props
  // overridden in <head>. If the CDN script hasn't run yet (or is blocked),
  // render() falls back to the hand-rolled month grid above.
  function renderCalendarFull(events) {
    var box = el("div", "calendar");
    var holder = document.createElement("div");
    holder.id = "ride-calendar";
    box.appendChild(holder);
    schedule.appendChild(box);

    var first = events[0];
    var initial = first && easternParts(first.start);
    var fcEvents = events.map(function (ev) {
      // extendedProps carries the full event so eventClick can open the modal.
      var out = { title: ev.title || "Café ride", start: ev.start, url: ev.rsvp_url || PARTIFUL, extendedProps: { data: ev } };
      if (ev.end) { out.end = ev.end; }
      return out;
    });

    currentCalendar = new FullCalendar.Calendar(holder, {
      initialView: "dayGridMonth",
      timeZone: "America/New_York",
      initialDate: initial ? initial.y + "-" + pad2(initial.m) + "-" + pad2(initial.d) : undefined,
      headerToolbar: { left: "prev,next", center: "title", right: "" },
      height: "auto",
      dayMaxEvents: 3,
      eventDisplay: "block",
      events: fcEvents,
      // Left-click shows the ride detail modal instead of jumping straight to
      // the RSVP page. Keep the event's url so middle-click / ctrl-click still
      // opens the RSVP target in a new tab (native anchor behavior).
      eventClick: function (info) {
        info.jsEvent.preventDefault();
        openRideModal(info.event.extendedProps.data);
      }
    });
    currentCalendar.render();
  }

  // The next-ride section always shows events[0] (events.json is sorted by
  // start, and the sync filters to future rides), or an empty-state with a
  // Partiful fallback link when the calendar has nothing upcoming.
  function setNextRide(events) {
    nextRideCard.textContent = "";
    if (!events.length) {
      nextRideCard.appendChild(el("p", "note", "No rides scheduled yet — check Partiful for the next one."));
      var link = el("a", "btn", "See all rides on Partiful");
      link.href = PARTIFUL;
      link.rel = "noopener";
      nextRideCard.appendChild(link);
      return;
    }
    nextRideCard.appendChild(rideCard(events[0], "next-ride"));
  }

  // The schedule section is calendar-only now: FullCalendar 6 when its CDN
  // script has loaded, otherwise the hand-rolled month grid. The list view
  // was removed in favor of the featured next-ride card above.
  function render() {
    destroyCalendar();
    var events = (currentData && currentData.events) || [];
    schedule.textContent = "";
    if (!events.length) {
      emptyState("No rides on the calendar right now — check Partiful for the next one.");
    } else if (typeof FullCalendar !== "undefined") {
      renderCalendarFull(events);
    } else {
      groupByMonth(events).forEach(function (month) {
        schedule.appendChild(monthGrid(month));
      });
    }
    setNextRide(events);
    // The "Last updated …" stamp is the link to the sync workflow. Hide the
    // whole line (not just the text) when there's no updated_at, so there's
    // no empty focusable link.
    var text = stamp(currentData && currentData.updated_at);
    if (updatedLink) { updatedLink.textContent = text; }
    if (updated) { updated.hidden = !text; }
  }

  // The deferred FullCalendar script usually finishes before the events fetch
  // resolves, so the first render already uses it. This hook covers the edge
  // case where the CDN script lands after an earlier fallback render.
  if (typeof FullCalendar === "undefined") {
    var fcScript = document.querySelector('script[src*="fullcalendar"]');
    if (fcScript && fcScript.addEventListener) {
      fcScript.addEventListener("load", function () {
        if (currentData) { render(); }
      });
    }
  }

  function loadData(url) {
    return fetch(url, { cache: "no-cache" })
      .then(function (res) {
        if (!res.ok) { throw new Error("HTTP " + res.status); }
        return res.json();
      });
  }

  loadData("events.json")
    .then(function (data) {
      currentData = data;
      render();
    })
    .catch(function () {
      setNextRide([]);
      emptyState("Couldn't load the ride schedule just now.");
    });
})();
