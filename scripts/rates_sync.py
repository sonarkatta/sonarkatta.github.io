#!/usr/bin/env python3
"""Standby rates publisher. Standalone: no agents, no external services beyond the two feed pages.

Hot standby: it only writes 1-rates.json when the current file is stale (the primary
publisher missed several cycles) and both feed pages verify. Every number is read from the
page, checked, and stamped with the page's own feed time. Nothing is derived or guessed.

Env: REF_URL_MUM, REF_URL_PUN (feed page URLs, kept in repository secrets)
     STALE_MIN (default 12)  FORCE=1 ignores window and staleness (for dry runs)
     DRY_RUN=1 never writes
"""
import html, json, os, re, sys, time, urllib.request
from datetime import datetime, timezone, timedelta
from html.parser import HTMLParser

IST = timezone(timedelta(hours=5, minutes=30))
TARGET = os.environ.get("RATES_FILE", "1-rates.json")
STALE_MIN = float(os.environ.get("STALE_MIN", "12"))
FORCE = os.environ.get("FORCE") == "1"
DRY = os.environ.get("DRY_RUN") == "1"
SRC_FILE = os.environ.get("SRC_DIR")  # test only: read saved pages from a folder


def log(*a):
    print(*a, flush=True)


def out_summary(lines):
    p = os.environ.get("GITHUB_STEP_SUMMARY")
    if p:
        with open(p, "a") as f:
            f.write("\n".join(lines) + "\n")


