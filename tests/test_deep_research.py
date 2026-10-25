import json
import tempfile
import unittest
from pathlib import Path
from research import deep_dossier as d, deep_investigate as ai, deep_publish as pub

class FocusedResearchTests(unittest.TestCase):
    def fixture(self):
        rows=[];screen=[]
        for t,pe,g in [('AAA',32,18),('BBB',8,4),('CCC',11,7)]:
            rows.append({'ticker':t,'company_sec_name':t+' inc',
             'status':'independent_annual_fundamentals_verified',
             'primary_source':'https://data.sec.gov/api/xbrl/companyfacts/CIK0000000123.json',
             'cik':123,'revenue_usd':500e6,'free_cash_flow_usd':50e6,
             'revenue_growth_yoy_pct':g,'net_income_usd':25e6,
             'operating_cash_usd':80e6,'capital_spending_usd':30e6,
             'positive_fcf_years':3,'fcf_years_available':3,'fiscal_year_ended':'2025-12-31',
             'cash_balance':{'value_usd':80e6},'long_term_debt_tag':{'value_usd':60e6},
             'annual_history_latest_three':[{'fiscal_year_ended':'2025-12-31','free_cash_flow_usd':50e6}],
             'reverse_cash_flow_valuation':{'implied_growth_needed_by_stock_price_pct':8,
                'required_return_assumed_pct':11,'terminal_perpetual_growth_assumed_pct':2,
                'fixed_assumption_scenarios':{'no_growth':{'annual_fcf_growth_assumed_pct':0,
                 'value_as_pct_of_current_market_cap':68}}}})
            screen.append({'ticker':t,'name':t+' Inc','forward_pe':pe,'market_cap_usd':700e6})
        return rows,screen

    def test_selection_excludes_crypto_and_diversifies(self):
        rows,screen=self.fixture()
        rows.append({**rows[0],'ticker':'BTCX','company_sec_name':'Bitcoin mining'})
        screen.append({'ticker':'BTCX','name':'Bitcoin mining','forward_pe':100})
        out=d.select_companies(rows,screen,limit=2)
        self.assertEqual(len(out),2)
        self.assertNotIn('BTCX',[x[0]['ticker'] for x in out])
        self.assertNotEqual(out[0][0]['ticker'],out[1][0]['ticker'])

    def test_source_dates_and_price_asset_not_spot(self):
        rows,screen=self.fixture()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            market={'last_completed_us_price_date':'2026-10-23',
                    'stock_investing_watchlist':screen,'discovery_feeds':{'unique_stock_quotes':133}}
            sec={'source_market_date':'2026-10-23','companies':rows}
            hub={'market_last_completed_close':'2026-10-23'}
            est={'latest_completed_us_market_day':'2026-10-23'}
            for name,obj in [('market_discovery.json',market),('sec_fundamentals.json',sec),
                             ('decision_hub.json',hub),('established_strategies.json',est)]:
                (root/name).write_text(json.dumps(obj))
            def quotes():return {'VOO':{'return_6m_pct':8,'asof':'2026-10-23'},
              'GLD':{'return_3m_pct':5,'return_6m_pct':6,'price_usd':120,
                     'asof':'2026-10-23','source':'https://finance.yahoo.com/quote/GLD/history/'}}
            dossier=d.assemble(root,quote_fn=quotes,filing_fn=lambda c,a:{'submissions_url':'https://data.sec.gov/submissions/CIK0000000123.json','recent_filings':[]})
            self.assertEqual(len(dossier['assets']),3)
            self.assertEqual(dossier['assets'][-1]['ticker'],'GLD')
            self.assertTrue(all('bitcoin' not in x['name'].lower() for x in dossier['assets']))
            report=pub.briefing(dossier,{'market_date':'2026-10-23','investigations':{},
                        'ai_review_configured':False})
            self.assertTrue(report['fresh'])
            self.assertEqual(report['ai_analysed_count'],0)
            rendered=pub.render_html(report)
            self.assertIn('SEC',rendered)
            self.assertIn('GLD',rendered)
            self.assertNotIn('review completed for 3',rendered)
            self.assertIn('Fewer ideas',rendered)

    def test_ai_review_must_have_actual_source_ids(self):
        rows,screen=self.fixture()
        entry={'kind':'equity','ticker':'AAA','name':'Example',
          'investment_role':'Watch','metrics':{'revenue':100},
          'sources':[{'id':'S1','url':'https://www.sec.gov','kind':'file','summary':'public filings'}]}
        def fake(key,system,payload,schema):
            names=[k for k in schema['properties'] if k!='evidence_ids']
            return {**{n:'A cautious research explanation supported by the filed facts.' for n in names},
                    'evidence_ids':['S1']}
        out=ai.investigate_asset(entry,'fake-test-key',request=fake)
        self.assertEqual(out['research']['evidence_ids'],['S1'])
        with self.assertRaises(ValueError):
            ai.validate({'summary':'A sufficiently long unsupported claim','evidence_ids':['INVALID']},
                        {'S1'},('summary',))
        with self.assertRaises(ValueError):
            ai.validate({'summary':'The upside is a guaranteed 25% profit.','evidence_ids':['S1']},
                        {'S1'},('summary',))

    def test_annual_filing_retrieved_even_when_buried_behind_events(self):
        from research.deep_dossier import get_filing_evidence
        forms=['8-K']*9+['10-Q','10-K']
        ids=['0000000123-26-'+str(i).zfill(6) for i in range(len(forms))]
        recent={'form':forms,
            'accessionNumber':ids,
            'primaryDocument':['document.htm']*len(forms),
            'filingDate':['2026-10-20']*9+['2026-09-01','2026-03-01']}
        def fake_json(url,agent):
            return {'filings':{'recent':recent}}
        def fake_html(url,agent):
            return ('<html><body>Risk factors index. Managements discussion index. '
                'Risk Factors Our customers may reduce orders. '
                'Managements Discussion Revenue growth depends on chip demand.'
                '</body></html>')
        result=get_filing_evidence(123,'test contact',fetch_json=fake_json,fetch_html=fake_html)
        self.assertIn('10-K',[x['form'] for x in result['priority_filings']])
        self.assertIn('10-Q',[x['form'] for x in result['priority_filings']])
        self.assertIn('8-K',[x['form'] for x in result['priority_filings']])
        self.assertTrue(any(x['form']=='10-K' for x in result['read_passages']))
        self.assertTrue(all(x['url'].startswith('https://www.sec.gov/') for x in result['priority_filings']))

    def test_report_is_self_contained_without_paid_ai(self):
        rows, screen = self.fixture()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            market = {'last_completed_us_price_date': '2026-10-23',
                      'stock_investing_watchlist': screen,
                      'discovery_feeds': {'unique_stock_quotes': 3}}
            sec = {'source_market_date': '2026-10-23', 'companies': rows}
            hub = {'market_last_completed_close': '2026-10-23'}
            est = {'latest_completed_us_market_day': '2026-10-23'}
            for name, obj in [('market_discovery.json', market),
                              ('sec_fundamentals.json', sec),
                              ('decision_hub.json', hub),
                              ('established_strategies.json', est)]:
                (root/name).write_text(json.dumps(obj))
            quotes = lambda: {'VOO': {'return_6m_pct': 8, 'asof': '2026-10-23'},
                              'GLD': {'return_3m_pct': 5, 'return_6m_pct': 6,
                                      'asof': '2026-10-23',
                                      'source': 'https://finance.yahoo.com/quote/GLD/history/'}}
            dossier = d.assemble(root, quote_fn=quotes, filing_fn=lambda c, a: {
                'submissions_url': 'https://data.sec.gov/submissions/CIK0000000123.json',
                'recent_filings': []})
            report = pub.briefing(dossier, {'market_date': '2026-10-23',
                                            'investigations': {}, 'ai_review_configured': False})
            html = pub.render_html(report)
            md = pub.render_markdown(report)
            self.assertEqual(report['ai_analysed_count'], 0)
            self.assertIn('NO SWITCH FROM VOO', html)
            self.assertIn('Bull', html)
            self.assertIn('Evidence completeness', html)
            self.assertIn('VOO comparison', md)
            self.assertNotIn('Copy-ready', html+md)
            self.assertNotIn('Investigate with ChatGPT', html+md)
            self.assertNotIn('manual_research_prompt', json.dumps(report))
            self.assertIn('research_completeness', json.dumps(report))
            self.assertEqual(len(report['assets']), 3)

    def test_research_does_not_call_headline_a_confirmed_event(self):
        from research.research_synthesis import analyse
        case = {'ticker': 'XYZ', 'kind': 'equity', 'metrics': {
            'annual_history': [{'free_cash_flow_usd': 105}, {'free_cash_flow_usd': 100}],
            'revenue_growth_yoy_pct': 30, 'fcf_yield_pct': 1,
            'fcf_usd': 105, 'market_cap_usd': 9999},
            'qualitative_context': {'headline_sample': [{'title': 'Unverified deal'}]}}
        memo = analyse(case)
        self.assertIn('NO SWITCH', memo['decision'])
        self.assertIn('cash', memo['economic_mechanism'].lower())
        self.assertTrue(any('NOT independently verified' in item for item in memo['source_audit']))
        self.assertIn('unavailable', memo['pricing_interpretation'].lower())

    def test_never_publish_stale_cross_source_dossier(self):
        with self.assertRaises(ValueError):
            pub.briefing({'market_date':'2026-10-23','assets':[]},
                         {'market_date':'2026-10-22','investigations':{}})

if __name__=='__main__':unittest.main()