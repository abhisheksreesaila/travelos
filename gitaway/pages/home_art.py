"""The four landing feature illustrations (F-060): small inline SVGs whose parts the page CSS moves on hover and focus.

Decorative (aria-hidden by their wrapper); the colours are the design tokens' hex values."""

PANES = (
    '<svg viewBox="0 0 240 110"><g class="p1"><rect x="30" y="22" width="56" height="66" rx="10" fill="#FFFFFF"/><rect x="38" y="32" width="40" height="8" rx="4" fill="#5AB0FF"/><rect x="38" y="46" width="28" height="6" rx="3" fill="#F2ECE3"/><rect x="38" y="58" width="34" height="6" rx="3" fill="#F2ECE3"/></g><g class="p2"><rect x="92" y="22" width="56" height="66" rx="10" fill="#FFFFFF"/><rect x="100" y="32" width="40" height="8" rx="4" fill="#C3B2FF"/><rect x="100" y="46" width="30" height="6" rx="3" fill="#F2ECE3"/><rect x="100" y="58" width="24" height="6" rx="3" fill="#F2ECE3"/></g><g class="p3"><rect x="154" y="22" width="56" height="66" rx="10" fill="#FFFFFF"/><circle cx="182" cy="46" r="11" fill="#FFC93C"/><rect x="164" y="64" width="36" height="6" rx="3" fill="#F2ECE3"/></g></svg>'
)

TOTAL = (
    '<svg viewBox="0 0 240 110"><g class="c c1"><rect x="40" y="30" width="44" height="30" rx="9" fill="#DDEEFF"/><path d="M52 47l10-3 8-8 3 1-4 9 6 1 2-2h2l-1 4 1 4h-2l-2-2-6 1 4 9-3 1-8-8-10-3z" fill="#1B6FC9" transform="translate(-2,-6) scale(.9)"/></g><g class="c c2"><rect x="98" y="30" width="44" height="30" rx="9" fill="#ECE4FF"/><path d="M108 52v-12M108 46h22a4 4 0 0 1 4 4v2M108 52h26M112 44a2.5 2.5 0 1 0 0-.01" stroke="#6A4FD6" stroke-width="2.6" fill="none" stroke-linecap="round"/></g><g class="c c3"><rect x="156" y="30" width="44" height="30" rx="9" fill="#FFF1C2"/><path d="M166 50l3-8h22l3 8v4h-28zM170 54v3M190 54v3" stroke="#8A6200" stroke-width="2.6" fill="none" stroke-linecap="round" stroke-linejoin="round"/></g><g class="sum"><rect x="70" y="66" width="100" height="32" rx="16" fill="#1E1A2E"/><text x="120" y="87" text-anchor="middle" font-family="Bricolage Grotesque, sans-serif" font-weight="800" font-size="16" fill="#FFFFFF">$1,912 total</text></g></svg>'
)

TOGETHER = (
    '<svg viewBox="0 0 240 110"><rect x="86" y="18" width="68" height="78" rx="12" fill="#FFFFFF"/><rect x="86" y="18" width="68" height="16" rx="8" fill="#48D1A0"/><g class="blk b1"><rect x="94" y="42" width="52" height="18" rx="6" fill="#FFF1C2"/></g><g class="blk b2"><rect x="94" y="66" width="52" height="22" rx="6" fill="#FFE3F1"/></g><g class="ppl1"><circle cx="58" cy="50" r="12" fill="#C3B2FF"/><path d="M38 96c0-14 9-24 20-24s20 10 20 24z" fill="#C3B2FF"/></g><g class="ppl2"><circle cx="182" cy="50" r="12" fill="#FF8A63"/><path d="M162 96c0-14 9-24 20-24s20 10 20 24z" fill="#FF8A63"/></g><g class="heart"><path d="M120 14c-3-5-10-3-10 2 0 4 10 9 10 9s10-5 10-9c0-5-7-7-10-2z" fill="#FF7352"/></g></svg>'
)

FORK = (
    '<svg viewBox="0 0 240 110"><path d="M24 70 H216" stroke="#6A4FD6" stroke-width="5" stroke-linecap="round" fill="none"/><circle cx="40" cy="70" r="8" fill="#6A4FD6"/><circle cx="92" cy="70" r="8" fill="#6A4FD6"/><circle cx="144" cy="70" r="8" fill="#FFFFFF" stroke="#6A4FD6" stroke-width="4"/><circle cx="200" cy="70" r="8" fill="#FFFFFF" stroke="#6A4FD6" stroke-width="4"/><path class="branch" d="M92 70 C 112 70, 112 32, 136 32 H 200" stroke="#FF7352" stroke-width="5" stroke-linecap="round" fill="none"/><g class="dot2"><circle cx="200" cy="32" r="10" fill="#FF7352"/><path d="M195 32l4 4 7-8" stroke="#FFFFFF" stroke-width="2.6" fill="none" stroke-linecap="round" stroke-linejoin="round"/></g></svg>'
)
