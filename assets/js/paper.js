// F-201 · the paper map (ported from docs/design/cockpit/core/paper.js). No map library and no tiles at run time: the trip's geo pack is one relief image, light or
// dark, and its OpenStreetMap shapes (main roads, lakes, towns, state lines); each day's drive is gitaway.geo's line. The sheet is tilted with a CSS 3D transform; the
// stops' dots lie on it and their labels stand upright over them like a pop-up book: the labels are a flat layer above the sheet, each placed where its point lands
// on the screen (the sheet's own matrix and the perspective, read from the page), so no browser has to sort 3D layers (which hid them at phone sizes) and the words
// are never sheared. A new day re-flies the camera: one CSS transition of the sheet's transform with the --motion-* tokens (cockpit.css: on the spring on a phone, a
// calm ease on a desktop, none under reduced motion, where the sheet fades in at its new place instead); the labels follow it frame by frame while it moves.
// Text from the trip or from OpenStreetMap is always escaped.
//
//   GA.paper.mount(el, data, opts) -> { setDay(i, { instant }), setPack(data), setDark(bool), day() }
//   data: { box: [w, s, e, n], km: [kw, kh], pack: { light, dark, shapes } | null, days: [{ stops: [{ lat, lon, label, time, kind, icon, stay }], route, min }], icons: { name: svg } }
//   opts: { tilt, fitW, fitH, cy, maxZoom, minor, pillAt, shapes (the pack's shapes JSON, once fetched) }
(function () {
  var GA = window.GA = window.GA || {};
  if (GA.paper) return;
  var PW = 1000;
  var reducedQ = window.matchMedia ? window.matchMedia('(prefers-reduced-motion: reduce)') : { matches: false };
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function mins(m) { var h = Math.floor(m / 60), r = m % 60; return h ? h + ' h' + (r ? ' ' + r + ' min' : '') : m + ' min'; }

  function mount(el, data, opts) {
    opts = opts || {};
    var box = data.box, PH, X, Y, shapes = opts.shapes || null, dark = false, day = -1, tilt = opts.tilt || 44;
    function project() {
      var km = data.km || [1, 1];
      PH = Math.round(PW * km[1] / km[0]);
      X = function (lon) { return (lon - box[0]) / (box[2] - box[0]) * PW; };
      Y = function (lat) { return (box[3] - lat) / (box[3] - box[1]) * PH; };
    }
    function pd(pts, close) {
      var out = '';
      for (var i = 0; i < pts.length; i++) out += (i ? 'L' : 'M') + X(pts[i][0]).toFixed(1) + ',' + Y(pts[i][1]).toFixed(1);
      return out + (close ? 'Z' : '');
    }
    function centroid(ring) { var x = 0, y = 0; ring.forEach(function (p) { x += p[0]; y += p[1]; }); return [x / ring.length, y / ring.length]; }
    function area(ring) { var s = 0; for (var i = 0; i < ring.length; i++) { var a = ring[i], b = ring[(i + 1) % ring.length]; s += X(a[0]) * Y(b[1]) - X(b[0]) * Y(a[1]); } return Math.abs(s) / 2; }

    function svg() {
      var parts = [];
      if (data.pack) parts.push('<image class="pp-relief" href="' + esc(dark ? data.pack.dark : data.pack.light) + '" x="0" y="0" width="' + PW + '" height="' + PH + '" preserveAspectRatio="none"/>');
      if (shapes) {
        shapes.lakes.forEach(function (l) { parts.push('<path class="pp-lake" d="' + pd(l.ring, true) + '"/>'); });
        if (shapes.borders.length) parts.push('<path class="pp-border" d="' + shapes.borders.map(function (b) { return pd(b); }).join('') + '"/>');
        var roads = shapes.roads.map(function (r) { return pd(r.pts); }).join('');
        parts.push('<path class="pp-road-c" d="' + roads + '"/><path class="pp-road" d="' + roads + '"/>');
        shapes.lakes.filter(function (l) { return l.name && area(l.ring) > PW * PH * 0.02; }).slice(0, 2).forEach(function (l) {
          var c = centroid(l.ring);
          parts.push('<text class="pp-lakename" font-size="22" x="' + X(c[0]).toFixed(1) + '" y="' + Y(c[1]).toFixed(1) + '">' + esc(l.name) + '</text>');
        });
        shapes.towns.forEach(function (t) { parts.push('<text class="pp-town" font-size="' + (t.city ? 14 : 12) + '" x="' + X(t.lon).toFixed(1) + '" y="' + Y(t.lat).toFixed(1) + '">' + esc(t.name) + '</text>'); });
      }
      var all = data.days.filter(function (d) { return d.route; }).map(function (d) { return pd(d.route); }).join('');
      if (all) parts.push('<path class="pp-route-all" d="' + all + '"/>');
      parts.push('<path class="pp-route-c" data-rc d=""/><path class="pp-route" data-route d="" pathLength="1"/>');
      return '<svg class="pp-svg" viewBox="0 0 ' + PW + ' ' + PH + '" width="' + PW + '" height="' + PH + '" aria-hidden="true">' + parts.join('') + '</svg>';
    }
    var plane, bb, tags, route, rc, anchors = [], follow = 0;
    function build() {
      project();
      el.classList.add('pp');
      el.innerHTML = '<div class="pp-plane" style="width:' + PW + 'px;height:' + PH + 'px">' + svg() + '<div class="pp-bb" data-bb></div></div><div class="pp-tags" data-tags></div>';
      plane = el.querySelector('.pp-plane'); bb = el.querySelector('[data-bb]'); tags = el.querySelector('[data-tags]');
      route = el.querySelector('[data-route]'); rc = el.querySelector('[data-rc]');
      plane.style.setProperty('--tilt', tilt + 'deg');
      plane.addEventListener('transitionend', function (e) { if (e.propertyName === 'transform') { stopFollow(); place(); } });
    }
    // where a point of the sheet lands on the screen: the sheet's matrix now (mid-flight too), then the parent's perspective about its origin
    function projector() {
      var cs = getComputedStyle(plane), ps = getComputedStyle(el);
      var m = new DOMMatrix(cs.transform === 'none' ? undefined : cs.transform);
      var P = parseFloat(ps.perspective) || 0, o = (ps.perspectiveOrigin || '0 0').split(' ').map(parseFloat);
      return function (x, y) {
        var q = m.transformPoint(new DOMPoint(x, y, 0, 1));
        var w = q.w - (P ? q.z / P : 0);
        if (w <= 0.01) return null;
        return [(q.x - o[0] * q.w) / w + o[0], (q.y - o[1] * q.w) / w + o[1]];
      };
    }
    function place() {
      var at = projector(), W = el.clientWidth, pad = 6;
      anchors.forEach(function (a) {
        var p = at(a.x, a.y);
        a.el.style.visibility = p ? '' : 'hidden';
        if (!p) return;
        a.el.style.transform = 'translate3d(' + p[0].toFixed(1) + 'px,' + p[1].toFixed(1) + 'px,0)';
        var tag = a.el.firstElementChild, half = (a.w || (a.w = tag.offsetWidth)) / 2;      // a label near an edge slides inward; its arrow stays on the point
        var dx = p[0] - half < pad ? pad - (p[0] - half) : p[0] + half > W - pad ? (W - pad) - (p[0] + half) : 0;
        tag.style.setProperty('--dx', dx.toFixed(1) + 'px');
      });
    }
    function stopFollow() { if (follow) cancelAnimationFrame(follow); follow = 0; }
    function startFollow() {      // while the camera flies, the labels ride along (a frame's few writes; the flight itself stays on the compositor)
      stopFollow();
      var until = performance.now() + 1500;
      (function tick(now) { place(); follow = now < until ? requestAnimationFrame(tick) : 0; })(performance.now());
    }

    var cam = { s: 1, cx: PW / 2, cy: 0 };
    function frame(pts, instant) {
      var b = el.getBoundingClientRect();
      if (!b.width || !b.height) return;
      var xs = pts.map(function (p) { return X(p[0]); }), ys = pts.map(function (p) { return Y(p[1]); });
      var minx = Math.min.apply(null, xs), maxx = Math.max.apply(null, xs), miny = Math.min.apply(null, ys), maxy = Math.max.apply(null, ys);
      var bw = Math.max(maxx - minx, 60), bh = Math.max(maxy - miny, 60), c = Math.cos(tilt * Math.PI / 180);
      var s = Math.max(0.12, Math.min(opts.maxZoom || 2.1, (b.width * (opts.fitW || 0.6)) / bw, (b.height * (opts.fitH || 0.5)) / (bh * c)));
      cam = { s: s, cx: (minx + maxx) / 2, cy: (miny + maxy) / 2, w: b.width, h: b.height };
      if (instant) { el.classList.add('is-instant'); requestAnimationFrame(function () { requestAnimationFrame(function () { el.classList.remove('is-instant'); }); }); }
      // scale3d, not scale: a 2D scale does not commute with the tilt, so the labels' counter-scale would stretch them
      plane.style.transform = 'translate3d(' + (b.width / 2).toFixed(1) + 'px,' + (b.height * (opts.cy || 0.58)).toFixed(1) + 'px,0) rotateX(' + tilt + 'deg) scale3d(' + s + ',' + s + ',' + s + ') translate(' + (-cam.cx).toFixed(1) + 'px,' + (-cam.cy).toFixed(1) + 'px)';
      plane.style.setProperty('--inv', (1 / s).toFixed(4));
    }
    function dot(st) { return '<span class="pp-dot ck-k-' + esc(st.kind) + '" style="left:' + X(st.lon).toFixed(1) + 'px;top:' + Y(st.lat).toFixed(1) + 'px"></span>'; }
    function label(st, minor, below) {
      var ic = (data.icons || {})[st.icon] || (data.icons || {}).pin || '';
      return '<div class="pp-a"><span class="pp-lbl' + (minor ? ' minor' : '') + (below ? ' below' : '') + '"><span class="pp-ic ck-k-' + esc(st.kind) + '">' + ic + '</span>' + esc(st.label) +
        (st.time ? ' <em>' + esc(st.time) + '</em>' : '') + '</span></div>';
    }
    function setDay(i, o) {
      o = o || {};
      if (i === day && !o.force) return;
      day = i;
      var d = data.days[i] || { stops: [], route: null, min: 0 };
      var p = d.route ? pd(d.route) : '';
      route.setAttribute('d', p); rc.setAttribute('d', p);
      route.classList.remove('draw');
      void route.getBoundingClientRect();
      if (p && !o.instant) route.classList.add('draw');
      var pts = (d.route || []).slice();
      d.stops.forEach(function (st) { pts.push([st.lon, st.lat]); });
      if (pts.length === 1) pts.push([pts[0][0] + 0.03, pts[0][1] + 0.02], [pts[0][0] - 0.03, pts[0][1] - 0.02]);
      if (!pts.length) pts = [[box[0] + (box[2] - box[0]) * 0.1, box[1] + (box[3] - box[1]) * 0.1], [box[2] - (box[2] - box[0]) * 0.1, box[3] - (box[3] - box[1]) * 0.1]];
      frame(pts, o.instant);
      // labels: the day's stops stand up; the stay is a small one unless it is all the day has; one that would sit on another hangs below its dot (judged where
      // the camera is going, so the choice holds when it lands)
      var dest = destProjector(), placed = [], dots = '', html = '';
      anchors = [];
      d.stops.forEach(function (st) {
        var minor = (st.stay && d.stops.length > 1) || !!opts.minor;
        var at = dest(X(st.lon), Y(st.lat)) || [0, 0], wide = 40 + st.label.length * 7.5 + (st.time ? 60 : 0), W = el.clientWidth;
        at = [Math.min(Math.max(at[0], wide / 2 + 6), Math.max(W - wide / 2 - 6, wide / 2 + 6)), at[1]];      // where it will sit once slid inside the map (place() slides it)
        var hit = placed.some(function (q) { return Math.abs(q[0] - at[0]) < (q[2] + wide) / 2 && Math.abs(q[1] - at[1]) < 40; });
        placed.push([at[0], at[1] + (hit ? 48 : 0), wide]);
        dots += dot(st);
        html += label(st, minor, hit);
        anchors.push({ x: X(st.lon), y: Y(st.lat) });
      });
      if (d.route && d.min) {
        var mid = d.route[Math.floor(d.route.length * (opts.pillAt || 0.3))];
        html += '<div class="pp-a"><span class="pp-time">' + ((data.icons || {}).car || '') + esc(mins(d.min)) + '</span></div>';
        anchors.push({ x: X(mid[0]), y: Y(mid[1]) });
      }
      bb.innerHTML = dots;
      tags.innerHTML = html;
      Array.prototype.forEach.call(tags.children, function (n, k) { anchors[k].el = n; });
      if (o.instant || reducedQ.matches) place(); else startFollow();
      if (!o.instant && reducedQ.matches && GA.motion) { GA.motion.fade(plane); GA.motion.fade(tags); }       // reduced motion: no flight, a short fade at the new place
      el.dataset.day = String(i);
    }
    // where a point will land once the camera has arrived (the transform just set, not the one mid-flight)
    function destProjector() {
      var ps = getComputedStyle(el), m = new DOMMatrix(plane.style.transform || undefined);
      var P = parseFloat(ps.perspective) || 0, o = (ps.perspectiveOrigin || '0 0').split(' ').map(parseFloat);
      return function (x, y) {
        var q = m.transformPoint(new DOMPoint(x, y, 0, 1)), w = q.w - (P ? q.z / P : 0);
        return w <= 0.01 ? null : [(q.x - o[0] * q.w) / w + o[0], (q.y - o[1] * q.w) / w + o[1]];
      };
    }
    function setPack(next) {
      data = next;
      box = data.box;
      shapes = next.shapes || shapes;
      var keep = day;
      build();
      day = -1;
      if (keep >= 0) setDay(keep, { instant: true });
    }
    function setDark(on) {
      dark = !!on;
      if (dark) el.setAttribute('data-dark', ''); else el.removeAttribute('data-dark');
      var img = el.querySelector('.pp-relief');
      if (img && data.pack) img.setAttribute('href', dark ? data.pack.dark : data.pack.light);
    }
    build();
    if ('ResizeObserver' in window) new ResizeObserver(function () { if (day >= 0) setDay(day, { force: true, instant: true }); }).observe(el);
    return { setDay: setDay, setPack: setPack, setDark: setDark, day: function () { return day; }, frameAll: function () { frame([[box[0], box[1]], [box[2], box[3]]]); } };
  }
  GA.paper = { mount: mount };
})();
