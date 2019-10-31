import toml
import feedparser
import subprocess


def mk_feed_urls(subs):
    for sub in subs:
        assert len(sub) == 1, "Can't have more than one address per subscription"
        if 'yt_id' in sub:
            yield f"https://www.youtube.com/feeds/videos.xml?channel_id={sub['yt_id']}"
        elif 'yt_name' in sub:
            yield f"https://www.youtube.com/feeds/videos.xml?user={sub['yt_name']}"
        elif 'feed' in sub:
            yield sub['feed']
        else:
            raise ValueError(f"Unknown sub: {sub!r}")


def main():
    with open('.offline-radio.toml', 'rt') as cf:
        config = toml.load(cf)

    for url in mk_feed_urls(config['sub']):
        feed = feedparser.parse(url)
        for ent in feed.entries:
            # TODO: Check if we've looked at this file before
            subprocess.run(
                [
                    'youtube-dl', '--add-metadata', '--xattrs',
                    '--extract-audio', '--audio-quality', '0',
                    ent.link,
                ],
            )

    # TODO: Apply quotas
