# nypenn — a self-hosted NY Penn departure board

A private departure board for New York Penn Station that predicts NJ Transit
track assignments before they are posted, built to run on a Raspberry Pi for
two people.

NJ Transit posts tracks at NY Penn roughly five minutes before departure. The
schedule, status and posted track all come straight from NJT's public feed;
the prediction is derived from history this collector gathers itself.

Not affiliated with NJ Transit. Their feed is offered as a public service and
not for commercial use — keep this private and don't charge for it.

> **Setting this up? Read [SETUP.md](SETUP.md) instead.** It is a short list of
> commands in order. This file is the reference: how things work, and every
> configuration option.

## The one thing that matters

**Start the collector before anything else, today.**

There is no public archive of historical NJ Transit track assignments. The
predictor can only learn from data you collect, from the moment you start
collecting. Every day you wait is a day of training data you cannot get back.

Rough quality curve:

| Elapsed | What you get |
|---|---|
| Day 1 | Live board, posted tracks, seeded line priors only |
| ~2 weeks | Usable predictions on weekday regulars |
| ~6–8 weeks | Good predictions, including weekends and holidays |

The UI is honest about this: a prediction with thin evidence is shown in red
and labelled a guess, never in green.

## Layout

```
collector/   polls NJT, writes history          (must run 24/7)
server/      prediction + API, reads history    (opens the DB read-only)
client/      React board, mobile-first
shared/      types, service-date logic, DB setup
deploy/      systemd units, backup, install
```

## Running it locally

For a Pi deployment use [SETUP.md](SETUP.md). To run it on a development machine:

```bash
cd nypenn
cp .env.example .env         # two blanks marked FILL ME IN
npm install
npm run build

npm run collector            # terminal 1 — start this first
npm run server               # terminal 2
```

Then open `http://localhost:3005`.

### Seeing the UI before you have data

```bash
npx tsc -p collector/tsconfig.test.json
cp collector/src/schema.sql collector/dist-test/src/schema.sql
node collector/dist-test/scripts/seed-demo.js data/demo.db
NYPENN_DB=data/demo.db npm run server
```

The demo database contains six weeks of invented history covering every state
the board can render: a posted track, confident predictions, a deliberately
erratic line, and a train with no history at all. It refuses to overwrite
`nypenn.db`.

## The NJT feed contract

Taken from *NJ TRANSIT RailData API V2*, and matched by tests in
`collector/test/parsing.test.ts` rather than assumed.

Every call is `POST` with **`multipart/form-data`**. Sending
`application/x-www-form-urlencoded` instead makes the API see no parameters at
all, and `getToken` then answers HTTP 500 `{"errorMessage":"Missing user
account."}` -- which reads exactly like a credentials problem and is not one.

The token travels as a **form field named `token`**, not an `Authorization`
header.

| Call | Purpose | Daily cap |
|---|---|---|
| `getToken` | credentials to token | **10** |
| `getTrainSchedule` | the live board for one station, with `TRACK` and `STATUS` | 40,000 (shared) |
| `getStationSchedule` | the flat 27-hour timetable | **200** |

The collector polls `getTrainSchedule` -- the DepartureVision feed, the next 19
departures with their tracks. `getStationSchedule` is the wrong endpoint for
this: it is the timetable rather than the live board, and its 200/day cap would
be spent before 08:00 at a 20s poll while still never reporting a track.

**The 10/day cap on `getToken` is the sharp edge.** Exceeding it locks the
account out until midnight and costs the rest of the day's history. So the
token is cached in `data/njt-token.json` and reused across restarts, attempts
are counted rather than successes -- a failed `getToken` has still been spent --
and the collector stops at `NJT_MAX_TOKENS_PER_DAY` (default 4) regardless of
what the API would still allow.

The API reports its own failures with **HTTP 200**, so the status is not the
signal:

- `{"errorMessage":"Invalid token."}` -- re-authenticate once, which is the only
  thing that triggers a new `getToken`
- `{"errorMessage":"Daily usage limit:10. ..."}` -- locked out; wait
- a bare `Null` -- the call arrived with no usable parameters

To check the account and the request shape without spending the day's quota:

```bash
./scripts/probe-njt.sh
```

NJT issues **separate Test and Production credentials**, and recommends
developing against Test:

```
Test:       https://testraildata.njtransit.com/api/TrainData
Production: https://raildata.njtransit.com/api/TrainData
```

Set `NJT_BASE_URL` to match the credentials you are using. Crossing them over
is another way to get an account-not-found answer.

## Deploying to the Pi

