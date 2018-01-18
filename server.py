import sys
import argparse
import socket
import os
import threading
import json
import time
import shutil

#################################################
def read_share_file(client_dir, filename):
	data = []
	path = os.path.join(client_dir, filename)
	with open(path, 'r') as sharefile:
		for line in sharefile:
			data.append(line.rstrip())
	return data
def send_msg(conn, msg):
	serialized = json.dumps(msg).encode('utf-8')
	length = str(len(serialized)) + '\n'
	length = length.encode('utf-8')
	conn.send(length)
	conn.sendall(serialized)

def send_user_status(conn, status):
	msg = {
		'type' : 'user_status',
		'user_status' : status
	}
	send_msg(conn, msg)

def send_file_names(conn, data):
	msg = {
		'type' : 'file_names',
		'names' : data
	}
	send_msg(conn, msg)

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

###########################################################################
def manage_sharing(sharefile_dropbin_path, old_data, username, first_time):
	old_sharing = 	[]
	new_sharing = 	[]
	additions   = 	[]
	removals    = 	[]
	share_path_server = os.getcwd() + '/' + 'share'

	if first_time == False:
		temp_path = os.getcwd() + '/' + username + '/' + 'temp.dropbin'
		file = open(temp_path, 'w')
		file.write(old_data)
		file.close()
		with open(temp_path, 'r') as myfile:
			for line in myfile:
				line = line.rstrip()
				old_sharing.append(line)
			myfile.close()
			os.remove(temp_path)
	with open(sharefile_dropbin_path, 'r') as myfile:
		for line in myfile:
			line = line.rstrip()
			new_sharing.append(line)
		myfile.close()

	for line in new_sharing:
		if line not in old_sharing:	#FIND ANY NEW ADDITIONS
			additions.append(line)

	for line in old_sharing:
		if line not in new_sharing: #FIND THE REMOVALS
			removals.append(line)

	for line in additions:
		curr_line = line.split(' ')
		file_to_share = curr_line[0]
		file_to_share_path = os.getcwd() + '/' + username + '/' + file_to_share
		users = curr_line[1:]
		for user in users:
			user_share_path_server = share_path_server + '/' + user
			if not os.path.exists(user_share_path_server):
				os.mkdir(user_share_path_server)
			dest_path = os.getcwd() + '/' + user
			shutil.copy(file_to_share_path, dest_path)
			file = open(user_share_path_server + '/' + file_to_share, 'w')
			file.write(username)
			file.close()

	for line in removals:
		curr_line = line.split(' ')
		file_to_remove = curr_line[0]
		users = curr_line[1:]
		for user in users:
			 file_to_remove_path = os.getcwd() + '/' + user + '/' + file_to_remove
			 share_path_server_user = share_path_server + '/' + user + '/' + file_to_remove
			 if os.path.exists(file_to_remove_path):
			 	os.remove(file_to_remove_path)
			 if os.path.exists(share_path_server_user):
			 	os.remove(share_path_server_user)
###########################################################################
def is_shared(client_dir, filename):		
	username = client_dir.split('/').pop()
	server_share_path = os.getcwd() + '/' + 'share' + '/' + username + '/' + filename
	if os.path.exists(server_share_path):
		with open(server_share_path, 'r') as sharefile:
			for line in sharefile:
				line = line.rstrip()
				sharefile.close()
				return True, line
	if os.path.exists(client_dir + '/' + 'sharefile.dropbin'):
		with open(client_dir + '/' + 'sharefile.dropbin', 'r') as sharefile:
			for line in sharefile:
				line = line.rstrip()
				name = line.split(' ')[0]
				if name == filename:
					sharefile.close()
					return True, username
	return False,''

def save_server_state():
	if os.path.exists(os.getcwd() + '/copy'):
		shutil.rmtree(os.getcwd() + '/copy')
	dirs = [d for d in os.listdir() if os.path.isdir(os.path.join(os.getcwd(), d))]
	for folder in dirs:
		if folder != 'copy':
			src_path = os.getcwd() + '/' + folder
			dst_path = os.getcwd() + '/' + '/copy/' + folder
			shutil.copytree(src_path, dst_path)

def load_server_state():
	dirs = [d for d in os.listdir() if os.path.isdir(os.path.join(os.getcwd(), d))]
	for folder in dirs:
		if folder != 'copy':
			shutil.rmtree(os.getcwd() + '/' + folder)
	path = os.getcwd() + '/copy'
	dirs = os.listdir(path)
	for folder in dirs:
		src_path = os.getcwd() + '/' + '/copy/' + folder
		dst_path = os.getcwd() + '/' + folder
		shutil.copytree(src_path, dst_path)

###########################################################################

def get_user_dir(server_dir, username, conn):
	path = server_dir + "/" + str(username)
	if not os.path.exists(path):
		os.makedirs(path, exist_ok=True)
	return path

def add_file(client_dir, filename, data):
	path = os.path.join(client_dir, filename)
	file = open(path, 'w')
	file.write(data)
	file.close()

def delete_file(client_dir, filename):
	path = os.path.join(client_dir, filename)
	if os.path.exists(path):
		os.remove(path)

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

