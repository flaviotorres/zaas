# zaas
Zabbix REST API, zabbix as a service


REST service to the zabbix API, it will:

- create a host
- create a hostgroup
- bind the provided template to the server + hostgroup

Using:
============================ 
<pre>curl -X PUT -F 'template=check-status' -F 'group=new-host-group' http://server/bind/your-hostname-1.intra"</pre>

# INSTALLING

* Python 2.7 [1]
* Bottle [2]

[1]: http://www.python.org/download/releases/2.7.3/
[2]: http://bottlepy.org/docs/dev/


A6_6zT4_0nE6-4oB0_1jK4_0vQ3_5kA8_0hK9.0r.