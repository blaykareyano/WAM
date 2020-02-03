#!/usr/bin/python

# Futures
from __future__ import print_function

# Standard Libraries
import sys

# 3rd Party Packages
import Pyro4
from tabulate import tabulate

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
		
		# Initialize the table
		headers = ["Host Name", "IP Address", "Cores", "Total Memory", "Job Queue Length"]
		table = []

		# Find all daemon servers and loop through them
		daemons = self.findServers()
		for daemon_uri, daemonName in daemons:
			currentServer = Pyro4.Proxy(daemon_uri)

			try:
				[compName, cpus, mem, IP] = currentServer.getComputerInfo()
				
				tmp = []
				tmp.append(compName)
				tmp.append(IP)
				tmp.append(cpus)
				tmp.append(str(mem) + " Gb")
				tmp.append("TODO")

				table.append(tmp[:])

			except Exception as e:
				print("*** ERROR: {0}".format(e))
				return

		print(tabulate(table, headers, tablefmt="rst", numalign="center", stralign="center"))

def main():
	front_end_client = frontEndClient()

	front_end_client.queryAllServers()

if __name__=="__main__":
	main()