"""Testes de nutri_avaliacao — somente números sintéticos."""
import unittest

import nutri_avaliacao as na


class PesoCorrigido(unittest.TestCase):
    def test_sem_ajustes(self):
        self.assertAlmostEqual(na.peso_corrigido(70), 70)

    def test_edema_ascite_amputacao(self):
        self.assertAlmostEqual(na.peso_corrigido(80, 3.5, 6.0, 5.9), (80 - 9.5) / 0.941)

    def test_invalidos(self):
        for args in ((0,), (70, 80), (70, 0, 0, 100), (70, -1)):
            with self.assertRaises(ValueError):
                na.peso_corrigido(*args)


class DRI(unittest.TestCase):
    def test_homem_adulto_sedentario(self):
        r = na.dri_energia("Masculino", 30, 70, 1.75, 0)
        self.assertAlmostEqual(r.kcal, 662 - 9.53 * 30 + 15.91 * 70 + 539.6 * 1.75)

    def test_mulher_sobrepeso_usa_tee(self):
        r = na.dri_energia("F", 40, 90, 1.60, 1)
        self.assertIn("sobrepeso", r.equacao)
        self.assertAlmostEqual(r.kcal, 448 - 7.95 * 40 + 1.16 * (11.4 * 90 + 619 * 1.6))

    def test_crianca_menino_10(self):
        r = na.dri_energia("H", 10, 32, 1.38, 1)
        self.assertAlmostEqual(r.kcal, 88.5 - 619 + 1.13 * (26.7 * 32 + 903 * 1.38) + 25)
        self.assertTrue(r.aviso)

    def test_indisponivel(self):
        for args in (("F", 2, 12, 0.85), ("F", 30, None, 1.6), (None, 30, 60, 1.6), ("F", 30, 60, 1.6, 9)):
            with self.assertRaises(na.DRIIndisponivel):
                na.dri_energia(*args)


class Suplementos(unittest.TestCase):
    def test_aporte(self):
        k, p, sem = na.aporte_suplementos([("Nutrison 1,5", 200, 3), ("Fresubin Protein Powder", 5.4, 2), ("Simbioflora (sachê)", 1, 1)])
        self.assertAlmostEqual(k, 600 * 1.51 + 10.8 * 3.6)
        self.assertAlmostEqual(p, 600 * 0.06 + 10.8 * 0.87)
        self.assertEqual(sem, ["Simbioflora (sachê)"])


if __name__ == "__main__":
    unittest.main()
