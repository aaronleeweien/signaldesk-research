"""Publish a focused magazine-style research briefing, with evidence and decisions.

Deliberately replaces the legacy daily report URL while preserving older
quantitative pages. Never invents a price target, BUY command or AI research.
"""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
from html import escape as H
import json

REPORT_URL='https://aaronleeweien.github.io/signaldesk-research/report.html'

def amount(v):
    if v is None:return 'unreported in this filing extraction'
    val=abs(v)
    if val>=1e9:s=f'${val/1e9:.2f} billion'
    elif val>=1e6:s=f'${val/1e6:.1f} million'
    else:s=f'${val:,.0f}'
    return '-'+s if v<0 else s

def percent(v):return f'{v:+.1f}%' if v is not None else 'not quantified'

def source_list(asset):
    return [{'id':s['id'],'label':s['kind'],'url':s['url']} for s in asset['sources']]

def verified_equity(asset):
    m=asset['metrics'];ticker=asset['ticker']
    fcf=m['fcf_usd'];cash=m['cash_usd'];debt=m['debt_usd']
    note=(f"{ticker} reported {amount(m['revenue_usd'])} in annual sales for its fiscal year "
          f"ending {m['fiscal_year_end']}. Sales changed {percent(m['revenue_growth_yoy_pct'])} "
          f"from the previous annual filing. Of those operations, {amount(m['operating_cash_usd'])} "
          f"became operating cash. After {amount(m['capital_spending_usd'])} of investment in "
          f"property and equipment, the simplified free cash flow was {amount(fcf)}. "
          f"Free cash flow is the money remaining after those investment costs; it is not the "
          f"same as accounting profit. The company generated positive free cash flow in "
          f"{m['fcf_positive_years']} of {m['fcf_years_available']} recorded years. [S1]")
    cap=(f"The latest available cash balance is {amount(cash)} and the SEC long-term debt tag "
         f"is {amount(debt)}. That debt tag is not a measure of every financial obligation. [S1]")
    pe=m['forward_pe'];implied=m['price_implied_fcf_growth_pct'];model=m['scenario_sensitivity']
    if implied is not None and model:
        scen='; '.join(f"{z['annual_fcf_growth_assumed_pct']:.0f}% growth → {z['value_as_pct_of_current_market_cap']:.0f}% of today's market cap"
               for z in model.values())
        val=(f"A reverse cash-flow check asks a useful question: what growth would today's price "
             f"need to justify it? Under deliberately fixed assumptions of an 11% required return, "
             f"2% perpetual growth and no net borrowing, the price implies approximately "
             f"{implied:.1f}% annual free-cash-flow growth over five years. "
             f"If growth were instead {scen}. These are sensitivity calculations, not "
             f"company-specific fair values. [S1][S2]")
    else:
        val=(f"The available annual figures permit a cash-flow-quality assessment. "
             f"The next investigation tests normalized cash generation against the current "
             f"market price, not a simple price-to-earnings shortcut. [S1][S2]")
    risk=("An important alternative explanation is that last year's cash generation may not "
          "represent a normal year. Competitive changes, industry cycles and working-capital "
          "timing can make a stock look inexpensive right before its profits decline. "
          "Our next test is to compare the latest quarterly filing with the prior three annual years.")
    return {'observation':note,'financial_health':cap,'valuation':val,
            'counter_case':risk,'decision':f"RESEARCH / WATCH {ticker}; no automatic purchase. "
                "Demand an independently justified earnings path and a margin of safety before diverting VOO contributions.",
            'next_check':'Read the latest 10-Q and management risk discussion; normalize margins and cash conversion across a full business cycle.'}

