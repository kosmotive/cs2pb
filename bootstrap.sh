#!/bin/bash

export REF="9af8c4fdfbd027508813bdca352e105229d3041b"

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
rm -rf cs2pb-bootstrap

source envvars.development
cd django
./reset.sh init
cat bootstrap.sql | sqlite3 db.sqlite3
