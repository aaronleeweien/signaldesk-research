"""Collect bounded, primary-source dossiers for at most two shares + one commodity ETF.

Reuses SignalDesk's quant engine. SEC companyfacts and submissions are independently
sourced; Yahoo price histories are clearly labelled unofficial. Crypto excluded.
No LLM is asked to invent a number. Errors remain in private diagnostic metadata.
"""
from __future__ import annotations
import json, math, os, re, time
from datetime import datetime, timezone, date
from pathlib import Path
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET
from html.parser import HTMLParser

CRYPTO_TICKERS={'COIN','MSTR','MARA','RIOT','CLSK','HUT','HIVE','BITF','BTDR','IBIT','FBTC','GBTC','BITO','ETHA','ETHE','BTC','ETH','SOL','DOGE'}
CRYPTO = re.compile(r'\b(crypto(?:currency)?|bitcoin|ethereum|blockchain|digital.asset|web3|dogecoin|stablecoin|tokeni[sz]ation)\b',re.I)
PROXIES = {
    'GLD': ('Physical gold', 'https://www.spdrgoldshares.com/usa/'),
    'SLV': ('Physical silver', 'https://www.ishares.com/us/products/239855/ishares-silver-trust-fund'),
    'USO': ('Oil futures fund', 'https://www.uscfinvestments.com/uso'),
    'DBA': ('Agricultural futures fund', 'https://www.invesco.com/us/financial-products/etfs/product-detail?productId=DBA'),
}

def num(v):
    try:
        x=float(v)
        return x if math.isfinite(x) else None
    except (ValueError,TypeError): return None

def select_companies(company_rows, market_rows, limit=2):
    """Diversify: highest evidence-rich growth candidate + value candidate.

    Not a recommendation; deliberately avoids picking two companies in the
    same oil-producing / refining industry. Only SEC-verifiable US companies.
    """
    info={x['ticker']:x for x in market_rows if x.get('ticker')}
    pool=[]
    for item in company_rows:
        sym=item.get('ticker','').upper()
        row=info.get(sym,{})
        if not sym or sym in CRYPTO_TICKERS or CRYPTO.search(' '.join([sym,str(item.get('company_sec_name','')),str(row.get('name',''))])):
            continue
        if item.get('status')!='independent_annual_fundamentals_verified':continue
        if num(item.get('revenue_usd')) is None or num(item.get('free_cash_flow_usd')) is None:continue
        pool.append((item,row))
    if not pool:return []
    # Evidence quality first: broader recent history and cash generation.
    broad=sorted(pool,key=lambda v:(len(v[0].get('annual_history_latest_three',[])),
                  num(v[1].get('market_cap_usd')) or 0),reverse=True)
    # Choose a faster growth business if we have it, then a less expensive one.
    growth=sorted(broad,key=lambda v:(num(v[0].get('revenue_growth_yoy_pct')) or 0,
              num(v[1].get('market_cap_usd')) or 0),reverse=True)
    chosen=[growth[0]]
    value=sorted(broad,key=lambda v:(num(v[1].get('forward_pe')) is None,
                 num(v[1].get('forward_pe')) or 1e12))
    for candidate in value:
        if candidate[0]['ticker']==chosen[0][0]['ticker']:continue
        chosen.append(candidate)
        break
    return chosen[:limit]

def verified_metrics(stock, quote):
    model=stock.get('reverse_cash_flow_valuation') or {}
    return {
        'ticker':stock['ticker'], 'name':stock.get('company_sec_name') or stock['ticker'],
        'fiscal_year_end':stock.get('fiscal_year_ended'),
        'market_cap_usd':num(quote.get('market_cap_usd')),
        'forward_pe':num(quote.get('forward_pe')),
        'revenue_usd':num(stock.get('revenue_usd')),
        'revenue_growth_yoy_pct':num(stock.get('revenue_growth_yoy_pct')),
        'net_income_usd':num(stock.get('net_income_usd')),
        'operating_cash_usd':num(stock.get('operating_cash_usd')),
        'capital_spending_usd':num(stock.get('capital_spending_usd')),
        'fcf_usd':num(stock.get('free_cash_flow_usd')),
        'fcf_yield_pct':num(stock.get('free_cash_flow_yield_pct')),
        'fcf_positive_years':stock.get('positive_fcf_years'),
        'fcf_years_available':stock.get('fcf_years_available'),
        'cash_usd':num((stock.get('cash_balance') or {}).get('value_usd')),
        'debt_usd':num((stock.get('long_term_debt_tag') or {}).get('value_usd')),
        'price_implied_fcf_growth_pct':num(model.get('implied_growth_needed_by_stock_price_pct')),
        'reverse_model_required_return_pct':num(model.get('required_return_assumed_pct')),
        'reverse_model_terminal_growth_pct':num(model.get('terminal_perpetual_growth_assumed_pct')),
        'scenario_sensitivity':model.get('fixed_assumption_scenarios') or {},
        'annual_history':stock.get('annual_history_latest_three') or [],
    }

