# GitAway scroll prototype — Take a trip. Leave a trail.

A local, standalone prototype of the approved watercolor direction. The question is how the story unfolds through scrolling, with the product argument leading and the travel scenes giving it room to breathe.

Open **index.html** directly. Its images, styles, icons and scripts are embedded; no server or network is needed. Links to Start a trip and creator import open the existing GitAway website.

## The narrative

1. **The problem:** booking a flight is one decision; understanding the whole trip usually means piecing together partial information.
2. **The context:** a Los Angeles → Tahoe sample puts the journey, stay, getting around, weather, nearby trails and budget together before handing booking to a partner.
3. **The plan comes along:** the shared day plan, directions, bookings and family notes continue to help during the holiday. Scrolling changes the sample to a slower morning.
4. **Be there:** a longer winter passage moves through the pines, sweeps across the lake, dissolves into the cabin, and pulls back to the story.
5. **Home again:** a trip is more than the photos you brought back. Its useful plan already exists.
6. **Leave a trail:** scrolling changes the private example into an anonymous, reusable trail. The public preview uses a landscape rather than a character photo.
7. **Someone starts further ahead:** Rosa and Tomás use the trail as a starting point, then adapt the season and pace.
8. **Their summer:** follow the shoreline, linger over the clear water, return to the couple, then pull back to the page.
9. **A world built together:** travellers, bloggers and creators contribute first-hand experience that becomes usable plans.
10. **Your turn:** Take a trip. Leave a trail.

## Interaction

- Native scrolling owns the pace. There is no autoplay, video player, timer, scroll snapping or intercepted wheel gesture.
- Practical chapters keep the words and a small product demonstration readable. The winter passage spans 6.2 viewport heights and summer 5.6, with several camera movements inside each. They open from an 84% framed view, stay fully open through most of the passage, then return completely to the framed view. Reversing the scroll reverses the camera and the illustrated dissolve.
- Three named moments in each passage show where you are and let you jump ahead or return. They have 48px targets and work with the keyboard. The main Next chapter control still skips the whole passage.
- Snow, summer light motes, water distortion, and a subtle mouse look follow the same depth camera. They render on input and stop while idle; no perpetual particle loop runs in the background. Touch keeps native scrolling, with no drag or wheel interception.
- The planning and privacy demonstrations progress with the scroll and reverse when the visitor scrolls back. A deliberate button click takes control of that demonstration.
- Calm view and the system's reduced-motion preference keep a static, readable sequence. No WebGL context is created under reduced motion.
- A small progress rail offers keyboard-accessible chapter jumps; a skip link goes directly to the closing action.
- Both lake scenes use native WebGL depth meshes textured with the approved watercolor art. The cabin is a second illustrated depth layer. These are depth/parallax scenes, not a complete geographic terrain model. If WebGL is unavailable or lost, the long passage collapses into a short readable poster section.
- Rendering is event-driven: the page requests frames on scrolling, resizing or image loading, and stops while idle.

## Scope

This is a design prototype with an illustrated sample trip. There are no reservation, price, sharing, account or payment writes. The application's landing page and production deployment are unchanged. The anonymity controls show the intended public presentation; integration must use and verify the application's real publication/privacy behavior.

The visual source is the user's approved watercolor storyboard and cast in ../story/sol-v2, with the project's existing SVG icons and kind colors. No new image generation was needed.

The follow-up reads the local Claude `designer` skill, `~/.claude/design-taste.md`, OMXqua's language and font guidance, and the local frontend-design guidance. It preserves the approved watercolor marketing direction. Fraunces is the travel-story face; Geist is the product-interface face. Both fonts and their licenses live in fonts/, and the builder embeds the fonts in both HTML outputs for offline viewing. This prototype does not replace the application's Direction A stylesheet.

Phone and desktop keep native vertical scrolling as the only camera gesture, with no threshold or gesture interception; the visible alternative is the Next chapter button. The planning and privacy samples also have 48px minimum phone buttons. On phones the practical chapters flow vertically; on desktop the copy and demonstration sit side by side. The system reduced-motion setting and Calm view show static, readable lake posters. WebGL failure also retains the posters.

## Source and build

- source.html: semantic copy and example interfaces.
- scroll.css: responsive composition and the calm fallback.
- scroll.js: scroll progress, the demonstrations and moment navigation.
- immersive.js: the staged camera paths, illustrated depth layers, water and particles; inserted into scroll.js's closure by the builder.
- images/: full-resolution WebP encodings of the two approved lake paintings, for the closer camera views.
- build_scroll.py: replaces the icon markers using gitaway.icons.icon() and embeds the approved WebP assets and local fonts.
- review.html: the same page with a fixed viewport and absolute image paths, opening at the winter passage for inline review tooling. The portable index.html still opens at the beginning of the story.

From the repo root:

    pixi run python docs/design/cover-v2/scroll-prototype/build_scroll.py

The generated index.html is the portable artifact. Keep application integration separate until the scroll direction has been reviewed.

The follow-up verification in verification.json checks four viewports (1440×900, 1024×768, 390×844 and 320×740), embedded font loading, the corrected sample origin, inward and outward camera positions, reverse scrolling, stable drawing-buffer sizes, idle rendering, sample interactions, manual control, horizontal overflow, Calm view, and reduced-motion/WebGL-unavailable fallbacks.

journey-verification.json adds five viewport checks, including the inline review width and landscape: long sticky passages, fourteen distinct camera positions per viewport, the cabin dissolve, keyboard moment navigation, native wheel scrolling, 48px moment controls, covered canvas edges, the final pullback, and a WebGL context-loss fallback that shortens the passage.

## ThreeUI references

The user requested ThreeUI as inspiration. The public catalogue descriptions and social preview images were inspected for these references:

- [MUGEN](https://threeui.com/landing-pages/mugen-landing-page): several places within one continuous scroll journey.
- [Workshop Codex — Cinematic Chapters](https://threeui.com/sections/chapters/section-workshop-codex-chapters): a long alpine passage with chapter navigation and atmospheric depth.
- [Fathomless](https://threeui.com/landing-pages/fathomless-landing-page): continuous spatial travel with layered environmental detail.

The implementation is original and keeps GitAway's approved artwork and type. No ThreeUI template source, images, package or authenticated Pro content is included.

