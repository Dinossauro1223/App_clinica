"""Gera PNG e ICO a partir da identidade SVG do NutriLab."""
from pathlib import Path
import cairosvg
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SVG = ROOT / "assets" / "identidade" / "nutrilab_identidade.svg"
ICON_SVG = ROOT / "assets" / "identidade" / "nutrilab_icone.svg"
PNG = ROOT / "assets" / "identidade" / "nutrilab_identidade.png"
ICON_PNG = ROOT / "assets" / "identidade" / "nutrilab_icone.png"
ICO = ROOT / "assets" / "identidade" / "nutrilab.ico"

def main():
    if not SVG.is_file():
        raise SystemExit(f"SVG de identidade não encontrado: {SVG}")
    if not ICON_SVG.is_file():
        raise SystemExit(f"SVG do ícone não encontrado: {ICON_SVG}")
    cairosvg.svg2png(url=str(SVG), write_to=str(PNG), output_width=1533, output_height=1026)
    cairosvg.svg2png(url=str(ICON_SVG), write_to=str(ICON_PNG), output_width=512, output_height=512)
    with Image.open(ICON_PNG) as imagem:
        imagem.convert("RGBA").save(ICO, format="ICO", sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])
    print(f"PNG gerado: {PNG}")
    print(f"PNG do ícone gerado: {ICON_PNG}")
    print(f"ICO quadrado gerado: {ICO}")

if __name__ == "__main__":
    main()
