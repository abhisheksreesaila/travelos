# GitAway — Take a trip. Leave a trail.

87-second, 18-scene watercolor film from the approved `../shots.json` storyboard and `../frames/` artwork. Master: 1920 × 1080, 24 fps, H.264/AAC. A smaller 1280 × 720 copy is exported too.

## Picture and sound

- Scenes 06, 07, 08 and 16 project the approved art onto depth meshes in Three.js, with a moving perspective camera. The lake has subtle shader ripples; the winter shots add drifting snow. This is depth/parallax animation of the paintings, rather than a free-flying geographic terrain model.
- The other scenes use restrained camera moves, dissolves, dialogue cards and route strokes. The characters preserve the approved drawings; they are not articulated or lip-synced.
- Narration reuses the project's eight existing Kokoro-82M `af_heart` recordings in `docs/design/cover-v2/e-assets/vo-*.ogg`. The accompanying piano-like score, room/wind textures and paper brushes are generated locally from seeded synthesis; no stock music was downloaded.
- English narration appears in the picture and is supplied as an optional subtitle track plus `gitaway-story.srt`. The 1080p master has a chapter per storyboard scene.

## Rebuild

From the repository root:

```sh
pixi run python docs/design/cover-v2/story/sol-v2/film/make_film.py audio
pixi run python docs/design/cover-v2/story/sol-v2/film/make_film.py test
pixi run python docs/design/cover-v2/story/sol-v2/film/make_film.py render
pixi run python docs/design/cover-v2/story/sol-v2/film/make_film.py finish
```

Requires the project's existing Playwright Chromium and system FFmpeg. Rendering is deterministic and offline: Playwright fulfils asset requests from repository files in memory; it does not start a web server. The application and its landing page are unchanged.
