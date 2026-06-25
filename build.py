#!/usr/bin/env python3
# Builds the Kotook DLD-validation static site (GitHub Pages friendly).
# Reads ONLY the pipeline deliverable kotook_market.duckdb (built by kotook_pipeline.ipynb).
# Every metric is split into off-plan / secondary / combined via the `segment` column.
import duckdb, pandas as pd, re, json, html, datetime, pathlib

ROOT  = pathlib.Path(__file__).parent
DB    = "/Users/mohsensalare/Desktop/dld_transactions_analysis/kotook_market.duckdb"
con   = duckdb.connect(DB, read_only=True)
TODAY = datetime.date.today().isoformat()
BUILD = datetime.datetime.now().strftime("%Y%m%d%H%M%S")  # cache-buster

# ---------- helpers ----------
def esc(x):
    if x is None: return ""
    try:
        if pd.isna(x): return ""
    except (TypeError, ValueError): pass
    return html.escape(str(x))
def fdate(x):
    try:
        if pd.isna(x): return ""
    except (TypeError, ValueError): pass
    return str(x)[:10]
def fnum(n):
    try: return f"{int(round(float(n))):,}"
    except: return "—"
def fmoney(n):
    try:
        n = float(n)
        if n != n: return "0.00"
        return f"{n:,.2f}"
    except: return "—"
def fpct(n, signed=False):
    try:
        n = float(n)
        if n != n: return "—"
        return (f"{n:+.0f}%" if signed else f"{n:.0f}%")
    except: return "—"
def slugify(s):
    s = re.sub(r'[^a-z0-9]+', '-', str(s).lower()).strip('-'); return s or 'x'

