#  framex0r
#  By: Evan Jensen (evanmj@gmail.com)
#
#  TODO: setting a channel from any screen should bring you back to the screen you were on (see /arm request return)
#
#
#  TODO: changing channel works, but the loop still goes, which is temporary anyway, but...
#        basically it tries to finish showing the folder with the new channel being passed to the client,
#        but with the old file name.
#
#  TODO: Verify files found are valid image extension and maybe check file sigs
#
#  TODO: Push separate images to all connected clients -  client allocation record needs tracked and reset in non-windowed channels.
#
#  TODO: (idea)- index page is current channel and channel flip page (next / prev)
#
#  TODO: Finish EXIF overlay in client.html / client.css
#
#  TODO: Status page that shows all connected clients (rooms)
#
#  TODO: Add sys info to respoinse of 'whos_there' to make it useful again... maybe
#
#  TODO: TEST DEALOCATION.
#
#  TODO: ADD ROOM TO SOCKET MESSAGES NOW THAT THEY ARE ROOM SPECIFIC.
#

from gevent import monkey
monkey.patch_all()

import time, os
from threading import Thread
from flask import Flask, render_template, session, request, url_for, redirect, g, flash
from flask.ext.socketio import SocketIO, emit, join_room, leave_room
import exifread

app = Flask(__name__)
app.debug = True
app.config['SECRET_KEY'] = 'adajjsjdkjljskjflas444'
socketio = SocketIO(app)
thread = None

photo_lib_path = './static/library/' #do not change
library_paths = {}
current_channel = 'landscape' #temporary until exists a 'global' channel.
current_clients = []          #list of clients queried
image_show_time_s = 10

def launch_bgthread():
    global thread
    if thread is None:
        thread = Thread(target=background_thread)
        thread.start()


def background_thread():
    """Example of how to send server generated events to clients."""
    global current_channel  #use global current_channel
    global image_show_time_s #use global sleep time between images.
    library_paths = get_directory_structure(photo_lib_path) 
    previous_allocations = {}
    count = 1
    while True:
    
        #get_attached_clients()   # No longer needed, rooms work better.

        previous_allocations = library_paths # store old path data so we can re-populate our allocation record.
        
        #read fresh copy of file paths off disk
        library_paths = get_directory_structure(photo_lib_path) 
    
        #print current channel each loop, but only if we have clients connected.    
        if socketio.rooms:        
            print 'Using images from channel: ' + current_channel

        #re-populate our allocation records so we show new images first and don't duplicate.
        #The images need to be in a round robin, but don't forget the data is dynmaic! A new image can hop in at any loop.
        for photo_name in library_paths[current_channel]:
            if previous_allocations[current_channel][photo_name] == 'allocated':
                library_paths[current_channel][photo_name] = 'allocated'



        #find out if this is a window channel or not... store it here.
        window_channel = False  

        #loop through namespaces, there should just be one for now, but we have to dig into it
        for namespace, roomdict in socketio.rooms.iteritems():

            print 'Active Namespaces: ' + namespace
            #loop through rooms giving each an image.  A 'room' is a connected client or possibly a duplicate client.
            
            #find out if this is a numbered channel or not.  If so, each image has a specific client destination.
            #look at all photo names... 
            for photo_name in library_paths[current_channel]:
                #look at all room names
                for room_name, object in roomdict.iteritems():
                    #does the first N char of the photo name match our room name?
                    if photo_name[:len(str(room_name))] == str(room_name):
                        window_channel = True
                        break #leave loop early, we found what we were looking for.
            if window_channel:
                print "Window Channel Detected: " + current_channel
            else:
                print "Window Channel Not Detected: " + current_channel
            
            #Every room (attached client) needs a photo.  Assign them here.
            for room_name, object in roomdict.iteritems():
                this_room = str(room_name) #convert the tuple to a string for ease of use.
                print 'Room Active: ' + this_room                
                new_url = ''

                # is this a window channel (meaning specific images go to specific monitors)
                if window_channel:
                    #look through all the photos. See if one matches our client name.
                    for photo_name in library_paths[current_channel]:
                        #does the first N char of the photo name match our room name?
                        if photo_name[:len(this_room)] == this_room:
                            #we found a match!
                            print 'Found unique monitor match: Client: ' + this_room + ' matches ' + photo_name
                            new_url = photo_name
                            break # leave loop now that we found a good photo to use.
                    if new_url == '':
                        print 'No matching photo found for client: ' + this_room + ' in window channel: ' + current_channel
                        #todo: if we made it here, some client has a photo for it, but not this one. show blank or logo, etc.
                        
                # not a window channel, image free for all.
                else:
                    #look through all the photos. See if one matches our client name.
                    for photo_name in library_paths[current_channel]:
                
                        #look for a photo that is not already displayed.                
                        if library_paths[current_channel][photo_name] == None:
                            #we found a match!
                            print 'Photo: ' + photo_name + ' was not yet displayed: Allocating to client: ' + this_room 
                            new_url = photo_name
                            library_paths[current_channel][photo_name] = 'allocated'
                            break # leave loop now that we found a good photo to use.
                      
                    if new_url == '':
                        #todo: if we made it here, we could not find a photo, but we are not in window mode, so we can start over on the list.
                        print 'Deallocating all images so they can be shown again (looped).'
                        for photo_name in library_paths[current_channel]:
                            #steal first photo in list, deallocate the rest.
                            if new_url == '':
                                new_url = photo_name
                                library_paths[current_channel][photo_name] = 'allocated'
                                continue #next element.
                            #we stole the first photo in the list to show, now set the rest back to none.
                            library_paths[current_channel][photo_name] = None

                #hopefully we have a URL by now...     
                if new_url != '':

                    #build exif data caption, and determine H or L orientation from exif (if possible).
                    new_caption = build_exif_string('static/library/' + current_channel + '/' + photo_name)
                    photo_orientation = get_exif_orientation('static/library/' + current_channel + '/' + photo_name)

                    #Note:  Display the last loaded image.  If one was not loaded before (first iteration), it'll still load and display, it just might be ugly.
                    socketio.emit('load_image_url',
                        {'data': new_url, 'current_channel': current_channel, 
                        'caption': new_caption, 'photo_orientation': photo_orientation}, 
                        namespace='/test',
                        room=room_name)  # send url of photo to client, current channel, exif info, and orientation.

                    print 'Cmd sent to load image:    ' + new_url + ' of channel: ' + current_channel

                    socketio.emit('display_image',
                        {'data': new_url, 'current_channel': current_channel, 'caption': new_caption},
                        namespace='/test',
                        room=room_name)

                    print 'Cmd sent to display image: ' + new_url + ' of channel: ' + current_channel
                        
                else:
                    print 'Error: No url assigned to room: ' + room_name + ' by the end of the loop. Channel: ' + current_channel



        #sleep time between image transitions.  This will eventually be a parameter... probably.
        slept_count = 0 #zero out counter.
        running_channel = current_channel # store current channel as running, current_channel may change while we are waiting to show the next image.
        #ignore wait timer if 0 clients are connected!
        if socketio.rooms:
            #user can change the channel at any time, so we basically check every 500ms or so to see if it changed to give better respose on channel change.
            while current_channel == running_channel and slept_count < (image_show_time_s * 2): 
                time.sleep(0.5) #sleep 500ms
                slept_count += 1 #keep track.
        else:
            time.sleep(0.5)    




