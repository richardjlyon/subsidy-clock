# Scotland briefing paper, 2026 edition

Fixed. Published 10 October 2026; figures are for calendar 2025. Do not edit
or regenerate this folder: a published paper does not move. A correction goes
on /corrections and, if it changes a figure here, into a reissued edition.

- figures.json   every number, frozen (from `tools/scotland_claims.py compute`)
- index.html     rendered from figures.json (`tools/scotland_claims.py render`)
- scotland-claims-2026.pdf   printed from index.html (`tools/scotland_paper_pdf.py`)

Next edition: when DESNZ publishes its 2026 regional figures (autumn 2027),
bump EDITION/PUBLISHED/CHECKED and the quoted constants in the tool, then
compute + render + pdf into a new folder, site/papers/scotland-2027/.
