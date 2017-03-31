#!/usr/bin/env bash
SHELL := /bin/bash

all: clean build  pip install
lite: clean build  pip install_lite

prepare:
	mkdir -p build
	cp *.py build/
	cp MANIFEST.in build/
	cp openvimd.py build/openvimd
	cp ovim.py build/ovim
	cp openvim build/
	cp openflow build/
	cp openvimd.cfg build/
	cp -r scripts build/
	#cd build/scripts; mv service-openvim.sh service-openvim; mv openvim-report.sh openvim-report; mv initopenvim.sh initopenvim
	cp -r database_utils build/

build: prepare
	python -m py_compile build/*.py

clean:
	rm -rf build

pip:
	cd build; ./setup.py sdist

install:
	cd build; python setup.py install

install_lite:
	cd build; python setup.py install --lite



