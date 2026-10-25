"""No API billing or external news access required for qualitative logic tests."""
from datetime import datetime, timezone, timedelta
from pathlib import Path
import json
import tempfile
import unittest
from research import narrative_watch as n
from research import deep_publish as p

NOW=datetime(2026,10,25,2,tzinfo=timezone.utc)
NEWS_LINK="https://news.google.com/rss/articles/CBMiExample"

def fixture_rss(items):
    bits=[]
    for title,when,outlet,link in items:
        bits.append("<item><title><![CDATA["+title+"]]></title>"
            "<link>"+link+"</link><pubDate>"+when+"</pubDate>"
            "<source>"+outlet+"</source></item>")
    return ("<rss><channel>"+"".join(bits)+"</channel></rss>").encode()

class QualitativeResearchTests(unittest.TestCase):
    def stock(self):
        return {"ticker":"MRVL","name":"MARVELL TECHNOLOGY, INC",
            "kind":"equity","metrics":{},"sources":[],"filings":{"read_passages":[
                {"form":"10-Q","filed":"2026-08-28",
                 "url":"https://www.sec.gov/Archives/example.htm",
                 "text":"Management describes customer demand as uncertain."}]}}

    def test_news_coverage_is_not_a_sentiment_prediction(self):
        rows=[
          ("Marvell Technology customer demand grows - Source A","Fri, 23 Oct 2026 14:00:00 GMT","Source A",NEWS_LINK),
          ("Marvell Technology margins face higher costs - Source B","Sat, 24 Oct 2026 16:00:00 GMT","Source B",NEWS_LINK+"2"),
          ("Marvell Technology leads crypto tokens - Source C","Sat, 24 Oct 2026 19:00:00 GMT","Source C",NEWS_LINK+"3"),
          ("Other unrelated company profits soar","Sat, 24 Oct 2026 17:00:00 GMT","Source D",NEWS_LINK+"4")]
        parsed=n.parse_news(fixture_rss(rows),self.stock(),NOW)
        self.assertEqual(len(parsed),2)
        self.assertTrue(all("crypto" not in a["title"].lower() for a in parsed))
        discussions=n.explain_narratives(parsed)
        self.assertEqual(len(discussions),2)
        self.assertTrue(all(all(x[k] for k in ("mechanism","competing_reading","test"))
                            for x in discussions))
        self.assertTrue(all(x["evidence_level"]=="headline_coverage_not_confirmed_event"
                            for x in discussions))

    def test_stale_future_unrelated_and_invalid_links_excluded(self):
        items=[
          ("Marvell Technology growing sales","Thu, 15 Oct 2026 14:00:00 GMT","Source A",NEWS_LINK),
          ("Marvell Technology will report","Mon, 26 Oct 2026 14:00:00 GMT","Source B",NEWS_LINK+"2"),
          ("Marvell Technology revenue surprise","Fri, 23 Oct 2026 14:00:00 GMT","Source C","https://evil.test/a")]
        self.assertFalse(n.parse_news(fixture_rss(items),self.stock(),NOW))

    def test_enrichment_does_not_change_financial_metrics_or_market_date(self):
        asset=self.stock()
        asset["metrics"]={"annual_fcf":1_200_000}
        input_data={"market_date":"2026-10-23","assets":[asset],"version":"v1"}
        stories=fixture_rss([
          ("Marvell Technology revenue outlook - News Co",
           "Sat, 24 Oct 2026 14:00:00 GMT","News Co",NEWS_LINK)])
        out=n.enrich(input_data,fetch=lambda url:stories,now=NOW)
        self.assertEqual(out["market_date"],"2026-10-23")
        self.assertEqual(out["assets"][0]["metrics"]["annual_fcf"],1_200_000)
        self.assertEqual(len(out["assets"][0]["qualitative_context"]["narratives"]),1)
        self.assertEqual(len(out["assets"][0]["sources"]),1)
        self.assertIn("Headline only",out["assets"][0]["sources"][0]["summary"])

    def test_qualitative_article_keeps_the_reasoning_chain(self):
        asset={"ticker":"GLD","name":"Gold ETF","kind":"commodity_proxy",
            "metrics":{"proxy_kind":"Physical gold","return_3m_pct":4.0,
                "return_6m_pct":5.0,"asof":"2026-10-23"},
            "sources":[{"id":"S1","url":"https://news.google.com/rss/articles/xxx",
                        "kind":"source","summary":"headline"}],
            "qualitative_context":{"asof_utc":"2026-10-25T02:00:00+00:00",
                "headline_sample":[{"title":"Gold prices rise","publisher":"Example",
                                    "published_utc":"2026-10-24T12:00:00+00:00",
                                    "url":NEWS_LINK}],
                "narratives":[{"headline":"Gold prices rise","publisher":"Example",
                    "published_utc":"2026-10-24T12:00:00+00:00",
                    "source_url":NEWS_LINK,"mechanism":"Interest rates can affect demand.",
                    "competing_reading":"The market may already expect it.",
                    "test":"Check real yields and fund tracking costs."}]}}
        report=p.briefing({"market_date":"2026-10-23","assets":[asset],
            "version":"focused_v1","qualitative_asof_utc":"2026-10-25T02:00:00+00:00"},
            {"market_date":"2026-10-23","investigations":{},"ai_review_configured":False})
        html=p.render_html(report)
        md=p.render_markdown(report)
        for phrase in ("Why it could matter IF true",
                       "Why that does not prove a profitable trade",
                       "The decisive follow-up check"):
            self.assertIn(phrase,html)
        self.assertIn("not verified company events",md)
        self.assertIn("2026-10-25T02:00:00+00:00",html)

if __name__=="__main__":
    unittest.main()