def page(title, active, body, depth=0):
    up = "../" * depth
    nav = [("Overview","index.html","home"),("Areas","areas.html","areas"),
           ("Developers","developers.html","developers"),("Market","market.html","market"),
           ("Compare","compare.html","compare"),("Method","about.html","about")]
    navhtml = "".join(f'<a class="{ "active" if k==active else "" }" href="{up}{href}">{esc(label)}</a>' for label,href,k in nav)
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
<meta http-equiv="Pragma" content="no-cache"><meta http-equiv="Expires" content="0">
<title>{esc(title)} · Kotook DLD Validation</title>
<link rel="stylesheet" href="{up}assets/style.css?v={BUILD}"></head><body>
<header class="top"><div class="wrap">
<div class="brand"><span class="dot"></span>Kotook&nbsp;<small>DLD Data Validation</small></div>
<nav class="main">{navhtml}</nav></div></header>
<main><div class="wrap">{body}</div></main>
<footer><div class="wrap">Kotook · DLD transaction validation · generated {TODAY} ·
source: pipeline deliverable <b>kotook_market.duckdb</b> · DLD Sales transactions</div></footer>
</body></html>"""

def bars(rows):  # rows: list of (label_x, value, label_top)
    mx = max([r[1] for r in rows] or [1]) or 1
    cells = ""
    for yr, v, lab in rows:
        h = max(2, round(100 * v / mx))
        cells += f'<div class="bar"><div class="v">{esc(lab)}</div><div class="col" style="height:{h}%"></div><div class="yr">{esc(yr)}</div></div>'
    return f'<div class="bars">{cells}</div>'

def kpi(label, val, hint="", green=False):
    g = " green" if green else ""
    h = f'<div class="hint">{esc(hint)}</div>' if hint else ""
    return f'<div class="card kpi"><div class="label">{esc(label)}</div><div class="val{g}">{esc(val)}</div>{h}</div>'

def statline(items):
    return '<div class="card statrow">' + "".join(f'<div><span class="lbl">{esc(l)}</span><span class="v">{v}</span></div>' for l, v in items) + '</div>'

SEG_LABEL = {"offplan": "Off-plan (primary)", "secondary": "Secondary (ready)", "all": "Combined"}
def seg_compare(rows, items):
    """rows: {segment: namedtuple|None}; items: [(label, fn(row)->str)]. Off-plan | Secondary | Combined."""
    cols = ["offplan", "secondary", "all"]
    th = "".join(f'<th class="num seg-{c}">{SEG_LABEL[c]}</th>' for c in cols)
    body = ""
    for label, fn in items:
        tds = "".join(f'<td class="num seg-{c}">{fn(rows.get(c))}</td>' for c in cols)
        body += f"<tr><td>{label}</td>{tds}</tr>"
    return f'<div class="tablecard segcmp"><table><thead><tr><th>Metric</th>{th}</tr></thead><tbody>{body}</tbody></table></div>'

def year_segment_table(yr_df, keycol, keyval):
    sub = yr_df[yr_df[keycol] == keyval]
    years = sorted(int(y) for y in sub.year.dropna().unique())
    def cell(y, seg, col):
        m = sub[(sub.year == y) & (sub.segment == seg)]
        if not len(m): return "—"
        v = m.iloc[0][col]
        return fnum(v) if pd.notna(v) else "—"
    rows = ""
    for y in years:
        rows += (f"<tr><td>{y}</td>"
                 f'<td class="num seg-offplan">{cell(y,"offplan","tx")}</td>'
                 f'<td class="num seg-secondary">{cell(y,"secondary","tx")}</td>'
                 f'<td class="num seg-all">{cell(y,"all","tx")}</td>'
                 f'<td class="num seg-offplan">{cell(y,"offplan","median_aed_sqft")}</td>'
                 f'<td class="num seg-secondary">{cell(y,"secondary","median_aed_sqft")}</td></tr>')
    return ('<div class="tablecard"><table><thead><tr><th>Year</th>'
            '<th class="num seg-offplan">Off-plan tx</th><th class="num seg-secondary">Secondary tx</th><th class="num seg-all">All tx</th>'
            '<th class="num seg-offplan">Off-plan AED/sqft</th><th class="num seg-secondary">Secondary AED/sqft</th></tr></thead>'
            f"<tbody>{rows}</tbody></table></div>")

# ---------- load the deliverable ----------
META  = dict(con.sql("SELECT key, value FROM meta").fetchall())
AST   = con.sql("SELECT * FROM area_stats").df()
AYR   = con.sql("SELECT * FROM area_year_stats").df()
ASY   = con.sql("SELECT * FROM area_supply_year").df()
DST   = con.sql("SELECT * FROM developer_stats").df()
DYR   = con.sql("SELECT * FROM developer_year_stats").df()
DSUP  = con.sql("SELECT * FROM developer_supply").df()
DSY   = con.sql("SELECT * FROM developer_supply_year").df()
UNM   = con.sql("SELECT * FROM area_unmapped ORDER BY tx_total DESC").df()
DUNM  = con.sql("SELECT * FROM developer_unmapped ORDER BY tx_total DESC").df()
MKT   = con.sql("SELECT * FROM market_stats").df()
MYR   = con.sql("SELECT * FROM market_year_stats").df()
MIDX  = con.sql("SELECT * FROM market_index ORDER BY year").df()
MDEM  = con.sql("SELECT * FROM market_demand ORDER BY year").df()
MSUPY = con.sql("SELECT * FROM market_supply_year ORDER BY year").df()
MSUPA = con.sql("SELECT * FROM market_supply_area ORDER BY pipeline_units DESC NULLS LAST").df()
MSC   = con.sql("SELECT * FROM market_service_charge ORDER BY aed_sqft DESC").df()
MSTK  = con.sql("SELECT * FROM market_existing_stock ORDER BY existing_units DESC").df()

BENCH = {
 'Emaar Properties':{'n':'28,521','note':'2024 off-plan units (Primo Capital); AED 65.4bn dev sales (Emaar)','url':'https://primocapital.ae/blog/10-top-performing-uae-real-estate-developers-of-2024-key-stats-and-success'},
 'DAMAC Properties':{'n':'16,463','note':'2024 off-plan units (Primo Capital)','url':'https://primocapital.ae/blog/10-top-performing-uae-real-estate-developers-of-2024-key-stats-and-success'},
 'sobha':{'n':'10,384','note':'2024 off-plan units (Primo); AED 23bn sales (Sobha)','url':'https://sobharealty.com/media-center/press-releases/sobha-realty-records-historic-aed-23-billion-in-sales-for-2024/'},
 'Binghatti':{'n':'7,259','note':'2024 off-plan units (Primo Capital); AED 10.86bn','url':'https://primocapital.ae/blog/dubai-apartments-hit-6786-billion-in-2024-a-look-at-developers-market-share'},
 'Azizi developments':{'n':'10,229','note':'2024 units sold (Azizi official); >AED 10bn','url':'https://www.zawya.com/en/press-release/companies-news/azizi-developments-delivers-19-projects-and-sells-over-10-000-units-in-2024-krao9vmx'},
 'Danube Properties':{'n':'6,334','note':'2024 transferred sales; AED 9.42bn (Primo Capital)','url':'https://primocapital.ae/blog/dubai-apartments-hit-6786-billion-in-2024-a-look-at-developers-market-share'},
 'Nshama':{'n':'3,024','note':'2024 transactions; AED 4.53bn; 2% share (Primo Capital)','url':'https://primocapital.ae/blog/dubai-apartments-hit-6786-billion-in-2024-a-look-at-developers-market-share'},
}

SAMPLE = 20
(ROOT/"a").mkdir(exist_ok=True); (ROOT/"d").mkdir(exist_ok=True); (ROOT/"data").mkdir(exist_ok=True)

# ============================================================ per-area pages
area_index = []
for dld in AST[AST.segment == "all"].dld_area.tolist():
    rows = {r.segment: r for r in AST[AST.dld_area == dld].itertuples()}
    a = rows["all"]
    status = "ok" if a.mapping_status == "Confirmed" else "warn"
    sl = slugify(dld)

    chips = f'<span class="chip {status}">{esc(a.mapping_status)}</span>'
    if a.corrected and not a.missing:
        chips += ' <span class="chip fix">Corrected mapping</span>'

    # combined headline KPIs
    vhint = (f"excl. bulk >500M: {fmoney(a.value_bn_excl_bulk_2023plus)} bn"
             if (float(a.value_bn_2023plus or 0) - float(a.value_bn_excl_bulk_2023plus or 0)) >= 0.05 else "")
    kpis = (f'<div class="grid k4">{kpi("Sales transactions", fnum(a.tx_total))}'
            f'{kpi("Since 2023", fnum(a.tx_2023plus))}'
            f'{kpi("Value 2023+ (bn AED)", fmoney(a.value_bn_2023plus), vhint)}'
            f'{kpi("Off-plan share 2023+", fpct(a.offplan_share_2023plus_pct))}</div>')

    # off-plan vs secondary vs combined
    seg_tbl = seg_compare(rows, [
        ("Sales transactions (all years)", lambda r: fnum(r.tx_total) if r is not None else "—"),
        ("Sales since 2023",              lambda r: fnum(r.tx_2023plus) if r is not None else "—"),
        ("Value 2023+ (bn AED)",          lambda r: fmoney(r.value_bn_2023plus) if r is not None else "—"),
        ("Median AED/sqft (2024+)",       lambda r: fnum(r.median_aed_sqft_2024plus) if r is not None else "—"),
        ("Median AED/m² (2024+)",         lambda r: fnum(r.median_aed_sqm_2024plus) if r is not None else "—"),
    ])
    prem = a.offplan_premium_2023plus_pct
    seg_note = (f'<p class="note" style="margin-top:8px">Off-plan trades at a '
                f'<b>{fpct(prem, signed=True)}</b> price premium over ready/secondary here (median AED/m², 2023+). '
                f"Counts cover all registered sales; prices use the clean residential basis (Unit/Villa).</p>"
                if pd.notna(prem) else "")

    # transactions per year (combined) + by-segment table
    yr_all = AYR[(AYR.dld_area == dld) & (AYR.segment == "all")].sort_values("year")
    yrows = [(str(int(x.year)), int(x.tx), fnum(x.tx)) for x in yr_all.itertuples()]
    yseg = year_segment_table(AYR, "dld_area", dld)

    # supply & absorption
    hy = ASY[ASY.dld_area == dld].sort_values("year")
    hands = [(str(int(x.year)), int(x.pipeline_units or 0), fnum(x.pipeline_units)) for x in hy.itertuples() if pd.notna(x.year)][:4]
    hbars = bars(hands) if hands else "<span class='muted'>no dated handovers in DLD registry</span>"
    supply_card = (f'<div class="grid k3">{kpi("Pipeline units", fnum(a.pipeline_units), "under construction / planned")}'
                   f'{kpi("Pipeline projects", fnum(a.pipeline_projects))}'
                   f'{kpi("Years of supply", (f"{a.years_of_supply:.1f}" if pd.notna(a.years_of_supply) else "—"), "pipeline ÷ avg annual sales")}</div>'
                   f'<div class="chartcard" style="margin-top:14px"><div class="note" style="margin-bottom:6px">Units handing over by year — '
                   f'<b>DLD registered-project pipeline (lower bound; undated projects excluded)</b></div>{hbars}</div>')

    # stats strip (valuation gap + service charge)
    stat_items = [("Off-plan premium (2023+)", fpct(prem, signed=True)),
                  ("Market vs DLD valuation (2024+)", fpct(a.valuation_gap_2024plus_pct, signed=True)),
                  ("Median AED/m² (2024+)", fnum(a.median_aed_sqm_2024plus))]
    if pd.notna(a.service_charge_2023_aed_sqft):
        stat_items.append(("Service charge 2023 (AED/sqft)", f"~{float(a.service_charge_2023_aed_sqft):.1f}"))
    stats = statline(stat_items)

    # existing built stock + unit mix
    stock_section = ""
    if pd.notna(a.existing_units) and a.existing_units:
        iv = lambda v: (int(v) if pd.notna(v) else 0)
        brc = [("Studio", iv(a.br_studio)), ("1 B/R", iv(a.br_1)), ("2 B/R", iv(a.br_2)),
               ("3 B/R", iv(a.br_3)), ("4+ B/R", iv(a.br_4plus))]
        brtot = sum(c for _, c in brc) or 1
        mixrows = "".join(f"<tr><td>{lab}</td><td class='num'>{fnum(c)}</td><td class='num'>{round(100*c/brtot)}%</td></tr>" for lab, c in brc)
        med = a.median_unit_size_sqm
        stock_card = (f'<div class="grid k2">{kpi("Existing built units", fnum(a.existing_units), "titled units in DLD registry")}'
                      f'{kpi("Median unit size", (fnum(med)+" m²") if pd.notna(med) else "—")}</div>'
                      f'<div class="tablecard" style="margin-top:14px"><table><thead><tr><th>Bedrooms</th><th class="num">Units</th><th class="num">Share</th></tr></thead><tbody>{mixrows}</tbody></table></div>'
                      f'<p class="note" style="margin-top:6px">Existing built stock from the DLD <b>units</b> registry (snapshot of titled units). Bedroom mix is among classified residential units; size uses cleaned <span class="mono">actual_area</span> (~13% unusable rows excluded).</p>')
        stock_section = f"<h2>Existing built stock &amp; unit mix</h2>{stock_card}"

    # evidence — top master_project labels inside this area
    masters = con.sql("""SELECT master_project_en m, COUNT(*) c FROM transactions_clean
                         WHERE dld_area=? AND master_project_en IS NOT NULL AND master_project_en<>''
                         GROUP BY 1 ORDER BY c DESC LIMIT 3""", params=[dld]).df()
    ev = " · ".join(f"<b>{esc(m.m)}</b> ({fnum(m.c)})" for m in masters.itertuples()) or "<span class='muted'>no master label</span>"

    # 20 sample transactions
    samp = con.sql("""SELECT dld_area a, instance_date d, project_name_en p, building_name_en b,
                        nearest_landmark_en lm, nearest_metro_en mt, rooms_en r, procedure_area ar,
                        actual_worth w, segment s
                      FROM transactions_clean WHERE dld_area=? ORDER BY instance_date DESC LIMIT ?""",
                   params=[dld, SAMPLE]).df()
    trs = ""
    for x in samp.itertuples():
        segpill = f'<span class="segdot seg-{x.s}">{esc(x.s)}</span>'
        trs += (f"<tr><td class='match'>{esc(x.a)}</td><td class='mono'>{esc(fdate(x.d))}</td><td>{segpill}</td>"
                f"<td class='name'>{esc(x.p)}</td><td>{esc(x.b)}</td><td>{esc(x.lm)}</td>"
                f"<td class='muted'>{esc(x.mt)}</td><td>{esc(x.r)}</td><td class='num'>{fnum(x.ar)}</td><td class='num'>{fnum(x.w)}</td></tr>")

    body = f"""<div class="crumb"><a href="../areas.html">Areas</a> / {esc(dld)}</div>
