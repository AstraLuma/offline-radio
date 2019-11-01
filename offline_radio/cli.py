from contextlib import contextmanager
from pathlib import Path
import subprocess
import sys
import time

import feedparser
import toml
import xattr


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


def iter_media_dir():
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
                self._urls = [
                    l.strip()
                    for l in f
                ]
        except FileNotFoundError:
            self._urls = set()

        # Attempt to load from xattrs
        # We can't rely on this, but there's gaps in the other algorithms
        for p in iter_media_dir():
            try:
                u = xattr.getxattr(str(p), "user.xdg.referrer.url").decode('utf-8')
            except OSError:
                pass
            else:
                if u not in self._urls:
                    self._urls.append(u)

        self._seen = set()

        return self

    def __exit__(self, type, value, traceback):
        with open('.offline-radio.state', 'wt') as f:
            # Only write the last 1000, as a pruning meassure
            # XXX: This will cause problems if there's enough feeds to have
            # 1000 active
            for u in self._urls[-1000:]:
                print(u, file=f)
            for u in self._seen:
                print(u, file=f)

    @contextmanager
    def handle_url(self, url):
        try:
            yield url in self._urls or url in self._seen
        except Exception:
            raise
        else:
            self._seen.add(url)


def remove_old(maxage):
    """
    Remove files that are too old
    """
    mintime = time.time() + maxage
    for f in iter_media_dir():
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
        for p in iter_media_dir()
    ], key=lambda i: pathtime(i[0]))
    totalsize = sum(s for _, s in files)
    if totalsize > maxsize:
        keep = {
            p
            for p, _ in iter_until_total(reversed(files), maxsize)
        }
        for f, _ in files:
            if f not in keep:
                print(f"Deleting {f}")
                f.unlink()


def iter_media_links(feeds):
    for url in feeds:
        feed = feedparser.parse(url)
        for ent in feed.entries:
            yield ent['title'], ent['link']


def main():
    # Load config
    with open('.offline-radio.toml', 'rt') as cf:
        config = toml.load(cf)

    # Scan feeds and download new items
    with SeenList() as sl:
        for title, url in iter_media_links(mk_feed_urls(config['sub'])):
            try:
                with sl.handle_url(url) as has_seen:
                    if not has_seen:
                        print(f"Downloading {title} ({url})", file=sys.stderr)
                        # XXX: How do direct and non-service links work?
                        subprocess.run(
                            [
                                'youtube-dl', '--add-metadata', '--xattrs',
                                '--match-filter', '!is_live',
                                '--extract-audio', '--audio-quality', '0',
                                # TODO: Pass maxage args
                                '--quiet',
                                url,
                            ],
                            check=True,
                        )
            except subprocess.CalledProcessError:
                print(f"Error downloading {title} ({url})", file=sys.stderr)

    # Now apply limits
    # First, delete everything too old
    maxdays = config.get('limits', {}).get('age', None)
    if maxdays is not None:
        remove_old(maxdays * 86_400)

    # Now scan for filesize
    maxsize = config.get('limits', {}).get('size', None)
    if maxsize is not None:
        remove_big(maxsize)
