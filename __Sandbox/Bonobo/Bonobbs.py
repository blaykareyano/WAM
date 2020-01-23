from __future__ import print_function
import Pyro4

@Pyro4.expose
class serverDaemon(object):
	def __init__(self):
		pass

	def getComputerInfo(self):
		# \todo get variable input from serverConf JSON dictionary
		compName = "Bonobbs"
		cpus = 4
		mem = 64
		IP = "10.200.209.251"
		return [compName, cpus, mem, IP];

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
