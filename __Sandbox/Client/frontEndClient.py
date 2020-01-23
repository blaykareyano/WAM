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
		serverDaemons = []
		for serverDaemon, serverDaemon_uri in ns.list(prefix="WAM.").items():
			print("found: {0}".format(serverDaemon))
			serverDaemons.append(serverDaemon_uri)
		if not serverDaemons:
			raise ValueError("no server daemons found!")

	## queryAllServers Method
	# Looks through all servers and gathers machine info (cores, avail. memory, IP addr)
	def queryAllServers(self):
		sys.excepthook = Pyro4.util.excepthook
		ns = Pyro4.locateNS()
		for serverDaemon, serverDaemon_uri in ns.list(prefix="WAM.").items():
			with Pyro4.Proxy(serverDaemon_uri) as currentServer:
				try:
					serverInfo = currentServer.getComputerInfo()
					print("{0} ---\ncores: {1}\nmem: {2}Gb\nIP: {3}\n".format(serverInfo[0],serverInfo[1],serverInfo[2],serverInfo[3]))
				except Exception as e:
					print("ERROR:	Unable to connect to server {0}".format(serverDaemon))
					print(e)
					print(serverDaemon_uri)



def main():
	front_end_client = frontEndClient()
	print("Looking for server daemons...")
	front_end_client.findServers()
	print("Gathering HPC info...")
	front_end_client.queryAllServers()

if __name__=="__main__":
	main()