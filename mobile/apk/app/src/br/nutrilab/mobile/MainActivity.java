package br.nutrilab.mobile;

import android.app.Activity;
import android.content.Intent;
import android.content.SharedPreferences;
import android.net.Uri;
import android.os.Bundle;
import android.webkit.DownloadListener;
import android.webkit.JavascriptInterface;
import android.webkit.ValueCallback;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

import java.io.BufferedReader;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;

import org.json.JSONObject;

/**
 * NutriLab Mobile: casca Android (WebView) que abre a pagina servida pelo computador do administrador.
 * O endereco informado e conferido (tem que ser o servidor do NutriLab, porta 8765) antes de ser salvo.
 * Criado em 12/11/2026; revisado em 14/11/2026 (conferencia do endereco, links de download, endereco sugerido).
 */
public class MainActivity extends Activity {
    private static final String PORTA = "8765";

    /** A pagina do NutriLab tem o elemento #app; qualquer outra pagina (por exemplo a do download do APK) nao tem. */
    private static final String E_NUTRILAB = "(function(){return !!document.getElementById('app')})()";

    /** Acrescenta o link "Trocar servidor" na tela de login da pagina, sem alterar a pagina do servidor. */
    private static final String LINK_TROCAR =
            "(function(){function ad(){var e=document.getElementById('entrada');"
            + "if(e&&!document.getElementById('nl-srv')){var p=document.createElement('p');p.id='nl-srv';"
            + "p.style.cssText='text-align:center;margin-top:18px';"
            + "p.innerHTML='<a href=\"#\" style=\"color:#5d6b66\" onclick=\"Android.trocar();return false\">Trocar servidor</a>';"
            + "e.appendChild(p)}}ad();"
            + "if(!window.__nlObs){window.__nlObs=1;new MutationObserver(ad).observe(document.body,{childList:true,subtree:true})}})();";

    private WebView web;
    private SharedPreferences prefs;

