#! /bin/bash

conf_file=/home/sebastian/modulos/odoo.conf
db=modulos
filestore=$(cat $conf_file | sed -nr 's/data_dir *= *(.*)/\1/p')/filestore/$db

echo $filestore