<h1>{esc(dld)} {chips}</h1>
<p class="sub">Mapped to Kotook community: <b>{esc(a.kotook_area)}</b>{(' · id '+str(int(a.kotook_area_id))) if pd.notna(a.kotook_area_id) else ''}</p>
{kpis}
<h2>Off-plan vs secondary vs combined</h2>
{seg_tbl}{seg_note}
<h2>Sales transactions per year (combined)</h2>
<div class="chartcard">{bars(yrows)}</div>
<h2>Split by segment, per year</h2>
{yseg}
<p class="note" style="margin-top:8px">Off-plan = primary (developer) sales; Secondary = ready/resale. Prices use a clean residential basis (Unit/Villa, impossible AED/m² removed). The secondary column is the cleanest read on real price growth — off-plan launch waves can't distort it.</p>
<div style="margin-top:12px">{stats}</div>
<h2>Supply &amp; absorption</h2>
{supply_card}
{stock_section}
<h2>Evidence — DLD <span class="mono">master_project_en</span> inside this area</h2>
<div class="card evid">{ev}<div class="note" style="margin-top:8px">Auto-status compares the Kotook community name to the dominant master_project. Reviewers should confirm using the sample below.</div></div>
<h2>{SAMPLE} sample transactions to validate</h2>
<p class="note">Why these rows: every transaction below has DLD <span class="mono">area_name_en = "{esc(dld)}"</span> — the selection rule for this area (highlighted column). The <b>Segment</b> column shows off-plan vs secondary.</p>
<div class="tablecard"><table><thead><tr><th class="match">Area (DLD)</th><th>Date</th><th>Segment</th><th>Project</th><th>Building</th><th>Nearest landmark</th><th>Nearest metro</th><th>Rooms</th><th class="num">Size m²</th><th class="num">Price AED</th></tr></thead><tbody>{trs}</tbody></table></div>
"""
    (ROOT/"a"/f"{sl}.html").write_text(page(dld, "areas", body, depth=1), encoding="utf-8")
    area_index.append(dict(dld=dld, kname=a.kotook_area,
                           kid=(int(a.kotook_area_id) if pd.notna(a.kotook_area_id) else None),
                           tx=int(a.tx_total), val23=float(a.value_bn_2023plus or 0),
                           status=status, stxt=a.mapping_status, corrected=bool(a.corrected), slug=sl))

# ============================================================ per-developer pages
dev_index = []
for did in DST[DST.segment == "all"].kotook_developer_id.tolist():
    rows = {r.segment: r for r in DST[DST.kotook_developer_id == did].itertuples()}
    d = rows["all"]; name = str(d.developer); sl = str(int(did))
    sup = DSUP[DSUP.kotook_developer_id == did]
    pipe_u = int(sup.iloc[0].pipeline_units) if len(sup) else 0
    pipe_p = int(sup.iloc[0].pipeline_projects) if len(sup) else 0
    ents = con.sql("""SELECT DISTINCT dld_developer_entity e FROM transactions_clean
                      WHERE kotook_developer_id=? AND dld_developer_entity IS NOT NULL ORDER BY 1""", params=[did]).df()['e'].tolist()
    nent = len(ents)

    vhint = (f"excl. bulk >500M: {fmoney(d.value_bn_excl_bulk_2023plus)} bn"
             if (float(d.value_bn_2023plus or 0) - float(d.value_bn_excl_bulk_2023plus or 0)) >= 0.05 else "")
    kpis = (f'<div class="grid k4">{kpi("Sales transactions", fnum(d.tx_total))}'
            f'{kpi("Since 2023", fnum(d.tx_2023plus))}'
            f'{kpi("Value 2023+ (bn AED)", fmoney(d.value_bn_2023plus), vhint)}'
            f'{kpi("DLD developer entities", fnum(nent))}</div>')

    seg_tbl = seg_compare(rows, [
        ("Sales transactions (all years)", lambda r: fnum(r.tx_total) if r is not None else "—"),
        ("Sales since 2023",              lambda r: fnum(r.tx_2023plus) if r is not None else "—"),
        ("Sales 2024",                    lambda r: fnum(r.tx_2024) if r is not None else "—"),
        ("Value 2023+ (bn AED)",          lambda r: fmoney(r.value_bn_2023plus) if r is not None else "—"),
        ("Median AED/sqft (2024+)",       lambda r: fnum(r.median_aed_sqft_2024plus) if r is not None else "—"),
    ])

    yr_all = DYR[(DYR.kotook_developer_id == did) & (DYR.segment == "all")].sort_values("year")
    yrows = [(str(int(x.year)), int(x.tx), fnum(x.tx)) for x in yr_all.itertuples()]
    yseg = year_segment_table(DYR, "kotook_developer_id", did)

    hy = DSY[DSY.kotook_developer_id == did].sort_values("year")
    hands = [(str(int(x.year)), int(x.pipeline_units or 0), fnum(x.pipeline_units)) for x in hy.itertuples() if pd.notna(x.year)][:4]
    dhbars = bars(hands) if hands else "<span class='muted'>no dated handovers in DLD registry</span>"
    dsupply = (f'<div class="grid k2">{kpi("Pipeline units", fnum(pipe_u), "under construction / planned")}{kpi("Pipeline projects", fnum(pipe_p))}</div>'
               f'<div class="chartcard" style="margin-top:14px"><div class="note" style="margin-bottom:6px">Units handing over by year — DLD registered-project pipeline (lower bound)</div>{dhbars}</div>')

    areas_ = con.sql("""SELECT kotook_area a, COUNT(*) c FROM transactions_clean
                        WHERE kotook_developer_id=? AND kotook_area IS NOT NULL GROUP BY 1 ORDER BY c DESC LIMIT 6""", params=[did]).df()
    areapills = " · ".join(f"<b>{esc(t.a)}</b> ({fnum(t.c)})" for t in areas_.itertuples()) or "<span class='muted'>—</span>"
    entpills = "".join(f'<span class="pill">{esc(e)}</span>' for e in ents) or "<span class='muted'>—</span>"

    samp = con.sql("""SELECT dld_developer_entity de, instance_date d, project_name_en p, building_name_en b,
                        dld_area a, nearest_landmark_en lm, nearest_metro_en mt, rooms_en r, procedure_area ar,
                        actual_worth w, segment s
                      FROM transactions_clean WHERE kotook_developer_id=? ORDER BY instance_date DESC LIMIT ?""",
                   params=[did, SAMPLE]).df()
    trs = ""
    for t in samp.itertuples():
        segpill = f'<span class="segdot seg-{t.s}">{esc(t.s)}</span>'
        trs += (f"<tr><td class='match'>{esc(t.de)}</td><td class='mono'>{esc(fdate(t.d))}</td><td>{segpill}</td>"
                f"<td class='name'>{esc(t.p)}</td><td>{esc(t.b)}</td><td class='muted'>{esc(t.a)}</td>"
                f"<td>{esc(t.lm)}</td><td class='muted'>{esc(t.mt)}</td><td>{esc(t.r)}</td>"
                f"<td class='num'>{fnum(t.ar)}</td><td class='num'>{fnum(t.w)}</td></tr>")

    b = BENCH.get(name); xcheck = ""
    if b:
        c24 = int(d.tx_2024 or 0); v24 = float(d.value_bn_2024 or 0)
        xcheck = (f'<div class="callout"><h3>External cross-check (2024)</h3>'
                  f'<div class="note">Our 2024 sales (official DLD chain): <b>{fnum(c24)}</b> · ~AED {fmoney(v24)}bn &nbsp;·&nbsp; '
                  f'Independent benchmark: <b>{esc(b["n"])}</b> — {esc(b["note"])} '
                  f'<a href="{esc(b["url"])}" target="_blank" rel="noopener">source ↗</a></div></div>')

    body = f"""<div class="crumb"><a href="../developers.html">Developers</a> / {esc(name)}</div>
