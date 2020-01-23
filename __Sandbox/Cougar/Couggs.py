from __future__ import print_function
import Pyro4
import os
import parseJSONFile
import threading

@Pyro4.expose
class serverDaemon(object):
	def __init__(self):
		self.serverScriptDirectory = os.path.dirname(os.path.realpath(__file__))
		self.confFileLock = threading.Lock()
		self.loadServerConfFile()

	def getComputerInfo(self):
		# \todo get variable input from serverConf JSON dictionary
		compName = "Couggs"
		cpus = 18
		mem = 124
		IP = "10.200.209.12"
		return [compName, cpus, mem, IP];

	def loadServerConfFile(self):
		with self.confFileLock:
			self.confFileLock = parseJSONFile(os.path.join(self.serverScriptDirectory,r"conf","serverConf.json"))

def main():
	server_daemon = serverDaemon()
	daemon = Pyro4.Daemon()
	daemon_uri = daemon.register(server_daemon)
	computerInfo =	server_daemon.getComputerInfo()
	computerName = computerInfo[0]
	ns = Pyro4.locateNS()
	ns.register("WAM.{0}".format(computerName),daemon_uri)
	print("Server is running")
	daemon.requestLoop()

if __name__=="__main__":
	main()
