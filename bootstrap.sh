#!/bin/bash

export REF="2d0bdc5c37efc9805e71cd869478d82dc93a39ec"

if [ -f .no-bootstrap ]; then
    echo "Bootstrap by accident? Bootstrap is blocked."
    echo "Remove the file .no-bootstrap to bootstrap."
    exit
fi

git clone git@github.com:kodikit/cs2pb-bootstrap.git
cd cs2pb-bootstrap
git -c advice.detachedHead=false checkout $REF
cd ..
cp -R cs2pb-bootstrap/django/* ./django/
cp cs2pb-bootstrap/envvars.development ./
cp cs2pb-bootstrap/envvars.production ./
rm -rf cs2pb-bootstrap

source envvars.development
cd django
./reset.sh init
cat bootstrap.sql | sqlite3 db.sqlite3
