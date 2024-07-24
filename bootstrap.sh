#!/bin/bash

export REF="13e28581333d883d682a65ff84132b70d46a822a"

git clone git@github.com:kodikit/cs2pb-bootstrap.git
cd cs2pb-bootstrap
git checkout $REF
cd ..
cp -R cs2pb-bootstrap/django/* django/
rm -rf cs2pb-bootstrap

cd django
./reset.sh init
cat bootstrap.sql | sqlite3 db.sqlite3