def verified_commodity(asset):
    m=asset['metrics'];ticker=asset['ticker'];relative=m.get('relative_6m_to_voo_pp')
    comparison=(f"That is {relative:+.1f} percentage points versus VOO over those same six months."
                if relative is not None else 'Its diversification value should be assessed against VOO across market regimes.')
    return {'observation':(f"{ticker} is an exchange-traded route into {m['proxy_kind'].lower()}, "
            f"not a claim of owning the spot commodity directly. Its adjusted share price "
            f"changed {percent(m['return_3m_pct'])} over three months and "
            f"{percent(m['return_6m_pct'])} over six months. {comparison} "
            f"Price date: {m['asof']}. [S1][S2]"),
        'financial_health':("Unlike a company, gold has no earnings or free cash flow to forecast. "
            "Its investment case depends on macroeconomic demand, real interest rates, currency conditions and fund costs."),
        'valuation':("For this exposure, monitor the gold price, real interest rates and the ETF's tracking costs "
            "rather than applying a company discounted-cash-flow formula."),
        'counter_case':("If interest-bearing assets become relatively more attractive, a commodity without "
            "cash distributions can lose demand. Past price momentum alone is not evidence of future outperformance."),
        'decision':("DIVERSIFICATION WATCH, not a performance-chasing trade. Compare the benefit of adding "
            "this exposure to your existing VOO holdings against extra costs and volatility."),
        'next_check':("Compare the fund's issuer documentation, charges and tracking against VOO, "
            "then test a modest allocation across different inflation and equity-market regimes.")}

def joined_critical(ai):
    analyst=ai.get('research') or {}
    reviewer=ai.get('adversarial_review') or {}
    if not analyst or not reviewer:return None
    return {
        'explanation':analyst['summary'],'business':analyst['business_drivers'],
        'market_view':analyst['market_expectation'],
        'variant':analyst['variant_perception'],'catalyst':analyst['catalyst'],
        'bear':analyst['bear_case'],'invalidation':analyst['invalidation_trigger'],
        'benchmark':analyst['voo_comparison'],'monitor':analyst['what_to_track'],
        'review':reviewer['criticism'],'alternative':reviewer['alternative_explanation'],
        'revision':reviewer['revised_conclusion'],'next':reviewer['decision_condition'],
        'sources':list(dict.fromkeys(analyst['evidence_ids']+reviewer['evidence_ids']))}

def briefing(dossier,investigation):
    if dossier['market_date']!=investigation['market_date']:
        raise ValueError('AI and quantitative source dates do not match')
    assets=[]
    for asset in dossier['assets'][:3]:
        verified=verified_equity(asset) if asset['kind']=='equity' else verified_commodity(asset)
        ai=joined_critical(investigation['investigations'].get(asset['ticker'],{}))
        assets.append({'ticker':asset['ticker'],'name':asset['name'],'kind':asset['kind'],
                       'facts':verified,'ai':ai,'sources':source_list(asset)})
    if not assets:raise ValueError('No independently measured asset for focused research')
    return {'date':dossier['market_date'],'fresh':True,
            'title':'SignalDesk | Investment Research Desk',
            'headline':'VOO remains the default; investigate only a few clearly defined alternatives.',
            'subtitle':'Deep research is an argument to test, not a signal to buy.',
            'summary':('We keep a diversified VOO base. Today we concentrate on a few public-company and commodity '
                       'exposures, calculating what their historical accounts show, what their market prices assume, '
                       'and which future evidence should change our view.'),
            'assets':assets,'ai_analysed_count':sum(bool(x['ai']) for x in assets),
            'ai_configured':bool(investigation.get('ai_review_configured')),
            'research_failures_count':len(investigation.get('errors') or {}),
            'selected_from':dossier.get('screened_total'),
            'research_version':dossier['version'],
            'conclusion':'Maintain the VOO baseline; place new ideas on a documented research watchlist rather than trade on a screener ranking.',
            'method':'SEC filing facts + dated market data; quantitative valuations are scenario stress tests; source-bounded analyst and skeptical review only when configured.',
            'crypto_excluded':True}