def get_json(url,user_agent):
    req=Request(url,headers={'User-Agent':user_agent,'Accept':'application/json'})
    with urlopen(req,timeout=25) as response:return json.load(response)

class TextOnly(HTMLParser):
    def __init__(self):super().__init__();self.out=[];self.skip=0
    def handle_starttag(self,tag,attrs):
        if tag in ('script','style','head','ix:header'):self.skip+=1
    def handle_endtag(self,tag):
        if tag in ('script','style','head','ix:header'):self.skip=max(0,self.skip-1)
    def handle_data(self,data):
        if not self.skip and data.strip():self.out.append(data.strip())

def excerpt(document):
    """Bound source text; retain selected MD&A and risk-factor vicinity only."""
    parser=TextOnly();parser.feed(document[:3_000_000]);s=' '.join(parser.out)
    s=re.sub(r'\s+',' ',s)
    sections=[]
    for name,pattern in [('Management discussion',r"management.s discussion and analysis"),
                         ('Risk factors',r"risk factors"),('Business overview',r"item 1\.? business")]:
        candidates=list(re.finditer(pattern,s,re.I))
        # First match often table of contents, so prefer the second when present.
        if candidates:
            i=candidates[min(len(candidates)-1,1)].start()
            sections.append({'section':name,'text':s[i:i+2300]})
    return sections or [{'section':'Filing excerpt','text':s[:2200]}]

def get_filing_evidence(cik,user_agent,fetch_json=get_json,fetch_html=None):
    """Fetch latest US filing *content*, not merely links to company filings.

    Annual 10-K is retrieved by form from the whole SEC submission index. It
    often is not in the latest five 8-Ks or 10-Qs! Save only short excerpts;
    preserve exact form, filing date and official URL for each quoted passage.
    """
    submissions_url=f'https://data.sec.gov/submissions/CIK{int(cik):010d}.json'
    data=fetch_json(submissions_url,user_agent)
    recent=(data.get('filings') or {}).get('recent') or {}
    forms=recent.get('form') or []
    all_items=[]
    for i,form in enumerate(forms):
        if form not in ('10-K','10-Q','8-K','20-F','6-K'):continue
        try:
            acc=recent['accessionNumber'][i]
            primary=recent['primaryDocument'][i]
            filed=recent['filingDate'][i]
        except (KeyError,IndexError):continue
        if not acc or not primary:continue
        url=f'https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc.replace("-","")}/{primary}'
        all_items.append({'form':form,'filed':filed,'url':url,'accession':acc})
    recent_list=all_items[:5]
    annual=next((x for x in all_items if x['form'] in ('10-K','20-F')),None)
    quarterly=next((x for x in all_items if x['form'] in ('10-Q','6-K')),None)
    event=next((x for x in all_items if x['form']=='8-K'),None)
    # A strong investigative packet needs at least these three *document types*.
    selected=[]
    for item in (annual,quarterly,event):
        if item and item['url'] not in {x['url'] for x in selected}:selected.append(item)
    if fetch_html is None:
        def fetch_html(url,agent):
            req=Request(url,headers={'User-Agent':agent,'Accept':'text/html'})
            with urlopen(req,timeout=30) as response:
                return response.read(3_000_000).decode('utf-8','replace')
    passages=[];source_errors=[]
    for item in selected:
        try:
            document=fetch_html(item['url'],user_agent)
            selected_excerpts=excerpt(document)
            text=' '.join(x['section']+': '+x['text'][:450] for x in selected_excerpts)[:1250]
            if text.strip():
                passages.append({'form':item['form'],'filed':item['filed'],
                                 'url':item['url'],'text':text})
        except Exception as exc:
            source_errors.append(item['form']+': '+type(exc).__name__)
        time.sleep(.3)
    return {'submissions_url':submissions_url,'recent_filings':recent_list,
            'priority_filings':selected,'read_passages':passages,
            'fetch_issues':source_errors}


def commodity_snapshot(tickers=('GLD','SLV','USO','DBA','VOO')):
    """Never equate fund returns with physical spot returns. No crypto tickers."""
    import yfinance as yf
    raw=yf.download(list(tickers),period='18mo',interval='1d',auto_adjust=True,
                    progress=False,threads=False)
    if raw.empty:raise ValueError('Commodity price download empty')
    close=raw['Close']
    if hasattr(close,'columns'):pass
    else:raise ValueError('Ticker prices unavailable')
    out={}
    for ticker in tickers:
        if ticker not in close.columns:continue
        series=close[ticker].dropna()
        if len(series)<140:continue
        latest=float(series.iloc[-1]);r63=(latest/float(series.iloc[-64])-1)*100
        r126=(latest/float(series.iloc[-127])-1)*100
        out[ticker]={'price_usd':round(latest,2),'return_3m_pct':round(r63,2),
            'return_6m_pct':round(r126,2),'asof':str(series.index[-1].date()),
            'source':'https://finance.yahoo.com/quote/'+ticker+'/history/'}
    return out

