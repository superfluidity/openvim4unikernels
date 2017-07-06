#!/usr/bin/env python

from setuptools import setup

__name = 'lib_osm_openvim'
__version = open('OVIM_VERSION').read().strip()
__description = 'OSM Openvim library'
__author = 'ETSI OSM'
__author_email = 'alfonso.tiernosepulveda@telefonica.com'
__maintainer = 'mirabal'
__maintainer_email = 'leonardo.mirabal@altran.com'
__license = 'Apache 2.0'
__url = 'https://osm.etsi.org/gitweb/?p=osm/openvim.git;a=summary'

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
    "pytest",
    "pexect"
]

__scripts__ = ['openflow-lib']

setup(name=__name,
      version=__version,
      description=__description,
      long_description=__description,
      author=__author,
      author_email=__author_email,
      license=__license,
      maintainer=__maintainer,
      maintainer_email=__maintainer_email,
      url=__url,
      packages=[__name],
      package_dir={__name: __name},
      scripts=__scripts__,
      package_data={'lib_osm_openvim': ['*']},
      include_package_data=True,
      install_requires=_req
      )


