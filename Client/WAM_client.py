#!/usr/bin/python

## WAM_client Package
# gives commands to selection daemon (computational machine) to run abaqus jobs



version = 0.0 	# current version number

## WAM Client Class:
# Contains all methods for WAM daemon  
class WAM_client(object):
	
	## __init__ method
	# initialize the values of instance members for the new object  
	def __init__(self):