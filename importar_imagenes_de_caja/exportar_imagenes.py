# extrae las imagenes en archivos jpg, el nombre que les dá es cod_barra.jpg 
# graba una carpeta imagenes_exportadas en el lugar donde se está ejecutando.
# configurar los datos de conexion al sql server 2000 de caja.
import pyodbc
import os

# Configuración de conexión
conn = pyodbc.connect(
    "DRIVER={SQL Server};"
    "SERVER=SERVER;"
    "DATABASE=caja_dados_LOCAL;"
    "UID=sa;"
    "PWD=aidepocente;"
)

cursor = conn.cursor()

cursor.execute("""
    SELECT cod_barra, imagen
    FROM articulos
    WHERE imagen IS NOT NULL
      AND DATALENGTH(imagen) > 0
      AND cod_barra IS NOT NULL
      AND LTRIM(RTRIM(cod_barra)) <> ''
      AND INHABILITADO = 0
      
    ORDER BY id_art;
""")

# Carpeta destino
output_folder = "imagenes_exportadas"
os.makedirs(output_folder, exist_ok=True)

for cod_barra, img_data in cursor:
    cod = str(cod_barra).strip()

    filename = f"{cod}.jpg"       # ajustar si tus imágenes no son JPG
    path = os.path.join(output_folder, filename)

    with open(path, "wb") as f:
        f.write(img_data)

    print(f"Guardado: {path}")

cursor.close()
conn.close()
