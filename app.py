from gevent import monkey
monkey.patch_all()

import time, os
from threading import Thread
from flask import Flask, render_template, session, request, url_for
from flask.ext.socketio import SocketIO, emit, join_room, leave_room
import base64

app = Flask(__name__)
app.debug = True
app.config['SECRET_KEY'] = 'adajjsjdkjljskjflas444'
socketio = SocketIO(app)
thread = None

photo_lib_path = './static/library/'
library_paths = {}

def launch_bgthread():
    global thread
    if thread is None:
        thread = Thread(target=background_thread)
        thread.start()


def background_thread():
    """Example of how to send server generated events to clients."""
    count = 3
    while True:
        count += 1

        #display loaded image

        #load new image.
#        imgpath = "./static/" + str(count) + ".png"
#        print "Showing: " + imgpath
#        with open(imgpath, "rb") as image_file:  # grab image off disk
#            encoded_string = base64.b64encode(image_file.read()) # encode image to base64 string

#        socketio.emit('load_image',
#                      {'data': encoded_string},
#                      namespace='/test')  # send string to client for it to show

        new_url = str(count) + ".png"  # 'static' folder will be added on client html side

        socketio.emit('load_image_url',
                      {'data': new_url},
                      namespace='/test')  # send url of photo to client

        print "done loading"

        time.sleep(10)

        print "displaying..."
        socketio.emit('display_image',
                      {'data': True},
                      namespace='/test')


        print "done displaying"
        if count == 6:
            count = 3


def get_directory_structure(rootdir):
    """
    Creates a nested dictionary that represents the folder structure of rootdir
    """
    dir = {}
    print rootdir
    rootdir = rootdir.rstrip(os.sep)
    print rootdir
    start = rootdir.rfind(os.sep) + 1
    print start 
    for path, dirs, files in os.walk(rootdir):
        folders =path[start:].split(os.sep)
        #keep '.' folder from stinking up our dict
        if folders <> ['library']:
            subdir = dict.fromkeys(files)
            parent = reduce(dict.get, folders[:0], dir)
            parent[folders[-1]] = subdir
    return dir



@app.route('/')
def index():
    #launch background thread if not already running.
    launch_bgthread()
    #library_paths = get_directory_structure(photo_lib_path)  # create dictionary
    #return page
    return render_template('index.html')

@app.route('/client/<client_id>')
def client_access(client_id):
    #launch background thread if not already running.
    launch_bgthread()
    return render_template('client.html',client_id=client_id)

@app.route('/channels')
def channels():
    library_paths = get_directory_structure(photo_lib_path)  # create dictionary
    return render_template('channels.html',library_paths=library_paths)    


@socketio.on('my event', namespace='/test')
def test_message(message):
    session['receive_count'] = session.get('receive_count', 0) + 1
    emit('my response',
         {'data': message['data'], 'count': session['receive_count']})


@socketio.on('my broadcast event', namespace='/test')
def test_message(message):
    session['receive_count'] = session.get('receive_count', 0) + 1
    emit('my response',
         {'data': message['data'], 'count': session['receive_count']},
         broadcast=True)


@socketio.on('join', namespace='/test')
def join(message):
    join_room(message['room'])
    session['receive_count'] = session.get('receive_count', 0) + 1
    emit('my response',
         {'data': 'In rooms: ' + ', '.join(request.namespace.rooms),
          'count': session['receive_count']})


@socketio.on('leave', namespace='/test')
def leave(message):
    leave_room(message['room'])
    session['receive_count'] = session.get('receive_count', 0) + 1
    emit('my response',
         {'data': 'In rooms: ' + ', '.join(request.namespace.rooms),
          'count': session['receive_count']})


@socketio.on('my room event', namespace='/test')
def send_room_message(message):
    session['receive_count'] = session.get('receive_count', 0) + 1
    emit('my response',
         {'data': message['data'], 'count': session['receive_count']},
         room=message['room'])


@socketio.on('connect', namespace='/test')
def test_connect():
    emit('my response', {'data': 'Connected', 'count': 0})


@socketio.on('disconnect', namespace='/test')
def test_disconnect():
    print('Client disconnected')

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=4000)
