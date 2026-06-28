# Laboratorio de Integración de Sistemas: Infraestructura Unificada de Comunicaciones y Gestión de Identidad

Este proyecto implementa una arquitectura de microservicios utilizando contenedores para integrar una central telefónica y un gestor de identidades corporativo.

## 🚀 Tecnologías Utilizadas
* **Orquestación:** Docker y Docker Compose.
* **Motor de Comunicación:** Asterisk (PBX).
* **Gestión de Identidad (IAM):** midPoint.
* **Base de Datos:** PostgreSQL.
* **Panel de Evidencias (CDR):** Python + Flask, contenedorizado, con reproductor de grabaciones integrado (interfaz inspirada en el módulo "CDR Reports" de FreePBX/Issabel).

---

## ⚡ Instalación desde cero (clonando el repo en una máquina nueva)

**Lee esto primero si es la primera vez que levantas el proyecto en esta máquina.** La imagen de Docker `evolveum/midpoint:latest` **no auto-genera su esquema de base de datos ni sus datos iniciales** (usuario `administrator`, roles, configuración del sistema). Si solo haces `docker compose up -d` sin más, midPoint se quedará en loop de reinicio o, si parece levantar, dará `500 Internal Server Error` al intentar iniciar sesión. Esto nos tomó varias horas de debugging la primera vez — el script `init_midpoint.sh` automatiza todo ese proceso.

```bash
docker compose up -d
# Espera ~30s a que la base de datos esté healthy (docker compose ps)
./init_midpoint.sh
```

El script hace, en orden:
1. Crea las extensiones de PostgreSQL que midPoint necesita (`pgcrypto`, `pg_trgm`, `intarray`) — sin ellas, la creación de tablas falla en silencio.
2. Crea el esquema de repositorio (`ninja.sh run-sql --mode repository --create`).
3. Crea el esquema de auditoría (`ninja.sh run-sql --mode audit --create`) — **fácil de olvidar**, es un paso separado del anterior y su ausencia causa un 500 específicamente al hacer login (no al arrancar).
4. Importa los ~171 archivos de `initial-objects` (roles, archetypes, configuración del sistema, etc.). **Esto tarda entre 15 y 50 minutos** dependiendo de qué tan rápida sea la máquina — cada importación reinicia el contexto de Spring internamente, es lento por diseño de la herramienta, no es un error.
5. Asigna la contraseña del usuario `administrator` y lo desbloquea (el objeto semilla viene sin contraseña por política de seguridad de midPoint).
6. Reinicia midPoint y espera a que esté `healthy`.

Puedes pasar una contraseña personalizada para el administrador como argumento:
```bash
./init_midpoint.sh "MiClaveSegura123!"
```
Si no se especifica, usa `Callcenter2026!` por defecto.

**No vuelvas a correr este script** una vez que midPoint ya esté funcionando — es solo para la primera inicialización de una base de datos vacía. Si necesitas reiniciar todo desde cero (por ejemplo, en otra máquina), borra los volúmenes primero:
```bash
docker compose down
docker volume rm laboratorio-midpoint-asterisk-main_db_data laboratorio-midpoint-asterisk-main_midpoint_home
docker compose up -d
./init_midpoint.sh
```

---

## 🛠️ Instrucciones de Despliegue (Para la Demostración)

> Esta sección asume que ya corriste `init_midpoint.sh` al menos una vez en esta máquina, o que el volumen de base de datos ya tiene los datos semilla (por ejemplo, si nunca borraste los volúmenes desde la primera instalación).

### 1. Levantar la Infraestructura
Abre tu terminal en la carpeta del proyecto y ejecuta:
```bash
docker compose up -d
```
> **Nota:** midPoint es un sistema robusto en Java. Espera unos **3 a 5 minutos** hasta que termine de iniciar antes de hacer cualquier prueba.

### 2. Sincronización de Usuarios (Script Puente)
El flujo de aprovisionamiento automatiza la creación de usuarios desde la lógica de identidad hacia la configuración de Asterisk. Para registrar un nuevo agente, ejecuta el script de integración indicando la extensión y la contraseña:
```bash
./sync_asterisk.sh 1001 clave1001
./sync_asterisk.sh 1002 clave1002
```
Este script configurará las credenciales SIP, actualizará el Dialplan (Enrutamiento) con políticas de grabación, y recargará el motor SIP de Asterisk en caliente.

