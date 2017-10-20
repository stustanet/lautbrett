#!venv/bin/python3

from flask import Flask, render_template, abort, Response, send_from_directory
import os
import gevent
from gevent.queue import Queue
from gevent.wsgi import WSGIServer

app = Flask(__name__)

PATH = "static"

last = None
subscriptions = []

@app.route('/set/<id>')
def set(id):
    """
    set the file id to play and is called by bernd
    it will send a message to all subscribed queues
    """
    last = id
    def notify():
        global subscriptions
        for sub in subscriptions[:]:
            sub.put(id)
    gevent.spawn(notify)

    return 'thx', 200


@app.route('/gen/')
def wait_for_events():
    def gen():
        """
        this url is called by the java script periodically
        and returns the current file path to play and opens a channel to
        continue providing updates
        """
        q = Queue()
        global subscriptions
        subscriptions.append(q)

        try:
            while True:
                id = q.get()
                yield 'data: {}/{}\n\n'.format( PATH, find_file(id))
        except GeneratorExit:
            subscriptions.remove(q)
    return Response(gen(), mimetype="text/event-stream")

@app.route('/audio/<path:path>')
def send_audio(path):
    """
    static file handler to serve the audio data
    """
    print(path)
    return send_from_directory('audio', path)


def find_file(id):
    """
    find the file in PATH based on the id
    """
    for f in os.listdir('audio'):
        f = f.strip("\"").strip("\'")
        if f.startswith(id):
            return f

    return abort(404)


@app.route('/')
def hello(name=None):
    """
    serve the default page, which is loaded by the widget
    """
    return render_template('soundboard.html', name=name)


if __name__ == '__main__':
#    app.run(host='0.0.0.0', debug=True)
    app.debug=True
    app.host='0.0.0.0'
    server = WSGIServer(("", 5000), app)
    server.serve_forever()
