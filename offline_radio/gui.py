import logging
import os
import random
import threading
import urllib.parse

import flask
import pause
import webview
import xattr

from .cli import main as run_downloader

api = flask.Flask(__name__)


@api.route('/next')
def get_next_track():
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

    return flask.jsonify({
        'filename': urllib.parse.urljoin(
            flask.request.base_url,
            f"/media/{file}"
        ),
        'title': g('user.dublincore.title'),
        'channel': g('user.dublincore.contributor'),
        'desc': g('user.dublincore.description'),
    })


def scanner_thread():
    while True:
        run_downloader()
        pause.hours(12 * random.random())


def start():
    # threading.Thread(target=scanner_thread, daemon=True).start()

    from whitenoise import WhiteNoise
    from webview.wsgi import do_404
    table = webview.Routing({
        '/': webview.StaticResources('offline_radio.static'),
        '/api': api,
        '/media': webview.StaticFiles(os.getcwd()),
        # '/media': WhiteNoise(do_404, root=os.getcwd()),
    })
    webview.create_window(
        'Radio',
        table,
        width=500, height=200,
    )
    webview.start(debug=True)


if __name__ == '__main__':
    logging.basicConfig(level='DEBUG')
    start()
