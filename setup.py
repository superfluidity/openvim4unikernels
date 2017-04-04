#!/usr/bin/env python

from setuptools import setup, find_packages
from setuptools.command.install import install
from os import system
from setuptools import setup

__name__ = 'lib-osm-openvim'
__version__ = '1.0.0'
__description__ = 'OSM Openvim library'
__author__ = 'ETSI OSM'
__author_email__ = 'alfonso.tiernosepulveda@telefonica.com'
__maintainer__ = 'mirabal'
__maintainer_email__ = 'leonardo.mirabal@altran.com'
__license__ = 'Apache 2.0'
__url__ = 'https://osm.etsi.org/gitweb/?p=osm/openvim.git;a=summary'


__data_files__ = [('osm/openvim/', ['openvimd.cfg']),
                  ('osm/openvim/database_utils/', ['database_utils/vim_db_structure.sql',
                                                   'database_utils/nets.sql',
                                                   'database_utils/of_ports_pci_correspondence.sql',
                                                   'database_utils/host_ranking.sql',
                                                   'database_utils/dump_db.sh',
                                                   'database_utils/init_vim_db.sh',
                                                   'database_utils/migrate_vim_db.sh',
                                                   'database_utils/install-db-server.sh'
                                                   ]),
                  ('osm/openvim/scripts/', ['scripts/service-openvim.sh',
                                            'scripts/openvim-report.sh',
                                            'scripts/service-floodlight.sh',
                                            'scripts/service-opendaylight.sh',
                                            'scripts/initopenvim.sh'
                                            ]),
                  ]


_req = [
    "asn1crypto",
    "cffi",
    "enum34",
    "functools32",
    "idna",
    "ipaddress",
    "packaging",
    "pbr",
    "pkgconfig",
    "pyasn1",
    "pycparser",
    "pycrypto",
    "pyparsing",
    "six",
    "jsonschema",
    "argcomplete",
    "requests",
    "PyYAML",
    "requestsexceptions",
    "netaddr",
    "bottle",
    "MySQL-python",
    "paramiko",
    "libvirt-python"
]

__scripts__ = ['openflow', 'ovim']


class LibOpenvimInstaller(install):
    lite = None
    user_options = install.user_options + [('lite', None, "Don't install without Machine Learning modules.")]

    def initialize_options(self):
        self.lite = None
        install.initialize_options(self)

    def finalize_options(self):
        install.finalize_options(self)

    def run(self):

        cmd = 'ln -sf -v /usr/local/osm/openvim/openvimd.cfg /etc/default/openvimd.cfg '
        system(cmd)
        cmd = 'ln -sf -v /usr/local/osm/openvim/openflow /usr/bin/openflow'
        system(cmd)
        cmd = 'ln -sf -v /usr/local/osm/openvim/ovim.py /usr/bin/ovim'
        system(cmd)
        if not self.lite:
            __scripts__.append('openvim')
            __scripts__.append('openvimd')

            cmd = 'ln -sf -v /usr/local/osm/openvim/openvimd /usr/bin/openvimd'
            system(cmd)
            cmd = 'ln -sf -v /usr/local/osm/openvim/openvim /usr/bin/openvim'
            system(cmd)
            cmd = 'ln -sf -v /usr/local/osm/openvim/scripts/service-openvim.sh /usr/sbin/service-openvim'
            system(cmd)
            cmd = 'ln -sf -v /usr/local/osm/openvim/scripts/openvim-report.sh /usr/sbin/service-report'
            system(cmd)
            cmd = 'ln -sf -v /usr/local/osm/openvim/scripts/service-floodlight.sh /usr/sbin/service-floodlight'
            system(cmd)
            cmd = 'ln -sf -v /usr/local/osm/openvim/scripts/service-opendaylight.sh /usr/sbin/service-opendaylight'
            system(cmd)
            cmd = 'ln -sf -v /usr/local/osm/openvim/scripts/initopenvim.sh /usr/sbin/initopenvim'
            system(cmd)

        install.run(self)


setup(name=__name__,
      version=__version__,
      description=__description__,
      long_description=__description__,
      author=__author__,
      author_email=__author_email__,
      license=__license__,
      maintainer=__maintainer__,
      maintainer_email=__maintainer_email__,
      url=__url__,
      py_modules=['ovim',
                  'openvimd',
                  'vim_db',
                  'httpserver',
                  'RADclass',
                  'auxiliary_functions',
                  'dhcp_thread',
                  'definitionsClass',
                  'host_thread',
                  'vim_schema',
                  'ovim',
                  'openflow_thread',
                  'openflow_conn',
                  'onos',
                  'ODL',
                  'floodlight',
                  ],
      packages=find_packages() + ['database_utils'] + ['scripts'],
      package_dir={__name__: __name__},
      package_data={'database_utils': ['*'], 'scripts': ['*']},
      scripts=__scripts__,
      data_files=__data_files__,
      include_package_data=True,
      cmdclass={'install': LibOpenvimInstaller},
      install_requires=_req
      )


