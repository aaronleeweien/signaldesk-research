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
        'financial_health':("Unlike a company, a commodity has no earnings or free cash flow to forecast. "
            "Its case depends on economic demand, interest rates, currency conditions and fund costs."),
        'valuation':("For this exposure, monitor underlying commodity prices, financing conditions and ETF tracking costs "
            "rather than applying a company discounted-cash-flow formula."),
        'counter_case':("If interest-bearing assets become relatively more attractive, a commodity without "
            "cash distributions can lose demand. Past price momentum alone is not evidence of future outperformance."),
        'decision':("DIVERSIFICATION WATCH, not a performance-chasing trade. Compare the benefit of adding "
            "this exposure to your existing VOO holdings against extra costs and volatility."),
        'next_check':("Compare the fund's issuer documentation, charges and tracking against VOO, "
            "then test a modest allocation across different inflation and equity-market regimes.")}

def qualitative_coverage(asset):
    """Preserve a traceable causal chain rather than guessing a sentiment score."""
    q=asset.get('qualitative_context') or {}
    sample=q.get('headline_sample') or []
    narratives=q.get('narratives') or []
    return {'asof_utc':q.get('asof_utc'),
        'headlines':sample[:6],
        'narratives':narratives[:3],
        'search_url':q.get('search_url'),
        'coverage_limit':q.get('coverage_limit') or
            'Headline coverage is not proof of an investor belief or a company event.',
        'source_status':('recent_index_headlines' if sample else 'primary_filings_only'),
        'filing_observations':[
            {'form':r.get('form'),'filed':r.get('filed'),'url':r.get('url'),
             'excerpt':(r.get('text') or '')[:420]}
            for r in ((asset.get('filings') or {}).get('read_passages') or [])
            if r.get('text') and r.get('url')][:2]}

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

def manual_research_prompt(asset):
    """Evidence-first ChatGPT handoff, no API calls or account information."""
    source_lines='\\n'.join(
        f"- {src['id']} ({src['label']}): {src['url']}"
        for src in asset['sources'][:14])
    q=asset.get('qualitative') or {}
    headline_lines='\\n'.join(
        f"- {h['published_utc'][:10]} | {h['publisher']}: {h['title']}"
        for h in q.get('headlines',[])[:6])
    return ("Research "+asset['name']+" ("+asset['ticker']+") for someone whose default "
        "alternative is regular VOO investing. The market close is "+asset['research_date']+
        ". Investigate, do not place an order.\\n\\n"
        "OPEN AND VERIFY the dated primary filings and sources, rather than trusting "
        "a headline to mean an event happened. Examine the business, competitors, "
        "earnings drivers, cash flows, balance sheet, management guidance and risks. "
        "Clearly separate filed facts, claims, media interpretations, consensus "
        "expectations and your own assumptions.\\n\\n"
        "Explain in connected simple English, defining each financial term at first use: "
        "(1) what happened; (2) why it affects future revenue, profits, cash flow or risk; "
        "(3) what expectations the current market price may already reflect; "
        "(4) how reasonable investors could disagree; (5) bull/base/bear scenarios with "
        "explicit sourced assumptions; (6) major upcoming catalysts; (7) strongest opposing "
        "evidence; (8) measurable falsification tests; (9) costs and risk versus VOO; and "
        "(10) an actionable WATCH / INVESTIGATE / NO-TRADE conclusion. "
        "Do not skip causal steps or invent consensus forecasts, sentiment surveys, "
        "price targets or missing financial numbers. Clearly label inferences and proxy "
        "estimates, and explain how to test them. No cryptocurrency or crypto exposure. "
        "Cite the evidence beside each material claim.\\n\\nSources:\\n"+source_lines+
        ("\\n\\nNews leads to confirm (not established facts):\\n"+headline_lines if headline_lines else ""))

