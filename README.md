# Laboratorio: Asterisk PBX + midPoint IAM + MariaDB
## Guía rápida para levantar el entorno

---

## ✅ Requisitos previos
- Docker y Docker Compose instalados
- Al menos 4 GB de RAM disponible
- Puertos libres: 5060 (UDP), 8080 (TCP), 3306 (TCP), 10000-10100 (UDP)

---

## 🚀 Clonar y levantar

```bash
git clone https://github.com/Erit18/laboratorio-midpoint-asterisk.git
cd laboratorio-midpoint-asterisk
git checkout erit-branch
docker compose up -d --build
```

Espera 2-3 minutos a que midPoint termine de iniciar.

---

## 🔍 Verificar que todo está corriendo

```bash
docker ps
```

Debes ver 3 contenedores en estado **healthy**:
- `asterisk_pbx`
- `midpoint_server`  
- `mariadb_server`

---

## ⚠️ IMPORTANTE — Primer arranque

La primera vez que se levanta el proyecto, las tablas PJSIP pueden no crearse automáticamente. Verifica así:

```bash
docker exec -it mariadb_server mysql -uroot -proot asterisk -e "SHOW TABLES;"
```

Deben aparecer: `ps_endpoints`, `ps_auths`, `ps_aors`, `sippeers`, `users`.

Si no aparecen, créalas manualmente ejecutando el contenido del archivo `init.sql`:

```bash
docker exec -i mariadb_server mysql -uroot -proot asterisk < init.sql
```

---

## 📞 Verificar extensiones en Asterisk

```bash
docker exec -it asterisk_pbx asterisk -rx "pjsip show endpoints"
```

Deben aparecer las extensiones **1001** y **1002**.

---

## 🌐 Acceder a midPoint

- URL: `http://localhost:8080/midpoint`
- Usuario: `administrator`
- Contraseña: `5ecr3t`

### Usuarios ya creados en midPoint:
| Usuario | Nombre | Rol | Extensión |
|---------|--------|-----|-----------|
| jperez | Juan Pérez | AgenteCallCenter | 1001 |
| mgarcia | María García | AgenteCallCenter | 1002 |

---

## 📱 Configurar Softphones

Instala **Zoiper5** (extensión 1001) y **MicroSIP** (extensión 1002) en Windows.

### Credenciales SIP:
| Campo | Extensión 1001 | Extensión 1002 |
|-------|---------------|---------------|
| Server/Domain | IP de tu máquina Debian | IP de tu máquina Debian |
| Username | 1001 | 1002 |
| Password | clave1001 | 1002 |
| Transport | UDP | UDP |

> Para saber la IP de tu Debian: `ip addr show | grep "inet " | grep -v "127.0.0.1"`

### Para MicroSIP — configuración adicional:
- Dirección Pública: IP de tu Windows (`ipconfig` para verla)
- Puerto de salida: 5060
- RTP ports: 10000 - 10100
- Marcar: Permitir Reescritura de IP

---

## ✅ Verificar llamadas (CDR)

Después de hacer una llamada entre 1001 y 1002:

```bash
docker exec -it asterisk_pbx cat /var/log/asterisk/cdr-csv/Master.csv
```

Deben aparecer registros con estado **ANSWERED**.

---

## 🔒 Scripts de midPoint (ya copiados al contenedor)

Los scripts Groovy están en `/opt/midpoint/var/scripts/` dentro del contenedor midPoint:
- `provision-sip.groovy` — aprovisiona extensiones SIP automáticamente
- `search-users.groovy` — lee extensiones existentes

---

## 🛡️ Análisis de vulnerabilidades Trivy

```bash
chmod +x run-trivy-scan.sh && ./run-trivy-scan.sh
```

Genera reportes en `./trivy-reports/`.

---

## 🔑 Credenciales del sistema

| Servicio | Usuario | Contraseña |
|----------|---------|------------|
| MariaDB root | root | root |
| midPoint web | administrator | 5ecr3t |
| Extensión SIP 1001 | 1001 | clave1001 |
| Extensión SIP 1002 | 1002 | 1002 |

---

## 🛠️ Comandos útiles

```bash
# Ver logs en tiempo real
docker logs -f asterisk_pbx

# Consola de Asterisk
docker exec -it asterisk_pbx asterisk -rvvv

# Ver usuarios en MariaDB
docker exec -it mariadb_server mysql -uroot -proot asterisk -e "SELECT * FROM users;"

# Ver audit log
docker exec -it mariadb_server mysql -uroot -proot asterisk -e "SELECT * FROM audit_log;"

# Reiniciar todo
docker compose down && docker compose up -d
```
