"""Qualitative, source-grounded context for a few SignalDesk research assets.

Tracks *coverage and hypotheses*, never claims to measure all investor sentiment.
Google News is an unofficial RSS index containing headlines, not verified article
contents or a representative survey. SEC filings remain primary company evidence.
Dates and attribution survive into the public daily report.
No OpenAI API subscription is needed for this monitored context.
"""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen
import json
import re
import xml.etree.ElementTree as ET

try:
    from .deep_dossier import CRYPTO
except ImportError:
    from deep_dossier import CRYPTO

SEARCH_ROOT = "https://news.google.com/rss/search?q="
NARRATIVE_RULES = (
    ("demand", ("demand", "sales", "orders", "customer", "contract", "revenue", "growth", "shipment"),
     "If this reflects real changes in customer spending, it could change future sales and cash generation.",
     "A strong headline may describe an already expected development, or orders that are not yet profitable.",
     "Compare the next reported sales and customer guidance with the previous filing and market expectations."),
    ("profitability", ("margin", "cost", "pricing", "expense", "profit", "earnings", "refining", "spread"),
     "Changes in selling prices or operating costs affect the fraction of sales that becomes profit and cash.",
     "A temporary price or cost improvement may disappear when conditions normalize.",
     "Check reported operating margins, cash conversion and the reasons for changes."),
    ("competition", ("competitor", "competition", "market share", "rival", "product", "launch"),
     "A lasting competitive change could alter future demand or the prices the company can charge.",
     "A competitor announcement does not itself prove customers will switch.",
     "Look for customer wins, product economics and margin changes in company filings."),
    ("policy", ("tariff", "regulat", "sanction", "approval", "lawsuit", "antitrust", "court", "policy"),
     "A rule or legal outcome could affect costs, demand, or the company's ability to operate.",
     "The impact could be limited, delayed, challenged or already reflected in the price.",
     "Check the actual decision, timing, geographic exposure and estimated cash-flow impact."),
    ("financing", ("debt", "financ", "interest", "rate", "bond", "buyback", "dividend", "liquid"),
     "Borrowing costs or capital allocation can affect how much future cash ultimately belongs to shareholders.",
     "Higher dividends or buybacks can be funded by debt and are not automatically value creation.",
     "Check the balance sheet, debt maturities and cash available after capital spending."),
    ("commodity", ("gold", "silver", "oil", "crude", "commodity", "inflation", "dollar", "yield", "supply"),
     "Changes in commodity supply, demand, currency or interest rates can alter what investors will pay for the exposure.",
     "Even a convincing macro narrative may already be priced in and an ETF may not track spot prices exactly.",
     "Compare actual commodity moves, real yields, currency shifts and the fund's tracking costs."),
)

def query_for(asset):
    name=asset.get("name", "").strip()
    if asset["kind"] == "commodity_proxy":
        term={"GLD":"gold prices ETF","SLV":"silver prices ETF",
              "USO":"crude oil prices ETF","DBA":"agricultural commodity ETF"}.get(
                  asset["ticker"],"commodity ETF")
    else:
        # Use recognizable company name rather than ambiguous short ticker.
        base=re.sub(r"\b(INCORPORATED|INCORPORATION|INC|CORPORATION|CORP|PLC|CO|COMPANY|LTD)\b",
                    "",name,flags=re.I).strip(" ,.")
        term=base or asset["ticker"]
    return SEARCH_ROOT+quote('"' + term + '" when:7d')+"&hl=en-US&gl=US&ceid=US:en"

def fetch_rss(url):
    req=Request(url,headers={"User-Agent":"SignalDeskResearch/1.0 public market news monitor",
                             "Accept":"application/rss+xml, application/xml, text/xml"})
    with urlopen(req,timeout=18) as resp:
        return resp.read(500_000)

def normalize_words(value):
    return re.sub(r"\s+"," ",unescape(re.sub(r"<[^>]*>","",value or ""))).strip()

def identify_topic(title):
    low=title.lower()
    for topic,words,*rest in NARRATIVE_RULES:
        if any(w in low for w in words):
            return topic
    return "other"

def has_entity(title,asset):
    lower=title.lower()
    ticker=asset["ticker"].lower()
    if asset["kind"]=="commodity_proxy":
        return any(w in lower for w in
                   {"GLD":("gold","spdr gold"),"SLV":("silver",),
                    "USO":("oil","crude"),"DBA":("agricultur","crop")}.get(
                        asset["ticker"],("commodity",)))
    name=asset.get("name","").lower()
    stem=re.split(r"\b(?:inc|corp|co|ltd|plc)\b",name)[0].strip(" ,.")
    if len(stem)>6 and stem in lower:return True
    # Recognize distinctive one-word brands (e.g., Marvell) when news drops a
    # formal suffix. Avoid ambiguous first names such as Marathon or United.
    first=stem.split()[0] if stem else ""
    if len(first)>=7 and first not in ("marathon","united","general","american","national","global") and bool(
            re.search(r"\\b"+re.escape(first)+r"\\b",lower)):
        return True
    # Avoid treating an unrelated article with a three-letter common acronym
    # as evidence that the company is under discussion.
    return len(ticker)>=4 and bool(re.search(r"\b"+re.escape(ticker)+r"\b",lower))

