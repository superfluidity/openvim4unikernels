import pytest
import time
from ...lib.test_utils import *


@pytest.fixture(autouse=True)
def post_install_service():
    """
    Fixture to be executed before test
    :param request: argument for a fixture... can be a list, dict, etc
    :param request:
    :return:
    """
    yield post_install_service
    print "Stoping service openvim "
    service_path = os.path.join(os.environ['OPENVIM_ROOT_FOLDER'], 'scripts', 'service-openvim')
    execute_local("{} stop".format(service_path))


@pytest.fixture()
def post_delete_server(request):
    """
    Fixture to be executed before test
    :param request: argument for a fixture... can be a list, dict, etc
    :param request:
    :return:
    """

    yield post_delete_server

    if hasattr(request, 'config'):
        config_path = request.config.getoption('config')
        config = get_config(config_path)

        if config['create_inf']:
            vm_id = os.environ['OPENVIM_VM']
            openvim_path = os.path.join(os.environ['OPENVIM_ROOT_FOLDER'], 'openvim')
            execute_local("{} vm-delete {}".format(openvim_path, vm_id))


@pytest.fixture()
def post_delete_net(request):
    """
    Fixture to be executed before test
    :param request: argument for a fixture... can be a list, dict, etc
    :param request:
    :return:
    """

    yield post_delete_net

    if hasattr(request, 'config'):
        config_path = request.config.getoption('config')
        config = get_config(config_path)
        if config['create_inf']:
            net_id = os.environ['OPENVIM_TEST_MGMT_NET']
            openvim_path = os.path.join(os.environ['OPENVIM_ROOT_FOLDER'], 'openvim')
            execute_local("{} net-delete -f {}".format(openvim_path, net_id))


@pytest.fixture()
def post_delete_vm():
    """
    Fixture to be executed after test
    :return:
    """
    yield post_delete_vm
    # destroy vm
    openvim_path = os.path.join(os.environ['OPENVIM_ROOT_FOLDER'], 'openvim')
    out = execute_local('{} vm-delete -f'.format(openvim_path))


@pytest.fixture()
def post_delete_flavor():
    """
    Fixture to be executed before test
    :param request: argument for a fixture... can be a list, dict, etc
    :param request:
    :return:
    """

    yield post_delete_flavor

    flavor_id = os.environ['OPENVIM_TEST_FLAVOR']
    openvim_path = os.path.join(os.environ['OPENVIM_ROOT_FOLDER'], 'openvim')
    execute_local("{} flavor-delete -f {}".format(openvim_path, flavor_id))


@pytest.fixture()
def post_delete_image():
    """
    Fixture to be executed before test
    :param request: argument for a fixture... can be a list, dict, etc
    :param request:
    :return:
    """

    yield post_delete_image

    img_id = os.environ['OPENVIM_TEST_IMAGE']
    openvim_path = os.path.join(os.environ['OPENVIM_ROOT_FOLDER'], 'openvim')
    execute_local("{} image-delete -f {}".format(openvim_path, img_id))


@pytest.fixture()
def post_delete_host(request):
    """
    Fixture to be executed before test
    :param request: argument for a fixture... can be a list, dict, etc
    :param request:
    :return:
    """

    yield post_delete_host

    if hasattr(request, 'config'):
        config_path = request.config.getoption('config')
        config = get_config(config_path)
        if config['create_inf']:
            host_ids = search_host_in_env_var()
            for host_ids in host_ids:
                openvim_path = os.path.join(os.environ['OPENVIM_ROOT_FOLDER'], 'openvim')
                execute_local("{} host-remove -f {}".format(openvim_path, os.environ[host_ids]))
        time.sleep(30)


