#!/bin/bash

export REF="442394d73390777e75103d9c6386a83ddea0bfb0"

git clone git@github.com:kodikit/cs2pb-bootstrap.git
cd cs2pb-bootstrap
git checkout $REF
cd ..
cp -R cs2pb-bootstrap/django/* django/
rm -rf cs2pb-bootstrap

cd django
./reset.sh init
