// Calendar view: FullCalendar 6 (dayGridMonth) when its CDN script has loaded,
// otherwise a hand-rolled month grid. Owns the current FullCalendar instance
// and the Eastern wall-clock date math. app.js calls renderCalendarFull /
// destroyCalendar / groupByMonth / monthGrid and appends the returned elements
// into #schedule itself. Renders a .calendar box; the ride-detail modal it
// opens is app.js's (BCB.openRideModal).
(function (BCB) {
  "use strict";

  let currentCalendar = null;

  // The start ISO string carries the Eastern offset, so its Y-M-D prefix IS
  // the Eastern wall-clock date. Building a Date whose UTC components equal
  // that date makes getUTC*() report the weekday / month length the ride
  // falls on in America/New_York, independent of the visitor's timezone.
  function easternParts(startIso) {
    const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(startIso || "");
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
    const months = {};
    const order = [];
    events.forEach((ev) => {
      const p = easternParts(ev.start);
      if (!p) { return; }
      const key = p.y + "-" + p.m;
      if (!months[key]) {
        months[key] = { y: p.y, m: p.m, events: [] };
        order.push(key);
      }
      months[key].events.push(ev);
    });
    return order.map((key) => months[key]);
  }

  function monthGrid(month) {
    const firstDow = easternWeekday(month.y, month.m, 1);
    const days = daysInMonth(month.y, month.m);
    const byDay = {};
    month.events.forEach((ev) => {
      const p = easternParts(ev.start);
      if (!p) { return; }
      (byDay[p.d] = byDay[p.d] || []).push(ev);
    });

    const grid = BCB.el("div", "cal-grid");
    BCB.DOW.forEach((name) => { grid.appendChild(BCB.el("div", "cal-dow", name)); });
    const cellCount = Math.ceil((firstDow + days) / 7) * 7;
    for (let i = 0; i < cellCount; i++) {
      const dayNum = i - firstDow + 1;
      if (dayNum < 1 || dayNum > days) {
        grid.appendChild(BCB.el("div", "cal-day empty"));
        continue;
      }
      const cell = BCB.el("div", "cal-day");
      cell.appendChild(BCB.el("span", "num", String(dayNum)));
      if (byDay[dayNum]) {
        cell.classList.add("has-ride");
        byDay[dayNum].forEach((ev) => {
          // A button (not a link) so clicking shows the detail modal; the
          // modal carries the RSVP / add-to-calendar actions.
          const chip = BCB.el("button", "ride-chip", ev.title);
          chip.type = "button";
          chip.setAttribute("aria-label", "View details for " + (ev.title || "this ride"));
          chip.addEventListener("click", () => { BCB.openRideModal(ev); });
          cell.appendChild(chip);
        });
      }
      grid.appendChild(cell);
    }

    const wrap = BCB.el("div", "calendar");
    wrap.appendChild(BCB.el("h3", null, BCB.MONTHS[month.m - 1] + " " + month.y));
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
  // app.js falls back to the hand-rolled month grid above. Returns the box
  // element; app.js appends it into #schedule.
  function renderCalendarFull(events) {
    const box = BCB.el("div", "calendar");
    const holder = document.createElement("div");
    holder.id = "ride-calendar";
    box.appendChild(holder);

    const first = events[0];
    const initial = first && easternParts(first.start);
    const fcEvents = events.map((ev) => {
      // extendedProps carries the full event so eventClick can open the modal.
      const out = { title: ev.title || "Café ride", start: ev.start, url: ev.rsvp_url || BCB.PARTIFUL, extendedProps: { data: ev } };
      if (ev.end) { out.end = ev.end; }
      return out;
    });

    currentCalendar = new FullCalendar.Calendar(holder, {
      initialView: "dayGridMonth",
      timeZone: "America/New_York",
      initialDate: initial ? initial.y + "-" + BCB.pad2(initial.m) + "-" + BCB.pad2(initial.d) : undefined,
      headerToolbar: { left: "prev,next", center: "title", right: "" },
      height: "auto",
      dayMaxEvents: 3,
      eventDisplay: "block",
      events: fcEvents,
      // Left-click shows the ride detail modal instead of jumping straight to
      // the RSVP page. Keep the event's url so middle-click / ctrl-click still
      // opens the RSVP target in a new tab (native anchor behavior).
      eventClick: (info) => {
        info.jsEvent.preventDefault();
        BCB.openRideModal(info.event.extendedProps.data);
      }
    });
    currentCalendar.render();
    return box;
  }

  BCB.groupByMonth = groupByMonth;
  BCB.monthGrid = monthGrid;
  BCB.destroyCalendar = destroyCalendar;
  BCB.renderCalendarFull = renderCalendarFull;
})(window.BCB = window.BCB || {});
