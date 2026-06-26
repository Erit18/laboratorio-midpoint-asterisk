#!/bin/bash
# Script de Integración Manual (Simulación de aprovisionamiento midPoint -> Asterisk)

EXTENSION=$1
PASSWORD=$2

if [ -z "$EXTENSION" ] || [ -z "$PASSWORD" ]; then
  echo "Error. Uso correcto: ./sync_asterisk.sh <extension> <password>"
  exit 1
fi

echo "Sincronizando agente $EXTENSION desde el gestor de identidades hacia Asterisk..."

# 1. Inyectando la configuración SIP (Autenticación)
cat <<EOF >> ./asterisk/config/pjsip.conf

; ===== Extensión $EXTENSION =====
[$EXTENSION]
type=endpoint
context=internal
disallow=all
allow=ulaw
allow=alaw
auth=$EXTENSION-auth
aors=$EXTENSION

[$EXTENSION-auth]
type=auth
auth_type=userpass
username=$EXTENSION
password=$PASSWORD

[$EXTENSION]
type=aor
max_contacts=1
EOF

# 2. Inyectando el Dialplan (Enrutamiento con Grabación)
cat <<EOF >> ./asterisk/config/extensions.conf

exten => $EXTENSION,1,MixMonitor($EXTENSION-\${STRFTIME(\${EPOCH},,%Y%m%d-%H%M%S)}.wav)
 same => n,Dial(PJSIP/$EXTENSION,20)
 same => n,Hangup()
EOF

echo "Recargando el motor SIP y el Dialplan de Asterisk en caliente..."
docker exec callcenter-asterisk asterisk -rx "module reload res_pjsip.so" > /dev/null
docker exec callcenter-asterisk asterisk -rx "dialplan reload" > /dev/null

echo "¡Integración completada! El anexo $EXTENSION está totalmente configurado y enrutable."
