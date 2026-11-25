# -*- coding: utf-8 -*-
"""Compila e valida o APK Android do NutriLab em CI (JDK 17 + Android SDK 34).

O APK gerado usa uma chave efêmera de teste. Para distribuir atualizações instaláveis
sobre uma versão já instalada, use Gerar_APK.bat com a keystore privada local.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import tempfile
import urllib.request
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "mobile" / "apk" / "app"
STATIC = ROOT / "mobile" / "static" / "index.html"
JAVA_DIR = APP / "src" / "br" / "nutrilab" / "mobile"
JAVA = JAVA_DIR / "MainActivity.java"
QR_JAVA = JAVA_DIR / "QRScannerActivity.java"
ZXING_URL = "https://maven-central.storage-download.googleapis.com/maven2/com/google/zxing/core/3.5.4/core-3.5.4.jar"


def executar(comando: list[str], cwd: Path | None = None) -> None:
    print("+", " ".join(str(x) for x in comando), flush=True)
    subprocess.run([str(x) for x in comando], cwd=cwd, check=True)


def validar_apk(apk: Path, app_dir: Path) -> None:
    with zipfile.ZipFile(apk) as pacote:
        ruim = pacote.testzip()
        if ruim:
            raise RuntimeError(f"APK ZIP corrompido no membro: {ruim}")
        nomes = set(pacote.namelist())
        obrigatorios = {
            "AndroidManifest.xml", "classes.dex", "resources.arsc",
            "assets/index.html", "assets/config.html", "assets/erro.html",
            "assets/THIRD_PARTY_NOTICES.txt",
        }
        faltando = sorted(obrigatorios - nomes)
        if faltando:
            raise RuntimeError("APK sem arquivos obrigatórios: " + ", ".join(faltando))
        if pacote.read("assets/index.html") != STATIC.read_bytes():
            raise RuntimeError("A interface HTML embutida no APK está desatualizada.")
        dex = pacote.read("classes.dex")
        if b"QRScannerActivity" not in dex or b"MultiFormatReader" not in dex:
            raise RuntimeError("O APK não contém o leitor QR nativo/ZXing.");
    if apk.stat().st_size < 20_000:
        raise RuntimeError(f"APK inesperadamente pequeno: {apk.stat().st_size} bytes")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sdk", default=os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT"))
    parser.add_argument("--output", default=str(ROOT / "build" / "NutriLab-Mobile.apk"))
    parser.add_argument("--keystore", default=str(ROOT / "build" / "nutrilab-ci.keystore"))
    parser.add_argument("--version-code", type=int, default=1)
    parser.add_argument("--version-name", default="1.0-ci")
    args = parser.parse_args()
    if not args.sdk:
        parser.error("Informe --sdk ou defina ANDROID_HOME.")
    sdk = Path(args.sdk).resolve()
    tools = sdk / "build-tools" / "34.0.0"
    android_jar = sdk / "platforms" / "android-34" / "android.jar"
    for arquivo in (tools / "aapt2", tools / "aapt", tools / "d8", tools / "zipalign",
                    tools / "apksigner", android_jar):
        if not arquivo.is_file():
            raise FileNotFoundError(f"Ferramenta Android ausente: {arquivo}")
    if not JAVA.is_file() or not QR_JAVA.is_file() or not STATIC.is_file():
        raise FileNotFoundError("MainActivity.java, QRScannerActivity.java ou mobile/static/index.html ausente.")

    output = Path(args.output).resolve()
    keystore = Path(args.keystore).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    keystore.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="nutrilab-apk-build-") as tmp:
        work = Path(tmp)
        app = work / "app"
        shutil.copytree(APP, app)
        shutil.copy2(STATIC, app / "assets" / "index.html")
        zxing = work / "zxing-core-3.5.4.jar"
        print("+ download ZXing Core 3.5.4", flush=True)
        urllib.request.urlretrieve(ZXING_URL, zxing)
        if zxing.stat().st_size < 500_000:
            raise RuntimeError("O arquivo ZXing Core baixado está incompleto.")
        obj = work / "obj"
        classes = obj / "classes"
        dex = obj / "dex"
        classes.mkdir(parents=True)
        dex.mkdir(parents=True)

        executar([tools / "aapt2", "compile", "--dir", app / "res", "-o", obj / "res.zip"])
        executar([
            tools / "aapt2", "link", "-o", obj / "base.apk", "-I", android_jar,
            "--manifest", app / "AndroidManifest.xml", "-A", app / "assets",
            "--min-sdk-version", "26", "--target-sdk-version", "34",
            "--version-code", str(args.version_code), "--version-name", args.version_name,
            obj / "res.zip",
        ])
        # Não use android.jar como bootclasspath: isso esconde java.lang.invoke.LambdaMetafactory
        # do javac 17 e gera o erro reportado no Windows. API Java 8 + Android API como classpath.
        executar([
            "javac", "-encoding", "UTF-8", "--release", "8",
            "-classpath", os.pathsep.join((str(android_jar), str(zxing))),
            "-d", classes,
            app / "src" / "br" / "nutrilab" / "mobile" / "MainActivity.java",
            app / "src" / "br" / "nutrilab" / "mobile" / "QRScannerActivity.java",
        ])
        executar(["jar", "cf", obj / "classes.jar", "-C", classes, "."])
        executar([tools / "d8", "--lib", android_jar, "--min-api", "26",
                  "--output", dex, obj / "classes.jar", zxing])
        executar([tools / "aapt", "add", obj / "base.apk", "classes.dex"], cwd=dex)
        executar([tools / "zipalign", "-f", "-p", "4", obj / "base.apk", obj / "alinhado.apk"])

        if not keystore.exists():
            executar([
                "keytool", "-genkeypair", "-noprompt", "-keystore", keystore,
                "-alias", "nutrilab-ci", "-keyalg", "RSA", "-keysize", "2048",
                "-validity", "10000", "-storepass", "android", "-keypass", "android",
                "-dname", "CN=NutriLab CI, OU=Testes, O=NutriLab, C=BR",
            ])
        assinado = work / "NutriLab-Mobile.apk"
        executar([
            tools / "apksigner", "sign", "--ks", keystore, "--ks-key-alias", "nutrilab-ci",
            "--ks-pass", "pass:android", "--key-pass", "pass:android",
            "--out", assinado, obj / "alinhado.apk",
        ])
        executar([tools / "apksigner", "verify", "--verbose", "--print-certs", assinado])
        executar([tools / "aapt", "dump", "badging", assinado])
        validar_apk(assinado, app)
        shutil.copy2(assinado, output)

    validar_apk(output, APP)
    print(f"APK_VALIDADO={output} ({output.stat().st_size} bytes)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
