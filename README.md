![yee](https://github.com/blaykareyano/WAM/blob/master/yeet.JPG "YEET") ![yee](https://github.com/blaykareyano/WAM/blob/master/yeet.JPG "YEET") ![yee](https://github.com/blaykareyano/WAM/blob/master/yeet.JPG "YEET") ![yee](https://github.com/blaykareyano/WAM/blob/master/yeet.JPG "YEET") ![yee](https://github.com/blaykareyano/WAM/blob/master/yeet.JPG "YEET")

# Workload Allocation Manager

## Summary
WAM centralizes job submission queues for multiple independent computational machines. A user controlled client computer (WAM Client) manages the queue and distribution of work to remote computational machines (WAM Daemon). Communication between the client and server(s) is enabled by the 3rd party package: [Pyro4](https://pyro4.readthedocs.io/en/stable/index.html "Pyro4 Documentation").

## Components
### WAM Daemon
Runs on all computational machines

Features:
- Collection of machine information including core count, memory, and status
- Job control execution including kill and submit commands
- Optional email notification on job completion

### WAM Client
Runs on the host machine through a command terminal

Features:
- Gathers information about active servers on the network
- Acts as an user interface for job controls and monitoring
- Transfer of input files and output files to and from the server and client machines

### Pyro4 Name Server
Acts as a phone book which directs communication between a client and the servers.

More information can be found on the Pyro4 website: [Pyro4 Documentation](https://pyro4.readthedocs.io/en/stable/index.html "Pyro4 Documentation")


### Serpent Files
- jobIDCounter.serpent - keeps a counter going for job IDs on each server
- jobList.serpent - keeps a running list of jobs in the queue and running for each server
---
