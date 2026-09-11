#!/usr/bin/env python3
"""Calculate levels, timing, rolling comparisons and estimator uncertainty.

Standalone calculator: no rth_stats.py file is needed.
Requires NumPy (already available in standard Google Colab runtimes).
Paste this entire file into a Colab cell, or upload it and use %run.
With no CSV argument, a CSV upload dialog opens in Colab.
Use --stats-only when today's RTH open is not yet known. All calibration rows
must precede --forecast-date, which defaults to today's date.
"""
from __future__ import annotations
import argparse
import sys
from datetime import date
from pathlib import Path
import numpy as np
# Bundled calculation helpers: this file runs independently in Colab.
import csv
import hashlib
import json
import math
from datetime import date, datetime
from pathlib import Path
import numpy as np

MODELS = {"Points": ("PUV_Points", "PDV_Points"),
          "Percentage": ("PUV_Percent", "PDV_Percent"),
          "ATR": ("PUV_ATR", "PDV_ATR")}
QUANTILES = (.10, .25, .50, .75, .90, .95)
COHORTS = {"All": None, "Last60": 60, "Last252": 252}
ENVELOPES = {"Mean": None, "MeanPlusSE": None,
             "Q50": .50, "Q75": .75, "Q90": .90, "Q95": .95}
ZONES = {"MeanSE": None, "P25_P75": (.25, .75), "P10_P90": (.10, .90)}

def clean(value):
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (tuple, list, np.ndarray)):
        return [clean(v) for v in value]
    if isinstance(value, (np.bool_,)): return bool(value)
    if isinstance(value, (np.integer,)): return int(value)
    if isinstance(value, (np.floating, float)):
        return float(value) if math.isfinite(float(value)) else None
    return value

def write_json(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(clean(value), indent=2, allow_nan=False) + "\n")

def write_csv(path, rows):
    rows = list(rows)
    if not rows: return
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(dict.fromkeys(k for row in rows for k in row))
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader()
        for row in rows:
            w.writerow({k: json.dumps(clean(v)) if isinstance(v, (dict, list)) else clean(v)
                        for k, v in row.items()})

def clock_minutes(value):
    for pattern in ("%H:%M:%S", "%H:%M"):
        try: t = datetime.strptime(str(value).strip(), pattern)
        except ValueError: continue
        m = t.hour * 60 + t.minute + t.second / 60 - 570
        return m if 0 <= m <= 390 else np.nan
    return np.nan

def clock_label(minutes):
    if not np.isfinite(minutes): return None
    seconds = int(round((570 + minutes) * 60))
    return f"{seconds//3600:02d}:{seconds%3600//60:02d}:{seconds%60:02d}"

def finite(x):
    x = np.asarray(x, dtype=float)
    return x[np.isfinite(x)]