def handle_client(conn, client_dir):
	share_on_server = os.getcwd() + '/' + 'share'
	if not os.path.exists(share_on_server):
		os.mkdir(share_on_server) 
	while True:
		msg = get_message(conn)
		###########################################################################
		if msg['type'] == 'file_add':
			print('file added ', os.path.join(client_dir, msg['filename']))
			if msg['filename'] == 'sharefile.dropbin':
				username = client_dir.split('/').pop()
				sharefile_dropbin_path = client_dir + '/' + 'sharefile.dropbin'
				if os.path.exists(client_dir + '/' + 'sharefile.dropbin'): # If there was an old sharefile
					file = open(sharefile_dropbin_path, 'r')
					old_data = file.read()
					add_file(client_dir, msg['filename'], msg['data'])
					manage_sharing(sharefile_dropbin_path, old_data, username, False)
				else:
					add_file(client_dir, msg['filename'], msg['data'])
					manage_sharing(sharefile_dropbin_path, '', username, True)
			else:
				share, owner = is_shared(client_dir, msg['filename'])
				if share == True:
					while os.path.exists(os.getcwd() + '/' + 'busy'):
						pass
					if not os.path.exists(os.getcwd() + '/' + 'busy'):
						os.mkdir(os.getcwd() + '/' + 'busy')
						add_file(os.getcwd() + '/' + owner, msg['filename'], msg['data'])
						with open(os.getcwd() + '/' + owner + '/' + 'sharefile.dropbin') as sharefile:
							for line in sharefile:
								line = line.rstrip()
								line = line.split(' ')
								users = []
								if line[0] == msg['filename']:
									users = line[1:]
									for user in users:
										add_file(os.getcwd() + '/' + user, msg['filename'], msg['data'])
							sharefile.close()
						os.rmdir(os.getcwd() + '/' + 'busy')
				else:
					add_file(client_dir, msg['filename'], msg['data'])
			save_server_state()
		###########################################################################
		elif msg['type'] == 'file_delete':
			print('file deleted ', os.path.join(client_dir, msg['filename']))
			share, owner = is_shared(client_dir, msg['filename'])
			if share == True:
				sharefile_dropbin_path = os.getcwd() + '/' + owner + '/' + 'sharefile.dropbin'
				with open(sharefile_dropbin_path, 'r') as sharefile:
					for line in sharefile:
						line = line.rstrip()
						line = line.split(' ')
						if msg['filename'] == line[0]:
							users = line[1:]
							for user in users:
								delete_file(os.getcwd() + '/' + user, msg['filename'])
								delete_file(os.getcwd() + '/' + 'share' + '/' + user, msg['filename'])
					sharefile.close()
				delete_file(os.getcwd() + '/' + owner, msg['filename'])
				file = open(sharefile_dropbin_path, 'r')
				lines = file.readlines()
				file.close()
				file = open(sharefile_dropbin_path, 'w')
				for line in lines:
					curr_line = line
					curr_line = curr_line.rstrip()
					curr_line = curr_line.split(' ')[0]
					if curr_line != msg['filename']:
						file.write(line)
				file.close()
			else:
				delete_file(client_dir, msg['filename'])
			save_server_state()
		###########################################################################
		elif msg['type'] == 'sync':
			if msg['sync_type'] == 'selective':
				files = os.listdir(client_dir)
				send_file_names(conn, files)    # TAG RFN
				selected_files = get_message(conn)['names'] # TAG SFN
				for file in selected_files:
					send_new_file(conn, file, client_dir)
			elif msg['sync_type'] == 'normal':
				files = os.listdir(client_dir)
				send_file_names(conn, files)    # TAG RFN
				for file in files:
					send_new_file(conn, file, client_dir)
		###########################################################################
		elif msg['type'] == 'files':
			files = get_file_list(client_dir)
			send_file_names(conn, files)
		elif msg['type'] == 'file_names':
			send_new_file(conn, msg['names'], client_dir)
		###########################################################################
		elif msg['type'] == 'logout':
			usernm = client_dir.split('/').pop()
			print(usernm, ' has logged out.')
			break
		###########################################################################
	conn.close()


def server(port, server_dir):
	server_state_path = os.getcwd() + '/copy'
	if os.path.exists(server_state_path):
		load_server_state()

	host = socket.gethostbyname("localhost")

	s = socket.socket()
	s.bind((host, port))
	s.listen(10)

	print("Host ", host, " is listening on ", port)

	while True:
		conn, addr = s.accept()
		print("Got connection form ", addr)
		##############################################
		get_username = get_message(conn) # TAG SU
		if os.path.exists(server_dir + '/' + get_username['username']):
			send_user_status(conn, 'olduser') # TAG GUS
		else:
			send_user_status(conn, 'newuser') # TAG GUS
		##############################################
		CLIENT = get_user_dir(server_dir, get_username['username'], conn)
		threading.Thread(target=handle_client, args=(conn, CLIENT)).start()

	s.close()
		

if __name__ == "__main__":
	parser = argparse.ArgumentParser()
	parser.add_argument("port", type=int, help="Port number the server will listen on.")
	args = parser.parse_args()
	server(args.port, os.getcwd())