import yaml
import re
import os
from string import Template
from ssh import *


def save_tmp_yaml(name, data):
    """
    Save a yaml file into a file to be declare in openvim
    :param name: file name
    :param data: 
    :return: 
    """
    with open(name, "w") as text_file:
        text_file.write(data)


def delete_tmp_yaml(name):
    """
    Delete yaml form Filesystem
    :param name: File name
    :return: 
    """
    execute_local('rm {}'.format(name))


def search_host_in_env_var():
    """
    Search for OPENVIM_TEST_HOST_X env var declare by pre_create_host fixture with the host id after creation. 
    :return: All env vars founded
    """
    return search('OPENVIM_TEST_HOST_')


def template_substitute(file_path, values):
    """
    Modify a Yaml template with values.
    :param file_path: template file
    :param values: values to be substituted
    :return: a string with the file content modified
    """
    with open(file_path, 'r') as server_yaml:
        template = Template(server_yaml.read())
        server_yaml = template.safe_substitute(values)
        return server_yaml


def search(reg_ex):
    """
    Search for environment vars. 
    :param reg_ex: regular expresion to be applied during the search
    :return: return results
    """
    result = {}
    for key in os.environ:
        if reg_ex in key:
            result[key] = os.environ[key]
    return result


def parse_uuid(data):
    """
    Parse an UUID value from a string given.
    :param data: String to be evaluated
    :return: the uuid value
    """
    match = re.compile(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', re.I).findall(data)
    if match:
        data = match[0].replace(' ', '')
        data = data.replace('\n', '')
        return data
    else:
        return []


def get_config(data):
    """
    Parse test config file
    :param data: config file path
    :return: config dict 
    """
    with open(data, 'r') as stream:
        try:
            return yaml.load(stream)
        except yaml.YAMLError as exc:
            print(exc)


def get_vm_ip(vm_id):
    """
    Parse vm id IP from openvim client.
    :param vm_id: vm id
    :return: IP value
    """
    openvim_path = os.path.join(os.environ['OPENVIM_ROOT_FOLDER'], 'openvim')
    ip = execute_local("{} vm-list {} -vvv | grep ip_address:".format(openvim_path, vm_id))
    ip = ip.replace('ip_address:', '')
    ip = ip.replace(' ', '')
    return ip


def get_net_status(net_id):
    """
    Parse a net status from openvim client
    :param net_id: network id
    :return: 
    """
    openvim_path = os.path.join(os.environ['OPENVIM_ROOT_FOLDER'], 'openvim')
    net_status = execute_local("{} net-list {} -vvv | grep status:".format(openvim_path, net_id))
    net_status = net_status.replace('status:', '')
    net_status = net_status.replace(' ', '')
    return net_status
