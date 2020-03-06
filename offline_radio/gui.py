import base64
import importlib.resources
import mimetypes
import os
import random
import subprocess
import tempfile
import threading

import pause
import webview
import xattr

from .cli import main as run_downloader


class JsApi:
    def _select_next_track(self):
        return random.choice([
            file
            for file in os.listdir()
            if not file.startswith('.') and os.path.isfile(file)
        ])

    def _build_metadata(self, filename):
        x = xattr.xattr(filename)

        def g(name):
            try:
                return x.get(name).decode('utf-8')
            except (OSError, IOError):
                pass

        return {
            'filename': filename,
            'title': g('user.dublincore.title'),
            'channel': g('user.dublincore.contributor'),
            'desc': g('user.dublincore.description'),
        }

    def get_next_track(self):
        file = self._select_next_track()
        return self._build_metadata(file)

    def read_track_contents(self, filename):
        """
        Returns track data as a data URL
        """
        if '/' in filename:
            raise ValueError("Other directories not allowed")

        with tempfile.NamedTemporaryFile(suffix='.mp3') as ntf:
            subprocess.run(
                ['ffmpeg', '-y', '-loglevel', 'warning', '-i', filename, ntf.name],
                check=True, stdin=subprocess.DEVNULL,
            )
            data = ntf.read()
            ctype = mimetypes.guess_type(ntf.name)[0] or 'application/octet-stream'

        return f"data:{ctype};base64,{base64.b64encode(data).decode('ascii')}"

    _process = None
    _buffer = None

    def track_open(self):
        """
        Opens the next track.

        Returns the metadata
        """
        # Clean up any existing stuff
        if self._process is not None:
            self._process.terminate()
            self._process = None

        if self._buffer is not None:
            self._buffer.close()
            self._buffer = None

        filename = self._select_next_track()
        metadata = self._build_metadata(filename)

        metadata['mimetype'] = 'audio/mpeg'

        # TODO: Stream
        self._buffer = tempfile.NamedTemporaryFile(suffix='.mp3')
        self._process = subprocess.run(
            ['ffmpeg', '-y', '-loglevel', 'warning', '-i', filename, self._buffer.name],
            check=True, stdin=subprocess.DEVNULL,
        )

        return metadata

    def track_read(self, amount):
        """
        Reads up to amount of data from the track and returns it. May return less.

        Data is base64 encoded.

        Returns {"eof": true} when finished.
        """
        data = self._buffer.read(amount)
        if not data:  # FIXME: Handle blocking vs non-blocking
            return {'eof': True}
        return base64.b64encode(data).decode('ascii')


def scanner_thread():
    while True:
        run_downloader()
        pause.hours(12 * random.random())


def start():
    threading.Thread(target=scanner_thread, daemon=True).start()
    webview.create_window(
        'Radio',
        html=importlib.resources.read_text('offline_radio', 'page.html'),
        js_api=JsApi(),
        width=500, height=200,
    )
    webview.start(debug=True)


if __name__ == '__main__':
    start()
