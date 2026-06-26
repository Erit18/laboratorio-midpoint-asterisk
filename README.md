# Laboratorio de Integración de Sistemas: Infraestructura Unificada de Comunicaciones y Gestión de Identidad

Este proyecto implementa una arquitectura de microservicios utilizando contenedores para integrar una central telefónica y un gestor de identidades corporativo.

## 🚀 Tecnologías Utilizadas
* **Orquestación:** Docker y Docker Compose.
* **Motor de Comunicación:** Asterisk (PBX).
* **Gestión de Identidad (IAM):** midPoint.
* **Base de Datos:** PostgreSQL.
* **Panel de Evidencias (CDR):** Python + Flask, contenedorizado, con reproductor de grabaciones integrado (interfaz inspirada en el módulo "CDR Reports" de FreePBX/Issabel).

---

## 🛠️ Instrucciones de Despliegue (Para la Demostración)

### 1. Levantar la Infraestructura
Abre tu terminal en la carpeta del proyecto y ejecuta:
```bash
docker compose up -d
```
> **Nota:** midPoint es un sistema robusto en Java. Espera unos **3 a 5 minutos** hasta que termine de inyectar sus tablas en PostgreSQL antes de hacer cualquier prueba.

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

---

## ✅ 8. Checklist rápido para el día de la demostración

1. `docker compose up -d` y espera 3-5 min a que midPoint termine de iniciar.
2. `docker compose ps` → confirma que los 4 contenedores estén `Up` (`db`, `midpoint`, `asterisk`, `cdr-panel`).
3. Registra 2-3 softphones (Zoiper/MicroSIP) contra la IP de la VM, puerto 5060 UDP.
4. Si son extensiones nuevas, créalas con `./sync_asterisk.sh <ext> <password>`.
5. Haz una llamada de prueba y contéstala (para generar CDR + grabación).
6. Abre `http://localhost:8088` (o la IP de la VM) y muestra la llamada en la tabla, reproduce el audio con el botón ▶.
7. Si el profesor pregunta por la auditoría ISO 27001, muestra los logs de midPoint en `http://localhost:8080`.
