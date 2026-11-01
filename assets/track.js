/* Shared GA4 events for AIReady Executive, modeled on rncld.com/assets/track.js.
   Events: cta_click, apply_now_click, book_call_click, book_call_scheduled,
   contact_form_submit. Existing page scripts still send calendly_open and
   meeting_booked when gtag exists.
   Payloads include page_location, page_template, cta_position and cta_id
   from data attributes (cluster and persona too, when set).

   The measurement ID is the assignment on the next line. Replace
   G-XXXXXXXXXX with the real GA4 ID. While it is still all X's, this
   file does not define gtag and does not request gtag.js. */
var GA_MEASUREMENT_ID = "G-XXXXXXXXXX";

(function () {
  var id = typeof GA_MEASUREMENT_ID === "string" ? GA_MEASUREMENT_ID : "";
  var enabled = /^G-(?!X+$)[A-Z0-9]+$/.test(id);

  function installGtag(measurementId) {
    window.dataLayer = window.dataLayer || [];
    window.gtag = function () { window.dataLayer.push(arguments); };
    window.gtag("js", new Date());
    window.gtag("config", measurementId);
    var script = document.createElement("script");
    script.async = true;
    script.src = "https://www.googletagmanager.com/gtag/js?id=" + encodeURIComponent(measurementId);
    document.head.appendChild(script);
  }

  if (enabled) installGtag(id);

  var CALENDLY_CSS = "https://assets.calendly.com/assets/external/widget.css";
  var CALENDLY_JS = "https://assets.calendly.com/assets/external/widget.js";
  var pending = null;

  function attr(el, name) {
    if (!el || !el.getAttribute) return "";
    return el.getAttribute(name) || "";
  }

  function payload(el) {
    var body = document.body;
    return {
      page_location: window.location.href,
      page_template: attr(el, "data-page-template") || attr(body, "data-page-template"),
      cta_position: attr(el, "data-cta-position") || attr(el, "data-cta"),
      cta_id: attr(el, "data-cta-id"),
      cluster: attr(el, "data-cluster") || attr(body, "data-cluster"),
      persona: attr(el, "data-persona") || attr(body, "data-persona")
    };
  }

  function track(name, el, extra) {
    if (typeof window.gtag !== "function") return;
    var data = payload(el || document.body);
    if (extra) {
      Object.keys(extra).forEach(function (key) { data[key] = extra[key]; });
    }
    window.gtag("event", name, data);
  }

  window.aireadyTrack = track;

  function loadWidget(done, fail) {
    if (window.Calendly && window.Calendly.initPopupWidget) {
      done();
      return;
    }
    if (!document.querySelector("link[data-aiready-calendly]")) {
      var link = document.createElement("link");
      link.rel = "stylesheet";
      link.href = CALENDLY_CSS;
      link.setAttribute("data-aiready-calendly", "1");
      document.head.appendChild(link);
    }
    var existing = document.querySelector("script[data-aiready-calendly]");
    if (existing) {
      existing.addEventListener("load", done);
      existing.addEventListener("error", fail);
      return;
    }
    var script = document.createElement("script");
    script.src = CALENDLY_JS;
    script.async = true;
    script.setAttribute("data-aiready-calendly", "1");
    script.addEventListener("load", done);
    script.addEventListener("error", fail);
    document.head.appendChild(script);
  }

  function openCalendly(anchor) {
    var url = anchor.href;
    loadWidget(
      function () {
        if (window.Calendly && window.Calendly.initPopupWidget) {
          window.Calendly.initPopupWidget({ url: url });
        } else {
          window.location.href = url;
        }
      },
      function () {
        window.location.href = url;
      }
    );
  }

  document.addEventListener("click", function (event) {
    var el = event.target && event.target.closest
      ? event.target.closest("[data-track], a[href*='calendly.com']")
      : null;
    if (!el) return;
    var href = el.getAttribute("href") || "";
    var kind = attr(el, "data-track");
    if (!kind && href.indexOf("calendly.com") !== -1) kind = "book_call";
    if (!kind) return;

    track("cta_click", el);
    if (kind === "apply_now") {
      track("apply_now_click", el);
      return;
    }
    if (kind === "book_call" || href.indexOf("calendly.com") !== -1) {
      track("book_call_click", el);
      pending = el;
      /* Same-tab Calendly links open the popup, as on rncld.com.
         target=_blank keeps the landing page's new tab. */
      if (href.indexOf("calendly.com") !== -1 && el.getAttribute("target") !== "_blank") {
        event.preventDefault();
        openCalendly(el);
      }
    }
  }, true);

  window.addEventListener("message", function (event) {
    var data = event.data;
    if (!data || data.event !== "calendly.event_scheduled") return;
    if (event.origin && event.origin.indexOf("calendly.com") === -1) return;
    var el = pending || document.querySelector("[data-cta-id='book_call-embed']") || document.body;
    track("book_call_scheduled", el);
    pending = null;
  });
})();
