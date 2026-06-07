#!/usr/bin/env python3
"""
Binds PS5 Tracker - Auto Updater v3
Uses Playwright (real browser) to check PlayStation Store directly.
Runs every 5 minutes via GitHub Actions.
"""

import json
import os
import re
import urllib.request
import asyncio
from datetime import datetime, timezone
from xml.etree import ElementTree

GAMES_PATH = "ps5-tracker/public/games.json"

# PlayStation Store search URLs per game
PS_STORE_SEARCHES = {
    "halloween":            "halloween the game illfonic",
    "gta6":                 "grand theft auto VI",
    "wolverine":            "marvel wolverine ps5",
    "silent-hill-f":        "silent hill f",
    "resident-evil-9":      "resident evil 9",
    "ghost-of-yotei":       "ghost of yotei",
    "call-of-duty-bo7":     "call of duty black ops 7",
    "blood-of-dawnwalker":  "blood of dawnwalker",
    "crimson-desert":       "crimson desert",
    "judas":                "judas game 2k",
    "ninja-gaiden-4":       "ninja gaiden 4",
    "virtua-fighter-6":     "virtua fighter 6",
    "lies-of-p-overture":   "lies of p overture",
    "predator-badlands":    "predator badlands",
    "ea-sports-fc-26":      "ea sports fc 26",
    "wwe-2k27":             "wwe 2k27",
    "hollow-knight-silksong": "hollow knight silksong",
    "final-fantasy-7-remake-part3": "final fantasy VII remake part 3",
}

RSS_FEEDS = [
    "https://www.gematsu.com/feed",
    "https://blog.playstation.com/feed/",
    "https://www.pushsquare.com/feeds/latest",
    "https://www.eurogamer.net/?format=rss",
    "https://www.ign.com/rss/articles",
    "https://gamerant.com/feed/",
]

WATCH_KEYWORDS = {
    "halloween":        ["halloween the game", "illfonic halloween", "michael myers game", "halloween illfonic"],
    "gta6":             ["gta 6", "gta vi", "grand theft auto vi", "grand theft auto 6", "rockstar games gta"],
    "silent-hill-f":    ["silent hill f", "neobards", "silent hill 2026"],
    "call-of-duty-bo7": ["black ops 7", "call of duty 2026", "treyarch 2026"],
    "wolverine":        ["insomniac wolverine", "marvel wolverine ps5", "wolverine ps5"],
    "resident-evil-9":  ["resident evil 9", "re9", "biohazard 9"],
    "crimson-desert":   ["crimson desert", "pearl abyss"],
    "judas":            ["judas game", "ghost story games", "ken levine game"],
    "blood-of-dawnwalker": ["blood of dawnwalker", "rebel wolves"],
    "ninja-gaiden-4":   ["ninja gaiden 4", "ninja gaiden ragebound"],
    "virtua-fighter-6": ["virtua fighter 6", "vf6 sega"],
    "hollow-knight-silksong": ["silksong", "hollow knight 2"],
    "ghost-of-yotei":   ["ghost of yotei", "sucker punch 2026"],
    "predator-badlands": ["predator badlands", "predator game illfonic"],
    "ea-sports-fc-26":  ["ea sports fc 26", "fc 26", "ea fc 26"],
    "wwe-2k27":         ["wwe 2k27", "wwe 2027"],
    "lies-of-p-overture": ["lies of p overture", "lies of p prequel"],
    "final-fantasy-7-remake-part3": ["final fantasy vii remake part 3", "ff7 remake 3", "final fantasy 7 part 3"],
}

DELAY_PATTERNS    = [r"delay", r"pushed back", r"postponed", r"moved to", r"new release date", r"shifted", r"no longer releasing"]
PREORDER_PATTERNS = [r"pre.?order", r"pre.?orders now live", r"available to pre.?order", r"pre.?order now", r"pre.?orders open"]
BETA_PATTERNS     = [r"beta", r"open beta", r"closed beta", r"beta date", r"beta announced"]
RELEASED_PATTERNS = [r"out now", r"available now", r"now available", r"launches today", r"released today", r"on sale now"]


def log(msg):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print(f"[{ts}] {msg}")


