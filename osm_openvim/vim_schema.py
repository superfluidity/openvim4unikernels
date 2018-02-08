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

''' Definition of dictionaries schemas used by validating input
    These dictionaries are validated using jsonschema library
'''
__author__="Alfonso Tierno"
__date__ ="$10-jul-2014 12:07:15$"

#
# SCHEMAS to validate input data
#

path_schema = {"type": "string", "maxLength": 255, "pattern": "^(\.){0,2}(/[^/\"':{}\(\)]+)+$"}
http_schema = {"type": "string", "pattern": "^https?://[^'\"=]+$"}
port_schema = {"type": "integer","minimum": 1, "maximun": 65534}
ip_schema = {"type": "string", "pattern": "^([0-9]{1,3}.){3}[0-9]{1,3}$"}
cidr_schema = {"type": "string", "pattern": "^([0-9]{1,3}.){3}[0-9]{1,3}/[0-9]{1,2}$"}
name_schema = {"type": "string", "minLength": 1, "maxLength": 255, "pattern": "^[^,;()'\"]+$"}
nameshort_schema = {"type": "string", "minLength": 1, "maxLength": 64, "pattern": "^[^,;()'\"]+$"}
nametiny_schema = {"type": "string", "minLength": 1, "maxLength": 12, "pattern": "^[^,;()'\"]+$"}
xml_text_schema = {"type": "string", "minLength": 1, "maxLength": 1000, "pattern": "^[^']+$"}
description_schema = {"type": ["string", "null"], "maxLength": 255, "pattern": "^[^'\"]+$"}
id_schema_fake = {"type": "string", "minLength": 2, "maxLength": 36}
                  # "pattern": "^[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}$"
id_schema = {"type": "string", "pattern": "^[a-fA-F0-9]{8}(-[a-fA-F0-9]{4}){3}-[a-fA-F0-9]{12}$"}
pci_schema = {"type": "string", "pattern": "^[0-9a-fA-F]{4}(:[0-9a-fA-F]{2}){2}\.[0-9a-fA-F]$"}
# used by VIO neutron-port-show <host_moid>-<domain>:<bus>:<device>.<function>-<VF-id>
pci_extended_schema = {"type": "string", "pattern": "^([0-9a-fA-F]{4}-)?[0-9a-fA-F]{4}(:[0-9a-fA-F]{2}){2}"
                                                     "\.[0-9a-fA-F](-[0-9a-fA-F]{3})?$"}
bandwidth_schema = {"type": "string", "pattern": "^[0-9]+ *([MG]bps)?$"}
integer0_schema = {"type": "integer", "minimum": 0}
integer1_schema = {"type": "integer", "minimum": 1}
vlan_schema = {"type": "integer", "minimum": 1, "maximun": 4095}
vlan1000_schema = {"type": "integer", "minimum": 1000, "maximun": 4095}
mac_schema = {"type": "string", "pattern": "^[0-9a-fA-F][02468aceACE](:[0-9a-fA-F]{2}){5}$"}
            # must be unicast LSB bit of MSB byte ==0
net_bind_schema = {"oneOf": [
    {"type": "null"},
    {"type": "string", "pattern":
        "^(default|((bridge|macvtap|ovsbr):[0-9a-zA-Z\.\-]{1,50})|openflow:[/0-9a-zA-Z\.\-]{1,50}(:vlan)?)$"} #CLICKOS MOD
]}
yes_no_schema = {"type": "string", "enum": ["yes", "no"]}
log_level_schema = {"type": "string", "enum":["DEBUG", "INFO", "WARNING","ERROR","CRITICAL"]}