def render_markdown(r):
    lines=['# '+r['title'],f"Market close: {r['date']}",
           '**'+r['headline']+'**',r['summary'],'',
           '## Today’s conclusion',r['conclusion'],'']
    for i,a in enumerate(r['assets'],1):
        f=a['facts'];lines += [f"## {i}. {a['ticker']} — {a['name']}",
           '**Why it is on the desk:** '+f['observation'],
           '**Financial context:** '+f['financial_health'],
           '**What today’s price appears to demand:** '+f['valuation']]
        if a['ai']:
            c=a['ai'];lines += [
                '**Investigative thesis:** '+c['explanation'],
                '**Business and economic drivers:** '+c['business'],
                '**What the market appears to assume:** '+c['market_view'],
                '**Where that view could be wrong:** '+c['variant'],
                '**What could cause revaluation:** '+c['catalyst'],
                '**The strongest opposing argument:** '+c['bear'],
                '**Independent reviewer’s challenge:** '+c['review'],
                '**Alternative explanation:** '+c['alternative'],
                '**Reviewer’s revised conclusion:** '+c['revision'],
                '**VOO comparison:** '+c['benchmark'],
                '**Thesis invalidation test:** '+c['invalidation'],
                '**What to track:** '+c['monitor'],
                '**Decision checkpoint:** '+c['next']]
        else:
            lines += ['**The opposing case:** '+f['counter_case']]
        lines += ['**Research decision:** '+f['decision'],
                  '**The next real investigation:** '+f['next_check'],
                  '**Primary evidence:**']
        for source in a['sources']:
            lines.append(f"- [{source['id']}] {source['label']}: {source['url']}")
        lines.append('')
    lines += ['## How the evidence is used',
        'Facts from SEC financial statements are not the same as estimates of next-year earnings. '
        'The cash-flow valuation is a numerical stress test; independent AI review adds interpretation '
        'only when source identifiers can be verified.',
        'Past performance and today’s valuation do not guarantee an outperforming investment. '
        'No crypto is included. This report makes no brokerage trades.',
        f"Research mode: {r['ai_analysed_count']} of {len(r['assets'])} opportunities received two-pass AI investigation. ",
        'See the permanent historical backtest and paper records at the SignalDesk website.']
    return '\n\n'.join(lines)+'\n'

