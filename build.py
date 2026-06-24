#!/usr/bin/env python3
# Builds the Kotook DLD-validation static site (GitHub Pages friendly).
import duckdb, pandas as pd, re, json, html, datetime, pathlib

ROOT = pathlib.Path(__file__).parent
DLD  = "/Users/mohsensalare/Desktop/dld_transactions_analysis/dld_transactions.duckdb"
REP  = "/Users/mohsensalare/Desktop/Kotook_Data_Report_EN.xlsx"
SM   = "/Users/mohsensalare/Desktop/dld_transactions_analysis/DLD_Kotook_Simple_Matches.xlsx"
con  = duckdb.connect(DLD, read_only=True)
TODAY= datetime.date.today().isoformat()
BUILD= datetime.datetime.now().strftime("%Y%m%d%H%M%S")  # cache-buster: changes every build

# ---------- helpers ----------
def esc(x):
    if x is None: return ""
    try:
        if pd.isna(x): return ""
    except (TypeError,ValueError): pass
    return html.escape(str(x))
def fdate(x):
    try:
        if pd.isna(x): return ""
    except (TypeError,ValueError): pass
    return str(x)[:10]
def fnum(n):
    try: return f"{int(round(float(n))):,}"
    except: return "—"
def fmoney(n):
    try:
        n=float(n)
        if n!=n: return "0.00"
        return f"{n:,.2f}"
    except: return "—"
def slug(s):
    s=re.sub(r'[^a-z0-9]+','-',str(s).lower()).strip('-'); return s or 'x'
def norm(s):
    return re.sub(r'[^a-z0-9]','',str(s).lower()) if s else ''
ALIAS={'downtowndubai':'downtown','dubaiworldcentral':'dubaisouth','siliconoasis':'dubaisiliconoasis',
       'liwan1':'liwan','jvcjumeirahvillagecircle':'jumeirahvillagecircle',
       'jvtjumeirahvillagetriangle':'jumeirahvillagetriangle','jumeirahlaketowersjlt':'jumeirahlaketowers',
       'jumeirahlakestowers':'jumeirahlaketowers'}
def key(s):
    k=norm(s); return ALIAS.get(k,k)
def agree(a,b):
    if not a or not b: return False
    ka,kb=key(a),key(b)
    return ka==kb or ka in kb or kb in ka

