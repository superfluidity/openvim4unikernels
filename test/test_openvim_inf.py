import pytest
import time
from fixtures.pre.pre_fixtures_create import *
from fixtures.post.post_fixtures_delete import *
from lib.ssh import *
from lib.test_utils import *


@pytest.mark.usefixtures('pre_init_db', 'pre_create_host', 'pre_create_tenant', 'pre_create_net', 'pre_create_image',
                         'pre_create_flavor', 'post_delete_net', 'post_delete_host')
def test_osm_01_create_vm(request, pre_init_db,
                          pre_create_host,
                          pre_create_tenant,
                          pre_create_net,
                          pre_create_image,
                          pre_create_flavor,
                          post_delete_image,
                          post_delete_flavor,
                          post_delete_vm,
                          post_delete_net,
                          post_delete_host):
    """
    Create a vm and check network connection btw qrouter namespace and vm, evaluate using ping againt the ip given by
    ovs dhcp server. Openvim is launched as a service by pre_launch_openvim_service before regresion start, is stopped
    by  post_stop_openvim_service after test regresion ends.

    :param request: Users argument --config=<test yaml>
    :param pre_init_db: initialize the openvim db
    :param pre_create_host: Create hosts
    :param pre_create_tenant: Create tenant
    :param pre_create_net: Create a mgmt net
    :param pre_create_image: Create an image
    :param pre_create_flavor: Create a flavor
    :param post_delete_image: Delete the image declare by the test
    :param post_delete_flavor: Delete the flavor declare by the test
    :param post_delete_vm: Delete the vm declare by the test
    :param post_delete_net: Delete the mgmt net declare by the test
    :param post_delete_host: remove the host attached by the test
    :return:
    """
    config_path = request.config.getoption('config')
    config = get_config(config_path)
    if not config['fake_mode']:
        vm_id = create_vm_per_host(config, 1)
        assert vm_id
        # get vlan id
        vlan_id = os.environ['OPENVIM_TEST_MGMT_NET_VLAN']
        assert vlan_id
        # get vm ip
        ip = get_vm_ip(vm_id)
        assert ip
        # check ping against the vm
        result = ping_ok(vlan_id, ip)
        assert result


@pytest.mark.usefixtures('pre_init_db', 'pre_create_host', 'pre_create_tenant', 'pre_create_net', 'pre_create_image',
                         'pre_create_flavor', 'post_delete_net','post_delete_host')
def test_osm_02_create_2_vm_ping_btw(request, pre_init_db,
                                     pre_create_host,
                                     pre_create_tenant,
                                     pre_create_net,
                                     pre_create_image,
                                     pre_create_flavor,
                                     post_delete_flavor,
                                     post_delete_image,
                                     post_delete_vm,
                                     post_delete_net,
                                     post_delete_host):
    """
    Create 2 vms and check network connection btw qrouter namespace and vms, after ssh ready check ping btw both vms
    to validate the vlxan mesh btw computes is ok. The vms ips are handle by ovs dhcp server. Openvim is launched as a
    service by pre_launch_openvim_service before regresion start, is stopped by  post_stop_openvim_service after
    test regresion ends.

    :param request: Users argument --config=<test yaml>
    :param pre_init_db: initialize the openvim db
    :param pre_create_host: Create hosts
    :param pre_create_tenant: Create tenant
    :param pre_create_net: Create a mgmt net
    :param pre_create_image: Create an image
    :param pre_create_flavor: Create a flavor
    :param post_delete_image: Delete the image declare by the test
    :param post_delete_flavor: Delete the flavor declare by the test
    :param post_delete_vm: Delete the vm declare by the test
    :param post_delete_net: Delete the mgmt net declare by the test
    :param post_delete_host: remove the host attached by the test
    :return:
    """
    config_path = request.config.getoption('config')
    config = get_config(config_path)

    if not config['fake_mode']:
        vm_id_1 = create_vm_per_host(config, 0)
        assert vm_id_1

        vm_id_2 = create_vm_per_host(config, 1)
        assert vm_id_2

        # get vlan id
        vlan_id = os.environ['OPENVIM_TEST_MGMT_NET_VLAN']
        assert vlan_id

        # get vm ip
        ip_1 = get_vm_ip(vm_id_1)
        ip_2 = get_vm_ip(vm_id_2)
        assert ip_2

        # check ping against the vms
        result = ping_ok(vlan_id, ip_1)
        assert result
        result = ping_ok(vlan_id, ip_2)
        assert result

        # Wait for ssh to be ready
        print "Wait for ssh to be ready"
        time.sleep(90)
        result = ping_ok_btw_2_vms(vlan_id, ip_1, ip_2)
        assert result


