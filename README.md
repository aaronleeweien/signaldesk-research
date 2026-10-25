# SignalDesk Research

A **research-only** VOO strategy comparison and automated end-of-day dashboard.

This site is **not** a trading bot or an approved real-money signal source. It compares four predeclared strategies with monthly VOO DCA, uses 2013–2021 for model selection, and holds out 2022 onward for evaluation. Live market-data retrieval and GitHub Pages publishing must succeed before real historical results appear.

**Privacy:** This repository and the published dashboard are public. Never add brokerage credentials, balances, positions, account statements, or other personal data.

**Status:** Initial research deployment. Workflow must pass and GitHub Pages must be enabled via **Settings → Pages → Source: GitHub Actions**.

The repository contains automated code and validation tests. Failed data downloads stop publication; they never generate invented signals. All reported model targets are for **paper research only**.

## Primary-source research (SEC)

The daily article now also attempts an **independent company filing check** for up to four existing US stock screener candidates. It reads SEC 10-K annual XBRL facts for revenue, year-on-year revenue growth, net income, operating cash flow, capital spending, free cash flow, and a backward-looking FCF yield against the screener's market cap. It provides direct SEC links and explicitly labels every missing value. This does **not** create forward profit forecasts, discounted-cash-flow fair values, independent evidence of a stock outperforming VOO, or live buy/sell approval. It does not eliminate selection/survivorship bias.

SEC automated access requires an identifying User-Agent. Add GitHub Actions secret `SIGNALDESK_SEC_USER_AGENT` with a value like `SignalDesk Research contact-you-control@example.com`. If this is absent, the workflow can use the `SIGNALDESK_MAIL_TO` secret as its SEC contact address. If neither exists, the report openly states that the SEC check is unavailable and the remaining research continues.

## Daily full-article Gmail delivery (not yet active until secrets configured)

The Actions workflow currently runs at **09:45 Singapore time, Tuesday–Saturday**, subject to GitHub's scheduling delays, corresponding to the usual preceding US market session. It only sends on scheduled runs **after** research and the website publish successfully finish; no email for ordinary code pushes or reruns. Market-date mismatches or a report older than four NY calendar days block delivery.

Set these **GitHub repository → Settings → Secrets and variables → Actions → New repository secret**:

- `SIGNALDESK_MAIL_TO`: your recipient Gmail address.
- `SIGNALDESK_GMAIL_FROM`: Gmail sender account address (can be the same Gmail account).
- `SIGNALDESK_GMAIL_APP_PASSWORD`: a **Google app password**, not the normal account password. Turn on Google 2-Step Verification and create an app password if the account permits it. Paste only in GitHub Secrets, NEVER in the public repository or ChatGPT. Not all Google accounts support app passwords.

Optionally set `SIGNALDESK_SEC_USER_AGENT` as explained above.

The email includes both a plain-text research article and the HTML article with source links. The recipient and sender addresses are only in GitHub Actions secrets, and the committed email receipt contains **dates only**, not addresses. Failed SMTP sends fail the scheduled workflow rather than pretending delivery succeeded. Email is not active merely because the code exists; verify a successful scheduled run and receipt after configuring secrets. No report is sent on the normal US weekend, when there is no new market close.

## Focused AI research desk (v2; no cryptocurrency)

The daily publication at `report.html` is now a **focused multi-asset research note** rather than a wall of screens. The legacy quantitative pages and paper ledgers are retained. The research pipeline selects up to two SEC-filed companies whose financial information is available, plus one commodity ETF exposure (physical gold first when a current GLD quote is available; other eligible noncrypto physical or futures proxies may be researched later). **No cryptocurrency and no crypto-linked companies or tokens** are eligible for selection.

Source chain: existing broad screener → official SEC XBRL figures → recent SEC filings with short passages where publicly reachable → independent historical ETF quotes for commodity comparison → structured OpenAI analyst → independent skeptical reviewer → deterministic valuation and evidence presentation. The AI only gets public research data, never brokerage credentials or email app passwords. It may not introduce new numeric return targets into the report. Citations are restricted to retrieved source identifiers. Quantitative results are still supplied by Python and never changed by the AI. The report is research-only, and offers explicit opposing arguments and decision conditions instead of forced daily BUY signals.

### Activate unattended AI analysis

ChatGPT Plus **does not cover OpenAI API usage**. In repository **Settings → Secrets and variables → Actions → New repository secret**, add:

- `OPENAI_API_KEY`: An OpenAI API secret key created under your own API account at https://platform.openai.com/api-keys . Do **not** paste the key into this public repository or ChatGPT. Configure API spend limits in the OpenAI platform first. The default model in the scheduled workflow is `gpt-6.1-sol`.
- The existing three Gmail secrets stay unchanged. Your existing Gmail app password is **not** an OpenAI API key and must not be reused.
- `SIGNALDESK_SEC_USER_AGENT`: Optional explicit SEC contact string, otherwise the workflow uses the stored recipient email as contact only for SEC requests.

If the API key has not been configured, the automated publication still provides financial evidence and detailed deterministic asset investigation. **It accurately labels its AI-review count**; it never claims that the model researched an asset when it did not. On API errors, reports retain the valid calculations rather than fabricating research. Delayed or inconsistent input dates block new reports before mailing.

A separate company-specific forecast and rigorous true historical point-in-time fundamental database remain methodological research objectives; the current fixed-parameter reverse cash-flow exercise must not be interpreted as a reliable fair-value prediction. Model output must be manually reviewed before acting on a particular security. Daily scheduled emails will contain the focused report after website deployment.

Provider documentation: https://developers.openai.com/api/docs/models/gpt-6.1-sol and https://developers.openai.com/api/docs/guides/structured-outputs . GitHub Models was retired on 2026-07-30, so its old free inference API is **not** used.