config_schema = {
    "title": "main configuration information schema",
    "$schema": "http://json-schema.org/draft-04/schema#",
    "type": "object",
    "properties":{
        "http_port": port_schema,
        "http_admin_port": port_schema,
        "http_host": nameshort_schema,
        "http_url_prefix": path_schema, # it does not work yet; it's supposed to be the base path to be used by bottle, but it must be explicitly declared
        "db_host": nameshort_schema,
        "db_user": nameshort_schema,
        "db_passwd": {"type": "string"},
        "db_name": nameshort_schema,
        "of_controller_ip": ip_schema,
        "of_controller_port": port_schema,
        "of_controller_dpid": nameshort_schema,
        "of_controller_nets_with_same_vlan": {"type" : "boolean"},
        "of_controller": nameshort_schema, #{"type":"string", "enum":["floodlight", "opendaylight"]},
        "of_controller_module": {"type":"string"},
        "of_user": nameshort_schema,
        "of_password": nameshort_schema,
        "test_mode": {"type": "boolean"}, # leave for backward compatibility
        "task_queue_sleep_time": {"type":"integer","minimum":1,"maximun":180000}, #task queue sleep time in ms. min:1ms, max:180000ms. (3 minutes) #CLICKOS MOD
        "libvirt_conn_mode": {"type" : "string", "enum":["ssh", "tcp", "tls"]}, #CLICKOS MOD
        "mode": {"type":"string", "enum":["normal", "host only", "OF only", "development", "test"] },
        "development_bridge": {"type":"string"},
        "tenant_id": {"type" : "string"},
        "image_path": path_schema,      # leave for backward compatibility
        "host_image_path": path_schema,
        "host_ssh_keyfile": path_schema,
        "network_vlan_range_start": vlan_schema,
        "network_vlan_range_end": vlan_schema,
        "bridge_ifaces": {
            "type": "object",
            "patternProperties": {
                "." : {
                    "type": "array",
                    "items": integer0_schema,
                    "minItems":2,
                    "maxItems":2,
                },
            },
            "minProperties": 2
        },
        "dhcp_server": {
            "type": "object",
            "properties": {
                "host": name_schema,
                "port": port_schema,
                "provider": {"type": "string", "enum": ["isc-dhcp-server"]},
                "user": nameshort_schema,
                "password": {"type": "string"},
                "key": path_schema,         # for backward compatibility, use keyfile instead
                "keyfile": path_schema,
                "bridge_ifaces": {
                    "type": "array",
                    "items": nameshort_schema,
                },
                "nets": {
                    "type": "array",
                    "items": name_schema,
                },
            },
            "required": ['host', 'provider', 'user']
        },
        "log_level": log_level_schema,
        "log_level_db": log_level_schema,
        "log_level_of": log_level_schema,
        "network_type": {"type": "string", "enum": ["ovs", "bridge"]},
        "ovs_controller_file_path": path_schema,
        "ovs_controller_ip": nameshort_schema,
        "ovs_controller_user": nameshort_schema,
        "ovs_controller_password": {"type": "string"},
        "ovs_controller_keyfile": path_schema,
    },
    "patternProperties": {
        "of_*" : {"type": ["string", "integer", "boolean"]}
    },
    "required": ['db_host', 'db_user', 'db_passwd', 'db_name'],
    "additionalProperties": False
}



metadata_schema={
    "type":"object",
    "properties":{
        "architecture": {"type":"string"},
        "use_incremental": yes_no_schema,
        "vpci": pci_schema,
        "os_distro": {"type":"string"},
        "os_type": {"type":"string"},
        "os_version": {"type":"string"},
        "bus": {"type":"string"},
        "topology": {"type":"string", "enum": ["oneSocket", "oneSocket:hyperthreading"]}
    }
}

tenant_new_schema = {
    "title":"tenant creation information schema",
    "$schema": "http://json-schema.org/draft-04/schema#",
    "type":"object",
    "properties":{
        "tenant":{
            "type":"object",
            "properties":{
                "id":id_schema,
                "name": nameshort_schema,
                "description":description_schema,
                "enabled":{"type" : "boolean"}
            },
            "required": ["name"]
        }
    },
    "required": ["tenant"],
    "additionalProperties": False
}

tenant_edit_schema = {
    "title":"tenant edition information schema",
    "$schema": "http://json-schema.org/draft-04/schema#",
    "type":"object",
    "properties":{
        "tenant":{
            "type":"object",
            "minProperties":1,
            "properties":{
                "name":nameshort_schema,
                "description":description_schema,
                "enabled":{"type" : "boolean"}
            },
            "additionalProperties": False,
        }
    },
    "required": ["tenant"],
    "additionalProperties": False
}
interfaces_schema={
    "type":"array",
    "minItems":0,
    "items":{
        "type":"object",
        "properties":{
            "name":name_schema,
            "dedicated":{"type":"string","enum":["yes","no","yes:sriov"]},
            "bandwidth":bandwidth_schema,
            "vpci":pci_schema,
            "uuid":id_schema,
            "mac_address":mac_schema
        },
        "additionalProperties": False,
        "required": ["dedicated", "bandwidth"]
    }
}