def build_exif_string(img_path):
    exif_string = ''
    f = open(img_path, 'rb')
    # Return Exif tags
    tags = exifread.process_file(f, details=False)
    if 'Image Model' in tags.keys():
        exif_string += str(tags['Image Model']) + ' | ' 
    if 'EXIF FocalLength' in tags.keys():
        exif_string += str(tags['EXIF FocalLength']) + 'mm '
    if 'EXIF FNumber' in tags.keys():
        exif_string += 'F' + str(tags['EXIF FNumber']) + ' '
    if 'EXIF ExposureTime' in tags.keys():
        exif_string += str(tags['EXIF ExposureTime']) + '\" '
    if 'EXIF ISOSpeedRatings' in tags.keys():
        exif_string += 'ISO' + str(tags['EXIF ISOSpeedRatings']) + ' | '
    if 'EXIF DateTimeDigitized' in tags.keys():
        exif_string += str(tags['EXIF DateTimeDigitized']) + ' | '
    if 'Image Artist' in tags.keys():
        exif_string += str(tags['Image Artist'])
    return exif_string
    
    
def get_exif_orientation(img_path):
    orientation_string = ''
    f = open(img_path, 'rb')    
    tags = exifread.process_file(f, details = False)
    if 'Image Orientation' in tags.keys():
        orientation_string = (str(tags['Image Orientation'])[:1]).upper()
    else:
        orientation_string = 'H'  # Safe to default to H.
    return orientation_string    

#DEPRECATED by socketio.rooms functionality
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

#handle 404 nicely
@app.errorhandler(404)
def internal_error(error):
    return render_template('404.html',library_paths=library_paths,current_channel=current_channel), 404

#handle 500 nicely
@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('500.html',library_paths=library_paths,current_channel=current_channel), 500

@app.route('/')
def index():
    #launch background thread if not already running.
    global current_channel
    launch_bgthread()
    library_paths = get_directory_structure(photo_lib_path)  # create dictionary
    return render_template('index.html',library_paths=library_paths,current_channel=current_channel)

@app.route('/client/<client_id>')
def client_access(client_id):
    global current_channel
    #launch background thread if not already running.
    launch_bgthread()
    return render_template('client.html',client_id=client_id)

@app.route('/become_client')
def become_client():
    """
    Quick link for uers to make a client without needing to know anything about the urls, etc.
    """
    new_room = 0  #start at 0 and add 1 to get the new room number for the client-to-be
    if socketio.rooms:
        for namespace, roomdict in socketio.rooms.iteritems():
            for room_name, object in roomdict.iteritems():
# TODO: BUG HERE.  doesn't work, but also should fill in starting at 1 unless taken.  for loop 1..infinity
#and look to see if there is a room called that, if not use it, and break/continue the loop.
                if int(room_name) > new_room:
                    print 'setting new_room = ' + str(room_name) + ' plus one.'
                    new_room = int(room_name) + 1 # increment one above highest number found. (rooms don't have to be numbers, but I recommend it.
    else:
        #no rooms to look through, default to 1.
        new_room = 1
    print "Become Client: Giving new client-to-be room url: /client/" + str(new_room)
    return redirect('client/' + str(new_room))   

@app.route('/status')
def status():
    return redirect(url_for('index'))    

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
    flash('Channel: ' + new_channel + ' set.')
    return redirect(url_for('channels'))  #return page the user wanted, or index if none reqd.



#DEPRECATED by socketio.rooms functionality
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
