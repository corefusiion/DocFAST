# DocFAST end-to-end test — 0/44 passed

| # | Where | Scenario | Result | Detail | Time |
|---|---|---|---|---|---|
| 1 | explorer | JPG → PNG | ❌ | AssertionError: no output file appeared | 20.7s |
| 2 | explorer | JPG → WEBP | ❌ | AssertionError: no output file appeared | 20.5s |
| 3 | explorer | JPG → HEIC | ❌ | AssertionError: no output file appeared | 20.5s |
| 4 | explorer | JPG → TIFF | ❌ | AssertionError: no output file appeared | 20.5s |
| 5 | explorer | JPG → AVIF | ❌ | AssertionError: no output file appeared | 20.7s |
| 6 | explorer | JPG → BMP | ❌ | AssertionError: no output file appeared | 20.5s |
| 7 | explorer | JPG → PDF | ❌ | AssertionError: no output file appeared | 20.5s |
| 8 | explorer | JPG → ICO | ❌ | AssertionError: no output file appeared | 20.5s |
| 9 | explorer | JPG → GIF | ❌ | AssertionError: no output file appeared | 20.5s |
| 10 | explorer | PNG → JPG | ❌ | AssertionError: no output file appeared | 20.3s |
| 11 | explorer | PDF → JPG (3 pages) | ❌ | AssertionError: no output file appeared | 20.3s |
| 12 | explorer | PDF → PNG (3 pages) | ❌ | AssertionError: no output file appeared | 20.5s |
| 13 | explorer | PDF → DOCX | ❌ | AssertionError: no output file appeared | 20.5s |
| 14 | explorer | PDF → TXT | ❌ | AssertionError: no output file appeared | 20.5s |
| 15 | explorer | DOCX → PDF | ❌ | AssertionError: no output file appeared | 20.2s |
| 16 | explorer | DOCX → TXT | ❌ | AssertionError: no output file appeared | 20.6s |
| 17 | explorer | TXT → PDF | ❌ | AssertionError: no output file appeared | 20.3s |
| 18 | explorer | TXT → DOCX | ❌ | AssertionError: no output file appeared | 20.7s |
| 19 | explorer | 2 images → 1 PDF | ❌ | AssertionError: no output file appeared | 22.4s |
| 20 | explorer | Compress to 200 KB | ❌ | RuntimeError: window not found: Compress.* | 18.7s |
| 21 | explorer | Resize 50% | ❌ | RuntimeError: window not found: Resize.* | 18.7s |
| 22 | explorer | Crop 1:1 | ❌ | RuntimeError: window not found: Crop Image.* | 18.4s |
| 23 | explorer | Edit: auto + rotate | ❌ | RuntimeError: window not found: Edit.* | 18.4s |
| 24 | explorer | Annotate | ❌ | RuntimeError: window not found: Annotate.* | 18.4s |
| 25 | explorer | Redact | ❌ | RuntimeError: window not found: Redact.* | 18.4s |
| 26 | explorer | Add BG 1:1 | ❌ | RuntimeError: window not found: Add BG.* | 18.4s |
| 27 | explorer | Metadata: remove location | ❌ | RuntimeError: window not found: Metadata.* | 18.4s |
| 28 | explorer | Metadata: remove all | ❌ | RuntimeError: window not found: Metadata.* | 18.4s |
| 29 | explorer | PDF Compress | ❌ | AssertionError: no output file appeared | 21.2s |
| 30 | explorer | PDF Split | ❌ | AssertionError: no output file appeared | 21.4s |
| 31 | explorer | PDF Rotate | ❌ | AssertionError: no output file appeared | 21.4s |
| 32 | explorer | PDF Protect | ❌ | RuntimeError: window not found: Password-protect.* | 18.6s |
| 33 | explorer | PDF Extract images | ❌ | AssertionError: no output file appeared | 21.4s |
| 34 | explorer | PDF Metadata | ❌ | RuntimeError: window not found: Metadata.* | 18.4s |
| 35 | explorer | Merge 2 PDFs | ❌ | AssertionError: no output file appeared | 22.9s |
| 36 | send-to | Send To → PNG | ❌ | AssertionError: no output file appeared | 19.1s |
| 37 | desktop | Desktop: JPG → PNG | ❌ | AssertionError: no output file appeared | 20.1s |
| 38 | desktop | Desktop: PDF → TXT | ❌ | AssertionError: no output file appeared | 20.0s |
| 39 | desktop | Desktop: DOCX → PDF | ❌ | AssertionError: no output file appeared | 20.0s |
| 40 | desktop | Desktop: Compress | ❌ | RuntimeError: window not found: Compress.* | 17.9s |
| 41 | desktop | Desktop: Crop | ❌ | RuntimeError: window not found: Crop Image.* | 18.0s |
| 42 | desktop | Desktop: Add BG | ❌ | RuntimeError: window not found: Add BG.* | 18.0s |
| 43 | desktop | Desktop: 2 PDFs merge | ❌ | AssertionError: no output file appeared | 22.3s |
| 44 | all | Drag picture kept out of the glass | ❌ | hidden during 0 menu captures | 0s |