extended_schema={
    "type":"object", 
    "properties":{                  
        "processor_ranking":integer0_schema,
        "devices":{
            "type": "array", 
            "items":{
                "type": "object",
                "properties":{
                    "type":{"type":"string", "enum":["usb","disk","cdrom","xml"]},
                    "vpci":pci_schema,
                    "imageRef":id_schema,
                    "xml":xml_text_schema,
                    "dev":nameshort_schema,
                    "size":integer1_schema,
                },
                "additionalProperties": False,
                "required": ["type"]
            }
        },
        "numas":{
            "type": "array",
            "items":{
                "type": "object",
                "properties":{
                    "memory":integer1_schema,
                    "cores":integer1_schema,
                    "paired-threads":integer1_schema,
                    "threads":integer1_schema,
                    "cores-id":{"type":"array","items":integer0_schema},
                    "paired-threads-id":{"type":"array","items":{"type":"array","minItems":2,"maxItems":2,"items":integer0_schema}},
                    "threads-id":{"type":"array","items":integer0_schema},
                    "interfaces":interfaces_schema
                },
                "additionalProperties": False,
                "minProperties": 1,
                #"required": ["memory"]
            }
        }
    },
    #"additionalProperties": False,
    #"required": ["processor_ranking"]
}

host_data_schema={
    "title":"hosts manual insertion information schema",
    "type":"object", 
    "properties":{
        "id": id_schema,
        "admin_state_up": {"type": "boolean"},
        "created_at": {"type": "string"},        # ignored, just for compatibility with host-list
        "ip_name": nameshort_schema,
        "name": name_schema,
        "description": description_schema,
        "user": nameshort_schema,
        "password": nameshort_schema,
        "keyfile": path_schema,
        "features": description_schema,
        "hypervisors": description_schema,   #CLICKOS MOD
        "ranking": integer0_schema,
        "autodiscover": {"type": "boolean"},    # try to discover host parameters instead of providing in this schema
        "devices": {
            "type": "array", 
            "items": {
                "type": "object",
                "properties": {
                    "type": {"type": "string", "enum": ["usb", "disk"]},
                    "vpci": pci_schema
                },
                "additionalProperties": False,
                "required": ["type"]
            }
        },
        "numas": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "properties": {
                    "admin_state_up": {"type": "boolean"},
                    "hugepages": integer0_schema,
                    "hugepages_consumed": integer0_schema,  # ignored, just for compatibility with host-list
                    "numa_socket": integer0_schema,
                    "memory": integer1_schema,
                    "cores":{
                        "type": "array",
                        "minItems": 2,
                        "items": {
                            "type": "object",
                            "properties": {
                                "core_id": integer0_schema,
                                "thread_id": integer0_schema,
                                "status": {"type": "string", "enum": ["noteligible"]},
                                "instance_id": {"type": "string"},   # ignored, just for compatibility with host-list
                                "v_thread_id": {"type": "integer"}   # ignored, just for compatibility with host-list
                            },
                            "additionalProperties": False,
                            "required": ["core_id", "thread_id"]
                        }
                    },
                    "interfaces": {
                        "type": "array",
                        "minItems": 1,
                        "items": {
                            "type": "object",
                            "properties": {
                                "source_name": nameshort_schema,
                                "mac": mac_schema,
                                "Mbps": integer0_schema,
                                "pci": pci_schema,
                                "sriovs": {
                                    "type": "array",
                                    "minItems":1,
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "source_name": {"oneOf": [integer0_schema, nameshort_schema]},
                                            "mac": mac_schema,
                                            "vlan": integer0_schema,  # ignored, just for backward compatibility
                                            "pci": pci_schema,
                                        },
                                        "additionalProperties": False,
                                        "required": ["source_name", "mac", "pci"]
                                    }
                                },
                                "switch_port": nameshort_schema,
                                "switch_dpid": nameshort_schema,
                                "switch_mac": mac_schema,
                            },
                            "additionalProperties": False,
                            "required": ["source_name", "mac", "Mbps", "pci"]
                        }
                    },
                },
                "additionalProperties": False,
                "required": ["cores", "numa_socket"]
            }
        }
    },
    "additionalProperties": False,
    "required": ["name", "user", "ip_name"]
}

