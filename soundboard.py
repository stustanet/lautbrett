#!venv/bin/python3

from flask import Flask, render_template, abort, Response, send_from_directory, request
import os
import gevent
from gevent.queue import Queue
from gevent.wsgi import WSGIServer
import time
import subprocess

app = Flask(__name__)
PATH = "static"
DEBUG = True
min_delay_s = 0.25;




subscriptions = []
last_call = time.time();

@app.route('/set/<sound_id>')
def set(sound_id):
    """
    set the file id to play and is called by bernd
    it will send a message to all subscribed queues
    """
    global last_call
    global min_delay_s
    now = time.time()

    if (now - last_call) < min_delay_s:
        return 'fu', 200
    last_call = now

    def notify():
        global subscriptions
        for sub in subscriptions[:]:
            sub.put(find_file(sound_id))
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
                sound = q.get()
                yield 'data: {}\n\n'.format(sound)
        except GeneratorExit:
            subscriptions.remove(q)
    return Response(gen(), mimetype="text/event-stream")


@app.route('/audio/<path:path>')
def send_audio(path):
    """
    static file handler to serve the audio data
    """
    print(path)
    return send_from_directory(PATH, path)


def find_file(sound_id):
    """
    find the file in PATH based on the id
    """
    for f in os.listdir(PATH):
        f = f.strip("\"\'")
        if f.startswith("{} ".format(sound_id)):
            return f
    return abort(404)


@app.route('/speak',methods=['POST', 'GET'])
def send_espeak_file():
    # Trigger espeak to speak
    if request.method == 'POST':
        phrase = request.form['phrase']
        voice = request.form['voice'] if 'voice' in request.form else 'de'
    elif request.method == 'GET':
        phrase = request.args.get('phrase', '')
        voice = 'de'

    say_file = os.path.join(os.path.dirname(os.path.realpath(__file__)), 
            "static", "audio", "say.mp3")
    tmp_file = '/tmp/speak.wav'

    if os.path.exists(tmp_file):
        os.unlink(tmp_file)
    # -w: wav file
    # -v: voice file
    subprocess.run(['/usr/bin/espeak', '-w', tmp_file, '-v', voice,
        phrase])

    # -y: always override
    # -i: input file
    subprocess.run(['/usr/bin/ffmpeg', '-y', '-i', tmp_file, '-codec:a', 'libmp3lame', say_file])
    os.unlink('/tmp/speak.wav')

    def notify():
        global subscriptions
        for sub in subscriptions[:]:
            sub.put(say_file)
    gevent.spawn(notify)

    return 'thx', 200

@app.route('/soundboard')
def sound ():
    files = []
    for f in os.listdir(PATH):
        f = f.strip("\"\'")
        f = f.split(' ', 1)
        files.append({'name':f[1], 'id':f[0]})
    return render_template('soundboard.html', buttons=files)


@app.route('/')
def hello():
    """
    serve the default page, which is loaded by the widget
    """
    return render_template('play.html')


if __name__ == '__main__':
    if DEBUG:
        app.debug = True
        app.host = '0.0.0.0'
        server = WSGIServer(("", 5000), app)
        server.serve_forever()
    else:
        app.debug = False
        app.host = '127.0.0.1'
        server = WSGIServer(("", 8081), app)
        server.serve_forever()

