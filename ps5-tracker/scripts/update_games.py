#!/usr/bin/env python3
"""
Binds PS5 Tracker - Auto Updater v4
Uses IsThereAnyDeal API for real price/preorder data.
Runs every 5 minutes via GitHub Actions.
"""

import json
import os
import re
import urllib.request
import urllib.parse
from datetime import datetime, timezone
from xml.etree import ElementTree

GAMES_PATH = "ps5-tracker/public/games.json"
ITAD_API_KEY = os.environ.get("ITAD_API_KEY", "")
ITAD_BASE = "https://api.isthereanydeal.com"

# ITAD search titles per game ID
ITAD_TITLES = {
    "halloween":            "Halloween The Game",
    "gta6":                 "Grand Theft Auto VI",
    "wolverine":            "Marvel's Wolverine",
    "silent-hill-f":        "Silent Hill f",
    "resident-evil-9":      "Resident Evil 9",
    "ghost-of-yotei":       "Ghost of Yotei",
    "call-of-duty-bo7":     "Call of Duty Black Ops 7",
    "blood-of-dawnwalker":  "Blood of Dawnwalker",
    "crimson-desert":       "Crimson Desert",
    "judas":                "Judas",
    "ninja-gaiden-4":       "Ninja Gaiden 4",
    "virtua-fighter-6":     "Virtua Fighter 6",
    "lies-of-p-overture":   "Lies of P Overture",
    "predator-badlands":    "Predator Badlands",
    "ea-sports-fc-26":      "EA Sports FC 26",
    "wwe-2k27":             "WWE 2K27",
    "hollow-knight-silksong": "Hollow Knight Silksong",
    "final-fantasy-7-remake-part3": "Final Fantasy VII Remake Part 3",
}

RSS_FEEDS = [
    "https://www.gematsu.com/feed",
    "https://blog.playstation.com/feed/",
    "https://www.pushsquare.com/feeds/latest",
    "https://www.eurogamer.net/?format=rss",
    "https://gamerant.com/feed/",
    "https://www.polygon.com/rss/index.xml",
    "https://www.gamespot.com/feeds/news/",
    "https://www.ign.com/feed.rss",
    "https://www.vg247.com/feed/news",
    "https://www.dualshockers.com/feed/",
]

WATCH_KEYWORDS = {
    "halloween":        ["halloween the game", "halloween: the game", "illfonic halloween", "michael myers game", "halloween illfonic", "halloween game 2026", "halloween ps5"],
    "gta6":             ["gta 6", "gta vi", "grand theft auto vi", "grand theft auto 6", "gta6", "rockstar pre-order", "gta vi pre-order"],
    "silent-hill-f":    ["silent hill f", "neobards"],
    "call-of-duty-bo7": ["black ops 7", "call of duty 2026", "treyarch 2026"],
    "wolverine":        ["insomniac wolverine", "marvel wolverine", "wolverine ps5", "wolverine pre-order", "marvels wolverine"],
    "resident-evil-9":  ["resident evil 9", "re9", "biohazard 9"],
    "crimson-desert":   ["crimson desert", "pearl abyss"],
    "judas":            ["judas game", "ghost story games", "ken levine"],
    "blood-of-dawnwalker": ["blood of dawnwalker", "rebel wolves"],
    "ninja-gaiden-4":   ["ninja gaiden 4", "ninja gaiden ragebound"],
    "virtua-fighter-6": ["virtua fighter 6", "vf6 sega"],
    "hollow-knight-silksong": ["silksong", "hollow knight 2"],
    "ghost-of-yotei":   ["ghost of yotei", "ghost of yotei pre-order", "sucker punch 2026", "yotei"],
    "predator-badlands": ["predator badlands"],
    "ea-sports-fc-26":  ["ea sports fc 26", "fc 26", "ea fc 26"],
    "wwe-2k27":         ["wwe 2k27"],
    "lies-of-p-overture": ["lies of p overture"],
    "final-fantasy-7-remake-part3": ["final fantasy vii remake part 3", "ff7 remake 3"],
}

