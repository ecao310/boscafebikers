// Contact form → the visitor's own mail app.
//
// GitHub Pages is static: there is no server to POST a form to and no place to
// keep an API key, so "send an email from the page" means composing a mailto:
// URL and handing it to whatever mail client the visitor already uses. The
// form's own action="mailto:…" is the single source for the address — change
// it there (in contact.html) and every use on the page follows, including the
// fallback link below. Without JS the browser still submits the form to that
// same mailto: action, which is why the address lives in the markup.
(function () {
  "use strict";

  const form = document.getElementById("contact-form");
  if (!form) { return; }

  const status = document.getElementById("contact-status");
  const direct = document.getElementById("contact-direct");
  const directLine = document.getElementById("contact-direct-line");

  // "mailto:someone@example.com" → "someone@example.com".
  function formAddress() {
    const action = form.getAttribute("action") || "";
    return action.replace(/^mailto:/i, "").split("?")[0].trim();
  }

  const address = formAddress();

  // Fill the "or email us directly" link from the same address, and only then
  // reveal the line — with JS off it stays hidden rather than showing an empty
  // link (same pattern as the "Last updated" stamp on the rides page).
  if (address && direct && directLine) {
    direct.href = "mailto:" + address;
    direct.textContent = address;
    directLine.hidden = false;
  }

  function value(name) {
    const field = form.elements[name];
    return field && field.value ? field.value.trim() : "";
  }

  function say(message) {
    if (status) {
      status.textContent = message;
      status.hidden = !message;
    }
  }

  form.addEventListener("submit", (event) => {
    if (!address) { return; }  // no address: let the native action have it
    // The native mailto submission mangles the body in most browsers; build a
    // proper prefilled message instead.
    event.preventDefault();

    const name = value("name");
    const replyTo = value("email");
    const subject = value("subject") || "Hello from the Boston Café Bikers site";
    const message = value("message");

    // Sign the body with the sender's own details: a mailto: opens in *their*
    // mail app, so the From address is theirs, but the name and a preferred
    // reply-to are worth carrying through anyway.
    const signature = [name, replyTo && "<" + replyTo + ">"].filter(Boolean).join(" ");
    const body = signature ? message + "\n\n— " + signature : message;

    const url = "mailto:" + encodeURIComponent(address).replace(/%40/g, "@") +
      "?subject=" + encodeURIComponent(subject) +
      "&body=" + encodeURIComponent(body);

    say("Opening your mail app with the message ready to send…");
    window.location.href = url;
  });
})();
