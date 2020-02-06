from __future__ import print_function
import Pyro4
import sys

class frontEndClient(object):
	def __init__(self):
		self.serverDaemons = set()

	## findServers Method
	# Looks through the name server to find all registered servers
	def findServers(self):
		sys.excepthook = Pyro4.util.excepthook
		ns = Pyro4.locateNS()

		daemon_uris = []
		daemonNames = []

		for daemonName, daemon_uri in ns.list(prefix="WAM.").items():
			print("--- INFO: Found {0}".format(daemonName))
			daemon_uris.append(daemon_uri)
			daemonNames.append(daemonName)

		if not daemon_uris:
			print("*** ERROR: No server daemons found!")
		
		daemons = zip(daemon_uris,daemonNames)
		return daemons

	## queryAllServers Method
	# Looks through all servers and gathers machine info (cores, avail. memory, IP addr)
	def queryAllServers(self):
		sys.excepthook = Pyro4.util.excepthook
		daemons = self.findServers()

		for daemon_uri, daemonName in daemons:
			currentServer = Pyro4.Proxy(daemon_uri)

			try:
				currentServer.shakeHands()
			except Exception as e:
				print("*** ERROR: Unable to connect to server {0}".format(daemonName))
				print("*** INFO: {0}".format(e))
				return

			[compName, cpus, mem, IP] = currentServer.getComputerInfo()
			print("{0} -----\ncores:	{1}\nRAM:	{2}\nIP:	{3}".format(compName,cpus,mem,IP))



def main():
	front_end_client = frontEndClient()

	print("--> Gathering HPC info")
	front_end_client.queryAllServers()

if __name__=="__main__":
	main()