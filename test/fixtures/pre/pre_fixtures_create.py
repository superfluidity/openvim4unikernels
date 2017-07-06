import pytest
import os
from ...lib.ssh import *
from ...lib.test_utils import *


@pytest.fixture(autouse=True)
def pre_launch_openvim_service():
    """
    Fixture to be executed before test
    :param request: argument for a fixture... can be a list, dict, etc
    :param request:
    :return:
    """
    service_path = os.path.join(os.environ['OPENVIM_ROOT_FOLDER'], 'scripts', 'service-openvim')

    execute_local('{} stop'.format(service_path))
    print "launching service openvim"
    execute_local('{} start'.format(service_path))
    out = execute_local('{} -h '.format(service_path))
    assert out

@pytest.fixture()
def pre_create_flavor(request):
    """
    Fixture to be executed before test
    :param request: argument for a fixture... can be a list, dict, etc
    :param request:
    :return:
    """
    if hasattr(request, 'config'):
        config_path = request.config.getoption('config')
        config = get_config(config_path)
        flavor = config['flavor']

        openvim_path = os.path.join(os.environ['OPENVIM_ROOT_FOLDER'], 'openvim')

        flavor_id = execute_local("{} flavor-create {}".format(openvim_path, flavor))
        flavor_id = parse_uuid(flavor_id)
        assert flavor_id
        os.environ['OPENVIM_TEST_FLAVOR'] = flavor_id


@pytest.fixture()
def pre_create_host(request):
    """
    Fixture to be executed before test
    :param request: argument for a fixture... can be a list, dict, etc
    :param request:
    :return:
    """
    if hasattr(request, 'config'):
        config_path = request.config.getoption('config')
        config = get_config(config_path)

        if config['create_inf']:
            hosts = config['host']
            counter = 0
            for key, value in hosts.iteritems():
                openvim_path = os.path.join(os.environ['OPENVIM_ROOT_FOLDER'], 'openvim')

                host_id = execute_local("{} host-add {}".format(openvim_path, value))
                host_id = parse_uuid(host_id)
                assert host_id
                os.environ['OPENVIM_TEST_HOST_' + str(counter)] = host_id
                counter += 1


@pytest.fixture()
def pre_create_image(request):
    """
    Fixture to be executed before test
    :param request: argument for a fixture... can be a list, dict, etc
    :param request:
    :return:
    """
    if hasattr(request, 'config'):
        config_path = request.config.getoption('config')
        config = get_config(config_path)
        img = config['image']

        openvim_path = os.path.join(os.environ['OPENVIM_ROOT_FOLDER'], 'openvim')
        image_id = execute_local("{} image-create {}".format(openvim_path, img))
        image_id = parse_uuid(image_id)
        assert image_id
        os.environ['OPENVIM_TEST_IMAGE'] = image_id


@pytest.fixture()
def pre_create_image(request):
    """
    Fixture to be executed before test
    :param request: argument for a fixture... can be a list, dict, etc
    :param request:
    :return:
    """
    if hasattr(request, 'config'):
        config_path = request.config.getoption('config')
        config = get_config(config_path)
        img = config['image']
        openvim_path = os.path.join(os.environ['OPENVIM_ROOT_FOLDER'], 'openvim')
        image_id = execute_local("{} image-create {}".format(openvim_path, img))
        image_id = parse_uuid(image_id)
        assert image_id
        os.environ['OPENVIM_TEST_IMAGE'] = image_id


@pytest.fixture()
def pre_create_net(request):
    """
    Fixture to be executed before test
    :param request: argument for a fixture... can be a list, dict, etc
    :return:
    """
    if hasattr(request, 'config'):
        config_path = request.config.getoption('config')
        config = get_config(config_path)
        if config['create_inf']:
            net_yaml = config['net']
            openvim_path = os.path.join(os.environ['OPENVIM_ROOT_FOLDER'], 'openvim')
            net_id = execute_local("{} net-create {}".format(openvim_path, net_yaml))
            net_id = parse_uuid(net_id)
            assert net_id

            vlan = execute_local("{} net-list {} -vvv | grep provider:vlan:".format(openvim_path, net_id))
            vlan = vlan.replace('provider:vlan:','')
            vlan = vlan.replace(' ', '')
            vlan = vlan.replace('\n', '')

            os.environ['OPENVIM_TEST_MGMT_NET'] = net_id
            os.environ['OPENVIM_TEST_MGMT_NET_VLAN'] = vlan


@pytest.fixture()
def pre_create_tenant(request):
    """
    Fixture to be executed before test
    :param request: argument for a fixture... can be a list, dict, etc
    :param monkeypatch:
    :return:
    """

    if hasattr(request, 'config'):
        config_path = request.config.getoption('config')
        config = get_config(config_path)
        tenant_yaml = config['tenant']
        openvim_path = os.path.join(os.environ['OPENVIM_ROOT_FOLDER'], 'openvim')

        tenant_id = execute_local("{} tenant-create {}".format(openvim_path, tenant_yaml))
        tenant_id = parse_uuid(tenant_id)
        assert tenant_id
        os.environ['OPENVIM_TENANT'] = tenant_id


@pytest.fixture()
def pre_init_db(request):
    """
    Fixture to be executed before test
    :param request: argument for a fixture... can be a list, dict, etc
    :param request:
    :return:
    """
    if hasattr(request, 'config'):
        config_path = request.config.getoption('config')
        config = get_config(config_path)
        if config['create_inf']:
            init_db_path = os.path.join(os.environ['OPENVIM_ROOT_FOLDER'], 'database_utils', 'init_vim_db.sh')
            execute_local('{}'.format(init_db_path))