host_edit_schema={
    "title":"hosts creation information schema",
    "$schema": "http://json-schema.org/draft-04/schema#",
    "type":"object",
    "properties":{
        "host":{
            "type":"object",
            "properties":{
                "ip_name":nameshort_schema,
                "name": name_schema,
                "description":description_schema,
                "user":nameshort_schema,
                "password":nameshort_schema,
                "admin_state_up":{"type":"boolean"},
                "numas":{
                    "type":"array", 
                    "items":{
                        "type": "object",
                        "properties":{
                            "numa_socket": integer0_schema,
                            "admin_state_up":{"type":"boolean"},
                            "interfaces":{
                                "type":"array", 
                                "items":{
                                    "type": "object",
                                    "properties":{
                                        "source_name": nameshort_schema,
                                        "switch_dpid": nameshort_schema,
                                        "switch_port": nameshort_schema,
                                    },
                                    "required": ["source_name"],
                                }
                            }
                        }, 
                        "required": ["numa_socket"],
                        "additionalProperties": False,
                    }
                }
            },
            "minProperties": 1,
            "additionalProperties": False
        },
    },
    "required": ["host"],
    "minProperties": 1,
    "additionalProperties": False
}

host_new_schema = {
    "title":"hosts creation information schema",
    "$schema": "http://json-schema.org/draft-04/schema#",
    "type":"object",
    "properties":{
        "host": host_data_schema,
        "host-data":host_data_schema
    },
    "required": ["host"],
    "minProperties": 1,
    "maxProperties": 2,
    "additionalProperties": False
}


flavor_new_schema = {
    "title":"flavor creation information schema",
    "$schema": "http://json-schema.org/draft-04/schema#",
    "type":"object",
    "properties":{
        "flavor":{
            "type":"object",
            "properties":{
                "id":id_schema,
                "name":name_schema,
                "description":description_schema,
                "ram":integer0_schema,
                "vcpus":integer0_schema,
                "extended": extended_schema,
                "public": yes_no_schema
            },
            "required": ["name"]
        }
    },
    "required": ["flavor"],
    "additionalProperties": False
}
flavor_update_schema = {
    "title":"flavor update information schema",
    "$schema": "http://json-schema.org/draft-04/schema#",
    "type":"object",
    "properties":{
        "flavor":{
            "type":"object",
            "properties":{
                "name":name_schema,
                "description":description_schema,
                "ram":integer0_schema,
                "vcpus":integer0_schema,
                "extended": extended_schema,
                "public": yes_no_schema
            },
            "minProperties": 1,
            "additionalProperties": False
        }
    },
    "required": ["flavor"],
    "additionalProperties": False
}

image_new_schema = {
    "title":"image creation information schema",
    "$schema": "http://json-schema.org/draft-04/schema#",
    "type":"object",
    "properties":{
        "image":{
            "type":"object",
            "properties":{
                "id":id_schema,
                "path": {"oneOf": [path_schema, http_schema]},
                "description":description_schema,
                "name":name_schema,
                "metadata":metadata_schema,
                "public": yes_no_schema
            },
            "required": ["name","path"]
        }
    },
    "required": ["image"],
    "additionalProperties": False
}

image_update_schema = {
    "title":"image update information schema",
    "$schema": "http://json-schema.org/draft-04/schema#",
    "type":"object",
    "properties":{
        "image":{
            "type":"object",
            "properties":{
                "path":{"oneOf": [path_schema, http_schema]},
                "description":description_schema,
                "name":name_schema,
                "metadata":metadata_schema,
                "public": yes_no_schema
            },
            "minProperties": 1,
            "additionalProperties": False
        }
    },
    "required": ["image"],
    "additionalProperties": False
}

