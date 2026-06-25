/**
 * provision-sip.groovy
 * Script Groovy de midPoint — Aprovisiona cuentas SIP en Asterisk vía MariaDB
 *
 * Ubicación en el contenedor midPoint:
 *   /opt/midpoint/var/scripts/provision-sip.groovy
 *
 * Flujo:
 *   1. midPoint detecta un usuario con rol "AgenteCallCenter"
 *   2. Llama a este script vía el conector ScriptedSQL
 *   3. El script inserta (o actualiza) filas en:
 *        - ps_endpoints  → define el endpoint SIP
 *        - ps_auths      → define las credenciales
 *        - ps_aors       → define el Address of Record (dónde registrarse)
 *
 * Variables disponibles inyectadas por el conector:
 *   - sql          → objeto groovy.sql.Sql ya conectado a MariaDB
 *   - operation    → 'CREATE' | 'UPDATE' | 'DELETE'
 *   - attributes   → mapa con los atributos de la cuenta a provisionar
 *   - log          → logger de midPoint
 */

import groovy.sql.Sql

// ============================================================
// Extraer atributos del objeto cuenta recibido por midPoint
// ============================================================
def extension = attributes.get('__NAME__')?.get(0) as String  // ej. "1001"
def sipPassword = attributes.get('password')?.get(0) as String ?: 'changeme'
def context    = attributes.get('context')?.get(0)  as String ?: 'default'

if (!extension) {
    log.error("provision-sip.groovy: extensión SIP nula. Abortando.")
    return
}

log.info("provision-sip.groovy: operación={}, extensión={}", operation, extension)

// ============================================================
// Lógica de aprovisionamiento según la operación
// ============================================================
switch (operation) {

    case 'CREATE':
        log.info("Creando extensión SIP {} en Asterisk", extension)

        // 1. ps_endpoints
        def existsEndpoint = sql.firstRow(
            "SELECT COUNT(*) AS cnt FROM ps_endpoints WHERE id = ?", [extension]
        )?.cnt ?: 0

        if (existsEndpoint == 0) {
            sql.execute("""
                INSERT INTO ps_endpoints
                    (id, transport, aors, auth, context, disallow, allow,
                     direct_media, force_rport, rewrite_contact, rtp_symmetric)
                VALUES
                    (?, NULL, ?, ?, ?, 'all', 'ulaw', 'no', 'yes', 'yes', 'yes')
            """, [extension, extension, extension, context])
            log.info("ps_endpoints: fila '{}' creada.", extension)
        } else {
            log.warn("ps_endpoints: la extensión '{}' ya existe, se omite INSERT.", extension)
        }

        // 2. ps_auths
        def existsAuth = sql.firstRow(
            "SELECT COUNT(*) AS cnt FROM ps_auths WHERE id2 = ?", [extension]
        )?.cnt ?: 0

        if (existsAuth == 0) {
            sql.execute("""
                INSERT INTO ps_auths (id2, auth_type, password, username)
                VALUES (?, 'userpass', ?, ?)
            """, [extension, sipPassword, extension])
            log.info("ps_auths: credenciales para '{}' creadas.", extension)
        } else {
            log.warn("ps_auths: credenciales para '{}' ya existen, se omite INSERT.", extension)
        }

        // 3. ps_aors
        def existsAor = sql.firstRow(
            "SELECT COUNT(*) AS cnt FROM ps_aors WHERE id = ?", [extension]
        )?.cnt ?: 0

        if (existsAor == 0) {
            sql.execute("""
                INSERT INTO ps_aors (id, max_contacts)
                VALUES (?, 1)
            """, [extension])
            log.info("ps_aors: AOR para '{}' creada.", extension)
        } else {
            log.warn("ps_aors: AOR '{}' ya existe, se omite INSERT.", extension)
        }

        // 4. Registro de auditoría ISO 27001 (Control A.8.16 — Monitoreo)
        logAuditEvent(sql, 'CREATE', extension, 'midPoint IAM', 'Extensión SIP provisionada automáticamente')
        break

    case 'UPDATE':
        log.info("Actualizando extensión SIP {} en Asterisk", extension)

        sql.execute("""
            UPDATE ps_auths
            SET password = ?
            WHERE id2 = ?
        """, [sipPassword, extension])

        sql.execute("""
            UPDATE ps_endpoints
            SET context = ?
            WHERE id = ?
        """, [context, extension])

        logAuditEvent(sql, 'UPDATE', extension, 'midPoint IAM', 'Credenciales SIP actualizadas')
        break

    case 'DELETE':
        log.info("Eliminando extensión SIP {} de Asterisk", extension)

        sql.execute("DELETE FROM ps_aors      WHERE id  = ?", [extension])
        sql.execute("DELETE FROM ps_auths     WHERE id2 = ?", [extension])
        sql.execute("DELETE FROM ps_endpoints WHERE id  = ?", [extension])

        logAuditEvent(sql, 'DELETE', extension, 'midPoint IAM', 'Extensión SIP eliminada (deprovisioning)')
        break

    default:
        log.warn("provision-sip.groovy: operación desconocida '{}'", operation)
}

// ============================================================
// Función de auditoría (ISO 27001 — Control A.8.16)
// Escribe en la tabla audit_log de la BD asterisk
// ============================================================
def logAuditEvent(Sql sqlConn, String action, String extension,
                  String actor, String detail) {
    try {
        // Crear la tabla si no existe (idempotente)
        sqlConn.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id         INT NOT NULL AUTO_INCREMENT,
                event_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                action     VARCHAR(20),
                extension  VARCHAR(40),
                actor      VARCHAR(80),
                detail     VARCHAR(255),
                PRIMARY KEY (id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)

        sqlConn.execute("""
            INSERT INTO audit_log (action, extension, actor, detail)
            VALUES (?, ?, ?, ?)
        """, [action, extension, actor, detail])

    } catch (Exception e) {
        log.error("Error al escribir en audit_log: {}", e.message)
    }
}