def page(title, active, body, depth=0):
    up = "../"*depth
    nav=[("Overview","index.html","home"),("Areas","areas.html","areas"),
         ("Developers","developers.html","developers"),("Market","market.html","market"),
         ("Compare","compare.html","compare"),("Method","about.html","about")]
    navhtml="".join(f'<a class="{ "active" if k==active else "" }" href="{up}{href}">{esc(label)}</a>' for label,href,k in nav)
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
source: Dubai Land Department transactions (Sales) · evidence field: <b>master_project_en</b></div></footer>
</body></html>"""

def bars(rows):  # rows: list of (year, value, label)
    mx=max([r[1] for r in rows] or [1]) or 1
    cells=""
    for yr,v,lab in rows:
        h=max(2,round(100*v/mx))
        cells+=f'<div class="bar"><div class="v">{esc(lab)}</div><div class="col" style="height:{h}%"></div><div class="yr">{esc(yr)}</div></div>'
    return f'<div class="bars">{cells}</div>'

def kpi(label,val,hint="",green=False):
    g=" green" if green else ""
    h=f'<div class="hint">{esc(hint)}</div>' if hint else ""
    return f'<div class="card kpi"><div class="label">{esc(label)}</div><div class="val{g}">{esc(val)}</div>{h}</div>'

# ---------- load mappings ----------
alld=pd.read_excel(REP,'All DLD Areas (297)')
real_areas=set(con.sql("SELECT DISTINCT area_name_en FROM transactions").df()['area_name_en'].dropna())

# corrections applied (the validated 5)
OVERRIDE={  # dld area -> (kotook name, kotook id or None, corrected_flag, missing_flag)
 'Al Barsha South Fourth':('JVC (Jumeirah Village Circle)',5,True,False),
 'Al Barsha South Fifth' :('JVT Jumeirah Village Triangle',6,True,False),
 'Al Thanyah Fifth'      :('Jumeirah Lake Towers - JLT',61,True,False),
 'Al Thanyah Third'      :('The Greens / The Views',None,True,True),
 'Al Thanayah Fourth'    :('Emirates Living (Springs/Meadows)',None,True,True),
}

area_rows=[]
for _,r in alld.iterrows():
    dld=r['Official DLD name']
    if dld not in real_areas: continue
    kname=r.get('Name in Kotook'); kid=r.get('ID in Kotook')
    if (kname is None or (isinstance(kname,float) and pd.isna(kname))): continue
    corrected=missing=False
    if dld in OVERRIDE:
        kname,kid,corrected,missing=OVERRIDE[dld]
    kid=None if (kid is None or (isinstance(kid,float) and pd.isna(kid))) else int(kid)
    area_rows.append(dict(dld=dld,kname=str(kname),kid=kid,corrected=corrected,missing=missing))

# developer attribution via the OFFICIAL DLD chain:
#   transaction.project_number -> projects(developer_number) -> entity_to_kotook map (-> Kotook developer)
PULS="/Users/mohsensalare/Desktop/dld_transactions_analysis/puls_data"
PROJ=f"{PULS}/projects_2026-05-21_02-07-22_1.csv"
ENT=f"{PULS}/entity_to_kotook.csv"
con.sql(f"CREATE OR REPLACE TEMP TABLE proj AS SELECT TRIM(CAST(project_number AS VARCHAR)) pn, CAST(developer_number AS BIGINT) devno FROM read_csv_auto('{PROJ}', sample_size=-1) WHERE project_number IS NOT NULL")
con.sql(f"CREATE OR REPLACE TEMP TABLE entk AS SELECT CAST(devno AS BIGINT) devno, dn, kotook, CAST(kid AS BIGINT) kid FROM read_csv_auto('{ENT}', sample_size=-1)")
con.sql("""CREATE OR REPLACE TEMP VIEW dev_tx AS
  SELECT t.*, e.kid, e.kotook AS dev_name, e.dn AS dld_entity
  FROM transactions t JOIN proj p ON p.pn=TRIM(CAST(t.project_number AS VARCHAR))
  JOIN entk e ON e.devno=p.devno WHERE t.trans_group_en='Sales'""")
# Published 2024 external benchmarks (scope/period noted per row) for cross-check links
BENCH={
 'Emaar Properties':{'n':'28,521','note':'2024 off-plan units (Primo Capital); AED 65.4bn dev sales (Emaar)','url':'https://primocapital.ae/blog/10-top-performing-uae-real-estate-developers-of-2024-key-stats-and-success'},
 'DAMAC Properties':{'n':'16,463','note':'2024 off-plan units (Primo Capital)','url':'https://primocapital.ae/blog/10-top-performing-uae-real-estate-developers-of-2024-key-stats-and-success'},
 'sobha':{'n':'10,384','note':'2024 off-plan units (Primo); AED 23bn sales (Sobha)','url':'https://sobharealty.com/media-center/press-releases/sobha-realty-records-historic-aed-23-billion-in-sales-for-2024/'},
 'Binghatti':{'n':'7,259','note':'2024 off-plan units (Primo Capital); AED 10.86bn','url':'https://primocapital.ae/blog/dubai-apartments-hit-6786-billion-in-2024-a-look-at-developers-market-share'},
 'Azizi developments':{'n':'10,229','note':'2024 units sold (Azizi official); >AED 10bn','url':'https://www.zawya.com/en/press-release/companies-news/azizi-developments-delivers-19-projects-and-sells-over-10-000-units-in-2024-krao9vmx'},
 'Danube Properties':{'n':'6,334','note':'2024 transferred sales; AED 9.42bn (Primo Capital)','url':'https://primocapital.ae/blog/dubai-apartments-hit-6786-billion-in-2024-a-look-at-developers-market-share'},
 'Nshama':{'n':'3,024','note':'2024 transactions; AED 4.53bn; 2% share (Primo Capital)','url':'https://primocapital.ae/blog/dubai-apartments-hit-6786-billion-in-2024-a-look-at-developers-market-share'},
 'Samana Developers':{'n':'~4.4% off-plan share','note':'2024; AED 7bn revenue (Zawya)','url':'https://www.zawya.com/en/projects/construction/dubais-samana-targets-24bn-sales-in-2024-amid-buoyant-market-conditions-l7qp00it'},
}

# ---- analytics precompute (supply / valuation / index / demand) ----
VAL=f"{PULS}/valuation_2026-05-21_02-09-14_1.csv"
IDX=f"{PULS}/residential_sale_index_2026-04-29_14-02-42_1.csv"
MAPR=f"{PULS}/map_requests_2026-06-01_10-45-55_1.csv"
con.sql(f"""CREATE OR REPLACE TEMP TABLE projfull AS
  SELECT area_name_en, CAST(developer_number AS BIGINT) devno, COALESCE(no_of_units,0) units,
         project_status, TRY_CAST(completion_date AS DATE) cdate
  FROM read_csv_auto('{PROJ}', sample_size=-1)""")
con.sql("""CREATE OR REPLACE TEMP TABLE projkid AS
  SELECT e.kid, pf.units, pf.project_status, pf.cdate FROM projfull pf JOIN entk e ON e.devno=pf.devno""")
con.sql(f"""CREATE OR REPLACE TEMP TABLE valarea AS
  SELECT area_name_en, MEDIAN(actual_worth/NULLIF(procedure_area,0)) val_sqm
  FROM read_csv_auto('{VAL}', sample_size=-1)
  WHERE procedure_area>0 AND actual_worth>0 AND TRY_CAST(instance_date AS DATE)>=DATE '2024-01-01'
  GROUP BY 1 HAVING COUNT(*)>=20""")
SQFT=10.7639
def sqlq(s):  # safe single-quoted SQL literal
    return "'"+str(s).replace("'","''")+"'"
def supply_block(where, param):  # returns (pipeline_units, projects, [(yr,units)...])
    s=con.sql(f"SELECT COALESCE(SUM(units),0) u, COUNT(*) p FROM {where} WHERE {param} AND project_status IN ('ACTIVE','NOT_STARTED')").df().iloc[0]
    h=con.sql(f"SELECT EXTRACT(year FROM cdate) y, SUM(units) u FROM {where} WHERE {param} AND project_status IN ('ACTIVE','NOT_STARTED') AND cdate>=DATE '2026-01-01' GROUP BY 1 ORDER BY 1 LIMIT 4").df()
    return int(s['u'] or 0), int(s['p'] or 0), [(str(int(r.y)),int(r.u or 0)) for r in h.itertuples() if pd.notna(r.y)]
def statline(items):  # items: list of (label, value) -> compact stat strip
    return '<div class="card statrow">'+"".join(f'<div><span class="lbl">{esc(l)}</span><span class="v">{v}</span></div>' for l,v in items)+'</div>'

# ---------- per-area pages ----------
SAMPLE=20
area_index=[]
for a in area_rows:
    dld=a['dld']
    s=con.sql("SELECT COUNT(*) tx, SUM(CASE WHEN transaction_year>=2023 THEN 1 ELSE 0 END) tx23,"
              "ROUND(SUM(CASE WHEN transaction_year>=2023 THEN actual_worth ELSE 0 END)/1e9,2) val23 "
              "FROM transactions WHERE area_name_en=? AND trans_group_en='Sales'",params=[dld]).df().iloc[0]
    off=con.sql("SELECT ROUND(100.0*SUM(CASE WHEN reg_type_en='Off-Plan Properties' THEN 1 ELSE 0 END)/NULLIF(COUNT(*),0)) p "
                "FROM transactions WHERE area_name_en=? AND trans_group_en='Sales' AND transaction_year>=2023",params=[dld]).df().iloc[0]['p']
    yr=con.sql(f"SELECT transaction_year yr, COUNT(*) tx, ROUND(MEDIAN(meter_sale_price)/{SQFT}) sqft, "
               f"ROUND(MEDIAN(CASE WHEN reg_type_en='Existing Properties' THEN meter_sale_price END)/{SQFT}) rsqft, "
               "ROUND(100.0*SUM(CASE WHEN reg_type_en='Off-Plan Properties' THEN 1 ELSE 0 END)/COUNT(*)) op "
               "FROM transactions WHERE area_name_en=? AND trans_group_en='Sales' "
               "AND transaction_year BETWEEN 2019 AND 2026 GROUP BY 1 ORDER BY 1",params=[dld]).df()
    oprem=con.sql("SELECT ROUND(MEDIAN(CASE WHEN reg_type_en='Off-Plan Properties' THEN meter_sale_price END)) op_sqm, "
               "ROUND(MEDIAN(CASE WHEN reg_type_en='Existing Properties' THEN meter_sale_price END)) rd_sqm "
               "FROM transactions WHERE area_name_en=? AND trans_group_en='Sales' AND transaction_year>=2023",params=[dld]).df().iloc[0]
    mkt_sqm=con.sql("SELECT ROUND(MEDIAN(meter_sale_price)) m FROM transactions WHERE area_name_en=? AND trans_group_en='Sales' AND transaction_year>=2024",params=[dld]).df().iloc[0]['m']
    val_sqm=con.sql(f"SELECT ROUND(val_sqm) v FROM valarea WHERE area_name_en={sqlq(dld)}").df()
    val_sqm=(val_sqm.iloc[0]['v'] if len(val_sqm) else None)
    pipe_u,pipe_p,hands=supply_block("projfull", f"area_name_en={sqlq(dld)}")
    masters=con.sql("SELECT master_project_en m, COUNT(*) c FROM transactions WHERE area_name_en=? AND trans_group_en='Sales' "
                    "AND master_project_en IS NOT NULL AND master_project_en<>'' GROUP BY 1 ORDER BY c DESC LIMIT 3",params=[dld]).df()
    samp=con.sql("SELECT area_name_en a, instance_date d, project_name_en p, building_name_en b, "
                 "nearest_landmark_en lm, nearest_metro_en mt, rooms_en r, procedure_area ar, actual_worth w "
                 "FROM transactions WHERE area_name_en=? AND trans_group_en='Sales' "
                 "ORDER BY instance_date DESC LIMIT ?",params=[dld,SAMPLE]).df()
    dom = masters.iloc[0]['m'] if len(masters) else None
    if a['missing']: status,stxt=('warn','Community to add')
    elif agree(a['kname'],dom): status,stxt=('ok','Confirmed')
    elif dom is None: status,stxt=('warn','Manual review')
    else: status,stxt=('warn','Review name')
    _v=s['val23']; sl=slug(dld); a['slug']=sl; a['tx']=int(s['tx'] or 0); a['val23']=0.0 if pd.isna(_v) else float(_v)
    a['status']=status; a['stxt']=stxt; a['dom']=dom

    # build detail
    chips=f'<span class="chip {status}">{esc(stxt)}</span>'
    if a['corrected'] and not a['missing']: chips+=' <span class="chip fix">Corrected mapping</span>'
    yrows=[(str(int(x.yr)),int(x.tx),fnum(x.tx)) for x in yr.itertuples()]
    # price & off-plan by year. Level = all-sales median (matches portal indices);
    # YoY = ready/secondary market, which removes off-plan launch-mix noise.
    ptbl=""; prev=None
    for x in yr.itertuples():
        sqftv=fnum(x.sqft) if pd.notna(x.sqft) else "—"
        opv=f"{int(x.op)}%" if pd.notna(x.op) else "—"
        if prev and pd.notna(x.rsqft):
            gp=(x.rsqft-prev)/prev*100; gcol="var(--green-d)" if gp>=0 else "var(--red)"
            ghtml=f'<span style="color:{gcol};font-weight:700">{gp:+.1f}%</span>'
        else: ghtml="—"
        ptbl+=f"<tr><td>{int(x.yr)}</td><td class='num'>{fnum(x.tx)}</td><td class='num'>{sqftv}</td><td class='num'>{ghtml}</td><td class='num'>{opv}</td></tr>"
        if pd.notna(x.rsqft): prev=x.rsqft
    # absorption + supply card
    recent=yr[yr['yr'].between(2023,2025)]['tx'].sum(); avg_annual=recent/3 if recent else 0
    absorp=(pipe_u/avg_annual) if avg_annual else None
    hbars=bars([(y,u,fnum(u)) for y,u in hands]) if hands else "<span class='muted'>no dated handovers in DLD registry</span>"
    supply_card=(f'<div class="grid k3">{kpi("Pipeline units",fnum(pipe_u),"under construction / planned")}'
                 f'{kpi("Pipeline projects",fnum(pipe_p))}'
                 f'{kpi("Years of supply",(f"{absorp:.1f}" if absorp else "—"),"pipeline ÷ avg annual sales")}</div>'
                 f'<div class="chartcard" style="margin-top:14px"><div class="note" style="margin-bottom:6px">Units handing over by year — <b>DLD registered-project pipeline (lower bound; undated projects excluded)</b></div>{hbars}</div>')
    # off-plan premium + valuation gap
    op_sqm=oprem['op_sqm']; rd_sqm=oprem['rd_sqm']
    prem=f"{(op_sqm-rd_sqm)/rd_sqm*100:+.0f}%" if (pd.notna(op_sqm) and pd.notna(rd_sqm) and rd_sqm) else "—"
    valgap=f"{(mkt_sqm-val_sqm)/val_sqm*100:+.0f}%" if (val_sqm and pd.notna(mkt_sqm)) else "—"
    stats=statline([("Off-plan premium (2023+)",prem),("Market vs DLD valuation (2024+)",valgap),
                    ("Median AED/m² (2024+)",fnum(mkt_sqm) if pd.notna(mkt_sqm) else "—")])
    ev=" · ".join(f"<b>{esc(m.m)}</b> ({fnum(m.c)})" for m in masters.itertuples()) or "<span class='muted'>no master label</span>"
    miss_note=""
    if a['missing']:
        miss_note=f'<div class="callout" style="border-color:var(--amber-soft);background:var(--amber-soft)"><h3 style="color:var(--amber)">Not yet a Kotook community</h3>'\
                  f'<div class="note">DLD area <b>{esc(dld)}</b> is actually <b>{esc(a["kname"])}</b> — a large established community that is <b>missing</b> from Kotook. Recommend adding it. Validate with the 20 sample transactions below.</div></div>'
    trs=""
    for x in samp.itertuples():
        d=fdate(x.d)
        trs+=f"<tr><td class='match'>{esc(x.a)}</td><td class='mono'>{esc(d)}</td><td class='name'>{esc(x.p)}</td><td>{esc(x.b)}</td>"\
             f"<td>{esc(x.lm)}</td><td class='muted'>{esc(x.mt)}</td>"\
             f"<td>{esc(x.r)}</td><td class='num'>{fnum(x.ar)}</td><td class='num'>{fnum(x.w)}</td></tr>"
    kpis=f'<div class="grid k4">{kpi("Sales transactions",fnum(a["tx"]))}{kpi("Since 2023",fnum(s["tx23"]))}'\
         f'{kpi("Value 2023+ (bn AED)",fmoney(a["val23"]))}{kpi("Off-plan 2023+",(fnum(off)+"%") if pd.notna(off) else "—")}</div>'
    body=f"""<div class="crumb"><a href="../areas.html">Areas</a> / {esc(dld)}</div>