def parse_news(xml,asset,now=None,max_items=6):
    now=now or datetime.now(timezone.utc)
    root=ET.fromstring(xml)
    articles=[];seen=set()
    for item in root.findall(".//channel/item"):
        title=normalize_words(item.findtext("title"))
        link=normalize_words(item.findtext("link"))
        stamp=item.findtext("pubDate") or ""
        outlet=normalize_words(item.findtext("source"))
        if not title or not link.startswith("https://news.google.com/"):continue
        if not has_entity(title,asset) or CRYPTO.search(title):continue
        try:
            when=parsedate_to_datetime(stamp).astimezone(timezone.utc)
        except (ValueError,TypeError,IndexError):continue
        if when>now+timedelta(minutes=15) or now-when>timedelta(days=8):continue
        norm=re.sub(r"[^a-z0-9]","",title.lower())
        if norm in seen:continue
        seen.add(norm)
        articles.append({"title":title[:210],"published_utc":when.isoformat(),
                         "publisher":outlet[:70] or "publisher not supplied",
                         "url":link,"topic":identify_topic(title)})
    articles.sort(key=lambda x:x["published_utc"],reverse=True)
    return articles[:max_items]

def explain_narratives(articles):
    """Explicit if/then causal bridge and the strongest check, NOT polarity scoring."""
    result=[];used=set()
    for article in articles:
        topic=article["topic"]
        if topic=="other" or topic in used:continue
        used.add(topic)
        rule=next(rule for rule in NARRATIVE_RULES if rule[0]==topic)
        result.append({
            "topic":topic,"headline":article["title"],"published_utc":article["published_utc"],
            "publisher":article["publisher"],"source_url":article["url"],
            "mechanism":rule[2],"competing_reading":rule[3],
            "test":rule[4],"evidence_level":"headline_coverage_not_confirmed_event"
        })
        if len(result)>=3:break
    return result

def record_for_asset(asset,fetch=fetch_rss,now=None):
    now=now or datetime.now(timezone.utc)
    url=query_for(asset)
    problems=[];articles=[]
    try:
        articles=parse_news(fetch(url),asset,now=now)
    except (OSError,ET.ParseError,ValueError) as exc:
        problems=[type(exc).__name__]
    return {"asof_utc":now.isoformat(),"search_url":url,
        "news_window_days":7,"headline_sample":articles,
        "narratives":explain_narratives(articles),
        "coverage_limit":"An indexed RSS headline sample, not a full-text article review, verified event, consensus forecast, or investor sentiment poll.",
        "fetch_issues":problems}

def enrich(dossier,fetch=fetch_rss,now=None):
    """Add source-linked coverage without changing numerical metrics or decisions."""
    now=now or datetime.now(timezone.utc)
    for asset in dossier.get("assets",[]):
        context=record_for_asset(asset,fetch=fetch,now=now)
        asset["qualitative_context"]=context
        existing={s["url"] for s in asset.get("sources",[])}
        for h in context["headline_sample"]:
            if h["url"] in existing:continue
            sid="S"+str(len(asset["sources"])+1)
            asset["sources"].append({"id":sid,"kind":"News-index headline · "+h["publisher"]+
                " · "+h["published_utc"][:10],"url":h["url"],
                "summary":"Headline only, not checked article text: "+h["title"]})
            existing.add(h["url"])
    dossier["qualitative_asof_utc"]=now.isoformat()
    dossier["qualitative_method"]="Dated headline watch + SEC filings; causal implications are conditional, not sentiment forecasts."
    return dossier

def main(root=Path("research"),fetch=fetch_rss):
    path=root/"focused_dossier.json"
    report=json.loads(path.read_text(encoding="utf-8"))
    if not report.get("market_date") or not report.get("assets"):
        raise ValueError("Fresh, focused asset dossier required")
    enriched=enrich(report,fetch=fetch)
    path.write_text(json.dumps(enriched,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print("QUALITATIVE CONTEXT",report["market_date"],
          [(a["ticker"],len(a["qualitative_context"]["headline_sample"])) for a in report["assets"]])
    return enriched

if __name__=="__main__":
    main()