def load_sessions(path):
    path = Path(path)
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f); fields = reader.fieldnames or []
        required = {"Date", "O_RTH", "H_RTH", "L_RTH", "C_RTH", "HOD_Time", "LOD_Time",
                    "ATR14_Previous", "ATR14_End"}
        if required.difference(fields):
            raise ValueError(f"Missing columns: {sorted(required.difference(fields))}")
        raw = list(reader)
    if not raw: raise ValueError("No completed sessions in the CSV. Check the converter exclusion report.")
    rows = []; seen = set(); inconsistencies = []; annual = {}; missing_counts = []
    for line, source in enumerate(raw, 2):
        ds = date.fromisoformat(source["Date"].strip()).isoformat()
        if ds in seen: raise ValueError(f"Duplicate session: {ds}")
        seen.add(ds)
        r = {"Date": ds}
        for key in ("O_RTH", "H_RTH", "L_RTH", "C_RTH", "ATR14_Previous", "ATR14_End", "RTH_Volume"):
            r[key] = float(source[key]) if source.get(key, "").strip() else np.nan
        o, h, l, c = (r[k] for k in ("O_RTH", "H_RTH", "L_RTH", "C_RTH"))
        if not all(np.isfinite([o,h,l,c])) or not 0 < l <= min(o,c) <= max(o,c) <= h:
            raise ValueError(f"Invalid OHLC at line {line}: {ds}")
        if np.isfinite(r["RTH_Volume"]) and r["RTH_Volume"] < 0:
            raise ValueError(f"Negative volume: {ds}")
        for key in ("ATR14_Previous", "ATR14_End"):
            if np.isfinite(r[key]) and r[key] <= 0: raise ValueError(f"Invalid {key}: {ds}")
        r.update(PUV_Points=h-o, PDV_Points=o-l, PUV_Percent=100*(h-o)/o, PDV_Percent=100*(o-l)/o)
        prior = r["ATR14_Previous"]
        r["PUV_ATR"] = (h-o)/prior if prior > 0 else np.nan
        r["PDV_ATR"] = (o-l)/prior if prior > 0 else np.nan
        for keys in MODELS.values():
            for key in keys:
                if source.get(key, "").strip() and np.isfinite(r[key]):
                    if abs(float(source[key])-r[key]) > 1e-7:
                        inconsistencies.append(f"{ds}: {key}")
        r["HOD_Minutes"] = clock_minutes(source["HOD_Time"])
        r["LOD_Minutes"] = clock_minutes(source["LOD_Time"])
        ht, lt = r["HOD_Minutes"], r["LOD_Minutes"]
        r["Order"] = ("HOD_FIRST" if ht < lt else "LOD_FIRST" if lt < ht else "SAME_BAR") if np.isfinite(ht+lt) else "UNKNOWN"
        if source.get("Extreme_First") and source["Extreme_First"] != r["Order"]:
            inconsistencies.append(f"{ds}: Extreme_First")
        r["Bar_Count"] = int(source["Bar_Count"]) if source.get("Bar_Count", "").strip() else None
        r["Duplicate_Bars"] = int(source["Duplicate_Bars"]) if source.get("Duplicate_Bars", "").strip() else None
        if r["Bar_Count"] not in (None, 390, 78, 26):
            raise ValueError(f"Expected 390 (1m), 78 (5m), or 26 (15m) complete-session bars: {ds}")
        if r["Duplicate_Bars"] not in (None, 0): raise ValueError(f"Duplicate bars: {ds}")
        if r["Bar_Count"] is None: missing_counts.append(ds)
        annual[ds[:4]] = annual.get(ds[:4], 0) + 1
        rows.append(r)
    if inconsistencies: raise ValueError(f"Inconsistent derived data: {inconsistencies[:10]}")
    rows.sort(key=lambda r:r["Date"])
    atr_links = []
    for prev, r in zip(rows, rows[1:]):
        gap = (date.fromisoformat(r["Date"])-date.fromisoformat(prev["Date"])).days
        if gap < 7 and np.isfinite(prev["ATR14_End"]+r["ATR14_Previous"]):
            if abs(prev["ATR14_End"]-r["ATR14_Previous"]) > 1e-7: atr_links.append(r["Date"])
        if np.isfinite(r["ATR14_Previous"]+r["ATR14_End"]):
            tr = max(r["H_RTH"]-r["L_RTH"], abs(r["H_RTH"]-prev["C_RTH"]), abs(r["L_RTH"]-prev["C_RTH"]))
            if abs((13*r["ATR14_Previous"]+tr)/14-r["ATR14_End"]) > 1e-7: atr_links.append(r["Date"])
    if atr_links: raise ValueError(f"ATR continuity/recalculation mismatches: {atr_links[:10]}")
    audit = {"Input":path.name, "SHA256":hashlib.sha256(path.read_bytes()).hexdigest(),
             "Rows":len(rows), "First_Date":rows[0]["Date"], "Last_Date":rows[-1]["Date"],
             "Annual_Counts":annual, "Missing_Bar_Count_Dates":missing_counts,
             "Bar_Timeframes_Minutes":sorted({390//r["Bar_Count"] for r in rows if r["Bar_Count"]}),
             "Invalid_HOD_Times":sum(not np.isfinite(r["HOD_Minutes"]) for r in rows),
             "Invalid_LOD_Times":sum(not np.isfinite(r["LOD_Minutes"]) for r in rows),
             "Derived_Value_Mismatches":len(inconsistencies), "ATR_Mismatches":len(atr_links),
             "Input_Was_Sorted": [r["Date"] for r in rows]==[r["Date"].strip() for r in raw],
             "Notes":["Completed-session status is inherited, not reverified from minute bars.",
                      "Extreme times use supplied labels; precision is limited to the source timeframe. Mixed timeframe histories can affect timing statistics.",
                      "ATR is the supplied Wilder RTH ATR, not full exchange-session daily ATR.",
                      "Original ATR sequence resets on calendar gaps >=7 days are preserved.",
                      "Continuous back-adjusted prices may differ from prices available in real time."]}
    return rows, audit

def block_indices(n, repetitions, block_length, rng):
    if n < 1: raise ValueError("Cannot bootstrap an empty sample")
    b = min(block_length, max(1, n//3))  # Avoid a full-sample block giving artificial zero SE on tiny samples.
    starts = rng.integers(0, n, size=(repetitions, math.ceil(n/b)))
    return ((starts[:,:,None] + np.arange(b)) % n).reshape(repetitions,-1)[:,:n]

def uncertainty(draws):
    x = finite(draws)
    if len(x) < 2: return {"SE_Block":None, "CI95_Low":None, "CI95_High":None, "Valid_Replicates":len(x)}
    return {"SE_Block":float(np.std(x, ddof=1)), "CI95_Low":float(np.quantile(x,.025)),
            "CI95_High":float(np.quantile(x,.975)), "Valid_Replicates":len(x)}

def describe(x, indices=None):
    x = np.asarray(x, dtype=float); v = finite(x)
    if len(v)<2: return None
    mean = float(v.mean()); sd = float(v.std(ddof=1)); se = sd/math.sqrt(len(v))
    estimates = {"Mean":mean, **{f"P{int(q*100)}":float(np.quantile(v,q)) for q in QUANTILES}}
    estimates.update(MeanSE_Low=max(0,mean-se), MeanSE_High=mean+se)
    estimates.update(IQR_Width=estimates["P75"]-estimates["P25"], P10P90_Width=estimates["P90"]-estimates["P10"])
    result = {"N":len(v), "Sample_SD":sd, "Mean_SE_IID":se, "Estimates":estimates, "Uncertainty":{}}
    if indices is None: return result
    samples = x[indices]; counts = np.sum(np.isfinite(samples),axis=1)
    with np.errstate(invalid="ignore",divide="ignore"):
        means = np.nanmean(samples,axis=1); sem = np.nanstd(samples,axis=1,ddof=1)/np.sqrt(counts)
        qs = np.nanquantile(samples,QUANTILES,axis=1)
    draws = {"Mean":means, **{f"P{int(q*100)}":qs[i] for i,q in enumerate(QUANTILES)}}
    draws.update(MeanSE_Low=np.maximum(0,means-sem),MeanSE_High=means+sem,
                 IQR_Width=qs[3]-qs[1],P10P90_Width=qs[4]-qs[0])
    result["Uncertainty"] = {k:uncertainty(v) for k,v in draws.items()}
    return result

def window_hist(x):
    x = np.asarray(x,dtype=float); v = finite(x)
    # Bar labels [09:30,10:00), ..., [15:30,16:00], final endpoint included.
    bins = np.minimum((v/30).astype(int),12)
    return np.bincount(bins,minlength=13), bins

def timing_report(rows, indices):
    result = {}; times = {}
    for side in ("HOD","LOD"):
        x = np.array([r[side+"_Minutes"] for r in rows]); times[side]=x
        desc = describe(x,indices)
        if desc:
            desc["Clock_Estimates"]={k:clock_label(v) for k,v in desc["Estimates"].items() if not k.endswith("Width")}
        hist, _ = window_hist(x); n = int(hist.sum()); max_count = hist.max()
        modes = np.flatnonzero(hist==max_count).tolist() if n else []
        sampled_hist = np.zeros((len(indices),13))
        for j in range(13):
            mask = np.isfinite(x) & (np.minimum(np.floor(np.nan_to_num(x,nan=-30)/30),12)==j)
            sampled_hist[:,j] = mask[indices].sum(axis=1)
        totals = sampled_hist.sum(axis=1)
        winners = sampled_hist==sampled_hist.max(axis=1,keepdims=True)
        entries=[]
        for j in range(13):
            share = int(hist[j])/n if n else np.nan
            draws=np.divide(sampled_hist[:,j],totals,out=np.full(len(indices),np.nan),where=totals>0)
            entries.append({"Window":f"{clock_label(j*30)[:5]}-{clock_label((j+1)*30)[:5]}",
                            "Count":int(hist[j]), "Share":share,
                            "Share_SE_IID":math.sqrt(share*(1-share)/n) if n else None,
                            **uncertainty(draws), "Is_Mode":j in modes,
                            "Bootstrap_Mode_Inclusion_Rate":float(winners[:,j].mean()) if n else None})
        result[side]={"Timing_Minutes_After_Open":desc,"Thirty_Minute_Windows":entries,
                      "Modal_Windows":[entries[j]["Window"] for j in modes]}
    h,l=times["HOD"],times["LOD"]; valid=np.isfinite(h+l)
    lf=valid & (l<h); hf=valid & (h<l); ties=valid & (h==l)
    ld=lf[indices].sum(axis=1); hd=hf[indices].sum(axis=1); known=ld+hd
    ratios=np.divide(ld,hd,out=np.full(len(indices),np.nan),where=hd>0)
    shares=np.divide(ld,known,out=np.full(len(indices),np.nan),where=known>0)
    nk=int(lf.sum()+hf.sum()); prob=float(lf.sum()/nk) if nk else np.nan
    result["Order"]={"LOD_First":int(lf.sum()), "HOD_First":int(hf.sum()), "Same_Bar":int(ties.sum()),
                     "Missing_Pair":int((~valid).sum()), "Known_Order_N":nk,
                     "LOD_First_Share":prob, "Share_SE_IID":math.sqrt(prob*(1-prob)/nk) if nk else None,
                     "Share_Uncertainty":uncertainty(shares),
                     "LOD_to_HOD_Ratio":float(lf.sum()/hf.sum()) if hf.sum() else None,
                     "Ratio_Uncertainty":uncertainty(ratios),
                     "Undefined_Ratio_Replicates":int(np.sum(hd==0))}
    return result

def cohort_report(rows, repetitions=1000, block_length=5, seed=731):
    rng=np.random.default_rng(seed)
    effective_block=min(block_length,max(1,len(rows)//3))
    ix=block_indices(len(rows),repetitions,effective_block,rng)
    return {"N_Sessions":len(rows),"First_Date":rows[0]["Date"],"Last_Date":rows[-1]["Date"],
            "Bootstrap_Repetitions":repetitions,"Block_Length":effective_block,"Requested_Block_Length":block_length,
            "Timing":timing_report(rows,ix),
            "Excursions":{model:{side:describe([r[key] for r in rows],ix)
                                  for side,key in zip(("HOD","LOD"),keys)}
                          for model,keys in MODELS.items()}}

def forecast(history, open_price, prior_atr):
    """No current high/low/close/time accepted: forecasts can use prior rows only."""
    result={}
    for model,keys in MODELS.items():
        scale = 1 if model=="Points" else open_price/100 if model=="Percentage" else prior_atr
        if not np.isfinite(scale) or scale<=0: continue
        stats=[describe([r[k] for r in history]) for k in keys]
        if any(s is None for s in stats): continue
        es=[s["Estimates"] for s in stats]
        envelopes={}
        for name,q in ENVELOPES.items():
            key="Mean" if name=="Mean" else "MeanSE_High" if name=="MeanPlusSE" else name.replace("Q","P")
            u,d=[e[key]*scale for e in es]
            envelopes[name]={"Upper":open_price+u,"Lower":open_price-d,"Up_Distance":u,"Down_Distance":d,"Q":q}
        zones={}
        for name,qs in ZONES.items():
            a,b=("MeanSE_Low","MeanSE_High") if qs is None else (f"P{int(qs[0]*100)}",f"P{int(qs[1]*100)}")
            zones[name]={"HOD_Low":open_price+es[0][a]*scale,"HOD_High":open_price+es[0][b]*scale,
                         "LOD_Low":open_price-es[1][b]*scale,"LOD_High":open_price-es[1][a]*scale}
        result[model]={"N_HOD":stats[0]["N"],"N_LOD":stats[1]["N"],"Scale":scale,
                       "Envelopes":envelopes,"Zones":zones}
    return result

def probability_summary(x, indices):
    x=np.asarray(x,dtype=float); v=finite(x)
    if not len(v): return {"N":0,"Hits":0,"Rate":None,"SE_IID":None,**uncertainty([])}
    p=float(v.mean()); z=1.95996398454; n=len(v); denom=1+z*z/n
    mid=(p+z*z/(2*n))/denom; half=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/denom
    with np.errstate(invalid="ignore",divide="ignore"):
        vals=np.nanmean(x[indices],axis=1)
    return {"N":n,"Hits":int(v.sum()),"Rate":p,"SE_IID":math.sqrt(p*(1-p)/n),
            "Wilson95_Low":mid-half,"Wilson95_High":mid+half,**uncertainty(vals)}

def notebook_safe_arguments(args):
    cleaned=[]; i=0
    while i<len(args):
        if args[i]=="-f": i+=2; continue
        if args[i].startswith("-f="): i+=1; continue
        cleaned.append(args[i]); i+=1
    return cleaned

def select_csv():
    try:
        from google.colab import files
    except ImportError:
        entered=input("Session CSV path: ").strip().strip('"')
        if not entered: raise ValueError("No CSV selected")
        return Path(entered)
    print("Upload the complete RTH sessions CSV.")
    uploaded=files.upload()
    if len(uploaded)!=1: raise ValueError("Select exactly one session CSV")
    return Path(next(iter(uploaded)))
# End of bundled calculation helpers.


def flatten_reports(reports):
    out=[]
    for cohort, report in reports.items():
        groups=[(model,side,desc,"points" if model=="Points" else "percentage_points" if model=="Percentage" else "ATR")
                for model,sides in report["Excursions"].items() for side,desc in sides.items()]
        groups += [("Time",side,report["Timing"][side]["Timing_Minutes_After_Open"],"minutes_after_09:30") for side in ("HOD","LOD")]
        for model,side,desc,unit in groups:
            if desc is None: continue
            for metric,val in desc["Estimates"].items():
                u=desc["Uncertainty"][metric]
                out.append({"Cohort":cohort,"Model":model,"Side":side,"Metric":metric,"N":desc["N"],
                            "Value":val,"Unit":unit,"Clock_Time":clock_label(val) if model=="Time" and not metric.endswith("Width") else None,
                            "SE_IID":desc["Mean_SE_IID"] if metric=="Mean" else None,**u})
    return out

def project_rows(name, report, open_price, atr):
    rows=[]
    for model,sides in report["Excursions"].items():
        factor=1 if model=="Points" else open_price/100 if model=="Percentage" else atr
        if not np.isfinite(factor) or factor<=0: continue
        for side,desc in sides.items():
            if not desc: continue
            sign=1 if side=="HOD" else -1
            for zone,lo,hi,center in [("MeanSE","MeanSE_Low","MeanSE_High","Mean"),
                                       ("P25_P75","P25","P75","P50"),
                                       ("P10_P90","P10","P90","P50")]:
                e,u=desc["Estimates"],desc["Uncertainty"]
                low_key,high_key=(lo,hi) if sign==1 else (hi,lo)
                rows.append({"Cohort":name,"Model":model,"Side":side,"Zone":zone,"N":desc["N"],
                             "RTH_Open":open_price,"Previous_ATR":atr,"Center":open_price+sign*e[center]*factor,
                             "Low":open_price+sign*e[low_key]*factor,"High":open_price+sign*e[high_key]*factor,
                             "Center_SE_Block_Points":u[center]["SE_Block"]*factor,
                             "Low_SE_Block_Points":u[low_key]["SE_Block"]*factor,
                             "High_SE_Block_Points":u[high_key]["SE_Block"]*factor,
                             "Mean_SE_IID_Points":desc["Mean_SE_IID"]*factor})
    return rows

def project_envelopes(name, report, open_price, atr):
    rows=[]
    for model,sides in report["Excursions"].items():
        factor=1 if model=="Points" else open_price/100 if model=="Percentage" else atr
        if not np.isfinite(factor) or factor<=0 or any(v is None for v in sides.values()): continue
        for envelope in ENVELOPES:
            key="Mean" if envelope=="Mean" else "MeanSE_High" if envelope=="MeanPlusSE" else envelope.replace("Q","P")
            up,down=sides["HOD"],sides["LOD"]
            upper=open_price+factor*up["Estimates"][key]
            lower=open_price-factor*down["Estimates"][key]
            rows.append({"Cohort":name,"Model":model,"Envelope":envelope,
                         "RTH_Open":open_price,"Previous_ATR":atr,
                         "Lower":lower,"Upper":upper,"Width_Points":upper-lower,
                         "Lower_SE_Block_Points":factor*down["Uncertainty"][key]["SE_Block"],
                         "Upper_SE_Block_Points":factor*up["Uncertainty"][key]["SE_Block"]})
    return rows

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("session_csv",nargs="?")
    p.add_argument("--open",dest="rth_open",type=float)
    p.add_argument("--current-atr",type=float)
    p.add_argument("--forecast-date",default=date.today().isoformat())
    p.add_argument("--start"); p.add_argument("--end")
    p.add_argument("--lookback",type=int,help="Adds a custom cohort; 60/252/full are always exported.")
    p.add_argument("--display-window",default="All",choices=list(COHORTS))
    p.add_argument("--bootstrap",type=int,default=1000)
    p.add_argument("--block-length",type=int,default=5)
    p.add_argument("--seed",type=int,default=731)
    p.add_argument("--stats-only",action="store_true")
    p.add_argument("--output-dir")
    p.add_argument("--summary-output");p.add_argument("--levels-output");p.add_argument("--timing-output")
    args=p.parse_args(notebook_safe_arguments(sys.argv[1:]))
    if args.bootstrap<100 or args.block_length<1: p.error("Use bootstrap >=100 and block length >=1")
    target=date.fromisoformat(args.forecast_date).isoformat()
    if args.start: date.fromisoformat(args.start)
    if args.end: date.fromisoformat(args.end)
    source=Path(args.session_csv) if args.session_csv else select_csv()
    all_rows,audit=load_sessions(source)
    available=[r for r in all_rows if r["Date"]<target]
    rows=[r for r in available if (not args.start or r["Date"]>=args.start) and (not args.end or r["Date"]<=args.end)]
    if len(rows)<2: p.error("Need at least two completed historical sessions before forecast date")
    windows=dict(COHORTS)
    if args.lookback is not None:
        if args.lookback<2: p.error("lookback must be >=2")
        windows[f"Last{args.lookback}"]=args.lookback
    reports={}
    for i,(name,length) in enumerate(windows.items()):
        sample=rows if length is None else rows[-length:]
        print(f"Calculating {name}: {len(sample)} sessions...")
        if length is not None and len(sample)<length:
            print(f"  Only {len(sample)} of the requested {length} sessions are available.")
        if len(sample)<3*args.block_length:
            print(f"  Small sample: bootstrap block reduced to {max(1,len(sample)//3)} session(s).")
        reports[name]=cohort_report(sample,args.bootstrap,args.block_length,args.seed+i)
    out=Path(args.output_dir) if args.output_dir else source.with_name(source.stem+"_ANALYSIS")
    out.mkdir(parents=True,exist_ok=True)
    summary=Path(args.summary_output) if args.summary_output else out/"statistical_summary.csv"
    timings=Path(args.timing_output) if args.timing_output else out/"timing_summary.json"
    write_csv(summary,flatten_reports(reports))
    write_json(timings,{k:v["Timing"] for k,v in reports.items()})
    write_csv(out/"timing_windows.csv",[{"Cohort":k,"Side":side,**w} for k,v in reports.items()
              for side in ("HOD","LOD") for w in v["Timing"][side]["Thirty_Minute_Windows"]])
    payload={"Forecast_Date":target,"Input_Audit":audit,"Cohorts":reports,
             "Method":"Mean SE IID=s/sqrt(n); SE_Block=SD of circular-block bootstrap estimators; not prediction bands.",
             "Window_Convention":"[09:30,10:00), etc.; [15:30,16:00] includes final endpoint; supplied labels retained."}
    selected=reports[args.display_window]
    print(f"\nHISTORICAL TIMING — {args.display_window} ({selected['N_Sessions']} sessions)")
    for side in ("LOD","HOD"):
        item=selected["Timing"][side]; d=item["Timing_Minutes_After_Open"]
        if d is None: print(f"{side}: unavailable"); continue
        e,u=d["Estimates"],d["Uncertainty"]
        print(f"{side} average: {clock_label(e['Mean'])} | standard uncertainty: {d['Mean_SE_IID']:.2f} min IID; {u['Mean']['SE_Block']:.2f} min block")
        print(f"{side} median: {clock_label(e['P50'])} +/- {u['P50']['SE_Block']:.2f} min (block SE)")
        print(f"{side} P25–P75: {clock_label(e['P25'])}–{clock_label(e['P75'])} | endpoint SEs: {u['P25']['SE_Block']:.2f}, {u['P75']['SE_Block']:.2f} min")
        for window in item["Thirty_Minute_Windows"]:
            if window["Is_Mode"]:
                print(f"{side} modal window: {window['Window']} | {window['Share']:.1%} of sessions +/- {window['SE_Block']*100:.2f} percentage points (block SE)")
    order=selected["Timing"]["Order"]
    print(f"LOD-first/HOD-first: {order['LOD_to_HOD_Ratio']} | block SE: {order['Ratio_Uncertainty']['SE_Block']}")
    projections=[]; envelopes=[]
    if not args.stats_only:
        o=args.rth_open if args.rth_open is not None else float(input("Current RTH open: "))
        if not np.isfinite(o) or o<=0: p.error("RTH open must be finite and positive")
        # Current ATR comes from the last available pre-forecast row, not a stale cohort.
        atr=args.current_atr if args.current_atr is not None else available[-1]["ATR14_End"]
        if args.current_atr is not None and (not np.isfinite(atr) or atr<=0):
            p.error("--current-atr must be finite and positive")
        if not np.isfinite(atr) or atr<=0:
            print("ATR levels unavailable: prior history has not completed ATR14 warm-up. Points and percentage levels will still be exported.")
        for name,report in reports.items():
            projections.extend(project_rows(name,report,o,atr))
            envelopes.extend(project_envelopes(name,report,o,atr))
        levels=Path(args.levels_output) if args.levels_output else out/"projected_zones.csv"
        write_csv(levels,projections)
        write_csv(out/"projected_envelopes.csv",envelopes)
        selected_history=rows if COHORTS[args.display_window] is None else rows[-COHORTS[args.display_window]:]
        payload["Outer_Envelopes"]=forecast(selected_history,o,atr)
        for model in MODELS:
            print(f"\n{model.upper()} LEVELS — {args.display_window}")
            if not any(r["Model"]==model and r["Cohort"]==args.display_window for r in projections):
                print("Unavailable: need a current ATR and at least two valid historical ATR-normalized excursions.")
                continue
            for r in projections:
                if r["Model"]==model and r["Cohort"]==args.display_window:
                    print(f"{r['Side']} {r['Zone']}: {r['Low']:.2f}–{r['High']:.2f} | boundary block SE: {r['Low_SE_Block_Points']:.2f}, {r['High_SE_Block_Points']:.2f} points")
            for r in envelopes:
                if r["Model"]==model and r["Cohort"]==args.display_window and r["Envelope"] in ("Q90","Q95"):
                    print(f"{r['Envelope']} envelope: {r['Lower']:.2f}–{r['Upper']:.2f} | boundary block SE: {r['Lower_SE_Block_Points']:.2f}, {r['Upper_SE_Block_Points']:.2f} points")
        payload.update(RTH_Open=o,Previous_ATR=atr,Projected_Zones=projections,Projected_Envelopes=envelopes)
    write_json(out/"analysis.json",payload)
    print(f"\nFiles saved in: {out}")
    print("Mean uncertainty is not next-session coverage. Percentile zones require out-of-sample calibration.")

if __name__=="__main__": main()
