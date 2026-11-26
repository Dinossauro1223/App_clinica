# -*- coding: utf-8 -*-
"""Testes do indicador de conexão e do registro administrativo do IP local."""
import os
import socket
import tempfile
import threading
import unittest
from unittest.mock import patch

from mobile import servidor as sv


class TestStatusRedeLocal(unittest.TestCase):
    def setUp(self):
        fd, self.db = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        sv.preparar_banco(self.db)
        self.addCleanup(lambda: os.path.exists(self.db) and os.remove(self.db))
        self.admin = sv.rotear(
            self.db, "192.168.10.20", "POST", "/api/login", {},
            {"login": "admin", "senha": sv.SENHA_ADMIN_INICIAL}, ""
        )["token"]

    def test_status_publica_ip_detectado_sem_expor_dados_de_usuario(self):
        with patch.object(sv, "ip_lan", return_value="192.168.10.15"):
            status = sv.rotear(self.db, "192.168.10.20", "GET", "/api/status", {}, {}, "")
        self.assertEqual(status["status"], "online")
        self.assertEqual(status["ip_lan"], "192.168.10.15")
        self.assertEqual(status["porta"], 8765)
        self.assertIsNone(status["ip_registrado"])
        self.assertNotIn("usuarios", status)

    def test_admin_registra_ip_atual_e_status_reflete_o_registro(self):
        with patch.object(sv, "ip_lan", return_value="192.168.10.15"):
            salvo = sv.rotear(self.db, "192.168.10.20", "POST",
                              "/api/admin/rede/registrar", {}, {}, "Bearer " + self.admin)
            status = sv.rotear(self.db, "192.168.10.20", "GET", "/api/status", {}, {}, "")
        self.assertTrue(salvo["ok"])
        self.assertEqual(salvo["ip_lan"], "192.168.10.15")
        self.assertEqual(status["ip_registrado"], "192.168.10.15")
        self.assertEqual(status["registrado_em"], salvo["registrado_em"])

    def test_perfil_nao_administrador_nao_pode_registrar_rede(self):
        with patch.object(sv, "ip_lan", return_value="192.168.10.15"):
            c = sv.conectar(self.db)
            try:
                sv.criar_usuario(c, "copa", "Equipe Copa", "copa", None, "senha123")
                c.commit()
            finally:
                c.close()
            token = sv.rotear(self.db, "192.168.10.20", "POST", "/api/login", {},
                              {"login": "copa", "senha": "senha123"}, "")["token"]
            with self.assertRaises(sv.Erro) as erro:
                sv.rotear(self.db, "192.168.10.20", "POST", "/api/admin/rede/registrar",
                          {}, {}, "Bearer " + token)
        self.assertEqual(erro.exception.cod, 403)


    def test_registro_ip_repetido_com_mesma_operacao_nao_aplica_novamente(self):
        token = "Bearer " + self.admin
        with patch.object(sv, "ip_lan", return_value="192.168.10.15"):
            primeira = sv.rotear(self.db, "192.168.10.20", "POST",
                                 "/api/admin/rede/registrar", {}, {}, token,
                                 operation_id="op-registro-ip-001")
        with patch.object(sv, "ip_lan", return_value="192.168.10.99"):
            repetida = sv.rotear(self.db, "192.168.10.20", "POST",
                                 "/api/admin/rede/registrar", {}, {}, token,
                                 operation_id="op-registro-ip-001")
        self.assertEqual(repetida, primeira)
        status = sv.rotear(self.db, "192.168.10.20", "GET", "/api/status", {}, {}, "")
        self.assertEqual(status["ip_registrado"], "192.168.10.15")

    def test_id_de_operacao_nao_pode_ser_reutilizado_com_outro_conteudo(self):
        token = "Bearer " + self.admin
        with patch.object(sv, "ip_lan", return_value="192.168.10.15"):
            sv.rotear(self.db, "192.168.10.20", "POST",
                      "/api/admin/rede/registrar", {}, {}, token,
                      operation_id="op-registro-ip-002")
        with patch.object(sv, "ip_lan", return_value="192.168.10.99"):
            with self.assertRaises(sv.Erro) as erro:
                sv.rotear(self.db, "192.168.10.20", "POST",
                          "/api/admin/rede/registrar", {"forjado": "valor"}, {}, token,
                          operation_id="op-registro-ip-002")
        self.assertEqual(erro.exception.cod, 409)


    def test_identidade_do_servidor_permanece_estavel_entre_inicializacoes(self):
        antes = sv.rotear(self.db, "192.168.10.20", "GET", "/api/status", {}, {}, "")["server_id"]
        sv.preparar_banco(self.db)
        depois = sv.rotear(self.db, "192.168.10.20", "GET", "/api/status", {}, {}, "")["server_id"]
        self.assertTrue(antes)
        self.assertEqual(antes, depois)

    def test_descoberta_udp_retorna_endereco_e_identidade_sem_expor_dados(self):
        servidor = sv.ServidorDescoberta(("127.0.0.1", 0), sv.ManipuladorDescoberta)
        servidor.db = self.db
        servidor.http_port = 8765
        thread = threading.Thread(target=servidor.serve_forever, daemon=True)
        thread.start()
        try:
            cliente = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            cliente.settimeout(2)
            with cliente:
                cliente.sendto(b"NUTRILAB_DISCOVER_V1", servidor.server_address)
                dados, _ = cliente.recvfrom(512)
            partes = dados.decode("utf-8").split("|")
            self.assertEqual(partes[0], "NUTRILAB_SERVER_V1")
            self.assertEqual(partes[1], "http://192.168.10.15:8765")
            self.assertTrue(partes[2])
        finally:
            servidor.shutdown()
            servidor.server_close()


if __name__ == "__main__":
    unittest.main()
