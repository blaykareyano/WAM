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
# Contains all functions for WAM server  
class WAMServer(object):
	## __init__ Method
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
		self.currentSubProcess = None				# holds the subprocess currently running one our solvers 
													# in case we want to kill it 
		self.start = datetime.datetime.now()		# init stop watch with dummy value
		self.jobsCompleted = []
		self.CPULock = threading.Lock()				# thread lock used to restrict CPU access while running an analysis
		self.jobListLock = threading.Lock()			# thread lock used to restict access to our jobs list while it is being used
		self.jobsCompletedListLock = threading.Lock()	# thread lock used to restict access to our jobsCompleted list
														# while it is being used
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

		## connectToNameServer Function
		# Function spawnes a thread that keeps connecting/reconnecting to the name server after every N seconds.
		def connectToNameServer(self, jss_uri):
