# Laboratorio: Aprovisionamiento Automatizado con midPoint y Asterisk PBX

Este proyecto demuestra la integración y automatización del ciclo de vida de identidades utilizando **midPoint (IdM)** para el aprovisionamiento de extensiones telefónicas (anexos) en un servidor de telecomunicaciones **Asterisk PBX** con persistencia en **MariaDB**.

## 🚀 Arquitectura del Proyecto
El entorno se encuentra completamente contenedorizado para garantizar su portabilidad:
* **midPoint:** Motor de Gestión de Identidades (IdM).
* **MariaDB:** Base de datos que almacena los peers y configuraciones de Asterisk (`sippeers`).

## 🛠️ Comandos de Verificación del Sistema
Para auditar la base de datos y confirmar que midPoint aprovisionó correctamente el **Anexo 101**, se utiliza:

```sql
USE asterisk;
SELECT name, secret FROM sippeers;

# 1. Crear el archivo vacío
touch README.md

# 2. Abrir el editor de texto integrado de Ubuntu
nano README.md
xit
exit
eof