```bash
sudo apt install -y nodejs npm sqlite3
git clone <your repo> /home/pi/nypenn-repo
ln -s /home/pi/nypenn-repo/nypenn /home/pi/nypenn
cd /home/pi/nypenn
cp .env.example .env && $EDITOR .env
./deploy/install.sh
```

That installs and starts both services, enables the nightly backup timer, and
caps journald so logs cannot outgrow the card.

### Remote access

Tailscale is the right answer: no open inbound ports, works on cellular at
Penn Station, no certificates to manage.

```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
```

Then reach the board at `http://<pi-name>:3005` from any device on your
tailnet. The board has no login of its own, so the tailnet is the access
control — do not forward port 3005 from a router instead.

The server is deliberately served over plain HTTP: there is no certificate for
`http://<pi-name>:3005` and no way to get one. That rules out any security
header that assumes TLS. In particular `upgrade-insecure-requests`, which
helmet sets by default, makes the browser rewrite the board's own JavaScript
URL to `https://` and the page renders blank on every device except the Pi
itself — `localhost` is exempt from the upgrade, so it looks fine there. See
the comment in `server/src/app.ts`, which `server/test/headers.test.ts`
enforces.

### The SD card is fine

A simulated service day writes **1,283 rows in 364 KiB** — under 0.4 MB/day,
well under 0.2 GB/year. Reproduce it yourself:

```bash
npm run simulate -w @nypenn/collector
```

This is not an accident of scale, it is the design. The collector writes a
*transition log*, not a snapshot log: a poll where nothing changed writes
nothing at all, which is most polls. Snapshot logging would have written
~95,000 rows a day, 74x more.

The real risk to an SD card here is power-loss corruption, not wear, which is
what the nightly verified backup is for. If the card dies you lose a day, not
the history.

## Operating it

```bash
systemctl status nypenn-collector
journalctl -u nypenn-collector -f
curl -s localhost:3005/api/health
```

`/api/health` is the one an uptime monitor should watch. `ok` goes false when
the last poll is more than three minutes old — that is the alert worth having,
because a silently dead collector costs history.

It also goes false when the collector has never created the database. The
server binds the port and reports that rather than exiting, so a misconfigured
collector shows up as an unhealthy board you can read, instead of a refused
connection whose cause is only in the *collector's* journal.

Once you have a few weeks of data:

```bash
curl -s localhost:3005/api/accuracy
```

Read `byConfidence` first. High-confidence predictions should be right far
more often than low-confidence ones; if they are not, the bands are lying to
you and the thresholds in `server/src/predictor.ts` need revisiting.

## How the prediction works

A recency-weighted modal track over that train's past runs on the same day
type (weekday / Saturday / Sunday-and-holiday), with a 21-day half-life so a
schedule change washes out in about a month. Confidence is the modal share,
shrunk toward zero on thin evidence so a single past run can never show green.

When a train has no history it falls back to its line's history (capped below
high confidence), then to a hand-seeded prior in `LINE_PRIORS`, then declines
to guess.

Deliberately not machine learning. Track assignment is overwhelmingly a
function of train number and day type, so this captures most of the available
signal while being able to show its work — which is what makes the confidence
colour trustworthy, and gives any future model a baseline to beat.

## Configuration

| Variable | Default | Notes |
|---|---|---|
| `NJT_USERNAME` / `NJT_PASSWORD` | — | Required. From the NJT developer portal. |
| `NJT_BASE_URL` | `https://raildata.njtransit.com/api/TrainData` | Confirm against your portal docs. |
| `NJT_STATION` | `NY` | New York Penn Station. |
| `NYPENN_DB` | `data/nypenn.db` | Shared by collector (write) and server (read). |
| `POLL_INTERVAL_MS` | `20000` | Polite, and fine for a personal feed. |
| `OBSERVATION_RETENTION_DAYS` | `14` | Rolling window; `departures` is never purged. |
| `LINE_PRIORS` | `{}` | Cold-start fallbacks, e.g. `{"Morris & Essex Line":"4"}`. |
| `BACKUP_REMOTE` | — | Optional rsync target for off-Pi copies. |

## Tests

```bash
npm test
```

Tests across the collector, the parser, the predictor and the served
responses. The ones worth knowing about:

- an unchanging board writes nothing beyond the first sighting
- the first track posting time survives later updates and a restart
- a prediction never reads the day it is predicting, or later
- weekday history never leaks into a weekend prediction
- a single past run never reaches high confidence
- the served page never asks the browser to upgrade its own bundle to `https`
- the server still listens, and says why, when the collector has made no database
