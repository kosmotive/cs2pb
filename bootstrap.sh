#!/bin/bash

export REF="c45d61062eb3075d39c00914e280acf45423c6e8"

git clone git@github.com:kodikit/cs2pb-bootstrap.git
cd cs2pb-bootstrap
git checkout $REF
cd ..
cp -R cs2pb-bootstrap/django/* django/
rm -rf cs2pb-bootstrap

cd django
./reset.sh init
cat ../bootstrap.sql | sqlite3 db.sqlite3