DELAY_PATTERNS    = [r"delay", r"pushed back", r"postponed", r"moved to", r"new release date", r"shifted"]
PREORDER_PATTERNS = [r"pre.?order", r"pre.?orders? (now|start|live|open|begin|available)", r"available (to|for) pre.?order", r"pre.?order now", r"now available", r"pre.?orders? start today", r"digital pre.?order"]
BETA_PATTERNS     = [r"beta", r"open beta", r"closed beta", r"beta date", r"beta announced"]
RELEASED_PATTERNS = [r"out now", r"available now", r"now available", r"launches today", r"released today"]


def log(msg):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print(f"[{ts}] {msg}")


def fetch_url(url, timeout=15, headers=None):
    try:
        h = {"User-Agent": "BindsPS5Tracker/4.0 (github.com/oBinds/ps5-tracker)"}
        if headers:
            h.update(headers)
        req = urllib.request.Request(url, headers=h)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception as e:
        log(f"  ⚠ fetch failed {url[:60]}: {e}")
        return None


def itad_search(title):
    """Search ITAD for a game and return its plain ID."""
    if not ITAD_API_KEY:
        return None
    url = f"{ITAD_BASE}/games/search/v1?key={ITAD_API_KEY}&title={urllib.parse.quote(title)}&results=5"
    data = fetch_url(url)
    if not data:
        return None
    try:
        results = json.loads(data)
        for r in results:
            if r.get("title", "").lower() == title.lower():
                return r.get("id")
        if results:
            return results[0].get("id")
    except Exception as e:
        log(f"  ⚠ ITAD search parse error: {e}")
    return None


def itad_get_prices(game_plain):
    """Get current prices for a game from ITAD — checks PS Store (psn) shop."""
    if not ITAD_API_KEY or not game_plain:
        return None
    url = f"{ITAD_BASE}/games/prices/v3?key={ITAD_API_KEY}&country=US&shops=psn"
    try:
        body = json.dumps([game_plain]).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            headers={
                "User-Agent": "BindsPS5Tracker/4.0",
                "Content-Type": "application/json"
            },
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:
        log(f"  ⚠ ITAD prices error: {e}")
        return None


def check_itad(game_id, game):
    """Check ITAD for pre-order/price/release info."""
    title = ITAD_TITLES.get(game_id)
    if not title:
        return False

    log(f"  Searching ITAD: {title}")
    plain = itad_search(title)
    if not plain:
        log(f"  ✗ Not found on ITAD: {title}")
        return False

    log(f"  ✓ Found on ITAD: {plain}")
    prices_data = itad_get_prices(plain)
    if not prices_data:
        return False

    changed = False
    try:
        for entry in prices_data:
            if entry.get("id") != plain:
                continue
            deals = entry.get("deals", [])
            if not deals:
                continue

            for deal in deals:
                shop = deal.get("shop", {}).get("id", "")
                price_info = deal.get("price", {})
                price_amount = price_info.get("amount", 0)
                price_str = f"${price_amount:.2f}" if price_amount else "TBA"
                cut = deal.get("cut", 0)

                log(f"  💰 {shop}: {price_str} ({cut}% off)")

                # If it's on PSN with a price, pre-order is available
                if shop == "psn" and price_amount > 0:
                    if not game["preOrderAvailable"] or game.get("preOrderPrice") in (None, "TBA", ""):
                        log(f"  🛒 PRE-ORDER/PRICE found on PSN: {price_str}")
                        game["preOrderAvailable"] = True
                        game["preOrderDate"] = "Now available"
                        game["preOrderPrice"] = price_str
                        if not game.get("preOrderLinks"):
                            game["preOrderLinks"] = "PlayStation Store"
                        changed = True

                    # If there's a cut, it might be released
                    if cut == 0 and game["releaseStatus"] not in ("released",):
                        pass  # Still pre-order price, not released
    except Exception as e:
        log(f"  ⚠ ITAD price parse error: {e}")

    return changed


def fetch_rss_items(feed_url):
    xml = fetch_url(feed_url)
    if not xml:
        return []
    try:
        root = ElementTree.fromstring(xml)
        items = []
        for item in root.iter("item"):
            title = item.findtext("title") or ""
            desc  = item.findtext("description") or ""
            link  = item.findtext("link") or ""
            items.append((title.lower(), desc.lower(), link))
        return items
    except Exception as e:
        log(f"  ⚠ RSS parse error: {e}")
        return []


