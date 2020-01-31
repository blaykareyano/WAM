1-) install Pyro4 and other needed packages:
	a-) sudo yum install python-setuptools
	b-) sudo yum install python-pip
	c-) sudo pip install serpent==1.28
	d-) sudo pip install Pyro4
	e-) sudo yum install ufw

2-) install Pyro4 naming server:
	a-) sudo cp ./pyro4NamingServer /etc/init.d
	b-) sudo chmod +x /etc/init.d/pyro4NamingServer
	c-) sudo /etc/init.d/pyro4NamingServer start

3-) set firewall settings
	a-) sudo ufw status
		i-) should report inactive
	b-) sudo ufw default deny incoming
	c-) sudo ufw default allow outgoing
	d-) sudo ufw allow ssh
	e-) sudo ufw allow 9999
	f-) sudo ufw status
		i-) should show all changes
	g-) sudo ufw enable
	h-) sudo systemctl enable ufw