# luego de copiar toda la carpeta de jpgs ejecutar este archivo.  modificar IMAGES_PATH
import os
import base64
import xmlrpc.client

# CONFIGURACIÓN
url = "http://127.0.0.1:8069"
db = "dados"
username = "desarrolloaliare@gmail.com"
password = "ai102030abc"

# Carpeta donde están las imágenes
IMAGES_PATH = "/home/admin/clientes/dados/jpgs"

# CONEXIÓN
common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
uid = common.authenticate(db, username, password, {})

models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")

# RECORRER ARCHIVOS
for filename in os.listdir(IMAGES_PATH):
    if not filename.lower().endswith((".jpg", ".jpeg", ".png")):
        continue

    barcode = os.path.splitext(filename)[0]  # nombre sin extensión
    img_path = os.path.join(IMAGES_PATH, filename)

    print(f"Procesando {filename} → barcode {barcode}")

    # Buscar producto por código de barras
    product_ids = models.execute_kw(
        db, uid, password,
        'product.template', 'search',
        [[('barcode', '=', barcode)]]
    )

    if not product_ids:
        print(f"  ❌ No encontrado en Odoo: {barcode}")
        continue

    product_id = product_ids[0]

    # Leer imagen
    with open(img_path, "rb") as f:
        image_data = base64.b64encode(f.read()).decode('utf-8')

    # Subir imagen al producto
    models.execute_kw(
        db, uid, password,
        'product.template', 'write',
        [[product_id], {'image_1920': image_data}]
    )
    print(f"  ✔ Imagen cargada en producto {product_id}")

