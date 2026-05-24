# Landing page screenshots

Drop PNGs here. The landing page (`../index.html`) already references
each filename below — once a file exists at the matching path, the
striped placeholder in the corresponding card disappears automatically
(via an `onerror` swap on each `<img>`).

| File                       | Where it shows up                     |
| -------------------------- | ------------------------------------- |
| `01-hero.png`              | Hero block at the top of the page     |
| `02-catalog.png`           | "Catalogue search" screenshot card    |
| `03-classify.png`          | "Classify scene" screenshot card      |
| `04-accuracy.png`          | "Accuracy report" screenshot card     |
| `05-change.png`            | "Time-series change" screenshot card  |

Suggested specs (matching the placeholder aspect ratio): **16:10**, at
least 1600 px wide. PNG. Compress with `oxipng -o 4` or similar before
committing if file size matters.

If you want to add more cards, edit `../index.html` — search for
`<figure class="shot">` and copy/paste a block.
