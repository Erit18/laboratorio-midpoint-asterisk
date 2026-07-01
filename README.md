# Laboratorio de Integración de Sistemas: Infraestructura Unificada de Comunicaciones y Gestión de Identidad

Este proyecto implementa una arquitectura de microservicios utilizando contenedores para integrar una central telefónica y un gestor de identidades corporativo.

## 🚀 Tecnologías Utilizadas
* **Orquestación:** Docker y Docker Compose.
* **Motor de Comunicación:** Asterisk (PBX).
* **Gestión de Identidad (IAM):** midPoint.
* **Base de Datos:** PostgreSQL.
* **Panel de Evidencias (CDR):** Python + Flask, contenedorizado, con reproductor de grabaciones integrado (interfaz inspirada en el módulo "CDR Reports" de FreePBX/Issabel).
* **Pruebas Unitarias:** pytest 8.3.5, con 20 casos de prueba sobre el módulo de aprovisionamiento SIP.

---

## 🔄 ¿Ya intentaste instalar este proyecto antes y midPoint no arrancaba?

Si ya clonaste este repositorio en algún momento y `callcenter-midpoint` se quedaba reiniciándose en loop (o nunca llegaba a `healthy`), es porque las versiones anteriores de esta guía no incluían los pasos de inicialización manual que sí están documentados a partir de ahora en la sección "⚡ Instalación desde cero". El problema no era tu instalación — la documentación anterior estaba incompleta.

**Antes de reinstalar, borra completamente el intento anterior** para no dejar una base de datos a medio inicializar que pueda interferir:

```bash
cd ~/laboratorio-midpoint-asterisk-main      # o el nombre que le hayas puesto a la carpeta
docker compose down -v
cd ~
rm -rf laboratorio-midpoint-asterisk-main
```

El `-v` borra también los volúmenes de datos (la base de datos vieja e incompleta), y el `rm -rf` borra la carpeta del proyecto entera. Después de esto, clona de nuevo el repo y sigue la sección de abajo desde el principio, sin saltarte ningún paso:

```bash
git clone https://github.com/Erit18/laboratorio-midpoint-asterisk.git laboratorio-midpoint-asterisk-main
cd laboratorio-midpoint-asterisk-main
chmod +x sync_asterisk.sh
```

**Si ya ejecutaste una versión anterior de este proyecto**, es posible que los archivos `pjsip.conf` y `extensions.conf` tengan extensiones duplicadas de instalaciones previas. Antes de reinstalar, asegúrate de limpiarlos junto con los volúmenes:

```bash
cd ~/laboratorio-midpoint-asterisk-main
docker compose down -v
cd ~
rm -rf laboratorio-midpoint-asterisk-main
```

Al clonar de nuevo el repositorio, los archivos vendrán limpios y `sync_asterisk.sh` agregará las extensiones correctamente sin duplicados.

---

## ⚡ Instalación desde cero (clonando el repo en una máquina nueva)

**Lee esto primero si es la primera vez que levantas el proyecto en esta máquina.** La imagen de Docker `evolveum/midpoint:latest` **no auto-genera su esquema de base de datos ni sus datos iniciales** (usuario `administrator`, roles, configuración del sistema). Si solo haces `docker compose up -d` sin más, midPoint se quedará en loop de reinicio o, si parece levantar, dará `500 Internal Server Error` al intentar iniciar sesión.

**Importante #1:** estos comandos deben ejecutarse **uno por uno, copiando y pegando tal cual**, incluyendo la flag `-it`. Probamos automatizar todo esto en un script de una sola pieza y, en algunas máquinas, los pasos de `ninja.sh` se quedaban colgados indefinidamente al ejecutarse sin terminal interactiva asignada. Ejecutados manualmente con `-it`, estos mismos comandos siempre funcionan en segundos. No los metas en un script propio salvo que también uses `-it` en cada `docker exec`.

**Importante #2:** los mensajes en pantalla de `ninja.sh` a veces no muestran su línea final ("Scripts executed successfully") aunque el comando sí haya funcionado — es un corte de buffer de la terminal, no un fallo real. **Verifica siempre contra la base de datos real** con el comando de verificación que se incluye después de cada paso, en vez de confiar solo en lo que se imprime en pantalla.

