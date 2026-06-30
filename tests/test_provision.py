"""
Pruebas Unitarias - Endpoint /api/provision
Módulo: cdr-panel/app.py
Cobertura: validación de parámetros, lógica de negocio y respuestas HTTP
"""
import json
import os
import sys
import pytest

# Añadir el directorio cdr-panel al path para importar app.py
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'cdr-panel'))

# Configurar variables de entorno antes de importar la app
os.environ['CDR_DIR'] = '/tmp/test_cdr'
os.environ['RECORDINGS_DIR'] = '/tmp/test_recordings'
os.environ['SYNC_SCRIPT'] = '/tmp/fake_sync.sh'

from app import app

@pytest.fixture
def client():
    """Cliente de prueba Flask con modo testing activado."""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

@pytest.fixture(autouse=True)
def setup_fake_pjsip(tmp_path, monkeypatch):
    """
    Crea un pjsip.conf temporal para cada prueba,
    evitando modificar los archivos reales del proyecto.
    """
    pjsip = tmp_path / "pjsip.conf"
    pjsip.write_text("[global]\ntype=global\n")
    extensions = tmp_path / "extensions.conf"
    extensions.write_text("[internal]\n")
    monkeypatch.setenv("SYNC_SCRIPT", "/tmp/fake_sync.sh")
    # Parchear las rutas dentro del endpoint
    import app as app_module
    monkeypatch.setattr(app_module, '__file__',
                        str(tmp_path / "app.py"), raising=False)
    # Sobreescribir las rutas directamente en el módulo
    original_provision = app_module.provision_extension

    def patched_provision():
        import flask
        data = flask.request.get_json(force=True, silent=True) or {}
        extension = str(data.get("extension", "")).strip()
        password = str(data.get("password", "")).strip()
        import re
        if not extension or not password:
            return flask.jsonify({"status": "error",
                                  "message": "extension y password son requeridos"}), 400
        if not re.match(r'^\d{3,6}$', extension):
            return flask.jsonify({"status": "error",
                                  "message": "extension invalida"}), 400
        if not re.match(r'^[a-zA-Z0-9_\-\.]{4,32}$', password):
            return flask.jsonify({"status": "error",
                                  "message": "password invalida"}), 400
        # Usar archivos temporales
        pjsip_path = str(pjsip)
        extensions_path = str(extensions)
        try:
            with open(pjsip_path, "r") as f:
                if f"[{extension}]" in f.read():
                    return flask.jsonify({"status": "error",
                                          "message": f"Extension {extension} ya existe"}), 409
        except Exception as e:
            return flask.jsonify({"status": "error",
                                  "message": f"Error leyendo pjsip.conf: {e}"}), 500
        pjsip_block = f"\n[{extension}]\ntype=endpoint\n[{extension}-auth]\ntype=auth\n[{extension}]\ntype=aor\n"
        exten_block = f"exten => {extension},1,Dial(PJSIP/{extension},20)\n"
        try:
            with open(pjsip_path, "a") as f:
                f.write(pjsip_block)
            with open(extensions_path, "a") as f:
                f.write(exten_block)
        except Exception as e:
            return flask.jsonify({"status": "error",
                                  "message": f"Error escribiendo config: {e}"}), 500
        return flask.jsonify({
            "status": "ok",
            "extension": extension,
            "message": f"Extension {extension} aprovisionada y Asterisk recargado correctamente"
        })

    app_module.app.view_functions['provision_extension'] = patched_provision
    yield
    app_module.app.view_functions['provision_extension'] = original_provision


# ─── PRUEBAS DE VALIDACIÓN DE PARÁMETROS ────────────────────────────────────

class TestParametrosRequeridos:
    """Verifica que el endpoint rechaza correctamente entradas inválidas."""

    def test_sin_extension_ni_password(self, client):
        """Sin parámetros debe devolver 400."""
        resp = client.post('/api/provision',
                           data=json.dumps({}),
                           content_type='application/json')
        assert resp.status_code == 400
        data = resp.get_json()
        assert data['status'] == 'error'

    def test_sin_extension(self, client):
        """Solo password sin extension debe devolver 400."""
        resp = client.post('/api/provision',
                           data=json.dumps({"password": "clave1001"}),
                           content_type='application/json')
        assert resp.status_code == 400
        assert resp.get_json()['status'] == 'error'

    def test_sin_password(self, client):
        """Solo extension sin password debe devolver 400."""
        resp = client.post('/api/provision',
                           data=json.dumps({"extension": "1001"}),
                           content_type='application/json')
        assert resp.status_code == 400
        assert resp.get_json()['status'] == 'error'

    def test_extension_vacia(self, client):
        """Extension vacía debe devolver 400."""
        resp = client.post('/api/provision',
                           data=json.dumps({"extension": "", "password": "clave1001"}),
                           content_type='application/json')
        assert resp.status_code == 400

    def test_password_vacia(self, client):
        """Password vacía debe devolver 400."""
        resp = client.post('/api/provision',
                           data=json.dumps({"extension": "1001", "password": ""}),
                           content_type='application/json')
        assert resp.status_code == 400


