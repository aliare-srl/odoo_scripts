#!/usr/bin/env python3

import xmlrpc.client
import csv

from pprint import pprint as pp

#~~~~~~INICIO PARÄMETROS~~~~~
USER_NAME = 'desarrolloaliare@gmail.com'
# Preferencia de usuario o mi perfil -> Seguridad de la cuenta -> Clave Api de Desarrollador -> Generar
USER_PASS = 'd294f2965cc499f65f145c66caacf90937666866'

HOST = 'http://localhost:8069'
DB_NAME = 'full24'

# Filtra los stock.quant según ubicación. Se puede ver el id en la url de la ubicación deseada.
# Este id es el de la ubicacion Gdor Express G2515
LOCATION_ID = 277

# ruta y nombre de los archivos a generar. Mejor si es el full path.
PRODUCT_FILE_PATH = '/opt/odoo/csv/productos.csv'
CATEGORY_FILE_PATH = '/opt/odoo/csv/category.csv'

#~~~~~FIN DE PARÄMETROS~~~~~

PRODUCT_CSV_HEADER = [
    'Producto/Código de barras',
    'Producto/Nombre',
    'Producto/Categoría de producto/ID',
    'Cantidad inventariada',
    'Producto/Precio de venta',
]

CATEGORY_CSV_HEADER = ['id', 'nombre', 'parent_id']

def get_product_data(query, location_id, csv_header):

    quants = query('stock.quant', 'search_read',
                   [[('location_id.id', '=', location_id)]],
                   {'fields': ['product_id', 'available_quantity']})

    product_ids = [q['product_id'][0] for q in quants]
    product_quants = {q['product_id'][0]
        : q['available_quantity'] for q in quants}

    products = query('product.product', 'search_read', [[('id', 'in', product_ids)]], {
                     'fields': ['barcode', 'name', 'categ_id', 'list_price']})

    return ({
        csv_header[0]: p['barcode'] if p['barcode'] != 'False' else p['id'],
        csv_header[1]: p['name'],
        csv_header[2]: p['categ_id'][0],
        csv_header[3]: product_quants.get(p['id'], 0),
        csv_header[4]: p['list_price'],
    } for p in products)

        #PRODUCT_CSV_HEADER[0]: p['barcode'] if p['barcode'] != 'False' else p['id'],
        #PRODUCT_CSV_HEADER[1]: p['name'],
        #PRODUCT_CSV_HEADER[2]: p['categ_id'][0],
        #PRODUCT_CSV_HEADER[3]: product_quants.get(p['id'], 0),
        #PRODUCT_CSV_HEADER[4]: p['list_price'],

def get_category_data(query, csv_header):
    categories = query('product.category', 'search_read',[[]], {'fields': ['name', 'parent_id'], 'order':'id asc'})

    # El campo parent_id es m2o y se resuelve en una lista cuyo primer elemento es el id y el segundo elemento el "nombre"
    # por los que debo usar el indice 0
    return ({
        csv_header[0]:c['id'],
        csv_header[1]:c['name'],
        csv_header[2]:c['parent_id'][0] if c['parent_id'] else '',
    } for c in categories)


def export(data, file_fullname, CSV_HEADER):
    with open(file_fullname, mode='w', encoding='utf-8') as file:
        csv_writer = csv.writer(
            file,
            delimiter=',',
            quotechar='"',
            quoting=csv.QUOTE_ALL,
        )

        csv_writer.writerow(CSV_HEADER)

        for d in data:
            row = (d[h] for h in CSV_HEADER)
            csv_writer.writerow(row)


def xmlrpc_make_model_querent(host, db_name, uid, password):
    models = xmlrpc.client.ServerProxy(f'{host}/xmlrpc/2/object')
    return lambda model, method, args, kwargs: models.execute_kw(
        db_name, uid, password, model, method, args, kwargs
    )


def main():

    url = f'{HOST}/xmlrpc/2/common'
    common = xmlrpc.client.ServerProxy(url)
    uid = common.authenticate(DB_NAME, USER_NAME, USER_PASS, {})

    query = xmlrpc_make_model_querent(HOST, DB_NAME, uid, USER_PASS)

    product_data = get_product_data(query, LOCATION_ID, PRODUCT_CSV_HEADER)
    export(product_data, PRODUCT_FILE_PATH, PRODUCT_CSV_HEADER)

    category_data = get_category_data(query, CATEGORY_CSV_HEADER)
    export(category_data, CATEGORY_FILE_PATH, CATEGORY_CSV_HEADER)


if __name__ == '__main__':
    main()
