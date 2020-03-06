import base64
import importlib.resources
import mimetypes
import os
import subprocess
import tempfile

import webview
import xattr


class JsApi:
    def read_track_data(self):
        rv = []
        for file in os.listdir():
            if file.startswith('.'):
                continue
            if not os.path.isfile(file):
                continue
            x = xattr.xattr(file)

            def g(name):
                try:
                    return x.get(name).decode('utf-8')
                except (OSError, IOError):
                    pass

            rv.append({
                'filename': file,
                'title': g('user.dublincore.title'),
                'channel': g('user.dublincore.contributor'),
                'desc': g('user.dublincore.description'),
            })
        return rv

    def read_track_contents(self, filename):
        """
        Returns track data as a data URL
        """
        if '/' in filename:
            raise ValueError("Other directories not allowed")

        ctype = mimetypes.guess_type(filename)[0] or 'application/octet-stream'
        with tempfile.NamedTemporaryFile(suffix='.mp3') as ntf:
            subprocess.run(
                ['ffmpeg', '-y', '-loglevel', 'warning', '-i', filename, ntf.name],
                check=True, stdin=subprocess.DEVNULL,
            )
            data = ntf.read()

        url = f"data:{ctype};base64,{base64.b64encode(data).decode('ascii')}"
        print(f"Made url {len(url)}")
        return url


def start():
    webview.create_window(
        'Radio',
        html=importlib.resources.read_text('offline_radio', 'page.html'),
        js_api=JsApi(),
    )
    webview.start(debug=True)


if __name__ == '__main__':
    start()
