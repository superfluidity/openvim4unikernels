# -*- coding: utf-8 -*-

##
# Copyright 2015 Telefónica Investigación y Desarrollo, S.A.U.
# This file is part of openvim
# All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
#
# For those usages not covered by the Apache License, Version 2.0 please
# contact with: nfvlabs@tid.es
##

'''
This is the thread for the http server North API. 
Two thread will be launched, with normal and administrative permissions.
'''

__author__ = "Alfonso Tierno, Leonardo Mirabal"
__date__ = "$06-Feb-2017 12:07:15$"

import threading
import vim_db
import logging
import threading
import imp
import host_thread as ht
import dhcp_thread as dt
import openflow_thread as oft

HTTP_Bad_Request =          400
HTTP_Unauthorized =         401
HTTP_Not_Found =            404
HTTP_Forbidden =            403
HTTP_Method_Not_Allowed =   405
HTTP_Not_Acceptable =       406
HTTP_Request_Timeout =      408
HTTP_Conflict =             409
HTTP_Service_Unavailable =  503
HTTP_Internal_Server_Error= 500


def convert_boolean(data, items):
    '''Check recursively the content of data, and if there is an key contained in items, convert value from string to boolean
    It assumes that bandwidth is well formed
    Attributes:
        'data': dictionary bottle.FormsDict variable to be checked. None or empty is consideted valid
        'items': tuple of keys to convert
    Return:
        None
    '''
    if type(data) is dict:
        for k in data.keys():
            if type(data[k]) is dict or type(data[k]) is tuple or type(data[k]) is list:
                convert_boolean(data[k], items)
            if k in items:
                if type(data[k]) is str:
                    if data[k] == "false":
                        data[k] = False
                    elif data[k] == "true":
                        data[k] = True
    if type(data) is tuple or type(data) is list:
        for k in data:
            if type(k) is dict or type(k) is tuple or type(k) is list:
                convert_boolean(k, items)



class ovimException(Exception):
    def __init__(self, message, http_code=HTTP_Bad_Request):
        self.http_code = http_code
        Exception.__init__(self, message)