**Importante #3 — Recursos de la máquina:** el Paso 4 (importación de objetos semilla) deja la VM bajo carga sostenida por mucho tiempo. Si la VM tiene poca RAM asignada (menos de 4 GB) o pocos núcleos de CPU, es posible que el sistema entre en un estado de sobrecarga severa (`watchdog: soft lockup`, pantalla congelada) hacia el final del proceso. Si esto pasa: **reinicia la VM** (no se pierde nada, los datos viven en volúmenes de Docker en disco) y verifica con `docker compose ps` — es probable que el trabajo ya se haya completado y solo haga falta el Paso 5. Antes de lanzar el Paso 4, cierra el navegador y cualquier otra aplicación pesada para darle más margen a la VM.

```bash
docker compose up -d
```
Espera a que el output muestre `Container callcenter-db Healthy` (unos 8-15 segundos).

**Paso 1 — Extensiones de PostgreSQL** (instantáneo):
```bash
docker exec -it callcenter-db psql -U callcenter_user -d callcenter -c "CREATE EXTENSION IF NOT EXISTS pgcrypto;"
docker exec -it callcenter-db psql -U callcenter_user -d callcenter -c "CREATE EXTENSION IF NOT EXISTS pg_trgm;"
docker exec -it callcenter-db psql -U callcenter_user -d callcenter -c "CREATE EXTENSION IF NOT EXISTS intarray;"
```

**Paso 2 — Esquema de repositorio:**
```bash
docker exec -it -w /opt/midpoint callcenter-midpoint /opt/midpoint/bin/ninja.sh run-sql \
  --mode repository \
  --jdbc-url jdbc:postgresql://db:5432/callcenter \
  --jdbc-username callcenter_user \
  --jdbc-password callcenter_pass123 \
  --create
```

**Verifica que sí se creó** (debe devolver un número alto, ~94 o más; si dice "Did not find any relations" repite el Paso 2):
```bash
docker exec -it callcenter-db psql -U callcenter_user -d callcenter --pset pager=off -c "\dt" | wc -l
```
*(Si en algún momento `psql` parece "colgarse" mostrando `(END)` al final, no está colgado — es el paginador de texto esperando que presiones la tecla `q` para continuar.)*

**Paso 3 — Esquema de auditoría** (este paso es fácil de olvidar y su ausencia causa un 500 específicamente al hacer login, no al arrancar):
```bash
docker exec -it -w /opt/midpoint callcenter-midpoint /opt/midpoint/bin/ninja.sh run-sql \
  --mode audit \
  --jdbc-url jdbc:postgresql://db:5432/callcenter \
  --jdbc-username callcenter_user \
  --jdbc-password callcenter_pass123 \
  --create
```

**Verifica que sí se creó** (debe mostrar `ma_audit_event` y tablas relacionadas):
```bash
docker exec -it callcenter-db psql -U callcenter_user -d callcenter --pset pager=off -c "\dt" | grep audit
```

**Paso 4 — Importar los objetos semilla (roles, configuración, usuario admin, etc.)**

⚠️ **Este paso tarda entre 50 minutos y 2 horas**, dependiendo de qué tan rápida sea la máquina (en una prueba real tardó casi 2 horas). Es lento por diseño de la herramienta (son ~171 archivos y cada uno reinicia el contexto interno de la aplicación) — **no está colgado, déjalo correr sin interrumpirlo.** No cierres la terminal. Ideal: lánzalo y ve a hacer otra cosa durante ese tiempo, idealmente sin usar la laptop para tareas pesadas en paralelo (ver "Importante #3" arriba).

```bash
docker exec -it -w /opt/midpoint callcenter-midpoint bash -c '
for f in $(find /opt/midpoint/doc/config/initial-objects -name "*.xml" | sort); do
  echo "=== Importando: $(basename "$f") ==="
  /opt/midpoint/bin/ninja.sh import -O -i "$f" 2>&1 | grep -E "Processed|ERROR"
done
'
```
Sabrás que terminó cuando el prompt (`$`) vuelva a aparecer solo, sin más líneas de "Importando...".

