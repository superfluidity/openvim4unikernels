import os

def pytest_addoption(parser):
    parser.addoption('--config',
                     help='Indicate tests are run on CI server')
    os.environ['OPENVIM_ROOT_FOLDER'] = os.getcwd()