def briefing(dossier,investigation):
    if dossier['market_date']!=investigation['market_date']:
        raise ValueError('AI and quantitative source dates do not match')
    assets=[]
    for asset in dossier['assets'][:3]:
        verified=verified_equity(asset) if asset['kind']=='equity' else verified_commodity(asset)
        ai=joined_critical(investigation['investigations'].get(asset['ticker'],{}))
        assets.append({'ticker':asset['ticker'],'name':asset['name'],'kind':asset['kind'],
                       'facts':verified,'ai':ai,'sources':source_list(asset),
                       'qualitative':qualitative_coverage(asset),'research_date':dossier['market_date']})
    for item in assets:
        item['manual_research_prompt']=manual_research_prompt(item)
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
            'qualitative_asof_utc':dossier.get('qualitative_asof_utc'),
            'conclusion':'Maintain the VOO baseline; place new ideas on a documented research watchlist rather than trade on a screener ranking.',
            'method':('SEC filings, dated market prices and independently attributed news headlines. '
                'Headline themes are hypotheses, NOT votes, crowd sentiment measurements, or forecasts. '
                'Financial calculations use Python; optional AI analysis is separately labelled.'),
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
        q=a.get('qualitative') or {}
        lines += ['**What the financial press is covering (as of '+str(q.get('asof_utc') or 'the report')+'):**']
        if q.get('narratives'):
            lines += ['The headlines below are reports of *coverage*, not verified company events '
                      'or a survey of investor opinion. Some may have appeared after the market close shown above.']
            for n in q['narratives']:
                lines += [f"**Headline ({n['published_utc'][:10]}, {n['publisher']}):** {n['headline']}",
                    '**Why it could affect value, if substantiated:** '+n['mechanism'],
                    '**Why the stock might not move as expected:** '+n['competing_reading'],
                    '**What would confirm or refute that interpretation:** '+n['test'],
                    '**Check the original news coverage:** '+n['source_url']]
        else:
            lines += ['**Decision now:** use the filed business results as the evidence base. '
                      'Do not infer bullish or bearish investor sentiment from an empty or incomplete '
                      'news sample; check the next filing and guidance against earlier company figures.']
        if q.get('filing_observations'):
            for r in q['filing_observations']:
                lines += [f"**Primary document to cross-check ({r['form']}, filed {r['filed']}):** {r['url']}"]
        lines += ['**Important distinction:** A well-supported business story can still be a poor '
                  'investment if the stock price already reflects that story.']
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
        lines += ['**Copy-ready guided ChatGPT investigation:**',
                  '```text',a['manual_research_prompt'],'```']
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
        q=a.get('qualitative') or {}
        body+='<h3>Market narratives: what is being discussed, and why it matters</h3>'
        if q.get('narratives'):
            asof=q.get('asof_utc') or 'unknown'
            body+=p('How to read this', 'These are dated news-index headlines as of '+asof+
                    '. A headline identifies a possible change in expectations, not a confirmed event, '
                    'an investor-sentiment poll, or proof that the share price will rise. Some headlines '
                    'may postdate the last completed US market session.')
            for n in q['narratives']:
                body+='<div class="narrative">'
                body+=p('What appeared ('+n['published_utc'][:10]+'; '+n['publisher']+')',
                       n['headline'])
                body+=p('Why it could matter IF true',n['mechanism'])
                body+=p('Why that does not prove a profitable trade',n['competing_reading'])
                body+=p('The decisive follow-up check',n['test'])
                body+=f'<p><a href="{esc(n["source_url"],quote=True)}" rel="noopener noreferrer">Read cited news coverage</a></p>'
                body+='</div>'
        else:
            body+=p('Reasoned conclusion',
                    'Use the business filings and valuation cases for the current decision. '
                    'Without a representative set of recent attributed stories, do not invent a '
                    'market-mood label. Check actual company guidance and the next financial release.')
        body+=p('The essential link',
                'A story changes investment value only if it changes expected future cash flows, '
                'the risk of receiving them, or the price investors will pay—and only if that '
                'change was not already fully reflected in the current share price.')
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
        body+='<details class="ai-prompt"><summary>Investigate with ChatGPT: copy the source-linked research brief</summary>'
        body+='<p>This uses your current ChatGPT access and does not require an API subscription. Verify the sources and ask ChatGPT to challenge its own case.</p>'
        body+='<pre>'+esc(a['manual_research_prompt'])+'</pre></details>'
        body+=f'<p class="decision">{esc(f["decision"])}</p>'+p('Next research action',f['next_check'])
        links=' · '.join(f'<a href="{esc(s["url"],quote=True)}" rel="noopener noreferrer">{esc(s["id"])}: {esc(s["label"])}</a>' for s in a['sources'])
        sections.append(f'<section class="asset"><div class="eyebrow">DOSSIER {i:02d} · {"COMPANY" if a["kind"]=="equity" else "COMMODITY EXPOSURE"}</div><h2>{esc(a["ticker"])} <small>{esc(a["name"])}</small></h2>{body}<p class="evidence"><strong>Open the underlying evidence:</strong> {links}</p></section>')
    mode=(f"Two-pass AI analyst and skeptical reviewer completed for {r['ai_analysed_count']} of {len(r['assets'])} cases."
          if r['ai_analysed_count'] else "This edition uses filed financial evidence and deterministic research; model-based investigation activates after an AI API key is configured.")
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>SignalDesk — Focused Investment Research</title>
<style>body{{margin:0;background:#f7f9fa;color:#142536;font:17px/1.75 Georgia,serif}}main{{max-width:900px;margin:auto;padding:30px 22px 70px}}h1,h2,.decision,.eyebrow,.nav,.meta,.evidence,.summary,footer{{font-family:system-ui,-apple-system,Arial,sans-serif}}h1{{font-size:clamp(30px,6vw,51px);letter-spacing:-.04em;line-height:1.12}}h2{{font-size:28px;line-height:1.25;margin:8px 0 20px}}h2 small{{display:block;font-size:15px;font-weight:400;color:#5c6c7b;margin-top:4px}}.eyebrow{{font-size:11px;letter-spacing:.14em;font-weight:800;color:#50697b}}.meta{{font-size:13px;color:#607082}}.intro{{font-size:20px;line-height:1.55}}.summary{{font-size:17px;background:#eef3f7;border-left:4px solid #345879;padding:18px;margin:20px 0}}.asset{{background:white;border:1px solid #d6e0e8;border-radius:14px;margin:32px 0;padding:28px}}.asset p{{margin:13px 0}}.asset h3{{font:700 18px/1.4 system-ui,-apple-system,Arial,sans-serif;margin:25px 0 10px}}.narrative{{border-left:3px solid #9ab4c6;background:#f2f6fa;padding:12px 16px;margin:14px 0}}.ai-prompt{{margin:18px 0;border:1px solid #b9cbd8;border-radius:8px;padding:12px}}.ai-prompt summary{{font:700 14px/1.5 system-ui;cursor:pointer}}.ai-prompt pre{{white-space:pre-wrap;overflow-wrap:anywhere;font:13px/1.55 system-ui;padding:10px;background:#f5f8fa;border-radius:6px}}.asset strong{{font-family:system-ui,-apple-system,Arial,sans-serif;font-size:15px}}.decision{{background:#eff4f0;border-left:4px solid #437b68;padding:16px;font-size:15px;font-weight:700}}a{{color:#195d83;text-underline-offset:3px}}.evidence{{border-top:1px solid #e2e7eb;font-size:13px;padding-top:15px;word-break:break-word}}footer{{font-size:13px;color:#627180;padding-top:20px;border-top:1px solid #d6dce1}}.nav{{display:flex;flex-wrap:wrap;gap:18px;font-size:13px;margin:16px 0}}@media(max-width:650px){{.asset{{padding:19px}}main{{padding:22px 14px}}body{{font-size:16px}}}}</style>
</head><body><main><div class="eyebrow">SIGNALDESK · INDEPENDENT RESEARCH DESK · NO CRYPTO</div><h1>Fewer ideas.<br>Stronger arguments.</h1><div class="meta">Completed US trading session: <b>{esc(r['date'])}</b> · Research only · No auto-trading</div>
<p class="intro">{esc(r['summary'])}</p><p class="meta">Market narrative monitoring updated at: {esc(r.get('qualitative_asof_utc') or 'not recorded')}. This timestamp can be later than the market-pricing date.</p><div class="summary"><b>Bottom line:</b> {esc(r['conclusion'])}</div>
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