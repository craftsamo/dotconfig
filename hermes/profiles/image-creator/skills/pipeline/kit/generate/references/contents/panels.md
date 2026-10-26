# panels

Native canvas: 512x384; pixel: 96x64. Front-facing UI, consistent frame
thickness, quiet empty content regions, no letters, fake screenshots or
embedded controls. These are fixed-size images; `create-kit` owns tested
9-slice geometry. Pixel canvases intentionally differ in aspect ratio.

| item | description | state |
| --- | --- | --- |
| window | main window with a broad blank title band | static |
| tooltip | quiet tooltip frame without a title band | static |
| inventory | inventory container, empty centre for runtime slots | static |
| dialogue | dialogue frame, blank body with no speaker portrait | static |
