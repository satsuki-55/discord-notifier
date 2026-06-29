import json
import os
import urllib.request
import xml.etree.ElementTree as ET


CONFIG_FILE = "config.json"
STATE_FILE = "state.json"


def load_json(path, default):
    if not os.path.exists(path):
        return default

    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=4)


def fetch_youtube_latest(channel_id):
    rss_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"

    request = urllib.request.Request(
        rss_url,
        headers={"User-Agent": "Mozilla/5.0"},
    )

    with urllib.request.urlopen(request) as response:
        xml_data = response.read()

    root = ET.fromstring(xml_data)

    ns = {
        "atom": "http://www.w3.org/2005/Atom",
        "yt": "http://www.youtube.com/xml/schemas/2015",
    }

    entry = root.find("atom:entry", ns)

    if entry is None:
        return None

    video_id = entry.find("yt:videoId", ns).text
    title = entry.find("atom:title", ns).text
    link = f"https://youtu.be/{video_id}"

    return {
        "id": video_id,
        "title": title,
        "link": link,
    }


def send_discord(webhook_url, content):
    data = json.dumps({"content": content}).encode("utf-8")

    request = urllib.request.Request(
        webhook_url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "DiscordNotifier/1.0",
        },
        method="POST",
    )

    with urllib.request.urlopen(request) as response:
        response.read()


def get_webhook_url(webhook_name):
    env_name = f"DISCORD_WEBHOOK_{webhook_name.upper()}"
    return os.environ.get(env_name)


def handle_youtube_source(source, state):
    name = source["name"]
    channel_id = source["channel_id"]
    webhook_name = source["webhook"]

    latest = fetch_youtube_latest(channel_id)

    if latest is None:
        print(f"[{name}] No videos found.")
        return

    state_key = f"youtube:{name}"
    last_seen_id = state.get(state_key)

    if latest["id"] == last_seen_id:
        print(f"[{name}] No new video.")
        return

    webhook_url = get_webhook_url(webhook_name)

    if webhook_url is None:
        raise RuntimeError(
            f"Webhook secret not found: DISCORD_WEBHOOK_{webhook_name.upper()}"
        )

    content = (
        f"🟥 {name} 新着動画！\n\n"
        f"{latest['title']}\n"
        f"{latest['link']}"
    )

    send_discord(webhook_url, content)

    state[state_key] = latest["id"]

    print(f"[{name}] Sent: {latest['title']}")


def main():
    config = load_json(CONFIG_FILE, {"sources": []})
    state = load_json(STATE_FILE, {})

    for source in config["sources"]:
        source_type = source.get("type")

        if source_type == "youtube":
            handle_youtube_source(source, state)
        else:
            print(f"Unsupported source type: {source_type}")

    save_json(STATE_FILE, state)


if __name__ == "__main__":
    main()
