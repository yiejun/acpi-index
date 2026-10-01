"""Reject stale required collectors, even if legacy scrapers exit zero on failure."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pandas as pd
from analysis.build_dashboard import quotes,GPU_PROVIDERS,API_MODELS

def main():
    q=quotes();now=pd.Timestamp.now(tz='UTC');errors=[]
    for layer,providers in [('gpu',GPU_PROVIDERS),('api',list(API_MODELS))]:
        for provider in providers:
            timestamps=q[(q.layer==layer)&(q.provider==provider)].timestamp
            newest=timestamps.max()
            if pd.isna(newest) or now-newest>pd.Timedelta(hours=24):errors.append(f'{layer}/{provider}: no valid quote in 24h')
            else:print(f'{layer}/{provider}: {newest.isoformat()}')
    if errors:raise SystemExit('\n'.join(errors))
if __name__=='__main__':main()
