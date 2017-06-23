#!/bin/sh
rm -rf pool
rm -rf dists
mkdir -p pool/openvim
mv .build/*.deb pool/openvim/
mkdir -p dists/unstable/openvim/binary-amd64/
apt-ftparchive packages pool/openvim > dists/unstable/openvim/binary-amd64/Packages
gzip -9fk dists/unstable/openvim/binary-amd64/Packages
