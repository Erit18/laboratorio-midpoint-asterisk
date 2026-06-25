# Solución al Problema de Audio RTP Unidireccional
## Laboratorio de Integración de Sistemas — Asterisk + Docker + NAT

---

## Diagnóstico del problema

El audio viaja solo en una dirección (PC → celular) porque los paquetes RTP
del celular llegan a la VM pero el kernel Linux no los reenvía al contenedor
Docker de Asterisk.

**Ruta que debería seguir el paquete RTP del celular:**
```
Celular → (WiFi/LTE) → IP pública de la VM → iptables NAT → Contenedor Asterisk
```

El problema ocurre en el paso de `iptables NAT → Contenedor`.

---

## Solución A — iptables DNAT (recomendada, permanente)

### Paso 1: Obtener la IP interna del contenedor Asterisk
```bash
docker inspect asterisk_pbx | grep '"IPAddress"'
# Ejemplo de resultado: "IPAddress": "172.18.0.4"
export ASTERISK_IP=$(docker inspect -f '{{range.NetworkSettings.Networks}}{{.IPAddress}}{{end}}' asterisk_pbx)
echo "IP del contenedor: $ASTERISK_IP"
```

### Paso 2: Ver la interfaz de red de la VM
```bash
ip addr show | grep "inet " | grep -v "127.0.0.1"
# La interfaz principal suele ser enp0s3, eth0 o ens33
# Anotar la IP, ej: 10.113.144.101
```

### Paso 3: Agregar reglas iptables para reenviar RTP
```bash
# Reemplazar enp0s3 por tu interfaz real y 172.18.0.4 por la IP del contenedor

# Regla para puerto SIP (señalización)
sudo iptables -t nat -A PREROUTING -i enp0s3 -p udp --dport 5060 \
  -j DNAT --to-destination $ASTERISK_IP:5060

# Regla para rango RTP (audio)
sudo iptables -t nat -A PREROUTING -i enp0s3 -p udp --dport 10000:10100 \
  -j DNAT --to-destination $ASTERISK_IP

# Habilitar IP forwarding
sudo sysctl -w net.ipv4.ip_forward=1

# Verificar que las reglas quedaron activas
sudo iptables -t nat -L PREROUTING -n -v
```

### Paso 4: Verificar con tcpdump
```bash
# En una terminal: escuchar paquetes UDP llegando a la VM
sudo tcpdump -i enp0s3 -n udp port 10000

# En otra terminal: ver logs de Asterisk en tiempo real
docker exec -it asterisk_pbx asterisk -rvvv
# Dentro de la CLI: rtp set debug on
```

---

## Solución B — Dos softphones en la misma PC (más fácil para la presentación)

Esta opción elimina completamente el problema de red porque el audio
viaja por localhost.

### Software recomendado
- **Extensión 1001** → Zoiper5 (ya lo tenés instalado)  
- **Extensión 1002** → MicroSIP (gratuito, muy liviano)
  - Descarga: https://www.microsip.org/downloads

### Configuración MicroSIP para extensión 1002
| Campo    | Valor                          |
|----------|-------------------------------|
| Account  | 1002                          |
| Domain   | IP de la VM (ej. 192.168.1.X) |
| Username | 1002                          |
| Password | clave1002                     |
| Port     | 5060                          |

### Verificar la llamada
1. Abrir Zoiper (1001) y MicroSIP (1002) en la misma PC
2. Desde Zoiper marcar `1002`
3. Contestar en MicroSIP
4. Verificar audio bidireccional
5. Revisar el CDR:
```bash
docker exec -it asterisk_pbx cat /var/log/asterisk/cdr-csv/Master.csv
```

---

## Configuración recomendada en ps_endpoints (ya incluida en init.sql)

Para mejor compatibilidad NAT, los endpoints deben tener:
```sql
force_rport     = yes   -- Usar el puerto de origen del paquete SIP
rewrite_contact = yes   -- Reescribir el Contact header con IP:puerto reales
rtp_symmetric   = yes   -- Enviar RTP al mismo IP:puerto del que llega
direct_media    = no    -- Asterisk siempre en el medio (no P2P directo)
```

Verificar que la tabla tiene estos valores:
```sql
-- Entrar a MariaDB:
docker exec -it mariadb_server mysql -uroot -proot asterisk

-- Verificar configuración:
SELECT id, direct_media, force_rport, rewrite_contact, rtp_symmetric
FROM ps_endpoints;
```

---

## Comandos de diagnóstico útiles en la CLI de Asterisk

```bash
docker exec -it asterisk_pbx asterisk -rvvv
```

Dentro de la consola:
```
pjsip show endpoints          -- Ver estado de extensiones
pjsip show contacts           -- Ver IPs registradas por cada extensión
rtp set debug on              -- Activar log de paquetes RTP
core set verbose 5            -- Nivel de verbosidad máximo
```
