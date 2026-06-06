#!/usr/bin/env python3
"""
Binds PS5 Tracker - Auto Updater
Runs every 5 minutes via GitHub Actions.
Checks PlayStation Store directly + RSS feeds for updates.
"""

import json
import os
import re
import urllib.request
import urllib.error
from datetime import datetime, timezone
from xml.etree import ElementTree

GAMES_PATH = "ps5-tracker/public/games.json"

# Direct PlayStation Store search URLs per game
PS_STORE_CHECKS = {
    "halloween":            "https://store.playstation.com/en-us/search/halloween%20illfonic",
    "gta6":                 "https://store.playstation.com/en-us/search/grand%20theft%20auto%20VI",
    "wolverine":            "https://store.playstation.com/en-us/search/marvel%20wolverine",
    "silent-hill-f":        "https://store.playstation.com/en-us/search/silent%20hill%20f",
    "resident-evil-9":      "https://store.playstation.com/en-us/search/resident%20evil%209",
    "ghost-of-yotei":       "https://store.playstation.com/en-us/search/ghost%20of%20yotei",
    "call-of-duty-bo7":     "https://store.playstation.com/en-us/search/black%20ops%207",
    "blood-of-dawnwalker":  "https://store.playstation.com/en-us/search/blood%20of%20dawnwalker",
    "crimson-desert":       "https://store.playstation.com/en-us/search/crimson%20desert",
    "judas":                "https://store.playstation.com/en-us/search/judas%20game",
    "ninja-gaiden-4":       "https://store.playstation.com/en-us/search/ninja%20gaiden%204",
    "virtua-fighter-6":     "https://store.playstation.com/en-us/search/virtua%20fighter%206",
    "lies-of-p-overture":   "https://store.playstation.com/en-us/search/lies%20of%20p%20overture",
    "predator-badlands":    "https://store.playstation.com/en-us/search/predator%20badlands",
    "ea-sports-fc-26":      "https://store.playstation.com/en-us/search/ea%20sports%20fc%2026",
    "wwe-2k27":             "https://store.playstation.com/en-us/search/wwe%202k27",
    "hollow-knight-silksong": "https://store.playstation.com/en-us/search/silksong",
    "final-fantasy-7-remake-part3": "https://store.playstation.com/en-us/search/final%20fantasy%20VII%20remake%20part%203",
}

# RSS feeds from trusted gaming news sites
RSS_FEEDS = [
    "https://www.gematsu.com/feed",
    "https://blog.playstation.com/feed/",
    "https://www.pushsquare.com/feeds/latest",
    "https://www.eurogamer.net/?format=rss",
]

# Keywords to watch per game ID
WATCH_KEYWORDS = {
    "halloween":        ["halloween game", "illfonic halloween", "michael myers game", "halloween illfonic"],
    "gta6":             ["gta 6", "gta vi", "grand theft auto 6", "grand theft auto vi", "rockstar games"],
    "silent-hill-f":    ["silent hill f", "neobards", "silent hill 2026"],
    "call-of-duty-bo7": ["black ops 7", "call of duty 2026", "treyarch"],
    "wolverine":        ["insomniac wolverine", "marvel wolverine ps5", "wolverine ps5"],
    "resident-evil-9":  ["resident evil 9", "re9", "biohazard 9"],
    "crimson-desert":   ["crimson desert", "pearl abyss"],
    "judas":            ["judas game", "ghost story games", "ken levine"],
    "blood-of-dawnwalker": ["blood of dawnwalker", "rebel wolves"],
    "ninja-gaiden-4":   ["ninja gaiden 4", "ninja gaiden ragebound"],
    "virtua-fighter-6": ["virtua fighter 6", "vf6"],
    "hollow-knight-silksong": ["silksong", "hollow knight 2"],
    "ghost-of-yotei":   ["ghost of yotei", "sucker punch 2026"],
    "predator-badlands": ["predator badlands", "predator game 2026"],
    "ea-sports-fc-26":  ["ea sports fc 26", "fc 26", "fifa 26"],
}

DELAY_PATTERNS = [
    r"delay", r"pushed back", r"postponed", r"moved to", r"new release date",
    r"no longer releasing", r"missed", r"shifted"
]

PREORDER_PATTERNS = [
    r"pre.?order", r"pre.?orders now live", r"available to pre.?order",
    r"pre.?order now", r"pre.?orders open", r"now available to pre.?order"
]

BETA_PATTERNS = [
    r"beta", r"open beta", r"closed beta", r"beta date", r"beta announced"
]

RELEASED_PATTERNS = [
    r"out now", r"available now", r"now available", r"launches today",
    r"released today", r"on sale now"
]


def log(msg):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print(f"[{ts}] {msg}")


def fetch_url(url, timeout=15):
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (compatible; BindsPS5Tracker/2.0)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        })
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception as e:
        log(f"  ⚠ Could not fetch {url}: {e}")
        return None


