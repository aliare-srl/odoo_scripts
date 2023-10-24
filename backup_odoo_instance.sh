#! /bin/bash

# Ante cualquier error finaliza el script

# -- Variables de Configuracion --

# El path al odoo.conf
conf_file=/home/sebastian/modulos/odoo.conf
# El nombre de la bd a respaldar
db_name=modulos
# El path a donde guardar el respaldo
backup_path=/home/sebastian/odoo_respaldo

# -- Fin Variables de Configuración --

# -- Variables de los comandos --
cmd_dump=/usr/bin/pg_dump 
sql_psql=/usr/bin/psql
cmd_zip=/usr/bin/zip

# Crea un directorio temporal según https://www.gnu.org/software/coreutils/manual/html_node/mktemp-invocation.html
tmp_dir=$(mktemp -qd) && {

# Hacer el pg_dump al tmp_dir
db_dump_file="$tmp_dir/dump.sql"
echo "Iniciando pg_dump: "$db_name" -> "$db_dump_file""
$cmd_dump --no-owner --file="$db_dump_file" -d "$db_name"

# Crea un manifest.json, ver odoo.service.db.dump
manifest_file="$tmp_dir"/manifest.json
# Estos valores están fijos en odoo.release
odoo_version="15.0"
odoo_version_info=[15,0,0,"final",0,""]
odoo_major_version="15.0"
pg_version=$($sql_psql -V | sed -r 's/.* ([0-9\.]+) .*/\1/p')

odoo_installed_modules=$($sql_psql -d $db_name -P pager=off \
-Atc "select  name, latest_version from ir_module_module where state='installed';" \
| sed -nr 's/(.*)\|(.*)/"\1":"\2",/ ; $s/,$// ; p')

odoo_installed_modules1="{${odoo_installed_modules}}"

echo "{'odoo_dump':'1','db_name:'$db_name','version':'$odoo_version','version_info':'$odoo_version_info',\
'major_version':'$odoo_major_version','pg_version':'$pg_version','modules':{$odoo_installed_modules}}" > $manifest_file

# Si no existe backup_path, intenta crearlo
[ ! -d "$backup_path" ] & mkdir -p "$backup_path";


# Obtiene el data_dir de conf_file
filestore=$(cat $conf_file | sed -nr 's/data_dir *= *(.*)/\1/p')/filestore/$db_name
# comprimir el dump.sql, el manifest.json y el filestore en el destino
zip_filename="$backup_path/"$db_name"_$(date +%Y_%m_%d__%H_%M_%S).zip" 

# para que zip no guarde el full path creo un symbolic link con el prefijo filestore
ln -s "$filestore" "$tmp_dir"/filestore
cd "$tmp_dir"
$cmd_zip -qr "$zip_filename" ./filestore
$cmd_zip -qjr "$zip_filename" "$manifest_file"
$cmd_zip -qTjr "$zip_filename" "$db_dump_file"


# por último borro el directorio temporal
echo "Borrando Directorio temporal."
rm -r "$tmp_dir"
echo "$tmp_dir borrado."
}

echo "Fin Backup."
