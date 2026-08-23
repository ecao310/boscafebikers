// Ride-card rendering and the add-to-calendar exports (.ics download + Google
// Calendar link). Loaded FIRST in the dependency order (defer), so it also owns
// the tiny DOM helper and the constants the later files share. Everything the
// other files use lives on the shared `BCB` namespace (window.BCB) — see the
// "JS module split" note in CLAUDE.md.
(function (BCB) {
  "use strict";

  BCB.PARTIFUL = "https://partiful.com/u/Hs47uq5mucZyXLBJZCda";

  BCB.MONTHS = ["January", "February", "March", "April", "May", "June", "July",
    "August", "September", "October", "November", "December"];

  BCB.DOW = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

  // DOM built with createElement/textContent, never innerHTML, so feed text
  // can't inject markup.
  BCB.el = (tag, cls, text) => {
    const node = document.createElement(tag);
    if (cls) { node.className = cls; }
    if (text) { node.textContent = text; }
    return node;
  };

  BCB.pad2 = (n) => (n < 10 ? "0" + n : String(n));

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
    const out = [];
    while (line.length > 75) {
      let cut = 75;
      const c = line.charCodeAt(cut);
      if (c >= 0xD800 && c <= 0xDBFF) { cut -= 1; }
      out.push(line.slice(0, cut));
      line = " " + line.slice(cut);
    }
    out.push(line);
    return out.join("\r\n");
  }
  function icsDateTime(iso) {
    const m = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2}))?/.exec(iso || "");
    if (!m) { return null; }
    return m[1] + m[2] + m[3] + "T" + m[4] + m[5] + (m[6] || "00");
  }
  function utcStamp() {
    const now = new Date();
    return now.getUTCFullYear() + BCB.pad2(now.getUTCMonth() + 1) + BCB.pad2(now.getUTCDate()) +
      "T" + BCB.pad2(now.getUTCHours()) + BCB.pad2(now.getUTCMinutes()) +
      BCB.pad2(now.getUTCSeconds()) + "Z";
  }
  function icsFilename(title) {
    const safe = String(title || "").toLowerCase()
      .replace(/[^\w\- ]+/g, "")
      .trim().replace(/\s+/g, "-").replace(/-+/g, "-").slice(0, 60);
    return (safe || "cafe-ride") + ".ics";
  }
  function fallbackUid(ev) {
    return "boscafebikers-" + (icsDateTime(ev.start) || "undated") + "-" +
      String(ev.title || "ride").toLowerCase().replace(/[^a-z0-9]+/g, "-");
  }
  BCB.buildIcs = (ev) => {
    const lines = [
      "BEGIN:VCALENDAR",
      "VERSION:2.0",
      "PRODID:-//Boston Café Bikers//boscafebikers//EN",
      "CALSCALE:GREGORIAN",
      "METHOD:PUBLISH",
      "BEGIN:VEVENT",
      "UID:" + icsEscape(ev.uid || fallbackUid(ev)),
      "DTSTAMP:" + utcStamp()
    ];
    const start = icsDateTime(ev.start);
    if (start) { lines.push("DTSTART;TZID=America/New_York:" + start); }
    const end = icsDateTime(ev.end);
    if (end) { lines.push("DTEND;TZID=America/New_York:" + end); }
    lines.push("SUMMARY:" + icsEscape(ev.title || "Café ride"));
    if (ev.location) { lines.push("LOCATION:" + icsEscape(ev.location)); }
    let desc = ev.description || "";
    if (ev.rsvp_url) { desc = desc ? desc + "\n\n" : ""; desc += "RSVP: " + ev.rsvp_url; }
    if (desc) { lines.push("DESCRIPTION:" + icsEscape(desc)); }
    if (ev.rsvp_url) { lines.push("URL:" + ev.rsvp_url); }
    lines.push("END:VEVENT", "END:VCALENDAR");
    return lines.map(foldIcsLine).join("\r\n") + "\r\n";
  };
  BCB.downloadIcs = (ev) => {
    const blob = new Blob([BCB.buildIcs(ev)], { type: "text/calendar;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = icsFilename(ev.title);
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(() => { URL.revokeObjectURL(url); }, 0);
  };

  // "Add to Google Calendar" link — mirrors the calendar export BCU offers on
  // its event detail pages, but as a static-site-friendly TEMPLATE URL. Like
  // buildIcs, it reuses the precomputed Eastern wall-clock fields (never new
  // Date(start) — see the calendar note), and ctz makes Google interpret the
  // naive times in America/New_York. end is null when the feed omits DTEND, so
  // default the block to an hour.
  function icsDateTimePlusHour(iso) {
    const dt = icsDateTime(iso);
    if (!dt) { return null; }
    // dt is YYYYMMDDTHHMMSS (Eastern wall-clock). Add an hour with Date.UTC
    // arithmetic so a near-midnight ride rolls into the next day correctly;
    // the result is still treated as a naive Eastern time by Google's ctz.
    const y = +dt.slice(0, 4), mo = +dt.slice(4, 6), d = +dt.slice(6, 8);
    const h = +dt.slice(9, 11), mi = +dt.slice(11, 13), s = dt.slice(13, 15);
    const date = new Date(Date.UTC(y, mo - 1, d, h + 1, mi));
    return date.getUTCFullYear() + BCB.pad2(date.getUTCMonth() + 1) + BCB.pad2(date.getUTCDate()) +
      "T" + BCB.pad2(date.getUTCHours()) + BCB.pad2(date.getUTCMinutes()) + s;
  }
  BCB.googleCalUrl = (ev) => {
    const parts = [];
    const add = (key, value) => {
      if (value) { parts.push(key + "=" + encodeURIComponent(value)); }
    };
    add("action", "TEMPLATE");
    add("text", ev.title || "Café ride");
    const start = icsDateTime(ev.start);
    const end = ev.end ? icsDateTime(ev.end) : icsDateTimePlusHour(ev.start);
    add("dates", start && end ? start + "/" + end : start);
    add("location", ev.location);
    let desc = ev.description || "";
    if (ev.rsvp_url) { desc = desc ? desc + "\n\n" : ""; desc += "RSVP: " + ev.rsvp_url; }
    add("details", desc);
    add("ctz", "America/New_York");
    return "https://calendar.google.com/calendar/render?" + parts.join("&");
  };

  // "O'Some Café, 100 Main St, Watertown, MA 02472" → "O'Some Café". Google's
  // saddr/daddr are full addresses; only the leading place name fits a card.
  function placeName(address) {
    return String(address || "").split(",")[0].trim();
  }

  // The shared ride-card builder — used by the featured next-ride card AND the
  // ride-detail modal, so the details and add-to-calendar exports can't drift.
  BCB.rideCard = (ev, extraClass) => {
    const card = BCB.el("div", "ride" + (ev.past ? " is-past" : "") + (extraClass ? " " + extraClass : ""));
    if (ev.image) {
      // Photo banner, linked to the same RSVP target as the button below.
      const imgLink = BCB.el("a", "ride-img-link");
      imgLink.href = ev.rsvp_url || BCB.PARTIFUL;
      imgLink.rel = "noopener";
      const img = BCB.el("img", "ride-img");
      img.src = ev.image;
      img.alt = ev.title || "Café ride";
      img.loading = "lazy";
      imgLink.appendChild(img);
      card.appendChild(imgLink);
    }
    const when = [ev.date_display, ev.time_display].filter(Boolean).join(" · ");
    if (when || ev.past) {
      const whenLine = BCB.el("p", "when", when);
      // A ride pulled off the archive needs to say so: the date alone doesn't
      // read as "already happened" when you land on it from the calendar.
      if (ev.past) { whenLine.appendChild(BCB.el("span", "ride-tag", "Past ride")); }
      card.appendChild(whenLine);
    }
    card.appendChild(BCB.el("h3", null, ev.title || "Café ride"));
    if (ev.location) {
      card.appendChild(BCB.el("p", "where", ev.location));
    } else if (ev.location_hidden) {
      // Partiful hides the address until RSVP; show a friendly note instead
      // of the feed's "Location available once RSVP'd" template text.
      card.appendChild(BCB.el("p", "where", "Location shared after you RSVP"));
    }
    // Route links come from the host's Partiful custom fields ("Estimated
    // Route", "Team A & C Route", …) and open Google Maps. The endpoints are
    // full postal addresses, so show just the place name — the whole thing is
    // one tap away in Maps, and in the link's title.
    (ev.routes || []).forEach((route) => {
      const line = BCB.el("p", "route");
      const link = BCB.el("a", null, route.label || "Route");
      link.href = route.url;
      link.target = "_blank";
      link.rel = "noopener";
      link.title = placeName(route.start) && placeName(route.end)
        ? route.start + " → " + route.end
        : "Open this route in Google Maps";
      line.appendChild(link);
      // Distance is measured from the route's own stops (see fetch_rides.py),
      // not quoted from Google — the "~" in the string is doing real work.
      if (route.distance_display) {
        line.appendChild(BCB.el("span", "route-distance", route.distance_display));
      }
      const ends = [placeName(route.start), placeName(route.end)].filter(Boolean);
      if (ends.length === 2) {
        const stops = (route.via || []).length;
        line.appendChild(BCB.el("span", "route-ends",
          ends.join(" → ") + (stops ? " · " + stops + (stops === 1 ? " stop" : " stops") + " on the way" : "")));
      }
      card.appendChild(line);
    });
    if (ev.description) { card.appendChild(BCB.el("p", null, ev.description)); }
    const actions = BCB.el("div", "ride-actions");
    const link = BCB.el("a", "btn", ev.past ? "See it on Partiful" : "RSVP on Partiful");
    link.href = ev.rsvp_url || BCB.PARTIFUL;
    link.rel = "noopener";
    actions.appendChild(link);
    if (ev.past) {
      // No RSVP, and nothing to add to a calendar — the ride is over. The
      // Partiful link still works, and that's where the photos are.
      card.appendChild(actions);
      return card;
    }
    const ics = BCB.el("button", "btn btn-ghost", "Add to calendar");
    ics.type = "button";
    ics.setAttribute("aria-label", "Download .ics for " + (ev.title || "this ride"));
    ics.addEventListener("click", () => { BCB.downloadIcs(ev); });
    actions.appendChild(ics);
    const gcal = BCB.el("a", "btn btn-ghost", "Google Calendar");
    gcal.href = BCB.googleCalUrl(ev);
    gcal.target = "_blank";
    gcal.rel = "noopener";
    actions.appendChild(gcal);
    card.appendChild(actions);
    return card;
  };
})(window.BCB = window.BCB || {});
