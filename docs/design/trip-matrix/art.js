/* GitAway place art (F-221 design): one drawn set in one style, ten places.
   Style rules: flat paper-cut layers (sky, far, mid, near, ground), one landmark silhouette, a sun (a moon in dark mode),
   at most eight tones per scene, no outlines, no text, no photos, no emoji. Each place has a day palette (light mode)
   and a night palette (dark mode); the weather layer (sun, cloud, rain, snow) is the same for every place and drifts slowly.
   Nothing is generated per visit: these are fixed drawings, one per place in places.py's table (build: one SVG file each).
   Use: <div class="pa" data-art="san-diego" data-wx="sun"></div>, then TMArt.mount(). Light skies keep ink text 7:1+ on their top third. */
(function () {
  const W = 480, H = 240;
  let uid = 0;

  // ---- palettes: sky1 (top), sky2 (horizon), sun, far, mid, near, water, foam, ground, ground2, line (structures), acc (landmark), leaf, snow
  const PAL = {
    'san-diego':   { day: ['#D9ECFA','#FCEBD6','#FFB547','#A9C3D9','#7FA6C4','#2F6B4F','#3F8FC2','#BFE0F2','#F0DDBA','#E2C594','#2B3A4A','#E4572E','#2F7A55','#FFFFFF'],
                     night:['#0A1830','#28365A','#F3EBD3','#1E2E48','#24395A','#0F2A1E','#123A5A','#2E6A93','#3A3328','#2C261E','#070D16','#B5452A','#14301F','#E8EEF6'] },
    'los-angeles': { day: ['#E2EEF8','#FBE3CF','#FF9F45','#C5CDD8','#C9A57E','#3E6B4A','#5B9BC6','#D5E8F4','#E9D3B0','#D6B98C','#33363F','#F2EEE6','#3B7550','#FFFFFF'],
                     night:['#0C1428','#3A2C4E','#F3EBD3','#252C40','#3A2E35','#13261A','#1A3550','#2D5577','#2C2620','#221D18','#05080F','#D8D2C4','#183022','#E8EEF6'] },
    'new-york':    { day: ['#DCE8F5','#F6E6D8','#FFB35C','#9EAFC4','#7E93AD','#4B5D73','#4F84B0','#C9DFF0','#B9C2AE','#98A38D','#3A4656','#5FA79A','#3E6E52','#FFFFFF'],
                     night:['#081226','#1F2C4A','#F3EBD3','#1B2740','#22314E','#121A28','#0F2C48','#2A5578','#1D2620','#161D18','#04070D','#3C7F73','#15281D','#E8EEF6'] },
    'lake-tahoe':  { day: ['#D6E9F7','#EEF5FA','#FFC861','#93AFC9','#6E8FB0','#2E5A44','#3D7FB0','#CFE5F4','#F5F8FB','#DCE6EF','#34404E','#FFFFFF','#2C5B43','#FFFFFF'],
                     night:['#081428','#1C2B48','#F3EBD3','#1B2A44','#203250','#0F2219','#0D2B47','#2A5A80','#8C9AAD','#6F7E92','#05080F','#E6EDF5','#0F2519','#DDE6F0'] },
    'orlando':     { day: ['#E6E3F6','#FCE1D2','#FF8F5A','#B9B6CF','#8E9DB8','#2F6B4F','#4B8EC0','#CFE4F3','#CDE4B8','#ABCB92','#323A48','#E9476B','#2F7A55','#FFFFFF'],
                     night:['#0E0F2A','#3B2448','#F3EBD3','#24233F','#2A3150','#0F2419','#121F45','#33508A','#1E2C1A','#172314','#05070F','#FF5C85','#14301F','#E8EEF6'] },
    'palm-springs':{ day: ['#DCEBF8','#FCE6CB','#FFAA3B','#C9A98B','#B48A6A','#4F7A55','#69A9D6','#D9EEF8','#F1D9B2','#E0BE8C','#3B3530','#F7F3EA','#5B8A5E','#FFFFFF'],
                     night:['#0C1430','#40294A','#F3EBD3','#3A2A2E','#2E2226','#16261A','#183A5A','#2D5F87','#33291F','#271F17','#06070C','#D8D2C4','#1A3020','#E8EEF6'] },
    'santa-barbara':{day: ['#DBEBF8','#FBEBDC','#FFB24E','#9DB7A8','#7FA08F','#3E6B4A','#3F8FC2','#C6E2F3','#C9DDAE','#A9C68B','#3A3A44','#C8562E','#3B7550','#FFFDF7'],
                     night:['#0A1630','#2A3456','#F3EBD3','#1C2C2A','#20302C','#12241A','#0F3150','#2A5A80','#1E2A1A','#172113','#05080F','#9C4426','#15281D','#D9D4C8'] },
    'orange-county':{day: ['#D8EAF8','#FCE9D9','#FFB84F','#B3C3CF','#9AB2C2','#3E6B4A','#3A8BC4','#C8E3F4','#F2E0BF','#E3C899','#2E3A48','#F25C54','#2F7A55','#FFFFFF'],
                     night:['#0A1530','#2A3256','#F3EBD3','#1D2A40','#22324A','#11231A','#0F3352','#2B5D84','#3A3328','#2C261E','#05080F','#FF6B63','#14301F','#E8EEF6'] },
    'honolulu':    { day: ['#D3ECF7','#F9EEDB','#FFB23F','#A7C7BE','#6E9C7F','#2E6E4C','#2A93C6','#BFE6F5','#F4E3C1','#E6CB98','#2C3A44','#F2A33A','#2F7A55','#FFFFFF'],
                     night:['#081A30','#273A58','#F3EBD3','#183028','#1B3A2C','#0E241A','#0C3552','#27648C','#3A3328','#2C261E','#05080F','#C27A20','#123020','#E8EEF6'] },
    'yosemite':    { day: ['#D9EAF7','#F2F2EC','#FFC35A','#A8B8C6','#8C9CAB','#2E5A44','#4A8DBA','#D3E8F5','#C7D9A8','#A6BF84','#3A4452','#FFFFFF','#2C5B43','#FFFFFF'],
                     night:['#081428','#1E2C46','#F3EBD3','#202C3C','#26323F','#0F2219','#0F2C47','#2A5A80','#1A2618','#141E12','#05080F','#E6EDF5','#0F2519','#DDE6F0'] },
  };
  const VARS = ['sky1','sky2','sun','far','mid','near','water','foam','ground','ground2','line','acc','leaf','snow'];

  const META = {
    'san-diego':     { name: 'San Diego',      kind: 'Beach',        line: 'Ocean Beach pier and a lifeguard tower' },
    'los-angeles':   { name: 'Los Angeles',    kind: 'City and hills', line: 'The observatory on the ridge, palms below' },
    'new-york':      { name: 'New York',       kind: 'City',         line: 'The Statue of Liberty and the skyline' },
    'lake-tahoe':    { name: 'Lake Tahoe',     kind: 'Snow and lake', line: 'Pines, snowy peaks and the lake' },
    'orlando':       { name: 'Orlando',        kind: 'Parks',        line: 'Lake Eola’s fountain and fireworks' },
    'palm-springs':  { name: 'Palm Springs',   kind: 'Desert',       line: 'San Jacinto, wind farms and a mid-century house' },
    'santa-barbara': { name: 'Santa Barbara',  kind: 'Coast town',   line: 'The mission’s twin bell towers' },
    'orange-county': { name: 'Orange County',  kind: 'Beach and parks', line: 'The harbour’s Ferris wheel and sails' },
    'honolulu':      { name: 'Honolulu',       kind: 'Island',       line: 'Diamond Head and the surf' },
    'yosemite':      { name: 'Yosemite',       kind: 'Hike',         line: 'Half Dome and the falls' },
  };

  // ---- shared drawing helpers (one style for every scene)
  const P = (d, c) => `<path class="${c}" d="${d}"/>`;
  const S = (d, c, w = 3) => `<path class="${c}s" d="${d}" stroke-width="${w}" fill="none" stroke-linecap="round"/>`;
  function palm(x, y, h, lean = 1, c = 'lf') {
    const tx = x + lean * h * 0.22, ty = y - h;
    let s = `<path class="lns" d="M${x} ${y} C${x + lean * 2} ${y - h * .45} ${tx - lean * 4} ${ty + h * .3} ${tx} ${ty}" stroke-width="${Math.max(2.5, h / 22)}" fill="none" stroke-linecap="round"/>`;
    const f = h * 0.34;
    [[-1, .15], [-1, -.45], [1, -.4], [1, .2], [-.15, -1]].forEach(([dx, dy]) => {
      const ex = tx + dx * f, ey = ty + dy * f * .55 + f * .32;
      s += `<path class="${c}" d="M${tx} ${ty} Q${tx + dx * f * .55} ${ty + dy * f * .55 - f * .2} ${ex} ${ey} Q${tx + dx * f * .45} ${ty + dy * f * .3 + f * .02} ${tx} ${ty}Z"/>`;
    });
    return s;
  }
  function pine(x, y, h, c = 'lf') {
    const w = h * .42;
    return `<rect class="ln" x="${x - 1.5}" y="${y - h * .16}" width="3" height="${h * .16}"/>` +
      [0, 1, 2].map(i => { const top = y - h + i * h * .24, bot = y - h * .14 - (2 - i) * h * .14, ww = w * (.55 + i * .22);
        return `<path class="${c}" d="M${x} ${top} L${x + ww} ${bot} L${x - ww} ${bot}Z"/>`; }).join('');
  }
  function towers(x0, base, list, c) { let s = '', x = x0; list.forEach(([w, h]) => { s += `<rect class="${c}" x="${x}" y="${base - h}" width="${w}" height="${h}"/>`; x += w + 2; }); return s; }
  function waves(y, c = 'fo') { return [[18, 0, 54], [110, 8, 34], [196, 3, 48], [300, 10, 40], [398, 5, 58]].map(([x, dy, w]) => S(`M${x} ${y + dy}h${w}`, c, 2.5)).join(''); }

  // ---- the weather layer: clouds drift (sixty seconds a crossing), rain falls, snow falls slower; the sun hides under rain and snow
  function cloud(x, y, s) { return `<g transform="translate(${x} ${y}) scale(${s})"><circle cx="0" cy="0" r="12"/><circle cx="14" cy="-6" r="15"/><circle cx="30" cy="0" r="11"/><rect x="-6" y="0" width="42" height="11" rx="5.5"/></g>`; }
  function weather() {
    let rain = '', snow = '';
    for (let i = 0; i < 36; i++) { const x = (i * 53) % W, y = (i * 37) % 150; rain += `<path d="M${x} ${y}l-5 12"/>`; snow += `<circle cx="${(i * 47) % W}" cy="${(i * 29) % 170}" r="${1.6 + (i % 3) * .5}"/>`; }
    return `<g class="wx-cl">${cloud(60, 52, 1.1)}${cloud(250, 34, .8)}${cloud(380, 62, 1.25)}</g>` +
      `<g class="wx-cl2">${cloud(150, 70, 1.4)}${cloud(330, 40, 1.6)}${cloud(10, 30, 1.2)}</g>` +
      `<g class="wx-rn">${rain}</g><g class="wx-sn">${snow}</g>`;
  }

  // ---- the ten scenes (drawn on 480 x 240; the horizon is near y 150)
  const SCENES = {
    'san-diego': () => ({ sun: [362, 112, 26], body:
      P('M0 140 C60 124 122 126 172 137 C204 130 232 133 262 142 L262 152 L0 152Z', 'fa') +
      P('M296 146 L480 143 L480 152 L296 152Z', 'fa') +
      `<rect class="wa" x="0" y="150" width="${W}" height="44"/>` + waves(160) +
      `<rect class="ln" x="250" y="135" width="230" height="5"/>` +
      Array.from({ length: 14 }, (_, i) => S(`M${258 + i * 16} 140 V${170 - i * .3}`, 'ln', 2.4)).join('') +
      `<rect class="ac" x="266" y="123" width="20" height="12" rx="1"/>` + P('M262 124 L276 116 L290 124Z', 'ln') +
      P('M0 192 C120 180 260 184 480 172 L480 240 L0 240Z', 'gr') + P('M0 214 C140 204 300 210 480 200 L480 240 L0 240Z', 'g2') +
      S('M112 210 L118 188 M142 210 L136 188 M118 196 H136', 'ln', 2.6) +
      `<rect class="ac" x="108" y="168" width="36" height="20" rx="2"/>` + P('M103 169 L126 157 L149 169Z', 'ln') + `<rect class="sn2" x="116" y="173" width="20" height="7" rx="1"/>` +
      palm(44, 214, 96, 1) + palm(452, 206, 70, -1) +
      `<rect class="ac" x="196" y="196" width="5" height="22" rx="2.5" transform="rotate(-12 198 207)"/>` }),
    'los-angeles': () => ({ sun: [108, 98, 24], body:
      towers(26, 152, [[10, 36], [14, 58], [9, 44], [16, 72], [11, 50], [13, 62], [8, 30]], 'fa') +
      P('M0 162 C80 142 140 130 200 118 C250 100 300 96 340 104 C392 112 432 124 480 132 L480 186 L0 186Z', 'mi') +
      `<rect class="ac" x="268" y="90" width="64" height="10" rx="1"/>` + P('M287 90 a13 13 0 0 1 26 0Z', 'ln') +
      P('M268 90 a6 6 0 0 1 12 0Z', 'ln') + P('M320 90 a6 6 0 0 1 12 0Z', 'ln') + `<rect class="ln" x="298" y="72" width="4" height="6"/>` +
      P('M0 192 C120 178 300 186 480 178 L480 240 L0 240Z', 'ne') + `<rect class="g2" x="0" y="214" width="${W}" height="26"/>` +
      palm(52, 214, 132, .2) + palm(84, 214, 112, -.1) + palm(392, 214, 124, .15) + palm(430, 214, 140, -.05) + palm(464, 214, 104, .1) }),
    'new-york': () => ({ sun: [404, 72, 20], body:
      towers(196, 152, [[12, 40], [16, 66], [10, 52], [14, 84], [18, 58], [12, 46], [16, 76], [10, 38], [14, 62], [20, 54], [12, 70], [16, 44], [14, 34]], 'fa') +
      `<rect class="mi" x="318" y="84" width="22" height="68"/><rect class="mi" x="322" y="74" width="14" height="10"/><rect class="mi" x="326" y="66" width="6" height="8"/>` + S('M329 66 V46', 'mi', 2) +
      P('M396 152 L402 62 L414 62 L420 152Z', 'mi') + S('M408 62 V38', 'mi', 2) +
      `<rect class="wa" x="0" y="150" width="${W}" height="90"/>` + waves(170) + waves(196) +
      P('M30 200 L182 200 L170 188 L44 188Z', 'gr') + P('M68 188 L144 188 L136 178 L76 178Z', 'g2') +
      `<rect class="g2" x="90" y="140" width="32" height="38"/>` + `<rect class="gr" x="86" y="136" width="40" height="5"/>` +
      P('M96 136 L100 98 C102 91 112 91 114 98 L118 136Z', 'ac') + `<circle class="ac" cx="107" cy="88" r="5.4"/>` +
      S('M101 84 l-4 -6 M104.5 82 l-1 -7.5 M109.5 82 l1 -7.5 M113 84 l4 -6', 'ac', 1.8) +
      P('M110 99 L117 70 L121 71 L115 101Z', 'ac') + `<rect class="ac" x="115" y="63" width="7" height="8" rx="1"/>` +
      `<ellipse class="sn-disc" cx="118.5" cy="59" rx="3.4" ry="5"/>` + `<rect class="ac" x="94" y="104" width="6" height="13" rx="1"/>` }),
    'lake-tahoe': () => ({ sun: [150, 80, 20], body:
      P('M0 142 L50 98 L80 118 L122 76 L170 124 L212 92 L258 130 L302 84 L352 120 L402 94 L442 118 L480 104 L480 152 L0 152Z', 'fa') +
      [[50, 98], [122, 76], [212, 92], [302, 84], [402, 94]].map(([x, y]) => P(`M${x} ${y} L${x - 13} ${y + 14} L${x - 5} ${y + 11} L${x + 1} ${y + 16} L${x + 7} ${y + 11} L${x + 13} ${y + 13}Z`, 'sn')).join('') +
      P('M0 152 L70 128 L120 146 L190 122 L250 150Z', 'mi') +
      `<rect class="wa" x="0" y="150" width="${W}" height="40"/>` + waves(162) +
      P('M0 190 C120 178 300 186 480 176 L480 240 L0 240Z', 'gr') + P('M0 218 C160 208 320 214 480 206 L480 240 L0 240Z', 'g2') +
      pine(30, 214, 92) + pine(64, 206, 70) + pine(96, 216, 54) + pine(392, 210, 78) + pine(428, 216, 104) + pine(462, 206, 66) }),
    'orlando': () => ({ sun: [398, 132, 20], body:
      [[118, 62, 'ac'], [372, 50, 'sn'], [300, 86, 'ac']].map(([x, y, c], k) => `<g class="fw">` + Array.from({ length: 12 }, (_, i) => { const a = i * Math.PI / 6, r1 = 6 + k, r2 = 18 + k * 3;
        return S(`M${(x + Math.cos(a) * r1).toFixed(1)} ${(y + Math.sin(a) * r1).toFixed(1)} L${(x + Math.cos(a) * r2).toFixed(1)} ${(y + Math.sin(a) * r2).toFixed(1)}`, c, 2); }).join('') + `</g>`).join('') +
      towers(300, 152, [[10, 30], [14, 44], [9, 26], [16, 52], [11, 36], [12, 24]], 'fa') + towers(30, 152, [[12, 22], [10, 34], [14, 26]], 'fa') +
      `<rect class="wa" x="0" y="150" width="${W}" height="56"/>` + waves(176) +
      `<ellipse class="ln" cx="240" cy="170" rx="46" ry="5"/>` + P('M204 168 Q240 158 276 168Z', 'sn') + P('M218 160 Q240 146 262 160 L254 162 L226 162Z', 'sn') + P('M228 150 Q240 140 252 150 L246 152 L234 152Z', 'sn') + `<rect class="sn" x="237" y="136" width="6" height="16" rx="2"/>` +
      S('M240 134 V86', 'fo', 4) + S('M240 104 C226 96 212 104 206 122 M240 104 C254 96 268 104 274 122 M240 120 C230 116 222 122 218 140 M240 120 C250 116 258 122 262 140', 'fo', 2.2) + `<circle class="sn" cx="240" cy="84" r="3"/>` +
      P('M0 204 C120 196 300 202 480 192 L480 240 L0 240Z', 'gr') + P('M0 224 C160 216 320 222 480 214 L480 240 L0 240Z', 'g2') +
      palm(40, 222, 100, .6) + palm(78, 222, 76, -.4) + palm(418, 218, 110, -.5) + palm(454, 220, 80, .3) }),
    'palm-springs': () => ({ sun: [300, 70, 26], body:
      P('M0 152 L58 112 L120 62 L170 84 L230 50 L300 104 L360 92 L420 122 L480 114 L480 152Z', 'fa') +
      P('M120 62 L150 100 L132 120 L170 84Z M230 50 L250 96 L224 118 L210 86Z', 'mi') +
      [[372, 128], [410, 134], [448, 124]].map(([x, y], i) => S(`M${x} ${y} V${y - 46}`, 'sn', 2.2) + `<g class="tb" style="transform-origin:${x}px ${y - 46}px;animation-delay:-${i * 2}s">` +
        [0, 120, 240].map(a => S(`M${x} ${y - 46} l${(Math.cos((a - 90) * Math.PI / 180) * 16).toFixed(1)} ${(Math.sin((a - 90) * Math.PI / 180) * 16).toFixed(1)}`, 'sn', 2)).join('') + `</g>`).join('') +
      P('M0 166 C120 150 300 160 480 150 L480 240 L0 240Z', 'gr') + P('M0 214 C140 202 320 210 480 200 L480 240 L0 240Z', 'g2') +
      `<rect class="ac" x="66" y="170" width="96" height="26"/>` + P('M56 170 L114 164 L172 170 L172 174 L56 174Z', 'ln') + `<rect class="wa" x="80" y="178" width="40" height="12"/><rect class="ln" x="130" y="178" width="12" height="18"/>` +
      palm(206, 214, 128, .05) + palm(232, 214, 106, -.08) +
      [[34, 222], [300, 220], [438, 218]].map(([x, y]) => [-.9, -.45, 0, .45, .9].map(a => S(`M${x} ${y} l${(Math.sin(a) * 18).toFixed(1)} ${(-Math.cos(a) * 18).toFixed(1)}`, 'lf', 3.2)).join('')).join('') }),
    'santa-barbara': () => ({ sun: [404, 92, 22], body:
      P('M0 122 C80 98 160 106 240 96 C320 88 400 102 480 94 L480 152 L0 152Z', 'fa') +
      `<rect class="wa" x="0" y="150" width="${W}" height="28"/>` + waves(160) +
      P('M0 176 C120 170 300 174 480 168 L480 240 L0 240Z', 'gr') + P('M0 220 C160 212 320 218 480 210 L480 240 L0 240Z', 'g2') +
      `<rect class="sn" x="22" y="140" width="66" height="34"/><rect class="ac" x="18" y="134" width="74" height="7"/>` +
      [30, 46, 62, 78].map(x => P(`M${x - 5} 174 V158 a5 5 0 0 1 10 0 V174Z`, 'ln')).join('') +
      `<rect class="sn" x="90" y="98" width="28" height="76"/><rect class="sn" x="160" y="98" width="28" height="76"/>` +
      P('M90 98 a14 10 0 0 1 28 0Z M160 98 a14 10 0 0 1 28 0Z', 'ac') + `<rect class="ln" x="99" y="106" width="10" height="12" rx="5"/><rect class="ln" x="169" y="106" width="10" height="12" rx="5"/>` +
      `<rect class="sn" x="118" y="116" width="42" height="58"/>` + P('M112 117 L139 96 L166 117Z', 'sn') + P('M132 174 V152 a7 7 0 0 1 14 0 V174Z', 'ln') + `<circle class="ln" cx="139" cy="132" r="5"/>` +
      palm(420, 214, 120, -.2) + palm(456, 214, 92, .1) }),
    'orange-county': () => ({ sun: [100, 84, 22], body:
      P('M0 134 C100 118 200 124 300 116 C380 112 430 122 480 120 L480 152 L0 152Z', 'fa') +
      `<rect class="wa" x="0" y="150" width="${W}" height="62"/>` + waves(186) +
      `<circle class="lns" cx="346" cy="118" r="38" fill="none" stroke-width="2.6"/>` +
      Array.from({ length: 8 }, (_, i) => { const a = i * Math.PI / 4; return S(`M346 118 l${(Math.cos(a) * 38).toFixed(1)} ${(Math.sin(a) * 38).toFixed(1)}`, 'ln', 1.4); }).join('') +
      Array.from({ length: 8 }, (_, i) => { const a = i * Math.PI / 4 + .2; return `<rect class="ac" x="${(346 + Math.cos(a) * 38 - 4).toFixed(1)}" y="${(118 + Math.sin(a) * 38 - 1).toFixed(1)}" width="8" height="8" rx="2"/>`; }).join('') +
      S('M346 118 L326 166 M346 118 L366 166', 'ln', 3) + `<rect class="ln" x="290" y="164" width="120" height="6"/>` +
      [[118, 182, 1], [196, 190, .8]].map(([x, y, s]) => P(`M${x - 22 * s} ${y} L${x + 24 * s} ${y} L${x + 16 * s} ${y + 9 * s} L${x - 16 * s} ${y + 9 * s}Z`, 'sn') + S(`M${x} ${y} V${y - 50 * s}`, 'ln', 1.8) +
        P(`M${x + 2} ${y - 48 * s} L${x + 2} ${y - 4} L${x + 30 * s} ${y - 4}Z`, 'sn') + P(`M${x - 2} ${y - 40 * s} L${x - 2} ${y - 4} L${x - 18 * s} ${y - 4}Z`, 'ac')).join('') +
      P('M0 212 C140 206 320 210 480 202 L480 240 L0 240Z', 'gr') + palm(450, 226, 96, -.2) }),
    'honolulu': () => ({ sun: [128, 76, 24], body:
      P('M0 136 C60 122 120 124 190 134 L190 152 L0 152Z', 'fa') +
      P('M180 152 C214 118 252 94 300 90 C330 88 352 96 382 110 C412 122 444 134 480 138 L480 152Z', 'mi') +
      S('M262 100 C280 110 310 108 330 98 M300 92 C300 104 304 118 312 130', 'ne', 2) +
      `<rect class="wa" x="0" y="150" width="${W}" height="54"/>` + waves(184) +
      P('M20 166 C60 146 108 146 132 162 C114 156 96 158 86 170 C70 172 44 172 20 166Z', 'fo') +
      P('M0 202 C120 194 300 200 480 190 L480 240 L0 240Z', 'gr') + P('M0 224 C160 216 320 222 480 214 L480 240 L0 240Z', 'g2') +
      `<rect class="ac" x="168" y="174" width="9" height="40" rx="4.5" transform="rotate(10 172 194)"/>` +
      palm(408, 220, 130, -.9) + palm(446, 222, 98, -.6) }),
    'yosemite': () => ({ sun: [78, 70, 20], body:
      P('M0 152 L0 58 C42 54 92 62 114 84 L132 152Z', 'mi') +
      P('M188 152 C192 110 210 76 242 60 C268 48 302 48 320 58 L324 62 L324 152Z', 'fa') + P('M320 58 L324 62 L324 152 L314 152 C318 120 318 88 320 58Z', 'mi') +
      P('M322 152 L360 112 L420 128 L480 108 L480 152Z', 'mi') +
      S('M106 80 C108 100 108 128 110 152', 'sn', 4) + S('M110 92 C111 110 112 132 113 152', 'fo', 1.6) +
      P('M0 152 L480 152 L480 240 L0 240Z', 'gr') + S('M0 196 C80 186 150 206 240 194 C320 184 400 200 480 190', 'wa', 7) +
      P('M0 226 C160 218 320 224 480 216 L480 240 L0 240Z', 'g2') +
      pine(30, 216, 88) + pine(66, 208, 60) + pine(250, 214, 50) + pine(384, 212, 76) + pine(420, 218, 98) + pine(456, 208, 62) }),
  };

  function svg(id, opts = {}) {
    const sc = SCENES[id]; if (!sc) return '';
    const { sun, body } = sc(); const g = 'pa' + (++uid);
    return `<svg class="pa-svg" viewBox="0 0 ${W} ${H}" preserveAspectRatio="${opts.fit || 'xMidYMax slice'}" role="img" aria-label="${META[id].name}: ${META[id].line}">` +
      `<defs><linearGradient id="${g}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" style="stop-color:var(--sky1)"/><stop offset=".72" style="stop-color:var(--sky2)"/></linearGradient></defs>` +
      `<rect width="${W}" height="${H}" fill="url(#${g})"/><circle class="sn-disc" cx="${sun[0]}" cy="${sun[1]}" r="${sun[2]}"/>` +
      `<g class="wx">${weather()}</g>${body}</svg>`;
  }

  // ---- CSS: palettes as variables (light = day, dark = night), the classes the scenes use, the weather states and their slow drift
  function css() {
    const block = (k, i) => `.pa[data-art="${k}"]{${VARS.map((v, j) => `--${v}:${PAL[k][i][j]}`).join(';')}}`;
    const day = Object.keys(PAL).map(k => block(k, 'day')).join('\n');
    const night = Object.keys(PAL).map(k => block(k, 'night')).join('\n');
    return `
.pa{position:relative;overflow:hidden;background:var(--sky2)}
.pa-svg{position:absolute;inset:0;width:100%;height:100%;display:block}
.pa .fa{fill:var(--far)}.pa .mi{fill:var(--mid)}.pa .ne{fill:var(--near)}.pa .wa{fill:var(--water)}.pa .gr{fill:var(--ground)}.pa .g2{fill:var(--ground2)}
.pa .ln{fill:var(--line)}.pa .ac{fill:var(--acc)}.pa .lf{fill:var(--leaf)}.pa .sn,.pa .sn2{fill:var(--snow)}
.pa .fos,.pa .fo{stroke:var(--foam);fill:none}.pa path.fo{fill:var(--foam);stroke:none}.pa .lns{stroke:var(--line)}.pa .acs{stroke:var(--acc)}.pa .sns{stroke:var(--snow)}.pa .lfs{stroke:var(--leaf)}.pa .mis{stroke:var(--mid)}.pa .nes{stroke:var(--near)}.pa .was{stroke:var(--water)}
.pa .sn-disc{fill:var(--sun);transition:opacity .6s}
.pa .wx g{fill:#fff;opacity:0;transition:opacity .8s}
.pa .wx-rn{stroke:var(--water);stroke-width:2;stroke-linecap:round;fill:none}
.pa .wx-sn{fill:var(--snow)}
.pa[data-wx="sun"] .wx-cl{opacity:.75}
.pa[data-wx="cloud"] .wx-cl,.pa[data-wx="cloud"] .wx-cl2{opacity:.92}.pa[data-wx="cloud"] .sn-disc{opacity:.45}
.pa[data-wx="rain"] .wx-cl,.pa[data-wx="rain"] .wx-cl2{opacity:1;fill:#C9D3DE}.pa[data-wx="rain"] .wx-rn{opacity:.75}.pa[data-wx="rain"] .sn-disc{opacity:0}
.pa[data-wx="snow"] .wx-cl,.pa[data-wx="snow"] .wx-cl2{opacity:.95;fill:#E6ECF3}.pa[data-wx="snow"] .wx-sn{opacity:.95}.pa[data-wx="snow"] .sn-disc{opacity:0}
.pa .wx-cl{animation:pa-drift 70s linear infinite}.pa .wx-cl2{animation:pa-drift 95s linear infinite}
.pa .wx-rn{animation:pa-rain .9s linear infinite}.pa .wx-sn{animation:pa-snow 7s linear infinite}
.pa .tb{animation:pa-spin 9s linear infinite}.pa .fw{animation:pa-burst 4.5s ease-out infinite;transform-box:fill-box;transform-origin:center}
.pa .fw:nth-of-type(2){animation-delay:-1.5s}.pa .fw:nth-of-type(3){animation-delay:-3s}
@keyframes pa-drift{from{transform:translateX(-30px)}50%{transform:translateX(30px)}to{transform:translateX(-30px)}}
@keyframes pa-rain{from{transform:translateY(-12px)}to{transform:translateY(12px)}}
@keyframes pa-snow{from{transform:translateY(-20px)}to{transform:translateY(20px)}}
@keyframes pa-spin{to{transform:rotate(360deg)}}
@keyframes pa-burst{0%{opacity:0;transform:scale(.5)}15%{opacity:1}60%{opacity:.85;transform:scale(1)}100%{opacity:0;transform:scale(1.05)}}
.pa.still *,.pa.still{animation:none!important}
@media (prefers-reduced-motion:reduce){.pa *{animation:none!important}}
${day}
:root[data-mode="dark"] ${night.replace(/\n/g, '\n:root[data-mode="dark"] ')}
:root[data-mode="dark"] .pa .wx g{fill:#3A4660}
@media (prefers-color-scheme:dark){:root:not([data-mode="light"]) ${night.replace(/\n/g, '\n:root:not([data-mode="light"]) ')}
:root:not([data-mode="light"]) .pa .wx g{fill:#3A4660}}
`;
  }

  function mount(root = document) {
    root.querySelectorAll('[data-art]').forEach(el => {
      if (el.dataset.done) return; el.dataset.done = 1; el.classList.add('pa');
      el.insertAdjacentHTML('afterbegin', svg(el.dataset.art, { fit: el.dataset.fit }));
    });
  }
  const st = document.createElement('style'); st.textContent = css(); document.head.appendChild(st);
  window.TMArt = { svg, mount, META, PLACES: Object.keys(SCENES) };
})();
