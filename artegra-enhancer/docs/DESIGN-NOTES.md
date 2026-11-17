# Design notes

## Mode marks

The tab's icon system has six glyph kinds. The Beta adds one more, the mode mark, with two names: `modeRedux` and `modeBolt` (`ui/qml/creative/CuIcon.qml`, `Tokens.glyphs`). They follow the same rules as every glyph:

- drawn as whole device-pixel rectangles on the 16-unit grid, one stroke weight (`Tokens.strokePx`), 45° lines as stairs, no shapes or layers, so they stay crisp at 100, 125 and 150 %;
- monochrome on the v5 tokens: `text3` at rest, `text1` when chosen, hovered or pressed, `text4` when disabled;
- 8 px before the word they label; decorative for assistive technology (the word carries the name).

**Redux, "courses".** Three stacked courses with staggered joints, like coursed stone: detail rebuilt in layers. When Redux is chosen, the courses settle into place from 2 units to the right, one after another (0, 60 and 120 ms, 160 ms each).

**Bolt, "strike".** One leaning strike: a down-left run, a short horizontal kick and a longer lower run. Outline only, no fill or arrowhead. When Bolt is chosen it draws from top to bottom over 200 ms, then brightens over 100 ms.

Each motion runs once and lasts about 300 ms. With reduced motion there is no travel or drawing, only a 120 ms fade from 60 % to full opacity. The standalone takes reduced motion from Windows: when Animation effects is off (Settings, Accessibility, Visual effects), the tab's reduced motion is on.

The marks appear on the Mode control, as a badge before the meta line of every queue row (the mode a waiting image will run in, or the mode that made a result), before the size of every result cell, and before the mode name in the viewer caption. Action tiles such as "Upscale again in Redux" carry words only.
