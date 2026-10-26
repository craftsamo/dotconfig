# bars

Native canvas: 512x64; pixel: 64x8. Front-facing horizontal UI. Frame
and fill share a canvas, baseline and padding. A generated fill is not
guaranteed to register to a separately generated frame: test the overlay;
route exact progress-fill geometry to create-kit if it drifts.

| item | description | state |
| --- | --- | --- |
| health-frame | empty health bar rim, transparent interior | static |
| health-fill | solid health fill inset to health-frame, no outer border | static |
| mana-frame | empty mana bar rim with the same geometry as health-frame | static |
| mana-fill | solid mana fill inset to mana-frame, no outer border | static |
