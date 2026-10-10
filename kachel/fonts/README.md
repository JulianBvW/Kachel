# Material Symbols Rounded

Google's icon font, used for Kachel's own chrome: the search button, the rail,
the shortcut buttons. App icons come from the icon theme instead.

Two static instances of the variable font, each with the full set of symbols
but only the one style Kachel uses. The variable font with every axis is
15 MB; these two together are 3 MB.

| File | Family | Axes |
|---|---|---|
| `MaterialSymbolsRounded.ttf` | Material Symbols Rounded | FILL 0, wght 400, GRAD 0, opsz 24 |
| `MaterialSymbolsRoundedFilled.ttf` | Material Symbols Rounded Filled | FILL 1, wght 400, GRAD 0, opsz 24 |

Fetched on 2026-10-10 from the Google Fonts CSS API:

    https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@24,400,0,0
    https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@24,400,1,0

Kachel loads them for its own process only (fontconfig's
`FcConfigAppFontAddFile`); nothing is installed on the system.

Licensed under the Apache License 2.0, see `LICENSE` in this folder,
copied from https://github.com/google/material-design-icons.
