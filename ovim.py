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
from netaddr import IPNetwork
from jsonschema import validate as js_v, exceptions as js_e

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

    @staticmethod
    def _check_dhcp_data_integrity(network):
        """
        Check if all dhcp parameter for anet are valid, if not will be calculated from cidr value
        :param network: list with user nets paramters
        :return:
        """
        if "cidr" in network:
            cidr = network["cidr"]
            ip_tools = IPNetwork(cidr)
            cidr_len = ip_tools.prefixlen
            if cidr_len > 29:
                return False

            ips = IPNetwork(cidr)
            if "dhcp_first_ip" not in network:
                network["dhcp_first_ip"] = str(ips[2])
            if "dhcp_last_ip" not in network:
                network["dhcp_last_ip"] = str(ips[-2])
            if "gateway_ip" not in network:
                network["gateway_ip"] = str(ips[1])

            return True
        else:
            return False

    @staticmethod
    def _check_valid_uuid(uuid):
        id_schema = {"type": "string", "pattern": "^[a-fA-F0-9]{8}(-[a-fA-F0-9]{4}){3}-[a-fA-F0-9]{12}$"}
        try:
            js_v(uuid, id_schema)
            return True
        except js_e.ValidationError:
            return False

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

        # create ovs dhcp thread
        result, content = self.db.get_table(FROM='nets')
        if result < 0:
            self.logger.error("http_get_ports Error %d %s", result, content)
            raise ovimException(str(content), -result)

        for net in content:
            net_type = net['type']
            if (net_type == 'bridge_data' or net_type == 'bridge_man') \
                    and net["provider"][:4] == 'OVS:' and net["enable_dhcp"] == "true":
                    self.launch_dhcp_server(net['vlan'],
                                            net['dhcp_first_ip'],
                                            net['dhcp_last_ip'],
                                            net['cidr'],
                                            net['gateway_ip'])

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

    def get_networks(self, columns=None, filter={}, limit=None):
        """
        Retreive networks available
        :param columns: List with select query parameters
        :param filter: List with where query parameters
        :param limit: Query limit result
        :return:
        """
        result, content = self.db.get_table(SELECT=columns, FROM='nets', WHERE=filter, LIMIT=limit)

        if result < 0:
            raise ovimException(str(content), -result)

        convert_boolean(content, ('shared', 'admin_state_up', 'enable_dhcp'))

        return content

    def show_network(self, network_id, filter={}):
        """
        Get network from DB by id
        :param network_id: net Id
        :param filter:
        :param limit:
        :return:
        """
        # obtain data
        if not network_id:
            raise ovimException("Not network id was not found")
        filter['uuid'] = network_id

        result, content = self.db.get_table(FROM='nets', WHERE=filter, LIMIT=100)

        if result < 0:
            raise ovimException(str(content), -result)
        elif result == 0:
            raise ovimException("show_network network '%s' not found" % network_id, -result)
        else:
            convert_boolean(content, ('shared', 'admin_state_up', 'enable_dhcp'))
            # get ports from DB
            result, ports = self.db.get_table(FROM='ports', SELECT=('uuid as port_id',),
                                              WHERE={'net_id': network_id}, LIMIT=100)
            if len(ports) > 0:
                content[0]['ports'] = ports

            convert_boolean(content, ('shared', 'admin_state_up', 'enable_dhcp'))
            return content[0]

    def new_network(self, network):
        """
        Create a net in DB
        :return:
        """
        tenant_id = network.get('tenant_id')

        if tenant_id:
            result, _ = self.db.get_table(FROM='tenants', SELECT=('uuid',), WHERE={'uuid': tenant_id, "enabled": True})
            if result <= 0:
                raise ovimException("set_network error, no tenant founded", -result)

        bridge_net = None
        # check valid params
        net_provider = network.get('provider')
        net_type = network.get('type')
        net_vlan = network.get("vlan")
        net_bind_net = network.get("bind_net")
        net_bind_type = network.get("bind_type")
        name = network["name"]

        # check if network name ends with :<vlan_tag> and network exist in order to make and automated bindning
        vlan_index = name.rfind(":")
        if not net_bind_net and not net_bind_type and vlan_index > 1:
            try:
                vlan_tag = int(name[vlan_index + 1:])
                if not vlan_tag and vlan_tag < 4096:
                    net_bind_net = name[:vlan_index]
                    net_bind_type = "vlan:" + name[vlan_index + 1:]
            except:
                pass

        if net_bind_net:
            # look for a valid net
            if self._check_valid_uuid(net_bind_net):
                net_bind_key = "uuid"
            else:
                net_bind_key = "name"
            result, content = self.db.get_table(FROM='nets', WHERE={net_bind_key: net_bind_net})
            if result < 0:
                raise ovimException(' getting nets from db ' + content, HTTP_Internal_Server_Error)
            elif result == 0:
                raise ovimException(" bind_net %s '%s'not found" % (net_bind_key, net_bind_net), HTTP_Bad_Request)
            elif result > 1:
                raise ovimException(" more than one bind_net %s '%s' found, use uuid" % (net_bind_key, net_bind_net), HTTP_Bad_Request)
            network["bind_net"] = content[0]["uuid"]

        if net_bind_type:
            if net_bind_type[0:5] != "vlan:":
                raise ovimException("bad format for 'bind_type', must be 'vlan:<tag>'", HTTP_Bad_Request)
            if int(net_bind_type[5:]) > 4095 or int(net_bind_type[5:]) <= 0:
                raise ovimException("bad format for 'bind_type', must be 'vlan:<tag>' with a tag between 1 and 4095",
                                    HTTP_Bad_Request)
            network["bind_type"] = net_bind_type

        if net_provider:
            if net_provider[:9] == "openflow:":
                if net_type:
                    if net_type != "ptp" and net_type != "data":
                        raise ovimException(" only 'ptp' or 'data' net types can be bound to 'openflow'",
                                            HTTP_Bad_Request)
                else:
                    net_type = 'data'
            else:
                if net_type:
                    if net_type != "bridge_man" and net_type != "bridge_data":
                        raise ovimException("Only 'bridge_man' or 'bridge_data' net types can be bound "
                                            "to 'bridge', 'macvtap' or 'default", HTTP_Bad_Request)
                else:
                    net_type = 'bridge_man'

        if not net_type:
            net_type = 'bridge_man'

        if net_provider:
            if net_provider[:7] == 'bridge:':
                # check it is one of the pre-provisioned bridges
                bridge_net_name = net_provider[7:]
                for brnet in self.config['bridge_nets']:
                    if brnet[0] == bridge_net_name:  # free
                        if not brnet[3]:
                            raise ovimException("invalid 'provider:physical', "
                                                "bridge '%s' is already used" % bridge_net_name, HTTP_Conflict)
                        bridge_net = brnet
                        net_vlan = brnet[1]
                        break
                        # if bridge_net==None:
                        #    bottle.abort(HTTP_Bad_Request, "invalid 'provider:physical', bridge '%s' is not one of the
                        #                    provisioned 'bridge_ifaces' in the configuration file" % bridge_net_name)
                        #    return

        elif self.config['network_type'] == 'bridge' and (net_type == 'bridge_data' or net_type == 'bridge_man'):
            # look for a free precreated nets
            for brnet in self.config['bridge_nets']:
                if not brnet[3]:  # free
                    if not bridge_net:
                        if net_type == 'bridge_man':  # look for the smaller speed
                            if brnet[2] < bridge_net[2]:
                                bridge_net = brnet
                        else:  # look for the larger speed
                            if brnet[2] > bridge_net[2]:
                                bridge_net = brnet
                    else:
                        bridge_net = brnet
                        net_vlan = brnet[1]
            if not bridge_net:
                raise ovimException("Max limits of bridge networks reached. Future versions of VIM "
                                    "will overcome this limit", HTTP_Bad_Request)
            else:
                self.logger.debug("using net " + bridge_net)
                net_provider = "bridge:" + bridge_net[0]
                net_vlan = bridge_net[1]
        elif net_type == 'bridge_data' or net_type == 'bridge_man' and self.config['network_type'] == 'ovs':
            net_provider = 'OVS'
        if not net_vlan and (net_type == "data" or net_type == "ptp" or net_provider == "OVS"):
            net_vlan = self.db.get_free_net_vlan()
            if net_vlan < 0:
                raise ovimException("Error getting an available vlan", HTTP_Internal_Server_Error)
        if net_provider == 'OVS':
            net_provider = 'OVS' + ":" + str(net_vlan)

        network['provider'] = net_provider
        network['type'] = net_type
        network['vlan'] = net_vlan
        dhcp_integrity = True
        if 'enable_dhcp' in network and network['enable_dhcp']:
            dhcp_integrity = self._check_dhcp_data_integrity(network)

        result, content = self.db.new_row('nets', network, True, True)

        if result >= 0 and dhcp_integrity:
            if bridge_net:
                bridge_net[3] = content
            if self.config.get("dhcp_server") and self.config['network_type'] == 'bridge':
                if network["name"] in self.config["dhcp_server"].get("nets", ()):
                    self.config["dhcp_nets"].append(content)
                    self.logger.debug("dhcp_server: add new net", content)
                elif not bridge_net and bridge_net[0] in self.config["dhcp_server"].get("bridge_ifaces", ()):
                    self.config["dhcp_nets"].append(content)
                    self.logger.debug("dhcp_server: add new net", content, content)
            return content
        else:
            raise ovimException("Error posting network", HTTP_Internal_Server_Error)
