#!/usr/bin/env bash
SHELL := /bin/bash

all: clean build pip install
lite: clean build_lite pip_lite install_lite

clean:
	rm -rf build

prepare_lite:
	mkdir -p build
	cp -r  osm_openvim/ build/lib_osm_openvim
	rm build/lib_osm_openvim/httpserver.py
	rm build/lib_osm_openvim/openvimd.cfg
	cp -r database_utils build/lib_osm_openvim/
	cp -r scripts build/lib_osm_openvim/
	cp MANIFEST.in build/
	cp setup_lite.py build/setup.py
	cp openflow build/
	sed -i "s/from osm_openvim/from lib_osm_openvim/g" build/openflow
	sed -i "s/import osm_openvim/import lib_osm_openvim/g" build/openflow
	sed -i "s/import osm_openvim; print osm_openvim.__path__[0]/import lib_osm_openvim; print lib_osm_openvim.__path__[0]/g" build/lib_osm_openvim/database_utils/migrate_vim_db.sh
	sed -i "s/recursive-include osm_openvim */recursive-include lib_osm_openvim */g" build/MANIFEST.in
	sed '/include openvimd/d' build/MANIFEST.in
	sed '/include openvim/d' build/MANIFEST.in

prepare:
	mkdir -p build
	cp -r osm_openvim/  build/
	cp -r scripts build/osm_openvim/
	cp -r database_utils build/osm_openvim/
	cp -r templates build/osm_openvim/
	cp -r test build/osm_openvim/
	cp -r charm build/osm_openvim/
	cp MANIFEST.in build/
	cp setup.py build/
	cp openflow build/
	cp openvim build/
	cp openvimd build/

build: prepare
	python -m py_compile build/osm_openvim/*.py

build_lite: prepare_lite
	python -m py_compile build/lib_osm_openvim/*.py

#deb:
#	cd build && python setup.py --command-packages=stdeb.command bdist_deb
#
#debianize:
#	cd build && python setup.py --command-packages=stdeb.command debianize

pip: clean build
	cd build; ./setup.py sdist

pip_lite: clean build_lite
	cd build; ./setup.py sdist

install: clean build
	cd build/dist; pip  install osm_openvim*

install_lite: clean build_lite
	cd build/dist; pip  install  lib_osm_openvim-*








