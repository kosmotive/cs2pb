#!/bin/bash

export REF="befd26a8430cf8502f036d041a8165b117f23377"

git clone git@github.com:kodikit/cs2pb-bootstrap.git
cd cs2pb-bootstrap
git checkout $REF
cd ..
cp -R cs2pb-bootstrap/django/* django/
rm -rf cs2pb-bootstrap

cd django
./reset.sh init
