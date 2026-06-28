#!/bin/bash
# ============================================================================
# init_midpoint.sh
#
# Automatiza la inicialización completa de midPoint contra una base de datos
# PostgreSQL nueva. Sin este script, midPoint queda en loop de reinicio o en
# error 500 al hacer login, porque la imagen Docker no auto-genera el
# esquema completo ni los datos semilla (ver sección 7 del README).
#
# Uso:
#   ./init_midpoint.sh
#
# Requiere que los contenedores ya estén corriendo (docker compose up -d)
# y que callcenter-db esté healthy.
# ============================================================================

set -e

DB_CONTAINER="callcenter-db"
MP_CONTAINER="callcenter-midpoint"
DB_USER="callcenter_user"
DB_PASS="callcenter_pass123"
DB_NAME="callcenter"
ADMIN_PASSWORD="${1:-Callcenter2026!}"

echo "============================================================"
echo " Inicializando midPoint (esto puede tardar 15-50 minutos)"
echo "============================================================"

echo ""
echo "[1/5] Creando extensiones de PostgreSQL requeridas por midPoint..."
docker exec -i "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -c "CREATE EXTENSION IF NOT EXISTS pgcrypto;"
docker exec -i "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -c "CREATE EXTENSION IF NOT EXISTS pg_trgm;"
docker exec -i "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -c "CREATE EXTENSION IF NOT EXISTS intarray;"

echo ""
echo "[2/5] Creando esquema de repositorio (tablas principales + Quartz)..."
docker exec -w /opt/midpoint "$MP_CONTAINER" /opt/midpoint/bin/ninja.sh run-sql \
  --mode repository \
  --jdbc-url "jdbc:postgresql://db:5432/$DB_NAME" \
  --jdbc-username "$DB_USER" \
  --jdbc-password "$DB_PASS" \
  --create

echo ""
echo "[3/5] Creando esquema de auditoría (tabla ma_audit_event y relacionadas)..."
docker exec -w /opt/midpoint "$MP_CONTAINER" /opt/midpoint/bin/ninja.sh run-sql \
  --mode audit \
  --jdbc-url "jdbc:postgresql://db:5432/$DB_NAME" \
  --jdbc-username "$DB_USER" \
  --jdbc-password "$DB_PASS" \
  --create

echo ""
echo "[4/5] Importando todos los objetos semilla (system-configuration, roles,"
echo "      usuario administrator, archetypes, etc.) — ~171 archivos, sea paciente."
docker exec -w /opt/midpoint "$MP_CONTAINER" bash -c '
for f in $(find /opt/midpoint/doc/config/initial-objects -name "*.xml" | sort); do
  echo "  -> Importando: $(basename "$f")"
  /opt/midpoint/bin/ninja.sh import -O -i "$f" 2>&1 | grep -E "Processed|ERROR" || true
done
'

echo ""
echo "[5/5] Estableciendo contraseña del administrador y desbloqueando la cuenta..."
docker exec -i "$MP_CONTAINER" sh -c 'cat > /tmp/admin-fixed.xml' << EOF
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
                <t:clearValue>${ADMIN_PASSWORD}</t:clearValue>
            </value>
        </password>
    </credentials>
    <fullName>midPoint Administrator</fullName>
    <givenName>midPoint</givenName>
    <familyName>Administrator</familyName>
</user>
</c:objects>
EOF
docker exec -w /opt/midpoint "$MP_CONTAINER" /opt/midpoint/bin/ninja.sh import -O -i /tmp/admin-fixed.xml

echo ""
echo "============================================================"
echo " Reiniciando midPoint para aplicar todo..."
echo "============================================================"
docker restart "$MP_CONTAINER"

echo ""
echo "Esperando 90s a que midPoint termine de iniciar..."
sleep 90
docker compose ps

echo ""
echo "============================================================"
echo " ¡Listo! Accede a http://localhost:8080 (o http://<IP>:8080)"
echo " Usuario:    administrator"
echo " Contraseña: $ADMIN_PASSWORD"
echo "============================================================"
