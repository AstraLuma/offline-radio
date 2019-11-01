import toml
import feedparser
from pathlib import Path
import subprocess
import sys
import time


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


def pathtime(p):
    """
    Get the earliest known time for this file
    """
    s = p.stat()
    return min((
        s.st_atime,
        s.st_mtime,
        s.st_ctime,
    ))


def iter_media():
    for f in Path().iterdir():
        if f.name.startswith('.'):
            continue
        if not f.is_file():
            continue
        yield f


class SeenList:
    """
    Manages the list of "seen" URLs
    """
    # So the way this works is that we load the seen list, and save the seen
    # list on exit.
    # To keep the list at a managable size, we prune everything not seen this
    # round, on the assumption that it's fallen out of the feed and won't come
    # back.

    # The way this shakes out is we keep two groups, seen last time and seen
    # this time.
    def __enter__(self):
        try:
            with open('.offline-radio.state', 'rt') as f:
                self._urls = {
                    l.strip()
                    for l in f
                }
        except FileNotFoundError:
            self._urls = set()

        self._seen = set()

        return self

    def __exit__(self, type, value, traceback):
        # On error exit, don't prune
        if value:
            seq = self._urls + self._seen
        else:
            seq = self._seen
        with open('.offline-radio.state', 'wt') as f:
            for u in seq:
                print(u, file=f)

    def has_seen(self, url):
        return url in self._urls or url in self._seen

    def add(self, url):
        self._seen.add(url)


def remove_old(maxage):
    """
    Remove files that are too old
    """
    mintime = time.time() + maxage
    for f in iter_media():
        if f.startswith('.'):
            continue
        if not f.is_file():
            continue

        if pathtime(f) < mintime:
            print(f"Deleting {f}")
            f.unlink()


def iter_until_total(seq, max):
    total = 0
    for k, n in seq:
        total += n
        if total < max:
            yield k, n
        else:
            break


def remove_big(maxsize):
    """
    Remove files until we're under the max size, oldest first
    """
    files = sorted([
        (p, p.stat().st_size)
        for p in iter_media()
    ], key=lambda i: pathtime(i[0]))
    totalsize = sum(s for _, s in files)
    if totalsize > maxsize:
        keep = {
            p
            for p, _ in iter_until_total(files, maxsize)
        }
        for f, _ in files:
            if f not in keep:
                print(f"Deleting {f}")
                f.unlink()


def main():
    # Load config
    with open('.offline-radio.toml', 'rt') as cf:
        config = toml.load(cf)

    # Scan feeds and download new items
    with SeenList() as sl:
        for url in mk_feed_urls(config['sub']):
            feed = feedparser.parse(url)
            for ent in feed.entries:
                if not sl.has_seen(ent.link):
                    print(f"Downloading {ent['title']} ({ent['link']})", file=sys.stderr)
                    # XXX: How do direct and non-service links work?
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

    # Now apply limits
    # First, delete everything too old
    maxdays = config.get('limits', {}).get('age', None)
    if maxdays is not None:
        remove_old(maxdays * 86_400)

    # Now scan for filesize
    maxsize = config.get('limits', {}).get('size', None)
    if maxsize is not None:
        remove_big(maxsize)
