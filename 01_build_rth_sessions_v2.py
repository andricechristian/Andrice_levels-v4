#!/usr/bin/env python3
"""Standalone 1/5/15-minute OHLCV -> completed ES RTH sessions.

Paste the entire file into a Colab cell to upload and convert a CSV.
CLI: python 01_build_rth_sessions.py input.csv --source-timezone America/New_York
     --timestamp-label start --timeframe auto
Requires pandas >=2.0 and numpy. No project helper files are required.
Output extreme times always label the END of their bar in Eastern time.
"""
from __future__ import annotations
import argparse
from collections import Counter
import csv
from datetime import date, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
import time
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd

INPUT_FIELDS = ['Date','Time','Open','High','Low','Close','Volume']
OUTPUT_FIELDS = ['Session','Date','O_RTH','H_RTH','L_RTH','C_RTH','HOD_Time','LOD_Time',
 'Extreme_First','PUV_Points','PDV_Points','PUV_Percent','PDV_Percent','RTH_Range_Points',
 'Calendar_Days_Since_Previous_Complete','ATR_Sequence_Reset','Previous_Complete_RTH_Close',
 'TR_RTH','ATR14_Previous','ATR14_End','PUV_ATR','PDV_ATR','RTH_Volume','Bar_Count','Duplicate_Bars']
SUPPORTED = (1,5,15)
TIMEFRAME_ERROR = ('Please upload 1-minute, 5-minute or 15-minute OHLCV. '
                   'Timeframes higher than 15 minutes are not supported.')


def read_chunks(path, chunksize=200000, nrows=None):
    with Path(path).open(encoding='utf-8-sig',newline='') as f:
        header=next(csv.reader(f),[])
    normalized=[h.strip() for h in header]
    if len(normalized)!=len(set(normalized)):
        raise ValueError('Duplicate column names in the input CSV.')
    if set(INPUT_FIELDS)-set(normalized):
        raise ValueError('Required input header: '+','.join(INPUT_FIELDS))
    names={old:new for old,new in zip(header,normalized)}
    with pd.read_csv(path,dtype=str,encoding='utf-8-sig',chunksize=chunksize,nrows=nrows) as reader:
        for chunk in reader:
            yield chunk.rename(columns=names)[INPUT_FIELDS]


def timestamps(frame,source_timezone='America/New_York',date_format=None):
    ds=frame['Date'].str.strip()
    ds=ds.str.replace(r'^(\d+)\.0+$',r'\1',regex=True)
    if date_format:
        days=pd.to_datetime(ds,format=date_format,errors='coerce')
    else:
        compact=ds.str.fullmatch(r'\d{8}',na=False)
        iso=ds.str.fullmatch(r'\d{4}-\d{2}-\d{2}',na=False)
        if not (compact|iso).all():
            raise ValueError('Use YYYYMMDD or YYYY-MM-DD dates, or specify --date-format, '
                             'for example "%m/%d/%Y" for month/day/year.')
        days=pd.Series(pd.NaT,index=frame.index,dtype='datetime64[ns]')
        days.loc[compact]=pd.to_datetime(ds[compact],format='%Y%m%d',errors='coerce')
        days.loc[iso]=pd.to_datetime(ds[iso],format='%Y-%m-%d',errors='coerce')
    ts=frame['Time'].str.strip().str.replace(r'^(\d+)\.0+$',r'\1',regex=True)
    digits=ts.str.fullmatch(r'\d{1,6}',na=False)
    small=digits & (ts.str.len()<=4)
    full=digits & ~small
    ts.loc[small]=ts[small].str.zfill(4).str.slice(0,2)+':'+ts[small].str.zfill(4).str.slice(2,4)+':00'
    ts.loc[full]=ts[full].str.zfill(6).str.slice(0,2)+':'+ts[full].str.zfill(6).str.slice(2,4)+':'+ts[full].str.zfill(6).str.slice(4,6)
    hm=ts.str.fullmatch(r'\d{1,2}:\d{2}',na=False)
    ts.loc[hm]=ts[hm]+':00'
    clock=pd.to_datetime(ts,format='%H:%M:%S',errors='coerce')
    if days.isna().any() or clock.isna().any():
        bad=frame.loc[days.isna()|clock.isna(),['Date','Time']].head(3).to_dict('records')
        raise ValueError(f'Invalid date/time values: {bad}')
    raw=days+pd.to_timedelta(clock.dt.hour*3600+clock.dt.minute*60+clock.dt.second,unit='s')
    if source_timezone in ('America/New_York','US/Eastern'):
        # Already Eastern wall-clock labels. RTH never intersects the overnight DST fold.
        return raw
    fixed=re.fullmatch(r'UTC([+-])(\d{1,2})(?::?(\d{2}))?',source_timezone,re.I)
    if fixed:
        hours=int(fixed[2]);mins=int(fixed[3] or 0)
        if hours>14 or mins>=60 or (hours==14 and mins):raise ValueError('Invalid UTC offset.')
        offset=(hours*60+mins)*(1 if fixed[1]=='+' else -1)
        tz=timezone(timedelta(minutes=offset))
    else:
        try:tz=ZoneInfo(source_timezone)
        except Exception as exc:raise ValueError('Use an IANA timezone, UTC, or fixed UTC-05:00.') from exc
    localized=raw.dt.tz_localize(tz,ambiguous='NaT',nonexistent='NaT')
    if localized.isna().any():
        raise ValueError('Ambiguous/nonexistent source timestamps around DST. Use a UTC export or resolve those labels; no automatic clock guess was made.')
    return localized.dt.tz_convert('America/New_York').dt.tz_localize(None)


