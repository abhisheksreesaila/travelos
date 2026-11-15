// The community shelf (F-253, docs/design/creators-v2): a plank under each row of books (drawn from the layout boxes, so a book mid-animation does not move it), and the book you open
// grows out of its place: its cover is named for the cross-document view transition, which the book page's cover takes up (cv2.css, `@view-transition`).
(function () {
  var grid = document.querySelector('.cv .shelf');
  if (!grid) return;
  function planks() {
    Array.prototype.forEach.call(grid.querySelectorAll('.shelf-row-bg'), function (x) { x.remove(); });
    var rows = {};
    Array.prototype.forEach.call(grid.querySelectorAll('.bk'), function (bk) {
      var m = bk.querySelector('.mini'); if (!m) return;
      var k = bk.offsetTop; rows[k] = Math.max(rows[k] || 0, k + m.offsetTop + m.offsetHeight);
    });
    Object.keys(rows).forEach(function (k) { var d = document.createElement('div'); d.className = 'shelf-row-bg'; d.style.top = (rows[k] - 8) + 'px'; grid.insertBefore(d, grid.firstChild); });
  }
  requestAnimationFrame(planks);
  addEventListener('resize', planks);
  grid.addEventListener('click', function (e) {
    var a = e.target.closest('.bk-open'); if (!a) return;
    var m = a.querySelector('.mini'); if (m) m.style.viewTransitionName = 'book-cover';
  });
})();
