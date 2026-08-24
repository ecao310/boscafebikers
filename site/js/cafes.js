// "Where we've been" — the café list on cafes.html, rendered from the same
// events-past.json the calendar dims its history with. No new sync work: every
// field here (café address, date_display, rsvp_url) is already in the archive.
//
// Standalone on purpose: this page has no calendar, no modal and no ride
// cards, so it does NOT join the window.BCB namespace the three rides scripts
// share — it is one small file instead of three, and nothing on the rides page
// depends on it.
(function () {
  "use strict";

  // Public profile — the fallback target whenever a ride has no event link,
  // and the CTA on the "couldn't load it" note.
  const PARTIFUL = "https://partiful.com/u/Hs47uq5mucZyXLBJZCda";

  // Month names by number so the "since September 2025" line can be written
  // straight off the ISO start string. Same no-`Date` rule as the rest of the
  // site: `start` carries the Eastern offset, and re-parsing it in the
  // visitor's timezone is how a ride lands on the wrong day.
  const MONTHS = ["January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"];

  // A Location field holding nothing but a link (fetch_rides.py stores it as
  // location_url). Name the link instead of printing the URL — same rule and
  // wording as ride-card.js meetingPointText().
  const MAPS_URL_RE =
    /^https?:\/\/(?:maps\.app\.goo\.gl\/|maps\.google\.[a-z.]+\/|(?:www\.)?goo\.gl\/maps|(?:www\.)?google\.[a-z.]+\/maps)/i;

  const list = document.getElementById("cafe-list");
  const countLine = document.getElementById("cafe-count");
  if (!list) { return; }

  // Everything is built with createElement/textContent, never innerHTML, so
  // café names and ride titles out of the feed can't inject markup.
  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) { node.className = className; }
    if (text !== undefined && text !== null) { node.textContent = text; }
    return node;
  }

  // "Localito Cafe, 30 Riverside Ave, Medford, MA" → the café is the leading
  // comma-segment (placeName() on the rides page), the rest is its address.
  function splitLocation(location) {
    const parts = String(location || "").split(",").map((s) => s.trim()).filter(Boolean);
    return { name: parts[0] || "", address: parts.slice(1).join(", ") };
  }

  function meetingPointText(url) {
    return MAPS_URL_RE.test(String(url || "")) ? "Meeting point on Google Maps" : "Meeting point";
  }

  // date_display has no year and the archive already spans two of them, so the
  // year comes off the ISO prefix: "Sunday, August 16" + "2026".
  function rideDate(ev) {
    const year = String(ev.start || "").slice(0, 4);
    const day = ev.date_display || "";
    if (day && year) { return day + ", " + year; }
    return day || year;
  }

  function cafeItem(ev) {
    const item = el("li", "cafe");
    const place = splitLocation(ev.location);
    const title = ev.title || "Café ride";
    // With no address at all there is no café name to head the card with, so
    // the ride's own name does the job.
    const heading = place.name || title;
    item.appendChild(el("h3", "cafe-name", heading));

    if (place.address) {
      item.appendChild(el("p", "cafe-address", place.address));
    } else if (ev.location_url) {
      // The organizer pasted the meeting point's map link in place of an
      // address: show it as a named link, not a raw URL.
      const line = el("p", "cafe-address");
      const link = el("a", null, meetingPointText(ev.location_url));
      link.href = ev.location_url;
      link.target = "_blank";
      link.rel = "noopener";
      line.appendChild(link);
      item.appendChild(line);
    } else if (!place.name) {
      item.appendChild(el("p", "cafe-address is-unknown", "Location wasn't published"));
    }

    item.appendChild(el("p", "cafe-when", rideDate(ev)));
    // Only when it isn't already the heading — no card says the same thing twice.
    if (title !== heading) { item.appendChild(el("p", "cafe-ride", title)); }

    const go = el("p", "cafe-go");
    const link = el("a", null, "See the ride on Partiful");
    link.href = ev.rsvp_url || PARTIFUL;
    link.rel = "noopener";
    go.appendChild(link);
    item.appendChild(go);
    return item;
  }

  // "34 rides to 19 named cafés and stops, since September 2025." — every
  // number is counted from the archive, nothing is hardcoded.
  function summary(events) {
    const names = new Set();
    events.forEach((ev) => {
      const name = splitLocation(ev.location).name;
      if (name) { names.add(name.toLowerCase()); }
    });
    const rides = events.length + (events.length === 1 ? " ride" : " rides");
    const cafes = names.size === 1
      ? "1 named café or stop"
      : names.size + " named cafés and stops";
    // events is newest-first, so the oldest ride is last.
    const iso = String((events[events.length - 1] || {}).start || "");
    const month = MONTHS[Number(iso.slice(5, 7)) - 1];
    const since = month ? ", since " + month + " " + iso.slice(0, 4) : "";
    return rides + " to " + cafes + since + ".";
  }

  function note(message) {
    list.textContent = "";
    list.appendChild(el("p", "note", message));
    const link = el("a", "btn", "See all rides on Partiful");
    link.href = PARTIFUL;
    link.rel = "noopener";
    list.appendChild(link);
  }

  function render(events) {
    list.textContent = "";
    let year = null;
    let group = null;
    events.forEach((ev) => {
      const evYear = String(ev.start || "").slice(0, 4) || "Earlier";
      if (evYear !== year) {
        year = evYear;
        list.appendChild(el("h2", "year", year));
        group = el("ul", "cafe-list");
        list.appendChild(group);
      }
      group.appendChild(cafeItem(ev));
    });
    if (countLine) {
      countLine.textContent = summary(events);
      countLine.hidden = false;
    }
  }

  async function load() {
    let data;
    try {
      const res = await fetch("events-past.json", { cache: "no-cache" });
      if (!res.ok) { throw new Error("HTTP " + res.status); }
      data = await res.json();
    } catch (err) {
      note("Couldn't load the café list just now. Try again in a moment.");
      return;
    }
    const events = (data && data.events) || [];
    if (!events.length) {
      note("No café stops logged yet — the first rides are still ahead.");
      return;
    }
    // Newest first. The ISO strings sort lexically (they all carry the Eastern
    // offset), which is exactly the no-`Date` rule the rest of the site keeps.
    render(events.slice().sort((a, b) =>
      String(b.start || "").localeCompare(String(a.start || ""))));
  }

  load();
})();
