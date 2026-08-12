# Source provenance

All source files remain in the isolated WS614 WhatsApp intake. The selected frame
sequences are deterministic excerpts; source audio is excluded. New v2 excerpts use
FFmpeg `vidstabdetect` followed by `vidstabtransform` with smoothing 8, adaptive zoom,
3% base zoom and bicubic interpolation. Each stabilisation pass includes surrounding
source padding before the exact 2.7-second publishing window is trimmed to 81 frames
at 30 fps. The original project's frame sequences are referenced through relative
symlinks and are not duplicated.

| Composition | Role | Intake file | Source range | SHA-256 |
|---|---|---|---:|---|
| Reel | Opening elevation | `20260728T104331000Z_aad7826804ee3275.mp4` | 18.5–21.2 s | `3c2c962e1f2f6f9cf4b28f41c72f6e8ec99f504f45036225659007fe69742242` |
| Reel | Measuring | `20260728T004155000Z_a2723e50879edf6a.mp4` | 0.3–2.7 s | `e67494cc36c653662d31aaf21388f156c42fcee9aa6ba4b153fae5dabcc09d40` |
| Reel | Scaffold context | `20260728T104331000Z_708e8859fe01f016.mp4` | 2.2–4.7 s | `d1cbcf115781c74ffb8960d1889d60175442f3e57e0399e93415cf59c88e098c` |
| Reel | Façade corridor | `20260728T104332000Z_98e5cdd08e6823e7.mp4` | 24.5–27.3 s | `e165d0803125ac99eea0b427b66fe748c34337c16acab5cc372615635c73e0e8` |
| Reel v2 | Calm closing opening | `20260728T104330000Z_90eb04555565606e.mp4` | 0.2–2.9 s | `10320102774593570bc432d66610401e81ec26ee61bbcd051e0ccedf8518df28` |
| Story | Parapet | `20260802T221733000Z_7b51fce76c1dca91.mp4` | 52.5–55.3 s | `d7e80b4b8ba8f12901d0f02be8327e54ea2290bcebdc413e5f9497397ce395f2` |
| Story | Junction | `20260803T100305000Z_4adaa851ebea9b2c.mp4` | 44.5–47.3 s | `0017905e74d965457a051544bc923e42a7d1f75cec09bef936cc324294168439` |
| Story | Wider context | `20260804T071338000Z_df80903dfc264319.mp4` | 20.5–23.9 s | `38700fe1697923f59f9da908997293e2610f1757d3e684e1fda646e42cd7cc5c` |
| Setting out | Sill line A | `20260728T004155000Z_a2723e50879edf6a.mp4` | 11.0–13.7 s | `e67494cc36c653662d31aaf21388f156c42fcee9aa6ba4b153fae5dabcc09d40` |
| Setting out | Sill line B | `20260728T004155000Z_a2723e50879edf6a.mp4` | 18.0–20.7 s | `e67494cc36c653662d31aaf21388f156c42fcee9aa6ba4b153fae5dabcc09d40` |
| Setting out | Sill line C | `20260728T004155000Z_a2723e50879edf6a.mp4` | 27.2–29.9 s | `e67494cc36c653662d31aaf21388f156c42fcee9aa6ba4b153fae5dabcc09d40` |
| Field craft | Return check | `20260727T094818000Z_e12b18ce287ad7cf.mp4` | 9.2–11.9 s | `3c077909577e9ae26c381fe499c54d0dd1a784161fc9496aee485d7304d78497` |
| Field craft | Surface work | `20260521T214156000Z_c34476877a3113cc.mp4` | 33.2–35.9 s | `0ad7a79a0e6527912748d2bee4e4fb32a35f6456ddeeed20c3c0f37aea2ac34b` |
| Field craft | Elevation context | `20260727T094818000Z_e12b18ce287ad7cf.mp4` | 136.5–139.2 s | `3c077909577e9ae26c381fe499c54d0dd1a784161fc9496aee485d7304d78497` |
| Façade progress | Parapet | `20260805T123040000Z_38f025170f3cb72c.mp4` | 0.2–2.9 s | `7f96c72a18d627b9f95878251b9bc2f54ff1b849f30ac26401a1894dd1823fa2` |
| Façade progress | Glazing context | `20260728T104331000Z_87b1a49fbe70ca1f.mp4` | 2.4–5.1 s | `ff9f61f5b32ff7c996522390fca0d61ea9c9ae10fedf693b53dd3d38f45a1be0` |
| Façade progress | Finished opening | `20260728T224538000Z_4a903375186c8da5.mp4` | 52.5–55.2 s | `3d6565751a138ac1ff09cf49fac84ef74f03561e2244e90e8129c36749721398` |
