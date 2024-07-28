#!/bin/bash

export REF="65ea3446c0b8d1397e125d94008ecb90e6aaf544"

git clone git@github.com:kodikit/cs2pb-bootstrap.git
cd cs2pb-bootstrap
git checkout $REF
cd ..
cp -R cs2pb-bootstrap/django/* django/
rm -rf cs2pb-bootstrap

cd django
./reset.sh init
cat bootstrap.sql | sqlite3 db.sqlite3