### 3. Prueba de Concepto (Llamada y Evidencias)
1. Abre tu Softphone (ej. Zoiper o MicroSIP).
2. Configura tu cuenta apuntando a la IP local de tu máquina usando el puerto **5060 (UDP)**.
3. Realiza una llamada entre las dos extensiones creadas (ej. del 1001 al 1002). **Contesta la llamada** y luego cuelga.

### 4. Extracción de Evidencias (CDRs y Grabaciones)
Al colgar la llamada, el contenedor de Asterisk exportará automáticamente los datos a tu sistema anfitrión:
* **Grabación de la llamada:** Revisa la carpeta local `asterisk/grabaciones/` para escuchar el archivo `.wav`.
* **CDRs (Registros de Detalle de Llamadas):** Revisa la carpeta local `asterisk/registros_cdr/` y abre el archivo `Master.csv` para ver la fecha, hora, duración y estado de la llamada.

Estas evidencias también se visualizan de forma integrada en el **Panel Web de CDR** (ver sección 6) — no es necesario abrir el CSV ni buscar los .wav a mano para la demostración.

### 5. Auditoría de Seguridad (ISO 27001)
Puedes acceder al panel web de midPoint ingresando a `http://localhost:8080` (o la IP de tu máquina). El sistema cuenta con logs de auditoría en la sección de reportes para garantizar la trazabilidad de accesos.

---

## 📞 6. Panel Web de Registro de Llamadas (CDR Viewer)

Como complemento visual a la sección 4, el proyecto incluye un **microservicio adicional** (`cdr-panel/`) que expone una interfaz web similar al módulo "CDR Reports" de FreePBX/Issabel: lista las llamadas con fecha, origen, destino, duración y estado, con un botón ▶ para reproducir la grabación correspondiente directamente desde el navegador.

**No requiere FreePBX ni Issabel** — es un backend ligero en Flask que lee directamente los archivos que Asterisk ya genera (`Master.csv` y los `.wav` de `MixMonitor`), montados como volúmenes de solo lectura. No modifica ni interfiere con la configuración de Asterisk, midPoint, ni el script `sync_asterisk.sh`.

### Cómo levantarlo
Ya viene integrado en el `docker-compose.yml` principal, así que con el `docker compose up -d` de la sección 1 es suficiente. Si lo agregaste después o necesitas reconstruirlo:
```bash
docker compose up -d --build cdr-panel
```

### Cómo verlo
Abre en el navegador:
```
http://localhost:8088
```
(o `http://<IP_DE_LA_VM>:8088` si accedes desde otra máquina de la misma red, por ejemplo desde Windows hacia la VM Debian).

La tabla se actualiza solo cada 15 segundos, o al hacer clic en "⟳ Actualizar". Incluye filtros por extensión, fecha y estado de la llamada.

### Cómo funciona internamente (por si el profesor pregunta)
* Lee `Master.csv` con el formato estándar de 18 columnas del módulo `cdr_csv` de Asterisk (sin necesidad de configuración adicional, es el formato que Asterisk genera por defecto).
* Empareja cada línea del CDR con su grabación `.wav` buscando un archivo que empiece con `<extensión>-<AAAAMMDD-HHMM>`. **Detalle importante:** el `MixMonitor` del dialplan (en `sync_asterisk.sh`) corre en la extensión que **recibe** la llamada, así que el archivo se nombra con el número de **destino** (`dst`), no el de origen (`src`). El backend prueba ambos campos para mayor robustez.
* Sirve los `.wav` mediante un endpoint propio (`/recordings/<archivo>`) que el reproductor de audio HTML5 consume directamente, sin necesidad de copiar archivos ni de un servidor de medios aparte.

---

## 🩹 7. Problemas conocidos y sus soluciones (guía de supervivencia)

Si vas a levantar este proyecto en una máquina nueva (otra laptop, otra VM), es muy probable que te topes con uno o más de estos errores **la primera vez**. Ya están resueltos en la configuración actual, pero se documentan aquí por si algo se reinstala desde cero o se reconstruye una imagen.

### a) `manifest unknown` al hacer `docker compose up`
La etiqueta de imagen de Asterisk (`andrius/asterisk`) cambia de tags con el tiempo. Si esto vuelve a ocurrir, usa `andrius/asterisk:latest` en vez de tags antiguos como `alpine-base`, y verifica las tags vigentes en Docker Hub antes de fijar una versión específica.