def fetch_url(url, timeout=15):
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,*/*;q=0.8"
        })
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception as e:
        log(f"  ⚠ fetch failed {url[:60]}: {e}")
        return None


async def check_ps_store_playwright(game_id, game, page):
    """Use real browser to check PS Store for pre-order/release status."""
    search_term = PS_STORE_SEARCHES.get(game_id)
    if not search_term:
        return False

    url = f"https://store.playstation.com/en-us/search/{search_term.replace(' ', '%20')}"
    changed = False

    try:
        await page.goto(url, wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(3000)

        content = await page.content()
        content_lower = content.lower()

        # Check if game title appears on page
        title_words = [w for w in game["title"].lower().split() if len(w) > 3]
        title_found = sum(1 for w in title_words if w in content_lower) >= min(2, len(title_words))

        if not title_found:
            log(f"  ✗ '{game['title']}' not found on PS Store search")
            return False

        log(f"  ✓ Found '{game['title']}' on PS Store")

        # Check for pre-order
        preorder_signals = ["pre-order", "preorder", "pre order"]
        if not game["preOrderAvailable"]:
            if any(s in content_lower for s in preorder_signals):
                log(f"  🛒 PRE-ORDER LIVE on PS Store: {game['title']}!")
                game["preOrderAvailable"] = True
                game["preOrderDate"] = "Now available"
                if not game.get("preOrderLinks"):
                    game["preOrderLinks"] = "PlayStation Store"

                # Try to get price
                price_match = re.search(r'\$[\d]+\.[\d]{2}', content)
                if price_match and (not game.get("preOrderPrice") or game.get("preOrderPrice") == "TBA"):
                    game["preOrderPrice"] = price_match.group(0)
                    log(f"  💰 Price found: {game['preOrderPrice']}")

                changed = True

        # Check for release
        buy_signals = ["buy now", "add to cart"]
        if game["releaseStatus"] != "released":
            if any(s in content_lower for s in buy_signals):
                if not any(s in content_lower for s in preorder_signals):
                    log(f"  ✅ RELEASED on PS Store: {game['title']}!")
                    game["releaseStatus"] = "released"
                    changed = True

    except Exception as e:
        log(f"  ⚠ Playwright error for {game['title']}: {e}")

    return changed


async def run_playwright_checks(game_index, changes):
    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 800}
            )
            page = await context.new_page()

            log("\n--- Checking PlayStation Store (real browser) ---")
            for game_id, game in game_index.items():
                if game.get("releaseStatus") == "released" and game.get("preOrderAvailable"):
                    continue
                log(f"Checking: {game['title']}")
                if await check_ps_store_playwright(game_id, game, page):
                    changes.append(f"PS_STORE: {game['title']}")

            await browser.close()
    except ImportError:
        log("⚠ Playwright not available, skipping PS Store checks")
    except Exception as e:
        log(f"⚠ Playwright failed: {e}")


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
        log(f"  ⚠ RSS parse error {feed_url}: {e}")
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
    data["updatedBy"] = "Binds PS5 Tracker Auto-Updater v3"
    with open(GAMES_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    log("✅ games.json saved.")


def build_game_index(data):
    return {g["id"]: g for g in data["games"]}


def main():
    log("=== Binds PS5 Tracker Auto-Updater v3 ===")

    data = load_games()
    game_index = build_game_index(data)
    changes = []

    # ── 1. PlayStation Store checks via real browser ──────────────────────────
    asyncio.run(run_playwright_checks(game_index, changes))

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
        for c in changes: log(f"  • {c}")
    else:
        log("\n✅ No changes detected.")

    summary_path = os.environ.get("GITHUB_STEP_SUMMARY", "")
    if summary_path:
        with open(summary_path, "a") as f:
            f.write(f"## PS5 Tracker — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}\n\n")
            if changes:
                f.write(f"### 🔥 {len(changes)} update(s)\n")
                for c in changes: f.write(f"- {c}\n")
            else:
                f.write("✅ No changes.\n")
            f.write(f"\nGames tracked: {len(data['games'])}\n")

    log("=== Done ===")


if __name__ == "__main__":
    main()