def check_ps_store(game_id, game):
    """Check PlayStation Store directly for pre-order/release status."""
    url = PS_STORE_CHECKS.get(game_id)
    if not url:
        return False

    html = fetch_url(url)
    if not html:
        return False

    html_lower = html.lower()
    game_title_lower = game["title"].lower()
    changed = False

    # Check if game appears in store results
    title_words = [w for w in game_title_lower.split() if len(w) > 3]
    title_found = sum(1 for w in title_words if w in html_lower) >= min(2, len(title_words))

    if not title_found:
        return False

    log(f"  ✓ Found '{game['title']}' on PS Store")

    # Check for pre-order button/text
    preorder_signals = ["pre-order", "preorder", "pre order", "add to cart"]
    if not game["preOrderAvailable"]:
        if any(s in html_lower for s in preorder_signals):
            log(f"  🛒 PRE-ORDER DETECTED on PS Store for {game['title']}!")
            game["preOrderAvailable"] = True
            game["preOrderDate"] = "Now available"
            game["preOrderLinks"] = "PlayStation Store"
            changed = True

    # Check for release (purchase now, buy now)
    release_signals = ["buy now", "add to cart", "purchase"]
    if game["releaseStatus"] != "released":
        if any(s in html_lower for s in release_signals):
            # Only flag as released if we also see no "pre-order" signals
            if not any(s in html_lower for s in ["pre-order", "preorder"]):
                log(f"  ✅ RELEASE DETECTED on PS Store for {game['title']}!")
                game["releaseStatus"] = "released"
                changed = True

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
        log(f"  ⚠ Parse error for {feed_url}: {e}")
        return []


def item_matches(item_title, item_desc, keywords):
    combined = item_title + " " + item_desc
    return any(kw.lower() in combined for kw in keywords)


def detect_event(item_title, item_desc):
    combined = item_title + " " + item_desc
    events = []
    if any(re.search(p, combined) for p in DELAY_PATTERNS):
        events.append("delay")
    if any(re.search(p, combined) for p in PREORDER_PATTERNS):
        events.append("preorder")
    if any(re.search(p, combined) for p in BETA_PATTERNS):
        events.append("beta")
    if any(re.search(p, combined) for p in RELEASED_PATTERNS):
        events.append("released")
    return events


def load_games():
    with open(GAMES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_games(data):
    data["lastUpdated"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    data["updatedBy"] = "Binds PS5 Tracker Auto-Updater"
    with open(GAMES_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    log("✅ games.json saved.")


def build_game_index(data):
    return {g["id"]: g for g in data["games"]}


def main():
    log("=== Binds PS5 Tracker Auto-Updater v2 Starting ===")

    data = load_games()
    game_index = build_game_index(data)
    changes = []

    # ── 1. Direct PlayStation Store checks ───────────────────────────────────
    log("\n--- Checking PlayStation Store directly ---")
    for game_id, game in game_index.items():
        if game.get("releaseStatus") == "released" and game.get("preOrderAvailable"):
            continue  # Nothing more to check
        log(f"Checking PS Store: {game['title']}")
        if check_ps_store(game_id, game):
            changes.append(f"PS_STORE: {game['title']}")

    # ── 2. RSS feed checks ────────────────────────────────────────────────────
    log("\n--- Fetching RSS feeds ---")
    all_items = []
    for feed in RSS_FEEDS:
        log(f"  Fetching {feed}")
        items = fetch_rss_items(feed)
        all_items.extend(items)
        log(f"  Got {len(items)} items")

    log(f"Total RSS items: {len(all_items)}")

    for game_id, keywords in WATCH_KEYWORDS.items():
        game = game_index.get(game_id)
        if not game:
            continue

        matched_items = [item for item in all_items if item_matches(item[0], item[1], keywords)]
        if not matched_items:
            continue

        log(f"\n📌 {len(matched_items)} news items for: {game['title']}")

        for item_title, item_desc, item_link in matched_items[:5]:
            events = detect_event(item_title, item_desc)
            if not events:
                continue

            log(f"  Events: {events} | {item_title[:80]}")

            if "delay" in events and game["releaseStatus"] not in ("released", "cancelled", "delayed"):
                log(f"  ⚠️  DELAY: {game['title']}")
                game["releaseStatus"] = "delayed"
                note = f"Delay reported {datetime.now(timezone.utc).strftime('%b %Y')}. Source: {item_link}"
                if not game.get("delayInfo"):
                    game["delayInfo"] = note
                changes.append(f"DELAY: {game['title']}")

            if "preorder" in events and not game["preOrderAvailable"]:
                log(f"  🛒 PREORDER: {game['title']}")
                game["preOrderAvailable"] = True
                game["preOrderDate"] = "Now available"
                if not game.get("preOrderLinks"):
                    game["preOrderLinks"] = "PlayStation Store"
                changes.append(f"PREORDER: {game['title']}")

            if "beta" in events and not game["hasBeta"]:
                log(f"  🧪 BETA: {game['title']}")
                game["hasBeta"] = True
                if not game.get("betaDate"):
                    game["betaDate"] = f"Beta announced {datetime.now(timezone.utc).strftime('%b %Y')}"
                changes.append(f"BETA: {game['title']}")

            if "released" in events and game["releaseStatus"] != "released":
                log(f"  ✅ RELEASED: {game['title']}")
                game["releaseStatus"] = "released"
                changes.append(f"RELEASED: {game['title']}")

    # ── 3. Always save (updates lastUpdated timestamp) ────────────────────────
    save_games(data)

    if changes:
        log(f"\n🔥 {len(changes)} change(s):")
        for c in changes:
            log(f"  • {c}")
    else:
        log("\n✅ No changes. All data current.")

    summary_path = os.environ.get("GITHUB_STEP_SUMMARY", "")
    if summary_path:
        with open(summary_path, "a") as f:
            f.write(f"## PS5 Tracker Update — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}\n\n")
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