# TODO kei change update->edit

    def edit_network(self, network_id, network):
        """
        Update entwork data byt id
        :return:
        """
        # Look for the previous data
        where_ = {'uuid': network_id}
        result, network_old = self.db.get_table(FROM='nets', WHERE=where_)
        if result < 0:
            raise ovimException("Error updating network %s" % network_old, HTTP_Internal_Server_Error)
        elif result == 0:
            raise ovimException('network %s not found' % network_id, HTTP_Not_Found)
        # get ports
        nbports, content = self.db.get_table(FROM='ports', SELECT=('uuid as port_id',),
                                             WHERE={'net_id': network_id}, LIMIT=100)
        if result < 0:
            raise ovimException("http_put_network_id error %d %s" % (result, network_old), HTTP_Internal_Server_Error)
        if nbports > 0:
            if 'type' in network and network['type'] != network_old[0]['type']:
                raise ovimException("Can not change type of network while having ports attached",
                                    HTTP_Method_Not_Allowed)
            if 'vlan' in network and network['vlan'] != network_old[0]['vlan']:
                raise ovimException("Can not change vlan of network while having ports attached",
                                    HTTP_Method_Not_Allowed)

        # check valid params
        net_provider = network.get('provider', network_old[0]['provider'])
        net_type = network.get('type', network_old[0]['type'])
        net_bind_net = network.get("bind_net")
        net_bind_type = network.get("bind_type")
        if net_bind_net:
            # look for a valid net
            if self._check_valid_uuid(net_bind_net):
                net_bind_key = "uuid"
            else:
                net_bind_key = "name"
            result, content = self.db.get_table(FROM='nets', WHERE={net_bind_key: net_bind_net})
            if result < 0:
                raise ovimException('Getting nets from db ' + content, HTTP_Internal_Server_Error)
            elif result == 0:
                raise ovimException("bind_net %s '%s'not found" % (net_bind_key, net_bind_net), HTTP_Bad_Request)
            elif result > 1:
                raise ovimException("More than one bind_net %s '%s' found, use uuid" % (net_bind_key, net_bind_net),
                                    HTTP_Bad_Request)
            network["bind_net"] = content[0]["uuid"]
        if net_bind_type:
            if net_bind_type[0:5] != "vlan:":
                raise ovimException("Bad format for 'bind_type', must be 'vlan:<tag>'", HTTP_Bad_Request)
            if int(net_bind_type[5:]) > 4095 or int(net_bind_type[5:]) <= 0:
                raise ovimException("bad format for 'bind_type', must be 'vlan:<tag>' with a tag between 1 and 4095",
                                    HTTP_Bad_Request)
        if net_provider:
            if net_provider[:9] == "openflow:":
                if net_type != "ptp" and net_type != "data":
                    raise ovimException("Only 'ptp' or 'data' net types can be bound to 'openflow'", HTTP_Bad_Request)
            else:
                if net_type != "bridge_man" and net_type != "bridge_data":
                    raise ovimException("Only 'bridge_man' or 'bridge_data' net types can be bound to "
                                        "'bridge', 'macvtap' or 'default", HTTP_Bad_Request)

        # insert in data base
        result, content = self.db.update_rows('nets', network, WHERE={'uuid': network_id}, log=True)
        if result >= 0:
            # if result > 0 and nbports>0 and 'admin_state_up' in network
            #     and network['admin_state_up'] != network_old[0]['admin_state_up']:
            if result > 0:
                r, c = self.config['of_thread'].insert_task("update-net", network_id)
                if r < 0:
                    raise ovimException("Error while launching openflow rules %s" % c, HTTP_Internal_Server_Error)
                if self.config.get("dhcp_server"):
                    if network_id in self.config["dhcp_nets"]:
                        self.config["dhcp_nets"].remove(network_id)
                    if network.get("name", network_old["name"]) in self.config["dhcp_server"].get("nets", ()):
                        self.config["dhcp_nets"].append(network_id)
                    else:
                        net_bind = network.get("bind", network_old["bind"])
                        if net_bind and net_bind[:7] == "bridge:" and net_bind[7:] in self.config["dhcp_server"].get(
                                "bridge_ifaces", ()):
                            self.config["dhcp_nets"].append(network_id)
            return network_id
        else:
            raise ovimException(content, -result)

    def delete_network(self, network_id):

        # delete from the data base
        result, content = self.db.delete_row('nets', network_id)

        if result == 0:
            raise ovimException("Network %s not found " % network_id, HTTP_Not_Found)
        elif result > 0:
            for brnet in self.config['bridge_nets']:
                if brnet[3] == network_id:
                    brnet[3] = None
                    break
            if self.config.get("dhcp_server") and network_id in self.config["dhcp_nets"]:
                self.config["dhcp_nets"].remove(network_id)
            return content
        else:
            raise ovimException("Error deleting  network %s" % network_id, HTTP_Internal_Server_Error)

    def get_openflow_rules(self, network_id=None):
        """
        Get openflow id from DB
        :param network_id: Network id, if none all networks will be retrieved
        :return: Return a list with Openflow rules per net
        """
        # ignore input data
        if not network_id:
            where_ = {}
        else:
            where_ = {"net_id": network_id}

        result, content = self.db.get_table(
            SELECT=("name", "net_id", "priority", "vlan_id", "ingress_port", "src_mac", "dst_mac", "actions"),
            WHERE=where_, FROM='of_flows')

        if result < 0:
            raise ovimException(str(content), -result)
        return content

    def edit_openflow_rules(self, network_id=None):

        """
        To make actions over the net. The action is to reinstall the openflow rules
        network_id can be 'all'
        :param network_id: Network id, if none all networks will be retrieved
        :return : Number of nets updated
        """

        # ignore input data
        if not network_id:
            where_ = {}
        else:
            where_ = {"uuid": network_id}
        result, content = self.db.get_table(SELECT=("uuid", "type"), WHERE=where_, FROM='nets')

        if result < 0:
            raise ovimException(str(content), -result)

        for net in content:
            if net["type"] != "ptp" and net["type"] != "data":
                result -= 1
                continue
            r, c = self.config['of_thread'].insert_task("update-net", net['uuid'])
            if r < 0:
                raise ovimException(str(c), -r)
        return result

    def delete_openflow_rules(self):
        """
        To make actions over the net. The action is to delete ALL openflow rules
        :return: return operation result
        """
        # ignore input data
        r, c = self.config['of_thread'].insert_task("clear-all")
        if r < 0:
            raise ovimException(str(c), -r)
        return r

    def get_openflow_ports(self):
        """
        Obtain switch ports names of openflow controller
        :return: Return flow ports in DB
        """
        data = {'ports': self.config['of_thread'].OF_connector.pp2ofi}
        return data

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

    def get_dhcp_controller(self):
        """
        Create an host_thread object for manage openvim controller and not create a thread for itself
        :return: dhcp_host openvim controller object
        """

        if 'openvim_controller' in self.config['host_threads']:
            return self.config['host_threads']['openvim_controller']

        bridge_ifaces = []
        controller_ip = self.config['ovs_controller_ip']
        ovs_controller_user = self.config['ovs_controller_user']

        host_test_mode = True if self.config['mode'] == 'test' or self.config['mode'] == "OF only" else False
        host_develop_mode = True if self.config['mode'] == 'development' else False

        dhcp_host = ht.host_thread(name='openvim_controller', user=ovs_controller_user, host=controller_ip,
                                   db=self.config['db'],
                                   db_lock=self.config['db_lock'], test=host_test_mode,
                                   image_path=self.config['image_path'], version=self.config['version'],
                                   host_id='openvim_controller', develop_mode=host_develop_mode,
                                   develop_bridge_iface=bridge_ifaces)

        self.config['host_threads']['openvim_controller'] = dhcp_host
        if not host_test_mode:
            dhcp_host.ssh_connect()
        return dhcp_host

    def launch_dhcp_server(self, vlan, first_ip, last_ip, cidr, gateway):
        """
        Launch a dhcpserver base on dnsmasq attached to the net base on vlan id across the the openvim computes
        :param vlan: vlan identifier
        :param first_ip: First dhcp range ip
        :param last_ip: Last dhcp range ip
        :param cidr: net cidr
        :param gateway: net gateway
        :return:
        """
        ip_tools = IPNetwork(cidr)
        dhcp_netmask = str(ip_tools.netmask)
        ip_range = [first_ip, last_ip]

        dhcp_path = self.config['ovs_controller_file_path']

        controller_host = self.get_dhcp_controller()
        controller_host.create_linux_bridge(vlan)
        controller_host.create_dhcp_interfaces(vlan, first_ip, dhcp_netmask)
        controller_host.launch_dhcp_server(vlan, ip_range, dhcp_netmask, dhcp_path, gateway)


