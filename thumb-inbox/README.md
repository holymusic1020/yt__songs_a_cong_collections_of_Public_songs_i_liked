# thumb-inbox — drop AI thumbnails here, no terminal needed

`tools/thumbgen.html` (the hosted page) can export a **commit pack**: it downloads
`index.json` plus one `.jpg` per accepted image. Create a folder named
`thumb-inbox/` here on github.com with *Add file → Upload files* and the release
engine picks those images up the next night — no `gh`, no release, no CLI.

* The bank reader (`src/thumb_bank.py::load_index`) reads this folder's
  `index.json` **and** the `thumb-lab` release assets, tags each row with where it
  came from, and de-duplicates by content hash — so uploading the same frame twice
  is harmless.
* The `index.json` from the page is already in the right shape:
  `{"images":[{"file","sha","genre","engine","luma","spread","dhash"}],"cursor"}`.
* Images already passed the same gates the nightly farm uses (≥900×500, 1.6–1.9
  aspect, mean luma ≥ 38, contrast, dHash spacing). Anything that did not was not
  written into the pack in the first place.
* Files here are **public** (this is a public repo). That is intended — they end up
  as video thumbnails anyway.

Prefer the release shelf for large batches (`gh release upload thumb-lab …`): it is
one asset list instead of N commits. Both sources feed the same picker.
