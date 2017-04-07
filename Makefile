#!/usr/bin/env bash
SHELL := /bin/bash

all: clean build  pip install
lite: clean build  pip install_lite

prepare:
	mkdir -p build
	cp *.py build/
	cp MANIFEST.in build/
	cp openvimd.py openvimd; cp openvimd build/openvimd
	cp ovim.py ovim; cp ovim build/ovim
	cp openvim build/
	cp openflow build/
	cp openvimd.cfg build/
	cp -r scripts build/
	cp -r database_utils build/

build: prepare
	python -m py_compile build/*.py

clean:
	rm -rf build
	rm -rf openvimd ovim

pip:
	cd build; ./setup.py sdist

install:
	cd build/dist; pip  install lib*

install_lite:
	cd build/dist; pip  install lib*