def iso(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(s):
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


class Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.t, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self.skip += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript") and self.skip:
            self.skip -= 1

    def handle_data(self, d):
        if not self.skip and d.strip():
            self.t.append(d.strip())


def rupees(s):
    m = re.search(r"₹\s*([\d,]+)", s)
    return int(m.group(1).replace(",", "")) if m else None


def unwrap(v):
    if isinstance(v, list) and len(v) == 2 and v[0] == 0:
        return unwrap(v[1])
    if isinstance(v, list) and len(v) == 2 and v[0] == 1:
        return [unwrap(x) for x in v[1]]
    if isinstance(v, dict):
        return {k: unwrap(x) for k, x in v.items()}
    return v


def fetch(url, tag):
    if SRC_FILE:
        return open(os.path.join(SRC_FILE, tag + ".html"), encoding="utf-8").read()
    last = None
    for i in range(3):
        try:
            sep = "&" if "?" in url else "?"
            req = urllib.request.Request(url + sep + "t=" + str(int(time.time())), headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36", "Accept-Language": "en-IN,en;q=0.9"})
            with urllib.request.urlopen(req, timeout=25) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:  # noqa
            last = e
            time.sleep(4)
    raise RuntimeError("fetch failed (%s): %s" % (tag, type(last).__name__))


def parse_page(h):
    """Return dict of verified numbers, or raise ValueError."""
    i = h.find("tokenEndpoint")
    if i < 0:
        raise ValueError("state block missing")
    s = h.rfind('props="', 0, i) + 7
    e = h.find('"', s)
    state = unwrap(json.loads(html.unescape(h[s:e])))
    init = state["initial"]
    ref = {x["s"]: x["a"] for x in init["ref"]}
    ts = datetime.fromtimestamp(init["ts"] / 1000, IST)
    tp = Text()
    tp.feed(h)
    t = tp.t

    def after(label):
        for k, x in enumerate(t):
            if x == label:
                for y in t[k + 1:k + 3]:
                    v = rupees(y)
                    if v:
                        return v
        return None

    g24, g22, silver = after("24K Gold"), after("22K Gold"), after("Silver")
    m = re.search(r"18K \(750 fineness\) gold in [A-Za-z ]+ is ₹([\d,]+) per 10 grams", " ".join(t))
    g18 = int(m.group(1).replace(",", "")) if m else None
    d = dict(g24=g24, g22=g22, g18=g18, silver=silver, r995=ref.get("GL995"), gst995=ref.get("GR995WG"),
             r999=ref.get("GL999"), gst999=ref.get("GR999WG"), ts=ts)
    rtgs995, rtgs999, silver_tile = ref.get("GR995"), ref.get("GR999"), ref.get("SL999")
    if None in d.values() or None in (rtgs995, rtgs999, silver_tile):
        raise ValueError("missing field: " + ",".join(k for k, v in d.items() if v is None))
    # coherence
    ok = []
    ok.append(d["r999"] - d["r995"] == 1000)
    ok.append(148 <= d["g24"] - d["r999"] <= 156)
    ok.append(abs(d["g22"] - round(d["g24"] * 0.916)) <= 3)
    ok.append(abs(d["g18"] - round(d["g24"] * 0.75)) <= 3)
    ok.append(abs(d["gst995"] - round(rtgs995 * 1.03)) <= 2)
    ok.append(abs(d["gst999"] - round(rtgs999 * 1.03)) <= 2)
    ok.append(silver == silver_tile)
    if not all(ok):
        raise ValueError("incoherent page numbers %s" % ok)
    return d


def apply_city(cur, which, d):
    if which == "Maharashtra":
        stamp = iso(d["ts"])
        cur.update(gold24_10g=d["g24"], gold22_10g=d["g22"], gold18_10g=d["g18"], silver999_kg=d["silver"],
                   gold995=d["r995"], retail_995=d["r995"], retail_999=d["r999"],
                   gold_995_with_gst=d["gst995"], gold_999_with_gst=d["gst999"], quote_timestamp=stamp)
        for k in list(cur):
            if k.endswith("_captured_at") and k != "silver_999_with_gst_captured_at":
                cur[k] = stamp
        for c in cur["cities"]:
            if c["name"] == "Maharashtra":
                c.update(gold24_10g=d["g24"], gold22_10g=d["g22"], gold995_10g=d["r995"], silver999_kg=d["silver"],
                         gold995_with_gst=d["gst995"], gold24_with_gst=d["gst999"], retail_995=d["r995"],
                         retail_999=d["r999"], captured_at=stamp)
    else:
        stamp = iso(d["ts"])
        for c in cur["cities"]:
            if c["name"] == "Pune":
                c.update(gold24_10g=d["g24"], gold22_10g=d["g22"], gold995_10g=d["r995"], silver999_kg=d["silver"],
                         gold995_with_gst=d["gst995"], gold24_with_gst=d["gst999"], retail_995=d["r995"],
                         retail_999=d["r999"], captured_at=stamp)
                for k in list(c):
                    if k.endswith("_captured_at"):
                        c[k] = stamp


def main():
    now = datetime.now(timezone.utc)
    ist = now.astimezone(IST)
    mins = ist.hour * 60 + ist.minute
    if not FORCE and not (9 * 60 <= mins <= 22 * 60):
        log("outside 09:00-22:00 IST, nothing to do")
        return 0
    cur = json.load(open(TARGET, encoding="utf-8"))
    pune_cur = next(c for c in cur["cities"] if c["name"] == "Pune")
    newest = max(parse_iso(cur["quote_timestamp"]), parse_iso(pune_cur["captured_at"]))
    age = (now - newest).total_seconds() / 60
    log("current file age: %.1f min (stale after %.0f)" % (age, STALE_MIN))
    if not FORCE and age < STALE_MIN:
        log("primary publisher is current, standing by")
        out_summary(["Standby: current file is %.1f min old, nothing written." % age])
        return 0
    res, problems = {}, []
    for name, env in (("Maharashtra", "REF_URL_MUM"), ("Pune", "REF_URL_PUN")):
        try:
            url = os.environ.get(env, "") if not SRC_FILE else "x"
            if not url:
                raise RuntimeError("secret %s not set" % env)
            d = parse_page(fetch(url, name.lower()))
            res[name] = d
            log(name, "verified", {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in d.items()})
        except Exception as e:  # noqa
            problems.append("%s: %s" % (name, e))
            log(name, "NOT verified:", e)
    # cross-city sanity
    if len(res) == 2:
        gap = res["Pune"]["g24"] - res["Maharashtra"]["g24"]
        if not (10 <= gap <= 90):
            problems.append("cross-city gap %s out of range" % gap)
            res = {}
    # no regress and jump guard
    cur_ts = {"Maharashtra": parse_iso(cur["quote_timestamp"]), "Pune": parse_iso(pune_cur["captured_at"])}
    cur_g24 = {"Maharashtra": cur["gold24_10g"], "Pune": pune_cur["gold24_10g"]}
    for name in list(res):
        d = res[name]
        if d["ts"].astimezone(timezone.utc) <= cur_ts[name]:
            log(name, "source is not newer than the file, skipped")
            del res[name]
        elif abs(d["g24"] - cur_g24[name]) > 2000:
            problems.append("%s: gold moved more than 2000 versus the file, needs a human" % name)
            del res[name]
        elif (now - d["ts"]).total_seconds() > 20 * 60 and not FORCE:
            problems.append("%s: source is older than 20 minutes" % name)
            del res[name]
    if not res:
        log("nothing verified to publish")
        out_summary(["Nothing published."] + ["- " + p for p in problems])
        return 1 if problems else 0
    for name, d in res.items():
        apply_city(cur, name, d)
    text = json.dumps(cur, ensure_ascii=False, indent=2) + "\n"
    summary = ["Published: " + ", ".join(res)] + ["- %s %s 24K %s" % (n, iso(d["ts"]), d["g24"]) for n, d in res.items()] + ["- " + p for p in problems]
    out_summary(summary)
    if DRY:
        log("DRY RUN, would write:\n" + text[:400])
        return 0
    open(TARGET, "w", encoding="utf-8").write(text)
    log("written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
