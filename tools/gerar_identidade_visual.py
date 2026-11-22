"""Gera os recursos raster usados pelo CustomTkinter e pelo executável Windows."""
from pathlib import Path
import cairosvg
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SVG = ROOT / "assets" / "identidade" / "nutrilab_identidade.svg"
PNG = ROOT / "assets" / "identidade" / "nutrilab_identidade.png"
ICO = ROOT / "assets" / "identidade" / "nutrilab.ico"

def main():
    if not SVG.is_file():
        raise SystemExit(f"SVG de identidade não encontrado: {SVG}")
    cairosvg.svg2png(url=str(SVG), write_to=str(PNG), output_width=1533, output_height=1026)
    with Image.open(PNG) as imagem:
        imagem.convert("RGBA").save(
            ICO, format="ICO",
            sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
        )
    print(f"PNG gerado: {PNG}")
    print(f"ICO gerado: {ICO}")

if __name__ == "__main__":
    main()
