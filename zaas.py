# -*- coding: utf-8; -*-
#!/usr/bin/python

# Change log
# zapi.py fork


import sys
import socket
import logging
from functools import wraps
from zabbix_api import ZabbixAPI
from bottle import route, run, error, get, post, request, response, abort, put, delete

DEBUG              = True
LOG_FORMAT         = "%(asctime)s [%(levelname)s] ZaaS[%(process)d/%(threadName)s].%(name)s: %(message)s"

try:
    from simplejson import dumps
except ImportError:
    from json import dumps

try:
   with open('/opt/zaas/bin/zabbix_api_pass.py'):
    sys.path.insert(0, './')
    import zabbix_api_pass
except IOError:
   print 'You must create the zabbix_api_pass.py password file, like this:\npassword=\"xxxxxx\"\n\n'

logging.basicConfig(filename="/var/log/zaas.log", format=LOG_FORMAT, level=logging.DEBUG)
zabbix_server = "monitoracao.stg.intra"
urlpath="/zabbix"
server = "http://" + zabbix_server + urlpath
username = "username_with_zabbix_super_admin"
zapi = ZabbixAPI(server = server, path="", log_level=0)
zapi.login(username, zabbix_api_pass.password)


def reply_json(f):
    @wraps(f)
    def json_dumps(*args, **kwargs):
        r = f(*args, **kwargs)
        if r and type(r) in (dict, list, tuple, str, unicode):
            response.content_type = "application/json; charset=UTF-8"
            return dumps(r)
        return r
    return json_dumps


def create_group(zabbix_group):
    """Function that will create host group on Zabbix Server."""
    result = zapi.hostgroup.create({ 'name' : zabbix_group })
    try:
        result['groupids']
    except NameError:
        """API throws an exception if such group already exists"""
        print 'There was na error while creating group'

    print 'Group "'+ zabbix_group +'" has been created with id: ' + result['groupids'][0]
    return result['groupids'][0]


def remove_duplicates(l):
    # remove duplicated item from list before update host
    return list(set(l))

@put('/<:re:bind[s]?>/<host_name>')
@reply_json
def add_group_template(host_name=None,zabbix_template=None,zabbix_group=None):
    """Function creates a zabbix group, host and will bind: hostname, group + template"""

    logger          = logging.getLogger("add_group_template")
    zabbix_template = request.forms.get("template", "").strip().lower()
    zabbix_group    = request.forms.get("group","").strip()
    
    try:
        # Get the provided host IP, zabbix use it when creating a new host.
        host_ip = socket.gethostbyname(host_name)
    except:
        logger.error("host_ip %s: nodename nor servname provided, or not known (is dns working?)", host_name)
        abort (500, "host_ip %s  nodename nor servname provided, or not known (is dns working?)" % host_name)

    # get the provided group ID, if not found we create it
    groupid=zapi.hostgroup.get({"output": "shorten","filter": { "name": zabbix_group}})
    logger.info("Groupid: %s group name: %s", groupid, zabbix_group)

    if not groupid.__len__():
        logger.info("Not found one or all of the groups, creating: %s", zabbix_group)
        groupid = create_group(zabbix_group)
        groupid = zapi.hostgroup.get({"output": "shorten","filter": { "name": zabbix_group}})


    # Getting already linked hostgroups, because the update function update deleting the existent data so we have to retrieve and append all together
    tmphglist = zapi.host.get({"output": ["hostid"], "selectGroups": "short",  "filter": {"host": host_name}})


    hostgrouplist=[]
    for hgroup in tmphglist:
        for key1,val1 in hgroup.items():
            if key1 == 'groups':
                for value in val1:
                    if isinstance(value, dict):
                        for key2,val2 in value.items():
                            hostgrouplist.append(val2)
    hostgroups = ",".join(hostgrouplist)
    if not hostgroups:
        hostgroups = "NA"

    # append exisnting groups to the new one provided (update all of them on the host)
    hostgrouplist.append(groupid[0]["groupid"])

    logger.info("Got hostgroup list: %s for host: %s", hostgrouplist, host_name)
    logger.info("Got group id: %s", zabbix_group)
    logger.info("Getting hostid for the received hostname: %s", host_name)

    try:
        hostid=zapi.host.get({"filter":{"host":host_name}})[0]["hostid"]
    except:
        logger.info("Hostname %s not found in Zabbix, creating... ", host_name)
        create=zapi.host.create({"host": host_name,"interfaces":[{"type":1,"main":1,"useip":1,"ip":host_ip,"dns":"","port": "10050"}],"groups":groupid})
        hostid=create["hostids"][0]

    logger.info("Hostname %s created, its hostid is %s", host_name,hostid)


    # Getting already linked templates, because the update function update deleting the existent data so we have to retrieve and append all tog
    tmpllist = zapi.host.get({"output": ["hostid"], "selectParentTemplates": ["templateid"],"hostids": hostid})
    templatelist=[]
    for tmpl in tmpllist:
        for key1,val1 in tmpl.items():
            if key1 == 'parentTemplates':
                for value in val1:
                    if isinstance(value, dict):
                        for key2,val2 in value.items():
                            templatelist.append(val2)
    templates = ",".join(templatelist)
    if not templates:
        templates = "NA"

    logger.info("Got linked templates %s for host %s", templates, host_name)
    logger.info("Getting template ID based on given name %s", zabbix_template)

    templateid=zapi.template.get({"output": "shorten","filter": { "host": zabbix_template}})
    if not templateid:
        logger.warn("WARN: Template %s not found!", zabbix_template)
    logger.info("My template id for %s is %s", zabbix_template,templateid)

    # append linked templates to the new one provided (update all of them on the host)
    templatelist.append(templateid[0]["templateid"]) 

    logger.info("Binding %s template to host %s", zabbix_template, host_name)
    try: 
        zapi.host.update({"hostid": hostid, "templates": remove_duplicates(templatelist), "groups": remove_duplicates(hostgrouplist)})
    except:
        logger.error("ERROR: Error registering host %s", host_name)
        abort (500, "Error registering host %s" % host_name)

    return { "template": zabbix_template,
            "hostname": host_name,
            "status": "created!"
            }


