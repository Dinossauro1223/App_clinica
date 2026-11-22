"""Gera os ícones e as camadas PNG transparentes a partir dos SVGs do NutriLab."""
from pathlib import Path
import io
import json
import xml.etree.ElementTree as ET

import cairosvg
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
IDENTIDADE = ROOT / "assets" / "identidade"
SVG = IDENTIDADE / "nutrilab_identidade.svg"
ICON_SVG = IDENTIDADE / "nutrilab_icone.svg"
PNG = IDENTIDADE / "nutrilab_identidade.png"
ICON_PNG = IDENTIDADE / "nutrilab_icone.png"
ICO = IDENTIDADE / "nutrilab.ico"
COMPONENTES = IDENTIDADE / "componentes"
RENDERIZADOS = IDENTIDADE / "renderizados"

CAMADAS = (
    "arco", "assinatura", "dna", "facisa_ufrn", "frasco",
    "haste_folhas", "maca", "wordmark", "topo_temas",
    "boas_vindas", "decoracao_inferior",
)


def renderizar_svg(origem, destino, escala=2):
    cairosvg.svg2png(url=str(origem), write_to=str(destino), scale=escala)


def renderizar_folhas_individuais():
    """Extrai cada path folha-1..5 do SVG original, preservando alpha e bbox."""
    origem = COMPONENTES / "folhas.svg"
    raiz = ET.parse(origem).getroot()
    ns = "{http://www.w3.org/2000/svg}"
    defs = raiz.find(ns + "defs")
    grupo = raiz.find(".//" + ns + "g[@id='folhas']")
    if grupo is None:
        raise SystemExit("O SVG componentes/folhas.svg não contém o grupo id='folhas'.")
    manifesto = []
    for indice in range(1, 6):
        elemento = grupo.find(f"{ns}path[@id='folha-{indice}']")
        if elemento is None:
            raise SystemExit(f"Folha independente folha-{indice} não encontrada.")
        svg = ET.Element(ns + "svg", {
            "width": "420", "height": "400", "viewBox": "0 0 420 400"
        })
        if defs is not None:
            svg.append(defs)
        grupo_unico = ET.SubElement(svg, ns + "g", {"fill": "url(#f)"})
        grupo_unico.append(elemento)
        dados = ET.tostring(svg, encoding="utf-8", xml_declaration=True)
        raster = cairosvg.svg2png(bytestring=dados, output_width=840, output_height=800)
        imagem = Image.open(io.BytesIO(raster)).convert("RGBA")
        bbox = imagem.getchannel("A").getbbox()
        if not bbox:
            raise SystemExit(f"A folha-{indice} foi renderizada vazia.")
        # A imagem é recortada no conteúdo visível, mantendo o bbox em coordenadas SVG.
        recorte = imagem.crop(bbox)
        nome = f"folha_{indice}.png"
        recorte.save(RENDERIZADOS / nome, optimize=True)
        manifesto.append({
            "arquivo": nome,
            "bbox": [round(valor / 2, 2) for valor in bbox],
        })
    (RENDERIZADOS / "folhas.json").write_text(
        json.dumps(manifesto, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def renderizar_camadas():
    RENDERIZADOS.mkdir(parents=True, exist_ok=True)
    for nome in CAMADAS:
        origem = COMPONENTES / f"{nome}.svg"
        if not origem.is_file():
            raise SystemExit(f"Camada SVG obrigatória não encontrada: {origem}")
        renderizar_svg(origem, RENDERIZADOS / f"{nome}.png", escala=2)
    renderizar_folhas_individuais()


def main():
    if not SVG.is_file():
        raise SystemExit(f"SVG de identidade não encontrado: {SVG}")
    if not ICON_SVG.is_file():
        raise SystemExit(f"SVG do ícone não encontrado: {ICON_SVG}")
    cairosvg.svg2png(url=str(SVG), write_to=str(PNG), output_width=1533, output_height=1026)
    cairosvg.svg2png(url=str(ICON_SVG), write_to=str(ICON_PNG), output_width=512, output_height=512)
    with Image.open(ICON_PNG) as imagem:
        imagem.convert("RGBA").save(
            ICO, format="ICO",
            sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
        )
    renderizar_camadas()
    print(f"PNG legado: {PNG}")
    print(f"Ícone PNG: {ICON_PNG}")
    print(f"Ícone ICO: {ICO}")
    print(f"Camadas transparentes: {RENDERIZADOS}")


if __name__ == "__main__":
    main()