def detect_timeframe(path,source_timezone='America/New_York',date_format=None):
    sample=next(read_chunks(path,chunksize=50000,nrows=50000))
    dt=timestamps(sample,source_timezone,date_format)
    diff=dt.diff().dt.total_seconds()/60
    same=dt.dt.normalize()==dt.shift().dt.normalize()
    mins=dt.dt.hour*60+dt.dt.minute
    near=mins.between(540,990) & mins.shift().between(540,990)
    ds=diff[same & near & (diff>0)]
    if ds.empty:ds=diff[diff>0]
    if ds.empty:raise ValueError('Not enough distinct timestamps to detect the timeframe. Set --timeframe 1, 5 or 15 explicitly.')
    mode=float(ds.value_counts().index[0])
    if mode not in SUPPORTED:
        raise ValueError(f'Detected spacing: {mode:g} minutes. '+TIMEFRAME_ERROR)
    return int(mode)


def resolve_timeframe(value,path,source_timezone,date_format):
    if str(value).lower()=='auto':return detect_timeframe(path,source_timezone,date_format)
    try:tf=int(value)
    except (ValueError,TypeError):raise ValueError(TIMEFRAME_ERROR)
    if str(tf)!=str(value) or tf not in SUPPORTED:raise ValueError(TIMEFRAME_ERROR)
    return tf


def add_atr(rows):
    """Legacy-compatible Wilder RTH ATR14: first TR is the session range.
    Seed with 14 TRs; first prior-ATR excursion is on session 15.
    Gaps >=7 calendar days reset previous close, seed and ATR.
    """
    seed=[];previous_close=None;atr=None;previous_date=None
    for r in rows:
        d=date.fromisoformat(r['Date'])
        gap=(d-previous_date).days if previous_date else None
        reset=gap is not None and gap>=7
        if reset:seed=[];previous_close=None;atr=None
        h,l=r['H_RTH'],r['L_RTH']
        tr=h-l if previous_close is None else max(h-l,abs(h-previous_close),abs(l-previous_close))
        r.update(Calendar_Days_Since_Previous_Complete=gap,ATR_Sequence_Reset=int(reset),
                 Previous_Complete_RTH_Close=previous_close,TR_RTH=tr,ATR14_Previous=atr)
        if atr is None:
            seed.append(tr)
            if len(seed)==14:atr=sum(seed)/14
        else:atr=(13*atr+tr)/14
        prior=r['ATR14_Previous']
        r.update(ATR14_End=atr,PUV_ATR=r['PUV_Points']/prior if prior and prior>0 else None,
                 PDV_ATR=r['PDV_Points']/prior if prior and prior>0 else None)
        previous_close=r['C_RTH'];previous_date=d


