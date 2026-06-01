# 🎮 Binds PS5 Tracker

> Built by **Binds** — Auto-updating PS5 game release tracker with delays, pre-orders, betas & live alerts.

---

## ✅ Features
- 35+ PS5 games tracked with accurate data
- Alphabet filter (A–Z), genre chips, status filters
- 🔔 Track any game — get notified of delays, pre-orders, betas, date changes
- **Auto-updates itself every day at 8am UTC** via GitHub Actions
- Hosted free on GitHub Pages — no server needed

---

## 🚀 Setup (5 minutes)

### Step 1 — Create the repo
1. Go to [github.com/new](https://github.com/new)
2. Name it exactly: `ps5-tracker`
3. Set to **Public**
4. Click **Create repository**

### Step 2 — Upload the files
Upload these files keeping the exact folder structure:
```
ps5-tracker/
├── .github/
│   └── workflows/
│       └── update-games.yml
├── public/
│   ├── index.html
│   └── games.json
├── scripts/
│   └── update_games.py
└── README.md
```

**How to upload:**
- Click `Add file` → `Upload files` in your repo
- Or use GitHub Desktop / Git CLI

### Step 3 — Enable GitHub Pages
1. Go to your repo → **Settings** → **Pages**
2. Under **Source** → select **Deploy from a branch**
3. Branch: `main` · Folder: `/public`
4. Click **Save**
5. Wait ~2 minutes — your site will be live at:
   `https://obinds.github.io/ps5-tracker`

### Step 4 — Enable GitHub Actions
1. Go to your repo → **Actions** tab
2. If prompted, click **"I understand my workflows, enable them"**
3. The action will now run **every day at 8am UTC automatically**
4. You can also trigger it manually: Actions → `Auto-Update PS5 Game Data` → `Run workflow`

### Step 5 — Update the DATA_URL in index.html
In `public/index.html`, line ~230, you'll see:
```javascript
const DATA_URL = "https://raw.githubusercontent.com/oBinds/ps5-tracker/main/public/games.json";
```
This is already set to your GitHub username `oBinds` — no change needed!

---

## 🔄 How Auto-Update Works

Every day at 8am UTC, GitHub Actions:
1. Runs `scripts/update_games.py`
2. Checks RSS feeds from PlayStation Blog, Gematsu, Push Square, Eurogamer
3. Scans for delay news, pre-order announcements, beta dates
4. If anything changed → automatically commits updated `games.json`
5. Your live site updates within minutes

---

## ➕ Adding a New Game

Edit `public/games.json` and add a new object to the `games` array:

```json
{
  "id": "your-game-id",
  "title": "Game Title",
  "genre": "horror",
  "releaseDate": "2026",
  "releaseStatus": "on-track",
  "delayInfo": null,
  "preOrderAvailable": false,
  "preOrderDate": "TBA",
  "preOrderPrice": "$69.99",
  "preOrderBonus": null,
  "preOrderLinks": null,
  "platforms": "PS5",
  "developer": "Studio Name",
  "publisher": "Publisher Name",
  "description": "Short description here.",
  "metacriticScore": null,
  "physicalEdition": true,
  "digitalEdition": true,
  "ps5Exclusive": false,
  "hasBeta": false,
  "betaDate": null,
  "tags": ["keyword1", "keyword2"]
}
```

Valid genres: `horror` `action` `rpg` `shooter` `sports` `fighting` `adventure`
Valid statuses: `on-track` `delayed` `released` `tba` `cancelled`

---

## 📁 File Reference

| File | Purpose |
|------|---------|
| `public/index.html` | The full tracker website |
| `public/games.json` | Game database — updated daily |
| `scripts/update_games.py` | Auto-updater script |
| `.github/workflows/update-games.yml` | GitHub Actions schedule |

---

*Made by Binds · Powered by GitHub Actions*
