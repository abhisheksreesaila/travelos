// All my posts at once and My drafts (F-190). Two small helps, both optional (the pages work without JavaScript):
//  1. Picking posts: the button counts what is ticked, stays off at zero and the boxes stop at the most the creator may draft today.
//  2. My drafts: while anything is still drafting, ask the server for the list every few seconds and swap in only the rows that changed (a new row fades in with the one calm motion
//     token); polling stops when nothing is drafting, and waits while the tab is hidden. Motion is CSS (--motion-* tokens only).
(function () {
  var pick = document.getElementById('cdr-pick');
  if (pick) {
    var boxes = Array.prototype.slice.call(pick.querySelectorAll('.cdr-box'));
    var go = document.getElementById('cdr-go');
    var count = document.getElementById('cdr-count');
    var max = parseInt(pick.getAttribute('data-max') || '0', 10);
    var sync = function () {
      var n = boxes.filter(function (b) { return b.checked; }).length;
      boxes.forEach(function (b) { b.disabled = !b.checked && n >= max; });
      if (go) go.disabled = n === 0 || max === 0;
      if (count) count.textContent = n + ' ticked' + (n >= max && max ? ' (the most for now)' : '');
    };
    pick.addEventListener('change', sync);
    sync();
  }

  var list = document.getElementById('cdr-list');
  if (!list || list.getAttribute('data-busy') !== '1') return;
  var every = 3000;
  var timer = null;

  function swap(fresh) {
    var rows = list.querySelector('.cdr-rows');
    var next = fresh.querySelector('.cdr-rows');
    var note = list.querySelector('#cdr-busy');
    var nextNote = fresh.querySelector('#cdr-busy');
    if (note && nextNote) { if (note.textContent !== nextNote.textContent) note.replaceWith(nextNote); }
    else if (note) note.remove();
    else if (nextNote) list.insertBefore(nextNote, list.firstChild);
    if (!rows || !next) return;
    var old = {};
    Array.prototype.forEach.call(rows.children, function (li) { old[li.id] = li; });
    var out = [];
    Array.prototype.forEach.call(next.children, function (li) {
      var was = old[li.id];
      if (was && was.outerHTML === li.outerHTML) { out.push(was); return; }
      li.classList.add('cdr-new');
      out.push(li);
    });
    rows.replaceChildren.apply(rows, out);
  }

  function poll() {
    timer = null;
    if (document.hidden) { schedule(); return; }
    fetch(location.pathname + '?part=1', { credentials: 'same-origin', headers: { Accept: 'text/html' } })
      .then(function (r) { return r.ok ? r.text() : Promise.reject(new Error('poll ' + r.status)); })
      .then(function (html) {
        var fresh = new DOMParser().parseFromString('<div>' + html + '</div>', 'text/html').getElementById('cdr-list');
        if (!fresh) return schedule();
        swap(fresh);
        list.setAttribute('data-busy', fresh.getAttribute('data-busy'));
        if (fresh.getAttribute('data-busy') === '1') schedule();
      })
      .catch(schedule);
  }
  function schedule() { if (!timer) timer = setTimeout(poll, every); }
  schedule();
})();
