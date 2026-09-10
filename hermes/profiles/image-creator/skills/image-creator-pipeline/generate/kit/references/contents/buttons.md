# buttons

Native canvas: 384x128; pixel: 48x16. All buttons face the screen, have
the same footprint and a clear label region; labels are runtime text,
never model-drawn pixels. Normal and pressed count as separate items.
Add hover/disabled only when asked. State pairs must overlay without drift.

| item | description | state |
| --- | --- | --- |
| primary-normal | main action button, accent rim, blank centre | normal |
| primary-pressed | same primary geometry, inset/darker surface, fixed outer border | pressed |
| secondary-normal | secondary action button, quiet rim, blank centre | normal |
| secondary-pressed | same secondary geometry, darker surface, fixed outer border | pressed |
