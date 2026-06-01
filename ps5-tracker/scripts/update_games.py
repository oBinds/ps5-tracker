#!/usr/bin/env python3
"""
Binds PS5 Tracker - Auto Updater
Runs daily via GitHub Actions to keep games.json accurate.
Checks gaming RSS feeds and known sources for updates.
"""

import json
import os
import re
import urllib.request
import urllib.error
from datetime import datetime, timezone
from xml.etree import ElementTree

GAMES_PATH = "public/games.json"

# RSS feeds from trusted gaming news sites
RSS_FEEDS = [
    "https://www.gematsu.com/feed",
    "https://blog.playstation.com/feed/",
    "https://www.pushsquare.com/feeds/latest",
    "https://www.eurogamer.net/?format=rss",
]

# Keywords to watch per game ID
WATCH_KEYWORDS = {
    "halloween":        ["halloween game", "illfonic halloween", "michael myers game"],
    "gta6":             ["gta 6", "gta vi", "grand theft auto 6", "grand theft auto vi", "rockstar"],
    "silent-hill-f":    ["silent hill f", "neobards", "silent hill 2026"],
    "call-of-duty-bo7": ["black ops 7", "call of duty 2025", "treyarch"],
    "wolverine":        ["insomniac wolverine", "marvel wolverine ps5"],
    "resident-evil-9":  ["resident evil 9", "re9", "biohazard 9"],
    "crimson-desert":   ["crimson desert", "pearl abyss"],
    "judas":            ["judas game", "ghost story games", "ken levine"],
    "blood-of-dawnwalker": ["blood of dawnwalker", "rebel wolves"],
    "ninja-gaiden-4":   ["ninja gaiden 4", "ninja gaiden ragebound"],
    "virtua-fighter-6": ["virtua fighter 6", "vf6"],
    "hollow-knight-silksong": ["silksong", "hollow knight 2"],
}

# Patterns that suggest a delay announcement
DELAY_PATTERNS = [
    r"delay", r"pushed back", r"postponed", r"moved to", r"new release date",
    r"no longer releasing", r"missed", r"shifted"
]

# Patterns that suggest a pre-order is live
PREORDER_PATTERNS = [
    r"pre.?order", r"pre.?orders now live", r"available to pre.?order",
    r"pre.?order now", r"pre.?orders open"
]

# Patterns for beta news
BETA_PATTERNS = [
    r"beta", r"open beta", r"closed beta", r"beta date", r"beta announced"
]


def log(msg):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print(f"[{ts}] {msg}")


def fetch_url(url, timeout=10):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "BindsPS5Tracker/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception as e:
        log(f"  ⚠ Could not fetch {url}: {e}")
        return None


def fetch_rss_items(feed_url):
    """Fetch and parse an RSS feed, return list of (title, description, link) tuples."""
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
    return events


def load_games():
    with open(GAMES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_games(data):
    data["lastUpdated"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(GAMES_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    log("✅ games.json saved.")


def build_game_index(data):
    return {g["id"]: g for g in data["games"]}


def check_gta6_preorder(game):
    """Special check: scrape Rockstar/Take-Two news for GTA6 pre-order."""
    log("  Checking GTA 6 pre-order status...")
    html = fetch_url("https://www.rockstargames.com/newswire")
    if html and "pre-order" in html.lower():
        if "grand theft auto" in html.lower() or "gta vi" in html.lower():
            log("  🚨 GTA 6 PRE-ORDER possibly live on Rockstar newswire!")
            game["preOrderAvailable"] = True
            game["preOrderDate"] = datetime.now(timezone.utc).strftime("%B %Y")
            game["preOrderLinks"] = "PlayStation Store, Rockstar Games"
            return True
    return False


def main():
    log("=== Binds PS5 Tracker Auto-Updater Starting ===")

    data = load_games()
    game_index = build_game_index(data)
    changes = []

    # Fetch all RSS feeds
    log("Fetching RSS feeds...")
    all_items = []
    for feed in RSS_FEEDS:
        log(f"  Fetching {feed}")
        items = fetch_rss_items(feed)
        all_items.extend(items)
        log(f"  Got {len(items)} items")

    log(f"Total RSS items: {len(all_items)}")

    # Check each watched game against RSS items
    for game_id, keywords in WATCH_KEYWORDS.items():
        game = game_index.get(game_id)
        if not game:
            continue

        matched_items = [item for item in all_items if item_matches(item[0], item[1], keywords)]
        if not matched_items:
            continue

        log(f"\n📌 Found {len(matched_items)} news items for: {game['title']}")

        for item_title, item_desc, item_link in matched_items[:3]:
            events = detect_event(item_title, item_desc)
            if not events:
                continue

            log(f"  Events detected: {events} | {item_title[:80]}")

            if "delay" in events and game["releaseStatus"] not in ("released", "cancelled"):
                log(f"  ⚠️  DELAY detected for {game['title']}")
                if game["releaseStatus"] != "delayed":
                    game["releaseStatus"] = "delayed"
                    note = f"Possible delay reported {datetime.now(timezone.utc).strftime('%b %Y')}. Source: {item_link}"
                    if not game.get("delayInfo"):
                        game["delayInfo"] = note
                    changes.append(f"DELAY: {game['title']}")

            if "preorder" in events and not game["preOrderAvailable"]:
                log(f"  🛒 PRE-ORDER news detected for {game['title']}")
                game["preOrderAvailable"] = True
                game["preOrderDate"] = datetime.now(timezone.utc).strftime("%B %Y")
                if not game.get("preOrderLinks"):
                    game["preOrderLinks"] = "PlayStation Store"
                changes.append(f"PREORDER: {game['title']}")

            if "beta" in events and not game["hasBeta"]:
                log(f"  🧪 BETA news detected for {game['title']}")
                game["hasBeta"] = True
                if not game.get("betaDate"):
                    game["betaDate"] = f"Beta announced {datetime.now(timezone.utc).strftime('%b %Y')} — check PlayStation Store for details"
                changes.append(f"BETA: {game['title']}")

    # Special case: GTA 6 pre-order live check
    gta = game_index.get("gta6")
    if gta and not gta["preOrderAvailable"]:
        if check_gta6_preorder(gta):
            changes.append("PREORDER: Grand Theft Auto VI")

    # Always update lastUpdated
    save_games(data)

    # Summary
    if changes:
        log(f"\n🔥 {len(changes)} change(s) detected:")
        for c in changes:
            log(f"  • {c}")
    else:
        log("\n✅ No changes detected. All data is current.")

    # Write summary file for GitHub Actions step summary
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY", "")
    if summary_path:
        with open(summary_path, "a") as f:
            f.write(f"## Binds PS5 Tracker Update — {datetime.now(timezone.utc).strftime('%Y-%m-%d')}\n\n")
            if changes:
                f.write(f"### 🔥 {len(changes)} update(s) detected\n")
                for c in changes:
                    f.write(f"- {c}\n")
            else:
                f.write("✅ No changes — all data current.\n")
            f.write(f"\nTotal games tracked: {len(data['games'])}\n")

    log("=== Done ===")


if __name__ == "__main__":
    main()
