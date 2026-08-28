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

Four blanks are marked **FILL ME IN**. Three you can do right now:

- `NJT_USERNAME` and `NJT_PASSWORD` — from developer.njtransit.com
- `JWT_SECRET` — run `openssl rand -hex 32` and paste the result

Leave `NYPENN_USERS` empty for now. Save and exit (`Ctrl+O`, `Enter`, `Ctrl+X`).

### 4. Install

```bash
./deploy/install.sh
```

This builds everything, installs both services, and starts them. It takes a few
minutes on a Pi.

It will finish, then the **server** will be in a restart loop because `NYPENN_USERS`
is still empty. That's expected — the collector is already running and gathering
data, which is the part that matters.

### 5. Create your logins

```bash
node server/dist/adduser.js alice 'a good password'
node server/dist/adduser.js bob 'another good password'
```

Each prints a line like `alice:a1b2c3...:d4e5f6...`. Put both into `.env`, separated
by a comma:

```
NYPENN_USERS=alice:a1b2...:d4e5...,bob:f7g8...:h9i0...
```

Then restart the server:

```bash
sudo systemctl restart nypenn-server
```

### 6. Check it's working

```bash
curl -s localhost:3005/api/health
```

You want `"ok":true`. If you see that, you're done for today — data is accumulating.

Open `http://localhost:3005` on the Pi, or from another machine on your network at
`http://<pi-address>:3005`, and log in.

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
TOKEN=$(curl -s -X POST localhost:3005/api/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"alice","password":"your password"}' | grep -o '"token":"[^"]*' | cut -d'"' -f4)

curl -s localhost:3005/api/accuracy -H "Authorization: Bearer $TOKEN"
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
journalctl -u nypenn-collector -n 50
```

**`health` says `"ok":false`**

The collector hasn't polled in over three minutes. Usually credentials or the feed:

```bash
journalctl -u nypenn-collector -n 20
```

- `getToken returned HTTP 401/403` — check `NJT_USERNAME` / `NJT_PASSWORD` in `.env`
- `could not locate a departure array` — NJT's endpoint names differ from what was
  assumed. See README, "Confirming the feed contract". Only one file needs changing.

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
