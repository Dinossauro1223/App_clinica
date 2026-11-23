"""Regressões do catálogo de exames: semeia os JSON versionados e é idempotente."""
import sqlite3
import tempfile
import unittest
from pathlib import Path

import db_esquema_legado


class TestCatalogoExamesSemente(unittest.TestCase):
    def test_catalogo_e_preenchido_a_partir_dos_json_versionados(self):
        with tempfile.TemporaryDirectory() as tmp:
            caminho = Path(tmp) / "clinica.db"
            conn = sqlite3.connect(caminho)
            db_esquema_legado.garantir_esquema_legado(conn)
            total = conn.execute("SELECT COUNT(*) FROM Exames_Catalogo").fetchone()[0]
            albumina = conn.execute(
                "SELECT nome_amigavel FROM Exames_Catalogo WHERE id_exame='EXM-ALBUMINA-SERICA'"
            ).fetchone()
            self.assertGreater(total, 15)
            self.assertIsNotNone(albumina)
            self.assertIn("Albumina", albumina[0])
            conn.close()

    def test_semente_e_idempotente_e_preserva_nome_existente(self):
        with tempfile.TemporaryDirectory() as tmp:
            caminho = Path(tmp) / "clinica.db"
            conn = sqlite3.connect(caminho)
            db_esquema_legado.garantir_esquema_legado(conn)
            conn.execute(
                "UPDATE Exames_Catalogo SET nome_amigavel='Nome personalizado' WHERE id_exame='EXM-ALBUMINA-SERICA'"
            )
            conn.commit()
            antes = conn.execute("SELECT COUNT(*) FROM Exames_Catalogo").fetchone()[0]
            db_esquema_legado.garantir_esquema_legado(conn)
            depois = conn.execute("SELECT COUNT(*) FROM Exames_Catalogo").fetchone()[0]
            nome = conn.execute(
                "SELECT nome_amigavel FROM Exames_Catalogo WHERE id_exame='EXM-ALBUMINA-SERICA'"
            ).fetchone()[0]
            self.assertEqual(depois, antes)
            self.assertEqual(nome, "Nome personalizado")
            conn.close()


if __name__ == "__main__":
    unittest.main()
