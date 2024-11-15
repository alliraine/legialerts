import re
from textwrap import wrap

from atproto_client import models

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
                parent = models.create_strong_ref(response)
                root = models.create_strong_ref(response)
                response = bsky.send_post(text=l, reply_to=models.AppBskyFeedPost.ReplyRef(parent=parent, root=root), facets=facets)
            else:
                print(l)
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