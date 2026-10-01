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


if __name__ == "__main__":
    unittest.main()
