import toml
import feedparser
import subprocess
import sys


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


class SeenList:
    """
    Manages the list of "seen" URLs
    """
    def __enter__(self):
        try:
            with open('.offline-radio.state', 'rt') as f:
                self._urls = set(f)
        except FileNotFoundError:
            self._urls = set()

        self._seen = set()

        return self

    def __exit__(self, *_):
        with open('.offline-radio.state', 'wt') as f:
            for u in self._seen:
                print(u, file=f)

    def has_seen(self, url):
        return url in self._urls or url in self._seen

    def add(self, url):
        self._seen.add(url)


def main():
    with open('.offline-radio.toml', 'rt') as cf:
        config = toml.load(cf)

    with SeenList() as sl:
        for url in mk_feed_urls(config['sub']):
            feed = feedparser.parse(url)
            for ent in feed.entries:
                if not sl.has_seen(ent.link):
                    # FIXME: Don't add to list unless downloaded successfully
                    proc = subprocess.run(
                        [
                            'youtube-dl', '--add-metadata', '--xattrs',
                            '--match-filter', '!is_live',
                            '--extract-audio', '--audio-quality', '0',
                            '--quiet',
                            ent.link,
                        ],
                    )
                    if proc.returncode:
                        print(f"Error downloading {ent['title']} ({ent['link']})", file=sys.stderr)
                    else:
                        sl.add(ent.link)

    # TODO: Apply quotas