def csv_write(path,rows,fields):
    with Path(path).open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)


def summarize_day(day,records,timeframe):
    expected=set(range(570+timeframe,961,timeframe))
    actual=[r[0].hour*60+r[0].minute for r in records]
    counts=Counter(actual)
    duplicates=sum(n-1 for n in counts.values())
    reasons=[]
    if not records:reasons.append('No bars overlapping RTH')
    if duplicates:reasons.append('Duplicate RTH timestamps')
    missing=sorted(expected-set(actual));extra=sorted(set(actual)-expected)
    if missing:reasons.append('Missing RTH bars')
    if extra or any(r[0].second!=0 for r in records):reasons.append('Bars misaligned with the RTH grid or crossing its boundaries')
    if any(b[0]<a[0] for a,b in zip(records,records[1:])):reasons.append('RTH timestamps out of order')
    if any(r[-1] for r in records):reasons.append('Invalid OHLCV')
    volume=sum(r[5] for r in records if np.isfinite(r[5]))
    if records and volume<=0:reasons.append('No positive RTH volume')
    if reasons:
        clock=lambda m:f'{m//60:02d}:{m%60:02d}'
        return None,{'Date':day,'Reasons':'; '.join(reasons),'Expected_Bars':390//timeframe,
           'Observed_Bars':len(records),'Duplicate_Bars':duplicates,'Missing_Bars':len(missing),
           'First_Missing_Labels':';'.join(map(clock,missing[:10]))}
    high=max(r[2] for r in records);low=min(r[3] for r in records)
    ht=next(r[0] for r in records if r[2]==high)
    lt=next(r[0] for r in records if r[3]==low)
    o=records[0][1];close=records[-1][4]
    return {'Date':day,'O_RTH':o,'H_RTH':high,'L_RTH':low,'C_RTH':close,
      'HOD_Time':ht.strftime('%H:%M:%S'),'LOD_Time':lt.strftime('%H:%M:%S'),
      'Extreme_First':'HOD_FIRST' if ht<lt else 'LOD_FIRST' if lt<ht else 'SAME_BAR',
      'PUV_Points':high-o,'PDV_Points':o-low,'PUV_Percent':100*(high-o)/o,
      'PDV_Percent':100*(o-low)/o,'RTH_Range_Points':high-low,
      'RTH_Volume':volume,'Bar_Count':len(records),'Duplicate_Bars':0},None


