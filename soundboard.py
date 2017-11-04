#!venv/bin/python3

from flask import Flask, render_template, abort, Response, send_from_directory, request, after_this_request
import os
import gevent
from gevent.queue import Queue, Empty
from gevent.wsgi import WSGIServer
import time
import subprocess
import random

app = Flask(__name__)
PATH = "static/audio"
DEBUG = False
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
        return 'keep cool', 200
    last_call = now

    def notify():
        global subscriptions
        for sub in subscriptions[:]:
            sub.put(os.path.join(PATH, find_file(sound_id)))
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
                sound = q.get(timeout=120) # Wait for a max. of 120 seconds to clear up the connectioni
                if sound == "kp":
                    yield 'data: {"fname":"kp","connected":"%d"}\n\n'%(len(subscriptions))
                else:
                    yield 'data: {"fname":"%s","connected":"%d"}\n\n'%(
                        sound, len(subscriptions))
        except (GeneratorExit, Empty):
            subscriptions.remove(q)
    r = Response(gen(), mimetype="text/event-stream")
    r.headers['X-Accel-Buffering'] = 'no'
    r.headers['Cache-Control'] = 'no-cache'
    r.headers['Content-Type'] = 'text/event-stream'
    return r

@app.route('/audio/<path:path>')
def send_audio(path):
    """
    static file handler to serve the audio data
    """
    return send_from_directory(PATH, path)



def find_file(sound_id):
    """
    find the file in PATH based on the id
    """

    if len(sound_id) == 1:
        sound_id = "0{}".format(sound_id)

    for f in os.listdir(PATH):
        f = f.strip("\"\'")
        if f.startswith("{} ".format(sound_id)):
            return f
    return abort(404)

@app.route('/speak',methods=['POST', 'GET'])
def send_espeak_file():
    """
    Convert text to speak and store it in /tmp/say.mp3
    """
    # Trigger espeak to speak
    if request.method == 'POST':
        phrase = request.form['phrase']
        voice = request.form['voice'] if 'voice' in request.form else 'de'
    elif request.method == 'GET':
        phrase = request.args.get('phrase', '')
        voice = request.args.get('voice', 'de')

    say_file = '/tmp/say.mp3'
    tmp_file = '/tmp/speak.wav'

    if os.path.exists(tmp_file):
        os.unlink(tmp_file)
    # -w: wav file
    # -v: voice file
    subprocess.run(['/usr/bin/espeak', '-w', tmp_file, '-v', voice,
        phrase])

    # -y: always override
    # -i: input file
    subprocess.run(['/usr/bin/ffmpeg', '-y', '-i', tmp_file, '-codec:a', 'libmp3lame', say_file], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
#    os.unlink('/tmp/speak.wav')
    def notify():
        global subscriptions
        for sub in subscriptions[:]:
            sub.put("/tmpaudio/{}".format(int(random.random() * 100000)))
    gevent.spawn(notify)

    return 'thx', 200


@app.route('/tmpaudio/<rand>')
def tmpaudiohandler(rand):
    """
    Send only the espeak file
    """
    @after_this_request
    def add_header(response):
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        return response
    return send_from_directory("/tmp", "say.mp3", cache_timeout=1)


@app.route('/soundboard')
def sound ():
    """
    display the soundboard
    """
    files = []
    for f in os.listdir(PATH):
        f = f.strip("\"\'")
        f = f.split(' ', 1)
        try:
            int(f[0]) # Skip over all invalid files
            files.append(f[0])
        except ValueError:
            pass

    # Notify all connected users about the newly arrived annoyand
    def notify():
        global subscriptions
        for sub in subscriptions[:]:
            sub.put("kp")
    gevent.spawn(notify)

    return render_template('soundboard.html', buttons=sorted(files, key=int), connected=len(subscriptions))


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

