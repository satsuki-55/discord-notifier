import io
import unittest
import urllib.error
from unittest.mock import patch

import notify


class YouTubeFallbackTests(unittest.TestCase):
    def test_valid_rss_does_not_fetch_page(self):
        xml = b'''<feed xmlns="http://www.w3.org/2005/Atom"
          xmlns:yt="http://www.youtube.com/xml/schemas/2015">
          <entry><yt:videoId>video</yt:videoId><title>Title</title></entry></feed>'''
        with patch("notify.urllib.request.urlopen", return_value=io.BytesIO(xml)), patch(
            "notify.fetch_youtube_latest_from_page"
        ) as page:
            self.assertEqual(notify.fetch_youtube_latest("channel")["id"], "video")
            page.assert_not_called()

    def test_fetch_and_parse_failures_use_page(self):
        failures = [
            urllib.error.HTTPError("url", code, "failure", {}, None)
            for code in (403, 404, 429, 503)
        ] + [urllib.error.URLError("network"), TimeoutError("timeout")]
        for failure in failures:
            with self.subTest(failure=failure), patch(
                "notify.urllib.request.urlopen", side_effect=failure
            ), patch("notify.fetch_youtube_latest_from_page", return_value={"id": "fallback"}):
                self.assertEqual(notify.fetch_youtube_latest("channel")["id"], "fallback")
        for xml in (b"not XML", b'<feed xmlns="http://www.w3.org/2005/Atom"><entry/></feed>'):
            with self.subTest(xml=xml), patch(
                "notify.urllib.request.urlopen", return_value=io.BytesIO(xml)
            ), patch("notify.fetch_youtube_latest_from_page", return_value={"id": "fallback"}):
                self.assertEqual(notify.fetch_youtube_latest("channel")["id"], "fallback")

    def test_both_fail_preserves_state_and_does_not_send(self):
        state = {"youtube:channel": "old-video"}
        with patch("notify.fetch_youtube_latest_from_rss", side_effect=TimeoutError("timeout")), patch(
            "notify.fetch_youtube_latest_from_page", side_effect=RuntimeError("no data")
        ), patch("notify.send_discord") as send:
            with self.assertRaisesRegex(RuntimeError, "official video list also failed"):
                notify.handle_youtube_source(
                    {"name": "Test", "channel_id": "channel", "webhook": "test"}, state
                )
            self.assertEqual(state, {"youtube:channel": "old-video"})
            send.assert_not_called()


class YouTubeHistoryTests(unittest.TestCase):
    source = {"name": "Test", "channel_id": "channel", "webhook": "test"}

    def handle(self, state, video_id, failure=None):
        with patch("notify.fetch_youtube_latest", return_value={
            "id": video_id, "title": "Title", "link": "mock"
        }), patch("notify.get_webhook_url", return_value="mock"), patch(
            "notify.send_discord", side_effect=failure
        ) as send:
            notify.handle_youtube_source(self.source, state)
            return send.call_count

    def test_alternating_videos_survive_state_reload(self):
        state = {"youtube:channel": "A"}
        self.assertEqual(self.handle(state, "B"), 1)
        state = notify.json.loads(notify.json.dumps(state))
        self.assertEqual(self.handle(state, "A"), 0)
        self.assertEqual(self.handle(state, "B"), 0)
        self.assertEqual(self.handle(state, "C"), 1)
        self.assertEqual(state["youtube:channel"], ["C", "B", "A"])

    def test_legacy_name_key_migrates_without_resending(self):
        for previous in ("A", ["A", "B"]):
            with self.subTest(previous=previous):
                state = {"youtube:Test": previous}
                self.assertEqual(self.handle(state, "A"), 0)
                self.assertNotIn("youtube:Test", state)
                self.assertIsInstance(state["youtube:channel"], list)

    def test_send_failure_does_not_record_video(self):
        for previous in ("A", ["A"]):
            with self.subTest(previous=previous):
                state = {"youtube:channel": previous}
                with self.assertRaises(RuntimeError):
                    self.handle(state, "B", RuntimeError("send failed"))
                self.assertEqual(state, {"youtube:channel": previous})

    def test_history_is_limited_to_200(self):
        state = {"youtube:channel": [str(i) for i in range(200)]}
        self.assertEqual(self.handle(state, "new"), 1)
        self.assertEqual(len(state["youtube:channel"]), 200)
        self.assertEqual(state["youtube:channel"][0], "new")
        self.assertNotIn("199", state["youtube:channel"])


if __name__ == "__main__":
    unittest.main()
