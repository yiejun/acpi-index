"""Fixed quote basket, daily UTC close. PCA never sets price weights."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/'data/raw';OUT=ROOT/'data/processed';BASKET=ROOT/'analysis/basket.json'
GPU_PROVIDERS=['aws','lambda','coreweave','azure']
API_MODELS={'openai':'openai/gpt-4o','anthropic':'anthropic/claude-sonnet-4.6','google':'google/gemini-2.5-flash'}
WEIGHTS={'gpu':.7,'api':.3}

def load(folder):
    files=sorted((RAW/folder).glob('*.parquet'))
    if not files:return pd.DataFrame()
    d=pd.concat([pd.read_parquet(p) for p in files],ignore_index=True)
    d['timestamp']=pd.to_datetime(d.timestamp,utc=True,errors='coerce')
    return d.dropna(subset=['timestamp'])

def quotes():
    rows=[]
    for provider in GPU_PROVIDERS:
        d=load(provider+'_gpu')
        if d.empty:continue
        d=d[d.price_per_gpu_hour_usd.gt(0)&np.isfinite(d.price_per_gpu_hour_usd)].copy()
        if 'pricing_type' in d:d=d[d.pricing_type.eq('on-demand')]
        if provider=='aws':
            d=d[d.instance_type.eq('p5.48xlarge')&d.region.isin(['US East (N. Virginia)','US West (Oregon)'])];key=d.region
        elif provider=='azure':
            d=d[d.instance_type.eq('Standard_ND96isr_H100_v5')&d.region.isin(['eastus','westus2','westus3'])];key=d.region
        elif provider=='lambda':
            d=d[d.gpu_type.eq('H100-SXM')];key=d.context.str.replace(r'\s+',' ',regex=True).str.strip()
        else:
            d=d[d.gpu_type.eq('H100-HGX')];key=d.context.str.replace(r'\s+',' ',regex=True).str.strip()
        for idx,r in d.iterrows():
            rows.append(dict(timestamp=r.timestamp,layer='gpu',provider=provider,item=provider+'|'+key.loc[idx],label=key.loc[idx],price=float(r.price_per_gpu_hour_usd)))
    d=load('api_pricing')
    if not d.empty:
        for provider,model in API_MODELS.items():
            for r in d[d.model_id.eq(model)].itertuples():
                price=(2*r.input_price_per_million_usd+r.output_price_per_million_usd)/3
                if price>0 and np.isfinite(price):rows.append(dict(timestamp=r.timestamp,layer='api',provider=provider,item=model,label=model,price=price))
    if not rows:raise ValueError('No valid quotes')
    return pd.DataFrame(rows).sort_values('timestamp')

def daily_quotes(q):
    q=q.copy();q['date']=q.timestamp.dt.floor('D')
    return q.groupby(['date','item'],sort=True).tail(1).set_index(['date','item']).sort_index()

def create_basket(q,days):
    d=daily_quotes(q).reset_index()
    for day in days:
        x=d[d.date.eq(day)]
        if set(x[x.layer.eq('gpu')].provider)==set(GPU_PROVIDERS) and set(x[x.layer.eq('api')].provider)==set(API_MODELS):
            members=[]
            for layer,providers in [('gpu',GPU_PROVIDERS),('api',list(API_MODELS))]:
                for provider in providers:
                    subset=x[x.layer.eq(layer)&x.provider.eq(provider)]
                    for r in subset.itertuples():members.append(dict(item=r.item,label=r.label,layer=layer,provider=provider,weight=1/len(providers)/len(subset),base_price=r.price))
            return dict(version='1.0',base_date=day.strftime('%Y-%m-%d'),weights=WEIGHTS,max_carry_days=7,members=members)
    raise ValueError('No complete base date')

def validate_basket(basket):
    members=basket['members']
    if len({m['item'] for m in members})!=len(members):raise ValueError('Duplicate basket member')
    if set(basket['weights'])!={'gpu','api'} or not np.isclose(sum(basket['weights'].values()),1):raise ValueError('Invalid composite weights')
    if any(not np.isfinite(v) or v<=0 for v in basket['weights'].values()):raise ValueError('Nonpositive composite weight')
    for layer in ['gpu','api']:
        rows=[m for m in members if m['layer']==layer]
        if not rows or not np.isclose(sum(m['weight'] for m in rows),1):raise ValueError('Invalid layer weights')
        if any(not np.isfinite(m['base_price']) or m['base_price']<=0 or not np.isfinite(m['weight']) or m['weight']<=0 for m in rows):raise ValueError('Invalid base price or weight')

def compute_levels(q,basket,end=None):
    validate_basket(basket)
    q=q.sort_values('timestamp')
    base=pd.Timestamp(basket['base_date'],tz='UTC');end=end or q.timestamp.max().floor('D')
    days=pd.date_range(base,end,freq='D');ids=[m['item'] for m in basket['members']]
    dq=daily_quotes(q).reset_index();dq=dq[dq.item.isin(ids)]
    p=dq.pivot(index='date',columns='item',values='price').reindex(index=days,columns=ids).ffill()
    ts=dq.pivot(index='date',columns='item',values='timestamp').reindex(index=days,columns=ids).ffill()
    rows=[];components=[]
    for day in days:
        row=dict(date=day.strftime('%Y-%m-%d'),coverage=0,carried=0,expired=0)
        for layer in ['gpu','api']:
            logindex=0.;raw=0.;valid=True
            for m in [m for m in basket['members'] if m['layer']==layer]:
                observed=ts.loc[day,m['item']];price=p.loc[day,m['item']]
                age=(day-observed.floor('D')).days if pd.notna(observed) else None
                status='missing' if age is None else 'expired' if age>basket['max_carry_days'] else 'carried' if age>0 else 'observed'
                usable=status in ['observed','carried'] and pd.notna(price) and price>0
                row['coverage']+=int(usable);row['carried']+=int(status=='carried');row['expired']+=int(status in ['missing','expired'])
                components.append(dict(date=row['date'],**m,price=float(price) if pd.notna(price) else None,observed_at=observed.isoformat() if pd.notna(observed) else None,age_days=age,status=status))
                if not usable:valid=False
                else:logindex+=m['weight']*np.log(price/m['base_price']);raw+=m['weight']*price
            row[layer+'_index']=100*np.exp(logindex) if valid else np.nan;row[layer+'_price']=raw if valid else np.nan
        row['acpi_level']=100*(row['gpu_index']/100)**basket['weights']['gpu']*(row['api_index']/100)**basket['weights']['api'];rows.append(row)
    df=pd.DataFrame(rows)
    for period in [1,7,30,90]:df[f'chg_{period}d_pct']=df.acpi_level.pct_change(period,fill_method=None)*100
    for layer in ['gpu','api']:df[f'contrib_{layer}_log_pct']=100*basket['weights'][layer]*np.log(df[layer+'_index']/df[layer+'_index'].shift())
    df['ma_7']=df.acpi_level.rolling(7,min_periods=7).mean();df['ma_30']=df.acpi_level.rolling(30,min_periods=30).mean()
    df['z_30']=(df.acpi_level-df.acpi_level.rolling(30,min_periods=7).mean())/df.acpi_level.rolling(30,min_periods=7).std().where(lambda x:x>1e-8)
    df['percentile_90']=df.acpi_level.rolling(90,min_periods=7).apply(lambda x:100*((x<x[-1]).sum()+.5*(x==x[-1]).sum())/len(x),raw=True)
    df['drawdown_pct']=(df.acpi_level/df.acpi_level.cummax()-1)*100
    df['quality_flag']=np.where(df.expired.gt(0),'incomplete',np.where(df.chg_1d_pct.abs().gt(20),'review_large_move',np.where(df.carried.gt(0),'carried','observed')))
    return df,pd.DataFrame(components)

def records(df):return json.loads(df.to_json(orient='records',date_format='iso'))

def context_data():
    output={}
    for name,folder,group,val in [('power','power_price','state','price_cents_per_kwh'),('market','market_signal','ticker','close_usd')]:
        d=load(folder)
        if d.empty:output[name]=[];continue
        d['date']=d.timestamp.dt.strftime('%Y-%m-%d')
        sort=['timestamp','period'] if name=='power' else ['timestamp']
        d=d.sort_values(sort).groupby(['date',group],sort=True).tail(1)
        cols=['date',group,'timestamp',val]+(['period'] if name=='power' else (['quote_date'] if 'quote_date' in d else []))
        output[name]=records(d[cols])
    return output

def analysis_data(df):
    changes=df[['gpu_index','api_index']].pct_change(fill_method=None)
    corr=changes.gpu_index.rolling(30,min_periods=7).corr(changes.api_index)
    result={'correlations':records(pd.DataFrame({'date':df.date,'gpu_api_returns':corr})),'pca':[]}
    for i in range(len(df)):
        x=changes.iloc[max(0,i-29):i+1].dropna();x=x.loc[:,x.std().gt(1e-8)]
        if len(x)<7 or x.shape[1]<2:continue
        x=(x-x.mean())/x.std();model=PCA(n_components=1).fit(x.values);sign=1 if model.components_[0].sum()>=0 else -1
        result['pca'].append(dict(date=df.date.iloc[i],pc1=float(model.transform(x.iloc[-1:].values)[0,0]*sign),variance_explained=float(model.explained_variance_ratio_[0])))
    return result

def main():
    q=quotes();days=pd.date_range(q.timestamp.min().floor('D'),q.timestamp.max().floor('D'),freq='D')
    if BASKET.exists():basket=json.loads(BASKET.read_text())
    else:basket=create_basket(q,days);BASKET.write_text(json.dumps(basket,indent=2)+'\n')
    end=max(q.timestamp.max().floor('D'),pd.Timestamp.now(tz='UTC').floor('D'))
    df,components=compute_levels(q,basket,end)
    if df.acpi_level.notna().sum()==0:raise ValueError('No complete observations')
    latest=df.iloc[-1]
    payload=dict(meta=dict(version='1.0',latest_date=latest.date,base_date=basket['base_date'],latest_observed_at=q.timestamp.max().isoformat(),generated_at=pd.Timestamp.now(tz='UTC').isoformat(),frequency='UTC daily last quote per fixed item',basket_size=len(basket['members']),weights=basket['weights'],max_carry_days=basket['max_carry_days'],quality_flag=latest.quality_flag),basket=basket,level=records(df),components=records(components),context=context_data(),**analysis_data(df))
    OUT.mkdir(exist_ok=True,parents=True);df.to_parquet(OUT/'acpi_level.parquet',index=False);components.to_parquet(OUT/'basket_daily.parquet',index=False)
    (ROOT/'docs/data.json').write_text(json.dumps(payload,allow_nan=False,separators=(',',':'))+'\n')
    print(f'Exported {len(df)} daily rows, {len(basket["members"])} fixed quotes; latest: {latest.quality_flag}')
    if latest.expired>0:raise ValueError('Latest basket incomplete; exported unavailable status')
if __name__=='__main__':main()
