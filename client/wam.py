#!/usr/bin/python

# Futures
from __future__ import print_function

# Standard Libraries
import sys
import os
import getpass
import platform
import subprocess
import threading
import argparse
from argparse import RawTextHelpFormatter
import string
import re, fnmatch
import json
import winsound
from subprocess import check_output
from string import Template

# 3rd Party Packages
import Pyro4
from tabulate import tabulate

# Local Source Packages
from utils.parseJSONFile import parseJSONFile

# Development Version
version = 0.4

class frontEndClient(object):
	def __init__(self, userArgs):
		# Define variables and load configuration file
		self.opSystem = platform.system()
		self.userName = getpass.getuser()
		self.clientScriptDirectory = os.path.dirname(os.path.realpath(__file__)) # directory of this file
		self.jsonFileName = None	# define default jsonFileName initialization
		self.confFileLock = threading.Lock()
		self.loadClientConfFile()
		self.defaultEmail = self.clientConf["defaults"]["email"]
		self.defaultFileTypes = self.clientConf["defaults"]["fileTypes"]
		self.defaultMonitorFileTypes = self.clientConf["defaults"]["monitorFileTypes"]
		self.runDirectory = None	# folder that job is created in
		self.jobDirectory = None	# folder that job in run in

		# Parser arguments and definitions
		self.parser = argparse.ArgumentParser(prog="wam",description="Client end of the WAM ecosystem. Connects to other server daemons on the Pyro4 Network allowing a user to manage the queue and distribution of work to remote computational machines.\nhttps://github.com/blaykareyano/WAM\nBlake Arellano, 2020", formatter_class=RawTextHelpFormatter) # \TODO add in description and epilog

		# Job submission arguments
		self.parser.add_argument("-bat","--batch", help="Scan current directory for all valid Abaqus input files and submit all selected.\nAdditional Arguments: [-cpus [#]] [-gpus [#]] [-n [hostname]] [-p [#]] [-e]", action="store_true")
		self.parser.add_argument("-a", "--all", help="Submit all files in directory. \nAdditional Arguments: [-cpus [#]] [-gpus [#]] [-n [hostname]] [-p [#]] [-e]", action="store_true")
		self.parser.add_argument("-j", "--job", help="Submit specified job. \nAdditional Arguments: [-cpus [#]] [-gpus [#]] [-n [hostname]] [-p [#]] [-e]", type=str, nargs='?', metavar="jobName", action="store")
		self.parser.add_argument("-cpus", help="Number of cores to be used in the analysis.", type=int, nargs='?', metavar="#", action="store")
		self.parser.add_argument("-gpus", help="Number of gpus to be used in the analysis.", type=int, nargs='?', metavar="#", action="store")
		self.parser.add_argument("-n","--host", help="Host name of the machine that will run the job (i.e. cougar, leopard, HPC-02).", type=str, nargs='?', metavar="hostname", action="store")
		self.parser.add_argument("-p","--priority", help="Set the job priority. Default = 1, high priority = 0, low priority = 2.", type=int, nargs='?', metavar="#", default=1, action="store")
		self.parser.add_argument("-e","--email", help="Email address for job completion email to be sent to using email from clientConf.json.", action="store_const", const=self.defaultEmail)

		# Other job controls
		self.parser.add_argument("-get", help="Retrieve job given job id once completed. Files are placed into current directory. \nAdditional Arguments: [-n [hostname]]", type=str, nargs='?', metavar="job# or job#:jobName", action="store")
		self.parser.add_argument("-m","--monitor", help="Checks on job status given job id. Retrieves all status files (*.msg, *.dat, *.sta, *.log) and places into current directory. \nAdditional Arguments: [-n [hostname]]", type=str, nargs='?', metavar="job# or job#:jobName", action="store")
		self.parser.add_argument("-k", "--kill", help="Kill job by job id. Entering the only the job number kills all jobs associated with that job number, entering both the job number and job name will only kill the specified job. If killing multiple jobs, separate each job ID with a space. \nAdditional Arguments: [-n [hostname]]", type=str, nargs='+', metavar="job# or job#:jobName", action="store")
		
		# Info request arguments
		self.parser.add_argument("-cstat","--computeStats", help="Check basic info (IP, cores, available memory, number of jobs in queue) of all machines on the network.", action="store_true")
		self.parser.add_argument("-qstat","--queueStats", help="Check job queues on all machines connected to the name server. \nAdditional Arguments: [-n [hostname]]", action="store_true")
		self.parser.add_argument("-hist","--history", help="Check job history on all machines connected to the name server. \nAdditional Optional Arguments: [-n [hostname]]", action="store_true")
		self.parser.add_argument("-tc","--tokenConvert", help="Displays cores to license tokens conversion table.",action="store_true")
		self.parser.add_argument("-about", help="See WAM version, author, and license info.", action="store_true")
		self.parser.add_argument("-ham", help="Try it and find out.... Sound on recommended.", action="store_true")
		
		# if no inputs given display WAM help
		if len(sys.argv)==1: 
			self.parser.print_help()
			sys.exit(1)

		# assign arguments to a variable
		userArgs = self.parser.parse_args()

		# Execute provided arguments
		if userArgs.batch:
			self.submitBatch(userArgs.all,userArgs.host,userArgs.cpus,userArgs.gpus,userArgs.email,userArgs.priority)
			sys.exit(0)

		if userArgs.job:
			self.submitJob(userArgs.job,userArgs.host,userArgs.cpus,userArgs.gpus,userArgs.email,userArgs.priority)
			sys.exit(0)

		if userArgs.get:
			self.getJob(userArgs.get,userArgs.host)
			sys.exit(0)

		if userArgs.monitor:
			self.monitor(userArgs.monitor,userArgs.host)
			sys.exit(0)

		if userArgs.kill:
			self.killJob(userArgs.kill,userArgs.host)
			sys.exit(0)

		if userArgs.computeStats:
			self.queryAllServers()
			sys.exit(0)

		if userArgs.queueStats:
			self.queryAllQueues()
			sys.exit(0)

		if userArgs.history:
			self.pullJobHistory(userArgs.host)
			sys.exit(0)

		if userArgs.tokenConvert:
			self.tokenConvert()
			sys.exit(0)

		if userArgs.about:
			self.printAbout()
			sys.exit(0)

		if userArgs.ham:
			self.ham()
			sys.exit(0)

	## findSimulationFiles Method
	#  Searches current directory for all simulation job input files and takes user input on which to run
	#  Returns a list of job paths
	#  Only searching for Abaqus *.inp files (for now)
	def findSimulationFiles(self,selectAll):
		# Define variables
		currentDirectory = os.getcwd()
		jobFiles = []
		jobTable = []

		# Find all files in currentDirectory with *.inp extension
		fileExt = "*.inp"
		inputFiles = self.findFiles(fileExt,currentDirectory)

		# Add all found files to jobFiles list
		for inputFile in inputFiles:
			tmp = []
			tmp.append(inputFile)
			jobFiles.append(os.path.join(inputFile))
			jobTable.append(tmp[:])

		# if no job files (*.inp) found then return an error
		if not jobFiles:
			print("*** ERROR: no Abaqus input files found")
			sys.exit(1)

		if selectAll:
			selectedJobs = jobFiles
			return selectedJobs

		while True:
			# present list of found jobs to the user and take input
			print("\n")
			print(tabulate(jobTable,headers=["#","Job Name"],showindex=True,tablefmt="rst"))
			selectedJobIndicesStr = raw_input("Enter job #'s to submit below or type help for more info:\n")

			# return help information
			if selectedJobIndicesStr == 'help':
				print("""\n
Job numbers are listed in the left most column adject to the input file name.
Input job numbers you wish to submit in a comma-separated list (e.g. 0,2,4 to run job #'s 0, 2, and 4).
	- Spaces will be ignored and are not required.
	- Any characters other than commas and integers will throw an error.
If all input files are desired to be run, enter: all
To quit the procedure enter: exit
					\n""")
				selectedJobIndicesStr = raw_input("Enter job #'s to submit below or type help for more info:\n")

			# select all jobs in directory
			if selectedJobIndicesStr == 'all':
				selectedJobs = jobFiles
				break

			elif selectedJobIndicesStr == 'exit':
				sys.exit(0)
			
			# select user requested jobs
			else:
				selectedJobIndices = selectedJobIndicesStr.strip().split(',')

				try:
					selectedJobIndices = [int(jobIndex) for jobIndex in selectedJobIndices]
					selectedJobs = []
					for index in selectedJobIndices:
						selectedJobs.append(jobFiles[index])
					break

				except ValueError as e:
					print("\n*** ERROR: {0}".format(e))
					print("    Enter 'help' for information on how to select input files")
					print("    Enter 'exit' to quit")
					pass
		
		print("\n")
		return selectedJobs

	## scpJobFiles
	#  sends job files to the server daemon which will run job
	#  \todo linux scp command [Popen]
	def scpJobFiles(self,files,host):
		print("Transferring files to: {0}:{1}".format(host,self.jobDirectory))
		userName = self.serverConfFile["localhost"]["userName"]
		pw = self.serverConfFile["localhost"]["password"]
		destination = host + ":" + self.jobDirectory
		if self.opSystem == "Windows":
			for file in files:
				p = subprocess.Popen(["pscp","-scp", "-l", userName, "-pw", pw, file, destination])
				p.wait()
		elif self.opSystem == "Linux":
			pass
		else:
			print("*** ERROR: Incompatible operating system, exiting")
			sys.exit(1)

	## submitBatch Method
	#  takes input from parser and submits jobs on selected server
	def submitBatch(self,selectAll,host,cpus,gpus,email,priority):
		# get current working directory
		currentDirectory = os.getcwd()

		# Find all simulation files in current directory
		inputFiles = self.findSimulationFiles(selectAll)

		# open template job info JSON file
		with open(os.path.join(self.clientScriptDirectory,r"utils",r"abaqusSubmit.json.tmpl"), "r") as tmp:
			jsonTemplate = tmp.read()

		# check user input
		userInput = self.checkUserInput(host,cpus,gpus,email,priority)
		host = userInput["host"]
		
		# create a dictionary with job submission information
		jobInfo = {}
		jobInfo["emailAddress"] = userInput["email"]
		jobInfo["nCPUs"] = userInput["cpus"]
		jobInfo["nGPUs"] = userInput["gpus"]
		jobInfo["jobFiles"] = json.dumps(inputFiles)
		jobInfo["clientUserName"] = self.userName
		jobInfo["priority"] = userInput["priority"]
		jobInfo["version"] = version

		# write dictionary to JSON template file
		jsonOutFile = Template(jsonTemplate).substitute(jobInfo)

		if self.jsonFileName is None:
			self.jsonFileName = os.path.join(currentDirectory,"abaqusSubmit.json")

		with open(self.jsonFileName, "w") as tmp:
			tmp.write(jsonOutFile)

		inputFiles.append(self.jsonFileName)

		# validate input file info
		jobData = parseJSONFile(self.jsonFileName)
		assert "InternalUse" in jobData.keys(), "JSON file ({0}) is missing the InternalUse block.".format(jsonFile)
		assert jobData["InternalUse"]["jsonFileType"] == "abaqus", "Invalid job type: {0}".format(jobData["InternalUse"]["jsonFileType"])

		# connect to defined host
		connectedServer = self.connectToServer(host)

		# get configuration file from daemon
		self.loadServerConfFile(host)

		# create job ID with server
		try:
			self.runDirectory = self.serverConfFile["localhost"]["runDirectory"]
			[jobID, self.jobDirectory] = connectedServer.jobInitialization(self.runDirectory)
			print("Job ID: {0}".format(jobID))
		except Exception as e:
			print("*** ERROR: Unable to initialize job: {0}".format(e))
			sys.exit(1)

		# send job files to server
		self.scpJobFiles(inputFiles, host)

		# submit job files
		try:
			connectedServer.jobDefinition(self.jobDirectory)
			print("{0} job(s) submitted to {1} for analysis".format(len(inputFiles)-1,host))
		except Exception as e:
			print("*** ERROR: Unable to submit job: {0}".format(e))
			sys.exit(1)

	## submitJob Method
	#  does same as submit batch, but for only one defined job
	def submitJob(self,jobName,host,cpus,gpus,email,priority):
		# get current working directory
		currentDirectory = os.getcwd()

		# create list of files to send over
		inputFiles = []
		jobNameSplit = string.split(jobName,".")
		if len(jobNameSplit)>1:
			inputFiles.append(jobName)
		else:
			jobName = jobName + ".inp"
			inputFiles.append(jobName)

		# open template job info JSON file
		with open(os.path.join(self.clientScriptDirectory,r"utils",r"abaqusSubmit.json.tmpl"), "r") as tmp:
			jsonTemplate = tmp.read()

		# check user input
		userInput = self.checkUserInput(host,cpus,gpus,email,priority)
		host = userInput["host"]
		
		# create a dictionary with job submission information
		jobInfo = {}
		jobInfo["emailAddress"] = userInput["email"]
		jobInfo["nCPUs"] = userInput["cpus"]
		jobInfo["nGPUs"] = userInput["gpus"]
		jobInfo["jobFiles"] = json.dumps(inputFiles)
		jobInfo["clientUserName"] = self.userName
		jobInfo["priority"] = userInput["priority"]
		jobInfo["version"] = version

		# write dictionary to JSON template file
		jsonOutFile = Template(jsonTemplate).substitute(jobInfo)

		if self.jsonFileName is None:
			self.jsonFileName = os.path.join(currentDirectory,"abaqusSubmit.json")

		with open(self.jsonFileName, "w") as tmp:
			tmp.write(jsonOutFile)

		inputFiles.append(self.jsonFileName)

		# validate input file info
		jobData = parseJSONFile(self.jsonFileName)
		assert "InternalUse" in jobData.keys(), "JSON file ({0}) is missing the InternalUse block.".format(jsonFile)
		assert jobData["InternalUse"]["jsonFileType"] == "abaqus", "Invalid job type: {0}".format(jobData["InternalUse"]["jsonFileType"])

		# connect to defined host
		connectedServer = self.connectToServer(host)

		# get configuration file from daemon
		self.loadServerConfFile(host)

		# create job ID with server
		try:
			self.runDirectory = self.serverConfFile["localhost"]["runDirectory"]
			[jobID, self.jobDirectory] = connectedServer.jobInitialization(self.runDirectory)
			print("Job ID: {0}".format(jobID))
		except Exception as e:
			print("*** ERROR: Unable to initialize job: {0}".format(e))
			sys.exit(1)

		# send job files to server
		self.scpJobFiles(inputFiles, host)

		# submit job files
		try:
			connectedServer.jobDefinition(self.jobDirectory)
			print("{0} job(s) submitted to {1} for analysis".format(len(inputFiles)-1,host))
		except Exception as e:
			print("*** ERROR: Unable to submit job: {0}".format(e))
			sys.exit(1)

	## checkUserInput Method
	#  ensures all job input info is accounted for
	def checkUserInput(self,host,cpus,gpus,email,priority):
		# check to make sure a host was specified
		if host == None:
			while True:
				host = raw_input("Specify desired host (by name) or enter 'list' to view all active servers: ")
				if host == "list":
					self.queryAllServers()
				elif host:
					break

		if cpus == None:
			while True:
				cpus = raw_input("Specify desired cpus or enter list to view active servers and their core counts or tc to see the token converter: ")
				if cpus == "list":
					self.queryAllServers()
				elif cpus == "tc":
					self.tokenConvert()
				elif cpus:
					break

		if gpus == None:
			while True:
				gpus = raw_input("Specify desired gpus: ")
				if gpus:
					break

		if email == None:
			while True:
				email = raw_input("Email desired upon job completion? (y/n): ")
				if email == "y":
					email = self.defaultEmail
					break
				elif email == "n":
					email = None
					break

		if priority == None:
			while True:
				priority = raw_input("Specify desired priority (0=high; 2=low): ")
				if priority >= 0 and priority <= 2:
					break

		userInputDict = {'host':host,'cpus':cpus,'gpus':gpus,'email':email,'priority':priority}
		return userInputDict	

	## getJob Method
	#  retrieves job files for specified job ID
	def getJob(self,jobID,host):
		# check to make sure a host was specified
		if host == None:
			while True:
				host = raw_input("Specify desired host (by name) or enter 'list' to view all active servers:\n")
				print("\n")
				if host == "list":
					self.queryAllServers()
				elif host:
					break

		# load server config
		self.loadServerConfFile(host)
		self.runDirectory = self.serverConfFile["localhost"]["runDirectory"]

		# normalize jobID input
		jobIDsplit = string.split(jobID,":")
		if len(jobIDsplit) > 1:
			jobNumber = jobIDsplit[0]
			jobName = string.split(jobIDsplit[1],".")[0] # incase .inp was added
		else:
			jobNumber = jobIDsplit[0]
			jobName = None

		# define job folder
		connectedServer = self.connectToServer(host)
		jobFolder = connectedServer.makePath(self.runDirectory,jobNumber)

		# transfer files
		print("Transferring job {0} from {1}:{2}".format(jobID,host,jobFolder))
		userName = self.serverConfFile["localhost"]["userName"]
		pw = self.serverConfFile["localhost"]["password"]
		destination = os.getcwd()

		if jobName == None:
			files = self.defaultFileTypes
			if self.opSystem == "Windows":
				for file in files:
					source = host + ":" + jobFolder + "/" + file
					p = subprocess.Popen(["pscp", "-l", userName, "-pw", pw, source, destination])
					p.wait()
			elif self.opSystem == "Linux":
				pass
			else:
				print("*** ERROR: Incompatible operating system, exiting")
				sys.exit(1)
		else:
			files = [jobName + fileExt[1:] for fileExt in self.defaultFileTypes]
			files = files[:-1]
			files.append("out.log")
			files.append("error.log")
			if self.opSystem == "Windows":
				for file in files:
					source = host + ":" + jobFolder + "/" + file
					p = subprocess.Popen(["pscp", "-l", userName, "-pw", pw, source, destination])
					p.wait()
			elif self.opSystem == "Linux":
				pass
			else:
				print("*** ERROR: Incompatible operating system, exiting")
				sys.exit(1)

	## monitor Method
	#  retrieves status files for job, displays out.log to user
	def monitor(self,jobID,host):
		# check to make sure a host was specified
		if host == None:
			while True:
				host = raw_input("Specify desired host (by name) or enter 'list' to view all active servers:\n")
				print("\n")
				if host == "list":
					self.queryAllServers()
				elif host:
					break
		
		# load server config
		self.loadServerConfFile(host)
		self.runDirectory = self.serverConfFile["localhost"]["runDirectory"]

		# normalize jobID input
		jobIDsplit = string.split(jobID,":")
		if len(jobIDsplit) > 1:
			jobNumber = jobIDsplit[0]
			jobName = string.split(jobIDsplit[1],".")[0] # incase .inp was added
		else:
			jobNumber = jobIDsplit[0]
			jobName = None

		# define job folder
		connectedServer = self.connectToServer(host)
		jobFolder = connectedServer.makePath(self.runDirectory,jobNumber)

		# transfer files
		print("Transferring files {0} from {1}:{2}".format(jobID,host,jobFolder))
		userName = self.serverConfFile["localhost"]["userName"]
		pw = self.serverConfFile["localhost"]["password"]
		destination = os.getcwd()

		if jobName == None:
			files = self.defaultMonitorFileTypes
			if self.opSystem == "Windows":
				for file in files:
					source = host + ":" + jobFolder + "/" + file
					p = subprocess.Popen(["pscp", "-l", userName, "-pw", pw, source, destination])
					p.wait()
			elif self.opSystem == "Linux":
				pass
			else:
				print("*** ERROR: Incompatible operating system, exiting")
				sys.exit(1)
		else:
			files = [jobName + fileExt[1:] for fileExt in self.defaultMonitorFileTypes]
			files = files[:-1]
			files.append("out.log")
			files.append("error.log")
			if self.opSystem == "Windows":
				for file in files:
					source = host + ":" + jobFolder + "/" + file
					p = subprocess.Popen(["pscp", "-l", userName, "-pw", pw, source, destination])
					p.wait()
			elif self.opSystem == "Linux":
				pass
			else:
				print("*** ERROR: Incompatible operating system, exiting")
				sys.exit(1)
		tmp = open(os.path.join(destination,"out.log"),"r")
		tmp = tmp.read()
		print("\n" + tmp)

	## killJob method
	#  kills job given a jobID
	def killJob(self,jobIDs,host):
		# check to make sure a host was specified
		if host == None:
			while True:
				host = raw_input("Specify desired host (by name) or enter 'list' to view all active servers:\n")
				print("\n")
				if host == "list":
					self.queryAllServers()
				elif host:
					break

		connectedServer = self.connectToServer(host)

		for jobID in jobIDs:
			msgs = connectedServer.killJob(jobID,self.userName)
			for msg in msgs:
				print(msg)

	## queryAllServers Method
	# Looks through all servers and gathers machine info (cores, avail. memory, IP addr)
	def queryAllServers(self):
		sys.excepthook = Pyro4.util.excepthook
		
		# get licensing info
		self.getLicenseInfo()

		# Initialize the table
		headers = ["Host Name", "IP Address", "Cores", "Total Memory", "Job Queue Length"]
		table = []

		# Find all daemon servers and loop through them
		daemons = self.findServers()

		for daemon_uri, daemonName in daemons:
			currentServer = Pyro4.Proxy(daemon_uri)

			try:
				[compName, cpus, mem, IP, jobList, jobsQueue, jobsRunning, jobHist] = currentServer.getComputerInfo()	
				tmp = []
				tmp.append(compName)
				tmp.append(IP)
				tmp.append(cpus)
				tmp.append(str(mem) + " Gb")
				tmp.append("Running: {0}, Queue: {1}".format(jobsRunning,jobsQueue))
				table.append(tmp[:])

			except Exception as e:
				tmp = []
				tmp.append(daemonName.lstrip("WAM.").rstrip(".daemon"))
				tmp.append("ERROR")
				tmp.append("ERROR")
				tmp.append("ERROR")
				tmp.append("ERROR")
				table.append(tmp[:])
				print("*** ERROR: {0}".format(e))
				pass

		print(tabulate(table, headers, tablefmt="rst", numalign="center", stralign="center"))

	## queryAllQueues Method
	#  Looks through all servers and gathers queue info (host, user, job ID, status)
	def queryAllQueues(self):
		sys.excepthook = Pyro4.util.excepthook

		# get licensing info
		self.getLicenseInfo()

		# Initialize the table
		headers = ["Host Name", "Username", "Job ID", "Status", "Priority", "Est. Tokens"]
		table = []

		# Find all daemon servers and loop through them
		daemons = self.findServers()

		for daemon_uri, daemonName in daemons:
			currentServer = Pyro4.Proxy(daemon_uri)
			try:
				[compName, cpus, mem, IP, jobList, jobsQueue, jobsRunning, jobHist] = currentServer.getComputerInfo()
				if jobList:
					for job in jobList:

						if job[4] == 0:
							priority = "High"
						elif job[4] == 1:
							priority = "Med"
						else:
							priority = "Low"

						tmp = []
						tmp.append(compName) # hostname
						tmp.append(job[0]) # username
						tmp.append(job[1]) # job ID
						tmp.append(job[2]) # status
						tmp.append(priority) # job priority
						tmp.append(str(int(5*job[3]**0.422))) # cores being used (cpus and gpus)
						table.append(tmp[:])

			except Exception as e:
				tmp = []
				tmp.append(daemonName.lstrip("WAM.").rstrip(".daemon"))
				tmp.append("ERROR")
				tmp.append("ERROR")
				tmp.append("ERROR")
				tmp.append("ERROR")
				tmp.append("ERROR")
				table.append(tmp[:])
				print("*** ERROR: {0}".format(e))
				pass

		print(tabulate(table, headers, tablefmt="rst", numalign="center", stralign="center"))

	def pullJobHistory(self,host):
		# Initialize the table
		headers = ["Host Name", "Username", "Job Number", "Job Name", "Status", "Submission Time"]
		table = []

		if host == None:
			# Find all daemon servers and loop through them
			daemons = self.findServers()

			for daemon_uri, daemonName in daemons:
				currentServer = Pyro4.Proxy(daemon_uri)
				try:
					[compName, cpus, mem, IP, jobList, jobsQueue, jobsRunning, jobHist] = currentServer.getComputerInfo()
					if jobHist:
						for job in jobHist:
							tmp = []
							tmp.append(compName) # hostname
							tmp.append(job[0]) # username
							tmp.append(job[1]) # job number
							tmp.append(job[2]) # job name
							tmp.append(job[3]) # status
							tmp.append(job[4]) # submission time
							table.append(tmp[:])

				except Exception as e:
					tmp = []
					tmp.append(daemonName.lstrip("WAM.").rstrip(".daemon"))
					tmp.append("ERROR")
					tmp.append("ERROR")
					tmp.append("ERROR")
					tmp.append("ERROR")
					table.append(tmp[:])
					print("*** ERROR: {0}".format(e))
					pass

		else:
			currentServer = self.connectToServer(host)
			try:
				[compName, cpus, mem, IP, jobList, jobsQueue, jobsRunning, jobHist] = currentServer.getComputerInfo()
				if jobHist:
					for job in jobHist:
						tmp = []
						tmp.append(compName) # hostname
						tmp.append(job[0]) # username
						tmp.append(job[1]) # job number
						tmp.append(job[2]) # job name
						tmp.append(job[3]) # status
						tmp.append(job[4]) # submission time
						table.append(tmp[:])

			except Exception as e:
				tmp = []
				tmp.append(daemonName.lstrip("WAM.").rstrip(".daemon"))
				tmp.append("ERROR")
				tmp.append("ERROR")
				tmp.append("ERROR")
				tmp.append("ERROR")
				table.append(tmp[:])
				print("*** ERROR: {0}".format(e))
				pass

		print(tabulate(table, headers, tablefmt="rst", numalign="center", stralign="center"))

	## tokenConvert Method
	#  Returns table of cores to abaqus tokens
	def tokenConvert(self):
		cores = [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18]
		tokens = [int(5*core**0.422) for core in cores]
		cores.insert(0,"Cores")
		tokens.insert(0,"Tokens")

		table = []
		table.append(cores)
		table.append(tokens)

		print(tabulate(table,tablefmt="presto",numalign="center"))

	## printAbout Method
	#  Pretty self explanatory I believe
	def printAbout(self):
		print("""
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
WAM - Workload Allocation Manager - Version {0}
GitHub: https://github.com/blaykareyano/WAM
Copyright (C) 2020 - Blake Arellano - blake.n.arellano@gmail.com
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
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
=================================================================
        """.format(str(version)))

	## connectToServer Method
	#  used Pyro to connect to defined server
	#  returns Pyro proxy object
	def connectToServer(self,host):
		sys.excepthook = Pyro4.util.excepthook
		nsIP = self.clientConf["nameServer"]["nsIP"]
		nsPort = self.clientConf["nameServer"]["nsPort"]
		ns = Pyro4.locateNS(host=nsIP,port=nsPort)
		daemon_uri = ns.lookup("WAM." + host + ".daemon")
		connectedServer = Pyro4.Proxy(daemon_uri)
		return connectedServer

	## findServers Method
	#  Looks through the name server to find all registered servers
	def findServers(self):
		sys.excepthook = Pyro4.util.excepthook

		nsHost = self.clientConf["nameServer"]["nsIP"]
		nsPort = self.clientConf["nameServer"]["nsPort"]

		ns = Pyro4.locateNS(host=nsHost,port=nsPort)

		daemon_uris = []
		daemonNames = []

		for daemonName, daemon_uri in ns.list(prefix="WAM.").items():
			daemon_uris.append(daemon_uri)
			daemonNames.append(daemonName)

		if not daemon_uris:
			print("*** ERROR: No server daemons found")
		
		daemons = zip(daemon_uris,daemonNames)
		return daemons

	## findFiles Method
	#  Returns all filenames from path (where) with given shell pattern (which)
	def findFiles(self,which,where="."):
		rule = re.compile(fnmatch.translate(which), re.IGNORECASE) # compile regex pattern into an object
		return [name for name in os.listdir(where) if rule.match(name)]

	def getLicenseInfo(self):
		try:
			licenseText = check_output('abaqus licensing -ru', shell=True)
			lines = []
			for line in licenseText.split('\n'):
				if "Users of abaqus" in line:
					lines.append(line)

			print("\n",lines[1])
		except Exception as e:
			print("\nUnable to get license info: {0}".format(e))

	def loadClientConfFile(self):
		with self.confFileLock:
			filePath = os.path.join(self.clientScriptDirectory,"clientConf.json")
			self.clientConf = parseJSONFile(filePath)

	def loadServerConfFile(self,host):
		try:
			connectedServer = self.connectToServer(host)
			self.serverConfFile = connectedServer.loadServerConfFile()
		except Exception as e:
			print("*** ERROR: Unable to get server configuration file: {0}".format(e))
			sys.exit(1)

	def ham(self):
		print(r"""
			                           `::..   .
                       `?XXX.  `T{/:.   %X/!!x "?x.
                         "4{7@( '!+!!X(:.`4!!X!x.?h7h
                     `!(:. ~!!!f(~!!!+!!{{.'~+h!tX!!?hh:.
                '`X!.  !(d!X!!H!?{{``"!:?{{!{X*!?tX!!H*))h.
              ...  '!X(!X!{{?@f!!!{!{x.!!%!!!%!!!)@Thh!!X)!).
               ^!!!{:!(((!!: ~((({!!!h+!{{!X!+%?+{!!?!+)!+X(!+
           -    `\tXX{(~!!!!!:.!.%%(!!!!!!!!!X!))!!!!X%``%!!!(>
           ^X>:x. {!!!!X: ~!!*!{!!!{!~!X!)%!{!!!)?@!!!?!)?!!!>~
             `X(!!:!!!{{(!!.)!%(:\!!:%~!~\!t!! `H!)~~!!!!!!(?@
              `!X: `)!!!C44XX!!!.%%.X:>-> %!!X! /!~!.'!> !S!!!
          +{..  \X%\.'{??X!!!t!!~!!{!~!~'.!~~~ -~` {> !~ /!X`
            `X!XXM!!4!%\(4!!!!%(`,zccccd$$$$$$$$$ccx ` .~
              "XLS@!)!!%L44X!!! d$$$$$$$$$$$$$$$$$$$,  '^
               `!X?%:!!??X!4?*';$$$$$$$$$$$$$$$$$$$$$
              `iXM:!!?Xt!XH!!! 9$$$$$$$$$$$$$$$$$$$$$
               `X3tiXS#?WH!X!! $$$$$$$$$$$$$$$$$$$$$$
               .MX?*StXX?X!!W? $$$$$$$>?$$$$$$$$$$$$
                8??M%T%' r `  ;$$$$$$$$$,?$$$$$$$$$F
                'StMX!': J$$d$$$$$$$$$$$$h ?$$$$$$"
                 tM9MH d$$$$$$$$$$$$$$C???r{$$$F,r
                 4M?t':$$$$$$$$$$$$$$$$h. $$$,cP"
                 'M>.d$$$$$$$$$$$$$$$$$>d$$${.,
                  ,d$$$$$$$$$$$$$$$$$'cd$$$$r"
                  `$$$$$$$$$$$$$$$??$Jcii`?$h
                   $$$$$$$$$$$$$F,;;, "?h,`$$h
                  j$$$$$$$$$$$$$.CC>>>>c`"  `"        ..,g q,
               .'!$$$$$$$$$$$$$' `''''''            aq`?g`$.Bk
           ,- '  "?$$$$$$$$$$$$$$d$$$$$c, .         .)od$$$$$$
      , -'           `""'   `"?$$$$$$$$$??=      .d$$$$$$$$F'
    ,'                           `??$$P       .ed$$P""   `
   ,                                `.      z$$$"
   `:dbe,                          x,/    e$$F'
   :$$$$P'`>                       $F  z$$$"
  d$$$P"'  >                       $Fe$$$"
.$$$?F     ;                       $$$$"
$$$$$$eeu. >                       >P"
 `""???$$$$$eu,._''uWb,            )
           `""??$P$$$$$$b.         :
            >     ?$$$"'           {
            F      `"              `:
            >                       `>
            >                        ?
           J                          :
           X                ..  .     ?
           "{ 4{!~;/'!>{`~{>~.>! ~! '"
            '>!>=.%=.;~~>~4~`{'>>>~!
             4'!/>!\\!{~~:/{;!{;`;/=':
             `=;!~:`~!>{.-; "(>=.':!;'
              :;=.~{`;`~>!~> ?!/>>~!!{'
              ~:~'!!;`;`~:>); ;(.uJL!~~
                >L.(.:,L;L:-+d$$$$$$
                :4$$$$$$$L   ?$$#$$$>
                 '$$$B$$$>    $$$MB$&
                  $$$$$$$      $$$@$F
                  `$$$$$$>     R$$$$
                   $$$$$$     {$$@$P
                   $R$$$R     `!)=!>
                   $$$6T       $$$$'
                   $$R$B      ;$$$F,._
                   !=!(!    .'        ``= .
                   $$$$F    (.             '\
                 ,{$$$$(      ``~'`` --:.._.,)
                ;   ``  `-.
                (          "\.
                 ` -{._       ".
                       `~:,._ .: """)

		# HAM HORRRNNNNN
		HAM = os.path.join(self.clientScriptDirectory,"utils","HAM.wav")
		winsound.PlaySound(HAM, winsound.SND_FILENAME)

def main():
	front_end_client = frontEndClient(sys.argv)

if __name__=="__main__":
	main()