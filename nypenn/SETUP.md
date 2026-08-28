# Setup

Follow this top to bottom. Only the first section is urgent.

---

## Today — about 15 minutes

Predictions are learned from data this thing collects itself, starting the day you
turn it on. Nothing else here matters until the collector is running, so do this
part and stop.

### 1. Install what's needed

On the Pi:

```bash
sudo apt install -y nodejs npm sqlite3 git
```

### 2. Get the code

```bash
git clone https://github.com/OrganizedMan/hello-world /home/pi/nypenn-repo
ln -s /home/pi/nypenn-repo/nypenn /home/pi/nypenn
cd /home/pi/nypenn
```

### 3. Fill in your settings

```bash
cp .env.example .env
nano .env
```

Two blanks are marked **FILL ME IN**:

- `NJT_USERNAME` and `NJT_PASSWORD` — from developer.njtransit.com

Everything below them already has working defaults. Save and exit (`Ctrl+O`,
`Enter`, `Ctrl+X`).

### 4. Install

```bash
./deploy/install.sh
```

This builds everything, installs both services, and starts them. It takes a few
minutes on a Pi.

### 5. Check it's working

```bash
curl -s localhost:3005/api/health
```

You want `"ok":true`. If you see that, you're done for today — data is accumulating.

`"ok":false` means the server is up but the collector is not feeding it — check
`journalctl -u nypenn-collector -n 30`. A refused connection means the server
itself is down; see "If something's wrong" below.

Open `http://localhost:3005` on the Pi, or from another machine on your network at
`http://<pi-address>:3005`. There is no login — the board loads straight away, so
keep it on your own network or on Tailscale rather than exposing port 3005 to the
internet.

> **You won't see predictions yet.** That's correct. Tracks show as `—` until NJ
> Transit posts them. Predictions start appearing once there's history to learn from.

---

## This week

### Reach it from your phones

Tailscale is the easiest way — no ports to open, works on cellular at Penn Station,
no certificates.

On the Pi:

```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
```

Install the Tailscale app on both phones and sign in with the same account. The board
is then at `http://<pi-name>:3005` from anywhere.

### Pin your usual trains

Tap a train, then **Pin to the top**. Pins are per-device, so you and your wife each
get your own. Add the board to your home screen while you're there.

---

## In two weeks

Predictions should be appearing. Check whether they can be trusted:

```bash
curl -s localhost:3005/api/accuracy
```

Look at `byConfidence`. Green (`high`) predictions should be right far more often than
red (`low`) ones. If they aren't, the colours are lying and the thresholds need
adjusting — say so and they can be retuned.

Quality keeps improving until roughly week eight, as weekends and holidays build up
enough history of their own.

---

## If something's wrong

**A service won't stay running**

```bash
systemctl status nypenn-collector
journalctl -u nypenn-collector -n 50 --no-pager
```

`--no-pager` matters: without it the lines are cut off at the terminal width,
and the HTTP status code in a feed error is usually the part that gets cut.

If systemd logs `Unknown key name 'StartLimitIntervalSec' in section 'Service'`,
the installed unit predates the fix that moved that line to `[Unit]`. It is
ignored where it was, so the unit gives up permanently after a fast crash loop
instead of retrying forever. Re-run `./deploy/install.sh`, then:

```bash
sudo systemctl reset-failed nypenn-server nypenn-collector
sudo systemctl restart nypenn-server nypenn-collector
```

`reset-failed` is the part that is easy to miss — a unit that already hit the
old rate limit stays failed until it is cleared, no matter how good the fix is.

**`health` says `"ok":false`**

The collector hasn't polled in over three minutes. Usually credentials or the feed:

```bash
journalctl -u nypenn-collector -n 20
```

- `getToken returned HTTP 401/403` — check `NJT_USERNAME` / `NJT_PASSWORD` in `.env`
- `could not locate a departure array` — NJT's endpoint names differ from what was
  assumed. See README, "Confirming the feed contract". Only one file needs changing.

**Port 3005 refuses the connection**

Nothing is listening. The server exits at startup if it cannot open the
database, and systemd restarts it every five seconds, so the port stays shut.
The database is created by the **collector**, not the server, which is why the
reason is in the collector's journal:

```bash
systemctl status nypenn-collector
journalctl -u nypenn-collector -n 30
```

`Missing required environment variable NJT_USERNAME` means `.env` was not filled
in, or systemd is not reading it — the collector checks credentials before it
creates the database, so a bad `.env` leaves both services down.

Newer builds no longer do this: the server binds the port regardless and the
board loads showing itself as unhealthy, which is a state you can diagnose. If
the port is refusing outright, you are on an older checkout:

```bash
cd /home/pi/nypenn-repo && git pull && cd /home/pi/nypenn && ./deploy/install.sh
```

**The page is blank, but `curl` works**

An empty page with nothing in `journalctl` means the browser fetched the HTML and
then refused to fetch the JavaScript inside it. Open the browser's developer
console — a failed request for `/assets/index-*.js` is the confirmation.

This was caused by a security header that told the browser to upgrade the page's
own script to `https://`, which nothing on the Pi answers. It is fixed; if you are
seeing it, you are running an older checkout:

```bash
cd /home/pi/nypenn-repo && git pull && cd /home/pi/nypenn && ./deploy/install.sh
```

Note that the symptom hides itself on the Pi: `http://localhost:3005` is exempt
from that upgrade, so the board looks fine there and blank on every phone.

**No predictions after several weeks**

Check history is actually accumulating:

```bash
sqlite3 data/nypenn.db "SELECT COUNT(*), COUNT(final_track) FROM departures;"
```

The second number is the one that matters — those are the runs with a known track. If
it's zero while the first is large, trains are being seen but tracks never recorded,
which points at the feed's track field rather than the predictor.

**Start over**

Deleting `data/nypenn.db` throws away all collected history and cannot be undone.
Restore from `backups/` instead if you can.

---

## What's running

| | |
|---|---|
| `nypenn-collector` | Polls NJT every 20s, records history. The important one. |
| `nypenn-server` | Serves the board and predictions on port 3005. |
| `nypenn-backup.timer` | Nightly at 04:15, keeps 7 days in `backups/`. |

Full reference, including how prediction works and every config option, is in
[README.md](README.md).
