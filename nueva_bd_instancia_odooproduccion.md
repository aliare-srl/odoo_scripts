# Nueva base de datos para cliente. Desde linea de comando.

```bash
sudo su odoo
cd
```

## Modulos completos produccion:

```bash
./odoo/odoo-bin -c /etc/odoo.conf -d NOMBREDELABD -i base,web,point_of_sale,sale_management,web_responsive,stock,purchase,account,hw_restaurant_ip_printer,contacts,hr,mrp,hw_escpos_network_printer,board,l10n_ar,l10n_ar_afipws_fe,l10n_ar_afipws,pos_l10n_ar_identification,l10n_ar_pos_einvoice_ticket,l10n_ar_pos_moldeo_fix,10n_latam_base,l10n_latam_invoice_document,ais_pos_show_takein_takeout_money_button,l10n_latam_check,pos_discount,pos_epson_printer_restaurant,google_account,google_drive,google_gmail,kg_hide_menu,product_brand,partner_statement,sh_pos_customer_account,ais_filtro_informes,pos_employee_close_session,pos_hide_cost_price_and_margin,pos_restrict,product_tax_multicompany_default,stock_quantity_history_location,stock_barcodes,hr_expense --load-language es_AR --language es_AR -p 8070 --stop-after-init --without-demo=all
```

### Modulos basicos: 

```bash
./odoo/odoo-bin -c /etc/odoo.conf -d NOMBREDELABD -i base,web,point_of_sale,web_responsive,stock,purchase,account --load-language es_AR --language es_AR -p 8070 --stop-after-init --without-demo=all
```

* Despues de esto reiniciar el odoo porque suele dar errores en los demas clientes:

```bash
sudo systemctl restart odoo.service
```