<h1>{esc(dld)} {chips}</h1>
<p class="sub">Mapped to Kotook community: <b>{esc(a['kname'])}</b>{(' · id '+str(a['kid'])) if a['kid'] else ''}</p>
{miss_note}
{kpis}
<h2>Sales transactions per year</h2>
<div class="chartcard">{bars(yrows)}</div>
<h2>Price &amp; off-plan by year</h2>
<div class="tablecard"><table><thead><tr><th>Year</th><th class="num">Sales</th><th class="num">AED/sqft (median, all)</th><th class="num">YoY (ready)</th><th class="num">Off-plan</th></tr></thead><tbody>{ptbl}</tbody></table></div>
<p class="note" style="margin-top:8px">Level = median AED/sqft of all sales (tracks portal price indices). YoY = ready/secondary-market growth — it strips out off-plan launch-mix noise, so a one-off luxury off-plan wave can't show up as a fake price swing.</p>
<div style="margin-top:12px">{stats}</div>
<h2>Supply &amp; absorption</h2>
{supply_card}
<h2>Evidence — DLD <span class="mono">master_project_en</span> inside this area</h2>
<div class="card evid">{ev}<div class="note" style="margin-top:8px">Auto-status compares the Kotook community name to the dominant master_project above. Reviewers should confirm using the sample below.</div></div>
<h2>{SAMPLE} sample transactions to validate</h2>
<p class="note">Why these rows: every transaction below has DLD <span class="mono">area_name_en = "{esc(dld)}"</span> — that is the selection rule for this area (highlighted column).</p>
<div class="tablecard"><table><thead><tr><th class="match">Area (DLD)</th><th>Date</th><th>Project</th><th>Building</th><th>Nearest landmark</th><th>Nearest metro</th><th>Rooms</th><th class="num">Size m²</th><th class="num">Price AED</th></tr></thead><tbody>{trs}</tbody></table></div>
"""
    (ROOT/"a"/f"{sl}.html").write_text(page(dld,"areas",body,depth=1),encoding="utf-8")
    area_index.append(dict(dld=dld,kname=a['kname'],kid=a['kid'],tx=a['tx'],val23=a['val23'],
                           status=status,stxt=stxt,corrected=a['corrected'],missing=a['missing'],slug=sl))

# ---------- per-developer pages (official DLD chain) ----------
devs=con.sql("SELECT kid, MAX(dev_name) dev_name, COUNT(*) tx, "
             "SUM(CASE WHEN transaction_year>=2023 THEN 1 ELSE 0 END) tx23, "
             "ROUND(SUM(CASE WHEN transaction_year>=2023 THEN actual_worth ELSE 0 END)/1e9,2) val23, "
             "COUNT(DISTINCT dld_entity) nent "
             "FROM dev_tx GROUP BY kid HAVING COUNT(*)>0 ORDER BY tx DESC").df()
dev_index=[]; our24={}
for x in devs.itertuples():
    did=int(x.kid); name=str(x.dev_name)
    ents=con.sql("SELECT DISTINCT dld_entity e FROM dev_tx WHERE kid=? ORDER BY 1",params=[did]).df()['e'].tolist()
    yr=con.sql(f"SELECT transaction_year yr, COUNT(*) tx, ROUND(MEDIAN(meter_sale_price)/{SQFT}) sqft, "
               f"ROUND(MEDIAN(CASE WHEN reg_type_en='Existing Properties' THEN meter_sale_price END)/{SQFT}) rsqft, "
               "ROUND(100.0*SUM(CASE WHEN reg_type_en='Off-Plan Properties' THEN 1 ELSE 0 END)/COUNT(*)) op "
               "FROM dev_tx WHERE kid=? AND transaction_year BETWEEN 2019 AND 2026 GROUP BY 1 ORDER BY 1",params=[did]).df()
    o=con.sql("SELECT SUM(CASE WHEN transaction_year=2024 THEN 1 ELSE 0 END) c24, ROUND(SUM(CASE WHEN transaction_year=2024 THEN actual_worth ELSE 0 END)/1e9,1) v24, "
              "ROUND(100.0*SUM(CASE WHEN transaction_year>=2023 AND reg_type_en='Off-Plan Properties' THEN 1 ELSE 0 END)/NULLIF(SUM(CASE WHEN transaction_year>=2023 THEN 1 ELSE 0 END),0)) opshare "
              "FROM dev_tx WHERE kid=?",params=[did]).df().iloc[0]
    our_c=int(o['c24'] or 0); our_v=0.0 if pd.isna(o['v24']) else float(o['v24']); our24[did]=(our_c,our_v)
    dopshare=o['opshare']; dpipe_u,dpipe_p,dhands=supply_block("projkid", f"kid={did}")
    areas_=con.sql("SELECT area_name_en a, COUNT(*) c FROM dev_tx WHERE kid=? GROUP BY 1 ORDER BY c DESC LIMIT 6",params=[did]).df()
    samp=con.sql("SELECT dld_entity de, instance_date d, project_name_en p, building_name_en b, area_name_en a, "
                 "nearest_landmark_en lm, nearest_metro_en mt, rooms_en r, procedure_area ar, actual_worth w "
                 "FROM dev_tx WHERE kid=? ORDER BY instance_date DESC LIMIT ?",params=[did,SAMPLE]).df()
    yrows=[(str(int(t.yr)),int(t.tx),fnum(t.tx)) for t in yr.itertuples()]
    # price growth by year + supply. Level = all-sales median; YoY = ready/secondary (mix-stable).
    ptbl=""; prev=None
    for t in yr.itertuples():
        sqftv=fnum(t.sqft) if pd.notna(t.sqft) else "—"
        opv=f"{int(t.op)}%" if pd.notna(t.op) else "—"
        if prev and pd.notna(t.rsqft):
            gp=(t.rsqft-prev)/prev*100; gcol="var(--green-d)" if gp>=0 else "var(--red)"
            ghtml=f'<span style="color:{gcol};font-weight:700">{gp:+.1f}%</span>'
        else: ghtml="—"
        ptbl+=f"<tr><td>{int(t.yr)}</td><td class='num'>{fnum(t.tx)}</td><td class='num'>{sqftv}</td><td class='num'>{ghtml}</td><td class='num'>{opv}</td></tr>"
        if pd.notna(t.rsqft): prev=t.rsqft
    dstat=statline([("Off-plan share (2023+)", f"{int(dopshare)}%" if pd.notna(dopshare) else "—")])
    dhbars=bars([(y,u,fnum(u)) for y,u in dhands]) if dhands else "<span class='muted'>no dated handovers in DLD registry</span>"
    dsupply=(f'<div class="grid k2">{kpi("Pipeline units",fnum(dpipe_u),"under construction / planned")}{kpi("Pipeline projects",fnum(dpipe_p))}</div>'
             f'<div class="chartcard" style="margin-top:14px"><div class="note" style="margin-bottom:6px">Units handing over by year — DLD registered-project pipeline (lower bound)</div>{dhbars}</div>')
    entpills="".join(f'<span class="pill">{esc(e)}</span>' for e in ents) or "<span class='muted'>—</span>"
    areapills=" · ".join(f"<b>{esc(t.a)}</b> ({fnum(t.c)})" for t in areas_.itertuples())
    trs=""
    for t in samp.itertuples():
        d=fdate(t.d)
        trs+=f"<tr><td class='match'>{esc(t.de)}</td><td class='mono'>{esc(d)}</td><td class='name'>{esc(t.p)}</td><td>{esc(t.b)}</td>"\
             f"<td class='muted'>{esc(t.a)}</td><td>{esc(t.lm)}</td><td class='muted'>{esc(t.mt)}</td>"\
             f"<td>{esc(t.r)}</td><td class='num'>{fnum(t.ar)}</td><td class='num'>{fnum(t.w)}</td></tr>"
    b=BENCH.get(name); xcheck=""
    if b:
        xcheck=(f'<div class="callout"><h3>External cross-check (2024)</h3>'
                f'<div class="note">Our 2024 sales (official DLD chain): <b>{fnum(our_c)}</b> · ~AED {fmoney(our_v)}bn &nbsp;·&nbsp; '
                f'Independent benchmark: <b>{esc(b["n"])}</b> — {esc(b["note"])} '
                f'<a href="{esc(b["url"])}" target="_blank" rel="noopener">source ↗</a></div></div>')
    kpis=(f'<div class="grid k4">{kpi("Sales transactions",fnum(x.tx))}{kpi("Since 2023",fnum(x.tx23))}'
          f'{kpi("Value 2023+ (bn AED)",fmoney(x.val23))}{kpi("DLD developer entities",fnum(x.nent))}</div>')
    body=f"""<div class="crumb"><a href="../developers.html">Developers</a> / {esc(name)}</div>
