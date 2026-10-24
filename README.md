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
