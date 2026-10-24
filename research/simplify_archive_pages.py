"""Presentation-only readability pass for the older SignalDesk homepage and archives.

Runs AFTER all numerical research and page generators. It NEVER changes signal
inputs, trade rules, results, published data JSON or any model output. The
nine main pages have their own more specific short explanations in templates.
"""
from pathlib import Path
import re

COPY={
 "index.html":{
    "title":"Start here: what should I do?",
    "answer":"This is an older strategy research page. Its model positions are NOT real trading instructions.",
    "action":"Open the Daily Decision Centre for the latest investment ideas and trade setups, with a clear YES/NO conclusion."
 },
 "factor_paper.html":{
    "title":"What is this SPMO paper journal?",
    "answer":"It records pretend SPMO portfolio decisions and their dates. It does NOT send brokerage orders.",
    "action":"Use it to check whether model decisions were saved before the next market move. Do not buy just because a paper signal says BUY."
 },
 "stocks_paper.html":{
    "title":"What is this stock paper journal?",
    "answer":"These are pretend trades from a stock-picking experiment. The historical stock list has survivorship bias.",
    "action":"Do not copy its stock purchases. Use the Daily Decision Centre for current research, and check forward performance later."
 },
 "forward.html":{
    "title":"What is this older paper-trade archive?",
    "answer":"It shows pretend investment choices saved by older models. No real money was used.",
    "action":"Do not use its old BUY/SELL labels as today's instructions. See the newer Forward Paper Portfolio for tracked results."
 }
}
STYLES="""<style>
.beginner-result{background:#102c39;color:#ecf7f4;border:1px solid #558785;border-radius:14px;padding:17px 20px;margin:15px 0 23px;line-height:1.5;font-family:system-ui,-apple-system,sans-serif}
.beginner-result h2{margin:0 0 11px;font-size:19px;color:#fff}
.beginner-result p{margin:9px 0;color:#ecf7f4;font-size:15px}
.beginner-result strong{color:#aaf2da}
.beginner-result small{font-size:12px;color:#c5dde0;display:block;margin-top:12px}
.beginner-result a{color:#b8e7ff;font-weight:650}
@media(max-width:600px){.beginner-result{padding:14px 15px}.beginner-result p{font-size:14px}}
</style>"""

def readable_card(info):
    from html import escape
    return ('<section class="beginner-result" aria-label="Simple answer">'
      f'<h2>{escape(info["title"])}</h2>'
      f'<p><strong>Simple answer:</strong> {escape(info["answer"])}</p>'
      f'<p><strong>What should I do?</strong> {escape(info["action"])}</p>'
      '<small><strong>Jargon:</strong> Paper trade = pretend trade. '
      'DCA = invest regularly. Backtest = test a rule on old prices. '
      'You can still read every original table and number below.</small>'
      '<p><a href="decisions.html">Open today&#39;s investment and trade decisions →</a></p>'
      '</section>')

def simplify_document(raw,info):
    if 'class="beginner-result"' in raw:
        return raw
    out=raw
    if "</head>" in out:
        out=out.replace("</head>",STYLES+"</head>",1)
    elif "</style>" in out:
        out=out.replace("</style>","</style>"+STYLES,1)
    else:
        # Keep the doctype at the very start, even on old headless HTML pages.
        out=re.sub(r"(<main(?:\\s[^>]*)?>)",lambda m:STYLES+m.group(1),out,count=1,flags=re.I)
    card=readable_card(info)
    new,count=re.subn(r"(<main(?:\s[^>]*)?>)",lambda m:m.group(1)+card,out,count=1,flags=re.I)
    if not count:
        new,count=re.subn(r"(<body(?:\s[^>]*)?>)",lambda m:m.group(1)+card,out,count=1,flags=re.I)
    if not count:
        raise ValueError("Cannot place beginner-friendly card (no <main> or <body>)")
    return new

def main():
    for name,info in COPY.items():
        file=Path("site")/name
        if not file.exists():
            print("SKIP (legacy page absent):",name)
            continue
        original=file.read_text(encoding="utf-8")
        rewritten=simplify_document(original,info)
        if rewritten!=original:
            file.write_text(rewritten,encoding="utf-8")
        print("Plain language:",name)

if __name__=="__main__":
    main()
