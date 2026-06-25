-- ============================================================
-- Laboratorio Integración de Sistemas
-- init.sql — Creación de BD asterisk y tablas PJSIP
-- Se ejecuta automáticamente al levantar el contenedor MariaDB
-- ============================================================

CREATE DATABASE IF NOT EXISTS asterisk;
USE asterisk;

-- Tabla de peers (compatibilidad SIP legacy)
CREATE TABLE IF NOT EXISTS sippeers (
    id INT NOT NULL AUTO_INCREMENT,
    name VARCHAR(80) NOT NULL,
    host VARCHAR(31) NOT NULL DEFAULT 'dynamic',
    nat VARCHAR(20) NOT NULL DEFAULT 'force_rport',
    type VARCHAR(6) NOT NULL DEFAULT 'friend',
    context VARCHAR(80) NOT NULL DEFAULT 'default',
    permit VARCHAR(95),
    secret VARCHAR(80),
    md5secret VARCHAR(32),
    transport VARCHAR(10) NOT NULL DEFAULT 'udp',
    dtmfmode VARCHAR(7) NOT NULL DEFAULT 'rfc2833',
    disallow VARCHAR(100) NOT NULL DEFAULT 'all',
    allow VARCHAR(100) NOT NULL DEFAULT 'ulaw',
    canreinvite VARCHAR(6) NOT NULL DEFAULT 'no',
    qualify VARCHAR(3) NOT NULL DEFAULT 'yes',
    PRIMARY KEY (id),
    UNIQUE KEY name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Tabla principal de endpoints PJSIP
CREATE TABLE IF NOT EXISTS ps_endpoints (
    id VARCHAR(40) NOT NULL,
    transport VARCHAR(40),
    aors VARCHAR(200),
    auth VARCHAR(40),
    context VARCHAR(40),
    disallow VARCHAR(200) DEFAULT 'all',
    allow VARCHAR(200) DEFAULT 'ulaw',
    direct_media VARCHAR(5) DEFAULT 'no',
    force_rport VARCHAR(5) DEFAULT 'yes',
    rewrite_contact VARCHAR(5) DEFAULT 'yes',
    rtp_symmetric VARCHAR(5) DEFAULT 'yes',
    PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Tabla de autenticación PJSIP
CREATE TABLE IF NOT EXISTS ps_auths (
    id INT NOT NULL AUTO_INCREMENT,
    id2 VARCHAR(40) NOT NULL,
    auth_type VARCHAR(10) DEFAULT 'userpass',
    password VARCHAR(80),
    username VARCHAR(40),
    PRIMARY KEY (id),
    UNIQUE KEY id2 (id2)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Tabla de Address of Records PJSIP
CREATE TABLE IF NOT EXISTS ps_aors (
    id VARCHAR(40) NOT NULL,
    max_contacts INT DEFAULT 1,
    PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Tabla de registro de usuarios (fuente de midPoint)
-- midPoint leerá esta tabla y provisionará extensiones SIP
CREATE TABLE IF NOT EXISTS users (
    id INT NOT NULL AUTO_INCREMENT,
    username VARCHAR(80) NOT NULL,
    full_name VARCHAR(150),
    email VARCHAR(150),
    role VARCHAR(50) DEFAULT 'AgenteCallCenter',
    extension VARCHAR(10),
    sip_password VARCHAR(80),
    status VARCHAR(20) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY username (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================================
-- Datos iniciales — Extensiones 1001 y 1002
-- ============================================================

-- Extensión 1001
INSERT INTO ps_endpoints (id, aors, auth, context, disallow, allow, direct_media, force_rport, rewrite_contact, rtp_symmetric)
VALUES ('1001', '1001', '1001', 'default', 'all', 'ulaw', 'no', 'yes', 'yes', 'yes');

INSERT INTO ps_auths (id2, auth_type, password, username)
VALUES ('1001', 'userpass', 'clave1001', '1001');

INSERT INTO ps_aors (id, max_contacts)
VALUES ('1001', 1);

INSERT INTO sippeers (name, secret, context) VALUES ('1001', 'clave1001', 'default');

-- Extensión 1002
INSERT INTO ps_endpoints (id, aors, auth, context, disallow, allow, direct_media, force_rport, rewrite_contact, rtp_symmetric)
VALUES ('1002', '1002', '1002', 'default', 'all', 'ulaw', 'no', 'yes', 'yes', 'yes');

INSERT INTO ps_auths (id2, auth_type, password, username)
VALUES ('1002', 'userpass', 'clave1002', '1002');

INSERT INTO ps_aors (id, max_contacts)
VALUES ('1002', 1);

INSERT INTO sippeers (name, secret, context) VALUES ('1002', 'clave1002', 'default');

-- ============================================================
-- Datos de usuarios para midPoint
-- ============================================================
INSERT INTO users (username, full_name, email, role, extension, sip_password)
VALUES
  ('jperez',  'Juan Pérez',   'jperez@empresa.com',  'AgenteCallCenter', '1001', 'clave1001'),
  ('mgarcia', 'María García', 'mgarcia@empresa.com', 'AgenteCallCenter', '1002', 'clave1002');
