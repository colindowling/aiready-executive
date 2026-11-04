/* Shared GA4 events for AIReady Executive, modeled on rncld.com/assets/track.js.
   Events: cta_click, apply_now_click, book_call_click, book_call_scheduled,
   calendly_time_selected, contact_form_submit, lead_magnet_request,
   outbound_email_click, outbound_phone_click, outbound_click.
   Payloads include page_location, page_template, cta_position and cta_id,
   plus first-touch attribution. Add ?aire_test=1 to mark hits for DebugView.

   The measurement ID is the assignment on the next line.
   An all-X ID does not define gtag and does not request gtag.js.
   */
var GA_MEASUREMENT_ID = "G-GDHNVJGQMJ";

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
  var ATTR_KEY = "aire_attr";
  var CTA_KEY = "aire_last_cta";
  var TEST_KEY = "aire_test";
  var pending = null;
  var seenBookingUris = {};

  function attr(el, name) {
    if (!el || !el.getAttribute) return "";
    return el.getAttribute(name) || "";
  }

  function ownHost(hostname) {
    if (!hostname) return false;
    if (hostname === window.location.hostname) return true;
    return hostname === "theaireadyexecutive.com" || hostname === "www.theaireadyexecutive.com";
  }

  function readJson(key) {
    try {
      var raw = sessionStorage.getItem(key);
      return raw ? JSON.parse(raw) : null;
    } catch (err) {
      return null;
    }
  }

  function writeJson(key, value) {
    try { sessionStorage.setItem(key, JSON.stringify(value)); } catch (err) {}
  }

  function landingPath() {
    var params = new URLSearchParams(window.location.search);
    params.delete("aire_test");
    var query = params.toString();
    return window.location.pathname + (query ? "?" + query : "");
  }

  function externalReferrer() {
    if (!document.referrer) return "";
    try {
      var host = new URL(document.referrer).hostname;
      if (ownHost(host)) return "";
      return document.referrer;
    } catch (err) {
      return "";
    }
  }

  function captureAttr() {
    var existing = readJson(ATTR_KEY);
    if (existing) return existing;
    var params = new URLSearchParams(window.location.search);
    var record = {
      utm_source: params.get("utm_source") || "",
      utm_medium: params.get("utm_medium") || "",
      utm_campaign: params.get("utm_campaign") || "",
      utm_term: params.get("utm_term") || "",
      utm_content: params.get("utm_content") || "",
      referrer: externalReferrer(),
      landing_page: landingPath()
    };
    writeJson(ATTR_KEY, record);
    return record;
  }

  function captureTest() {
    var params = new URLSearchParams(window.location.search);
    if (params.get("aire_test") !== "1") return;
    try {
      if (!sessionStorage.getItem(TEST_KEY)) {
        var day = new Date().toISOString().slice(0, 10).replace(/-/g, "");
        sessionStorage.setItem(TEST_KEY, "TEST-aire-" + day);
      }
    } catch (err) {}
  }

  function attrParams() {
    var stored = readJson(ATTR_KEY) || {};
    return {
      first_utm_source: stored.utm_source || "",
      first_utm_medium: stored.utm_medium || "",
      first_utm_campaign: stored.utm_campaign || "",
      first_utm_term: stored.utm_term || "",
      first_utm_content: stored.utm_content || "",
      landing_page: stored.landing_page || "",
      first_referrer: stored.referrer || ""
    };
  }

  function testParams() {
    var label = "";
    try { label = sessionStorage.getItem(TEST_KEY) || ""; } catch (err) {}
    if (!label) return {};
    return { debug_mode: true, test_label: label };
  }

  function offerOf(el) {
    return attr(el, "data-offer") || attr(document.body, "data-offer");
  }

  function payload(el) {
    var body = document.body;
    var data = {
      page_location: window.location.href,
      page_template: attr(el, "data-page-template") || attr(body, "data-page-template"),
      cta_position: attr(el, "data-cta-position") || attr(el, "data-cta"),
      cta_id: attr(el, "data-cta-id")
    };
    var offer = offerOf(el);
    if (offer) data.offer = offer;
    var base = attrParams();
    Object.keys(base).forEach(function (key) { data[key] = base[key]; });
    var flags = testParams();
    Object.keys(flags).forEach(function (key) { data[key] = flags[key]; });
    return data;
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
  window.aireadyAttribution = function () { return readJson(ATTR_KEY) || {}; };
  window.aireadyLastCta = function () { return readJson(CTA_KEY); };

  function rememberCta(el) {
    writeJson(CTA_KEY, {
      post: attr(el, "data-source-post"),
      position: attr(el, "data-cta-position") || attr(el, "data-cta"),
      cta_id: attr(el, "data-cta-id"),
      offer: offerOf(el),
      page: window.location.pathname,
      href: el.getAttribute ? (el.getAttribute("href") || el.getAttribute("data-url") || "") : ""
    });
  }

  function withAttribution(url) {
    var parsed;
    try { parsed = new URL(url, window.location.href); } catch (err) { return url; }
    if (parsed.hostname.indexOf("calendly.com") === -1) return url;
    var stored = readJson(ATTR_KEY) || {};
    if (stored.utm_source) parsed.searchParams.set("utm_source", stored.utm_source);
    if (stored.utm_medium) parsed.searchParams.set("utm_medium", stored.utm_medium);
    if (stored.utm_term) parsed.searchParams.set("utm_term", stored.utm_term);
    return parsed.toString();
  }

  function rewriteEmbeds() {
    var nodes = document.querySelectorAll(".calendly-inline-widget[data-url]");
    Array.prototype.forEach.call(nodes, function (node) {
      var next = withAttribution(node.getAttribute("data-url"));
      if (next !== node.getAttribute("data-url")) node.setAttribute("data-url", next);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", rewriteEmbeds);
  } else {
    rewriteEmbeds();
  }

  function calendlySlug(url) {
    if (!url) return "";
    try {
      var path = new URL(url, window.location.href).pathname.replace(/\/+$/, "");
      var parts = path.split("/");
      return parts[parts.length - 1] || "";
    } catch (err) {
      return "";
    }
  }

  function schedulingUrl(el) {
    if (!el || !el.getAttribute) return "";
    return el.getAttribute("data-url") || el.getAttribute("href") || "";
  }

  var CALENDLY_CSS = "https://assets.calendly.com/assets/external/widget.css";
  var CALENDLY_JS = "https://assets.calendly.com/assets/external/widget.js";

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
    var url = withAttribution(anchor.href);
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

  function linkHost(href) {
    try { return new URL(href, window.location.href).hostname; } catch (err) { return ""; }
  }

  document.addEventListener("click", function (event) {
    var el = event.target && event.target.closest ? event.target.closest("a[href]") : null;
    if (!el) return;
    var href = el.getAttribute("href") || "";
    if (href.indexOf("mailto:") === 0) {
      track("outbound_email_click", el, { link_domain: "mailto" });
      return;
    }
    if (href.indexOf("tel:") === 0) {
      track("outbound_phone_click", el, { link_domain: "tel" });
      return;
    }

    var host = linkHost(href);
    var calendly = href.indexOf("calendly.com") !== -1 || (host && host.indexOf("calendly.com") !== -1);
    var kind = attr(el, "data-track");
    if (!kind && calendly) kind = "book_call";

    if (kind) {
      rememberCta(el);
      track("cta_click", el);
      if (kind === "apply_now") {
        track("apply_now_click", el);
        return;
      }
      if (kind === "book_call" || calendly) {
        track("book_call_click", el);
        pending = el;
        if (calendly && el.getAttribute("target") !== "_blank") {
          event.preventDefault();
          openCalendly(el);
        }
      }
      return;
    }

    if (host && !ownHost(host)) {
      track("outbound_click", el, { link_domain: host });
    }
  }, true);

  function bookingUri(data) {
    var body = data.payload || {};
    var scheduled = body.event;
    if (!scheduled) return "";
    if (typeof scheduled === "string") return scheduled;
    return scheduled.uri || "";
  }

  function embedEl() {
    return document.querySelector(".calendly-inline-widget[data-cta-id]") ||
      document.querySelector("[data-cta-id='book_call-embed']");
  }

  window.addEventListener("message", function (event) {
    var data = event.data;
    if (!data || typeof data.event !== "string") return;
    if (data.event.indexOf("calendly.") !== 0) return;
    if (event.origin && event.origin.indexOf("calendly.com") === -1) return;

    if (data.event === "calendly.event_type_viewed") {
      if (pending) return;
      var embed = embedEl();
      if (!embed) return;
      pending = embed;
      track("book_call_click", embed, { cta_position: "embed" });
      return;
    }

    var source = pending || embedEl() || document.body;

    if (data.event === "calendly.date_and_time_selected") {
      track("calendly_time_selected", source);
      return;
    }

    if (data.event !== "calendly.event_scheduled") return;
    var uri = bookingUri(data);
    if (uri && seenBookingUris[uri]) return;
    if (uri) seenBookingUris[uri] = true;

    var offer = offerOf(source);
    track("book_call_scheduled", source, {
      offer: offer,
      calendly_event: calendlySlug(schedulingUrl(source))
    });
    if (offer === "roadmap_15min") {
      track("lead_magnet_request", source, { lead_magnet: "roadmap_15min", offer: offer });
    }
    pending = null;
  });

  captureAttr();
  captureTest();
})();
