#!/usr/bin/env python
# -*- coding: utf-8 -*-

##
# Copyright 2016, I2T Research Group (UPV/EHU)
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
# contact with: alaitz.mendiola@ehu.eus or alaitz.mendiola@gmail.com
##

'''
ImplementS the pluging for the Open Network Operating System (ONOS) openflow
controller. It creates the class OF_conn to create dataplane connections
with static rules based on packet destination MAC address
'''

__author__="Alaitz Mendiola"
__date__ ="$22-nov-2016$"


import json
import requests
import base64
import logging
import openflow_conn


class OF_conn(openflow_conn.OpenflowConn):
    """
    ONOS connector. No MAC learning is used
    """
    def __init__(self, params):
        """ Constructor.
            Params: dictionary with the following keys:
                of_dpid:     DPID to use for this controller ?? Does a controller have a dpid?
                of_ip:       controller IP address
                of_port:     controller TCP port
                of_user:     user credentials, can be missing or None
                of_password: password credentials
                of_debug:    debug level for logging. Default to ERROR
                other keys are ignored
            Raise an exception if same parameter is missing or wrong
        """

        openflow_conn.OpenflowConn.__init__(self, params)

        # check params
        if "of_ip" not in params or params["of_ip"]==None or "of_port" not in params or params["of_port"]==None:
            raise ValueError("IP address and port must be provided")
        #internal variables
        self.name = "onos"
        self.headers = {'content-type':'application/json','accept':'application/json',}

        self.auth="None"
        self.pp2ofi={}  # From Physical Port to OpenFlow Index
        self.ofi2pp={}  # From OpenFlow Index to Physical Port

        self.dpid = str(params["of_dpid"])
        self.id = 'of:'+str(self.dpid.replace(':', ''))
        self.url = "http://%s:%s/onos/v1/" %( str(params["of_ip"]), str(params["of_port"] ) )

        # TODO This may not be straightforward
        if "of_user" in params and params["of_user"]!=None:
            if not params.get("of_password"):
                of_password=""
            else:
                of_password=str(params["of_password"])
            self.auth = base64.b64encode(str(params["of_user"])+":"+of_password)
            self.headers['authorization'] = 'Basic ' + self.auth

        self.logger = logging.getLogger('vim.OF.onos')
        self.logger.setLevel( getattr(logging, params.get("of_debug", "ERROR")) )
        self.ip_address = None

    def get_of_switches(self):
        """
        Obtain a a list of switches or DPID detected by this controller
        :return: list where each element a tuple pair (DPID, IP address)
                 Raise a openflowconnUnexpectedResponse expection in case of failure
        """
        try:
            self.headers['content-type'] = 'text/plain'
            of_response = requests.get(self.url + "devices", headers=self.headers)
            error_text = "Openflow response %d: %s" % (of_response.status_code, of_response.text)
            if of_response.status_code != 200:
                self.logger.warning("get_of_switches " + error_text)
                raise openflow_conn.OpenflowconnUnexpectedResponse(error_text)

            self.logger.debug("get_of_switches " + error_text)
            info = of_response.json()

            if type(info) != dict:
                self.logger.error("get_of_switches. Unexpected response, not a dict: %s", str(info))
                raise openflow_conn.OpenflowconnUnexpectedResponse("Unexpected response, not a dict. Wrong version?")

            node_list = info.get('devices')

            if type(node_list) is not list:
                self.logger.error(
                    "get_of_switches. Unexpected response, at 'devices', not found or not a list: %s",
                    str(type(node_list)))
                raise openflow_conn.OpenflowconnUnexpectedResponse("Unexpected response, at 'devices', not found "
                                                                   "or not a list. Wrong version?")

            switch_list = []
            for node in node_list:
                node_id = node.get('id')
                if node_id is None:
                    self.logger.error("get_of_switches. Unexpected response at 'device':'id', not found: %s",
                                      str(node))
                    raise openflow_conn.OpenflowconnUnexpectedResponse("Unexpected response at 'device':'id', "
                                                                       "not found . Wrong version?")

                node_ip_address = node.get('annotations').get('managementAddress')
                if node_ip_address is None:
                    self.logger.error(
                        "get_of_switches. Unexpected response at 'device':'managementAddress', not found: %s",
                        str(node))
                    raise openflow_conn.OpenflowconnUnexpectedResponse(
                        "Unexpected response at 'device':'managementAddress', not found. Wrong version?")

                node_id_hex = hex(int(node_id.split(':')[1])).split('x')[1].zfill(16)

                switch_list.append(
                    (':'.join(a + b for a, b in zip(node_id_hex[::2], node_id_hex[1::2])), node_ip_address))
            raise switch_list

        except requests.exceptions.RequestException as e:
            error_text = type(e).__name__ + ": " + str(e)
            self.logger.error("get_of_switches " + error_text)
            raise openflow_conn.OpenflowconnConnectionException(error_text)
        except ValueError as e:
            # ValueError in the case that JSON can not be decoded
            error_text = type(e).__name__ + ": " + str(e)
            self.logger.error("get_of_switches " + error_text)
            raise openflow_conn.OpenflowconnUnexpectedResponse(error_text)

    def obtain_port_correspondence(self):
        """
        Obtain the correspondence between physical and openflow port names
        :return: dictionary with physical name as key, openflow name as value
                 Raise a openflowconnUnexpectedResponse expection in case of failure
        """
        try:
            self.headers['content-type'] = 'text/plain'
            of_response = requests.get(self.url + "devices/" + self.id + "/ports", headers=self.headers)
            error_text = "Openflow response %d: %s" % (of_response.status_code, of_response.text)
            if of_response.status_code != 200:
                self.logger.warning("obtain_port_correspondence " + error_text)
                raise openflow_conn.OpenflowconnUnexpectedResponse(error_text)

            self.logger.debug("obtain_port_correspondence " + error_text)
            info = of_response.json()

            node_connector_list = info.get('ports')
            if type(node_connector_list) is not list:
                self.logger.error(
                    "obtain_port_correspondence. Unexpected response at 'ports', not found or not a list: %s",
                    str(node_connector_list))
                raise openflow_conn.OpenflowconnUnexpectedResponse("Unexpected response at 'ports', not found  or not "
                                                                   "a list. Wrong version?")

            for node_connector in node_connector_list:
                if node_connector['port'] != "local":
                    self.pp2ofi[str(node_connector['annotations']['portName'])] = str(node_connector['port'])
                    self.ofi2pp[str(node_connector['port'])] = str(node_connector['annotations']['portName'])

            node_ip_address = info['annotations']['managementAddress']
            if node_ip_address is None:
                self.logger.error(
                    "obtain_port_correspondence. Unexpected response at 'managementAddress', not found: %s",
                    str(self.id))
                raise openflow_conn.OpenflowconnUnexpectedResponse("Unexpected response at 'managementAddress', "
                                                                   "not found. Wrong version?")
            self.ip_address = node_ip_address

            # print self.name, ": obtain_port_correspondence ports:", self.pp2ofi
            return self.pp2ofi
        except requests.exceptions.RequestException as e:
            error_text = type(e).__name__ + ": " + str(e)
            self.logger.error("obtain_port_correspondence " + error_text)
            raise openflow_conn.OpenflowconnConnectionException(error_text)
        except ValueError as e:
            # ValueError in the case that JSON can not be decoded
            error_text = type(e).__name__ + ": " + str(e)
            self.logger.error("obtain_port_correspondence " + error_text)
            raise openflow_conn.OpenflowconnUnexpectedResponse(error_text)

    def get_of_rules(self, translate_of_ports=True):
        """
        Obtain the rules inserted at openflow controller
        :param translate_of_ports: if True it translates ports from openflow index to physical switch name
        :return: dict if ok: with the rule name as key and value is another dictionary with the following content:
                    priority: rule priority
                    name:         rule name (present also as the master dict key)
                    ingress_port: match input port of the rule
                    dst_mac:      match destination mac address of the rule, can be missing or None if not apply
                    vlan_id:      match vlan tag of the rule, can be missing or None if not apply
                    actions:      list of actions, composed by a pair tuples:
                        (vlan, None/int): for stripping/setting a vlan tag
                        (out, port):      send to this port
                    switch:       DPID, all
                 Raise a openflowconnUnexpectedResponse expection in case of failure
        """

        try:

            if len(self.ofi2pp) == 0:
                self.obtain_port_correspondence()

            # get rules
            self.headers['content-type'] = 'text/plain'
            of_response = requests.get(self.url + "flows/" + self.id, headers=self.headers)
            error_text = "Openflow response %d: %s" % (of_response.status_code, of_response.text)

            # The configured page does not exist if there are no rules installed. In that case we return an empty dict
            if of_response.status_code == 404:
                return {}

            elif of_response.status_code != 200:
                self.logger.warning("get_of_rules " + error_text)
                raise openflow_conn.OpenflowconnUnexpectedResponse(error_text)
            self.logger.debug("get_of_rules " + error_text)

            info = of_response.json()

            if type(info) != dict:
                self.logger.error("get_of_rules. Unexpected response, not a dict: %s", str(info))
                raise openflow_conn.OpenflowconnUnexpectedResponse("Unexpected openflow response, not a dict. "
                                                                   "Wrong version?")

            flow_list = info.get('flows')

            if flow_list is None:
                return {}

            if type(flow_list) is not list:
                self.logger.error(
                    "get_of_rules. Unexpected response at 'flows', not a list: %s",
                    str(type(flow_list)))
                raise openflow_conn.OpenflowconnUnexpectedResponse("Unexpected response at 'flows', not a list. "
                                                                   "Wrong version?")

            rules = dict() # Response dictionary

            for flow in flow_list:
                if not ('id' in flow and 'selector' in flow and 'treatment' in flow and \
                                    'instructions' in flow['treatment'] and 'criteria' in \
                                    flow['selector']):
                    raise openflow_conn.OpenflowconnUnexpectedResponse("unexpected openflow response, one or more "
                                                                       "elements are missing. Wrong version?")

                rule = dict()
                rule['switch'] = self.dpid
                rule['priority'] = flow.get('priority')
                rule['name'] = flow['id']

                for criteria in flow['selector']['criteria']:
                    if criteria['type'] == 'IN_PORT':
                        in_port = str(criteria['port'])
                        if in_port != "CONTROLLER":
                            if not in_port in self.ofi2pp:
                                raise openflow_conn.OpenflowconnUnexpectedResponse("Error: Ingress port {} is not "
                                                                                   "in switch port list".format(in_port))
                            if translate_of_ports:
                                in_port = self.ofi2pp[in_port]
                        rule['ingress_port'] = in_port

                    elif criteria['type'] == 'VLAN_VID':
                        rule['vlan_id'] = criteria['vlanId']

                    elif criteria['type'] == 'ETH_DST':
                        rule['dst_mac'] = str(criteria['mac']).lower()

                actions = []
                for instruction in flow['treatment']['instructions']:
                    if instruction['type'] == "OUTPUT":
                        out_port = str(instruction['port'])
                        if out_port != "CONTROLLER":
                            if not out_port in self.ofi2pp:
                                raise openflow_conn.OpenflowconnUnexpectedResponse("Error: Output port {} is not in "
                                                                                   "switch port list".format(out_port))

                            if translate_of_ports:
                                out_port = self.ofi2pp[out_port]

                        actions.append( ('out', out_port) )

                    if instruction['type'] == "L2MODIFICATION" and instruction['subtype'] == "VLAN_POP":
                        actions.append( ('vlan', 'None') )
                    if instruction['type'] == "L2MODIFICATION" and instruction['subtype'] == "VLAN_ID":
                        actions.append( ('vlan', instruction['vlanId']) )

                rule['actions'] = actions
                rules[flow['id']] = dict(rule)
            return rules

        except requests.exceptions.RequestException as e:
            # ValueError in the case that JSON can not be decoded
            error_text = type(e).__name__ + ": " + str(e)
            self.logger.error("get_of_rules " + error_text)
            raise openflow_conn.OpenflowconnConnectionException(error_text)
        except ValueError as e:
            # ValueError in the case that JSON can not be decoded
            error_text = type(e).__name__ + ": " + str(e)
            self.logger.error("get_of_rules " + error_text)
            raise openflow_conn.OpenflowconnUnexpectedResponse(error_text)

    def del_flow(self, flow_name):
        """
        Delete an existing rule
        :param flow_name:
        :return: Raise a openflowconnUnexpectedResponse expection in case of failure
        """

        try:
            self.headers['content-type'] = None
            of_response = requests.delete(self.url + "flows/" + self.id + "/" + flow_name, headers=self.headers)
            error_text = "Openflow response %d: %s" % (of_response.status_code, of_response.text)

            if of_response.status_code != 204:
                self.logger.warning("del_flow " + error_text)
                raise openflow_conn.OpenflowconnUnexpectedResponse(error_text)

            self.logger.debug("del_flow OK " + error_text)
            return None

        except requests.exceptions.RequestException as e:
            error_text = type(e).__name__ + ": " + str(e)
            self.logger.error("del_flow " + error_text)
            raise openflow_conn.OpenflowconnConnectionException(error_text)

    def new_flow(self, data):
        """
        Insert a new static rule
        :param data: dictionary with the following content:
                priority:     rule priority
                name:         rule name
                ingress_port: match input port of the rule
                dst_mac:      match destination mac address of the rule, missing or None if not apply
                vlan_id:      match vlan tag of the rule, missing or None if not apply
                actions:      list of actions, composed by a pair tuples with these posibilities:
                    ('vlan', None/int): for stripping/setting a vlan tag
                    ('out', port):      send to this port
        :return: Raise a openflowconnUnexpectedResponse expection in case of failure
        """
        try:

            if len(self.pp2ofi) == 0:
                self.obtain_port_correspondence()

            # Build the dictionary with the flow rule information for ONOS
            flow = dict()
            #flow['id'] = data['name']
            flow['tableId'] = 0
            flow['priority'] = data.get('priority')
            flow['timeout'] = 0
            flow['isPermanent'] = "true"
            flow['appId'] = 10 # FIXME We should create an appId for OSM
            flow['selector'] = dict()
            flow['selector']['criteria'] = list()

            # Flow rule matching criteria
            if not data['ingress_port'] in self.pp2ofi:
                error_text = 'Error. Port ' + data['ingress_port'] + ' is not present in the switch'
                self.logger.warning("new_flow " + error_text)
                raise openflow_conn.OpenflowconnUnexpectedResponse(error_text)

            ingress_port_criteria = dict()
            ingress_port_criteria['type'] = "IN_PORT"
            ingress_port_criteria['port'] = self.pp2ofi[data['ingress_port']]
            flow['selector']['criteria'].append(ingress_port_criteria)

            if 'dst_mac' in data:
                dst_mac_criteria = dict()
                dst_mac_criteria["type"] = "ETH_DST"
                dst_mac_criteria["mac"] = data['dst_mac']
                flow['selector']['criteria'].append(dst_mac_criteria)

            if data.get('vlan_id'):
                vlan_criteria = dict()
                vlan_criteria["type"] = "VLAN_VID"
                vlan_criteria["vlanId"] = int(data['vlan_id'])
                flow['selector']['criteria'].append(vlan_criteria)

            # Flow rule treatment
            flow['treatment'] = dict()
            flow['treatment']['instructions'] = list()
            flow['treatment']['deferred'] = list()

            for action in data['actions']:
                new_action = dict()
                if  action[0] == "vlan":
                    new_action['type'] = "L2MODIFICATION"
                    if action[1] == None:
                        new_action['subtype'] = "VLAN_POP"
                    else:
                        new_action['subtype'] = "VLAN_ID"
                        new_action['vlanId'] = int(action[1])
                elif action[0] == 'out':
                    new_action['type'] = "OUTPUT"
                    if not action[1] in self.pp2ofi:
                        error_msj = 'Port '+ action[1] + ' is not present in the switch'
                        raise openflow_conn.OpenflowconnUnexpectedResponse(error_msj)
                    new_action['port'] = self.pp2ofi[action[1]]
                else:
                    error_msj = "Unknown item '%s' in action list" % action[0]
                    self.logger.error("new_flow " + error_msj)
                    raise openflow_conn.OpenflowconnUnexpectedResponse(error_msj)

                flow['treatment']['instructions'].append(new_action)

            self.headers['content-type'] = 'application/json'
            path = self.url + "flows/" + self.id
            of_response = requests.post(path, headers=self.headers, data=json.dumps(flow) )

            error_text = "Openflow response %d: %s" % (of_response.status_code, of_response.text)
            if of_response.status_code != 201:
                self.logger.warning("new_flow " + error_text)
                raise openflow_conn.OpenflowconnUnexpectedResponse(error_text)

            flowId = of_response.headers['location'][path.__len__() + 1:]

            data['name'] = flowId

            self.logger.debug("new_flow OK " + error_text)
            return None

        except requests.exceptions.RequestException as e:
            error_text = type(e).__name__ + ": " + str(e)
            self.logger.error("new_flow " + error_text)
            raise openflow_conn.OpenflowconnConnectionException(error_text)

    def clear_all_flows(self):
        """
        Delete all existing rules
        :return: Raise a openflowconnUnexpectedResponse expection in case of failure
        """
        try:
            rules = self.get_of_rules(True)

            for rule in rules:
                self.del_flow(rule)

            self.logger.debug("clear_all_flows OK ")
            return None

        except requests.exceptions.RequestException as e:
            error_text = type(e).__name__ + ": " + str(e)
            self.logger.error("clear_all_flows " + error_text)
            raise openflow_conn.OpenflowconnConnectionException(error_text)