@pytest.mark.usefixtures('pre_init_db', 'pre_create_host', 'pre_create_tenant', 'pre_create_net', 'pre_create_image',
                         'pre_create_flavor', 'post_delete_net','post_delete_host')
def test_osm_03_test_service_openvim(request, pre_init_db,
                                     pre_create_host,
                                     pre_create_tenant,
                                     pre_create_net,
                                     pre_create_image,
                                     pre_create_flavor,
                                     post_delete_flavor,
                                     post_delete_image,
                                     post_delete_net,
                                     post_delete_host):
    """
    Create a net, restart openvim service and check net status to avoid issues with preexisting nets during openvim
    startup. Openvim is launched as a service by pre_launch_openvim_service before regresion start, is stopped by
    post_stop_openvim_service after test regresion ends.

    :param request: Users argument --config=<test yaml>
    :param pre_init_db: initialize the openvim db
    :param pre_create_host: Create hosts
    :param pre_create_tenant: Create tenant
    :param pre_create_net: Create a mgmt net
    :param pre_create_image: Create an image
    :param pre_create_flavor: Create a flavor
    :param post_delete_image: Delete the image declare by the test
    :param post_delete_flavor: Delete the flavor declare by the test
    :param post_delete_net: Delete the mgmt net declare by the test
    :param post_delete_host: remove the host attached by the test
    :return:
    """

    net_id = os.environ['OPENVIM_TEST_MGMT_NET']
    status = get_net_status(net_id)
    if 'ACTIVE' in status:
        service_path = os.path.join(os.environ['OPENVIM_ROOT_FOLDER'], 'scripts', 'service-openvim')
        execute_local('{} restart'.format(service_path))
    else:
        # force test fail if net status is not ACTIVE
        assert None

    status = get_net_status(net_id)
    if 'ACTIVE' not in status:
        assert None


def create_vm_per_host(config, host_number=0):
    """
    Create a vm in an specific compute.
    :param config: test config
    :param host_number: compute number to be depolyed. 
    :return: 
    """
    # get env var for server descriptor
    tenant_id = os.environ['OPENVIM_TENANT']
    image_id = os.environ['OPENVIM_TEST_IMAGE']
    flavor_id = os.environ['OPENVIM_TEST_FLAVOR']
    net_id = os.environ['OPENVIM_TEST_MGMT_NET']

    values = {'OPENVIM_TENANT': tenant_id,
              'OPENVIM_TEST_IMAGE': image_id,
              'OPENVIM_TEST_FLAVOR': flavor_id,
              'OPENVIM_TEST_MGMT_NET': net_id,
              'HOST_ID': os.environ['OPENVIM_TEST_HOST_' + str(host_number)]
              }

    descriptor = template_substitute(config['server'], values)
    save_tmp_yaml('tmp.yaml', descriptor)
    # create vm
    openvim_path = os.path.join(os.environ['OPENVIM_ROOT_FOLDER'], 'openvim')
    vm_id = execute_local("{} vm-create {}".format(openvim_path, 'tmp.yaml'))
    vm_id = parse_uuid(vm_id)
    delete_tmp_yaml('tmp.yaml')
    return vm_id