Si quieres confirmar que avanza sin interrumpir el bucle, abre una **segunda terminal** y de vez en cuando corre (el número debería ir creciendo con el tiempo):
```bash
docker exec -it callcenter-db psql -U callcenter_user -d callcenter --pset pager=off -c "SELECT COUNT(*) FROM m_object;"
```

**Paso 5 — Asignar contraseña al usuario `administrator`** (sin esto, el usuario existe pero no tiene clave y no se puede iniciar sesión):
```bash
docker exec -i callcenter-midpoint sh -c 'cat > /tmp/admin-fixed.xml' << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<c:objects xmlns="http://midpoint.evolveum.com/xml/ns/public/common/common-3"
	xmlns:c="http://midpoint.evolveum.com/xml/ns/public/common/common-3"
	xmlns:org="http://midpoint.evolveum.com/xml/ns/public/common/org-3">
<user xmlns="http://midpoint.evolveum.com/xml/ns/public/common/common-3" xmlns:c="http://midpoint.evolveum.com/xml/ns/public/common/common-3" xmlns:org="http://midpoint.evolveum.com/xml/ns/public/common/org-3" xmlns:t="http://prism.evolveum.com/xml/ns/public/types-3" oid="00000000-0000-0000-0000-000000000002" version="19">
    <name>administrator</name>
    <indestructible>true</indestructible>
    <assignment id="1">
        <identifier>superuserRole</identifier>
        <targetRef oid="00000000-0000-0000-0000-000000000004" relation="org:default" type="c:RoleType"/>
    </assignment>
    <assignment id="2">
        <identifier>archetype</identifier>
        <targetRef oid="00000000-0000-0000-0000-000000000300" relation="org:default" type="c:ArchetypeType"/>
    </assignment>
    <activation>
        <administrativeStatus>enabled</administrativeStatus>
        <effectiveStatus>enabled</effectiveStatus>
        <lockoutStatus>normal</lockoutStatus>
    </activation>
    <credentials>
        <password>
            <value>
                <t:clearValue>Callcenter2026!</t:clearValue>
            </value>
        </password>
    </credentials>
    <fullName>midPoint Administrator</fullName>
    <givenName>midPoint</givenName>
    <familyName>Administrator</familyName>
</user>
</c:objects>
EOF
docker exec -it -w /opt/midpoint callcenter-midpoint /opt/midpoint/bin/ninja.sh import -O -i /tmp/admin-fixed.xml
```

**Listo.** Verifica con `docker compose ps` que `callcenter-midpoint` esté `healthy`, y entra a `http://localhost:8080` con usuario `administrator` y contraseña `Callcenter2026!` (puedes cambiar `Callcenter2026!` por otra clave en el XML del Paso 5 antes de ejecutarlo, si prefieres una distinta).

**Paso 6 — Importar el rol "AgenteCallCenter" en midPoint**

Este paso crea el rol que activa el aprovisionamiento automático. Cuando se asigna este rol a un usuario, midPoint llama automáticamente al endpoint `/api/provision` del panel CDR, que configura la extensión SIP en Asterisk sin intervención manual.

```bash
docker cp rol-agente-callcenter.xml callcenter-midpoint:/tmp/rol-agente-callcenter.xml
docker exec -it -w /opt/midpoint callcenter-midpoint \
  /opt/midpoint/bin/ninja.sh import -O -i /tmp/rol-agente-callcenter.xml
```

El output debe terminar con `Processed: 1, error: 0`. Verifica que el rol aparece en midPoint entrando a `http://localhost:8080` → **Roles** → **All roles** — debe aparecer "AgenteCallCenter" en la lista.

**Paso 7 — Importar la configuración del sistema (notifier de aprovisionamiento)**

Este paso configura el notifier Groovy en midPoint que dispara automáticamente el aprovisionamiento SIP cada vez que un usuario con `telephoneNumber` recibe el rol "AgenteCallCenter". **Sin este paso, el aprovisionamiento no será automático.**

```bash
docker cp midpoint-sysconfg.xml callcenter-midpoint:/tmp/midpoint-sysconfg.xml
docker exec -it -w /opt/midpoint callcenter-midpoint \
  /opt/midpoint/bin/ninja.sh import -O -i /tmp/midpoint-sysconfg.xml
```

El output debe terminar con `Processed: 1, error: 0`.

