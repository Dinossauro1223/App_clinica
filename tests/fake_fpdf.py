# -*- coding: utf-8 -*-
"""Simulador mínimo da API do FPDF usada em mapa_export.exportar_pdf.

Serve só para testar o layout (posições, quebras, cores) onde a biblioteca fpdf não
está instalada. Usa a Liberation Sans (métricas idênticas às do Arial/Helvetica) e
desenha cada página numa imagem PIL. NÃO substitui um teste real com o fpdf.
"""
import os

from PIL import Image, ImageDraw, ImageFont

_NOMES = {"": ("LiberationSans-Regular.ttf", "arial.ttf", "DejaVuSans.ttf"),
          "B": ("LiberationSans-Bold.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"),
          "I": ("LiberationSans-Italic.ttf", "ariali.ttf", "DejaVuSans-Oblique.ttf"),
          "BI": ("LiberationSans-BoldItalic.ttf", "arialbi.ttf", "DejaVuSans-BoldOblique.ttf")}
_PASTAS = ("/usr/share/fonts/truetype/liberation", "/usr/share/fonts/truetype/dejavu",
           os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"))


def _achar_fonte(estilo):
    """Liberation Sans (Linux) ou Arial (Windows), de métricas idênticas; senão a fonte padrão do Pillow."""
    for pasta in _PASTAS:
        for nome in _NOMES[estilo]:
            caminho = os.path.join(pasta, nome)
            if os.path.exists(caminho):
                return caminho
    return None
S = 5.0  # pixels por mm


class FakePDF:
    def __init__(self, orientation="P", unit="mm", format="A4"):
        assert unit == "mm" and format == "A4"
        self.w, self.h = (297.0, 210.0) if orientation == "L" else (210.0, 297.0)
        self.paginas = []
        self._img = self._d = None
        self._estilo, self._pt = "", 12
        self._texto = self._preench = self._traco = (0, 0, 0)
        self._lw = 0.2
        self.textos = []  # (pagina, x, y, texto, cor) para asserções

    # configuração ----------------------------------------------------------------
    def set_auto_page_break(self, auto, margin=0):
        pass

    def set_margins(self, l, t, r=-1):
        pass

    def set_font(self, familia, estilo="", tamanho=12):
        assert familia.lower() in ("arial", "helvetica")
        self._estilo = estilo.upper().replace("U", "")
        self._pt = tamanho

    def set_text_color(self, r, g=None, b=None):
        self._texto = (r, g, b)

    def set_fill_color(self, r, g=None, b=None):
        self._preench = (r, g, b)

    def set_draw_color(self, r, g=None, b=None):
        self._traco = (r, g, b)

    def set_line_width(self, w):
        self._lw = w

    # páginas ---------------------------------------------------------------------
    def add_page(self):
        self._img = Image.new("RGB", (int(self.w * S), int(self.h * S)), "white")
        self._d = ImageDraw.Draw(self._img)
        self.paginas.append(self._img)

    def _fonte(self):
        tamanho = max(1, round(self._pt * 0.3528 * S))
        caminho = _achar_fonte(self._estilo)
        return ImageFont.truetype(caminho, tamanho) if caminho else ImageFont.load_default(tamanho)

    def get_string_width(self, txt):
        txt.encode("latin-1")  # o FPDF real também exige latin-1
        return self._fonte().getlength(txt) / S

    # desenho ---------------------------------------------------------------------
    def rect(self, x, y, w, h, style=""):
        kw = {}
        if "F" in style:
            kw["fill"] = self._preench
        if style in ("", "D") or "D" in style:
            kw["outline"] = self._traco
        self._d.rectangle([x * S, y * S, (x + w) * S, (y + h) * S], width=max(1, round(self._lw * S)), **kw)

    def line(self, x1, y1, x2, y2):
        self._d.line([x1 * S, y1 * S, x2 * S, y2 * S], fill=self._traco, width=max(1, round(self._lw * S)))

    def text(self, x, y, txt):
        txt.encode("latin-1")
        self._d.text((x * S, y * S), txt, font=self._fonte(), fill=self._texto, anchor="ls")
        self.textos.append((len(self.paginas), x, y, txt, self._texto))

    def output(self, caminho):
        self.paginas[0].save(caminho, "PDF", resolution=S * 25.4, save_all=True, append_images=self.paginas[1:])

    def salvar_pngs(self, prefixo):
        saida = []
        for i, im in enumerate(self.paginas, 1):
            p = f"{prefixo}_p{i}.png"
            im.save(p)
            saida.append(p)
        return saida
