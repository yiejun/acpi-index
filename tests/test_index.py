import unittest
import numpy as np
import pandas as pd
from analysis.build_dashboard import compute_levels, analysis_data, context_data
from unittest.mock import patch

class IndexTests(unittest.TestCase):
    def basket(self):
        return dict(base_date='2026-01-01',weights={'gpu':.7,'api':.3},max_carry_days=7,
            members=[dict(item='g',label='g',layer='gpu',provider='cloud',weight=1.,base_price=5.),dict(item='a',label='a',layer='api',provider='model',weight=1.,base_price=10.)])
    def quotes(self,days=2):
        return pd.DataFrame([dict(timestamp=pd.Timestamp(f'2026-01-{d:02d}T12:00Z'),item=k,price=p,layer=l,provider=n,label=k)
            for d in range(1,days+1) for k,p,l,n in [('g',5.,'gpu','cloud'),('a',10.,'api','model')]])
    def test_geometric_change_and_contributions(self):
        q=self.quotes();q.loc[(q.item=='g')&(q.timestamp.dt.day==2),'price']=4
        d,_=compute_levels(q,self.basket())
        self.assertAlmostEqual(d.acpi_level.iloc[-1],100*.8**.7)
        c=d.contrib_gpu_log_pct.iloc[-1]+d.contrib_api_log_pct.iloc[-1]
        self.assertAlmostEqual(100*np.expm1(c/100),d.chg_1d_pct.iloc[-1])
    def test_unlisted_member_cannot_change_index(self):
        q=self.quotes();extra=q.iloc[[0]].copy();extra['item']='new-cloud';extra['price']=1000
        d,_=compute_levels(pd.concat([q,extra]),self.basket());self.assertTrue(np.allclose(d.acpi_level,100))
    def test_missing_member_is_carried_not_reweighted_then_expires(self):
        q=self.quotes(1);d,c=compute_levels(q,self.basket(),pd.Timestamp('2026-01-09',tz='UTC'))
        self.assertEqual(d.carried.iloc[1],2);self.assertEqual(d.acpi_level.iloc[7],100)
        self.assertTrue(pd.isna(d.acpi_level.iloc[8]));self.assertEqual(d.expired.iloc[8],2)
    def test_frequency_does_not_weight_daily_price(self):
        q=self.quotes();dup=q.iloc[[0]].copy();dup['timestamp']=pd.Timestamp('2026-01-01T01:00Z');dup['price']=50
        d,_=compute_levels(pd.concat([q,dup]).sort_values('timestamp'),self.basket())
        self.assertTrue(np.allclose(d.acpi_level,100))
    def test_returns_use_calendar_days_and_missing_values_stay_missing(self):
        q=self.quotes();q=q[q.timestamp.dt.day==1];d,_=compute_levels(q,self.basket(),pd.Timestamp('2026-01-17',tz='UTC'))
        self.assertEqual(d.chg_7d_pct.iloc[7],0);self.assertTrue(pd.isna(d.chg_7d_pct.iloc[8]))
    def test_flat_series_has_centered_rank_no_fake_zscore_or_pca(self):
        d,_=compute_levels(self.quotes(15),self.basket())
        self.assertEqual(d.percentile_90.iloc[-1],50);self.assertTrue(pd.isna(d.z_30.iloc[-1]))
        self.assertEqual(analysis_data(d)['pca'],[])

    def test_manifest_with_invalid_weights_is_rejected(self):
        basket=self.basket();basket['members'][0]['weight']=.5
        with self.assertRaises(ValueError):compute_levels(self.quotes(),basket)
    def test_power_history_retains_earlier_source_month(self):
        power=pd.DataFrame([dict(timestamp=pd.Timestamp('2026-06-01T12:00Z'),period='2026-04',state='CA',price_cents_per_kwh=20.),dict(timestamp=pd.Timestamp('2026-07-01T12:00Z'),period='2026-05',state='CA',price_cents_per_kwh=21.)])
        with patch('analysis.build_dashboard.load',side_effect=lambda folder:power.copy() if folder=='power_price' else pd.DataFrame()):
            rows=context_data()['power']
        self.assertEqual([r['period'] for r in rows],['2026-04','2026-05'])
    def test_pca_history_does_not_change_when_future_prices_arrive(self):
        q=self.quotes(25)
        for i in q.index:
            d=q.loc[i,'timestamp'].day
            q.loc[i,'price']*=1+.001*d*d if q.loc[i,'item']=='g' else 1+.01*np.sin(d)
        full,_=compute_levels(q,self.basket());prefix,_=compute_levels(q[q.timestamp.dt.day<=18],self.basket())
        a=analysis_data(prefix)['pca'];b=[r for r in analysis_data(full)['pca'] if r['date']<=prefix.date.iloc[-1]]
        self.assertTrue(len(a)>0);self.assertEqual(a,b)

if __name__=='__main__':unittest.main()
