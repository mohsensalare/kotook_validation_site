# Kotook · DLD Data Validation site

A minimal static site for the team to review and confirm the DLD ↔ Kotook
area/developer mappings. Each area and developer page carries **20 sample
transactions** for manual validation.

White theme · green = confirmed · amber = needs review.

## Pages
- `index.html` — overview (KPIs, market-by-year, the 5 corrected mappings)
- `areas.html` — searchable list of all DLD areas → Kotook communities
- `developers.html` — searchable list of Kotook developers with confirmed DLD matches
- `a/<area>.html`, `d/<id>.html` — one page per entity (summary + evidence + 20 sample tx)
- `about.html` — method & data sources

## Preview locally
Just open `index.html` in a browser, or:
```bash
cd kotook_validation_site
python3 -m http.server 8000   # then visit http://localhost:8000
```

## Deploy to GitHub Pages
1. Create a repo and push this folder's contents to it.
2. Repo → **Settings → Pages** → Source: *Deploy from a branch* → branch `main`, folder `/ (root)`.
3. The `.nojekyll` file is already included so the `a/` and `d/` folders serve correctly.

## Rebuild the data
Regenerates every page from the DuckDB + mapping files:
```bash
/Users/mohsensalare/Desktop/dld_transactions_analysis/.venv/bin/python build.py
```
Inputs: `dld_transactions.duckdb` (Sales only), `Kotook_Data_Report_EN.xlsx`
(tab *All DLD Areas*), `DLD_Kotook_Simple_Matches.xlsx` (*Developer_Matches*).
The 5 validated corrections (JVC / JVT / JLT / The Greens / Emirates Living) are
applied in `build.py` → `OVERRIDE`.