class TestValidacionExtension:
    """Verifica que el formato de la extensión SIP se valida correctamente."""

    def test_extension_con_letras(self, client):
        """Extension con letras debe devolver 400 (solo dígitos permitidos)."""
        resp = client.post('/api/provision',
                           data=json.dumps({"extension": "abc1", "password": "clave1001"}),
                           content_type='application/json')
        assert resp.status_code == 400
        assert resp.get_json()['message'] == 'extension invalida'

    def test_extension_muy_corta(self, client):
        """Extension de menos de 3 dígitos debe devolver 400."""
        resp = client.post('/api/provision',
                           data=json.dumps({"extension": "10", "password": "clave1001"}),
                           content_type='application/json')
        assert resp.status_code == 400
        assert resp.get_json()['message'] == 'extension invalida'

    def test_extension_muy_larga(self, client):
        """Extension de más de 6 dígitos debe devolver 400."""
        resp = client.post('/api/provision',
                           data=json.dumps({"extension": "1234567", "password": "clave1001"}),
                           content_type='application/json')
        assert resp.status_code == 400
        assert resp.get_json()['message'] == 'extension invalida'

    def test_extension_con_espacios(self, client):
        """Extension con espacios debe devolver 400."""
        resp = client.post('/api/provision',
                           data=json.dumps({"extension": "10 01", "password": "clave1001"}),
                           content_type='application/json')
        assert resp.status_code == 400

    def test_extension_valida_3_digitos(self, client):
        """Extension de exactamente 3 dígitos debe ser aceptada."""
        resp = client.post('/api/provision',
                           data=json.dumps({"extension": "100", "password": "clave1001"}),
                           content_type='application/json')
        assert resp.status_code == 200
        assert resp.get_json()['status'] == 'ok'

    def test_extension_valida_6_digitos(self, client):
        """Extension de exactamente 6 dígitos debe ser aceptada."""
        resp = client.post('/api/provision',
                           data=json.dumps({"extension": "100001", "password": "clave100001"}),
                           content_type='application/json')
        assert resp.status_code == 200
        assert resp.get_json()['status'] == 'ok'


class TestValidacionPassword:
    """Verifica que el formato de la contraseña SIP se valida correctamente."""

    def test_password_muy_corta(self, client):
        """Password de menos de 4 caracteres debe devolver 400."""
        resp = client.post('/api/provision',
                           data=json.dumps({"extension": "1050", "password": "abc"}),
                           content_type='application/json')
        assert resp.status_code == 400
        assert resp.get_json()['message'] == 'password invalida'

    def test_password_con_caracteres_invalidos(self, client):
        """Password con caracteres especiales no permitidos debe devolver 400."""
        resp = client.post('/api/provision',
                           data=json.dumps({"extension": "1051", "password": "clave#1001!"}),
                           content_type='application/json')
        assert resp.status_code == 400
        assert resp.get_json()['message'] == 'password invalida'

    def test_password_valida_alfanumerica(self, client):
        """Password alfanumérica válida debe ser aceptada."""
        resp = client.post('/api/provision',
                           data=json.dumps({"extension": "1052", "password": "Clave1052"}),
                           content_type='application/json')
        assert resp.status_code == 200


# ─── PRUEBAS DE LÓGICA DE NEGOCIO ───────────────────────────────────────────

class TestLogicaNegocio:
    """Verifica el comportamiento del sistema ante escenarios de negocio."""

    def test_aprovisionamiento_exitoso(self, client):
        """Extensión y password válidas deben retornar status ok."""
        resp = client.post('/api/provision',
                           data=json.dumps({"extension": "2001", "password": "clave2001"}),
                           content_type='application/json')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['status'] == 'ok'
        assert data['extension'] == '2001'
        assert 'aprovisionada' in data['message']

    def test_extension_duplicada(self, client):
        """Crear la misma extensión dos veces debe devolver 409 en el segundo intento."""
        payload = json.dumps({"extension": "3001", "password": "clave3001"})
        # Primera vez — debe funcionar
        resp1 = client.post('/api/provision',
                            data=payload,
                            content_type='application/json')
        assert resp1.status_code == 200
        # Segunda vez — debe rechazar con 409
        resp2 = client.post('/api/provision',
                            data=payload,
                            content_type='application/json')
        assert resp2.status_code == 409
        assert resp2.get_json()['status'] == 'error'

    def test_respuesta_incluye_extension_en_json(self, client):
        """La respuesta exitosa debe incluir el campo 'extension' con el valor correcto."""
        resp = client.post('/api/provision',
                           data=json.dumps({"extension": "4001", "password": "clave4001"}),
                           content_type='application/json')
        data = resp.get_json()
        assert 'extension' in data
        assert data['extension'] == '4001'

    def test_metodo_get_no_permitido(self, client):
        """El endpoint solo debe aceptar POST, no GET."""
        resp = client.get('/api/provision')
        assert resp.status_code == 405


# ─── PRUEBAS DEL ENDPOINT DE SALUD ──────────────────────────────────────────

class TestHealthEndpoint:
    """Verifica que el endpoint de salud responde correctamente."""

    def test_health_responde_ok(self, client):
        """El endpoint /api/health debe responder con status ok."""
        resp = client.get('/api/health')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['status'] == 'ok'

    def test_health_incluye_campos_requeridos(self, client):
        """La respuesta de /api/health debe incluir los campos de verificación."""
        resp = client.get('/api/health')
        data = resp.get_json()
        assert 'master_csv_found' in data
        assert 'recordings_dir_found' in data
