# Runbook: paper trading with the safe rebalance runner

This is a step-by-step guide for someone who has never traded. It covers the
simulator, an Alpaca **paper** (play-money) account, scheduling, alerts, the
kill switches and, only at the end, what a tiny live test can and cannot tell
you. Read `docs/research-report.md` first; the short version is that paper
trading proves the *code* works, not that a strategy makes money.

Nothing in this runner calls an LLM. It is plain, deterministic Python.

---

## 0. The rules that never change

1. **Dry run is the default.** Every command prints a plan and sends nothing
   unless you add `--no-dry-run`.
2. **Paper before live, always.** Live needs three separate switches at once:
   the environment variable `LIVE_TRADING=yes-live`, the flag `--live`, and the
   flag `--i-understand-live`. Missing any one of them aborts.
3. **Keys live in environment variables only**, never in files inside this
   repository, never in chat, never anywhere an AI coding agent can read them.
4. **Margin, short selling and options stay off** at the broker. The runner
   refuses to run if they are on.
5. **Every safety check is a hard stop.** When a guard trips, the run aborts,
   writes the reason to the ledger and sends an alert. It never "warns and
   continues".

---

## 1. Create an Alpaca paper-only account

1. Go to <https://alpaca.markets> and sign up with an email address. A
   *paper-only* account needs no identity documents and is open to residents of
   any country.
2. Log in to the dashboard and make sure you are looking at **Paper Trading**
   (there is a switch between Paper and Live near the top of the dashboard).

Facts about paper-only accounts that matter here:

| Fact | Consequence |
|---|---|
| The default paper balance is $100,000. | Create a new paper account at the size you actually intend to trade (step 2), otherwise every percentage looks the same but order sizes and fee effects do not. |
| A paper account's balance cannot be edited later. | To change the amount you create another paper account (or reset), which starts empty. |
| Paper-only accounts receive **IEX** market data only (one exchange, not the consolidated feed). | The runner takes its daily bars and its latest trade prices from Alpaca's IEX feed (`APCA_DATA_FEED=iex` is the default; see "Where prices come from" below). Prices can differ from the consolidated tape by a few cents. |
| Paper does **not** simulate regulatory fees, dividends, slippage or market impact. | The runner's shadow ledger adds *modelled* Alpaca fees and dividends. For paper trading, the ledger's modelled numbers are the profit-and-loss of record, not the paper account's equity. |

### Where prices come from

There are two price sources, and they are not interchangeable:

* **The research cache** (`data/cache/`, filled by `scripts/fetch_data.py`) is **personal-use research data
  downloaded from Yahoo**. Yahoo's terms forbid automated collection, so it is used only for the one-off research
  backtests and is never committed. When Alpaca's data cannot be read, a cache that **already exists on this
  machine** is read as it is, with a loud warning: the fallback never refreshes it and never downloads anything, so
  an unattended run never collects data from Yahoo. On a GitHub runner there is no cache, so an Alpaca data failure
  stops the run with a data error (exit 4, no orders) and the dead-man check reports the missed day. A stale cache
  is refused by the price freshness guard (`price_stale`).
* **Alpaca Market Data** is what the **unattended runner** uses (`--price-source alpaca`, the default whenever
  `APCA_API_KEY_ID` and `APCA_API_SECRET_KEY` are set): daily bars adjusted for splits and dividends
  (`adjustment=all`, at least 18 months of history) from the broker's own data API, which your account is licensed to
  use. The feed is `iex` by default, because a paper-only account is entitled to IEX only; set `APCA_DATA_FEED=sip`
  (or `--data-feed sip`) only on a funded account that has the consolidated feed. Cash dividends for the modelled
  ledger come from Alpaca's corporate-actions endpoint (best effort; 0 with a warning if unavailable).
* The T-bill yield used by the absolute-momentum rules is FRED's public DTB3 series, fetched with `--refresh-data`
  (the default for `--broker alpaca`) and refused if its last observation is more than 10 days old.