networks_schema={
    "type":"array",
    "items":{
        "type":"object",
        "properties":{
            "name":name_schema,
            "bandwidth":bandwidth_schema,
            "vpci":pci_schema,
            "uuid":id_schema,
            "mac_address": mac_schema,
            "model": {"type":"string", "enum":["virtio","e1000","ne2k_pci","pcnet","rtl8139"]},
            "type": {"type":"string", "enum":["virtual","PF","VF","VFnotShared"]}
        },
        "additionalProperties": False,
        "required": ["uuid"]
    }
}

server_new_schema = {
    "title":"server creation information schema",
    "$schema": "http://json-schema.org/draft-04/schema#",
    "type":"object",
    "properties":{
        "server":{
            "type":"object",
            "properties":{
                "id":id_schema,
                "name":name_schema,
                "description":description_schema,
                "start":{"type":"string", "enum":["yes","no","paused"]},
                "hypervisor":{"type":"string", "enum":["kvm","xen-unik","xenhvm"]}, #CLICKOS MOD
                "osImageType":{"type":"string", "enum":["clickos","other"]}, #CLICKOS MOD
                "hostId":id_schema,
                "flavorRef":id_schema,
                "imageRef":id_schema,
                "extended": extended_schema,
                "networks":networks_schema
            },
            "required": ["name","flavorRef","imageRef"]
        }
    },
    "required": ["server"],
    "additionalProperties": False
}

server_action_schema = {
    "title":"server action information schema",
    "$schema": "http://json-schema.org/draft-04/schema#",
    "type":"object",
    "properties":{
        "start":{"oneOf":[{"type": "null"}, {"type":"string", "enum":["rebuild","null"] }]},
        "pause":{"type": "null"},
        "resume":{"type": "null"},
        "shutoff":{"type": "null"},
        "shutdown":{"type": "null"},
        "forceOff":{"type": "null"},
        "terminate":{"type": "null"},
        "createImage":{
            "type":"object",
            "properties":{ 
                "path":path_schema,
                "description":description_schema,
                "name":name_schema,
                "metadata":metadata_schema,
                "imageRef": id_schema,
                "disk": {"oneOf":[{"type": "null"}, {"type":"string"}] },
            },
            "required": ["name"]
        },
        "rebuild":{"type": ["object","null"]},
        "reboot":{
            "type": ["object","null"],
#            "properties": {
#                "type":{"type":"string", "enum":["SOFT"] }
#            }, 
#            "minProperties": 1,
#            "maxProperties": 1,
#            "additionalProperties": False
        }
    },
    "minProperties": 1,
    "maxProperties": 1,
    "additionalProperties": False
}

network_new_schema = {
    "title": "network creation information schema",
    "$schema": "http://json-schema.org/draft-04/schema#",
    "type": "object",
    "properties": {
        "network": {
            "type": "object",
            "properties":{
                "id": id_schema,
                "name": name_schema,
                "type": {"type":"string", "enum": ["bridge_man", "bridge_data", "data", "ptp"]},
                "shared": {"type": "boolean"},
                "tenant_id": id_schema,
                "admin_state_up": {"type": "boolean"},
                "provider:vlan": vlan_schema,
                "provider:physical": net_bind_schema,
                "region": nameshort_schema,
                "cidr": cidr_schema,
                "enable_dhcp": {"type": "boolean"},
                "dhcp_first_ip": ip_schema,
                "dhcp_last_ip": ip_schema,
                "dns": {"type": "array", "items": [ip_schema]},
                "links":    {"type": "array", "items": {"type": "object", "properties": {
                                "nat": cidr_schema,
                                "iface": name_schema,
                                "vlan": vlan_schema},
                                "required": ["iface"],
                                "additionalProperties": False
                                },

                             },
                "routes":   {"type": "object", "properties":  {"default": ip_schema}, "patternProperties": {
                                                            "^([0-9]{1,3}.){3}[0-9]{1,3}/[0-9]{1,2}$": ip_schema,
                                                            },
                                                            "additionalProperties": False
                             },

                "bind_net": name_schema,   # can be name, or uuid
                "bind_type": {"oneOf": [{"type": "null"}, {"type": "string", "pattern": "^vlan:[0-9]{1,4}$"}]}
            },
        "required": ["name"]
        }
    },
    "required": ["network"],
    "additionalProperties": False
}

