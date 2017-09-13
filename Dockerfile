FROM ubuntu:16.04

RUN  apt-get update && \
  DEBIAN_FRONTEND=noninteractive apt-get -y install git make python python-pip debhelper && \
  DEBIAN_FRONTEND=noninteractive pip install -U pip && \
  DEBIAN_FRONTEND=noninteractive pip install -U setuptools setuptools-version-command stdeb


