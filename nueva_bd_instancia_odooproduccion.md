# Nueva base de datos para cliente. Desde linea de comando.

```bash
sudo su odoo
cd
```

## Modulos completos produccion:

```bash
./odoo/odoo-bin -c /etc/odoo.conf -d NOMBREDELABD -i base,web,point_of_sale,sale_management,web_responsive,stock,purchase,account,hw_restaurant_ip_printer,contacts,hr,mrp,hw_escpos_network_printer,board,l10n_ar,l10n_ar_afipws_fe,l10n_ar_afipws,pos_l10n_ar_identification,l10n_ar_pos_einvoice_ticket,l10n_ar_pos_moldeo_fix,10n_latam_base,l10n_latam_invoice_document,ais_pos_show_takein_takeout_money_button,l10n_latam_check,pos_discount,pos_epson_printer_restaurant,google_account,google_drive,google_gmail,kg_hide_menu,product_brand,partner_statement,sh_pos_customer_account,ais_filtro_informes,pos_employee_close_session,pos_hide_cost_price_and_margin,pos_restrict,product_tax_multicompany_default,stock_quantity_history_location,stock_barcodes,hr_expense,l10n_ar_reports,ais_pos_discount_auth,ais_credit_card_instalment_pos,l10n_ar_rg5614,l10n_ar_rg5616,ais_bi_pos_receipt_in_backend,widget_preview_image,ais_corrige_price_total_pos_report,ais_product_tracking,ais_sale_global_discount,mass_price_update,ais_pos_custom_validation --load-language es_AR --language es_AR -p 8070 --stop-after-init --without-demo=all
```

### Modulos basicos: 

```bash
./odoo/odoo-bin -c /etc/odoo.conf -d NOMBREDELABD -i base,web,point_of_sale,web_responsive,stock,purchase,account --load-language es_AR --language es_AR -p 8070 --stop-after-init --without-demo=all
```

* Despues de esto reiniciar el odoo porque suele dar errores en los demas clientes:

```bash
sudo systemctl restart odoo.service
```
### Para instalar modulos puntualmente:
```bash
/opt/odoo/odoo/odoo-bin -c /etc/odoo.conf -d NOMBREDELABD -i NOMBRETECNICODELMODULO --load-language es_AR --language es_AR -p 8070 --stop-after-init --without-demo=all
```
- En caso de necesitar más tiempo para la instalación de un módulo, puede agregarse el parámtetro `--limit-time-real=99999` para evitar timeouts.
- En caso de necesitar un update en vez de una instalacion cambiar -i por -u Ej: /etc/odoo.conf -d NOMBREDELABD -u NOMBRETECNICODELMODULO
- En caso de necesitar ver un log al ejecutar ese comando agregar al final: --logfile ""

## Para finalizar con el alta de una nueva BD de produccion recordar realizar las siguientes configuraciones:
- Configurar los backups en el servidor de respaldo siguiendo el instructivo de https://github.com/aliare-srl/odoo_scripts/blob/master/README.md de los archivos "backup_ftp.sh" y "backup_odoo_instance.sh"
- Configurar dominio en: https://www.dynu.com/
- REGISTRAR EL certificado en: https://github.com/aliare-srl/Documentacion/blob/main/Instalaci%C3%B3n%20ssl%20con%20certbot%20plug-in%20y%20certificado.md





