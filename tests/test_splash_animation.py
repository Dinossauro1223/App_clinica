"""Regressions tests for the welcome-screen leaf animation contract."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TestSplashAnimationContract(unittest.TestCase):
    def test_large_leaves_are_anchored_and_only_sway(self):
        source = (ROOT / "tela_boas_vindas.py").read_text(encoding="utf-8")
        self.assertIn('"base_x": 815 + px_svg * .95', source)
        self.assertIn('center=folha["pivo"]', source)
        self.assertIn('math.sin(folha["fase"]) * folha["amplitude"]', source)
        self.assertNotIn('folha["x"] +=', source)
        self.assertNotIn('folha["x"] = -', source)

    def test_small_leaflets_have_random_motion_and_fade_before_apple(self):
        source = (ROOT / "tela_boas_vindas.py").read_text(encoding="utf-8")
        for token in ("random.uniform(-1.15, 1.15)", "random.randint(35, 75)",
                      "progresso - .35", 'p["x"] >= 850', "folha_marca"):
            self.assertIn(token, source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