**Listo.** A partir de este punto, cada vez que crees un usuario en midPoint con `Telephone number` y le asignes el rol "AgenteCallCenter", la extensión SIP se aprovisionará automáticamente en Asterisk.

> **⚠️ Nota sobre `sync_asterisk.sh`:** este script de aprovisionamiento manual ya no es necesario para el flujo normal. Solo úsalo si necesitas agregar una extensión sin pasar por midPoint (por ejemplo, para pruebas rápidas). La contraseña SIP que genera el notifier automático sigue el patrón `SIP` + número de extensión + `2026` (ej. extensión `1001` → contraseña `SIP10012026`).

**Si necesitas reiniciar todo desde cero** (por ejemplo, en otra máquina o si algo quedó a medias), borra los volúmenes primero y repite los pasos 1 a 6:
```bash
docker compose down -v
docker compose up -d
```

---

## 🛠️ Instrucciones de Despliegue (Para la Demostración)

> Esta sección asume que ya completaste los 6 pasos de "Instalación desde cero" al menos una vez en esta máquina, o que el volumen de base de datos ya tiene los datos semilla (por ejemplo, si nunca borraste los volúmenes desde la primera instalación).

### 1. Levantar la Infraestructura
Abre tu terminal en la carpeta del proyecto y ejecuta:
```bash
docker compose up -d
```
> **Nota:** midPoint es un sistema robusto en Java. Espera unos **3 a 5 minutos** hasta que termine de iniciar antes de hacer cualquier prueba.

### 2. Verificar que los 4 contenedores estén activos
```bash
docker compose ps
```
Confirma que `db`, `midpoint`, `asterisk` y `cdr-panel` estén `Up` y que `midpoint` diga `(healthy)`.

### 3. Flujo de Aprovisionamiento midPoint → Asterisk (Demo Principal)

Este es el flujo central del proyecto — demuestra que midPoint actúa como fuente de la verdad para la gestión de identidades y que los agentes se aprovisionan automáticamente en Asterisk.

**Paso A — Crear un nuevo agente en midPoint:**
1. Abre `http://localhost:8080` y entra con `administrator` / `Callcenter2026!`
2. Ve a **Users** → **New user**
3. Selecciona tipo **Person**
4. Rellena los campos:
   - **Name:** `agente08` (username único)
   - **Given name:** `Agente`
   - **Family name:** `Ocho`
   - **Telephone number:** `1008` ← este es el número de extensión SIP
5. Ve a la pestaña **Assignments** → sub-pestaña **Role**
6. Haz clic en el ícono de asignar → busca y selecciona **AgenteCallCenter**
7. Haz clic en **Save**

El usuario queda registrado en midPoint con el rol "AgenteCallCenter" y su número de extensión `1008`.

**Paso B — Aprovisionar la extensión en Asterisk (script de integración):**

En la terminal, ejecuta el script de integración indicando la extensión y la contraseña:
```bash
curl -s -X POST http://localhost:8088/api/provision \
  -H "Content-Type: application/json" \
  -d '{"extension": "1008", "password": "clave1008"}' | python3 -m json.tool
```

El output debe mostrar `"status": "ok"` y `"Extension 1008 aprovisionada y Asterisk recargado correctamente"`.

**Paso C — Verificar que la extensión aparece en Asterisk:**
```bash
docker exec callcenter-asterisk asterisk -rx "pjsip show endpoints" | grep 1008
```
Debe mostrar `Endpoint: 1008  Unavailable` — la extensión está configurada y lista para recibir registro SIP.

**Paso D — Verificar en PostgreSQL que el usuario está en la BD:**
```bash
docker exec -it callcenter-db psql -U callcenter_user -d callcenter --pset pager=off \
  -c "SELECT nameorig, fullname, lifecyclestate FROM m_user WHERE nameorig = 'agente08';"
```
Confirma que el usuario existe en la base de datos con su estado activo.

### 4. Aprovisionamiento manual de emergencia (opcional)

El flujo normal es 100% automático vía midPoint. Solo usa el script manual si necesitas agregar una extensión sin pasar por midPoint (por ejemplo, para pruebas rápidas sin usuario en midPoint):
```bash
./sync_asterisk.sh 1001 clave1001
```
> **Nota:** las extensiones creadas con `sync_asterisk.sh` usan la contraseña que tú indiques. Las creadas vía midPoint usan automáticamente `SIP` + número + `2026`.