def render_html(r):
    esc=H
    sections=[]
    def p(title,value):return f'<p><strong>{esc(title)}.</strong> {esc(value)}</p>'
    for i,a in enumerate(r['assets'],1):
        f=a['facts'];body=p('Why it deserves investigation',f['observation'])
        body+=p('Financial reality',f['financial_health'])+p('Valuation or economic pricing',f['valuation'])
        if a['ai']:
            c=a['ai']
            for title,key in [('The investment thesis','explanation'),('Business drivers','business'),
                 ('Market expectations','market_view'),('Why investors may be wrong','variant'),
                 ('Catalyst','catalyst'),('The bear case','bear'),('Skeptical review','review'),
                 ('Alternative explanation','alternative'),("Reviewer's verdict",'revision'),
                 ('Why compare against VOO','benchmark'),('What disproves the thesis','invalidation'),
                 ('Ongoing watchpoints','monitor'),('Decision checkpoint','next')]:
                body+=p(title,c[key])
        else:body+=p('The strongest competing interpretation',f['counter_case'])
        body+=f'<p class="decision">{esc(f["decision"])}</p>'+p('Next research action',f['next_check'])
        links=' · '.join(f'<a href="{esc(s["url"],quote=True)}" rel="noopener noreferrer">{esc(s["id"])}: {esc(s["label"])}</a>' for s in a['sources'])
        sections.append(f'<section class="asset"><div class="eyebrow">DOSSIER {i:02d} · {"COMPANY" if a["kind"]=="equity" else "COMMODITY EXPOSURE"}</div><h2>{esc(a["ticker"])} <small>{esc(a["name"])}</small></h2>{body}<p class="evidence"><strong>Open the underlying evidence:</strong> {links}</p></section>')
    mode=(f"Two-pass AI analyst and skeptical reviewer completed for {r['ai_analysed_count']} of {len(r['assets'])} cases."
          if r['ai_analysed_count'] else "This edition uses filed financial evidence and deterministic research; model-based investigation activates after an AI API key is configured.")
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>SignalDesk — Focused Investment Research</title>
<style>body{{margin:0;background:#f7f9fa;color:#142536;font:17px/1.75 Georgia,serif}}main{{max-width:900px;margin:auto;padding:30px 22px 70px}}h1,h2,.decision,.eyebrow,.nav,.meta,.evidence,.summary,footer{{font-family:system-ui,-apple-system,Arial,sans-serif}}h1{{font-size:clamp(30px,6vw,51px);letter-spacing:-.04em;line-height:1.12}}h2{{font-size:28px;line-height:1.25;margin:8px 0 20px}}h2 small{{display:block;font-size:15px;font-weight:400;color:#5c6c7b;margin-top:4px}}.eyebrow{{font-size:11px;letter-spacing:.14em;font-weight:800;color:#50697b}}.meta{{font-size:13px;color:#607082}}.intro{{font-size:20px;line-height:1.55}}.summary{{font-size:17px;background:#eef3f7;border-left:4px solid #345879;padding:18px;margin:20px 0}}.asset{{background:white;border:1px solid #d6e0e8;border-radius:14px;margin:32px 0;padding:28px}}.asset p{{margin:13px 0}}.asset strong{{font-family:system-ui,-apple-system,Arial,sans-serif;font-size:15px}}.decision{{background:#eff4f0;border-left:4px solid #437b68;padding:16px;font-size:15px;font-weight:700}}a{{color:#195d83;text-underline-offset:3px}}.evidence{{border-top:1px solid #e2e7eb;font-size:13px;padding-top:15px;word-break:break-word}}footer{{font-size:13px;color:#627180;padding-top:20px;border-top:1px solid #d6dce1}}.nav{{display:flex;flex-wrap:wrap;gap:18px;font-size:13px;margin:16px 0}}@media(max-width:650px){{.asset{{padding:19px}}main{{padding:22px 14px}}body{{font-size:16px}}}}</style>
</head><body><main><div class="eyebrow">SIGNALDESK · INDEPENDENT RESEARCH DESK · NO CRYPTO</div><h1>Fewer ideas.<br>Stronger arguments.</h1><div class="meta">Completed US trading session: <b>{esc(r['date'])}</b> · Research only · No auto-trading</div>
<p class="intro">{esc(r['summary'])}</p><div class="summary"><b>Bottom line:</b> {esc(r['conclusion'])}</div>
<nav class="nav"><a href="decisions.html">Quantitative research</a><a href="validation.html">Historical validation</a><a href="market.html">Full screening evidence</a><a href="established.html">ETF comparisons</a></nav>
{''.join(sections)}<footer><p><strong>Method.</strong> {esc(r['method'])}</p><p><strong>Review status.</strong> {esc(mode)}</p><p>Primary-company disclosures and historical price data carry uncertainty. An investment hypothesis is only as strong as its evidence, assumptions, and future checks. No order is placed and no claim of reliably outperforming VOO is made.</p></footer></main></body></html>'''

def publish(root=Path('research'),site=Path('site')):
    dossier=json.loads((root/'focused_dossier.json').read_text())
    analysis=json.loads((root/'ai_investigation.json').read_text())
    report=briefing(dossier,analysis)
    site.mkdir(parents=True,exist_ok=True)
    # Keep previous editorial report available for accountability.
    old=site/'report.html'
    if old.exists() and not (site/'report_legacy.html').exists():
        (site/'report_legacy.html').write_text(old.read_text(encoding='utf-8'),encoding='utf-8')
    (site/'report.html').write_text(render_html(report),encoding='utf-8')
    (site/'daily_brief.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    (site/'focused_dossier.json').write_text(json.dumps(dossier,indent=2)+'\n',encoding='utf-8')
    (root/'daily_brief.md').write_text(render_markdown(report),encoding='utf-8')
    (root/'focused_report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print('FOCUSED REPORT',report['date'],'assets',len(report['assets']),
          'AI reviewed',report['ai_analysed_count'])
    return report

if __name__=='__main__':publish()