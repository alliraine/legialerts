import logging
import os
import re
import time
from textwrap import wrap

from atproto_client import models

from utils.config import CACHE_DIR

logger = logging.getLogger(__name__)

BSKY_POST_MIN_INTERVAL = float(os.environ.get("BSKY_POST_MIN_INTERVAL", "60"))
_last_bsky_post_ts = None
_bsky_marker_path = os.path.join(CACHE_DIR, "bsky-last-post.txt")


def _load_last_post_time():
    global _last_bsky_post_ts
    if _last_bsky_post_ts is not None:
        return _last_bsky_post_ts
    try:
        with open(_bsky_marker_path, "r") as handle:
            _last_bsky_post_ts = float(handle.read().strip())
            return _last_bsky_post_ts
    except Exception:
        return None


def _save_last_post_time(ts):
    global _last_bsky_post_ts
    _last_bsky_post_ts = ts
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(_bsky_marker_path, "w") as handle:
            handle.write(str(ts))
    except Exception:
        logger.debug("Unable to persist Bluesky throttle marker", exc_info=True)


def throttle_before_post():
    if BSKY_POST_MIN_INTERVAL <= 0:
        return
    last = _load_last_post_time()
    now = time.time()
    if last is not None:
        wait = (last + BSKY_POST_MIN_INTERVAL) - now
        if wait > 0:
            logger.info("Throttling Bluesky post for %.2fs to respect rate limits", wait)
            time.sleep(wait)
    _save_last_post_time(time.time())

def parse_links(text):
    facets = []
    url_regex = r"[$|\W](https?:\/\/(www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b([-a-zA-Z0-9()@:%_\+.~#?&//=]*[-a-zA-Z0-9@%_\+~#//=])?)"
    all_urls = re.findall(url_regex, text)
    for url in all_urls:
        facets.append(
            models.AppBskyRichtextFacet.Main(
                features=[models.AppBskyRichtextFacet.Link(uri=url[0])],
                # we should pass when our link starts and ends in the text
                # the example below selects all the text
                index=models.AppBskyRichtextFacet.ByteSlice(byte_start=text.index(url[0]), byte_end=text.index(url[0])+len(url[0])),
            )
        )
    return facets


def send_skeet(text, bsky):
    # lets start by splitting by new line
    lines = text.splitlines()

    # now split those lines up if they are too long
    for i, line in enumerate(lines):
        b_line = wrap(line, 280)
        lines.pop(i)
        for idx, l in enumerate(b_line):
            lines.insert(i + idx, l)

    # now combine the lines where possible
    lines = setup_skeets(0, lines)

    # send tweets. thread where needed
    try:
        print("trying to send skeet")
        response = None
        for l in lines:
            facets = parse_links(l)
            if response is not None:
                print(l)
                throttle_before_post()
                parent = models.create_strong_ref(response)
                root = models.create_strong_ref(response)
                response = bsky.send_post(text=l, reply_to=models.AppBskyFeedPost.ReplyRef(parent=parent, root=root), facets=facets)
            else:
                print(l)
                throttle_before_post()
                response = bsky.send_post(text=l, facets=facets)
    except Exception as e:
        print("error sending skeet", e)

# recursive function for spliting up tweets
def setup_skeets(i, lines):
    if i < len(lines) - 1:
        if len(lines[i]) + len(lines[i + 1]) < 280:
            lines[i] = (lines[i] + "\n" + lines[i + 1])
            lines.pop(i + 1)
            lines = setup_skeets(i, lines)
        else:
            lines = setup_skeets(i + 1, lines)
    return lines