### 5. Prueba de Concepto (Llamada y Evidencias)
1. Abre tu Softphone (ej. Zoiper o MicroSIP).
2. Configura tu cuenta apuntando a la IP local de tu máquina usando el puerto **5060 (UDP)**.
3. Realiza una llamada entre dos extensiones (ej. del 1001 al 1002). **Contesta la llamada** y luego cuelga.
4. Para mostrar verbosidad en vivo durante la llamada, abre una segunda terminal y ejecuta:
```bash
docker exec callcenter-asterisk asterisk -rx "core set verbose 5" && docker logs -f callcenter-asterisk
```

### 6. Extracción de Evidencias (CDRs y Grabaciones)
Al colgar la llamada, el contenedor de Asterisk exportará automáticamente los datos a tu sistema anfitrión:
* **Grabación de la llamada:** Revisa la carpeta local `asterisk/grabaciones/` para escuchar el archivo `.wav`.
* **CDRs (Registros de Detalle de Llamadas):** Revisa la carpeta local `asterisk/registros_cdr/` y abre el archivo `Master.csv`.

Estas evidencias también se visualizan de forma integrada en el **Panel Web de CDR** — no es necesario abrir el CSV ni buscar los .wav a mano.

### 7. Auditoría de Seguridad (ISO 27001)
Puedes acceder al panel web de midPoint ingresando a `http://localhost:8080`. El sistema cuenta con logs de auditoría en la sección de reportes para garantizar la trazabilidad de accesos y cumplir con el control A.8.16 de ISO 27001.

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

### d) Zoiper/softphone no encuentra la central — o "funcionaba en una red y en otra no"
**La IP que pones en Zoiper (Dominio/Host) NO es un valor fijo del proyecto — es la IP local de la laptop donde corre Asterisk en ESE momento, y cambia cada vez que esa laptop se conecta a una red WiFi distinta.** Si configuraste Zoiper en casa y luego llevas la laptop a la universidad (u otra red), la IP vieja ya no sirve.

**Antes de cada sesión de pruebas, en una red nueva, vuelve a verificar la IP:**
```bash
ip addr show | grep "inet " | grep -v 127.0.0.1
```
Usa el resultado (típicamente algo como `192.168.x.x`) como Dominio/Host en cada softphone, actualizando la configuración si cambió respecto a la última vez.

También verifica que la VM esté en red **Bridged** (no NAT puro de VirtualBox) para que otros dispositivos de la misma red puedan alcanzarla. Asterisk corre con `network_mode: host`, así que escucha directo en la IP de la VM, puerto **5060 UDP**.

**⚠️ Redes institucionales (universidad, oficina, WiFi de eventos):** muchas de estas redes tienen activado el **"aislamiento de clientes"** (client/AP isolation), una medida de seguridad que impide que dos dispositivos conectados al mismo WiFi se comuniquen directamente entre sí — aunque ambos tengan IP válida y estén en la misma red. Si esto está activo, el celular (o cualquier otro dispositivo) **nunca podrá alcanzar la laptop con Asterisk**, sin importar que la configuración de Zoiper sea correcta. Esto no es un error del proyecto ni de la configuración — es una política de red fuera de nuestro control.

**Recomendación:** prueba la conectividad entre dispositivos en la red de la universidad **con anticipación**, no justo antes de la demo. Si detectas que el aislamiento de clientes está activo y no se puede desactivar:
- Usa **dos softphones en la misma laptop** (instala un segundo cliente SIP, o usa la misma extensión registrada dos veces si el `max_contacts` lo permite), o
- Crea un **hotspot/punto de acceso propio** desde el celular o la laptop y conecta ambos dispositivos a esa red en vez de a la de la universidad.

### e) El panel CDR muestra "sin audio" aunque la llamada sí se grabó
Ver el detalle del punto 6 ("Cómo funciona internamente") sobre el emparejamiento por `dst` en vez de `src`. Si el problema persiste, confirma que el nombre del archivo `.wav` realmente coincide en minuto exacto con el campo `start` del CDR (`ls asterisk/grabaciones/`).

