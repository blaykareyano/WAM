from __future__ import absolute_import
from __future__ import print_function
import Pyro4
import sys
import os
from parseJSONFile import parseJSONFile
import threading
import socket
import time

Pyro4.config.COMMTIMEOUT = 10.0

@Pyro4.expose
class serverDaemon(object):
	def __init__(self):
		self.HMAC_KEY = "WAM!WAM!WAM!"
		self.serverScriptDirectory = os.path.dirname(os.path.realpath(__file__))
		self.confFileLock = threading.Lock()
		self.loadServerConfFile()
		self.nsThread = None

	## connectToNameServer Method
	# spawns a thread to continously attempt to connect to the name server
	def connectToNameServer(self, daemon_uri):
		registerWithNameServer = self.serverConf["nameServer"]["registerWithNameServer"]
		if registerWithNameServer:
			def nsReregister(daemon_uri):
				while 1:
					self.loadServerConfFile()
					reconnectTime_sec = self.serverConf["nameServer"]["reconnectToNameServer_minutes"]*60
					try:
						NS_HOST = self.serverConf["nameServer"]["nameServerIP"]
						NS_PORT = self.serverConf["nameServer"]["nameServerPort"]
						ns = Pyro4.locateNS(host=NS_HOST,port=NS_PORT,hmac_key=self.HMAC_KEY)
						print("--- Successfully located name server")
						print("--> Registering with name server {0}:{1}".format(NS_HOST,NS_PORT))
						ns.register("WAM.{0}".format(self.serverConf["localhost"]["hostName"]), daemon_uri)
						print("--- Successfully registered with name server")
						print(ns)
					except:
						if self.serverConf["nameServer"]["quitOnNameServerConnectionError"]:
							print("*** ERROR: Cannot connect to name server! Exiting script.")
							print("*** INFO: Host: {0}	Port: {1}	HMAC key: {2}".format(NS_HOST,NS_PORT,self.HMAC_KEY))
							sys.exit(1)
						print("--> Will attempt to reconnect to name server (%s:%s) in %.2f minutes"%(NS_HOST, NS_PORT, self.serverConf["nameServer"]["reconnectToNameServer_minutes"]))
					time.sleep(reconnectTime_sec)
			self.nsThread = threading.Thread(target=nsReregister, args=(daemon_uri,))
			self.nsThread.setDaemon(True)
			self.nsThread.start()

	def getComputerInfo(self):
		# \todo get variable input from serverConf JSON dictionary
		compName = self.serverConf["localhost"]["hostName"]
		cpus = self.serverConf["localhost"]["maxCPUs"]
		mem = self.serverConf["localhost"]["maxMEM"]
		IP = self.serverConf["localhost"]["IPaddr"]
		return [compName, cpus, mem, IP];

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
	except: # otherwise use local host
		daemon = Pyro4.Daemon(port=server_daemon.serverConf["usePortNumber"])
		print("--> Starting daemon on localhost:{0}".format(server_daemon.serverConf["usePortNumber"]))

	daemon_uri = daemon.register(server_daemon)
	server_daemon.connectToNameServer(daemon_uri)

	print("--- Daemon started successfully")
	print("--- INFO: uri: {0}".format(daemon_uri))

	daemon.requestLoop()

if __name__=="__main__":
	main()