// App bootstrap: fetch events.json, render the featured next-ride card + the
// calendar, the ride-detail modal, and the "Last updated …" stamp. Loads LAST
// in the dependency order (defer) and reads the shared helpers off the `BCB`
// namespace (window.BCB) that ride-card.js / calendar.js populate — see the
// "JS module split" note in CLAUDE.md.
(function (BCB) {
  "use strict";

  const { el, rideCard, PARTIFUL, MONTHS } = BCB;
  const { renderCalendarFull, destroyCalendar, groupByMonth, monthGrid } = BCB;

  const schedule = document.getElementById("schedule");
  const updated = document.getElementById("updated");
  const updatedLink = document.getElementById("updated-link");
  const nextRideCard = document.getElementById("next-ride-card");

  let currentData = null;
  let lastFocused = null;

  function emptyState(message) {
    schedule.textContent = "";
    schedule.appendChild(el("p", "note", message));
    const link = el("a", "btn", "See all rides on Partiful");
    link.href = PARTIFUL;
    link.rel = "noopener";
    schedule.appendChild(link);
  }

  // events.json timestamps already carry an Eastern offset and the display
  // strings are precomputed in Python — never re-format with Date(), or
  // visitors outside Eastern see the wrong time.
  function stamp(iso) {
    const m = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/.exec(iso || "");
    if (!m) { return ""; }
    const hour = parseInt(m[4], 10);
    const suffix = hour < 12 ? "am" : "pm";
    const hour12 = hour % 12 === 0 ? 12 : hour % 12;
    return "Last updated " + MONTHS[parseInt(m[2], 10) - 1] + " " +
      parseInt(m[3], 10) + ", " + m[1] + " at " + hour12 + ":" + m[5] +
      " " + suffix + " ET.";
  }

  // --- ride detail modal ---
  // Clicking a calendar event (FullCalendar or the fallback grid) opens this
  // instead of navigating straight to the RSVP page — the BCU detail-page
  // pattern adapted for a static site. The content reuses the rideCard
  // builder, so details and the add-to-calendar exports match the featured
  // next-ride card exactly. Exposed on BCB so calendar.js can open it.
  const rideModal = document.getElementById("ride-modal");
  const rideModalContent = document.getElementById("ride-modal-content");
  const rideModalDialog = rideModal ? rideModal.querySelector(".modal-dialog") : null;

  function openRideModal(ev) {
    lastFocused = document.activeElement;
    rideModalContent.textContent = "";
    rideModalContent.appendChild(rideCard(ev, "modal-ride"));
    if (rideModalDialog) {
      rideModalDialog.setAttribute("aria-label", ev.title || "Ride details");
    }
    rideModal.hidden = false;
    document.body.style.overflow = "hidden";
    const close = rideModal.querySelector(".modal-close");
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
    const modalCloseBtn = rideModal.querySelector(".modal-close");
    if (modalCloseBtn) { modalCloseBtn.addEventListener("click", closeRideModal); }
    // Clicking the backdrop (or anywhere outside the dialog) closes it.
    rideModal.addEventListener("click", (e) => {
      if (!e.target.closest(".modal-dialog")) { closeRideModal(); }
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && !rideModal.hidden) { closeRideModal(); }
    });
  }
  BCB.openRideModal = openRideModal;

  // The next-ride section always shows events[0] (events.json is sorted by
  // start, and the sync filters to future rides), or an empty-state with a
  // Partiful fallback link when the calendar has nothing upcoming.
  function setNextRide(events) {
    nextRideCard.textContent = "";
    if (!events.length) {
      nextRideCard.appendChild(el("p", "note", "No rides scheduled yet — check Partiful for the next one."));
      const link = el("a", "btn", "See all rides on Partiful");
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
    const events = (currentData && currentData.events) || [];
    schedule.textContent = "";
    if (!events.length) {
      emptyState("No rides on the calendar right now — check Partiful for the next one.");
    } else if (typeof FullCalendar !== "undefined") {
      schedule.appendChild(renderCalendarFull(events));
    } else {
      groupByMonth(events).forEach((month) => {
        schedule.appendChild(monthGrid(month));
      });
    }
    setNextRide(events);
    // The "Last updated …" stamp is the link to the sync workflow. Hide the
    // whole line (not just the text) when there's no updated_at, so there's
    // no empty focusable link.
    const text = stamp(currentData && currentData.updated_at);
    if (updatedLink) { updatedLink.textContent = text; }
    if (updated) { updated.hidden = !text; }
  }

  // The deferred FullCalendar script usually finishes before the events fetch
  // resolves, so the first render already uses it. This hook covers the edge
  // case where the CDN script lands after an earlier fallback render.
  if (typeof FullCalendar === "undefined") {
    const fcScript = document.querySelector('script[src*="fullcalendar"]');
    if (fcScript && fcScript.addEventListener) {
      fcScript.addEventListener("load", () => {
        if (currentData) { render(); }
      });
    }
  }

  async function loadData(url) {
    const res = await fetch(url, { cache: "no-cache" });
    if (!res.ok) { throw new Error("HTTP " + res.status); }
    return res.json();
  }

  loadData("events.json")
    .then((data) => {
      currentData = data;
      render();
    })
    .catch(() => {
      setNextRide([]);
      emptyState("Couldn't load the ride schedule just now.");
    });
})(window.BCB = window.BCB || {});
