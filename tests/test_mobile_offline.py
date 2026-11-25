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
        self.assertIn('copy /y "%~dp0..\\static\\index.html" "%APP%\\assets\\index.html"', bat)
        release = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
        self.assertIn("setup-android@v4", release)
        self.assertIn("QRScannerActivity.java", release)
        self.assertIn("zxing-core-3.5.4.jar", release)
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
        scanner = JAVA.parent / "QRScannerActivity.java"
        self.assertTrue(scanner.is_file(), "O APK precisa do leitor QR nativo para funcionar em HTTP local.")
        java = scanner.read_text(encoding="utf-8")
        self.assertIn("MultiFormatReader", java)
        self.assertIn("Camera.open()", java)
        manifest = (ROOT / "mobile" / "apk" / "app" / "AndroidManifest.xml").read_text(encoding="utf-8")
        self.assertIn('android:name=".QRScannerActivity"', manifest)


if __name__ == "__main__":
    unittest.main()
