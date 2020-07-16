#!/usr/bin/python

# Futures
from __future__ import absolute_import
from __future__ import print_function

# Standard Libraries
import sys
import os
import platform
import getpass
import subprocess
import threading
import socket
import signal
import time
import datetime
import multiprocessing
import logging
import copy
import string
import base64
from subprocess import CalledProcessError, check_output

# 3rd Party Packages
import Pyro4 # https://pypi.org/project/Pyro4/
import serpent # https://pypi.org/project/serpent/1.28/
from psutil import virtual_memory # https://pypi.org/project/psutil/

# Local Source Packages
from utils.parseJSONFile import parseJSONFile
from utils.emailMisc import sendEmailMsg

# Pyro4 configuration options
# Pyro4.config.COMMTIMEOUT = 300.0 # timeout in seconds

# Daemon class visible to Pyro client
@Pyro4.expose
class serverDaemon(object):
	def __init__(self):
		# define this directory
		self.serverScriptDirectory = os.path.dirname(os.path.realpath(__file__))

		# lock and load server conf. file
		self.confFileLock = threading.Lock()
		self.loadServerConfFile()

		# lock and load serialized objects
		self.jobIDLock = threading.Lock()
		self.loadSerializedJobID()
		self.jobListLock = threading.Lock()
		self.serializedJobListLock = threading.Lock()
		self.loadSerializedJobList()
		self.serializedJobHistLock = threading.Lock()
		self.loadSerializedJobHist()

		# set up cpu lock for running jobs
		self.CPULock = threading.Lock()

		# start logging
		self.loggingSetup()

		# gather HPC info
		self.hostName = socket.gethostname()
		self.IPaddr = socket.gethostbyname(self.hostName)
		self.cpus = multiprocessing.cpu_count()
		self.mem = virtual_memory() # in bytes; options include: total & available
		self.opSystem = platform.system()

		# name server connect/reconnect thread initialization
		self.nsThread = None

		logging.info("WAM daemon server script initalized")

	## jobInitialization Method
	# set up work directory for job
	# returns jobID and directory to client
	def jobInitialization(self,runDirectory):
		# create new jobID and serialize
		self.jobID = self.jobID + 1
		self.serializeJobID()

		# create directory to run jobs 
		logging.info("job initialization started in directory: {0}".format(runDirectory))
		jobDirectory = os.path.join(runDirectory, str(self.jobID))
		
		try:
			os.mkdir(jobDirectory)
			os.chmod(jobDirectory, 0o777)
			logging.info("directory made for job: {0}".format(self.jobID))
		except OSError as e:
			logging.error("unable to create job directory for job {0}: {1}".format(self.jobID,e))

		# return job ID for client
		return(self.jobID, jobDirectory)

	## jobDefinition Method
	# Gathers all necessary information for job submission
	# Submits job to queue
	def jobDefinition(self,jobDirectory):
		jsonFile = os.path.join(jobDirectory,"abaqusSubmit.json")
		jobData = parseJSONFile(jsonFile)

		logging.info("job {0} submission JSON loaded".format(self.jobID))

		subTime = datetime.datetime.now().strftime("%B %d - %H:%M %p")
		jobData["InternalUse"]["submissionTime"] = subTime

		# Separate all job files and create indivual dictionaries for each
		for i,jobFile in enumerate(jobData["jobFiles"]):
			singleJob = copy.deepcopy(jobData)
			singleJob.pop("jobFiles",None)
			singleJob["jobName"] = os.path.splitext(os.path.basename(jobFile))[0]
			singleJob["InternalUse"]["jobNumber"] = str(self.jobID)
			singleJob["InternalUse"]["jobID"] = str(self.jobID)+":"+singleJob["jobName"]
			singleJob["InternalUse"]["jobFile"] = os.path.join(jobDirectory,singleJob["jobName"]+".inp")
			singleJob["InternalUse"]["jobDirectory"] = jobDirectory

			logging.info("created job {0}".format(singleJob["InternalUse"]["jobID"]))

			self.addJobToQueue(singleJob, jobDirectory)	

	## addJobToQueue Method
	# adds jobs from job list into queue
	# calls _runJob from created queue
	def addJobToQueue(self,job,jobDirectory):
		with self.jobListLock:

			job["InternalUse"]["status"] = "queue"
			logging.info("job {0} added to queue".format(job["InternalUse"]["jobID"]))

			self.jobs.append(job)

			# sort the job queue by priority
			try:
				self.jobs.sort(key=lambda i: (i["InternalUse"]["status"]!="running",i["advanced"]["priority"],i["InternalUse"]["submissionTime"]))
			except Exception as e:
				logging.error("unable to prioritize jobs list: {0}".format(e))
			
			self.serializeJobList()

		threading.Thread(target=self.__runJob).start()

	## __runJob Private Method
	# submits each job individually
	def __runJob(self):
		with self.CPULock:
			
			job = self.jobs[0]
			jobDirectory = job["InternalUse"]["jobDirectory"]

			# check if job has been killed
			if "killed" in job["InternalUse"]["status"]:
				return

			# preliminary job submission stuff	
			self.start = datetime.datetime.now() # start a clock
			with self.jobListLock:
				job["InternalUse"]["status"] = "running"
				self.serializeJobList()
			os.chdir(jobDirectory)
			cwd = jobDirectory

			# create log files
			stdErrorFile = os.path.join(jobDirectory, "error.log")
			stdOutFile = os.path.join(jobDirectory, "out.log")

			# gather job information
			clientName = job["InternalUse"]["clientName"]
			cpus = job["solverFlags"]["cpus"]
			gpus = job["solverFlags"]["gpus"]
			jobName = job["jobName"]
			jobID = job["InternalUse"]["jobID"]
			solver = job["InternalUse"]["jsonFileType"]

			self.currentJobID = jobID
			self.currentJobNumber = job["InternalUse"]["jobNumber"]

			# compile command line options
			cmd = []
			cmd.append(solver)
			cmd.append("job={0}".format(jobName))
			for key in job["solverFlags"].keys():
				if job["solverFlags"][key] is None:
					cmd.append(key)
				else:
					cmd.append("{0}={1}".format(key,job["solverFlags"][key]))

			if self.opSystem == "Linux":
				import pwd
				# define user id, environment variables, etc.
				currentUserID = pwd.getpwnam(getpass.getuser()).pw_uid 
				pw_record = pwd.getpwnam(getpass.getuser())
				user_name      = pw_record.pw_name
				user_home_dir  = pw_record.pw_dir
				user_uid       = pw_record.pw_uid
				user_gid       = pw_record.pw_gid
				env = os.environ.copy()
				env[ 'HOME'     ]  = user_home_dir
				env[ 'LOGNAME'  ]  = user_name
				env[ 'PWD'      ]  = jobDirectory
				env[ 'USER'     ]  = user_name
				env[ 'PATH'		]  = '/var/DassaultSystemes/SIMULIA/Commands:/sbin:/bin:/usr/sbin:/usr/bin'

				# spawn subprocess as a given user
				def demote(user_uid, user_gid):
					def result():
						os.setgid(user_gid)
						os.setuid(user_uid)
						os.setsid()
					return result

				# Run the job
				with open(stdOutFile,"a+") as out, open(stdErrorFile,"a+") as err:
					os.chown(stdOutFile, currentUserID, -1)
					os.chown(stdErrorFile, currentUserID, -1)
					try:
						logging.info("job {0} has been submitted for analysis".format(self.currentJobID))
						self.currentSubProcess = subprocess.Popen(cmd, stdout=out, stderr=err, preexec_fn=demote(user_uid,user_gid), cwd=cwd, env=env)
						self.currentSubProcess.wait()
						self.currentSubProcess = None
						logging.info("job {0} has completed".format(self.currentJobID))

					except Exception as e:

						self.currentSubProcess = None

						cmd = " ".join(cmd)
						err.write("*** ERROR: command line error\n")
						err.write(str(e)+"\n")
						err.write("Error encountered while executing: {0} \n".format(cmd))
						err.write("\n")

						logging.error("error running Abaqus: {0}".format(self.currentJobID))
						logging.error("error encountered while executing: {0}".format(cmd))

					# convert unix2dos
					fileTypes = [jobName+".fil",jobName+".sta",jobName+".msg",jobName+".dat"]
					for fileType in fileTypes:
						cmd = ["unix2dos",fileType]
						try:
							self.currentSubProcess = subprocess.Popen(cmd,cwd=cwd)
							self.currentSubProcess.wait()
							self.currentSubProcess = None
							logging.info("converted file {0} using unix2dos".format(fileType))
						except Exception as e:
							logging.error("unable to convert file {0} using unix2dos: {1}".format(fileType,e))

					# send email on completion (if requested)
					if job["advanced"]["sendEmailTo"] != "None":
						message = None

						# get the msg file contents:
						if os.path.exists(jobName+".msg") == False:
							out = open("{0}.msg".format(jobName),"w")
							out.write("*** no message file exists for job {0} ***\r\n\n".format(jobName))
							out.write("*** this is probably due to an input file error ***\r\n\n".format(jobName))
							out.close()

						with open("{0}.msg".format(jobName),"r") as out:
							# get server data:
							SMTPServer = self.serverConf["emailServer"]["SMTPServer"]
							SMTPPort   = self.serverConf["emailServer"]["SMTPPort"]
							username   = self.serverConf["emailServer"]["username"]
							password   = self.serverConf["emailServer"]["password"]
							emailInfoEncrypted = self.serverConf["emailServer"]["emailInfoEncrypted"]
							useStarttls   = self.serverConf["emailServer"]["useStarttls"]

							if emailInfoEncrypted:
								SMTPServer = base64.b64decode(SMTPServer)
								SMTPPort   = base64.b64decode(SMTPPort)
								username   = base64.b64decode(username)
								password   = base64.b64decode(password)

							data  = out.readlines()
							logFileLines = data[-100::]
							message = []
							message.append("Finished running: {0}.inp \r\n\nTo retrieve your files use the command: wam -get {1} -n {2} \r\n\n *** The end of {0}.msg reads: \r\n\r\n".format(jobName, jobID, self.hostName))
							for line in logFileLines:
								message.append(line.strip() + "\r\n")

						# get the status file contents if the file exists:
						if os.path.isfile("{0}.sta".format(jobName)):
							with open("{0}.sta".format(jobName),"r") as sta:
								data  = sta.readlines()
								staFileLines = data[-100::]
								message.append("\r\n *** The end of {0}.sta reads: \r\n\r\n".format(jobName))
								for line in staFileLines:
									message.append(line.strip() + "\r\n")

						if message is not None:
							message = "".join(message)
							recipient = job["advanced"]["sendEmailTo"]
							subject = "WAM Run Complete ({0})".format(self.currentJobID)
							sendEmailMsg(message, subject, recipient, username, password, SMTPServer, SMTPPort, useStarttls, logging)

			elif self.opSystem == "Windows":
				with open(stdOutFile,"a+") as out, open(stdErrorFile,"a+") as err:
					try:
						cmd[0] = "C:\\SIMULIA\\Commands\\abaqus.bat"
						self.currentSubProcess = subprocess.Popen(cmd, stdout=out, stderr=err, cwd=cwd)
						self.currentSubProcess.wait()
						logging.info("job {0} has completed".format(self.currentJobID))					
						self.currentSubProcess = None
					except:
						cmd = " ".join(cmd)
						err.write("*** ERROR: command line error\n")
						err.write(str(e)+"\n")
						err.write("Error encountered while executing: {0} \n".format(cmd))
						err.write("\n")

						logging.error("error running Abaqus: {0}".format(self.currentJobID))
						logging.error("error encountered while executing: {0} \n".format(cmd))

			# post job cleanup
			self.currentJobID = None
			self.currentJobNumber = None
			self.currentSubProcess = None

			with self.jobListLock:
				job["InternalUse"]["status"] = "complete"

				# add job to job history
				self.jobHist.insert(0,job)
				self.serializeJobHist()

				# remove job from jobs list
				if job in self.jobs:
					indexToRemove = self.jobs.index(job)
					removedItem = self.jobs.pop(indexToRemove)
					self.serializeJobList()

	## killJob Method
	# looks through all jobs in queue and kills requested jobs
	def killJob(self,jobID,username):
		# normalize jobID input
		jobIDsplit = string.split(jobID,":")
		if len(jobIDsplit) > 1:
			jobNumber = jobIDsplit[0]
			jobName = string.split(jobIDsplit[1],".")[0] # incase .inp was added
			jobID = jobNumber + ":" + jobName
		else:
			jobNumber = jobIDsplit[0]
			jobName = None
			jobID = jobNumber

		msgs = []

		with self.jobListLock:
			for job in self.jobs[::-1]: # iterate backwards so we dont skip jobs
				if jobName == None:
					jobRef = job["InternalUse"]["jobNumber"]
					curJobRef = self.currentJobNumber
				else:
					jobRef = job["InternalUse"]["jobID"]
					curJobRef = self.currentJobID

				if jobRef == jobID:
					job["InternalUse"]["status"] = "killed by %s"%(username)
					self.jobHist.insert(0,job)
					self.serializeJobHist()
					indexToRemove = self.jobs.index(job)
					removedItem = self.jobs.pop(indexToRemove)
					self.serializeJobList()

					# if the job is currently running... SACRIFICE
					if jobID == curJobRef:
						if self.currentSubProcess is not None:
							os.killpg(self.currentSubProcess.pid, signal.SIGTERM)

					msg = "Job {0} killed by {1}".format(job["InternalUse"]["jobID"],username)
					logging.info("job {0} killed by {1}".format(job["InternalUse"]["jobID"],username))

					msgs.append(msg)

		if len(msgs) == 0:
			msg = "*** ERROR: invalid job number: {0}".format(jobID)
			msgs.append(msg)
			logging.error("attempted to kill job, invalid job number: {0}".format(jobID))
		
		return msgs

	## getComputerInfo Method
	# gathers host info to be presented to client
	def getComputerInfo(self):
		logging.info("HPC information requested from client")
		
		# Get total memory and convert from bytes to Gb
		totMem = int(self.mem.total/1024.0 ** 3) # convert from bytes to gb

		jobsQueue = 0
		jobsRunning = 0
		jobList = []
		for job in self.jobs:
			tmp = []
			tmp.append(job["InternalUse"]["clientName"])
			tmp.append(job["InternalUse"]["jobID"])
			if "running" in job["InternalUse"]["status"]:
				now = datetime.datetime.now()
				deltaTime = now - self.start
				hours, remainder = divmod(deltaTime.seconds, 3600)
				minutes, seconds = divmod(remainder, 60)
				deltaTime = ("({0:d}:{1:02d}:{2:02d})".format(hours,minutes,seconds))
				tmp.append("{0} {1}".format(job["InternalUse"]["status"],deltaTime))
				jobsRunning = jobsRunning + 1
			else:
				tmp.append(job["InternalUse"]["status"])
				jobsQueue = jobsQueue + 1
			tmp.append(job["solverFlags"]["cpus"]+job["solverFlags"]["gpus"])
			tmp.append(job["advanced"]["priority"])

			jobList.append(tmp[:])

		jobHistory = []
		for job in self.jobHist:
			tmp = []
			tmp.append(job["InternalUse"]["clientName"])
			tmp.append(job["InternalUse"]["jobID"])
			tmp.append(job["jobName"])
			tmp.append(job["InternalUse"]["status"])
			tmp.append(job["InternalUse"]["submissionTime"])

			jobHistory.append(tmp[:])

		# return needed values
		return [self.hostName, self.cpus, totMem, self.IPaddr, jobList, jobsQueue, jobsRunning, jobHistory]
	
	## loadSerializedJobID Method
	# loads the serialized job ID or creates one if it doesn't exist
	def loadSerializedJobID(self):
		jobIDPath = os.path.join(self.serverScriptDirectory,"jobIDCounter.serpent")
		if os.path.isfile(jobIDPath):
			self.jobID = serpent.load(open(jobIDPath, "rb"))
			logging.info("job ID serpent file opened. Current ID = {0}".format(self.jobID))
		else:
			self.jobID = 0
			serpent.dump(self.jobID, open(jobIDPath, "wb"))
			logging.info("created job ID serpent file: {0}".format(self.jobID))
	
	## serializeJobID Method
	# opens the serialized job ID object to update it
	def serializeJobID(self):
		jobIDPath = os.path.join(self.serverScriptDirectory,"jobIDCounter.serpent")
		with self.jobIDLock:        
			try:
				serpent.dump(self.jobID, open(jobIDPath,"wb"))
				logging.info("job ID serpent file edited. Current ID = {0}".format(self.jobID))
			except:
				logging.error("unable to serialize job ID counter")

	## loadSerializedJobList Method
	# loads the serialized job List or creates one if it doesn't exist
	def loadSerializedJobList(self):
		jobListPath = os.path.join(self.serverScriptDirectory,"jobList.serpent")
		with self.serializedJobListLock:
			if os.path.isfile(jobListPath):
				self.jobs = serpent.load(open(jobListPath,"rb"))
			else:
				self.jobs = []
				serpent.dump(self.jobs, open(jobListPath, "wb"))
				logging.info("created job list serpent file")
	
	## initSerializedJobList Method
	# initializes the job list by clearing any stale jobs from list on daemon startup or creates one if it doesn't exist
	def initSerializedJobList(self):
		jobListPath = os.path.join(self.serverScriptDirectory,"jobList.serpent")
		with self.jobListLock:
			if os.path.isfile(jobListPath):
				self.jobs = serpent.load(open(jobListPath,"rb"))
				for job in self.jobs:
					job["InternalUse"]["status"] = "ERROR"
					logging.info("Job {0} removed from queue (jobList) due to daemon initialization".format(job["InternalUse"]["jobID"]))
					self.jobHist.insert(0,job)
					self.serializeJobHist()
					indexToRemove = self.jobs.index(job)
					removedItem = self.jobs.pop(indexToRemove)
					self.serializeJobList()
			else:
				logging.info("here (else)")
				self.jobs = []
				serpent.dump(self.jobs, open(jobListPath, "wb"))
				logging.info("created job list serpent file")

	## serializeJobHist Method
	# opens the serialized job history list object to update it
	def serializeJobList(self):
		jobListPath = os.path.join(self.serverScriptDirectory,"jobList.serpent")
		with self.serializedJobListLock:
			try:
				serpent.dump(self.jobs, open(jobListPath,"wb"))
			except:
				logging.error("unable to serializeJobList")

	## loadSerializedJobHist Method
	# loads the serialized job history list or creates one if it doesn't exist
	def loadSerializedJobHist(self):
		jobHistPath = os.path.join(self.serverScriptDirectory,"jobHist.serpent")
		logging.info("here: loadSerializedJobHist")
		with self.serializedJobHistLock:
			logging.info("here: with")
			if os.path.isfile(jobHistPath):
				logging.info("here: if")
				self.jobHist = serpent.load(open(jobHistPath,"rb"))
			else:
				logging.info("here: else")
				self.jobHist = []
				serpent.dump(self.jobHist, open(jobHistPath, "wb"))
				logging.info("created job history serpent file")

	## serializeJobHist Method
	# opens the serialized job list object to update it
	def serializeJobHist(self):
		jobHistPath = os.path.join(self.serverScriptDirectory,"jobHist.serpent")
		with self.serializedJobHistLock:
			if len(self.jobHist) > 20:
				self.jobHist.pop()
			try:
				serpent.dump(self.jobHist, open(jobHistPath,"wb"))
			except:
				logging.error("unable to serializeJobHist")

	## loadServerConfFile Method
	# returns configuration json for client
	def loadServerConfFile(self):
		with self.confFileLock:
			filePath = os.path.join(self.serverScriptDirectory,"serverConf.json")
			self.serverConf = parseJSONFile(filePath)

			return self.serverConf

	## loggingSetup Method
	# configure and start logging
	def loggingSetup(self):
		logFile = os.path.join(self.serverScriptDirectory,"logs",self.serverConf["localhost"]["logFileName"])
		maxLogSize = self.serverConf["localhost"]["maxLogSize"] # maximum size of log file in Mb

		if not os.path.isfile(logFile): # check if log file exists and create one if not
			open(logFile, 'a').close()

		logFileSize = os.path.getsize(logFile) # delete log file is larger than max - only occurs during restart
		if logFileSize > maxLogSize*1048576:
			os.remove(logFile)

		for handler in logging.root.handlers[:]: # reset logging handlers incase some dumb dumb came along and messed it all up
			logging.root.removeHandler(handler)

		logging.basicConfig(filename=logFile, level=logging.DEBUG, format='%(asctime)s - %(levelname)s: %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p')

	## connectToNameServer Method
	# connects to name server at the location defined in serverConf.JSON
	# starts a thread which continuously checks the connection to the name server
	def connectToNameServer(self, daemon_uri):
		registerWithNameServer = self.serverConf["nameServer"]["registerWithNameServer"]
		if registerWithNameServer:
			def nsReregister(daemon_uri):
				while 1:
					nsHost = self.serverConf["nameServer"]["nameServerIP"] # name server IP address
					nsPort = self.serverConf["nameServer"]["nameServerPort"] # name server port
					reconnectTime = self.serverConf["nameServer"]["reconnectToNameServer_minutes"] # time in minutes

					try:
						ns = Pyro4.locateNS(host=nsHost,port=nsPort)
						ns.register("WAM.{0}.daemon".format(self.hostName), daemon_uri)
						logging.info("shook hands with naming server at {0}:{1}".format(nsHost,nsPort))

					except:
						if self.serverConf["nameServer"]["quitOnNameServerConnectionError"]:
							logging.error("cannot connect to name server ({0}:{1}), exiting script".format(nsHost,nsPort))
							sys.exit(1)
						logging.error("cannot connect to name server ({0}:{1}), attempting to reconnect in {2} minutes".format(nsHost,nsPort,reconnectTime))
					
					time.sleep(reconnectTime*60)

			self.nsThread = threading.Thread(target=nsReregister, args=(daemon_uri,))
			self.nsThread.setDaemon(False)
			self.nsThread.start()

	## makePath Method
	# allows the client to make a path in the daemons syntax
	def makePath(self,path,folder):
		reqPath = os.path.join(path,folder)
		return reqPath

def main():
	server_daemon = serverDaemon()

	# initialize job list and job history list
	logging.info("Initializing Job List")
	server_daemon.initSerializedJobList()

	# initialize Pyro4
	try: # use network ip addr. if connected to network
		myIP = [(s.connect(('8.8.8.8', 80)), s.getsockname()[0], s.close()) for s in [socket.socket(socket.AF_INET, socket.SOCK_DGRAM)]][0][1]
		daemon = Pyro4.Daemon(host=myIP, port=server_daemon.serverConf["usePortNumber"])
		logging.info("starting daemon on {0}:{1}".format(myIP,server_daemon.serverConf["usePortNumber"]))
	except: # otherwise send error
		logging.error("unable to connect to network, exiting script")
		sys.exit(1)

	daemon_uri = daemon.register(server_daemon,objectId="WAM." + socket.gethostname())
	server_daemon.connectToNameServer(daemon_uri)

	logging.info("daemon started successfully")
	logging.info("registered with name server: uri = {0}".format(daemon_uri))

	daemon.requestLoop()

if __name__=="__main__":
	main()