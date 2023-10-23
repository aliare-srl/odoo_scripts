# Este script permite generar una nueva Master Password.
# Copiar y pegar el resultado en el config del Odoo.
# Depende de la biblioteca passlib que también es utilizada por odoo, por lo que debería estar accesible.

from getpass import getpass
from passlib.context import CryptContext

nuevapass = getpass('Nueva MasterPass: ')
print(CryptContext(schemes=['pbkdf2_sha512']).hash(nuevapass))
