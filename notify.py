import json
import os
import html
import re
import urllib.request
import urllib.error
import urllib.parse
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


def strip_html(text):
    if not text:
        return ""

    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    return " ".join(text.split())


def find_text(element, paths, namespaces):
    for path in paths:
        found = element.find(path, namespaces)
        if found is not None and found.text:
            return strip_html(found.text)
    return ""


def fetch_rss_latest(feed_url):
    request = urllib.request.Request(
        feed_url,
        headers={"User-Agent": "Mozilla/5.0"},
    )

    try:
        with urllib.request.urlopen(request) as response:
            xml_data = response.read()
    except urllib.error.HTTPError as error:
        if error.code in (301, 302, 303, 307, 308):
            redirected_url = error.headers.get("Location")
            if not redirected_url:
                raise

            redirected_url = urllib.parse.urljoin(feed_url, redirected_url)

            redirected_request = urllib.request.Request(
                redirected_url,
                headers={"User-Agent": "Mozilla/5.0"},
            )

            with urllib.request.urlopen(redirected_request) as response:
                xml_data = response.read()
        else:
            raise

    root = ET.fromstring(xml_data)

    namespaces = {
        "atom": "http://www.w3.org/2005/Atom",
        "content": "http://purl.org/rss/1.0/modules/content/",
        "dc": "http://purl.org/dc/elements/1.1/",
    }

    entry = root.find(".//item")
    is_atom = False

    if entry is None:
        entry = root.find("atom:entry", namespaces)
        is_atom = True

    if entry is None:
        return None

    if is_atom:
        title = find_text(entry, ["atom:title"], namespaces)
        summary = find_text(entry, ["atom:summary", "atom:content"], namespaces)
        article_id = find_text(entry, ["atom:id"], namespaces)

        link_element = entry.find("atom:link", namespaces)
        link = ""
        if link_element is not None:
            link = link_element.attrib.get("href", "")
    else:
        title = find_text(entry, ["title"], namespaces)
        summary = find_text(entry, ["description", "content:encoded"], namespaces)
        article_id = find_text(entry, ["guid"], namespaces)
        link = find_text(entry, ["link"], namespaces)

    if not article_id:
        article_id = link or title

    return {
        "id": article_id,
        "title": title,
        "summary": summary,
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

    state_key = f"youtube:{channel_id}"
    old_state_key = f"youtube:{name}"
    last_seen_id = state.get(state_key)

    if last_seen_id is None and old_state_key in state:
        last_seen_id = state[old_state_key]
        state[state_key] = last_seen_id
        del state[old_state_key]

    if latest["id"] == last_seen_id:
        print(f"[{name}] No new video.")
        return

    webhook_url = get_webhook_url(webhook_name)

    if webhook_url is None:
        raise RuntimeError(
            f"Webhook secret not found: DISCORD_WEBHOOK_{webhook_name.upper()}"
        )

    content = (
        f"{latest['title']}\n"
        f"{latest['link']}"
    )

    send_discord(webhook_url, content)

    state[state_key] = latest["id"]

    print(f"[{name}] Sent: {latest['title']}")


def handle_rss_source(source, state):
    name = source["name"]
    feed_url = source["url"]
    webhook_name = source["webhook"]

    if not feed_url:
        print(f"[{name}] RSS URL is empty. Skipped.")
        return

    latest = fetch_rss_latest(feed_url)

    if latest is None:
        print(f"[{name}] No RSS entries found.")
        return

    state_key = f"rss:{webhook_name}"
    sent_ids = state.get(state_key, [])

    # 旧バージョンとの互換性
    if isinstance(sent_ids, str):
        sent_ids = [sent_ids]

    if latest["id"] in sent_ids:
        print(f"[{name}] No new article.")
        return

    webhook_url = get_webhook_url(webhook_name)

    if webhook_url is None:
        raise RuntimeError(
            f"Webhook secret not found: DISCORD_WEBHOOK_{webhook_name.upper()}"
        )

    content_parts = [latest["title"]]

    if latest["summary"]:
        content_parts.append(latest["summary"])

    if latest["link"]:
        content_parts.append(latest["link"])

    content = "\n\n".join(content_parts)

    send_discord(webhook_url, content)

    # 新しい記事を先頭に追加
    sent_ids.insert(0, latest["id"])

    # 最新20件だけ保持
    state[state_key] = sent_ids[:20]

    print(f"[{name}] Sent: {latest['title']}")


def main():
    config = load_json(CONFIG_FILE, {"sources": []})
    state = load_json(STATE_FILE, {})

    for source in config["sources"]:
        source_type = source.get("type")

        try:
            if source_type == "youtube":
                handle_youtube_source(source, state)
            elif source_type == "rss":
                handle_rss_source(source, state)
            else:
                print(f"Unsupported source type: {source_type}")
        except Exception as error:
            source_name = source.get("name", "unknown")
            print(f"[{source_name}] Error: {error}")

    save_json(STATE_FILE, state)


if __name__ == "__main__":
    main()
