"""Send selected NON STYLE videos from their own or Yoshimoto's official channel."""
import json
import os
import re
import time
import urllib.parse
import urllib.request

from notify import get_webhook_url, send_discord


def main():
    ids = json.loads(os.environ["SELECTED_VIDEO_IDS"])
    if not isinstance(ids, list) or not 1 <= len(ids) <= 25:
        raise ValueError("Supply a JSON array of 1 to 25 video IDs")
    if any(not isinstance(vid, str) or not re.fullmatch(r"[A-Za-z0-9_-]{11}", vid) for vid in ids):
        raise ValueError("Invalid YouTube video ID")
    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate video IDs")
    webhook = get_webhook_url("nonstyle")
    if not webhook:
        raise RuntimeError("DISCORD_WEBHOOK_NONSTYLE is missing")

    # Validate the entire selection before sending any message.
    videos = []
    for vid in ids:
        url = "https://www.youtube.com/oembed?" + urllib.parse.urlencode(
            {"format": "json", "url": f"https://www.youtube.com/watch?v={vid}"}
        )
        with urllib.request.urlopen(url, timeout=30) as response:
            data = json.load(response)
        author_url = data.get("author_url", "").rstrip("/")
        nonstyle_channel = author_url in (
            "https://www.youtube.com/@nonstyle4271",
            "https://www.youtube.com/channel/UCJcyQ-N0sbvwjYpDNXP9tsw",
        )
        yoshimoto_nonstyle_video = author_url in (
            "https://www.youtube.com/@yoshimotokogyo",
            "https://www.youtube.com/user/yoshimotokogyo",
            "https://www.youtube.com/channel/UCfhfIBo7PhDzpK_Yuyk2OXg",
        ) and re.search(r"NON\s*STYLE", data.get("title", ""), re.IGNORECASE)
        if not (nonstyle_channel or yoshimoto_nonstyle_video):
            raise ValueError(f"Video {vid} is not an official NON STYLE video")
        videos.append((vid, data["title"]))

    for vid, title in videos:
        send_discord(webhook, f"{title}\nhttps://youtu.be/{vid}")
        print(f"Sent selected video: {vid} {title}", flush=True)
        time.sleep(1)


if __name__ == "__main__":
    main()
