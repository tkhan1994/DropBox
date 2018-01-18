import sys
import argparse
import socket
import os
import time
import json
import shutil

##############################################
def add_file(client_dir, filename, data, select_sync):
	not_selected_files = []
	if select_sync == True:
		path = os.getcwd() + '/' + 'other' + '/' + 'selective.txt'
		with open(path, 'r') as selectfile:
			for line in selectfile:
				not_selected_files.append(line.rstrip())
			selectfile.close()
	if filename not in not_selected_files: # If file is synched in selective sync
		path = os.path.join(client_dir, filename)
		file = open(path, 'w')
		file.write(data)
		file.close()

def delete_file(client_dir, filename):
	path = os.path.join(client_dir, filename)
	if os.path.exists(path):
		os.remove(path)

def selective_sync(conn, status, directory, relogin): # CATERS FOR EVERYTHING
	selected = []
	not_selected = []
	if status == 'olduser':
		if relogin == 0:
			print('Press 1 for selective Sync.')
			print('Press any for normal Sync.')
			sync = input()
		elif relogin == 1: # USER SELECTED SELECTIVE SYNC ON FIRST LOGIN
			sync = '1'
		elif relogin == 2: # USER SELECTED NORMAL SELECT ON FIRST LOGIN
			sync = 2
		if sync == '1':
			send_sync(conn, 'selective')
			files = get_message(conn)['names'] # TAG RFN
			if relogin == 0:
				for i in range(0, len(files)):
					print('Filename :: ', files[i])
					sync = input('Do you want this file to be selected ? (y/n) :: ')
					if sync == 'y':
						selected.append(files[i])
					else:
						not_selected.append(files[i])
			if relogin == 1:
				selected = get_file_list(directory)
			send_file_names(conn, selected) # TAG SFN
			for file in selected:
				msg = get_message(conn)
				add_file(directory, msg['filename'], msg['data'], False)
			if len(not_selected) > 0:
				path = os.getcwd() + '/' + 'other'
				os.mkdir(path)
				file = open(path + '/' + 'selective.txt', 'w')
				for files in not_selected:
					file.write(str(files) + "\n")
		else:
			send_sync(conn, 'normal')
			files = get_message(conn)['names']	# TAG RFN
			for file in files:
				msg = get_message(conn)
				add_file(directory, msg['filename'], msg['data'], False)



def get_server_file_list(conn):
	msg = {
		'type': 'files'
	}
	send_msg(conn, msg)
	msg = get_message(conn)['names']
	return msg	

def send_username(conn, username):
	msg = {
		'type' : 'username',
		'username' : username
	}
	send_msg(conn, msg)

def send_sync(conn, sync_type):
	msg = {
		'type' : 'sync',
		'sync_type' : sync_type
	}
	send_msg(conn, msg)

def send_file_names(conn, data):
	msg = {
		'type' : 'file_names',
		'names' : data
	}
	send_msg(conn, msg)

def send_logout(conn):
	msg = {
		'type' : 'logout'
	}
	send_msg(conn, msg)

def get_message(conn):
	length_str = b''
	char = conn.recv(1)
	while char != b'\n':
		length_str += char
		char = conn.recv(1)
	total = int(length_str)
	off = 0
	msg = b''
	while off < total:
		temp = conn.recv(total - off)
		off = off + len(temp)
		msg = msg + temp
	return json.loads(msg.decode('utf-8'))
##############################################


def send_msg(conn, msg):
	serialized = json.dumps(msg).encode('utf-8')
	length = str(len(serialized)) + '\n'
	length = length.encode('utf-8')
	conn.send(length)
	conn.sendall(serialized)

def get_file_list(client_dir):
	files = os.listdir(client_dir)
	files = [file for file in files if os.path.isfile(os.path.join(client_dir, file))]
	file_list = {}
	for file in files:
		path = os.path.join(client_dir, file)
		mtime = os.path.getmtime(path)
		ctime = os.path.getctime(path)
		file_list[file] = max(ctime, mtime)
	return file_list

def send_new_file(conn, filename, client_dir):
	with open(client_dir + '/' + filename, 'r') as myfile:
		data = myfile.read()
		msg = {
			'type': 'file_add',
			'filename': filename,
			'data': data
		}
		send_msg(conn, msg)

def send_delete_file(conn, filename):
	msg = {
		'type': 'file_delete',
		'filename': filename
	}
	send_msg(conn, msg)

def get_changes(client_dir, last_file_list):
	file_list = get_file_list(client_dir)
	changes = {}
	for filename, mtime in file_list.items():
		if filename not in last_file_list or last_file_list[filename] < mtime:
			changes[filename] = 'file_add'

	for filename, time in last_file_list.items():
		if filename not in file_list:
			changes[filename] = 'file_delete'

	return (changes, file_list)