<h1>{esc(name)} <span class="chip ok">Official DLD attribution</span></h1>
<p class="sub">Kotook developer id {sl} · attribution via DLD <span class="mono">project_number → developer</span> (official projects registry).</p>
{kpis}
{xcheck}
<h2>Off-plan vs secondary vs combined</h2>
{seg_tbl}
<p class="note" style="margin-top:8px">Off-plan = primary launches; Secondary = resales of this developer's delivered stock. Counts are all registered sales; prices use the clean residential basis.</p>
<h2>Sales transactions per year (combined)</h2><div class="chartcard">{bars(yrows)}</div>
<h2>Split by segment, per year</h2>
{yseg}
<h2>Supply pipeline</h2>{dsupply}
<h2>Top communities</h2><div class="card evid">{areapills}</div>
<h2>DLD developer entities mapped to this brand</h2><div class="card">{entpills}</div>
<h2>{SAMPLE} sample transactions to validate</h2>
<p class="note">Why these rows: each transaction's project is officially registered in DLD to the developer entity in the highlighted column, which rolls up to <b>{esc(name)}</b>.</p>
<div class="tablecard"><table><thead><tr><th class="match">DLD developer (official)</th><th>Date</th><th>Segment</th><th>Project</th><th>Building</th><th>Community</th><th>Nearest landmark</th><th>Nearest metro</th><th>Rooms</th><th class="num">Size m²</th><th class="num">Price AED</th></tr></thead><tbody>{trs}</tbody></table></div>
"""
    (ROOT/"d"/f"{sl}.html").write_text(page(name, "developers", body, depth=1), encoding="utf-8")
    dev_index.append(dict(id=int(did), name=name, tx=int(d.tx_total), val23=float(d.value_bn_2023plus or 0),
                          nproj=nent, slug=sl, our2024=int(d.tx_2024 or 0), bench=bool(b)))

# ---------- list data (JS) ----------
(ROOT/"data"/"areas.js").write_text("window.AREAS=" + json.dumps(area_index, ensure_ascii=False) + ";", encoding="utf-8")
(ROOT/"data"/"developers.js").write_text("window.DEVS=" + json.dumps(dev_index, ensure_ascii=False) + ";", encoding="utf-8")

# ============================================================ overview
mall = {r.segment: r for r in MKT.itertuples()}
op_share_all = round(100 * float(mall["offplan"].tx_total) / float(mall["all"].tx_total))
op_share_23  = round(100 * float(mall["offplan"].tx_2023plus) / float(mall["all"].tx_2023plus))
cov = float(META.get("area_coverage_pct", 0))
n_ok = sum(1 for a in area_index if a['status'] == 'ok')
n_warn = sum(1 for a in area_index if a['status'] == 'warn')
n_corr = sum(1 for a in area_index if a['corrected'])
gyr = MYR[MYR.segment == "all"].sort_values("year")
gyrows = [(str(int(x.year)), int(x.tx), fnum(x.tx)) for x in gyr.itertuples()]

kpis = (f'<div class="grid k4">{kpi("DLD sales transactions", fnum(META.get("total_sales")))}'
        f'{kpi("Mapped to Kotook areas", f"{cov:.0f}%", f"{len(area_index)} communities", green=True)}'
        f'{kpi("Off-plan share (2023+)", f"{op_share_23}%", "primary vs secondary")}'
        f'{kpi("Developers under review", fnum(len(dev_index)))}</div>')

# off-plan vs secondary vs combined, city-wide
seg_tbl = seg_compare(mall, [
    ("Sales transactions (all years)", lambda r: fnum(r.tx_total) if r is not None else "—"),
    ("Sales since 2023",              lambda r: fnum(r.tx_2023plus) if r is not None else "—"),
    ("Value 2023+ (bn AED)",          lambda r: fmoney(r.value_bn_2023plus) if r is not None else "—"),
    ("Median AED/sqft (2024+)",       lambda r: fnum(r.median_aed_sqft_2024plus) if r is not None else "—"),
])
body = f"""<h1>DLD ↔ Kotook data validation</h1>
<p class="sub">A working dataset for the team to review and confirm. Every area and developer carries {SAMPLE} sample transactions, split into <b class="seg-offplan">off-plan</b> and <b class="seg-secondary">secondary</b>. Built from the pipeline deliverable <span class="mono">kotook_market.duckdb</span> ({esc(META.get("build_date"))}).</p>
{kpis}
<div class="legend"><span><i style="background:var(--green)"></i>Confirmed ({n_ok})</span><span><i style="background:var(--amber)"></i>Needs review ({n_warn})</span><span><i style="background:var(--green-d)"></i>Corrected mappings ({n_corr})</span></div>
<h2>Off-plan vs secondary — the whole Dubai market</h2>
{seg_tbl}
<p class="note" style="margin-top:8px">Off-plan is <b>{op_share_all}%</b> of all registered sales since records began and <b>{op_share_23}%</b> since 2023 — Kotook's core market. Secondary (ready/resale) is the rest. Every area and developer page repeats this split.</p>
<h2>Dubai sales transactions per year (all DLD)</h2>
<div class="chartcard">{bars(gyrows)}</div>
<h2>Browse</h2>
<div class="grid k2"><a class="card" href="areas.html"><div class="kpi"><div class="label">Areas</div><div class="val green">{len(area_index)}</div><div class="hint">DLD areas mapped to Kotook communities →</div></div></a>
<a class="card" href="developers.html"><div class="kpi"><div class="label">Developers</div><div class="val green">{len(dev_index)}</div><div class="hint">official DLD project→developer attribution →</div></div></a></div>
"""
(ROOT/"index.html").write_text(page("Overview", "home", body, depth=0), encoding="utf-8")

# ============================================================ areas list (+ unmapped)
unm_rows = ""
for u in UNM.head(40).itertuples():
    sugg = f'<b class="seg-secondary">{esc(u.suggested_kotook_community)}</b>' if isinstance(u.suggested_kotook_community, str) and u.suggested_kotook_community else "<span class='muted'>—</span>"
    landflag = f' <span class="chip warn">{int(u.pct_land)}% land</span>' if pd.notna(u.pct_land) and u.pct_land >= 40 else ""
    unm_rows += (f"<tr><td class='name'>{esc(u.dld_area)}{landflag}</td><td class='num'>{fnum(u.tx_total)}</td>"
                 f"<td class='num'>{float(u.pct_of_market):.1f}%</td><td class='num'>{fmoney(u.value_bn_2023plus)}</td><td>{sugg}</td></tr>")
body = f"""<h1>Areas <span class="muted" style="font-size:16px">({len(area_index)})</span></h1>
<p class="sub">Each row is a DLD area mapped to a Kotook community. Open one to see off-plan/secondary stats and {SAMPLE} sample transactions.</p>
<div class="toolbar"><input id="q" class="search" placeholder="Search DLD area or Kotook community…">
<button class="filterbtn active" data-f="all">All</button>
<button class="filterbtn" data-f="ok">Confirmed</button>
<button class="filterbtn" data-f="warn">Review</button>
<button class="filterbtn" data-f="corrected">Corrected</button>
<span class="count" id="count"></span></div>
<div class="tablecard"><table><thead><tr><th>DLD area</th><th>Kotook community</th><th>Status</th><th class="num">Sales tx</th><th class="num">Value 2023+ (bn)</th></tr></thead><tbody id="rows"></tbody></table></div>
<h2 style="margin-top:34px">DLD areas <u>not</u> yet mapped to Kotook — candidates to review</h2>
<p class="sub">These {int(META.get("n_areas_unmapped",0))} areas make up the ~{100-cov:.0f}% of sales outside Kotook's community list. None is individually large; most are old/industrial or land-heavy (flagged). Two high-volume ones are established communities simply missing from Kotook (suggested).</p>
<div class="tablecard"><table><thead><tr><th>DLD area</th><th class="num">Sales tx</th><th class="num">% of market</th><th class="num">Value 2023+ (bn)</th><th>Suggested Kotook community</th></tr></thead><tbody>{unm_rows}</tbody></table></div>
<p class="note" style="margin-top:8px">These are not errors, gaps, or double-counts — they are simply outside the communities Kotook covers, so they don't enter Kotook's area stats. Showing the top 40 by volume.</p>
<script src="data/areas.js?v={BUILD}"></script><script src="assets/app_areas.js?v={BUILD}"></script>"""
(ROOT/"areas.html").write_text(page("Areas", "areas", body, depth=0), encoding="utf-8")

# ============================================================ developers list (+ unmapped)
dunm_rows = ""
for u in DUNM.head(30).itertuples():
    nm = esc(u.developer_name) if isinstance(u.developer_name, str) and u.developer_name else f"<span class='muted'>#{int(u.developer_number)}</span>"
    dunm_rows += (f"<tr><td class='name'>{nm}</td><td class='num'>{fnum(u.tx_total)}</td>"
                  f"<td class='num'>{float(u.pct_of_market):.1f}%</td><td class='num'>{fnum(u.tx_2023plus)}</td></tr>")
body = f"""<h1>Developers <span class="muted" style="font-size:16px">({len(dev_index)})</span></h1>
<p class="sub">Kotook developers, attributed via the official DLD <span class="mono">project_number → developer</span> chain. Each page splits off-plan vs secondary. See <a href="compare.html">Compare</a> for top-10 numbers vs market sources.</p>
<div class="toolbar"><input id="q" class="search" placeholder="Search developer…"><span class="count" id="count"></span></div>
<div class="tablecard"><table><thead><tr><th>Developer</th><th class="num">Sales tx</th><th class="num">Value 2023+ (bn)</th><th class="num">DLD entities</th></tr></thead><tbody id="rows"></tbody></table></div>
<h2 style="margin-top:34px">DLD developer entities not yet in the Kotook map — candidates</h2>
<p class="sub">{int(META.get("n_developers_unmapped",0))} DLD developer entities carry sales but aren't yet in the curated <span class="mono">entity_to_kotook.csv</span> map. Top by volume — add the relevant ones next refresh to raise developer coverage (currently {esc(META.get("developer_coverage_pct"))}% of sales).</p>
<div class="tablecard"><table><thead><tr><th>DLD developer entity</th><th class="num">Sales tx</th><th class="num">% of market</th><th class="num">Since 2023</th></tr></thead><tbody>{dunm_rows}</tbody></table></div>
<script src="data/developers.js?v={BUILD}"></script><script src="assets/app_devs.js?v={BUILD}"></script>"""
(ROOT/"developers.html").write_text(page("Developers", "developers", body, depth=0), encoding="utf-8")

# ============================================================ compare page
devs_sorted = sorted(dev_index, key=lambda x: -x['tx'])[:12]
crows = ""
for d in devs_sorted:
    name = d['name']; did = d['id']; b = BENCH.get(name)
    if b:
        extcell = f'{esc(b["n"])}<div class="note">{esc(b["note"])}</div>'
        srccell = f'<a href="{esc(b["url"])}" target="_blank" rel="noopener">source ↗</a>'
    else:
        extcell = '<span class="muted">— (verify via source)</span>'
        srccell = '<a href="https://dxbinteract.com/" target="_blank" rel="noopener">dxbinteract ↗</a>'
    drow = DST[(DST.kotook_developer_id == did) & (DST.segment == "all")].iloc[0]
    crows += (f"<tr><td class='name'><a href='d/{did}.html'>{esc(name)}</a></td>"
              f"<td class='num'>{fnum(drow.tx_2024)}</td><td class='num'>{fmoney(drow.value_bn_2024)}</td>"
              f"<td>{extcell}</td><td>{srccell}</td></tr>")
body = f"""<h1>Cross-check vs market sources</h1>
<p class="sub">Our DLD figures (official <span class="mono">project_number → developer</span> chain) next to published 2024 benchmarks, so the team can verify each number against an external source.</p>
<div class="callout"><h3>Read the numbers carefully</h3><div class="note">Figures differ by <b>scope</b>: we count <b>all registered sales</b> (off-plan + ready/resale) for the full calendar year; several sources count <b>off-plan only</b>, or developer <b>bookings</b>, or a different window. Closeness (not exact equality) is the signal. Developer attribution covers ~{esc(META.get("developer_coverage_pct"))}% of all sales — the share linked to a DLD-registered project (off-plan &amp; newer builds are well covered; many older secondary resales carry no project link).</div></div>
<div class="tablecard"><table><thead><tr><th>Developer</th><th class="num">Our 2024 sales</th><th class="num">Our 2024 value (bn)</th><th>External 2024 benchmark</th><th>Source</th></tr></thead><tbody>{crows}</tbody></table></div>
"""
(ROOT/"compare.html").write_text(page("Compare", "compare", body, depth=0), encoding="utf-8")

# ============================================================ market page
itbl = ""; iprev = None
for r in MIDX.itertuples():
    if iprev: gp = (r.index_all - iprev) / iprev * 100; gcol = "var(--green-d)" if gp >= 0 else "var(--red)"; g = f'<span style="color:{gcol};font-weight:700">{gp:+.1f}%</span>'
    else: g = "—"
    itbl += f"<tr><td>{int(r.year)}</td><td class='num'>{fnum(r.index_all)}</td><td class='num'>{fnum(r.index_flat)}</td><td class='num'>{fnum(r.index_villa)}</td><td class='num'>{g}</td></tr>"
    iprev = r.index_all
idx_bars = bars([(str(int(r.year)), int(r.index_all), fnum(round(r.index_all/1000))+"k") for r in MIDX.itertuples()])
dem_bars = bars([(str(int(r.year)), int(r.map_requests), fnum(r.map_requests)) for r in MDEM.itertuples()])
gsup_bars = bars([(str(int(r.year)), int(r.pipeline_units or 0), fnum(r.pipeline_units)) for r in MSUPY.head(5).itertuples()])
total_pipe = int(META.get("total_pipeline_units", 0))
units_total_city = int(META.get("existing_stock_units", 0))

# city-wide off-plan vs secondary, per year
myr_rows = ""
for y in sorted(int(x) for x in MYR.year.dropna().unique()):
    def mc(seg, col):
        m = MYR[(MYR.year == y) & (MYR.segment == seg)]
        return fnum(m.iloc[0][col]) if len(m) and pd.notna(m.iloc[0][col]) else "—"
    myr_rows += (f"<tr><td>{y}</td><td class='num seg-offplan'>{mc('offplan','tx')}</td><td class='num seg-secondary'>{mc('secondary','tx')}</td>"
                 f"<td class='num seg-offplan'>{mc('offplan','median_aed_sqft')}</td><td class='num seg-secondary'>{mc('secondary','median_aed_sqft')}</td></tr>")

tarows = "".join(f"<tr><td class='name'>{esc(r.dld_area)}</td><td class='num'>{fnum(r.pipeline_units)}</td><td class='num'>{fnum(r.pipeline_projects)}</td></tr>" for r in MSUPA.head(10).itertuples())
tsrows = "".join(f"<tr><td class='name'>{esc(r.dld_area)}</td><td class='num'>{fnum(r.existing_units)}</td><td class='num'>{(fnum(r.median_unit_size_sqm)+' m²') if pd.notna(r.median_unit_size_sqm) else '—'}</td></tr>" for r in MSTK[MSTK.existing_units >= 1000].head(12).itertuples())
scrows = "".join(f"<tr><td class='name'>{esc(r.community)}</td><td class='num'>~{float(r.aed_sqft):.1f}</td><td class='num'>{int(r.n_proj)}</td></tr>" for r in MSC.head(20).itertuples())

body = f"""<h1>Market — Dubai-wide statistics</h1>
<p class="sub">City-level indicators and the off-plan/secondary split for the whole market — context for the area &amp; developer pages.</p>
<h2>Off-plan vs secondary, per year (city-wide)</h2>
<div class="tablecard"><table><thead><tr><th>Year</th><th class="num seg-offplan">Off-plan tx</th><th class="num seg-secondary">Secondary tx</th><th class="num seg-offplan">Off-plan AED/sqft</th><th class="num seg-secondary">Secondary AED/sqft</th></tr></thead><tbody>{myr_rows}</tbody></table></div>
<p class="note" style="margin-top:8px">Counts = all registered sales; prices use the clean residential basis. Off-plan is Kotook's core market; this is the city-wide reference for every area page's split.</p>
<h2>Official DLD residential price index (avg price, AED)</h2>
<div class="chartcard">{idx_bars}</div>
<div class="tablecard" style="margin-top:14px"><table><thead><tr><th>Year</th><th class="num">All</th><th class="num">Flat</th><th class="num">Villa</th><th class="num">YoY (all)</th></tr></thead><tbody>{itbl}</tbody></table></div>
<div class="note" style="margin-top:8px">Source: DLD Residential Sale Index. The open dataset currently ends at <b>{int(MIDX.year.max())}</b>; later price growth is on each area page (from transactions).</div>
<h2>Demand proxy — DLD map / siteplan requests per year</h2>
<div class="chartcard">{dem_bars}</div>
<div class="note">Leading-indicator proxy for buyer/transaction activity. Latest year may be partial.</div>
<h2>City-wide upcoming supply (handovers by year)</h2>
<div class="chartcard">{gsup_bars}</div>
<div class="callout" style="margin-top:12px"><h3>Reality check on supply</h3><div class="note">This is the <b>DLD registered-project pipeline</b> — {fnum(total_pipe)} units across ACTIVE/NOT_STARTED projects (undated projects excluded from the by-year chart, so yearly bars are a <b>lower bound</b>). For context, Knight Frank/Fitch forecast ≈ <b>60,000–120,000</b> Dubai handovers in 2026. Treat per-year figures as a floor, not total market supply.</div></div>
<h2>Top areas by pipeline units</h2>
<div class="tablecard"><table><thead><tr><th>DLD area</th><th class="num">Pipeline units</th><th class="num">Projects</th></tr></thead><tbody>{tarows}</tbody></table></div>
<h2>Existing built stock — top areas (units registry)</h2>
<p class="note">Total titled units in the DLD <b>units</b> registry: <b>{fnum(units_total_city)}</b>. This is <b>existing stock</b> — the complement to the forward-looking pipeline above.</p>
<div class="tablecard"><table><thead><tr><th>DLD area</th><th class="num">Existing units</th><th class="num">Median size</th></tr></thead><tbody>{tsrows}</tbody></table></div>
<h2>Typical service charge by community (2023)</h2>
<div class="tablecard"><table><thead><tr><th>Community</th><th class="num">AED/sqft</th><th class="num">Projects</th></tr></thead><tbody>{scrows}</tbody></table></div>
<div class="callout" style="margin-top:8px"><h3>How to read this</h3><div class="note">Source: DLD owner-association <b>service charges</b>. Per project = sum of its ~20 service categories; community figure = <b>median across projects</b> (residential usage). Latest full year is <b>2023</b>. Higher = premium/waterfront (Palm, Downtown), lower = mid-market (JVC, Marina).</div></div>
"""
(ROOT/"market.html").write_text(page("Market", "market", body, depth=0), encoding="utf-8")

# ============================================================ about / method
body = f"""<h1>Method &amp; data sources</h1>
<p class="sub">How these numbers are produced, segmented, and validated.</p>
<div class="card"><h2 style="margin-top:0">One pipeline → one database</h2>
<p>Every number on this site comes from a single deliverable, <span class="mono">kotook_market.duckdb</span>, produced by the <b>kotook_pipeline</b> notebook from the latest DLD open-data dump. To refresh each year: drop the new DLD CSVs into <span class="mono">puls_data/</span> and run the notebook — it auto-picks the newest valid file per dataset, recomputes every statistic, runs a validation gate, and writes the database + CSV/parquet exports. This site then just renders that database.</p>
<h2>Off-plan vs secondary vs combined</h2>
<p>Every statistic is split three ways using the DLD <span class="mono">reg_type_en</span> field: <b class="seg-offplan">off-plan</b> (primary / developer sales), <b class="seg-secondary">secondary</b> (ready / resale), and <b>combined</b>. Off-plan is <b>{op_share_23}%</b> of sales since 2023 — Kotook's core market. Price growth (YoY) is read off the secondary segment, which strips off-plan launch-mix noise.</p>
<h2>Source &amp; the validation field</h2>
<p>Dubai Land Department public <b>Transactions</b> — {fnum(META.get("total_sales"))} <b>Sales</b> records (mortgages/gifts excluded). Area mapping is validated against the dominant <span class="mono">master_project_en</span> inside each DLD area; developer attribution follows the official <span class="mono">project_number → developer</span> chain.</p>
<h2>Coverage</h2>
<p>Area mapping covers <b>{cov:.0f}%</b> of all sales ({len(area_index)} Kotook communities); the rest are listed on the <a href="areas.html">Areas</a> page as review candidates. Developer attribution covers <b>{esc(META.get("developer_coverage_pct"))}%</b> of sales (the share linked to a DLD-registered project).</p>
<h2>Data cleaning &amp; outliers</h2>
<ul>
<li><b>No duplicates / no missing IDs</b> — every transaction has a unique <span class="mono">transaction_id</span>.</li>
<li><b>Price metrics use a clean residential basis</b> — median AED/sqft, YoY, off-plan premium and share use only <b>Unit/Villa</b> in a plausible AED/m² band (drops Land + commercial + impossible prices, ~{esc(META.get("clean_drop_pct"))}% of rows). Because we use the <b>median</b>, headline numbers barely move — the cleaning is for correctness, not to chase a number.</li>
<li><b>Value sums stay over all sales</b>, but bulk/portfolio deals above AED 500M (~{esc(META.get("bulk_value_pct"))}% of the 2023+ total) get an <b>"excl. bulk &gt;500M"</b> figure on each value card.</li>
<li><b>Counts</b> always cover all registered sales.</li>
</ul>
<h2>What to validate</h2>
<p>For each area and developer we list <b>{SAMPLE} recent transactions</b> with their segment. Confirm that project / building / master names genuinely belong to the stated Kotook community or developer. In Kotook, the area mapping is stored on <span class="mono">CityArea.old_name</span> (en).</p>
</div>"""
(ROOT/"about.html").write_text(page("Method", "about", body, depth=0), encoding="utf-8")

print(f"areas={len(area_index)}  developers={len(dev_index)}  coverage={cov:.0f}%  confirmed={n_ok} review={n_warn}  "
      f"unmapped_areas={int(META.get('n_areas_unmapped',0))}  build={META.get('build_date')}")
