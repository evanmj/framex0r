#
#  By: Evan Jensen (evanmj@gmail.com)
#
#
#  TODO: changing channel works, but the loop still goes, which is temporary anyway, but...
#        basically it tries to finish showing the folder with the new channel being passed to the client,
#        but with the old file name.
#
#  TODO: Verify files found are valid image extension and maybe check file sigs
#
#  TODO: Client list populated, but never depopulated.
#

from gevent import monkey
monkey.patch_all()

import time, os
from threading import Thread
from flask import Flask, render_template, session, request, url_for, redirect, g
from flask.ext.socketio import SocketIO, emit, join_room, leave_room
import base64

app = Flask(__name__)
app.debug = True
app.config['SECRET_KEY'] = 'adajjsjdkjljskjflas444'
socketio = SocketIO(app)
thread = None

photo_lib_path = './static/library/' #do not change
library_paths = {}
current_channel = 'landscape' #temporary until exists a 'global' channel.
current_clients = []          #list of clients queried

def launch_bgthread():
    global thread
    if thread is None:
        thread = Thread(target=background_thread)
        thread.start()


def background_thread():
    """Example of how to send server generated events to clients."""
    global current_channel  #use global current_channel

    count = 1
    while True:
    
        get_attached_clients()

        library_paths = get_directory_structure(photo_lib_path)  # create dictionary of photos

        #loop the current channel for a photo to show
        print 'Using images from channel: ' + current_channel

        for photo_name in library_paths[current_channel]:
            
            print photo_name

            new_url = photo_name  # '/static/library' path will be added on client html side

            socketio.emit('load_image_url',
                          {'data': new_url, 'current_channel': current_channel},
                          namespace='/test')  # send url of photo to client

            print 'Cmd sent to load image:    ' + photo_name + ' of channel: ' + current_channel

            time.sleep(3)

            socketio.emit('display_image',
                           {'data': True},
                           namespace='/test')

            print 'Cmd sent to display image: ' + photo_name + ' of channel: ' + current_channel

            

def get_attached_clients():
    print 'Sending Client \'Who\'s There\'?'
    socketio.emit('whos_there',
                 namespace='/test')

def get_directory_structure(rootdir):
    """
    Creates a nested dictionary that represents the folder structure of rootdir
    """
    dir = {}
    rootdir = rootdir.rstrip(os.sep)
    start = rootdir.rfind(os.sep) + 1
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
    global current_channel
    #launch background thread if not already running.
    launch_bgthread()
    return render_template('client.html',client_id=client_id)


#@app.route('/client_new')
#def client_new():
    #TODO: Make this function grab the next open client number
#    return redirect(url_for('/client')+'/1')

@app.route('/channels')
def channels():
    library_paths = get_directory_structure(photo_lib_path)  # create dictionary
    return render_template('channels.html',library_paths=library_paths)    

@app.route('/setchannel/<new_channel>')
def new_channel(new_channel):
    global current_channel 
    # TODO: Validate!!!
    print 'changing channel from: ' + current_channel + ' to: ' + new_channel
    current_channel = new_channel
    return redirect(url_for('channels'))  #return page the user wanted, or index if none reqd.

# watch for responses to our 'whos_there' request.  They will provide their client ID.
@socketio.on('im_here', namespace='/test')
def im_here(message):
    global current_clients
    # add client to the list if it is not already there.
    if current_clients.count(message['data']) == 0:
        current_clients.append(message['data'])
    print 'Current Client List:  ' + str([x.encode('ascii') for x in current_clients])
    print 'Client Reported Back: ' + message['data']






#@socketio.on('my event', namespace='/test')
#def test_message(message):
#    session['receive_count'] = session.get('receive_count', 0) + 1
#    emit('my response',
#         {'data': message['data'], 'count': session['receive_count']})


#@socketio.on('my broadcast event', namespace='/test')
#def test_message(message):
#    session['receive_count'] = session.get('receive_count', 0) + 1
#    emit('my response',
#         {'data': message['data'], 'count': session['receive_count']},
#         broadcast=True)

#when a client joins it's image listening room.  One client is typical for a room, but duplicate clients is fine.
@socketio.on('join', namespace='/test')
def join(message):
    join_room(message['room'])  #join the room 'client_id' as sent from the client.
    emit('room_joined',
         {'data': 'Successfully Joined Room: ' + ', '.join(request.namespace.rooms)})



#@socketio.on('leave', namespace='/test')
#def leave(message):
#    leave_room(message['room'])
#    session['receive_count'] = session.get('receive_count', 0) + 1
#    emit('my response',
#         {'data': 'In rooms: ' + ', '.join(request.namespace.rooms),
#          'count': session['receive_count']})


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
