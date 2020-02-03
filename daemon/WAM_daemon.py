#!/usr/bin/python

# Futures
from __future__ import absolute_import
from __future__ import print_function

# Standard Libraries
import sys
import os
import threading
import socket
import time
import multiprocessing
from psutil import virtual_memory

# 3rd Party Packages
import Pyro4

# Local Source Libraries
from utils.parseJSONFile import parseJSONFile

# Pyro4 configuration
Pyro4.config.COMMTIMEOUT = 10.0

# Daemon class visible to Pyro client
@Pyro4.expose
class serverDaemon(object):
	def __init__(self):
		# directory of this script
		self.serverScriptDirectory = os.path.dirname(os.path.realpath(__file__))

		# lock server conf. file
		self.confFileLock = threading.Lock()
		self.loadServerConfFile()

		# gather HPC info
		self.hostName = socket.gethostname()
		self.IPaddr = socket.gethostbyname(self.hostName)
		self.cpus = multiprocessing.cpu_count()
		self.mem = virtual_memory() # in bytes; options include: total & available

		# name server connect/reconnect thread initialization
		self.nsThread = None

	## connectToNameServer Method
	# connects to name server at the location defined in serverConf.JSON
	# starts a thread which continuously checks the connection to the name server
	def connectToNameServer(self, daemon_uri):
		registerWithNameServer = self.serverConf["nameServer"]["registerWithNameServer"]
		if registerWithNameServer:
			def nsReregister(daemon_uri):
				while 1:
					nsHost = self.serverConf["nameServer"]["nameServerIP"]
					nsPort = self.serverConf["nameServer"]["nameServerPort"]
					reconnectTime = self.serverConf["nameServer"]["reconnectToNameServer_minutes"] # time in minutes

					try:
						ns = Pyro4.locateNS(host=nsHost,port=nsPort)
						ns.register("WAM.{0}.daemon".format(self.hostName), daemon_uri)
					
					except:
						if self.serverConf["nameServer"]["quitOnNameServerConnectionError"]:
							print("*** ERROR: Cannot connect to name server! Exiting script")
							print("*** INFO: Host: {0}	Port: {1}".format(nsHost,nsPort))
							sys.exit(1)

						print("*** ERROR: Cannot connect to name server!")
						print("*** INFO: Host: {0}	Port: {1}".format(nsHost,nsPort))
						print("*** Attempting to reconnect in {0} minutes".format(reconnectTime))
					
					time.sleep(reconnectTime*60)

			self.nsThread = threading.Thread(target=nsReregister, args=(daemon_uri,))
			self.nsThread.setDaemon(False)
			self.nsThread.start()

	## getComputerInfor Method
	# gathers host info to be presented to client
	def getComputerInfo(self):
		# Get total memory and convert from bytes to Gb
		totMem = int(self.mem.total/1000000000) # convert from bytes to gb
		
		# return needed values
		return [self.hostName, self.cpus, totMem, self.IPaddr]

	## loadServerConfFile Method
	# pretty self explanatory I believe
	def loadServerConfFile(self):
		with self.confFileLock:
			filePath = os.path.join(self.serverScriptDirectory,"serverConf.json")
			self.serverConf = parseJSONFile(filePath)

def main():
	server_daemon = serverDaemon()

	try: # use network ip addr. if connected to network
		myIP = [(s.connect(('8.8.8.8', 80)), s.getsockname()[0], s.close()) for s in [socket.socket(socket.AF_INET, socket.SOCK_DGRAM)]][0][1]
		daemon = Pyro4.Daemon(host=myIP, port=server_daemon.serverConf["usePortNumber"])
		print("--> Starting daemon on {0}:{1}".format(myIP,server_daemon.serverConf["usePortNumber"]))
	except: # otherwise send error
		print("*** ERROR: unable to connect to network")
		sys.exit(1)

	daemon_uri = daemon.register(server_daemon,objectId="WAM." + socket.gethostname())
	server_daemon.connectToNameServer(daemon_uri)

	print("--- Daemon started successfully")
	print("--- INFO: uri = {0}".format(daemon_uri))

	daemon.requestLoop()

if __name__=="__main__":
	main()