    @Override
    protected void onCreate(Bundle estado) {
        super.onCreate(estado);
        prefs = getSharedPreferences("nutrilab", MODE_PRIVATE);
        web = new WebView(this);
        setContentView(web);
        WebSettings ajustes = web.getSettings();
        ajustes.setJavaScriptEnabled(true);
        ajustes.setDomStorageEnabled(true);
        web.addJavascriptInterface(new Ponte(), "Android");
        web.setDownloadListener(new DownloadListener() {
            @Override
            public void onDownloadStart(String url, String agente, String disposicao, String tipo, long tamanho) {
                startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(url))); // deixa o navegador do celular baixar
            }
        });
        web.setWebViewClient(new WebViewClient() {
            @Override
            public void onReceivedError(WebView v, WebResourceRequest pedido, WebResourceError erro) {
                if (pedido.isForMainFrame()) {
                    v.loadUrl("file:///android_asset/erro.html?motivo=conexao");
                }
            }

            @Override
            public void onPageFinished(final WebView v, String url) {
                if (url == null || !url.startsWith("http")) {
                    return; // paginas locais do aplicativo (config e erro)
                }
                v.evaluateJavascript(E_NUTRILAB, new ValueCallback<String>() {
                    @Override
                    public void onReceiveValue(String ehNutriLab) {
                        if ("true".equals(ehNutriLab)) {
                            v.evaluateJavascript(LINK_TROCAR, null);
                        } else {
                            v.loadUrl("file:///android_asset/erro.html?motivo=outro");
                        }
                    }
                });
            }
        });
        abrir();
    }

    private void abrir() {
        String url = prefs.getString("servidor", "");
        web.loadUrl(url.isEmpty() ? "file:///android_asset/config.html" : url);
    }

    @Override
    public void onBackPressed() {
        if (web.canGoBack()) {
            web.goBack();
        } else {
            super.onBackPressed();
        }
    }

    /** "192.168.0.10" vira "http://192.168.0.10:8765"; sem porta, usa a do servidor do NutriLab. */
    private static String normalizar(String texto) {
        String e = texto == null ? "" : texto.trim();
        if (e.isEmpty()) {
            return "";
        }
        if (!e.startsWith("http://") && !e.startsWith("https://")) {
            e = "http://" + e;
        }
        while (e.endsWith("/")) {
            e = e.substring(0, e.length() - 1);
        }
        String semEsquema = e.substring(e.indexOf("//") + 2);
        if (semEsquema.indexOf(':') < 0 && semEsquema.indexOf('/') < 0) {
            e = e + ":" + PORTA;
        }
        return e;
    }

    /** Confere se o endereco e o servidor do NutriLab: GET /api/eu sem login devolve 401 com {"erro": ...}. */
    private String testar(String url) {
        HttpURLConnection c = null;
        try {
            c = (HttpURLConnection) new URL(url + "/api/eu").openConnection();
            c.setConnectTimeout(5000);
            c.setReadTimeout(5000);
            int codigo = c.getResponseCode();
            InputStream in = codigo >= 400 ? c.getErrorStream() : c.getInputStream();
            StringBuilder corpo = new StringBuilder();
            if (in != null) {
                BufferedReader leitor = new BufferedReader(new InputStreamReader(in, "UTF-8"));
                String linha;
                while ((linha = leitor.readLine()) != null && corpo.length() < 2000) {
                    corpo.append(linha);
                }
                leitor.close();
            }
            if (codigo == 401 && corpo.indexOf("\"erro\"") >= 0) {
                return null;
            }
            return "Esse endereço respondeu, mas não é o servidor do NutriLab. Use o endereço com a porta "
                    + PORTA + " (a porta 8000 serve só para baixar o aplicativo).";
        } catch (Exception e) {
            return "Não consegui conectar em " + url + ". Confira: celular no mesmo Wi-Fi do computador, servidor ligado "
                    + "(mobile\\iniciar_servidor.bat) e Firewall do Windows liberando a porta " + PORTA + ".";
        } finally {
            if (c != null) {
                c.disconnect();
            }
        }
    }

    /** Mostra uma mensagem na pagina de configuracao (config.html). */
    private void avisar(final String texto) {
        runOnUiThread(new Runnable() {
            @Override
            public void run() {
                web.evaluateJavascript("window.resultado&&window.resultado(" + JSONObject.quote(texto) + ")", null);
            }
        });
    }

    /** Ponte entre as paginas locais (config e erro) e o aplicativo. */
    public class Ponte {
        @JavascriptInterface
        public String servidor() {
            return prefs.getString("servidor", "");
        }

        /** Endereco deste computador na rede, gravado pelo Gerar_APK.bat (pode nao existir). */
        @JavascriptInterface
        public String sugestao() {
            try {
                BufferedReader leitor = new BufferedReader(new InputStreamReader(getAssets().open("servidor.txt"), "UTF-8"));
                String linha = leitor.readLine();
                leitor.close();
                return linha == null ? "" : linha.trim();
            } catch (Exception e) {
                return "";
            }
        }

        @JavascriptInterface
        public void salvar(String endereco) {
            final String url = normalizar(endereco);
            if (url.isEmpty()) {
                avisar("Digite o endereço do servidor.");
                return;
            }
            new Thread(new Runnable() {
                @Override
                public void run() {
                    final String problema = testar(url);
                    runOnUiThread(new Runnable() {
                        @Override
                        public void run() {
                            if (problema == null) {
                                prefs.edit().putString("servidor", url).apply();
                                abrir();
                            } else {
                                avisar(problema);
                            }
                        }
                    });
                }
            }).start();
        }

        @JavascriptInterface
        public void trocar() {
            prefs.edit().remove("servidor").apply();
            recarregar();
        }

        @JavascriptInterface
        public void tentarDeNovo() {
            recarregar();
        }

        private void recarregar() {
            runOnUiThread(new Runnable() {
                @Override
                public void run() {
                    abrir();
                }
            });
        }
    }
}
