#! /bin/bash

# Ante cualquier error finaliza el script

# -- Variables de Configuracion --

# El path al odoo.conf
conf_file=/home/sebastian/modulos/odoo.conf
# El nombre de la bd a respaldar
db_name=modulos
# El path a donde guardar el respaldo
backup_path=/home/sebastian/odoo_respaldo

# -- Fin Variables de Configuraciń --


# Obtiene el data_dir de conf_file
filestore=$(cat $conf_file | sed -nr 's/data_dir *= *(.*)/\1/p')/filestore/$db_name


echo "Filestore: $filestore"
echo "Backup Dir: $backup_path"

# Crea un directorio temporal según https://www.gnu.org/software/coreutils/manual/html_node/mktemp-invocation.html
tmp_dir=$(mktemp -qd) && {
# Es seguro utilizar tmp_dir dentro de este bloque
# Como tmp_dir podría contener estacios hay que usarlo entre comillas
echo "Directorio Temporal: $tmp_dir."

# Hacer el pg_dump al tmp_dir
db_dump_file="$tmp_dir/dump.sql"
echo "Iniciando pg_dump: "$db_name" -> "$db_dump_file""
/usr/bin/pg_dump --no-owner --file="$db_dump_file" -d "$db_name"

#TODO: crear un manifest.json si es posible, ver odoo.service.db.dump

# Si no existe backup_path, intenta crearlo
[ ! -d "$backup_path" ] & mkdir -p "$backup_path";

# comprimir el dump.sql, el manifest.json y el filestore en el destino
zip_filename="$backup_path/"$db_name"_$(date +%Y_%m_%d__%H_%M_%S).zip" 

# para que zip no guarde el full path creo un symbolic link con el prefijo filestore
ln -s "$filestore" "$tmp_dir"/filestore
cd "$tmp_dir"
/usr/bin/zip -r "$zip_filename" ./filestore
/usr/bin/zip -Tjr "$zip_filename" "$db_dump_file"

# por último borro el directorio temporal
echo "Borrando Directorio temporal."
rm -r "$tmp_dir"
echo "$tmp_dir borrado."
}

echo "Fin Backup."
