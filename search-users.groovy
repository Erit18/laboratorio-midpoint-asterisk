/**
 * search-users.groovy
 * Script de búsqueda: midPoint lo llama para leer las cuentas
 * existentes en la BD asterisk y reconciliarlas con sus usuarios internos.
 *
 * Retorna una lista de objetos ConnectorObject que representan
 * las extensiones SIP registradas en ps_endpoints.
 */

import groovy.sql.Sql
import org.identityconnectors.framework.common.objects.AttributeBuilder
import org.identityconnectors.framework.common.objects.ConnectorObjectBuilder
import org.identityconnectors.framework.common.objects.ObjectClass

log.info("search-users.groovy: iniciando búsqueda de extensiones SIP")

def results = []

try {
    sql.eachRow("""
        SELECT
            e.id            AS extension,
            a.password      AS sip_password,
            e.context       AS context,
            e.allow         AS codecs,
            aor.max_contacts AS max_contacts
        FROM ps_endpoints e
        LEFT JOIN ps_auths a   ON a.id2 = e.id
        LEFT JOIN ps_aors aor  ON aor.id = e.id
        ORDER BY e.id
    """) { row ->

        def builder = new ConnectorObjectBuilder()
        builder.setObjectClass(ObjectClass.ACCOUNT)
        builder.setUid(row.extension as String)
        builder.setName(row.extension as String)

        builder.addAttribute(AttributeBuilder.build('password',     row.sip_password ?: ''))
        builder.addAttribute(AttributeBuilder.build('context',      row.context      ?: 'default'))
        builder.addAttribute(AttributeBuilder.build('codecs',       row.codecs       ?: 'ulaw'))
        builder.addAttribute(AttributeBuilder.build('max_contacts', row.max_contacts?.toString() ?: '1'))

        handler.handle(builder.build())
        results << row.extension
        log.info("search-users.groovy: encontrada extensión {}", row.extension)
    }
} catch (Exception e) {
    log.error("search-users.groovy: error al consultar ps_endpoints: {}", e.message)
}

log.info("search-users.groovy: {} extensión(es) encontrada(s): {}", results.size(), results)
return results
