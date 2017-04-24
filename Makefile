#!/usr/bin/env bash
SHELL := /bin/bash

all: clean build pip install
lite: clean build_lite pip_lite install_lite

clean_deb:
	rm -rf .build
clean:
	rm -rf build
	find osm_openvim -name '*.pyc' -delete
	find osm_openvim -name '*.pyo' -delete

prepare_lite:
	#pip install --upgrade setuptools
	mkdir -p build
	VER1=$(shell git describe | sed -e 's/^v//' |cut -d- -f1); \
	VER2=$(shell git describe | cut -d- -f2); \
	VER3=$(shell git describe | cut -d- -f3); \
	echo "$$VER1.dev$$VER2+$$VER3" > build/OVIM_VERSION
	cp MANIFEST.in build/
	sed -i "s/include OPENVIM_VERSION/include OVIM_VERSION/g" build/MANIFEST.in
	sed -i "s/recursive-include osm_openvim/recursive-include lib_osm_openvim/g" build/MANIFEST.in
	sed -i "s/include openflow/include openflow-lib/g" build/MANIFEST.in
	sed -i '/include openvimd/d' build/MANIFEST.in
	sed -i '/include openvim/d' build/MANIFEST.in
	cp README_lite.rst build/README.rst
	cp setup_lite.py build/setup.py
	cp stdeb_lite.cfg build/stdeb.cfg
	cp -r osm_openvim/ build/lib_osm_openvim
	rm build/lib_osm_openvim/httpserver.py
	rm build/lib_osm_openvim/openvimd.cfg
	cp -r database_utils build/lib_osm_openvim/
	cp -r scripts build/lib_osm_openvim/
	cp openflow build/openflow-lib
	sed -i "s/from osm_openvim/from lib_osm_openvim/g" build/openflow-lib
	sed -i "s/import osm_openvim/import lib_osm_openvim/g" build/openflow-lib
	sed -i "s/import osm_openvim; print osm_openvim\.__path__\[0\]/import lib_osm_openvim; print lib_osm_openvim\.__path__\[0\]/g" build/lib_osm_openvim/database_utils/migrate_vim_db.sh

prepare:
	#pip install --upgrade setuptools
	mkdir -p build
	VER1=$(shell git describe | sed -e 's/^v//' |cut -d- -f1); \
	VER2=$(shell git describe | cut -d- -f2); \
	VER3=$(shell git describe | cut -d- -f3); \
	echo "$$VER1.dev$$VER2+$$VER3" > build/OPENVIM_VERSION
	cp MANIFEST.in build/
	cp README.rst build/
	cp setup.py build/
	cp stdeb.cfg build/
	cp -r osm_openvim/  build/
	cp -r scripts build/osm_openvim/
	cp -r database_utils build/osm_openvim/
	cp -r templates build/osm_openvim/
	cp -r test build/osm_openvim/
	cp -r charm build/osm_openvim/
	cp openflow build/
	cp openvim build/
	cp openvimd build/

build: prepare
	python -m py_compile build/osm_openvim/*.py

build_lite: prepare_lite
	python -m py_compile build/lib_osm_openvim/*.py

pip: clean build
	cd build && ./setup.py sdist

pip_lite: clean build_lite
	cd build && ./setup.py sdist

package_openvim: clean prepare
	#apt-get install -y python-stdeb
	cd build && python setup.py --command-packages=stdeb.command sdist_dsc --with-python2=True
	cd build && cp osm_openvim/scripts/python-osm-openvim.postinst deb_dist/osm-openvim*/debian/
	cd build/deb_dist/osm-openvim* && dpkg-buildpackage -rfakeroot -uc -us
	mkdir -p .build
	cp build/deb_dist/python-*.deb .build/

package_lib: clean prepare_lite
	#apt-get install -y python-stdeb
	cd build && python setup.py --command-packages=stdeb.command sdist_dsc --with-python2=True
	cd build/deb_dist/lib-osm-openvim* && dpkg-buildpackage -rfakeroot -uc -us
	mkdir -p .build
	cp build/deb_dist/python-*.deb .build/

package: clean_deb package_openvim package_lib

snap:
	echo "Nothing to be done yet"

install: clean build
	cd build/dist; pip install osm_openvim*

install_lite: clean build_lite
	cd build/dist; pip install lib_osm_openvim-*