class ovim():
    running_info = {} #TODO OVIM move the info of running threads from config_dic to this static variable
    def __init__(self, configuration):
        self.config = configuration
        self.logger = logging.getLogger(configuration["logger_name"])
        self.db = None
        self.db =   self._create_database_connection()

    def _create_database_connection(self):
        db = vim_db.vim_db((self.config["network_vlan_range_start"], self.config["network_vlan_range_end"]),
                           self.config['log_level_db']);
        if db.connect(self.config['db_host'], self.config['db_user'], self.config['db_passwd'],
                      self.config['db_name']) == -1:
            # self.logger.error("Cannot connect to database %s at %s@%s", self.config['db_name'], self.config['db_user'],
            #              self.config['db_host'])
            raise ovimException("Cannot connect to database {} at {}@{}".format(self.config['db_name'],
                                                                                self.config['db_user'],
                                                                                self.config['db_host']) )
        return db


    def start_service(self):
        #if self.running_info:
        #    return  #TODO service can be checked and rebuild broken threads
        r = self.db.get_db_version()
        if r[0]<0:
            raise ovimException("DATABASE is not a VIM one or it is a '0.0' version. Try to upgrade to version '{}' with "\
                                "'./database_utils/migrate_vim_db.sh'".format(self.config["database_version"]) )
        elif r[1]!=self.config["database_version"]:
            raise ovimException("DATABASE wrong version '{}'. Try to upgrade/downgrade to version '{}' with "\
                                "'./database_utils/migrate_vim_db.sh'".format(r[1], self.config["database_version"]) )

        # create database connection for openflow threads
        db_of = self._create_database_connection()
        self.config["db"] = db_of
        db_lock = threading.Lock()
        self.config["db_lock"] = db_lock

        # precreate interfaces; [bridge:<host_bridge_name>, VLAN used at Host, uuid of network camping in this bridge, speed in Gbit/s
        self.config['dhcp_nets'] = []
        self.config['bridge_nets'] = []
        for bridge, vlan_speed in self.config["bridge_ifaces"].items():
        # skip 'development_bridge'
            if self.config['mode'] == 'development' and self.config['development_bridge'] == bridge:
                continue
            self.config['bridge_nets'].append([bridge, vlan_speed[0], vlan_speed[1], None])

        # check if this bridge is already used (present at database) for a network)
        used_bridge_nets = []
        for brnet in self.config['bridge_nets']:
            r, nets = db_of.get_table(SELECT=('uuid',), FROM='nets', WHERE={'provider': "bridge:" + brnet[0]})
            if r > 0:
                brnet[3] = nets[0]['uuid']
                used_bridge_nets.append(brnet[0])
                if self.config.get("dhcp_server"):
                    if brnet[0] in self.config["dhcp_server"]["bridge_ifaces"]:
                        self.config['dhcp_nets'].append(nets[0]['uuid'])
        if len(used_bridge_nets) > 0:
            self.logger.info("found used bridge nets: " + ",".join(used_bridge_nets))
        # get nets used by dhcp
        if self.config.get("dhcp_server"):
            for net in self.config["dhcp_server"].get("nets", ()):
                r, nets = db_of.get_table(SELECT=('uuid',), FROM='nets', WHERE={'name': net})
                if r > 0:
                    self.config['dhcp_nets'].append(nets[0]['uuid'])

        # get host list from data base before starting threads
        r, hosts = db_of.get_table(SELECT=('name', 'ip_name', 'user', 'uuid'), FROM='hosts', WHERE={'status': 'ok'})
        if r < 0:
            raise ovimException("Cannot get hosts from database {}".format(hosts))
        # create connector to the openflow controller
        of_test_mode = False if self.config['mode'] == 'normal' or self.config['mode'] == "OF only" else True

        if of_test_mode:
            OF_conn = oft.of_test_connector({"of_debug": self.config['log_level_of']})
        else:
            # load other parameters starting by of_ from config dict in a temporal dict
            temp_dict = {"of_ip": self.config['of_controller_ip'],
                         "of_port": self.config['of_controller_port'],
                         "of_dpid": self.config['of_controller_dpid'],
                         "of_debug": self.config['log_level_of']
                         }
            for k, v in self.config.iteritems():
                if type(k) is str and k[0:3] == "of_" and k[0:13] != "of_controller":
                    temp_dict[k] = v
            if self.config['of_controller'] == 'opendaylight':
                module = "ODL"
            elif "of_controller_module" in self.config:
                module = self.config["of_controller_module"]
            else:
                module = self.config['of_controller']
            module_info = None
            try:
                module_info = imp.find_module(module)

                OF_conn = imp.load_module("OF_conn", *module_info)
                try:
                    OF_conn = OF_conn.OF_conn(temp_dict)
                except Exception as e:
                    self.logger.error("Cannot open the Openflow controller '%s': %s", type(e).__name__, str(e))
                    if module_info and module_info[0]:
                        file.close(module_info[0])
                    exit(-1)
            except (IOError, ImportError) as e:
                if module_info and module_info[0]:
                    file.close(module_info[0])
                self.logger.error(
                    "Cannot open openflow controller module '%s'; %s: %s; revise 'of_controller' field of configuration file.",
                    module, type(e).__name__, str(e))
                raise ovimException("Cannot open openflow controller module '{}'; {}: {}; revise 'of_controller' field of configuration file.".fromat(
                        module, type(e).__name__, str(e)))


                # create openflow thread
        thread = oft.openflow_thread(OF_conn, of_test=of_test_mode, db=db_of, db_lock=db_lock,
                                     pmp_with_same_vlan=self.config['of_controller_nets_with_same_vlan'],
                                     debug=self.config['log_level_of'])
        r, c = thread.OF_connector.obtain_port_correspondence()
        if r < 0:
            raise ovimException("Cannot get openflow information %s", c)
        thread.start()
        self.config['of_thread'] = thread

        # create dhcp_server thread
        host_test_mode = True if self.config['mode'] == 'test' or self.config['mode'] == "OF only" else False
        dhcp_params = self.config.get("dhcp_server")
        if dhcp_params:
            thread = dt.dhcp_thread(dhcp_params=dhcp_params, test=host_test_mode, dhcp_nets=self.config["dhcp_nets"],
                                    db=db_of, db_lock=db_lock, debug=self.config['log_level_of'])
            thread.start()
            self.config['dhcp_thread'] = thread

        # Create one thread for each host
        host_test_mode = True if self.config['mode'] == 'test' or self.config['mode'] == "OF only" else False
        host_develop_mode = True if self.config['mode'] == 'development' else False
        host_develop_bridge_iface = self.config.get('development_bridge', None)
        self.config['host_threads'] = {}
        for host in hosts:
            host['image_path'] = '/opt/VNF/images/openvim'
            thread = ht.host_thread(name=host['name'], user=host['user'], host=host['ip_name'], db=db_of, db_lock=db_lock,
                                    test=host_test_mode, image_path=self.config['image_path'], version=self.config['version'],
                                    host_id=host['uuid'], develop_mode=host_develop_mode,
                                    develop_bridge_iface=host_develop_bridge_iface)
            thread.start()
            self.config['host_threads'][host['uuid']] = thread

    def stop_service(self):
        threads = self.config.get('host_threads', {})
        if 'of_thread' in self.config:
            threads['of'] = (self.config['of_thread'])
        if 'dhcp_thread' in self.config:
            threads['dhcp'] = (self.config['dhcp_thread'])

        for thread in threads.values():
            thread.insert_task("exit")
        for thread in threads.values():
            thread.join()
            # http_thread.join()
            # if http_thread_admin is not None:
            # http_thread_admin.join()


    def get_ports(self, columns=None, filter={}, limit=None):
        # result, content = my.db.get_ports(where_)
        result, content = self.db.get_table(SELECT=columns, WHERE=filter, FROM='ports', LIMIT=limit)
        if result < 0:
            self.logger.error("http_get_ports Error %d %s", result, content)
            raise ovimException(str(content), -result)
        else:
            convert_boolean(content, ('admin_state_up',))
            return content


    def new_port(self, port_data):
        port_data['type'] = 'external'
        if port_data.get('net_id'):
            # check that new net has the correct type
            result, new_net = self.db.check_target_net(port_data['net_id'], None, 'external')
            if result < 0:
                raise ovimException(str(new_net), -result)
        # insert in data base
        result, uuid = self.db.new_row('ports', port_data, True, True)
        if result > 0:
            if 'net_id' in port_data:
                r, c = self.config['of_thread'].insert_task("update-net", port_data['net_id'])
                if r < 0:
                    self.logger.error("Cannot insert a task for updating network '$s' %s", port_data['net_id'], c)
                    #TODO put network in error status
            return uuid
        else:
            raise ovimException(str(uuid), -result)

    def delete_port(self, port_id):
        # Look for the previous port data
        result, ports = self.db.get_table(WHERE={'uuid': port_id, "type": "external"}, FROM='ports')
        if result < 0:
            raise ovimException("Cannot get port info from database: {}".format(ports), http_code=-result)
        # delete from the data base
        result, content = self.db.delete_row('ports', port_id)
        if result == 0:
            raise ovimException("External port '{}' not found".format(port_id), http_code=HTTP_Not_Found)
        elif result < 0:
            raise ovimException("Cannot delete port from database: {}".format(content), http_code=-result)
        # update network
        network = ports[0].get('net_id', None)
        if network:
            # change of net.
            r, c = self.config['of_thread'].insert_task("update-net", network)
            if r < 0:
                self.logger.error("Cannot insert a task for updating network '$s' %s", network, c)
        return content


    def edit_port(self, port_id, port_data, admin=True):
        # Look for the previous port data
        result, content = self.db.get_table(FROM="ports", WHERE={'uuid': port_id})
        if result < 0:
            raise ovimException("Cannot get port info from database: {}".format(content), http_code=-result)
        elif result == 0:
            raise ovimException("Port '{}' not found".format(port_id), http_code=HTTP_Not_Found)
        port = content[0]
        nets = []
        host_id = None
        result = 1
        if 'net_id' in port_data:
            # change of net.
            old_net = port.get('net_id', None)
            new_net = port_data['net_id']
            if old_net != new_net:

                if new_net:
                    nets.append(new_net)  # put first the new net, so that new openflow rules are created before removing the old ones
                if old_net:
                    nets.append(old_net)
                if port['type'] == 'instance:bridge' or port['type'] == 'instance:ovs':
                    raise ovimException("bridge interfaces cannot be attached to a different net", http_code=HTTP_Forbidden)
                elif port['type'] == 'external' and not admin:
                    raise ovimException("Needed admin privileges",http_code=HTTP_Unauthorized)
                if new_net:
                    # check that new net has the correct type
                    result, new_net_dict = self.db.check_target_net(new_net, None, port['type'])
                    if result < 0:
                        raise ovimException("Error {}".format(new_net_dict), http_code=HTTP_Conflict)
                # change VLAN for SR-IOV ports
                if result >= 0 and port["type"] == "instance:data" and port["model"] == "VF":  # TODO consider also VFnotShared
                    if new_net:
                        port_data["vlan"] = None
                    else:
                        port_data["vlan"] = new_net_dict["vlan"]
                    # get host where this VM is allocated
                    result, content = self.db.get_table(FROM="instances", WHERE={"uuid": port["instance_id"]})
                    if result > 0:
                        host_id = content[0]["host_id"]

        # insert in data base
        if result >= 0:
            result, content = self.db.update_rows('ports', port_data, WHERE={'uuid': port_id}, log=False)

        # Insert task to complete actions
        if result > 0:
            for net_id in nets:
                r, v = self.config['of_thread'].insert_task("update-net", net_id)
                if r < 0:
                    self.logger.error("Error updating network '{}' {}".format(r,v))
                    # TODO Do something if fails
            if host_id:
                r, v = self.config['host_threads'][host_id].insert_task("edit-iface", port_id, old_net, new_net)
                if r < 0:
                    self.logger.error("Error updating network '{}' {}".format(r,v))
                    # TODO Do something if fails
        if result >= 0:
            return port_id
        else:
            raise ovimException("Error {}".format(content), http_code=-result)