<h1>{esc(name)} <span class="chip ok">Official DLD attribution</span></h1>
<p class="sub">Kotook developer id {did} · attribution via DLD <span class="mono">project_number → developer</span> (official projects registry).</p>
{kpis}
{xcheck}
<h2>Sales transactions per year</h2><div class="chartcard">{bars(yrows)}</div>
<h2>Price growth &amp; off-plan by year</h2>
<div class="tablecard"><table><thead><tr><th>Year</th><th class="num">Sales</th><th class="num">AED/sqft (median, all)</th><th class="num">YoY (ready)</th><th class="num">Off-plan</th></tr></thead><tbody>{ptbl}</tbody></table></div>
<p class="note" style="margin-top:8px">Level = median AED/sqft of all sales; YoY = ready/secondary-market growth (strips off-plan launch-mix noise).</p>
<div style="margin-top:12px">{dstat}</div>
<h2>Supply pipeline</h2>{dsupply}
<h2>Top communities</h2><div class="card evid">{areapills or "<span class='muted'>—</span>"}</div>
<h2>DLD developer entities mapped to this brand</h2><div class="card">{entpills}</div>
<h2>{SAMPLE} sample transactions to validate</h2>
<p class="note">Why these rows: each transaction's project is officially registered in DLD to the developer entity in the highlighted column, which rolls up to <b>{esc(name)}</b>.</p>
<div class="tablecard"><table><thead><tr><th class="match">DLD developer (official)</th><th>Date</th><th>Project</th><th>Building</th><th>Community</th><th>Nearest landmark</th><th>Nearest metro</th><th>Rooms</th><th class="num">Size m²</th><th class="num">Price AED</th></tr></thead><tbody>{trs}</tbody></table></div>
"""
    sl=str(did)
    (ROOT/"d"/f"{sl}.html").write_text(page(name,"developers",body,depth=1),encoding="utf-8")
    dev_index.append(dict(id=did,name=name,tx=int(x.tx),val23=float(x.val23 or 0),nproj=int(x.nent),slug=sl,our2024=our_c,bench=bool(b)))

# ---------- list data (JS) ----------
(ROOT/"data"/"areas.js").write_text("window.AREAS="+json.dumps(area_index,ensure_ascii=False)+";",encoding="utf-8")
(ROOT/"data"/"developers.js").write_text("window.DEVS="+json.dumps(dev_index,ensure_ascii=False)+";",encoding="utf-8")

# ---------- overview ----------
g=con.sql("SELECT COUNT(*) tx, ROUND(SUM(actual_worth)/1e9,0) val FROM transactions WHERE trans_group_en='Sales'").df().iloc[0]
g23=con.sql("SELECT COUNT(*) tx FROM transactions WHERE trans_group_en='Sales' AND transaction_year>=2023").df().iloc[0]['tx']
mapped_tx=sum(a['tx'] for a in area_index if not a['missing'])
cov=round(100*mapped_tx/int(g['tx']))
gyr=con.sql("SELECT transaction_year yr, COUNT(*) tx FROM transactions WHERE trans_group_en='Sales' AND transaction_year BETWEEN 2019 AND 2026 GROUP BY 1 ORDER BY 1").df()
gyrows=[(str(int(t.yr)),int(t.tx),fnum(t.tx)) for t in gyr.itertuples()]
n_ok=sum(1 for a in area_index if a['status']=='ok'); n_warn=sum(1 for a in area_index if a['status']=='warn')
cov_hint=fnum(mapped_tx)+" of "+fnum(g["tx"])
kpis=(f'<div class="grid k4">{kpi("DLD sales transactions",fnum(g["tx"]))}'
      f'{kpi("Mapped to Kotook areas",str(cov)+"%",cov_hint,green=True)}'
      f'{kpi("Areas under review",fnum(len(area_index)))}{kpi("Developers under review",fnum(len(dev_index)))}</div>')
corr_list="".join(f"<li><b>{esc(a['dld'])}</b> → {esc(a['kname'])}{(' (id '+str(a['kid'])+')') if a['kid'] else ' — <i>add as new community</i>'}</li>"
                  for a in area_index if a['corrected'])
body=f"""<h1>DLD ↔ Kotook data validation</h1>
<p class="sub">A working dataset for the team to review and confirm. Every area and developer carries {SAMPLE} sample transactions for manual validation. White = neutral, <b style="color:var(--green-d)">green = confirmed</b>, amber = needs review.</p>
{kpis}
<div class="legend"><span><i style="background:var(--green)"></i>Confirmed ({n_ok})</span><span><i style="background:var(--amber)"></i>Needs review ({n_warn})</span><span><i style="background:var(--green-d)"></i>Corrected mappings (5)</span></div>
<h2>Dubai sales transactions per year (all DLD)</h2>
<div class="chartcard">{bars(gyrows)}</div>
<h2>Corrected mappings applied (validated via master_project_en)</h2>
<div class="callout"><h3>5 high-volume areas fixed</h3><ul>{corr_list}</ul>
<div class="note" style="margin-top:6px">Validation: dominant <span class="mono">master_project_en</span> reproduced 21/21 uncontested mappings; each corrected master sits 100% inside one DLD area.</div></div>
<h2>Browse</h2>
<div class="grid k2"><a class="card" href="areas.html"><div class="kpi"><div class="label">Areas</div><div class="val green">{len(area_index)}</div><div class="hint">DLD areas mapped to Kotook communities →</div></div></a>
<a class="card" href="developers.html"><div class="kpi"><div class="label">Developers</div><div class="val green">{len(dev_index)}</div><div class="hint">official DLD project→developer attribution →</div></div></a></div>
"""
(ROOT/"index.html").write_text(page("Overview","home",body,depth=0),encoding="utf-8")

# ---------- areas list ----------
body=f"""<h1>Areas <span class="muted" style="font-size:16px">({len(area_index)})</span></h1>
<p class="sub">Each row is a DLD area mapped to a Kotook community. Open one to see {SAMPLE} sample transactions and confirm.</p>
<div class="toolbar"><input id="q" class="search" placeholder="Search DLD area or Kotook community…">
<button class="filterbtn active" data-f="all">All</button>
<button class="filterbtn" data-f="ok">Confirmed</button>
<button class="filterbtn" data-f="warn">Review</button>
<button class="filterbtn" data-f="corrected">Corrected</button>
<span class="count" id="count"></span></div>
<div class="tablecard"><table><thead><tr><th>DLD area</th><th>Kotook community</th><th>Status</th><th class="num">Sales tx</th><th class="num">Value 2023+ (bn)</th></tr></thead><tbody id="rows"></tbody></table></div>
<script src="data/areas.js?v={BUILD}"></script><script src="assets/app_areas.js?v={BUILD}"></script>"""
(ROOT/"areas.html").write_text(page("Areas","areas",body,depth=0),encoding="utf-8")

# ---------- developers list ----------
body=f"""<h1>Developers <span class="muted" style="font-size:16px">({len(dev_index)})</span></h1>
<p class="sub">Kotook developers, attributed via the official DLD <span class="mono">project_number → developer</span> chain. See <a href="compare.html">Compare</a> for top-10 numbers vs market sources. Open one to validate its {SAMPLE} sample transactions.</p>
<div class="toolbar"><input id="q" class="search" placeholder="Search developer…"><span class="count" id="count"></span></div>
<div class="tablecard"><table><thead><tr><th>Developer</th><th class="num">Sales tx</th><th class="num">Value 2023+ (bn)</th><th class="num">DLD entities</th></tr></thead><tbody id="rows"></tbody></table></div>
<script src="data/developers.js?v={BUILD}"></script><script src="assets/app_devs.js?v={BUILD}"></script>"""
(ROOT/"developers.html").write_text(page("Developers","developers",body,depth=0),encoding="utf-8")

# ---------- compare page (top developers vs published market benchmarks) ----------
crows=""
for x in devs.head(12).itertuples():
    name=str(x.dev_name); did=int(x.kid); c24,v24=our24.get(did,(0,0.0)); b=BENCH.get(name)
    if b:
        extcell=f'{esc(b["n"])}<div class="note">{esc(b["note"])}</div>'
        srccell=f'<a href="{esc(b["url"])}" target="_blank" rel="noopener">source ↗</a>'
    else:
        extcell='<span class="muted">— (verify via source)</span>'
        srccell='<a href="https://dxbinteract.com/" target="_blank" rel="noopener">dxbinteract ↗</a>'
    crows+=(f"<tr><td class='name'><a href='d/{did}.html'>{esc(name)}</a></td>"
            f"<td class='num'>{fnum(c24)}</td><td class='num'>{fmoney(v24)}</td>"
            f"<td>{extcell}</td><td>{srccell}</td></tr>")
body=f"""<h1>Cross-check vs market sources</h1>
<p class="sub">Our DLD figures (official <span class="mono">project_number → developer</span> chain) next to published 2024 benchmarks, so the team can verify each number against an external source.</p>
<div class="callout"><h3>Read the numbers carefully</h3><div class="note">Figures differ by <b>scope</b>: we count <b>all registered sales</b> (off-plan + ready/resale) for the full calendar year; several sources count <b>off-plan only</b>, or developer <b>bookings</b>, or a different window. Closeness (not exact equality) is the signal. Our developer attribution covers ~77% of sales (projects registered in the May-2026 projects snapshot); brand-new launches may be slightly under-counted.</div></div>
<div class="tablecard"><table><thead><tr><th>Developer</th><th class="num">Our 2024 sales</th><th class="num">Our 2024 value (bn)</th><th>External 2024 benchmark</th><th>Source</th></tr></thead><tbody>{crows}</tbody></table></div>
"""
(ROOT/"compare.html").write_text(page("Compare","compare",body,depth=0),encoding="utf-8")

# ---------- Market page (city-wide analytics) ----------
idx=con.sql(f"""WITH r AS (SELECT EXTRACT(year FROM first_date_of_month) y,
   all_yearly_price_index a, flat_yearly_price_index f, villa_yearly_price_index v,
   ROW_NUMBER() OVER(PARTITION BY EXTRACT(year FROM first_date_of_month) ORDER BY first_date_of_month DESC) rn
   FROM read_csv_auto('{IDX}', sample_size=-1))
   SELECT y, a, f, v FROM r WHERE rn=1 AND a IS NOT NULL AND y>=2019 ORDER BY y""").df()
itbl=""; iprev=None
for r in idx.itertuples():
    if iprev: gp=(r.a-iprev)/iprev*100; gcol="var(--green-d)" if gp>=0 else "var(--red)"; g=f'<span style="color:{gcol};font-weight:700">{gp:+.1f}%</span>'
    else: g="—"
    itbl+=f"<tr><td>{int(r.y)}</td><td class='num'>{fnum(r.a)}</td><td class='num'>{fnum(r.f)}</td><td class='num'>{fnum(r.v)}</td><td class='num'>{g}</td></tr>"
    iprev=r.a
idx_bars=bars([(str(int(r.y)),int(r.a),fnum(round(r.a/1000))+"k") for r in idx.itertuples()])
dem=con.sql(f"SELECT EXTRACT(year FROM TRY_CAST(request_date AS DATE)) y, COUNT(*) c FROM read_csv_auto('{MAPR}', sample_size=-1) WHERE EXTRACT(year FROM TRY_CAST(request_date AS DATE)) BETWEEN 2019 AND 2026 GROUP BY 1 ORDER BY 1").df()
dem_bars=bars([(str(int(r.y)),int(r.c),fnum(r.c)) for r in dem.itertuples() if pd.notna(r.y)])
gsup=con.sql("SELECT EXTRACT(year FROM cdate) y, SUM(units) u FROM projfull WHERE project_status IN ('ACTIVE','NOT_STARTED') AND cdate>=DATE '2026-01-01' GROUP BY 1 ORDER BY 1 LIMIT 5").df()
gsup_bars=bars([(str(int(r.y)),int(r.u or 0),fnum(r.u)) for r in gsup.itertuples() if pd.notna(r.y)])
total_pipe=con.sql("SELECT COALESCE(SUM(units),0) u FROM projfull WHERE project_status IN ('ACTIVE','NOT_STARTED')").fetchone()[0]
toparea=con.sql("SELECT area_name_en, SUM(units) u, COUNT(*) p FROM projfull WHERE project_status IN ('ACTIVE','NOT_STARTED') GROUP BY 1 ORDER BY u DESC NULLS LAST LIMIT 10").df()
tarows="".join(f"<tr><td class='name'>{esc(r.area_name_en)}</td><td class='num'>{fnum(r.u)}</td><td class='num'>{fnum(r.p)}</td></tr>" for r in toparea.itertuples())
body=f"""<h1>Market — Dubai-wide statistics</h1>
<p class="sub">City-level indicators that have no per-area breakdown in the DLD open data — context for the area &amp; developer pages.</p>
<h2>Official DLD residential price index (avg price, AED)</h2>
<div class="chartcard">{idx_bars}</div>
<div class="tablecard" style="margin-top:14px"><table><thead><tr><th>Year</th><th class="num">All</th><th class="num">Flat</th><th class="num">Villa</th><th class="num">YoY (all)</th></tr></thead><tbody>{itbl}</tbody></table></div>
<div class="note" style="margin-top:8px">Source: DLD Residential Sale Index. The open dataset currently ends at <b>2023</b>; 2024–2025 price growth is on each area page (from transactions).</div>
<h2>Demand proxy — DLD map / siteplan requests per year</h2>
<div class="chartcard">{dem_bars}</div>
<div class="note">Leading-indicator proxy for buyer/transaction activity (map &amp; siteplan requests). 2026 is partial.</div>
<h2>City-wide upcoming supply (handovers by year)</h2>
<div class="chartcard">{gsup_bars}</div>
<div class="callout" style="margin-top:12px"><h3>Reality check on supply</h3><div class="note">This is the <b>DLD registered-project pipeline</b> — {fnum(total_pipe)} units across ACTIVE/NOT_STARTED projects (undated projects are excluded from the by-year chart, so yearly bars are a <b>lower bound</b>). For context, Knight Frank/Fitch forecast ≈ <b>60,000–120,000</b> Dubai handovers in 2026 (historical completion ≈ 56%). Treat our per-year figures as a floor, not total market supply.</div></div>
<h2>Top areas by pipeline units</h2>
<div class="tablecard"><table><thead><tr><th>DLD area</th><th class="num">Pipeline units</th><th class="num">Projects</th></tr></thead><tbody>{tarows}</tbody></table></div>
"""
(ROOT/"market.html").write_text(page("Market","market",body,depth=0),encoding="utf-8")

# ---------- about ----------
body=f"""<h1>Method &amp; data sources</h1>
<p class="sub">How these mappings were built and validated.</p>
<div class="card"><h2 style="margin-top:0">Source</h2>
<p>Dubai Land Department public <b>Transactions</b> dataset — 1,274,696 <b>Sales</b> records (1998–2026), loaded into DuckDB. Mortgages and gifts are excluded from these views.</p>
<h2>The validation field</h2>
<p>DLD records carry an official <span class="mono">master_project_en</span> label. We treat the <b>dominant</b> master inside each DLD area (<span class="mono">area_name_en</span>) as the ground-truth community signal. Checks: it reproduced <b>21/21</b> uncontested mappings, each contested master is <b>100% confined to one</b> DLD area, and fragmentation only ever happens <i>within</i> a single community (e.g. Springs-1/2/3 → Emirates Living).</p>
<h2>Corrected mappings</h2>
<p>Five high-volume areas were mislabeled and have been corrected here: Al Barsha South Fourth → JVC, Al Barsha South Fifth → JVT, Al Thanyah Fifth → JLT; and two areas (Al Thanyah Third = The Greens, Al Thanayah Fourth = Emirates Living) belong to communities <b>missing</b> from Kotook.</p>
<h2>What to validate</h2>
<p>For each area and developer we list <b>{SAMPLE} recent transactions</b>. Confirm that the project / building / master names genuinely belong to the stated Kotook community or developer. In Kotook, the area mapping is stored on <span class="mono">CityArea.old_name</span> (en).</p>
</div>"""
(ROOT/"about.html").write_text(page("Method","about",body,depth=0),encoding="utf-8")

print(f"areas={len(area_index)}  developers={len(dev_index)}  coverage={cov}%  confirmed={n_ok} review={n_warn}")