def get_server_changes(client_dir, last_file_list):
	file_list = get_file_list(client_dir)
	changes = {}
	for filename, mtime in file_list.items():
		if filename not in last_file_list:
			changes[filename] = 'file_delete'

	for filename, time in last_file_list.items():
		if filename not in file_list:
			changes[filename] = 'file_add'

	for filename, mtime in last_file_list.items():
		if filename in file_list and mtime > file_list[filename]:
			changes[filename] = 'file_add'

	return changes


def handle_dir_change(conn, changes, client_dir):
	for filename, change in changes.items():
		if change == 'file_add':
			print('new file added ', filename)
			send_new_file(conn, filename, client_dir)
		elif change == 'file_delete':
			print('file deleted ', filename)
			send_delete_file(conn, filename)

def perfect_mirror(conn, changes, client_dir, select_sync):
	for filename, change in changes.items():
		if change == 'file_add':
			send_file_names(conn, filename) # send the name to server that I want this file
			msg = get_message(conn) # Recieve the file from the server
			add_file(client_dir, filename, msg['data'], select_sync) # Add that file to the user directory
		elif change == 'file_delete':
			delete_file(client_dir, filename)

def read_offline_changes(path):
	list_to_return = {}
	with open(path, 'r') as offline_changes_file:
		for line in offline_changes_file:
			line = line.rstrip()
			contents = line.split(' ')
			filename = contents[0]
			max_mtime_ctime = contents[1]
			list_to_return[filename] = float(max_mtime_ctime)
		offline_changes_file.close()
	return list_to_return


def watch_dir(conn, client_dir, handler):
	#Calculate Offline changes
	select_sync = False
	changes_offline = {}
	if os.path.exists(os.getcwd() + '/' + 'offline.txt'):
		last_logout = read_offline_changes(os.getcwd() + '/' + 'offline.txt')
		changes_offline, current_list = get_changes(client_dir, last_logout)
		if changes_offline:
			os.mkdir(client_dir + '/' + 'temp')
			for filename, change in changes_offline.items():
				if change != 'file_delete':
					shutil.copy(client_dir + '/' + filename, client_dir + '/' + 'temp')
	#Pull Updates From Server
	get_user_status = get_message(conn)['user_status'] # TAG GUS
	if not os.path.exists(client_dir): # If Client is using this PC for the first time
		os.mkdir(client_dir)
		selective_sync(conn, get_user_status, client_dir, 0)
	else:
		if os.path.exists(os.getcwd() + '/' + 'other' + '/' + 'selective.txt'):
			selective_sync(conn, get_user_status, client_dir, 1)
			select_sync = True
		else:
			selective_sync(conn, get_user_status, client_dir, 2)
	last_file_list = get_file_list(client_dir)
	#Push Offline Changes
	if os.path.exists(client_dir + '/' + 'temp'):
		for filename,change in changes_offline.items():
			if change != 'file_delete':
				shutil.copy(client_dir + '/' + 'temp' + '/' + filename, client_dir)
		handler(conn, changes_offline, client_dir)
		shutil.rmtree(client_dir + '/' + 'temp')
	#Check selective sync
	if os.path.exists(os.getcwd() + '/' + 'other' + '/' + 'selective.txt'):
		select_sync = True
	if get_user_status == 'newuser':
		last_file_list = {}
	#push client offline changes (on logout keep copy on client side than compare on login again) (Later)
	print('Selective Sync Status :: ', select_sync)
	print('Press (Ctrl + C) at anytime to logout.')
	try:
		while True:
			time.sleep(5)
			changes, last_file_list = get_changes(client_dir, last_file_list) # Monitor any changes in the client directory
			handler(conn, changes, client_dir)	# handles those changes accordingly
			server_files = get_server_file_list(conn) # get list of files on server
			changes = get_server_changes(client_dir, server_files) # compare server files and client files
			perfect_mirror(conn, changes, client_dir, select_sync) # If there are any differences resolve them
			last_file_list = get_file_list(client_dir)
	except KeyboardInterrupt:
		send_logout(conn)
		print('\n','client has logged out')
		files_offline = get_file_list(client_dir)
		file = open(os.getcwd() + '/' + 'offline.txt', 'w')
		file.close()
		file = open(os.getcwd() + '/' + 'offline.txt', 'a')
		for files in files_offline:
			file.write(files)
			file.write(' ')
			file.write(str(files_offline[files]))
			file.write('\n')
		file.close()

def client(server_addr, server_port, client_dir, username):
	s = socket.socket()
	s.connect((server_addr, server_port))
	send_username(s, username) # TAG SU
	watch_dir(s, client_dir, handle_dir_change)
	s.close()

if __name__ == "__main__":
	parser = argparse.ArgumentParser()
	parser.add_argument("server_addr", help="Address of the server.")
	parser.add_argument("server_port", type=int, help="Port number the server is listening on.")
	parser.add_argument("username", type=str, help="Username of the client.")
	args = parser.parse_args()
	CLIENT = os.getcwd() + '/' + args.username
	client(args.server_addr, args.server_port, CLIENT, args.username)