def item_matches(title, desc, keywords):
    combined = title + " " + desc
    return any(kw.lower() in combined for kw in keywords)


def detect_event(title, desc):
    combined = title + " " + desc
    events = []
    if any(re.search(p, combined) for p in DELAY_PATTERNS):    events.append("delay")
    if any(re.search(p, combined) for p in PREORDER_PATTERNS): events.append("preorder")
    if any(re.search(p, combined) for p in BETA_PATTERNS):     events.append("beta")
    if any(re.search(p, combined) for p in RELEASED_PATTERNS): events.append("released")
    return events


def load_games():
    with open(GAMES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_games(data):
    data["lastUpdated"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    data["updatedBy"] = "Binds PS5 Tracker Auto-Updater v4"
    with open(GAMES_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    log("✅ games.json saved.")


def build_game_index(data):
    return {g["id"]: g for g in data["games"]}


def main():
    log("=== Binds PS5 Tracker Auto-Updater v4 (ITAD) ===")

    if not ITAD_API_KEY:
        log("⚠ ITAD_API_KEY not set!")
    else:
        log(f"✓ ITAD API key loaded")

    data = load_games()
    game_index = build_game_index(data)
    changes = []

    # ── 1. IsThereAnyDeal API checks ──────────────────────────────────────────
    log("\n--- Checking IsThereAnyDeal API ---")
    for game_id, game in game_index.items():
        if game.get("releaseStatus") == "released" and game.get("preOrderAvailable"):
            continue
        if check_itad(game_id, game):
            changes.append(f"ITAD: {game['title']}")

    # ── 2. RSS feed checks ────────────────────────────────────────────────────
    log("\n--- Checking RSS feeds ---")
    all_items = []
    for feed in RSS_FEEDS:
        log(f"  {feed}")
        items = fetch_rss_items(feed)
        all_items.extend(items)
        log(f"  → {len(items)} items")

    for game_id, keywords in WATCH_KEYWORDS.items():
        game = game_index.get(game_id)
        if not game:
            continue
        matched = [i for i in all_items if item_matches(i[0], i[1], keywords)]
        if not matched:
            continue
        log(f"\n📌 {len(matched)} news items: {game['title']}")
        for title, desc, link in matched[:5]:
            events = detect_event(title, desc)
            if not events:
                continue
            log(f"  Events: {events} | {title[:80]}")
            if "delay" in events and game["releaseStatus"] not in ("released", "cancelled", "delayed"):
                game["releaseStatus"] = "delayed"
                if not game.get("delayInfo"):
                    game["delayInfo"] = f"Delay reported {datetime.now(timezone.utc).strftime('%b %Y')}. Source: {link}"
                changes.append(f"DELAY: {game['title']}")
            if "preorder" in events and not game["preOrderAvailable"]:
                game["preOrderAvailable"] = True
                game["preOrderDate"] = "Now available"
                if not game.get("preOrderLinks"):
                    game["preOrderLinks"] = "PlayStation Store"
                changes.append(f"PREORDER: {game['title']}")
            if "beta" in events and not game["hasBeta"]:
                game["hasBeta"] = True
                if not game.get("betaDate"):
                    game["betaDate"] = f"Beta announced {datetime.now(timezone.utc).strftime('%b %Y')}"
                changes.append(f"BETA: {game['title']}")
            if "released" in events and game["releaseStatus"] != "released":
                game["releaseStatus"] = "released"
                changes.append(f"RELEASED: {game['title']}")

    # ── 3. Save ───────────────────────────────────────────────────────────────
    save_games(data)

    if changes:
        log(f"\n🔥 {len(changes)} change(s):")
        for c in changes:
            log(f"  • {c}")
    else:
        log("\n✅ No changes detected.")

    summary_path = os.environ.get("GITHUB_STEP_SUMMARY", "")
    if summary_path:
        with open(summary_path, "a") as f:
            f.write(f"## PS5 Tracker — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}\n\n")
            if changes:
                f.write(f"### 🔥 {len(changes)} update(s)\n")
                for c in changes:
                    f.write(f"- {c}\n")
            else:
                f.write("✅ No changes.\n")
            f.write(f"\nGames tracked: {len(data['games'])}\n")

    log("=== Done ===")


if __name__ == "__main__":
    main()
