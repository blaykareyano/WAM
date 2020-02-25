|~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~|
| Instructions for installation of WAM Daemon		 	|
| Blake Arellano - 2020									|
|~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~|

1-) install Pyro4 and other needed packages:
	a-) install python packaging library 
		$ sudo yum install python-setuptools
	b-) install python development package
		$ sudo yum install python-devel.x86_64
	c-) install python package installer pip
		$ sudo yum install python-pip
	d-) install serpent (older version needed for python 2.7)
		$ sudo pip install serpent==1.28
	e-) Pyro4 install using pip
		$ sudo pip install Pyro4
	f-) install psutil using pip
		$ sudo pip install psutil
	g-) install unix2dos
		$ sudo yum install unix2dos

2-) place WAM folder into opt directory:
	a-) copy all WAM files to opt directory
		$ sudo -R cp ./WAM /opt/WAM

4-) install WAM daemon executable:
	a-) copy the naming server executable to init.d
		~ this will force run executable on sys startup
		$ sudo cp ./wamDaemon /etc/init.d	
	b-) change permissions to make executable
		$ sudo chmod +x /etc/init.d/wamDaemon	
	c-) start up the executable
		$ sudo /etc/init.d/wamDaemon start
	d-) enable the executable to run on startup
		$ sudo systemctl daemon-reload
		$ sudo systemctl enable wamDaemon.service
	e-) test that it is starting up properly
		$ sudo systemctl reboot
		$ sudo systemctl status wamDaemon.service

5-) set firewall settings
	a-) check current state of firewall
		$ sudo firewall-cmd --state
		-> should report: running
	b-) temporarily stop: 
		$ sudo systemctl stop firewalld
	c-) disable at startup: 
		$ sudo systemctl disable firewalld
	d-) mask to prevent startup from other services: 
		$ sudo systemctl mask --now firewalld