#!/bin/bash

export REF="eeb746f1642aa46cee01415c19ed5d700337f0f4"

git clone git@github.com:kodikit/cs2pb-bootstrap.git
cd cs2pb-bootstrap
git checkout $REF
cd ..
cp -R cs2pb-bootstrap/django/* django/
rm -rf cs2pb-bootstrap

cd django
./reset.sh init
cat bootstrap.sql | sqlite3 db.sqlite3
