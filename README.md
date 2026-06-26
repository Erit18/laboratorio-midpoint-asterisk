# Laboratorio de Integración de Sistemas: Infraestructura Unificada de Comunicaciones y Gestión de Identidad

Este proyecto implementa una arquitectura de microservicios utilizando contenedores para integrar una central telefónica y un gestor de identidades corporativo.

## 🚀 Tecnologías Utilizadas
* **Orquestación:** Docker y Docker Compose.
* **Motor de Comunicación:** Asterisk (PBX).
* **Gestión de Identidad (IAM):** midPoint.
* **Base de Datos:** PostgreSQL.

---

## 🛠️ Instrucciones de Despliegue (Para la Demostración)

### 1. Levantar la Infraestructura
Abre tu terminal en la carpeta del proyecto y ejecuta:
\`\`\`bash
docker compose up -d
\`\`\`
> **Nota:** midPoint es un sistema robusto en Java. Espera unos **3 a 5 minutos** hasta que termine de inyectar sus tablas en PostgreSQL antes de hacer cualquier prueba.

### 2. Sincronización de Usuarios (Script Puente)
El flujo de aprovisionamiento automatiza la creación de usuarios desde la lógica de identidad hacia la configuración de Asterisk. Para registrar un nuevo agente, ejecuta el script de integración indicando la extensión y la contraseña:
\`\`\`bash
./sync_asterisk.sh 1001 clave1001
./sync_asterisk.sh 1002 clave1002
\`\`\`
Este script configurará las credenciales SIP, actualizará el Dialplan (Enrutamiento) con políticas de grabación, y recargará el motor SIP de Asterisk en caliente.

### 3. Prueba de Concepto (Llamada y Evidencias)
1. Abre tu Softphone (ej. Zoiper o MicroSIP).
2. Configura tu cuenta apuntando a la IP local de tu máquina usando el puerto **5060 (UDP)**.
3. Realiza una llamada entre las dos extensiones creadas (ej. del 1001 al 1002). **Contesta la llamada** y luego cuelga.

### 4. Extracción de Evidencias (CDRs y Grabaciones)
Al colgar la llamada, el contenedor de Asterisk exportará automáticamente los datos a tu sistema anfitrión:
* **Grabación de la llamada:** Revisa la carpeta local \`asterisk/grabaciones/\` para escuchar el archivo \`.wav\`.
* **CDRs (Registros de Detalle de Llamadas):** Revisa la carpeta local \`asterisk/registros_cdr/\` y abre el archivo \`Master.csv\` para ver la fecha, hora, duración y estado de la llamada.

### 5. Auditoría de Seguridad (ISO 27001)
Puedes acceder al panel web de midPoint ingresando a \`http://localhost:8080\` (o la IP de tu máquina). El sistema cuenta con logs de auditoría en la sección de reportes para garantizar la trazabilidad de accesos.
