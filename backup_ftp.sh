#! /bin/bash

servidorftp="mochipa.com.ar"
userftp=backupcliente
passftp=backupcliente

origen=/var/log/odoo/backup
destino=/Odoo/full24backup

ftpurl="ftp://$userftp:$passftp@$servidorftp"

#eliminarantiguos="--delete"

lftp -c "set ftp:list-options -a;
open '$ftpurl'
lcd $origen
cd $destion
mirror --reverse \
       	$eliminarantiguos \
		--verbose "
