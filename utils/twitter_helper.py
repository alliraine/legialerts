def send_tweet(text, twitter):
    # lets start by splitting by new line
    lines = text.splitlines()

    # now split those lines up if they are too long
    for i, line in enumerate(lines):
        b_line = wrap(line, 280)
        lines.pop(i)
        for idx, l in enumerate(b_line):
            lines.insert(i + idx, l)

    # now combine the lines where possible
    lines = setup_tweets(0, lines)

    # send tweets. thread where needed
    try:
        t_id = None
        for l in lines:
            if t_id is not None:
                print(l)
                r = twitter.create_tweet(text=l, in_reply_to_tweet_id=t_id)
            else:
                print(l)
                r = twitter.create_tweet(text=l)
            t_id = r.data.get("id")
    except:
        print("error sending tweet")

# recursive function for spliting up tweets
def setup_tweets(i, lines):
    if i < len(lines) - 1:
        if len(lines[i]) + len(lines[i + 1]) < 280:
            lines[i] = (lines[i] + "\n" + lines[i + 1])
            lines.pop(i + 1)
            lines = setup_tweets(i, lines)
        else:
            lines = setup_tweets(i + 1, lines)
    return lines