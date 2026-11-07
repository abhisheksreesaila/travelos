// Story pieces concepts B and C share (A grew its own copies first): in-world labels, the plan's widgets laid out
// at a chapter's endpoint and pinned to the world with dashed leaders, and postcards flying to the next family.
import { Vector3 } from 'three';
import { Spring, clamp, smooth } from './core.js';

const anchorsEl = () => document.querySelector('.anchors');
export const dot = (c) => `<i style="background:#${c.toString(16).padStart(6, '0')}"></i>`;
export function label(S, html, pos, opts = {}, cls = 'lbl') {
  const el = document.createElement('div'); el.className = cls; el.innerHTML = html; anchorsEl().appendChild(el);
  S.anchor(el, pos, opts); return el;
}

// items: [{ sel, at: [x, y] screen fraction at the chapter endpoint, th: local threshold, to: () => Vector3 of its place }]
export function widgets(S, chapter, items, isPhone) {
  const svgNS = 'http://www.w3.org/2000/svg', layer = anchorsEl();
  const svg = document.createElementNS(svgNS, 'svg'); svg.setAttribute('class', 'leaders'); layer.prepend(svg);
  const pops = items.map((w) => {
    const src = document.querySelector(`[data-chapter="${chapter}"] ${w.sel}`); if (!src) return null;
    const el = src.cloneNode(true); el.setAttribute('aria-hidden', 'true'); layer.appendChild(el);
    const sp = new Spring(0, 260, 16), tickets = /flight|stay|car|tix/.test(w.sel), pos = new Vector3();
    const line = document.createElementNS(svgNS, 'path'); svg.appendChild(line);
    S.anchor(el, pos, { ax: -50, ay: -50, show: () => (isPhone() ? 0 : clamp(sp.v * 4, 0, 1)), scale: () => (tickets ? 1.25 - 0.33 * sp.v : 0.74 + 0.18 * sp.v), rot: () => (tickets ? -6 * (1 - sp.v) - 1.2 : 0) });
    return { w, el, sp, pos, line };
  }).filter(Boolean);
  let need = true; addEventListener('resize', () => (need = true));
  const a = new Vector3(), b = new Vector3();
  return {
    relayout() { need = true; },
    update(st, dt) {
      if (need) {
        const c = S.cameraAt(chapter), ray = new Vector3(), o = c.position;
        pops.forEach((p) => { ray.set(p.w.at[0] * 2 - 1, -(p.w.at[1] * 2 - 1), 0.5).unproject(c).sub(o).normalize(); p.pos.copy(o).addScaledVector(ray, ((p.w.y ?? 3) - o.y) / ray.y); });
        need = false;
      }
      const [vw, vh] = S.size();
      pops.forEach((p) => {
        p.sp.t = st.chapter === chapter && st.local >= p.w.th ? 1 : 0; p.sp.step(dt);
        p.el.classList.toggle('in', p.sp.t === 1 && p.sp.v > 0.6);
        const o = isPhone() ? 0 : clamp(p.sp.v * 4, 0, 1);
        if (!p.w.to || o < 0.02) { p.line.setAttribute('opacity', 0); return; }
        a.copy(p.pos).project(S.camera); b.copy(p.w.to()).project(S.camera);
        p.line.setAttribute('d', `M${((a.x * 0.5 + 0.5) * vw).toFixed(1)} ${((-a.y * 0.5 + 0.5) * vh).toFixed(1)} L${((b.x * 0.5 + 0.5) * vw).toFixed(1)} ${((-b.y * 0.5 + 0.5) * vh).toFixed(1)}`);
        p.line.setAttribute('opacity', o.toFixed(2));
      });
    },
  };
}

// cards fly from `from` to `to` on staggered arcs as k goes 0 → 1
export function flyCards(cards, from, to, k, time, camera, size = 1.15) {
  cards.userData.cards.forEach((card, i) => {
    const t = clamp((k - i * 0.07) / 0.42, 0, 1);
    card.visible = t > 0 && t < 1;
    if (!card.visible) return;
    const e = smooth(0, 1, t);
    card.position.lerpVectors(from, to, e); card.position.y += Math.sin(e * Math.PI) * (3.2 + i * 0.5); card.position.x += Math.sin(e * Math.PI) * (i - 1.5) * 0.9;
    card.lookAt(camera.position); card.rotateZ(Math.sin(time * 2 + i) * 0.18 + (i - 1.5) * 0.1);
    card.scale.setScalar(size * (1 - smooth(0.85, 1, t)) + 0.05);
  });
}