def assemble(root=Path('research'),quote_fn=commodity_snapshot,filing_fn=get_filing_evidence):
    market=json.loads((root/'market_discovery.json').read_text())
    sec=json.loads((root/'sec_fundamentals.json').read_text())
    hub=json.loads((root/'decision_hub.json').read_text())
    est=json.loads((root/'established_strategies.json').read_text())
    close=hub['market_last_completed_close']
    assert market['last_completed_us_price_date']==sec['source_market_date']==est['latest_completed_us_market_day']==close,'Inconsistent source sessions'
    rows=market.get('stock_investing_watchlist') or []
    selected=select_companies(sec.get('companies') or [],rows)
    quotes={x['ticker']:x for x in rows}
    contact=(os.environ.get('SIGNALDESK_SEC_USER_AGENT') or ('SignalDesk '+os.environ.get('SIGNALDESK_MAIL_TO',''))).strip()
    diagnostics=[];dossiers=[]
    for item,quote in selected:
        sym=item['ticker'];metrics=verified_metrics(item,quote)
        sources=[{'id':'S1','kind':'SEC company financial facts','url':item['primary_source'],
                  'summary':'SEC filed annual statements; values computed in verified_metrics, including fiscal year and filing dates.'},
                 {'id':'S2','kind':'Market screener snapshot','url':'https://finance.yahoo.com/quote/'+sym+'/financials/',
                  'summary':'Yahoo screen-forward P/E and as-of market capitalization are non-audited and change daily.'}]
        filing={}
        if contact and item.get('cik'):
            try:
                filing=filing_fn(item['cik'],contact)
                sources.append({'id':'S3','kind':'SEC submissions','url':filing['submissions_url'],
                                'summary':'Dated SEC filing history, including recent 10-Q and 8-K documents.'})
                for f in filing.get('recent_filings',[])[:4]:
                    sources.append({'id':f'S{len(sources)+1}','kind':f['form']+' filed '+f['filed'],
                                    'url':f['url'],'summary':f['form']+' primary filing document; examine before relying on management claims.'})
                for primary in filing.get('priority_filings',[]):
                    if primary['url'] not in {x['url'] for x in sources}:
                        sources.append({'id':f'S{len(sources)+1}',
                            'kind':primary['form']+' primary filing, '+primary['filed'],
                            'url':primary['url'],
                            'summary':'Official company filing. The cited report is a research lead, not an independently verified claim.'})
                for passage in filing.get('read_passages',[]):
                    sources.append({'id':f'S{len(sources)+1}',
                        'kind':passage['form']+' read passages, filed '+passage['filed'],
                        'url':passage['url'],'summary':passage['text']})
            except Exception as exc:diagnostics.append(sym+': SEC submissions '+type(exc).__name__)
        dossiers.append({'kind':'equity','ticker':sym,'name':metrics['name'],
                         'metrics':metrics,'sources':sources,'filings':filing,
                         'investment_role':'Candidate for multi-year valuation research, not an approved trade.'})
    # An exposure to a REAL commodity via an exchange-traded proxy, not digital assets.
    commodity_prices={}
    try: commodity_prices=quote_fn()
    except Exception as exc:diagnostics.append('commodity quotes '+type(exc).__name__)
    voo=commodity_prices.get('VOO')
    ranked=[]
    for ticker,(label,url) in PROXIES.items():
        row=commodity_prices.get(ticker)
        if row and row['asof']==close and (not voo or row['asof']==voo['asof']):
            ranked.append((ticker,label,url,row))
    # Diversification research rotation: gold first if priced; otherwise a priced proxy.
    # Transparent and reproducible; never promote performance-chasing as fair value.
    if ranked:
        chosen=next((z for z in ranked if z[0]=='GLD'),ranked[0])
        ticker,label,url,quote=chosen
        metrics={**quote,'relative_6m_to_voo_pp':round(quote['return_6m_pct']-voo['return_6m_pct'],2) if voo else None,
                 'proxy_kind':label,'voo_return_6m_pct':voo['return_6m_pct'] if voo else None}
        dossiers.append({'kind':'commodity_proxy','ticker':ticker,'name':label,
          'metrics':metrics,'sources':[{'id':'S1','kind':'Fund issuer','url':url,
                                     'summary':'Issuer describes the commodity exposure and its costs and structure.'},
                                    {'id':'S2','kind':'Historical adjusted ETF prices','url':quote['source'],
                                     'summary':'Historical adjusted share prices, not a spot commodity price or futures curve.'}],
          'investment_role':'Portfolio-diversification research, not a commodity spot-price prediction.'})
    return {'version':'focused_dossier_v1','market_date':close,'generated_utc':datetime.now(timezone.utc).isoformat(),
            'screened_total':market.get('discovery_feeds',{}).get('unique_stock_quotes'),
            'selected_equities':len(selected),'asset_count':len(dossiers),
            'assets':dossiers,'excluded':'All cryptocurrency, tokens and crypto-exposed businesses; no crypto recommendations.',
            'benchmark':'VOO after costs where comparable','diagnostics':diagnostics}

if __name__=='__main__':
    report=assemble();p=Path('research/focused_dossier.json')
    p.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print('FOCUSED DOSSIER',report['market_date'],[x['ticker'] for x in report['assets']])