def convert_file(input_csv,output=None,*,timeframe='auto',source_timezone='America/New_York',
                 timestamp_label='start',date_format=None,chunksize=200000,verbose=True):
    source=Path(input_csv)
    if timestamp_label not in ('start','end'):raise ValueError('timestamp_label must be start or end')
    if chunksize<1:raise ValueError('chunksize must be positive')
    tf=resolve_timeframe(timeframe,source,source_timezone,date_format)
    output=Path(output) if output else source.with_name(source.stem+'_RTH_SESSIONS.csv')
    if output.resolve()==source.resolve():raise ValueError('Output must not overwrite the raw OHLCV input.')
    excluded_path=output.with_name(output.stem+'_EXCLUDED.csv')
    metadata_path=output.with_name(output.stem+'_METADATA.json')
    rows=[];excluded=[];current_day=None;records=[];total=0;first_raw=None;last_raw=None
    first_eastern=None;last_eastern=None
    def finish():
        if current_day is None:return
        accepted,rejected=summarize_day(current_day,records,tf)
        if accepted:
            accepted['Session']=len(rows)+1;rows.append(accepted)
        else:excluded.append(rejected)
    for chunk_no,chunk in enumerate(read_chunks(source,chunksize),1):
        dt=timestamps(chunk,source_timezone,date_format)
        end=dt+pd.to_timedelta(tf,unit='m') if timestamp_label=='start' else dt
        start=end-pd.to_timedelta(tf,unit='m')
        days=end.dt.strftime('%Y-%m-%d')
        if not days.is_monotonic_increasing or (current_day and days.iloc[0]<current_day):
            raise ValueError('CSV dates must be in chronological order. No rows have been silently sorted.')
        if first_raw is None:
            first_raw=str(chunk.iloc[0]['Date'])+' '+str(chunk.iloc[0]['Time'])
            first_eastern=dt.iloc[0].isoformat()
        last_raw=str(chunk.iloc[-1]['Date'])+' '+str(chunk.iloc[-1]['Time'])
        last_eastern=dt.iloc[-1].isoformat();total+=len(chunk)
        end_min=end.dt.hour*60+end.dt.minute+end.dt.second/60
        start_min=start.dt.hour*60+start.dt.minute+start.dt.second/60
        overlap=(end_min>570)&(start_min<960)&(start.dt.normalize()==end.dt.normalize())
        numeric=chunk[['Open','High','Low','Close','Volume']].apply(pd.to_numeric,errors='coerce')
        o,h,l,c,v=[numeric[k] for k in numeric.columns]
        bad=(~np.isfinite(numeric).all(axis=1)) | (l<=0) | (h<l) | (o<l) | (o>h) | (c<l) | (c>h) | (v<0)
        work=numeric.copy();work['End']=end;work['Day']=days;work['Overlap']=overlap;work['Bad']=bad
        for day,group in work.groupby('Day',sort=False):
            if day!=current_day:finish();current_day=day;records=[]
            group=group[group['Overlap']]
            for b in group[['End','Open','High','Low','Close','Volume','Bad']].itertuples(index=False,name=None):
                records.append(b)
        if verbose:print(f'Read {total:,} source bars...',flush=True)
    finish()
    if total==0:raise ValueError('Input CSV has no data rows.')
    add_atr(rows)
    output.parent.mkdir(parents=True,exist_ok=True)
    csv_write(output,rows,OUTPUT_FIELDS)
    exclusion_fields=['Date','Reasons','Expected_Bars','Observed_Bars','Duplicate_Bars','Missing_Bars','First_Missing_Labels']
    csv_write(excluded_path,excluded,exclusion_fields)
    sha=hashlib.sha256()
    with source.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):sha.update(block)
    metadata={'Input_File':source.name,'Input_SHA256':sha.hexdigest(),'Source_Bars':total,
      'First_Source_Label':first_raw,'Last_Source_Label':last_raw,
      'First_Eastern_Label':first_eastern,'Last_Eastern_Label':last_eastern,
      'Source_Timezone':source_timezone,'Source_Timestamp_Label':timestamp_label,'Date_Format':date_format or 'ISO/compact auto',
      'Timeframe_Minutes':tf,'Timeframe_Method':'observed modal spacing in first 50000 rows' if str(timeframe)=='auto' else 'user-specified',
      'RTH':'09:30-16:00 America/New_York','Expected_Bars_Per_Complete_Session':390//tf,
      'Output_Extreme_Times':'Eastern END-of-bar labels; first bar attaining each final extreme',
      'Extreme_Time_Precision_Minutes':tf,'Same_Bar_Order':'unknown; recorded as SAME_BAR',
      'Complete_Sessions':len(rows),'Excluded_Source_Dates':len(excluded),
      'First_Complete_Date':rows[0]['Date'] if rows else None,'Last_Complete_Date':rows[-1]['Date'] if rows else None,
      'ATR_Period':14,'ATR_Method':'Wilder RTH; first TR=H-L; seed=mean first 14 TR; previous ATR for excursions; reset on gaps >=7 calendar days',
      'Sessions_With_Prior_ATR':sum(r['ATR14_Previous'] is not None for r in rows),
      'Notes':['No minute bars are fabricated when the source is 5m/15m.',
               'Completeness uses an exact 390-minute RTH grid, not an exchange holiday calendar.',
               'A repeated missing-bar pattern cannot be distinguished from a coarser source using timestamps alone; confirm the actual export timeframe.',
               'Five sessions cannot seed ATR14. Blank warm-up fields are intentional.',
               'This converter does not append an old session CSV; convert a complete history for calibrated ATR levels.']}
    metadata_path.write_text(json.dumps(metadata,indent=2)+'\n',encoding='utf-8')
    return {'sessions':rows,'excluded':excluded,'metadata':metadata,'csv':str(output),
            'excluded_csv':str(excluded_path),'metadata_json':str(metadata_path)}


