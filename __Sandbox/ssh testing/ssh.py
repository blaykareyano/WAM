import os
import sys
import platform
import subprocess
import re, fnmatch
from tabulate import tabulate

# This is to test sending some files using ssh or scp protocols using python standard libraries.
# wish me luck

class frontEndClient(object):
	def __init__(self):
		# Variables
		self.clientScriptDirectory = os.path.dirname(os.path.realpath(__file__)) # directory of this file
		self.jsonFileName = None	# define default jsonFileName
		self.opSystem = platform.system()

	## findFiles Method
	# Returns all filenames from path (where) with given shell pattern (which)
	def findFiles(self,which,where="."):
		rule = re.compile(fnmatch.translate(which), re.IGNORECASE) # compile regex pattern into an object
		return [name for name in os.listdir(where) if rule.match(name)]

	def sshFiles(self,files,host,user,pw,outDir):
		destination = host + ":" + outDir
		if self.opSystem == "Windows":
			for file in files:
				p = subprocess.Popen(["pscp","-scp", "-l", user, "-pw", pw, file, destination])
				p.wait()
		elif self.opSystem == "Linux":
			pass
		else:
			print("*** ERROR: Incompatible operating system. Exiting.")
			sys.exit(1)

	## findSimulationFiles Method
	# Searches current directory for all simulation job input files
	# Returns a list of job paths
	# Only searching for Abaqus *.inp files (for now)
	def findSimulationFiles(self):
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
			jobFiles.append(os.path.join(currentDirectory,inputFile))
			jobTable.append(tmp[:])

		# if no job files (*.inp) found then return an error
		if not jobFiles:
			print("*** ERROR: no Abaqus input files found")
			sys.exit(1)

		# Let's go ahead and toss the JSON file into the mix too
		jsonPath = os.path.join(currentDirectory,"abaqusSubmit.json")
		jobFiles.append(jsonPath)

		self.sshFiles(jobFiles,"cougar","analysis","pA55word$","/home/analysis/Run/Blake/WAM")

def main():
	testies = frontEndClient()

	testies.findSimulationFiles()

if __name__=="__main__":
	main()