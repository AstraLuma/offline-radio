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
    def get_next_track(self):
        file = random.choice([
            file
            for file in os.listdir()
            if not file.startswith('.') and os.path.isfile(file)
        ])

        x = xattr.xattr(file)

        def g(name):
            try:
                return x.get(name).decode('utf-8')
            except (OSError, IOError):
                pass

        return {
            'filename': file,
            'title': g('user.dublincore.title'),
            'channel': g('user.dublincore.contributor'),
            'desc': g('user.dublincore.description'),
        }

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
