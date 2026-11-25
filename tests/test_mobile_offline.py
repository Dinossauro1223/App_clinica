# -*- coding: utf-8 -*-
"""Testes do cache, fila offline e fallback Android do NutriLab Mobile."""
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "mobile" / "static" / "index.html"
JAVA = ROOT / "mobile" / "apk" / "app" / "src" / "br" / "nutrilab" / "mobile" / "MainActivity.java"
BAT = ROOT / "mobile" / "apk" / "Gerar_APK.bat"


class TestMobileOffline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        texto = HTML.read_text(encoding="utf-8")
        scripts = re.findall(r"<script>(.*?)</script>", texto, re.S)
        cls.offline_js = scripts[0]
        cls.html = texto

    def node(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("Node.js não instalado neste ambiente.")
        return node

    def test_sintaxe_javascript(self):
        node = self.node()
        with tempfile.TemporaryDirectory() as tmp:
            js = Path(tmp) / "offline.js"
            js.write_text(self.offline_js, encoding="utf-8")
            r = subprocess.run([node, "--check", str(js)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_cache_offline_fila_e_atualizacao_local_do_mapa(self):
        node = self.node()
        prelude = r"""
const assert=require('assert');
global.window=global;global.addEventListener=()=>{};
global.location={href:'http://127.0.0.1:8765/'};
const store=new Map();
global.localStorage={getItem:k=>store.has(k)?store.get(k):null,setItem:(k,v)=>store.set(k,String(v)),removeItem:k=>store.delete(k)};
global.document={addEventListener(){},body:{appendChild(){}},createElement(){return {style:{},className:'',innerHTML:'',querySelector(){return {onclick:null,textContent:''}},remove(){}}}};
let online=true;
global.fetch=async (input,init={})=>{
 if(!online)throw new TypeError('offline');
 const u=new URL(typeof input==='string'?input:input.url,location.href);
 if(u.pathname==='/api/mapa' && (!init.method||init.method==='GET'))
  return new Response(JSON.stringify({linhas:[{id_leito:1,codigo:'A01',nome:'Paciente base',idade_anos:70,cor:'B',suplementos:[]}]}),{status:200,headers:{'Content-Type':'application/json'}});
 if(u.pathname==='/api/eu')
  return new Response(JSON.stringify({usuario:{id:1,nome:'Copa'},hoje:'2026-11-22'}),{status:200,headers:{'Content-Type':'application/json'}});
 return new Response(JSON.stringify({ok:true}),{status:200,headers:{'Content-Type':'application/json'}});
};
window.NL={isStaff:()=>false,token:()=>'',userId:()=>1};
"""
        verificacao = r"""
(async()=>{
 const url='/api/mapa?setor=1&data=2026-11-22';
 let r=await fetch(url);let first=await r.json();assert.equal(first.linhas[0].nome,'Paciente base');
 online=false;
 r=await fetch(url);let cached=await r.json();assert.equal(cached.__offline,true);
 const body={setor:1,data:'2026-11-22',linhas:[{id_leito:1,nome:'Paciente alterado',cor:'N',
  suplementos:[{id_suplemento:1,nome:'Fórmula',ml_oferta:100,agua_ml:20,refeicoes:['desjejum','ceia'],batido_fruta:true}]}]};
 r=await fetch('/api/mapa',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
 assert.equal((await r.json()).queued,true);assert.equal(NLOffline.pendentes(),1);
 r=await fetch(url);cached=await r.json();assert.equal(cached.linhas[0].nome,'Paciente alterado');
 assert.equal(cached.linhas[0].suplementos[0].qtd_dia,200);
 NLOffline.set('user',JSON.stringify({usuario:{id:1,nome:'Copa'},hoje:'2026-11-22'}));
 r=await fetch('/api/eu');const eu=await r.json();assert.equal(eu.usuario.id,1);assert.equal(eu.__offline,true);
 NLOffline.clearData();assert.equal(NLOffline.pendentes(),0);
 console.log('OK');
})().catch(e=>{console.error(e);process.exit(1)});
"""
        with tempfile.TemporaryDirectory() as tmp:
            js = Path(tmp) / "teste.js"
            js.write_text(prelude + self.offline_js + verificacao, encoding="utf-8")
            r = subprocess.run([node, str(js)], capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("OK", r.stdout)

    def test_interface_oferece_as_tres_acoes_de_sincronizacao(self):
        for texto in ("Enviar atualizações", "Adiar até o próximo acesso ao servidor",
                      "Reverter cópia local para a versão do servidor"):
            self.assertIn(texto, self.html)

    def test_apk_tem_fallback_local_e_cache_cifrado(self):
        java = JAVA.read_text(encoding="utf-8")
        bat = BAT.read_text(encoding="utf-8")
        self.assertIn('getAssets().open("index.html")', java)
        self.assertIn("loadDataWithBaseURL", java)
        self.assertIn("AES/GCM/NoPadding", java)
        self.assertIn("AndroidKeyStore", java)
        self.assertIn('getAssets().open("jsQR.js")', java)
        self.assertIn(r"..\static\jsQR.js", bat)
        self.assertIn(r"..\static\index.html", bat)
        self.assertIn("--release 8", bat)
        self.assertIn('-classpath "%AJAR%;%ZXING%"', bat)
        self.assertIn("QRScannerActivity.java", bat)
        self.assertIn("ZXINGURL", bat)
        self.assertNotIn("-bootclasspath", bat)
        # Uma única fonte versionada; os builds CI/local geram o asset dentro do APK.
        asset = ROOT / "mobile" / "apk" / "app" / "assets" / "index.html"
        self.assertFalse(asset.exists(), "Não manter segunda cópia versionada de index.html")
        builder = (ROOT / "tools" / "build_apk_ci.py").read_text(encoding="utf-8")
        self.assertIn('shutil.copy2(STATIC, app / "assets" / "index.html")', builder)
        self.assertIn('shutil.copy2(JSQR, app / "assets" / "jsQR.js")', builder)
        self.assertIn('copy /y "%~dp0..\\static\\index.html" "%APP%\\assets\\index.html"', bat)
        release = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
        self.assertIn("setup-android@v4", release)
        self.assertIn("QRScannerActivity.java", release)
        self.assertIn("zxing-core-3.4.1.jar", release)
        self.assertIn('cp mobile/static/jsQR.js "$WORK/app/assets/jsQR.js"', release)
        self.assertIn("--release 8 -classpath", release)
        self.assertNotIn("-bootclasspath", release)
        self.assertIn('tags: ["v*"]', release)
        workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        self.assertIn("apk-java:", workflow)
        self.assertIn("android-34", workflow)


    def test_login_mobile_oferece_qr_e_apk_tem_leitor_nativo(self):
        self.assertIn("Escanear QR code", self.html)
        self.assertIn("Android.escanearQR()", self.html)
        self.assertIn("nutrilab-server", self.html)
        self.assertIn("Prazo médio de reposição dos insumos", self.html)
        self.assertIn("carregaPrazos", self.html)
        self.assertIn("novoPedidoMobile", self.html)
        self.assertIn('/static/jsQR.js', self.html)
        jsqr = ROOT / "mobile" / "static" / "jsQR.js"
        self.assertTrue(jsqr.is_file())
        scanner = JAVA.parent / "QRScannerActivity.java"
        self.assertTrue(scanner.is_file(), "O APK precisa do leitor QR nativo para funcionar em HTTP local.")
        java = scanner.read_text(encoding="utf-8")
        self.assertIn("MultiFormatReader", java)
        self.assertIn("Camera.open()", java)
        aviso_terceiros = ROOT / "mobile" / "apk" / "app" / "assets" / "THIRD_PARTY_NOTICES.txt"
        self.assertTrue(aviso_terceiros.is_file(), "A licença do ZXing deve acompanhar o APK.")
        manifest = (ROOT / "mobile" / "apk" / "app" / "AndroidManifest.xml").read_text(encoding="utf-8")
        self.assertIn('android:name=".QRScannerActivity"', manifest)


    def test_sintaxe_do_decodificador_qr_offline(self):
        node = self.node()
        jsqr = ROOT / "mobile" / "static" / "jsQR.js"
        r = subprocess.run([node, "--check", str(jsqr)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)


@unittest.skipUnless(
    sv is not None and all(hasattr(sv, n) for n in ("preparar_banco", "post_mapa", "exportar")),
    "servidor mobile não disponível",
)
class TestBackendMobileSemAparelho(unittest.TestCase):
    """Exercita o backend completo em SQLite, sem câmera, APK ou rede."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="nutrilab-backend-mobile-")
        self.desktop = os.path.join(self.tmp, "desktop.db")
        self.mobile = os.path.join(self.tmp, "mobile.db")
        self.addCleanup(shutil.rmtree, self.tmp, True)

        mdb.inicializar(self.desktop)
        mdb.criar_setor(self.desktop, "Clinica A")
        sid = next(
            s["id_setor"] for s in mdb.listar_setores(self.desktop)
            if s["nome"] == "Clinica A"
        )
        mdb.criar_leitos_sequencia(self.desktop, sid, "A", 1, 2)
        self.leitos = {
            l["codigo"]: l["id_leito"]
            for l in mdb.listar_leitos(self.desktop, sid)
        }
        sv.preparar_banco(self.mobile)

    def _salvar(self, nome="Paciente Teste", idade=72):
        mdb.salvar_registro(self.desktop, {
            "data": "2026-11-25",
            "id_leito": self.leitos["A01"],
            "nome_paciente": nome,
            "idade_anos": idade,
            "consistencia": "Pastosa",
            "dm": 1,
        })

    def test_desktop_server_export_roundtrip_sem_aparelho(self):
        """Desktop -> servidor -> exportação é validado somente com bancos locais."""
        self._salvar()

        resultado = im.enviar_mapa(self.desktop, self.mobile, "2026-11-25")
        self.assertEqual(resultado[0]["leitos"], 2)

        exportado = im.ler_mobile(self.mobile, "2026-11-25")
        paciente = next(x for x in exportado["mapa"] if x["codigo"] == "A01")
        vazio = next(x for x in exportado["mapa"] if x["codigo"] == "A02")

        self.assertEqual(paciente["nome"], "Paciente Teste")
        self.assertEqual(paciente["idade_anos"], 72)
        self.assertEqual(paciente["consistencia"], "Pastosa")
        self.assertEqual(vazio["nome"], "")
        self.assertEqual(vazio["ocupado"], 0)

    def test_proposta_da_copa_e_aprovacao_sem_celular(self):
        """Uma alteração de perfil Copa percorre proposta -> aprovação sem dispositivo."""
        self._salvar("Paciente Original", 70)
        im.enviar_mapa(self.desktop, self.mobile, "2026-11-25")

        c = sv.conectar(self.mobile)
        try:
            sv.criar_usuario(c, "copa_teste", "Copa Teste", "copa", None, "senha123")
            c.commit()
            copa = dict(c.execute(
                "SELECT * FROM usuarios WHERE login='copa_teste'"
            ).fetchone())
            sid = c.execute(
                "SELECT id FROM setores WHERE nome='Clinica A'"
            ).fetchone()["id"]
            lid = c.execute(
                "SELECT id FROM leitos WHERE id_setor=? AND codigo='A01'",
                (sid,),
            ).fetchone()["id"]

            linhas = [{
                "id_leito": lid,
                "nome": "Paciente Corrigido",
                "idade_anos": 71,
                "idade_meses": None,
                "ocupado": 1,
                "acompanhante": 0,
                "dieta": "Pastosa",
                "diagnostico": "",
                "pref_sim": "",
                "pref_nao": "",
                "cor": "",
                "consistencia": "Pastosa",
                "via": "Oral",
                "dm": 1,
                "has": 0,
                "laxativa": 0,
                "constipante": 0,
                "drc": 0,
                "suplementos_json": "[]",
                "atualizado_em": "2026-11-25T10:00:00-03:00",
            }]
            res = sv.post_mapa(
                c, copa, {"id": sid, "nome": "Clinica A"},
                "2026-11-25", linhas
            )
            self.assertEqual(res["pendente"], 1)
            c.commit()
        finally:
            c.close()

        exportado = im.ler_mobile(self.mobile, "2026-11-25")
        propostas = im.propostas_mapa(self.desktop, exportado)

        self.assertEqual(len(propostas), 1)
        self.assertIn("nome_paciente", propostas[0]["campos"])

        aplicado = im.aplicar_mapa(
            self.desktop, propostas, mobile_db=self.mobile
        )
        self.assertEqual(aplicado, {"aplicados": 1, "erros": []})
        self.assertEqual(
            mdb.obter_registro(
                self.desktop, "2026-11-25", self.leitos["A01"]
            )["nome_paciente"],
            "Paciente Corrigido",
        )

    def test_reenvio_e_idempotencia_sem_aparelho(self):
        """Repetir o envio local simula reconexão/reenvio sem duplicar setores ou leitos."""
        self._salvar()
        im.enviar_mapa(self.desktop, self.mobile, "2026-11-25")
        im.enviar_mapa(self.desktop, self.mobile, "2026-11-25")

        with closing(sv.conectar(self.mobile)) as c:
            self.assertEqual(
                c.execute("SELECT COUNT(*) FROM setores").fetchone()[0], 1
            )
            self.assertEqual(
                c.execute("SELECT COUNT(*) FROM leitos").fetchone()[0], 2
            )
            self.assertEqual(
                c.execute("SELECT COUNT(*) FROM mapa_dia").fetchone()[0], 1
            )
            self.assertEqual(
                c.execute("SELECT COUNT(*) FROM avisos").fetchone()[0], 1
            )


if __name__ == "__main__":
    unittest.main()