network_update_schema = {
    "title":"network update information schema",
    "$schema": "http://json-schema.org/draft-04/schema#",
    "type":"object",
    "properties":{
        "network":{
            "type":"object",
            "properties":{
                "name":name_schema,
                "type":{"type":"string", "enum":["bridge_man","bridge_data","data", "ptp"]},
                "shared":{"type":"boolean"},
                "tenant_id":id_schema,
                "admin_state_up":{"type":"boolean"},
                "provider:vlan":vlan_schema, 
                "provider:physical":net_bind_schema,
                "cidr":cidr_schema,
                "enable_dhcp": {"type":"boolean"},
                # "dhcp_first_ip": ip_schema,
                # "dhcp_last_ip": ip_schema,
                "bind_net":name_schema, #can be name, or uuid
                "bind_type":{"oneOf":[{"type":"null"},{"type":"string", "pattern":"^vlan:[0-9]{1,4}$"}]}
            },
            "minProperties": 1,
            "additionalProperties": False
        }
    },
    "required": ["network"],
    "additionalProperties": False
}


port_new_schema = {
    "title":"port creation information schema",
    "$schema": "http://json-schema.org/draft-04/schema#",
    "type":"object",
    "properties":{
        "port":{
            "type":"object",
            "properties":{
                "id":id_schema,
                "name":nameshort_schema,
                "network_id":{"oneOf":[{"type": "null"}, id_schema ]},
                "tenant_id":id_schema,
                "mac_address": {"oneOf":[{"type": "null"}, mac_schema] },
                "admin_state_up":{"type":"boolean"},
                "bandwidth":bandwidth_schema,
                "binding:switch_port":nameshort_schema,
                "binding:vlan": {"oneOf":[{"type": "null"}, vlan_schema ]}
            },
            "required": ["name"]
        }
    },
    "required": ["port"],
    "additionalProperties": False
}

port_update_schema = {
    "title":"port update information schema",
    "$schema": "http://json-schema.org/draft-04/schema#",
    "type":"object",
    "properties":{
        "port":{
            "type":"object",
            "properties":{
                "name":nameshort_schema,
                "network_id":{"anyOf":[{"type":"null"}, id_schema ] }
            },
            "minProperties": 1,
            "additionalProperties": False
        }
    },
    "required": ["port"],
    "additionalProperties": False
}

localinfo_schema = {
    "title":"localinfo information schema",
    "$schema": "http://json-schema.org/draft-04/schema#",
    "type":"object",
    "properties":{
        "files":{ "type": "object"},
        "inc_files":{ "type": "object"},
        "server_files":{ "type": "object"}
    },
    "required": ["files"]
}

hostinfo_schema = {
    "title":"host information schema",
    "$schema": "http://json-schema.org/draft-04/schema#",
    "type":"object",
    "properties":{
        "iface_names":{
            "type":"object",
            "patternProperties":{
                ".":{ "type": "string"}
            },
            "minProperties": 1
        }
    },
    "required": ["iface_names"]
}

openflow_controller_schema = {
    "title": "network creation information schema",
    "$schema": "http://json-schema.org/draft-04/schema#",
    "type": "object",
    "properties": {
        "ofc": {
            "type": "object",
            "properties": {
                "name": name_schema,
                "dpid": nameshort_schema,
                "ip": nameshort_schema,
                "port": port_schema,
                "type": nameshort_schema,
                "version": nametiny_schema,
                "user": nameshort_schema,
                "password": nameshort_schema
            },
            "required": ["dpid", "type", "ip", "port", "name"]
        }
    },
    "required": ["ofc"],
    "additionalProperties": False
}

of_port_new_schema = {
    "title": "OF port mapping",
    "type": "object",
    "properties": {
        "ofc_id": id_schema,
        "region": nameshort_schema,
        "compute_node": nameshort_schema,
        "pci": pci_extended_schema,
        "switch_dpid": nameshort_schema,
        "switch_port": nameshort_schema,
        "switch_mac": mac_schema
    },
    "required": ["region", "compute_node",  "pci", "switch_dpid"]
}

of_port_map_new_schema = {
    "title": "OF port mapping",
    "$schema": "http://json-schema.org/draft-04/schema#",
    "type": "object",
    "properties": {
        "of_port_mapings": {"type": "array", "items": of_port_new_schema, "minLenght":1},
    },
    "required": ["of_port_mapings"],
    "additionalProperties": False

}