### b) Asterisk se queda en `Restarting` — `Module initialization failed`
Ocurre si el volumen `./asterisk/config:/etc/asterisk` se monta **vacío** o con solo 1-2 archivos personalizados. Asterisk necesita su set completo de ~100 archivos `.conf` de fábrica (`modules.conf`, `logger.conf`, `stasis.conf`, etc.), no solo `pjsip.conf` y `extensions.conf`.

**Si necesitas regenerar la carpeta `asterisk/config/` desde cero:**
```bash
docker run -d --name temp-asterisk andrius/asterisk:latest
sleep 8
docker cp temp-asterisk:/etc/asterisk/. ./asterisk/config/
docker stop temp-asterisk && docker rm temp-asterisk
```
Esto copia la configuración de fábrica completa. Las extensiones SIP personalizadas (`pjsip.conf`, `extensions.conf`) se vuelven a generar después con `sync_asterisk.sh`, así que no se pierde nada.

### c) Softphone da error `404 Not Found` al registrarse (con contraseña correcta)
Síntoma en los logs de Asterisk (`asterisk -rvvv` con `pjsip set logger on`):
```
WARNING: find_registrar_aor: AOR '' not found for endpoint '1001'
```
**Causa:** en PJSIP, el motor de registro (`res_pjsip_registrar`) busca el AOR usando el **mismo nombre que el endpoint**, sin importar lo que diga la directiva `aors=`. Si tu bloque AOR se llama distinto al endpoint (por ejemplo `[1001-aor]` en vez de `[1001]`), el registro SIP falla con 404 aunque la autenticación (401 → digest) sea correcta.

**Solución ya aplicada en `sync_asterisk.sh`:** el bloque `type=aor` usa el mismo nombre de sección que el `type=endpoint` (ej. ambos se llaman `[1001]`). Es válido tener dos bloques con el mismo nombre en `pjsip.conf` siempre que su `type=` sea diferente.

### d) Zoiper/softphone en Windows no encuentra la central
Verifica que la VM esté en red **Bridged** (no NAT puro de VirtualBox) para que el host (Windows) pueda alcanzar la IP de la VM directamente. Confirma la IP de la VM con:
```bash
ip addr show | grep "inet " | grep -v 127.0.0.1
```
Asterisk corre con `network_mode: host`, así que escucha directo en la IP de la VM (ej. `192.168.x.x`), puerto **5060 UDP**.

### e) El panel CDR muestra "sin audio" aunque la llamada sí se grabó
Ver el detalle del punto 6 ("Cómo funciona internamente") sobre el emparejamiento por `dst` en vez de `src`. Si el problema persiste, confirma que el nombre del archivo `.wav` realmente coincide en minuto exacto con el campo `start` del CDR (`ls asterisk/grabaciones/`).

### f) midPoint se reinicia en loop con `relation "m_global_metadata" does not exist`
Síntoma: `docker compose ps` muestra `callcenter-midpoint` reiniciándose cada 5-40 segundos, sin importar cuánto tiempo se espere. El log muestra `PSQLException: relation "m_global_metadata" does not exist`.

**Causa:** a la base de datos PostgreSQL le faltan las extensiones `pgcrypto`, `pg_trgm` e `intarray`. Sin ellas, el script de creación de esquema de midPoint (`postgres.sql`) falla en crear ciertas tablas **sin lanzar un error fatal** — por eso `ninja.sh run-sql --create` reporta "Scripts executed successfully" aunque el esquema haya quedado incompleto.

**Solución:** usar `./init_midpoint.sh`, que ya crea estas extensiones en su primer paso. Si necesitas hacerlo a mano:
```bash
docker exec -it callcenter-db psql -U callcenter_user -d callcenter -c "CREATE EXTENSION IF NOT EXISTS pgcrypto;"
docker exec -it callcenter-db psql -U callcenter_user -d callcenter -c "CREATE EXTENSION IF NOT EXISTS pg_trgm;"
docker exec -it callcenter-db psql -U callcenter_user -d callcenter -c "CREATE EXTENSION IF NOT EXISTS intarray;"
```

### g) Login da `500 Internal Server Error` aunque midPoint esté `healthy` y las credenciales sean correctas
Síntoma: la pantalla de login carga bien, pero al hacer clic en "Sign in" devuelve un 500. El log muestra `PSQLException: relation "ma_audit_event" does not exist`.

