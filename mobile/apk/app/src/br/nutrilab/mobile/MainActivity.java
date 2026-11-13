package br.nutrilab.mobile;

import android.app.Activity;
import android.content.SharedPreferences;
import android.os.Bundle;
import android.webkit.JavascriptInterface;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

/**
 * NutriLab Mobile: casca Android (WebView) que abre a pagina servida pelo computador do administrador.
 * O endereco do servidor e informado uma vez e fica salvo no aparelho. Criado em 12/11/2026.
 */
public class MainActivity extends Activity {
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
        web.setWebViewClient(new WebViewClient() {
            @Override
            public void onReceivedError(WebView v, WebResourceRequest pedido, WebResourceError erro) {
                if (pedido.isForMainFrame()) {
                    v.loadUrl("file:///android_asset/erro.html");
                }
            }

            @Override
            public void onPageFinished(WebView v, String url) {
                v.evaluateJavascript(LINK_TROCAR, null);
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

    /** Ponte entre as paginas locais (config e erro) e o aplicativo. */
    public class Ponte {
        @JavascriptInterface
        public String servidor() {
            return prefs.getString("servidor", "");
        }

        @JavascriptInterface
        public void salvar(String endereco) {
            String e = endereco == null ? "" : endereco.trim();
            if (e.isEmpty()) {
                return;
            }
            if (!e.startsWith("http://") && !e.startsWith("https://")) {
                e = "http://" + e;
            }
            while (e.endsWith("/")) {
                e = e.substring(0, e.length() - 1);
            }
            prefs.edit().putString("servidor", e).apply();
            recarregar();
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