### f) midPoint se reinicia en loop con `relation "m_global_metadata" does not exist`
Síntoma: `docker compose ps` muestra `callcenter-midpoint` reiniciándose cada 5-40 segundos, sin importar cuánto tiempo se espere. El log muestra `PSQLException: relation "m_global_metadata" does not exist`.

**Causa:** a la base de datos PostgreSQL le faltan las extensiones `pgcrypto`, `pg_trgm` e `intarray`. Sin ellas, el script de creación de esquema de midPoint (`postgres.sql`) falla en crear ciertas tablas **sin lanzar un error fatal** — por eso `ninja.sh run-sql --create` reporta "Scripts executed successfully" aunque el esquema haya quedado incompleto.

**Solución:** seguir el Paso 1 de "Instalación desde cero" arriba (crear las extensiones). Si necesitas hacerlo a mano:
```bash
docker exec -it callcenter-db psql -U callcenter_user -d callcenter -c "CREATE EXTENSION IF NOT EXISTS pgcrypto;"
docker exec -it callcenter-db psql -U callcenter_user -d callcenter -c "CREATE EXTENSION IF NOT EXISTS pg_trgm;"
docker exec -it callcenter-db psql -U callcenter_user -d callcenter -c "CREATE EXTENSION IF NOT EXISTS intarray;"
```

### g) Login da `500 Internal Server Error` aunque midPoint esté `healthy` y las credenciales sean correctas
Síntoma: la pantalla de login carga bien, pero al hacer clic en "Sign in" devuelve un 500. El log muestra `PSQLException: relation "ma_audit_event" does not exist`.

**Causa:** cada intento de login (exitoso o fallido) dispara un registro de auditoría. `ninja.sh run-sql --mode repository --create` solo crea las tablas del repositorio principal y de Quartz — **el esquema de auditoría es un módulo separado** que se crea con `--mode audit`, y es fácil olvidarlo porque no se nota hasta el primer login.

**Solución:** seguir el Paso 3 de "Instalación desde cero" arriba (crear el esquema de auditoría). A mano:
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

**Solución:** seguir el Paso 5 de "Instalación desde cero" arriba, que ya asigna una contraseña y desbloquea la cuenta. Si necesitas hacerlo a mano con otro usuario, exporta el usuario, edita el XML insertando un bloque `<credentials><password><value><t:clearValue>TU_CLAVE</t:clearValue></value></password></credentials>` como **hermano** de `<activation>` (no anidado dentro), pon `<lockoutStatus>normal</lockoutStatus>`, y reimporta con `ninja.sh import -O -i archivo.xml`.

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

### k) La VM se congela o aparece `watchdog: BUG: soft lockup` durante el Paso 4
Síntoma: tras dejar correr la importación de objetos semilla por un tiempo largo, la pantalla de la VM se queda fija y/o muestra mensajes en amarillo tipo `watchdog: soft lockup - CPU#0 stuck for Xs`.

**Causa:** la VM se quedó sin recursos suficientes (CPU y/o RAM) bajo la carga sostenida de Docker + Java + Postgres corriendo por mucho tiempo. No es un error del proyecto ni de los comandos — es el sistema operativo de la VM literalmente sin capacidad de seguir respondiendo.

**Solución:** reinicia la VM. Los datos no se pierden porque viven en volúmenes de Docker en disco, no en memoria — al reiniciar, `docker compose ps` puede incluso mostrar que el trabajo ya había terminado y los contenedores vuelven a `healthy` solos. Si vuelve a pasar seguido, asigna más RAM/CPU a la VM desde la configuración de VirtualBox, y cierra el navegador y otras aplicaciones pesadas antes de lanzar el Paso 4.

### l) Los mensajes de `ninja.sh` en pantalla no muestran la línea final aunque el comando funcionó
Síntoma: el output de `run-sql` se corta justo después de "Executing script ..." sin mostrar "Scripts executed successfully", y parece que falló.

**Causa:** corte de buffer/timing de la terminal al mostrar el output de un proceso Java vía `docker exec`. No siempre refleja si el comando realmente terminó bien o mal.

**Solución:** nunca asumas éxito o fallo solo por el mensaje en pantalla — verifica siempre contra la base de datos real con `\dt` (ver los pasos de verificación en "Instalación desde cero" arriba).

