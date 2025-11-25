# Purga de mail_message en Odoo

Script para borrar registros de tipo notification de la tabla `mail_message` anteriores a una fecha de corte (sin incluirla).


## Requisitos

- Ejecutarse en el **crontab del usuario `postgres`**
- Permisos de ejecución en el script
- Rutas absolutas en la configuración del cron
- Programas flock, time, logger y psql: En general siempre están accesibles para todos
  los usuario y psql en particular para el usuario postgres.


## Implementación.

Suponiendo que el script esté en `/home/admin/odoo_scripts/purge_mail_message`:

1. Verificar que el usuario `postgres` pueda ejecutar el script:
```bash
cd /home/admin/odoo_scripts/purge_mail_message
sudo -u postgres ./mail_message_purge.sh
# Debe fallar con: "ERROR: Debe especificar variable BD_A_PURGAR"
```

**NOTA**: En adelante se asume que estás en el directorio del script (`pwd` -> `/home/admin/odoo_scripts/purge_mail_message`).


### Ejecución Manual.

Para probar el script con variables definidas en línea:

```bash
BD_A_PURGAR=nombre_bd FECHA_CORTE="2024-11-01" BATCH_SIZE=10000 sudo -u postgres ./mail_message_purge.sh
```

Sólo es obligatoria BD_A_PURGAR, las demás son opcionales y se pueden ver sus valores predeterminados en los mismos scripts.


## Configuración del Cron.

1. Ver la configuración de ejemplo:
```bash
cat cron_config.txt
```
Este ejemplo habrá que ajustar la rutas a los ejecutables de ser necesario. 

2. Editar crontab del usuario postgres:
```bash
sudo crontab -eu postgres
```

3. Copiar o tipear la configuración, **ajustando la ruta absoluta de lis scripts y utilitarios** si está en otra ubicación.


## Funcionamiento

- script principal: mail_message_purge.sh
- scripts auxiliares: setup.sh y reset.sh
- Ejemplo de configuración en cron: cron_config.txt

### Horarios de Ejecución Sugeridos.

- **2:58 AM**: Setup - Configura PostgreSQL para optimizar el borrado
- **3:00-5:55 AM**: Purga - Ejecuta cada 5 minutos borrando lotes de registros
- **6:02 AM**: Reset - Restaura configuración de PostgreSQL

### Variables Configurables

- `BD_A_PURGAR`: Base de datos (obligatorio)
- `FECHA_CORTE`: Fecha límite (opcional)
- `BATCH_SIZE`: Tamaño del lote (opcional)
- `LOCK_TIMEOUT`: Timeout de locks (opcional). Si hay algún bloqueo que impida el delete
                  espera este tiempo antes de fallar. Predeterminado en 60s.

## Monitoreo
### Ver logs (TODOS)
```bash
journalctl -t PURGAR_MAIL_MESSAGE
```

### Ver logs en tiempo real(-f muestra a medida que hay nuevos logs, se sale con CTRL+c)
```bash
journalctl -f -t PURGAR_MAIL_MESSAGE
```

### Ver logs del día
```bash
journalctl -t PURGAR_MAIL_MESSAGE --since today
```

### Ver logs de una ventana específica
```bash
journalctl -t PURGAR_MAIL_MESSAGE --since "2024-11-25 03:00" --until "2024-11-25 06:05"
```

### Contar ejecuciones exitosas
```bash
journalctl -t PURGAR_MAIL_MESSAGE --since today | grep -c "Borrados:"
```

### Detectar bloqueos
```bash
journalctl -t PURGAR_MAIL_MESSAGE --since yesterday | grep -i "lock timeout"
```

## Ejemplo de Salida

```
Nov 25 03:00:01 PURGAR_MAIL_MESSAGE: Borrados: 50000 | Última fecha: 2024-06-28 15:23:41
Nov 25 03:00:01 PURGAR_MAIL_MESSAGE: real 12.34
Nov 25 03:05:01 PURGAR_MAIL_MESSAGE: Borrados: 50000 | Última fecha: 2024-06-29 08:15:22
Nov 25 05:55:01 PURGAR_MAIL_MESSAGE: Borrados: 0 | Última fecha: ninguna
```

Cuando muestra `Borrados: 0` significa que ya no quedan registros que purgar.
