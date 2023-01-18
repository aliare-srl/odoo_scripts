#!/bin/bash

servidorftp="mochipa.com.ar"
userftp=backupcliente
passftp=backupcliente

origen=/var/log/odoo/backup
# Full path en el servidor ftp. La carpeta debe existir
destino=/Odoo/full24backup

ftpurl="ftp://$userftp:$passftp@$servidorftp"

eliminarantiguos="--delete"

# Copias a conservar 
conservar=5
((conservar=conservar+1)) # necesario para saltear n archivos, hay que especificar n + 1

#Elimina los archivos mas viejos, dejando solo los indicados en la variable conservar
ls -tp | grep -v '\$' | tail -n +$conservar | xargs -I {} -d '\n' -r rm -- {}

lftp -c "set ftp:list-options -a;
open '$ftpurl';
lcd $origen;
cd $destino;
mirror --reverse \
       	$eliminarantiguos \
		--verbose ; "