---

## ✅ 8. Checklist rápido para el día de la demostración

**Si es la primera vez en esta máquina:** completa los 6 pasos de "Instalación desde cero" arriba antes de todo lo siguiente. Hazlo con tiempo de sobra — el Paso 4 puede tardar entre 50 minutos y 2 horas, y no se puede interrumpir. Este flujo fue probado de punta a punta (incluyendo llamada real y panel CDR) en una máquina nueva.

**⚠️ Si vas a presentar en una red distinta a la que usaste para probar (ej. WiFi de la universidad en vez de tu casa):** verifica la conectividad entre dispositivos **con anticipación**, no el mismo día. La IP cambia con la red (ver punto "d" de Problemas Conocidos) y algunas redes institucionales bloquean la comunicación directa entre dispositivos conectados al mismo WiFi.

1. `docker compose up -d` y espera 3-5 min a que midPoint termine de iniciar.
2. `docker compose ps` → confirma que los 4 contenedores estén `Up` (`db`, `midpoint`, `asterisk`, `cdr-panel`), y que `midpoint` diga `(healthy)`.
3. **Demo midPoint → Asterisk (flujo automático):**
   - Abre `http://localhost:8080` → entra con `administrator` / `Callcenter2026!`
   - Ve a **Users → New user → Person**
   - Llena los campos:
     - **Name:** identificador único sin espacios (ej. `jperez`)
     - **Given name:** nombre real (ej. `Juan`)
     - **Family name:** apellido real (ej. `Pérez`)
     - **Telephone number:** número de extensión SIP (ej. `1001`) ← **campo crítico**
   - Ve a **Assignments → Role** → agrega **AgenteCallCenter** → **Save**
   - midPoint ejecuta automáticamente el notifier Groovy → la extensión SIP queda configurada en Asterisk
   - La contraseña SIP generada automáticamente es: `SIP` + número + `2026` (ej. extensión `1001` → `SIP10012026`)
   - Verifica en terminal: `docker exec callcenter-asterisk asterisk -rx "pjsip show endpoints" | grep 1001`
4. Registra los softphones (Zoiper/MicroSIP) con los datos generados:
   - **Servidor:** IP de la VM (ver con `ip addr show | grep "inet " | grep -v 127`)
   - **Usuario:** el Telephone number (ej. `1001`)
   - **Contraseña:** `SIP10012026`
   - **Puerto:** 5060 UDP
5. Haz una llamada de prueba y contéstala (para generar CDR + grabación).
6. Abre `http://localhost:8088` → muestra las métricas, las extensiones en tiempo real y reproduce la grabación con ▶.
7. Muestra auditoría ISO 27001 en `http://localhost:8080` → reportes de acceso.
8. Para mostrar verbosidad técnica en vivo durante una llamada:
```bash
docker logs -f callcenter-midpoint 2>&1 | grep -i "SIP provision\|HTTP 200"
```

## 🧪 9. Pruebas Unitarias (Quality Assurance)

El proyecto incluye una suite de pruebas unitarias escrita con `pytest` que valida la lógica de negocio del módulo de aprovisionamiento SIP (`/api/provision`). Las pruebas se encuentran en `tests/test_provision.py`.

### Ejecutar las pruebas

```bash
pip3 install flask pytest --break-system-packages
python3 -m pytest tests/test_provision.py -v
```

### Cobertura: 20 pruebas en 4 categorías

| Categoría | Pruebas | Qué valida |
|---|---|---|
| Parámetros requeridos | 5 | Rechaza extensión/password vacíos o ausentes |
| Validación de extensión | 6 | Solo acepta 3-6 dígitos numéricos |
| Validación de contraseña | 3 | Mínimo 4 caracteres alfanuméricos |
| Lógica de negocio | 4 | Aprovisionamiento exitoso, duplicados (409), método HTTP |
| Endpoint de salud | 2 | Respuesta y campos de `/api/health` |

### Resultado esperado

20 passed

Estas pruebas garantizan que el sistema rechaza correctamente entradas inválidas antes de intentar modificar la configuración de Asterisk, cumpliendo con el atributo de **Fiabilidad** de la norma ISO/IEC 25010.