Every run records in the ledger which source and feed it used (`price_source`, `data_feed` on the `run_start` record,
and on the `hold` record of a month a strategy does not rebalance); a fallback to the cache is recorded as
`cache (fallback: alpaca ...; local, not refreshed)`. `--price-source cache` (with `--refresh-data`) is the only path
that downloads from Yahoo; use it by hand for research, never in a scheduler.

## 2. Create a paper account at your intended capital

In the paper dashboard, open the account menu and create a new paper account
(Alpaca calls this opening a new paper account or resetting; the exact button
label has changed over time). Enter the amount you would really invest, for
example `1000`. Use that new account's keys in the next step.

## 3. Generate paper API keys

1. In the paper dashboard, find **API Keys** and click **Generate** (or
   *Regenerate*).
2. Copy the **Key ID** (starts with `PK`) and the **Secret Key**. The secret is
   shown only once.
3. Store both in a password manager. Do not paste them into this repository,
   an issue, a chat, or a file an AI assistant can open.

## 4. Install and set environment variables

```bash
cd stock-try
python3.11 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
pip install --no-deps -e .

# In the terminal session you will run from (not in a file in the repo):
export APCA_API_KEY_ID='PK...'          # paper key id
export APCA_API_SECRET_KEY='...'        # paper secret
# optional, see section 9:
export NTFY_TOPIC='a-long-random-topic-name'
export HEALTHCHECK_URL='https://hc-ping.com/<your-uuid>'
export APCA_DATA_FEED=iex               # optional; iex is the default (paper-only accounts get IEX only)
```

Install with `pip install -e .` (editable), as above: the kill-switch file and the default ledger live at the
repository root, and the runner refuses to guess them after a non-editable `pip install .` (set `KILL_SWITCH_FILE`
and pass `--ledger` if you ever install it that way).

On Windows PowerShell use `$env:APCA_API_KEY_ID = 'PK...'`.

## 5. Run the simulator first (no keys, no network)

```bash
python scripts/paper_rebalance.py --broker sim \
  --targets-json tests/fixtures/sample_targets.json --capital 100 --dry-run
```

