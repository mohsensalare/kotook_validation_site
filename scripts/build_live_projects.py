"""Collect every Kotook project that has DLD stats into one JSON for the live stats page."""
import json, sys, urllib.request, concurrent.futures as cf
API = "https://backend.kotook.ae/en"
def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "kotook-stats-builder"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r: return json.load(r)
    except urllib.error.HTTPError as e:
        if e.code == 404: return None
        raise
projects, url = [], f"{API}/project/Projects/?size=100"
while url:
    d = get(url); projects += d["results"]; url = d["next"]
def stats(p):
    d = get(f"{API}/dld-stats/api/project/{p['id']}/?recent=0")
    return p, (d or {}).get("summary", {}).get("all"), (d or {}).get("as_of")
out, as_of = [], None
with cf.ThreadPoolExecutor(8) as ex:
    for p, s, a in ex.map(stats, projects):
        if not s or not s.get("tx"): continue
        as_of = max(as_of or "", a or "")
        out.append({"id": p["id"], "slug": p["slug"], "title": p["title"], "status": p.get("status"),
            "min_price": p.get("min_price"), "handover": (p.get("handover_date") or "")[:7] or None,
            "thumb": (p.get("thumbnails") or {}).get("small") or p.get("image"),
            "area": {"id": p["area"]["id"], "title": p["area"]["title"], "city": p["area"].get("city_slug")} if p.get("area") else None,
            "developer": {"id": p["developer"]["id"], "name": p["developer"]["full_name"]} if p.get("developer") else None,
            "tx": s["tx"], "median_psf": s.get("median_psf"), "change_pct": s.get("change_pct")})
out.sort(key=lambda x: -x["tx"])
json.dump({"as_of": as_of, "count": len(out), "projects": out}, open(sys.argv[1], "w"), ensure_ascii=False, separators=(",", ":"))
print(len(projects), "projects checked,", len(out), "with DLD data, as_of", as_of)