**Causa:** cada intento de login (exitoso o fallido) dispara un registro de auditoría. `ninja.sh run-sql --mode repository --create` solo crea las tablas del repositorio principal y de Quartz — **el esquema de auditoría es un módulo separado** que se crea con `--mode audit`, y es fácil olvidarlo porque no se nota hasta el primer login.

**Solución:** usar `./init_midpoint.sh`, que ya incluye este paso. A mano:
```bash
docker exec -it -w /opt/midpoint callcenter-midpoint /opt/midpoint/bin/ninja.sh run-sql \
  --mode audit \
  --jdbc-url jdbc:postgresql://db:5432/callcenter \
  --jdbc-username callcenter_user \
  --jdbc-password callcenter_pass123 \
  --create
docker restart callcenter-midpoint
```

### h) El usuario `administrator` no tiene contraseña / aparece bloqueado (`lockoutStatus: locked`)
Síntoma: error 500 al intentar el login, incluso después de resolver los puntos (f) y (g). Al exportar el usuario con `ninja.sh export -t UserType`, no aparece ningún bloque `<credentials>`, y/o `<lockoutStatus>` dice `locked`.

**Causa:** el objeto semilla `050-user-administrator.xml` no trae contraseña por diseño (midPoint normalmente la genera en un asistente de primer arranque que se omite al importar el XML directamente). Los intentos fallidos de login antes de tener contraseña configurada bloquean la cuenta.

**Solución:** `./init_midpoint.sh` ya asigna una contraseña y desbloquea la cuenta en su último paso. Si necesitas hacerlo a mano, exporta el usuario, edita el XML insertando un bloque `<credentials><password><value><t:clearValue>TU_CLAVE</t:clearValue></value></password></credentials>` como **hermano** de `<activation>` (no anidado dentro), pon `<lockoutStatus>normal</lockoutStatus>`, y reimporta con `ninja.sh import -O -i archivo.xml`.

### i) Ninja da `[ERROR] Was passed main parameter '-U' but no main parameter was defined`
**Causa:** orden incorrecto de argumentos. Las opciones generales de conexión (`-U`, `-u`, `-p`, `-v`) deben ir **antes** del nombre del subcomando (`import`, `run-sql`), y solo las opciones específicas del subcomando (`-i`, `-O`) van después. Ejemplo correcto:
```bash
docker exec -it -w /opt/midpoint callcenter-midpoint /opt/midpoint/bin/ninja.sh \
  -v \
  import -O -i /ruta/al/archivo.xml
```

### j) `ninja.sh run-sql` da `NoSuchFileException: ./doc/config/sql/native/postgres.sql`
**Causa:** el script usa una ruta relativa a su directorio de trabajo. Si el `docker exec` no se ejecuta desde `/opt/midpoint`, no encuentra el archivo.

**Solución:** usar siempre `-w /opt/midpoint` en el `docker exec`:
```bash
docker exec -it -w /opt/midpoint callcenter-midpoint /opt/midpoint/bin/ninja.sh run-sql ...
```

---

## ✅ 8. Checklist rápido para el día de la demostración

**Si es la primera vez en esta máquina:** corre `./init_midpoint.sh` antes de todo lo siguiente (ver sección "Instalación desde cero" arriba). Hazlo con tiempo de sobra — puede tardar hasta 50 minutos.

1. `docker compose up -d` y espera 3-5 min a que midPoint termine de iniciar.
2. `docker compose ps` → confirma que los 4 contenedores estén `Up` (`db`, `midpoint`, `asterisk`, `cdr-panel`), y que `midpoint` diga `healthy` (no `unhealthy` ni reiniciándose).
3. Registra 2-3 softphones (Zoiper/MicroSIP) contra la IP de la VM, puerto 5060 UDP.
4. Si son extensiones nuevas, créalas con `./sync_asterisk.sh <ext> <password>`.
5. Haz una llamada de prueba y contéstala (para generar CDR + grabación).
6. Abre `http://localhost:8088` (o la IP de la VM) y muestra la llamada en la tabla, reproduce el audio con el botón ▶.
7. Si el profesor pregunta por la auditoría ISO 27001, muestra los logs de midPoint en `http://localhost:8080` (usuario `administrator`, contraseña la que se configuró en `init_midpoint.sh`).