You should see a plan like this (the fixture's prices are made up):

```
simulated clock: 2026-10-01 11:00 New York time
strategy=sample_three_asset broker=sim dry_run=True rebalance_id=sample_three_asset-2026-10-01 ... price_source=file
symbol  side      notional         est_qty  client_order_id
SPY     sell         $6.00        0.010504  sample_three_asset-2026-10-01-SPY-sell-a1
GLD     buy          $4.93        0.020311  sample_three_asset-2026-10-01-GLD-buy-a1
IEF     buy          $2.96        0.031053  sample_three_asset-2026-10-01-IEF-buy-a1
status=dry_run market gate open
estimated Alpaca regulatory fees: $0.03
```

How to read it: sells are always sent first; buys are sized from the cash that
is actually available (never from margin); every order has a deterministic
`client_order_id` of the form `<strategy>-<rebalance date>-<symbol>-<side>-a<attempt>`.
That id is what makes a repeated or late trigger harmless: the broker already
holds an order with that id, so it is never sent twice.

Then try a submission on the simulator, and a first deployment from cash:

```bash
python scripts/paper_rebalance.py --broker sim --targets-json tests/fixtures/sample_targets.json --capital 100 --no-dry-run
python scripts/paper_rebalance.py --broker sim --targets-json tests/fixtures/sample_targets_initial.json --capital 100 --no-dry-run
#   -> BLOCKED by guard: [max_daily_notional] ...   (moving 100% of the account in one day)
python scripts/paper_rebalance.py --broker sim --targets-json tests/fixtures/sample_targets_initial.json --capital 100 --no-dry-run --initial-deployment
```

A registry strategy on the simulator uses real daily data from the data layer (the research cache when no Alpaca
keys are set):

```bash
python scripts/paper_rebalance.py --broker sim --strategy spy_buy_hold --capital 1000 --dry-run
```

The simulator prints its simulated clock. It opens a month's rebalance only on the month's first session (see
section 8, "Later triggers in the same month"), so on other days the plan is printed with its legs skipped
(`first_session_passed`) or marked `market gate would skip: execution_window_closed`; add
`--rebalance-date 2026-10-01` to simulate a rebalance day. A targets file with prices simulates the session after
its prices and warns when that is more than five days before today.

## 6. Harden the paper account (once)

```bash
python scripts/paper_rebalance.py --broker alpaca --harden-account
```

This sets, then re-reads and checks: margin multiplier `1` (no margin), no
short selling, options level `0`, overnight trading disabled, a confirmation
e-mail for every trade, fractional trading on. Paper accounts normally start
with margin (and often options) enabled, and **every run refuses to start
until the account reads as hardened**. If `disable_overnight_trading` prints `unconfirmed`, Alpaca did
not echo that field back; the runner never sends overnight orders anyway
(market DAY orders only, inside regular hours only).

## 7. Paper dry run

```bash
python scripts/paper_rebalance.py --broker alpaca --strategy spy_buy_hold
```

(`--dry-run` is the default.) The runner:

1. checks the kill switches;
2. reads Alpaca's clock and calendar, refuses a stale clock, and works out the
   **due rebalance**: the first trading day of the current month. Missed months
   are never replayed; only the latest due rebalance is traded. Its legs are
   **opened only on that first trading day**; the next four sessions (the
   **execution window**, the first five sessions of the month) only finish legs
   that already have an order. Later in the month a run does nothing (a
   heartbeat) and the month waits for the next rebalance, so a signal decided
   weeks earlier is never traded late;
3. checks the account (margin 1, no shorting, options 0, not blocked, not
   suspended, empty crypto withdrawal whitelist where that endpoint still exists);
4. refuses to trade while any open order at the broker was not placed by this
   rebalance (for example one you placed by hand in the dashboard);
5. evaluates the strategy on the close of the trading day *before* the
   rebalance date (the backtest's decide-at-close, trade-next-day rule), on
   Alpaca's daily bars, and sizes orders with the latest prices;
6. prints the plan and every guard result.

Orders are only ever sent between **30 minutes after the open and 30 minutes
before the close** (10:00-15:30 New York time; 10:00-12:30 on early-close days).
A dry run outside those hours still prints the plan, marked
`market gate would skip`. A real run outside those hours does nothing and
exits 0. The window is re-checked with a fresh broker clock immediately before
**every** order, so waiting on slow fills can never push an order past
close-30min, and a run stops sending orders 8 minutes after it started; the
remaining legs are reported (exit 1, alert `submissions_stopped`) and left for
the next trigger. Market orders are never queued for the next open.

Exit codes: `0` fine (including "nothing to do", "market closed", "not a
rebalance month" and "execution window closed"), `1` rebalance incomplete (a
partial fill that could not be finished, or the market window or run deadline
reached mid-run; an alert was sent), `2` blocked by a guard, `3` kill switch or
live not authorized (including `--live` without `LIVE_TRADING=yes-live`), `4`
configuration, credential or data error (a missing or malformed targets file, a
non-finite `--capital`, a bad symbol), `5` unexpected error during a run
(already alerted and written to the ledger).

## 8. Paper for real

When several dry runs look right:

```bash
python scripts/paper_rebalance.py --broker alpaca --strategy spy_buy_hold --no-dry-run
```

### The size limits and when you will hit them

The default hard limits are deliberately tight, sized for a $1-$100 smoke test:

| Limit | Default | At $100 | At $1,000 | At $10,000 |
|---|---|---|---|---|
| Per order | min($50, 25% of equity) | $25 | $50 | $50 |
| Per day, buys + sells | 60% of equity | $60 | $600 | $6,000 |
| One-way turnover per rebalance | 1.0 | | | |
| Orders per run | 2 x number of symbols | | | |
| Weight per symbol | 0 to 100%, total at most 100% | | | |
| Price sanity | closes dated the last completed session; NaN, zero, negative refused; a move above 30% refused unless `--corporate-action SYMBOL` | | | |

So the first deployment of $1,000 into one ETF is blocked twice: the single
order exceeds $50, and moving 100% of the account in one day exceeds 60%.
That is intended. To deploy, you explicitly acknowledge both:

```bash
python scripts/paper_rebalance.py --broker alpaca --strategy spy_buy_hold --no-dry-run \
  --initial-deployment \
  --max-order-notional 1000 --max-order-frac 1.0 \
  --limits-ack "I accept larger automated orders than the safety defaults"
```

`--initial-deployment` is only accepted when the account is all cash. A trend
strategy that has moved to cash re-enters through the same flag, so a
re-entry month needs you to confirm it; the alert tells you when.

At very small sizes some strategies cannot be built at all: Alpaca's minimum
is $1 for **buy** orders, so a five-ETF strategy at 20% each needs at least $1
per sleeve (a little over $5 in total, plus a fee buffer). Below that the runner
refuses the **whole** rebalance rather than trade a distorted half-portfolio:
use a single-ETF strategy (`spy_buy_hold`) or more capital. Sells have no
minimum: an over-weight position is trimmed by any amount of at least one cent,
and a full exit sells the exact quantity held, however small. Top-up buys
smaller than $1 are left as drift, so below a few hundred dollars a multi-ETF
portfolio holds some cash and wanders from its targets between months, and
trimming costs a few cents of fees a month (the backtest's `scaling.md` shows
the effect).

A strategy that moves most of the portfolio to cash (a trend filter going
"out") is only allowed if the strategy declares it (`allows_exit_to_cash` on
the strategy's specification; in a targets file, a JSON `true`, never the
string `"true"`). The registry's trend and GTAA strategies are declared; the
buy-and-hold and 60/40 benchmarks are not, so a bug that tells them to sell
everything is refused. For a declared strategy, full-exit sells and buys of its
cash ETF are exempt from the size caps (they reduce risk); the cash ETF must be
a T-bill fund (BIL, SHV, SGOV, TBIL or BILS), so no other symbol can be bought
uncapped under that label.

### Partial fills

If an order fills only partly, the runner computes what is still missing from
fresh prices and sends **one** more order with a new id (`...-a2`). If that
also fails to fill, it stops, alerts, and leaves the residual until next month.
It never sends a third attempt for the same rebalance. An order Alpaca reports
as `stopped` (a trade is guaranteed but has not happened yet) or `suspended` is
treated as still open: the runner waits and never sends a second attempt while
it is outstanding.

### Later triggers in the same month

New legs of a rebalance (attempt `-a1`) are opened **only on its scheduled
session**, the first trading day of the month, just as the backtest trades
only at that month's first open. A later trigger the same day can finish it
(for example after a crash between the sells and the buys). From the second
session on, a trigger only finishes legs that already have an order (waits, or
one `-a2` residual); it never opens a new leg because prices drifted, **even if
the first session placed no order at all** (everything was within $1 of
target, status `nothing_to_do`). This rule uses only the broker's calendar and
its order list, so it holds on a GitHub runner that starts with an empty ledger
every time. Where the ledger is kept (a local machine), a run recorded as
`completed`, `already_done` or `nothing_to_do` also closes new legs for the rest
of that day. If a run could not finish the buys on the first day, the rest of
the month is held in cash with an alert, and the next rebalance restores the
targets. A later session with no order prints the plan with its legs skipped
(`first_session_passed`), exits 0 and pings the dead-man check.

**If the first session was missed** (the scheduler or GitHub was down, the data
source failed, or a guard blocked the run and you fixed the cause), nothing
trades automatically that month. After checking the ledger or the log that no
run evaluated that day, you can start the rebalance by hand on a later session
of the execution window (sessions 2 to 5):

```bash
python scripts/paper_rebalance.py --broker alpaca --strategy spy_buy_hold --no-dry-run --late-start
```

`--late-start` opens legs only while no order of the rebalance exists at the
broker and the local ledger shows no evaluated run for it; it is recorded in
the ledger (`late_start`), refused when `CI` or `GITHUB_ACTIONS` is `true`, and
must never be put in a scheduler (it would bring back mid-month trading on
drifted prices). The ledger check fails closed: if the local ledger cannot be
read (typically a line cut short by a crash), a `--late-start` run sends
nothing, alerts `late_start_ledger_unreadable`, prints `status=blocked` and
exits 2 (a dry run is refused the same way). Repair the ledger (section 9),
confirm again that no run evaluated the scheduled session, and rerun. Runs
without `--late-start` are not affected: they fall back to the broker rule
above, which never opens new legs after the first session. A re-entry blocked
on the first day by the size limits (section 8) is confirmed the same way:
`--initial-deployment` plus `--late-start` if it is no longer the first
session.

## 9. Read the ledger

Every run appends JSON lines to `data/ledger/<strategy>.jsonl` (the `data/`
folder is git-ignored). It records the inputs hash, targets, prices, the plan,
a write-ahead `submit_intent` before each order, each order, fills, modelled
fees, modelled dividends and a reconciliation against Alpaca's activity feed.

```bash
python scripts/paper_rebalance.py --strategy spy_buy_hold --show-ledger 20
# or, with jq:
jq -c 'select(.event=="run_end") | {ts, rebalance_id, status, fees: .modelled_fees_by_day, divs: .modelled_dividends.total}' \
  data/ledger/spy_buy_hold.jsonl
```

Because Alpaca paper charges no regulatory fees and pays no dividends, the
modelled values are the P&L of record for paper trading. Fees are per New York
day (the last record for a day wins); dividends are per rebalance id (the last
record for an id wins). The broker, not the ledger, decides idempotency: a
crash between sending an order and writing the ledger loses nothing, because
the next run finds the order by its id.

**A line cut short by a crash.** Every write starts on a new line (a newline is
added first if the file does not end with one), so a crash mid-write damages
only its own line. That line still makes the file unreadable as a whole:
unattended runs carry on under the broker rule, but `--late-start` and
`--show-ledger` need it repaired. Keep a copy, find the bad line and delete
only that line (never edit any other):

```bash
cp data/ledger/spy_buy_hold.jsonl data/ledger/spy_buy_hold.jsonl.bak
python - data/ledger/spy_buy_hold.jsonl <<'EOF'
import json, sys
for i, line in enumerate(open(sys.argv[1], encoding="utf-8"), 1):
    try:
        if line.strip():
            json.loads(line)
    except ValueError:
        print(f"line {i} is not valid JSON: {line[:80]!r}")
EOF
sed -i '<N>d' data/ledger/spy_buy_hold.jsonl   # <N>: the line number printed above
```

## 10. Scheduling: use an external trigger, not GitHub's cron

**Evidence.** GitHub Actions `schedule:` is best effort: in 2026 there were
documented delays of 1 to 9 hours and dropped runs. A rebalance that must
happen inside a 5.5-hour window cannot rely on it. The workflow
`.github/workflows/paper-rebalance.yml` therefore has **no cron**; it only
runs on `workflow_dispatch`.

**Recommended.** A free external scheduler calls GitHub's dispatch API:

* **cron-job.org** (free): create a job with URL
  `https://api.github.com/repos/<you>/<repo>/actions/workflows/paper-rebalance.yml/dispatches`,
  method `POST`, body `{"ref":"<branch>"}`, headers
  `Authorization: Bearer <PAT>`, `Accept: application/vnd.github+json`.
* **Cloudflare Workers cron trigger** (free tier): a Worker whose `scheduled()`
  handler makes the same `fetch` call; keep the PAT in a Worker secret.

The **PAT** must be a *fine-grained* personal access token restricted to this
one repository with only **Actions: Read and write**. Nothing else. Give it an
expiry date.

**When to fire.** Weekdays at **15:35 UTC and again at 18:05 UTC**. Both
times fall inside the safe window in summer and winter time (the window is
14:00-19:30 UTC in summer, 15:00-20:30 UTC in winter). Firing every weekday is
fine: the runner works out itself whether a rebalance is due (legs are opened
only on the first session of a month), a second trigger finds the orders
already placed and only finishes legs that are already started, and every
other run is a heartbeat that does nothing but ping the dead-man check. Both
daily triggers matter on the first session of a month: if neither runs, that
month is not traded unless you start it by hand with `--late-start`
(section 8).

```bash
# the same call by hand (useful to test the PAT):
curl -X POST -H "Accept: application/vnd.github+json" -H "Authorization: Bearer $PAT" \
  https://api.github.com/repos/<you>/<repo>/actions/workflows/paper-rebalance.yml/dispatches \
  -d '{"ref":"main"}'
```

**GitHub setup** (the repository must be **private**):

* Settings -> Secrets and variables -> Actions -> *Secrets*:
  `APCA_PAPER_API_KEY_ID`, `APCA_PAPER_API_SECRET_KEY`, optional `NTFY_TOPIC`,
  `HEALTHCHECK_URL`. Paper keys only.
* *Variables*: `PAPER_STRATEGY` (e.g. `spy_buy_hold`), `KILL_SWITCH` = `off`.
* Optional *variable* `APCA_DATA_FEED` (default `iex`). The workflow passes
  `--price-source alpaca`: prices come from Alpaca, never from Yahoo.
* The workflow runs `--dry-run`. To submit paper orders, edit the one command
  in the workflow from `--dry-run` to `--no-dry-run` and push.
* Dependencies are installed only from the hash-locked `requirements.lock`
  (every package, transitive ones included); the job fails rather than install
  anything unpinned next to the paper keys.
* The job timeout is 20 minutes; the runner itself stops sending orders after
  8 minutes and cancels what is still open, so GitHub never kills it between a
  submit and its cancel.
* Each run uploads the ledger as a private artifact kept for 90 days.

**A local machine** works too: `cron` (Linux/macOS) or Task Scheduler
(Windows) running the same command, if the machine is reliably on.

**Dead-man alert.** Create a free check at <https://healthchecks.io> using a
**cron schedule**, not a simple period: schedule `35 15 * * 1-5`, time zone
UTC, grace time 4 hours. Put its ping URL in `HEALTHCHECK_URL`. (A 1-day period
would report "down" every weekend, because nothing runs on Saturday and Sunday,
and false alarms teach you to ignore the real one.) The runner pings after
every run that ends without error at a valid time: a completed or unchanged
rebalance, a month the strategy does not rebalance, a day outside the
execution window, and a weekday market holiday. It does **not** ping when it
ran on a trading day outside the market-hours window, so a scheduler set to the
wrong time trips the alert. If the scheduler, GitHub, or the runner silently
stops, healthchecks.io e-mails you.

## 11. Alerts

The runner always logs alerts. If `NTFY_TOPIC` is set, it also sends a short
push message via <https://ntfy.sh> (install the ntfy app and subscribe to your
topic). Anyone who knows a topic name can read it, so pick a long random name
and treat it like a password. Messages contain only a code, the strategy and
the rebalance date, never positions, amounts, keys or account numbers; the
details are in the log. Logs themselves are scrubbed of API keys, secrets and
account numbers.

## 12. The three kill switches

Use whichever is fastest. Each one stops new orders on its own.

**1. Local (file or environment variable).** Any value other than exactly `off`
aborts the next run and every order not yet sent in a running one.

```bash
echo on > KILL_SWITCH          # at the repository root; stop
echo off > KILL_SWITCH         # or: rm KILL_SWITCH; resume
export KILL_SWITCH=on          # for runs from this shell
```

On GitHub: set the repository variable `KILL_SWITCH` to `on` (works from the
phone app / web), or commit a file named `KILL_SWITCH` containing `on`.

**2. Broker-side (Alpaca refuses new orders even if the code is broken).**

```bash
python scripts/paper_rebalance.py --broker alpaca --engage-kill-switch
python scripts/paper_rebalance.py --broker alpaca --release-kill-switch release-broker-kill-switch
```

This sets Alpaca's account configuration `suspend_trade=true`. Dashboard
fallback if you cannot run code: open the account's configuration settings in
the Alpaca dashboard and switch on the option that suspends trading; if you
cannot find it, **regenerate the API keys** on the API Keys page (the old key
stops working immediately) and cancel any open orders from the Orders page.

**3. Mode.** Dry run is the default; live needs `LIVE_TRADING=yes-live`,
`--live` and `--i-understand-live` together. `--live` without
`LIVE_TRADING=yes-live` is refused outright (exit 3), including for
`--harden-account` and `--engage-kill-switch`: it never falls back to the paper
account, so an admin action can never silently act on the wrong one. Admin
actions print which account (`alpaca-paper` or `alpaca-live`) they act on.

## 13. Gates before anything real

**Gate B, paper is working** only if, over at least 20 trading days including
one rebalance, one market holiday and one early close: every signal is
reproduced by the backtest engine on the same data, no run was missed or
duplicated (check the ledger and the order list), and the paper-versus-backtest
price-return tracking difference averages under 10 bp a day (dividends
excluded).

**Gate C, a $1-$100 live smoke test** needs Gate B, a hardened live account
(below), and funding that costs at most a few dollars. It is judged on
plumbing only: fills, fees posted, reconciliation, alerts.

## 14. Harden a live account before any live key exists

1. Open the live account and complete its onboarding (non-US residents: W-8BEN).
2. **Before generating any live API key**, set in the dashboard: margin off
   (multiplier 1), short selling off, options off, trade confirmation e-mails on.
3. Generate the live key only on your own computer, keep it in a password
   manager, and export it only in a terminal you control. Then verify:

   ```bash
   LIVE_TRADING=yes-live APCA_API_KEY_ID=AK... APCA_API_SECRET_KEY=... \
     python scripts/paper_rebalance.py --broker alpaca --live --harden-account
   ```

4. Never put the live key in GitHub, in `.env` inside the repo, or anywhere an
   AI coding agent works.

## 15. What a $1-$100 live test can and cannot show

| It can show | It cannot show |
|---|---|
| Authentication, order submission and fills work with real money | Any profit: at 10% a year $1 earns $0.10, while one $1 round trip costs about **$0.04** (each fee type rounds up to $0.01 per day) |
| Regulatory fees posting as Alpaca activities, and reconciliation against the ledger | Dividends: fractional dividends round to the nearest cent, so a $1 SPY position receives **$0.00** |
| Alerts, kill switches and account permissions behave | Slippage or market impact at realistic size |
| | Anything statistical: the sample is far too short |

For a non-US resident, funding is the real cost: about $35 for an outbound
international wire from Alpaca, 1.5% (max $40) for local-currency transfers,
plus $15-50 from your own bank per wire. A $1-$100 live test is then
effectively unrecoverable; paper trading covers the same plumbing for free.

## 16. Never do this

* Never store live keys where an LLM agent can read them (repo files, `.env`
  in the repo, chat, agent environment variables).
* Never enable margin, short selling or options on this account.
* Never run a public repository with keys in its secrets, and never make this
  repository public.
* Never schedule live trading from GitHub Actions cron alone.
* Never raise a limit without reading why it exists; the acknowledgement string
  is there to make you stop and think.
* Never "fix" a guard violation by deleting the guard. Find out why it fired.

## 17. Troubleshooting guard codes

| Code | Meaning | What to do |
|---|---|---|
| `margin_enabled`, `shorting_enabled`, `options_enabled`, `options_level_unknown` | Account not hardened | Run `--harden-account` (section 6) |
| `broker_suspend_trade`, `kill_switch_env`, `kill_switch_file` | A kill switch is on | Release it deliberately (section 12) |
| `stale_clock` | Broker clock and your clock differ by more than 5 minutes | Fix the machine's clock / retry |
| `price_stale`, `price_undated`, `price_invalid`, `price_prev_missing` | Data not from the last completed session, or bad | Refresh data (`--refresh-data`), check the data source |
| `price_jump`, `live_price_jump` | A move above 30% | If it is a real split or distribution, rerun with `--corporate-action SYMBOL` |
| `max_order_notional`, `max_daily_notional`, `max_turnover` | Size limits | See section 8; use `--initial-deployment` from all cash, or an acknowledged override |
| `min_notional_impossible_leg` | A position would be under $1 | More capital or a single-ETF strategy |
| `sell_everything_not_declared` | Target exposure dropped by more than half without the strategy declaring exits | Investigate: probably a data or strategy bug |
| `units_mismatch`, `qty_on_notional_leg` | The order about to be sent does not match the plan's dollars | A code bug: do not override; report it |
| `rebalance_id_not_due` | Someone asked for an old (or future) rebalance | Nothing: only the latest due rebalance is ever traded |
| `position_outside_universe`, `foreign_orders` | The account holds or traded symbols this strategy does not own | Use a dedicated account per strategy |
| `foreign_open_orders` | An open order at the broker was not placed by this rebalance (e.g. a manual dashboard order) | Cancel it or wait for it to finish, then rerun; use a dedicated account |
| `cash_symbol_not_cash_like` | A strategy names something other than a T-bill ETF (BIL, SHV, SGOV, TBIL, BILS) as its cash | Fix the strategy or targets file |
| `kill_switch_path_unknown` | Not a source checkout, so the repository-root `KILL_SWITCH` file cannot be located | Install with `pip install -e .`, or set `KILL_SWITCH_FILE` |
| `submissions_stopped` (alert, exit 1) | The market window closed or the 8-minute run deadline passed while the run was waiting on fills | Nothing to undo: no order was sent late. The next trigger (same day) finishes the started legs |
| `execution_window_closed` (skip, exit 0) | The month's rebalance is past its first five sessions | Nothing: the next month's rebalance restores the targets |
| `first_session_passed` (skip, exit 0) | A session after the month's first: new legs are not opened on drifted prices | Nothing, normally. If the first session was missed, see section 8, `--late-start` |
| `late_start_ledger_unreadable` (blocked, exit 2) | `--late-start` could not read the local ledger to confirm no run evaluated the scheduled session; nothing was sent | Repair the ledger (section 9), check again that no run evaluated the scheduled session, rerun |
| `rebalance_already_evaluated`, `rebalance_already_executed` (skipped legs) | A run already evaluated or started this rebalance; drift is not traded until next month | Nothing |

## 18. Alpaca behaviours that are ambiguous, and how the code handles them

* **client_order_id uniqueness scope.** Alpaca rejects a reused id with
  `client_order_id must be unique`, but does not document for how long or
  across which order states. The runner never relies on it alone: before every
  order it looks the id up directly *and* scans all orders since the rebalance
  date, and it treats a uniqueness error as "someone already placed this".
* **Notional limit orders.** Fractional orders can be limit orders, but whether
  a *notional* (dollar) limit order is accepted is not clearly documented. The
  runner uses only market DAY orders for notional legs.
* **Full exits.** A notional sell of the whole position is rejected if the price
  ticks down before the fill and otherwise leaves dust. Full exits (target 0)
  therefore sell the exact held quantity (`qty`, up to 9 decimals), of any size;
  every other leg is dollars-only.
* **Minimum order size.** Alpaca documents "a minimum 1 USD notional amount for
  Buy entry orders". The runner, the simulator and the backtest therefore apply
  the $1 minimum to buys only and send notional sells down to one cent. If
  Alpaca ever rejects a sub-$1 notional sell, the leg fails with an alert and the
  runner does not retry it in that run.
* **`stopped` orders.** Alpaca uses `stopped` for an order whose trade is
  guaranteed but has not yet happened. The runner treats it as open (never as
  final), so it never sends a residual order next to it.
* **`done_for_day` / partial fills.** For DAY orders the unfilled remainder
  never fills, so the runner treats `done_for_day` as final and re-sizes the
  residual once (`-a2`).
* **FINRA TAF pause (Oct-Dec 2026).** Whether Alpaca passes it through is
  unverified, so the modelled fees keep charging it (overstating cost slightly).
* **Account configuration field `disable_overnight_trading`.** Not in
  alpaca-py 0.44.0's model; the runner sends it raw and reports it as
  unconfirmed if Alpaca does not echo it.
* **Crypto wallet whitelist endpoint.** Scheduled for sunset on 2026-10-09; the
  check is best effort and logs when the endpoint is gone.
* **Margin multiplier after hardening.** The configuration change may take time
  to show in the account's `multiplier`; the preflight checks both and refuses
  until both read `1`.
* **Fee activity types.** Regulatory fees are read from activity types `FEE`
  and `PTC`; if Alpaca posts them under another type, the reconciliation shows
  zero broker fees and the modelled fees remain the record.
