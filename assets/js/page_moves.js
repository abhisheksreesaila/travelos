/* F-099: tags each cross-document page change as forward or back so base.css can slide it the right way.
   Loaded without defer in the head: the reveal of the new page can fire before a deferred script runs.
   Needs pageswap/pagereveal (Chrome 124+, Safari 18.2+); elsewhere it does nothing. */
(function () {
  function go(act) {
    if (!act || act.navigationType === 'reload') return '';
    if (act.navigationType !== 'traverse') return 'ga-fwd';
    return act.from && act.entry && act.entry.index > act.from.index ? 'ga-fwd' : 'ga-back';
  }
  function tag(e, act) {
    var t = go(act);
    if (t && e.viewTransition && e.viewTransition.types) e.viewTransition.types.add(t);
  }
  addEventListener('pageswap', function (e) { tag(e, e.activation); });
  addEventListener('pagereveal', function (e) { tag(e, window.navigation && navigation.activation); });
})();