def download_output(path):
    """Download a converted file in Colab; print its path when running locally."""
    try:
        from google.colab import files
    except ImportError:print('File available at:',Path(path).resolve())
    else:files.download(str(path))


def notebook_args(args):
    clean=[];i=0
    while i<len(args):
        if args[i]=='-f':i+=2;continue
        if args[i].startswith('-f='):i+=1;continue
        clean.append(args[i]);i+=1
    return clean


def select_input():
    try:
        from google.colab import files
    except ImportError:return Path(input('OHLCV CSV path: ').strip().strip('"'))
    print('Upload ONE 1-minute, 5-minute or 15-minute OHLCV CSV.')
    uploaded=files.upload()
    if len(uploaded)!=1:raise ValueError('Select exactly one CSV file.')
    return Path(next(iter(uploaded)))


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('input_csv',nargs='?');p.add_argument('--output')
    p.add_argument('--timeframe',default='auto')
    p.add_argument('--source-timezone',default='America/New_York')
    p.add_argument('--timestamp-label',choices=['start','end'],default='start')
    p.add_argument('--date-format');p.add_argument('--chunksize',type=int,default=200000)
    p.add_argument('--no-download',action='store_true')
    args=p.parse_args(notebook_args(sys.argv[1:] if argv is None else argv))
    try:
        source=Path(args.input_csv) if args.input_csv else select_input()
        if not args.input_csv:
            preview=next(read_chunks(source,chunksize=3,nrows=3))
            print('First source labels:\n'+preview[['Date','Time']].to_string(index=False))
            args.source_timezone=input(f'Source timezone [{args.source_timezone}] (or UTC / UTC-05:00): ').strip() or args.source_timezone
            args.timestamp_label=input(f'Does each timestamp mark the bar start or end? [{args.timestamp_label}]: ').strip().lower() or args.timestamp_label
            first_date=str(preview.iloc[0]['Date']).strip()
            if not args.date_format and not re.fullmatch(r'\d{8}|\d{4}-\d{2}-\d{2}',first_date):
                choice=input('Date order: 1 = month/day/year, 2 = day/month/year [1]: ').strip() or '1'
                if choice not in ('1','2'):raise ValueError('Choose date order 1 or 2.')
                args.date_format='%m/%d/%Y' if choice=='1' else '%d/%m/%Y'
            tf=resolve_timeframe(args.timeframe,source,args.source_timezone,args.date_format)
            answer=input(f'Detected/selected interval: {tf} minutes. Confirm actual export timeframe [1/5/15; Enter={tf}]: ').strip()
            args.timeframe=answer or str(tf)
        result=convert_file(source,args.output,timeframe=args.timeframe,source_timezone=args.source_timezone,
             timestamp_label=args.timestamp_label,date_format=args.date_format,chunksize=args.chunksize)
    except (ValueError,OSError,pd.errors.ParserError,pd.errors.EmptyDataError) as exc:
        print('\nConversion stopped:',exc)
        return 1
    m=result['metadata']
    print(f"\nConverted {m['Complete_Sessions']} complete sessions; excluded {m['Excluded_Source_Dates']} source dates.")
    print(f"Timeframe: {m['Timeframe_Minutes']}m; expected {m['Expected_Bars_Per_Complete_Session']} bars/session.")
    print('HOD/LOD times are Eastern END-of-bar labels, not exact intrabar event times.')
    if m['Sessions_With_Prior_ATR']==0:
        print('ATR14 warm-up: no prior ATR yet. The first normalized session requires 15 completed sessions without a reset.')
    print('Converted CSV:',result['csv']);print('Exclusions:',result['excluded_csv']);print('Settings/audit:',result['metadata_json'])
    if not args.no_download:download_output(result['csv'])
    return 0


if __name__=='__main__':
    exit_code=main()
    if exit_code and 'ipykernel' not in sys.modules:raise SystemExit(exit_code)