@get("/healthcheck")
def healthcheck():
    return "LIVE"

@get("/<:re:(?:index.htm[l]?)?>")
def index():
    return("""<center><h3>RESTFul Zabbix Interface.</h3></center>
              <hr size="1"><br>
              <center>Check <a href="/help">/help</a> (human readable) to see all available methods/endpoints.</center>
              <center><i>.</i></center>""")


@get("/help")
def help(name="help"):
    return ("""
            <!doctype html>
            <html><head>
            <link rel="stylesheet" href="https://maxcdn.bootstrapcdn.com/bootstrap/3.3.1/css/bootstrap.min.css">
            </head>
            <body>
            <div class="starter-template">
            <h4>RESTFul zabbix Interface</h1>
            <p class="lead">
            <ul>
                <li>/bind: Bind group and template in the received hostname</li>
                <ul>
                    <li>URI: /bind/your-hostname-1.intra</li>
                    <li>Method: PUT </li>
                    <li>Params: template, group</li>
                    <li>Ex: curl -X PUT -F "template=check-status" -F "group=host-group" http://zaas-server-api/bind/you-hostname-1.intra</li>
                    <li>How to use with Chef Opscode <a href="/chef">chef</a></li>

                </ul>
                <br>
                <li>/check/status: Application healthcheck</li>
                <ul>
                    <li>URI: /check/status</li>
                    <li>Method: GET </li>
                </ul>
                <br>
            </ul>
            </p></body></html>""")

@get("/chef")
def chef_use(name="chef"):
    return("""<!doctype html>
            <html><head>
            <link rel="stylesheet" href="https://maxcdn.bootstrapcdn.com/bootstrap/3.3.1/css/bootstrap.min.css">
            </head>
            <body>
            <pre>
include_recipe "zaas"

execute "zabbix-template" do
    command "curl -X PUT -F 'template=check-status' -F 'group=host-group' http://#{node[:zaas][:server]}/bind/#{node[:fqdn]}"
    action :run
end</pre><br>
            </body></html>""")
@error(500)
@reply_json
def error500(err):
    err_doc =  { "http_status_code": err.status_code,
                 "http_status":      err.status,
                 "error_message":    err.body }

    if DEBUG is True:
        err_doc.update({ "debug":          DEBUG,
                         "exception_msg":  err.exception.__getattribute__("message") or repr(err.exception),
                         "exception_type": err.exception.__class__.__name__ })

    return err_doc

@error(400)
@reply_json
def error400(err):
    return { "http_status_code": err.status_code,
             "http_status":      err.status,
             "error_message":    err.body }


run(host='127.0.0.1', port=8080, debug=DEBUG, reloader=True)
