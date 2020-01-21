#!/usr/bin/python

## @package WAMServer
## @brief 
# Manages work allocation and acts as portal for all computational machines on the network
#
# \todo library definitions
from utils.parseJSONFile import parseJSONFile
from utils.emailMisc import sendEmailMsg
import Pyro4
import threading
import sys
import os
import logging
import pickle

## [Pyro Documentation](https://pythonhosted.org/Pyro4/index.html, "Pyro Documentation")
#
## signature preventing arbitrary connections  
Pyro4.config.HMAC_KEY = 'W4MquestW4MintegrityW4M'
## network communication timeout in seconds
Pyro4.config.COMMTIMEOUT = 10.0
## current version number
version = 0.0

## WAM Server Class:
# Contains all methods for WAM server  
class WAMServer(object):
	## __init__ method
	# initialize the values of instance members for the new object  
	def __init__(self):
		self.serverScriptDirectory = os.path.dirname(os.path.realpath(__file__))	# directory where this file is located
		self.confFileLock = threading.Lock()		# thread lock server configuration file
		self.loadServerConfFile()					# load server configuration file
        self.jobs = []								# initialize SerializedJobList
        self.serializeJobListLock = threading.Lock()# thread lock used to safely serialize self.jobs list
		self.serializeCounterLock = threading.Lock()# thread lock used to safely serialize the JobID counter
		self.loadSerializedCounter()				# loads job ID counter
		self.loadSerializedJobList()				# loads self.jobs

		runFailSafe = False 	# False until proven true

		# are we restarting jobs after the server has crashed?
		if ("failsafe" in self.serverConf.keys()):
			if ((len(self.jobs) > 0) and (self.serverConf["failsafe"] is True)):
				runFailSafe = True
					for job in self.jobs:
					job["InternalUse"]["failsafe"] = True               
		else:
			self.jobs = [] # fail safe is not present in config file: set default to disabled

		self.currentJobID = None					# the job id for the current job that is running
		self.currentSubProcess = None				# holds subprocess currently running solver in case of kill 
		self.start = datetime.datetime.now()		# init stop watch with dummy value
		self.jobsCompleted = []
		self.CPULock = threading.Lock()				# thread lock to restrict CPU access while running an analysis
		self.jobListLock = threading.Lock()			# thread lock to restict access to jobs list while in use
		self.jobsCompletedListLock = threading.Lock()	# thread lock to restict access to jobsCompleted list while in use
		self.logFile = os.path.join(self.serverScriptDirectory,r"logs",self.serverConf["localhost"]["logFileFile"])  # log file path
		
		# see if the log file exists:
		if not os.path.isfile(self.logFile):
			open(self.logFile, 'a').close()  # if it doesn't, just create an empty one

		# Start logging
		logging.basicConfig(filename=self.logFile,level=logging.DEBUG, format='%(asctime)s - %(levelname)s: %(message)s', 
			datefmt='%m/%d/%Y %I:%M:%S %p')
		logging.info("WAM server is up and running... Good job!")

		if runFailSafe:
			logging.info("Running %i failsafe jobs..."%(len(self.jobs)))
			for job in self.jobs:
				threading.Thread(target=self.__runJob, args=(job,)).start()

		self.nsThread = None  # name server connection/reconnection thread

	## about method
	# Returns licens and version information
	# \todo Need reference to Bruno's JSS Server?
	# \todo add anyone else working on WAM
	def about(self):
		return """
WAM - Workload Allocation Manager - Version %s
Copyright (C) 2020 - Blake N. Arellano - blake.n.arellano@gmail.com

This program is free software; you can redistribute it and/or
modify it under the terms of the GNU General Public License
as published by the Free Software Foundation; either version 2
of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program; if not, write to the Free Software
Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
MA  02110-1301, USA.
        """%(version)

	## connectToNameServer method
	# Function spawnes a thread that keeps connecting/reconnecting to the name server after every N seconds.
	def connectToNameServer(self, jss_uri):
		registerWithNameServer = self.serverConf["nameServer"]["registerWithNameServer"]

		if registerWithNameServer:
			# check to see if we should use the name server:
			def nsReregister(jss_uri):
				while 1:
					self.loadServerConfFile() 
					reconnectTime_sec = self.serverConf["nameServer"]["reconnectToNameServer_minutes"]*60.0 
					try:
						Pyro4.config.NS_HOST  = self.serverConf["nameServer"]["nameServerIP"]
						Pyro4.config.NS_PORT  = self.serverConf["nameServer"]["nameServerPort"]
						ns = Pyro4.locateNS()
						ns.register("jssServer-%s.server"%(socket.gethostname()), jss_uri)
					except Exception as e:
						logging.error(str(e))
						if self.serverConf["nameServer"]["quitWAMOnNameServerConnectionError"]:
							logging.info("Stopping JSS server since quitWAMOnNameServerConnectionError was set to true in the WAM server configuration file")
							sys.exit(1)
						logging.error("Will attempt to reconnect to the name server (%s) in %.2f minutes"%(self.serverConf["nameServer"]["nameServerIP"],
							self.serverConf["nameServer"]["reconnectToNameServer_minutes"]))
					time.sleep(reconnectTime_sec)

			self.nsThread = threading.Thread(target=nsReregister, args=(jss_uri,))
			self.nsThread.setDaemon(True)
			self.nsThread.start()

	## shakeHands method
	# tests if the client can connect to the server
    def shakeHands(self, clientName, clientMachine):
		logging.info("Shook hands with client %s@%s"%(clientName,clientMachine))
		return True

	## loadSerializedCounter method
	# Loads the JobID counter from a pickle file; used to init the persistent counter
	# If the file does not exist it will initialize self.jobID to 0
	# \todo finalize pickle file path
	def loadSerializedCounter(self,filePath = "/opt/WAM/server/counter.p"):
		with self.serializeCounterLock:
			if os.path.isfile(filePath):
				self.jobID = pickle.load(open(filePath,"rb"))
			else:
				self.jobID = 0

    ## loadSerializedJobList method
    # Loads self.jobs list from a pickle file
    # Used to init jobs in case the server crashes or is killed while have jobs are in the queue
    # If the file does not exist it will return an empty list.
    # \todo finalize pickle file path
	def loadSerializedJobList(self,filePath = "/opt/WAM/server/jobList.p"):
		with self.serializeJobListLock:
			if os.path.isfile(filePath):
				self.jobs = pickle.load(open(filePath,"rb"))
			else:
				self.jobs = []

	## serializeCounter method
	# Serialized the JobID counter using a pickle file
	# Used to init the persistent counter
	# \todo finalize pickle file path
	def serializeCounter(self,filePath = "/opt/WAM/server/counter.p"):
		with self.serializeCounterLock:        
			try:
				pickle.dump(self.jobID, open(filePath,"wb"))
			except:
				logging.error("Unable to serialize (i.e., pickle) counter")

	## serializeJobList method
	# Serialize our job list to restart a job in the queue in case the server application is killed.
	# \todo finalize pickle file path
	def serializeJobList(self,filePath = "/opt/WAM/server/jobList.p"):
		with self.serializeJobListLock:
			try:
				pickle.dump(self.jobs, open(filePath,"wb"))
			except:
				logging.error("Unable to serialize (i.e., pickle) self.jobs")

	## removeAbqLockFile method
	# Scans the directory for an Abaqus lock file (*.lck) and deletes if it exists
	# \todo update clientWorkingDir?
	def removeAbqLockFile(self, job):
		if (job["InternalUse"]["jsonFileType"] == "abaqus"):
			lckFile = "%s%s"%(job["jobName"],".lck")
			clientWorkingDir = job["InternalUse"]["clientWorkingDir"]   
			lckFile = os.path.join(clientWorkingDir,lckFile)  
			if os.path.isfile(lckFile):
			os.remove(lckFile)

	## jobData method
	# takes user input to define job variables
	# \todo all of it
	def jobData(self)

	## jobDispatcher
	# submits and valides JSON job input files via 'parsed; JSON dictionary
	# jData: dictionary with all parsed data contained in the *.json file
	# \todo make jData compiled from user data - jobData method 
	def jobDispatcher(self, jData):
		self.loadServerConfFile() # reload the configuration file before job submission
		# Do some error trapping and logging
		if ("InternalUse" not in jData.keys()):
			logging.error("jobDispatcher call from %s@%s: 'InternalUse' block not present the passed %s file"%(jData["InternalUse"]["clientName"],jData["InternalUse"]["clientMachine"],jData["InternalUse"]["jsonFileName"]))
			return
		if ("jsonFileType" not in jData["InternalUse"].keys()):
			logging.error("jobDispatcher call from %s@%s: 'jsonFileType' entry not present the passed %s file"%(jData["InternalUse"]["clientName"],jData["InternalUse"]["clientMachine"],jData["InternalUse"]["jsonFileName"]))
			return