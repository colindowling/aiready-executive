/* Shared primary navigation.
 *
 * One list, rendered into the first <nav> on the page. Desktop shows at most
 * five top-level items. The Apply Now control is a separate bordered button
 * (the withants.com pattern) and does not count toward the five. Anything
 * past the fifth item is placed under a "More" dropdown. Dropdowns open on
 * hover, on keyboard focus, and on click/tap. Below 1000px — and at any
 * width where the bar would wrap — the text links move into a hamburger panel.
 *
 * What is in the bar today (main):
 *   logo → /
 *   Apply Now → /contact/   (on /contact/, the existing #form target is kept)
 *   No other pages. /15minutesairoadmap/ is an unlisted landing page and is
 *   never added.
 *
 * When PR #2 merges (Advisory, About, Blog), do not hand-copy its <div class="nav-links">
 * into new pages. Either:
 *   1. Leave those anchors in place for one release. If this list's `items`
 *      is still empty, they are adopted, /15minutesairoadmap/ is dropped, and
 *      the rest are ordered Advisory, About, Blog. Three items, no dropdown.
 *   2. Or paste the block below into `items` and delete the duplicated anchors
 *      (and the matching block in scripts/build_blog.py). Preferred, one source.
 *
 *      { label: "Advisory", href: "/advisory/" },
 *      { label: "About", href: "/about/" },
 *      { label: "Blog", href: "/blog/" },
 *
 *   A sixth page goes in a dropdown, which still counts as one of the five:
 *
 *      { label: "More", children: [
 *        { label: "Blog", href: "/blog/" }
 *      ]}
 *
 *   Do not add /15minutesairoadmap/. The roadmap page stays a single-action
 *   page and does not load this script.
 */
