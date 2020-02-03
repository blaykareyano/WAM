|~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~|
| Instructions for installation of Pyro4 naming server 	|
| Blake Arellano - 2020									|
|~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~|

*** Only install on front end client machine
*** Having more than one naming server running is bad m'kay

1-) install Pyro4 and other needed packages:
	a-) install python packaging library 
		$ sudo yum install python-setuptools
	b-) install python package installer pip
		$ sudo yum install python-pip
	c-) install serpent (older version needed for python 2.7)
		$ sudo pip install serpent==1.28
	d-) Pyro4 install using pip
		$ sudo pip install Pyro4

2-) install Pyro4 naming server:
	a-) copy the naming server executable to init.d
		~ this will force run executable on sys startup
		$ sudo cp ./pyro4NamingServer /etc/init.d
	b-) change permissions to make executable
		$ sudo chmod +x /etc/init.d/pyro4NamingServer
	c-) start up the executable
		$ sudo /etc/init.d/pyro4NamingServer start

3-) set firewall settings
	a-) check curren state of firewall
		$ sudo firewall-cmd --state
		-> should report: running
	b-) temporarily stop: 
		$ sudo systemctl stop firewalld
	c-) disable at startup: 
		$ sudo systemctl disable firewalld
	d-) mask to prevent startup from other services: 
		$ sudo systemctl mask --now firewalld