(function () {
  var MAX_TOP = 5;
  var BOFU = ["/15minutesairoadmap/"];
  /* Order used only when adopting anchors PR #2 wrote into the HTML. */
  var ADOPT_ORDER = ["/advisory/", "/about/", "/blog/"];

  var nav = document.querySelector("nav.site-nav") || document.querySelector("nav:not(.footer-links)");
  if (!nav || nav.getAttribute("data-nav-ready") === "true") return;
  if (nav.classList.contains("footer-links")) return;

  var preset = window.AIREADY_NAV || {};
  var logoEl = nav.querySelector(".nav-logo");
  var logoHTML = logoEl ? logoEl.innerHTML.trim() : "AIReady <span>Executive</span>";
  var logoHref = (logoEl && logoEl.getAttribute("href")) || "/";
  var ctaEl = nav.querySelector(".nav-cta");
  var ctaHref = nav.getAttribute("data-cta") || (ctaEl && ctaEl.getAttribute("href")) || (preset.cta && preset.cta.href) || "/contact/";
  var ctaLabel = (ctaEl && ctaEl.textContent.trim()) || (preset.cta && preset.cta.label) || "Apply Now";

  function trackAttrString(el, inMenu) {
    if (!el || !el.getAttribute) return "";
    var names = ["data-track", "data-cta", "data-cta-position", "data-cta-id", "data-offer", "data-source-post", "data-cluster", "data-persona"];
    var parts = [];
    names.forEach(function (name) {
      var value = el.getAttribute(name);
      if (!value) return;
      if (inMenu && name === "data-cta-position") value = "nav_menu";
      if (inMenu && name === "data-cta-id") value = value.replace(/-nav$/, "-nav-menu");
      parts.push(name + '="' + esc(value) + '"');
    });
    return parts.length ? " " + parts.join(" ") : "";
  }

  function esc(value) {
    return String(value == null ? "" : value).replace(/[&<>"']/g, function (ch) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch];
    });
  }

  function pathOnly(href) {
    if (!href) return "";
    var path = String(href).split("#")[0].split("?")[0];
    if (!path) return "";
    if (path.length > 1 && path.charAt(path.length - 1) !== "/") path += "/";
    return path;
  }

  function here() {
    var path = window.location.pathname.replace(/index\.html$/, "");
    if (!path) path = "/";
    if (path.length > 1 && path.charAt(path.length - 1) !== "/") path += "/";
    return path;
  }

  function isExcluded(href) {
    var path = pathOnly(href);
    if (!path) return false;
    for (var i = 0; i < BOFU.length; i++) {
      if (path === BOFU[i] || path.indexOf(BOFU[i]) === 0) return true;
    }
    return false;
  }

  function isCurrent(href) {
    var path = pathOnly(href);
    if (!path || path.charAt(0) !== "/") return false;
    if (href.indexOf("#") !== -1 && path === here() && path !== "/") return false;
    return path === here();
  }

  function adoptFromDom() {
    var found = [];
    var anchors = nav.querySelectorAll("a.nav-link[href]");
    Array.prototype.forEach.call(anchors, function (anchor) {
      var href = anchor.getAttribute("href");
      if (!href || isExcluded(href)) return;
      found.push({ label: anchor.textContent.replace(/\s+/g, " ").trim(), href: href });
    });
    found.sort(function (a, b) {
      var ia = ADOPT_ORDER.indexOf(pathOnly(a.href));
      var ib = ADOPT_ORDER.indexOf(pathOnly(b.href));
      if (ia === -1) ia = 1000;
      if (ib === -1) ib = 1000;
      return ia - ib;
    });
    return found;
  }

  function sanitize(list) {
    var clean = [];
    (list || []).forEach(function (item) {
      if (!item || !item.label) return;
      if (item.children && item.children.length) {
        var kids = [];
        item.children.forEach(function (child) {
          if (!child || !child.href || !child.label || isExcluded(child.href)) return;
          kids.push({ label: child.label, href: child.href });
        });
        if (!kids.length) return;
        var parentHref = item.href && !isExcluded(item.href) ? item.href : "";
        clean.push({ label: item.label, href: parentHref, children: kids });
      } else if (item.href && !isExcluded(item.href)) {
        clean.push({ label: item.label, href: item.href });
      }
    });
    if (clean.length <= MAX_TOP) return clean;
    var head = clean.slice(0, MAX_TOP - 1);
    var extra = [];
    clean.slice(MAX_TOP - 1).forEach(function (item) {
      if (item.children) extra = extra.concat(item.children);
      else extra.push({ label: item.label, href: item.href });
    });
    head.push({ label: "More", href: "", children: extra });
    return head;
  }

  var source = Array.isArray(preset.items) ? preset.items : null;
  var items = sanitize(source && source.length ? source : adoptFromDom());

  var chev = '<svg class="aiready-nav__chev" viewBox="0 0 10 6" aria-hidden="true" focusable="false"><path d="M1 1l4 4 4-4" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>';

  function currentAttr(href) {
    return isCurrent(href) ? ' aria-current="page"' : "";
  }

  function linkIsCurrent(item) {
    if (item.href && isCurrent(item.href)) return true;
    if (!item.children) return false;
    for (var i = 0; i < item.children.length; i++) {
      if (isCurrent(item.children[i].href)) return true;
    }
    return false;
  }

  var desktop = items.map(function (item, index) {
    if (!item.children) {
      return '<a class="aiready-nav__link" href="' + esc(item.href) + '"' + currentAttr(item.href) + ">" + esc(item.label) + "</a>";
    }
    var menuId = "aiready-nav-menu-" + index;
    var triggerCurrent = linkIsCurrent(item) ? ' aria-current="page"' : "";
    var trigger;
    if (item.href) {
      trigger = '<a class="aiready-nav__drop-trigger" href="' + esc(item.href) + '" aria-haspopup="true" aria-expanded="false" aria-controls="' + menuId + '"' + triggerCurrent + ">" + esc(item.label) + chev + "</a>";
    } else {
      trigger = '<button type="button" class="aiready-nav__drop-trigger" aria-haspopup="true" aria-expanded="false" aria-controls="' + menuId + '"' + triggerCurrent + ">" + esc(item.label) + chev + "</button>";
    }
    var links = item.children.map(function (child) {
      return '<a href="' + esc(child.href) + '"' + currentAttr(child.href) + ">" + esc(child.label) + "</a>";
    }).join("");
    return '<div class="aiready-nav__drop">' + trigger + '<div class="aiready-nav__menu" id="' + menuId + '" inert>' + links + "</div></div>";
  }).join("");

  var mobile = items.map(function (item) {
    if (!item.children) {
      return '<a class="aiready-nav__plink" href="' + esc(item.href) + '"' + currentAttr(item.href) + ">" + esc(item.label) + "</a>";
    }
    var bits = '<p class="aiready-nav__label">' + esc(item.label) + "</p>";
    if (item.href) {
      bits += '<a class="aiready-nav__plink" href="' + esc(item.href) + '"' + currentAttr(item.href) + ">" + esc(item.label) + "</a>";
    }
    bits += item.children.map(function (child) {
      return '<div class="aiready-nav__sub"><a class="aiready-nav__plink" href="' + esc(child.href) + '"' + currentAttr(child.href) + ">" + esc(child.label) + "</a></div>";
    }).join("");
    return bits;
  }).join("");

  var ctaTrack = trackAttrString(ctaEl, false);
  var ctaTrackMenu = trackAttrString(ctaEl, true);

  nav.classList.add("aiready-nav");
  nav.setAttribute("aria-label", "Primary");
  nav.setAttribute("data-nav-ready", "true");
  nav.innerHTML =
    '<a class="aiready-nav__logo" href="' + esc(logoHref) + '">' + logoHTML + "</a>" +
    '<div class="aiready-nav__bar">' +
      '<div class="aiready-nav__links">' + desktop + "</div>" +
      '<a class="aiready-nav__cta" href="' + esc(ctaHref) + '"' + ctaTrack + ">" + esc(ctaLabel) + "</a>" +
      '<button type="button" class="aiready-nav__toggle" aria-expanded="false" aria-controls="aiready-nav-panel" aria-label="Open menu">' +
        "<span></span><span></span><span></span>" +
      "</button>" +
    "</div>" +
    '<div id="aiready-nav-panel" class="aiready-nav__panel" hidden role="region" aria-label="Menu">' +
      mobile +
      '<a class="aiready-nav__cta" href="' + esc(ctaHref) + '"' + ctaTrackMenu + ">" + esc(ctaLabel) + "</a>" +
    "</div>";

  var toggle = nav.querySelector(".aiready-nav__toggle");
  var panel = nav.querySelector(".aiready-nav__panel");
  var lockedScroll = "";
  var pointerIsMouse = true;

  window.addEventListener("pointerdown", function (event) {
    pointerIsMouse = !event.pointerType || event.pointerType === "mouse";
  }, true);

  function focusable(root) {
    return Array.prototype.filter.call(
      root.querySelectorAll("a[href], button:not([disabled])"),
      function (el) {
        return !el.hidden && el.getAttribute("aria-hidden") !== "true" && el.getClientRects().length > 0;
      }
    );
  }

  function placeMenu(menu) {
    menu.style.left = "0";
    menu.style.right = "auto";
    var rect = menu.getBoundingClientRect();
    if (rect.right > window.innerWidth - 12) {
      menu.style.left = "auto";
      menu.style.right = "0";
    }
  }

  function closeDrop(drop, restore) {
    if (!drop) return;
    var trigger = drop.querySelector(".aiready-nav__drop-trigger");
    var menu = drop.querySelector(".aiready-nav__menu");
    drop.classList.remove("is-open");
    if (trigger) trigger.setAttribute("aria-expanded", "false");
    if (menu) menu.inert = true;
    if (restore && trigger) trigger.focus();
  }

  function closeAllDrops(except) {
    Array.prototype.forEach.call(nav.querySelectorAll(".aiready-nav__drop.is-open"), function (drop) {
      if (drop !== except) closeDrop(drop, false);
    });
  }

  function openDrop(drop) {
    drop.dataset.openedAt = String(performance.now());
    closeAllDrops(drop);
    var trigger = drop.querySelector(".aiready-nav__drop-trigger");
    var menu = drop.querySelector(".aiready-nav__menu");
    drop.classList.add("is-open");
    if (trigger) trigger.setAttribute("aria-expanded", "true");
    if (menu) {
      menu.inert = false;
      placeMenu(menu);
    }
  }

  function closePanel(restore) {
    if (!panel || panel.hidden) return;
    panel.hidden = true;
    toggle.setAttribute("aria-expanded", "false");
    toggle.setAttribute("aria-label", "Open menu");
    document.body.style.overflow = lockedScroll;
    if (restore) toggle.focus();
  }

  function openPanel() {
    closeAllDrops(null);
    panel.hidden = false;
    toggle.setAttribute("aria-expanded", "true");
    toggle.setAttribute("aria-label", "Close menu");
    lockedScroll = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    var first = focusable(panel)[0];
    if (first) first.focus();
  }

  function mobileLayout() {
    return window.matchMedia("(max-width: 1000px)").matches || nav.classList.contains("aiready-nav--collapsed");
  }

  toggle.addEventListener("click", function () {
    if (toggle.getAttribute("aria-expanded") === "true") closePanel(false);
    else openPanel();
  });

  panel.addEventListener("click", function (event) {
    var link = event.target.closest("a");
    if (!link) return;
    closePanel(false);
  });

  Array.prototype.forEach.call(nav.querySelectorAll(".aiready-nav__drop"), function (drop) {
    var trigger = drop.querySelector(".aiready-nav__drop-trigger");
    var suppressClick = false;
    var closeTimer;

    drop.addEventListener("mouseenter", function () {
      if (!pointerIsMouse || mobileLayout()) return;
      clearTimeout(closeTimer);
      openDrop(drop);
    });

    drop.addEventListener("mouseleave", function () {
      if (!pointerIsMouse) return;
      closeTimer = setTimeout(function () {
        if (drop.contains(document.activeElement)) return;
        closeDrop(drop, false);
      }, 140);
    });

    if (trigger) {
      trigger.addEventListener("focus", function () {
        if (mobileLayout() || !trigger.matches(":focus-visible")) return;
        suppressClick = true;
        openDrop(drop);
        setTimeout(function () { suppressClick = false; }, 0);
      });

      trigger.addEventListener("click", function (event) {
        if (mobileLayout()) return;
        var isLink = trigger.tagName === "A";
        var open = drop.classList.contains("is-open");
        if (suppressClick && open) {
          if (!isLink) event.preventDefault();
          return;
        }
        if (!open) {
          event.preventDefault();
          openDrop(drop);
          return;
        }
        /* Hover opens on mouseenter just before this click. Keep that open
           instead of toggling it shut on the same gesture. A later click closes. */
        if (performance.now() - Number(drop.dataset.openedAt || 0) < 450) {
          if (!isLink) event.preventDefault();
          return;
        }
        if (!isLink) {
          event.preventDefault();
          closeDrop(drop, false);
        }
      });
    }

    drop.addEventListener("focusout", function (event) {
      if (!drop.contains(event.relatedTarget)) closeDrop(drop, false);
    });

    drop.addEventListener("keydown", function (event) {
      if (event.key === "Escape") {
        event.stopPropagation();
        closeDrop(drop, true);
      }
    });
  });

  document.addEventListener("click", function (event) {
    if (nav.contains(event.target)) return;
    closePanel(false);
    closeAllDrops(null);
  });

  document.addEventListener("keydown", function (event) {
    if ((event.key === "Escape" || event.key === "Esc") && panel && !panel.hidden) {
      event.preventDefault();
      closePanel(true);
      return;
    }
    if (event.key !== "Tab" || !panel || panel.hidden) return;
    var nodes = [toggle].concat(focusable(panel));
    if (!nodes.length) return;
    var first = nodes[0];
    var last = nodes[nodes.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }, true);

  /* Measure the bar itself. A wide table elsewhere on the page must not
     collapse the nav, and a wrapping bar must collapse even if the document
     hasn't grown a scrollbar yet. */
  /* Letter-spacing paints past the logo's border box, so measure the glyphs. */
  function inkRight(el) {
    if (!el) return 0;
    var range = document.createRange();
    range.selectNodeContents(el);
    var rect = range.getBoundingClientRect();
    return rect.width ? rect.right : el.getBoundingClientRect().right;
  }

  function collides() {
    var logo = nav.querySelector(".aiready-nav__logo");
    var bar = nav.querySelector(".aiready-nav__bar");
    if (!logo || !bar) return false;
    var navRect = nav.getBoundingClientRect();
    var logoRect = logo.getBoundingClientRect();
    var limit = inkRight(logo) + 12;
    var kids = bar.children;
    for (var i = 0; i < kids.length; i++) {
      var el = kids[i];
      if (window.getComputedStyle(el).display === "none") continue;
      var rect = el.getBoundingClientRect();
      if (rect.width < 1) continue;
      if (rect.left < limit) return true;
      if (rect.right > navRect.right + 1) return true;
      if (rect.bottom > navRect.bottom + 1) return true;
    }
    if (logoRect.left < navRect.left - 1) return true;
    if (logoRect.bottom > navRect.bottom + 1) return true;
    return false;
  }

  function fit() {
    var wasMobile = mobileLayout();
    nav.classList.remove("aiready-nav--collapsed", "aiready-nav--hide-cta", "aiready-nav--compact");
    if (!window.matchMedia("(max-width: 1000px)").matches && collides()) {
      nav.classList.add("aiready-nav--collapsed");
    }
    /* The panel always carries Apply Now, so the bar copy can leave
       before the wordmark is tightened. */
    if (collides()) nav.classList.add("aiready-nav--hide-cta");
    if (collides()) nav.classList.add("aiready-nav--compact");
    if (wasMobile && !mobileLayout() && panel && !panel.hidden) closePanel(false);
  }

  fit();
  window.addEventListener("resize", fit);
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(fit);
})();
