package br.nutrilab.mobile;

import android.Manifest;
import android.app.Activity;
import android.content.Intent;
import android.database.Cursor;
import android.content.pm.PackageManager;
import android.content.SharedPreferences;
import android.net.Uri;
import android.net.DhcpInfo;
import android.net.wifi.WifiManager;
import android.content.Context;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.util.Base64;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import android.webkit.DownloadListener;
import android.webkit.JavascriptInterface;
import android.webkit.PermissionRequest;
import android.webkit.WebChromeClient;
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
import java.net.DatagramPacket;
import java.net.DatagramSocket;
import java.net.InetAddress;
import java.net.SocketTimeoutException;
import java.security.KeyStore;
import java.security.MessageDigest;
import java.util.concurrent.atomic.AtomicBoolean;
import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;

import org.json.JSONObject;

/**
 * NutriLab Mobile: casca Android (WebView) que abre a pagina servida pelo computador do administrador.
 * O endereco informado e conferido (tem que ser o servidor do NutriLab, porta 8765) antes de ser salvo.
 * Criado em 12/11/2026; revisado em 14/11/2026 (conferencia do endereco, links de download, endereco sugerido).
 */
public class MainActivity extends Activity {
    private static final String PORTA = "8765";
    private static final int PORTA_DESCOBERTA = 8766;
    private static final int PEDIR_CAMERA = 4102;
    private static final int ESCOLHER_IMAGEM_QR = 4103;
    private static final int ESCANEAR_QR = 4104;
    private static final int PEDIR_CAMERA_SCANNER = 4105;
    private static final int PEDIR_NOTIFICACAO = 4106;

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
    private volatile boolean offlineMode = false;
    private final AtomicBoolean descobertaEmAndamento = new AtomicBoolean(false);
    private final Handler handlerDescoberta = new Handler(Looper.getMainLooper());
    private final Runnable tentarRedescobrir = new Runnable() {
        @Override public void run() {
            if (!offlineMode) return;
            descobrirServidor(true);
            handlerDescoberta.postDelayed(this, 15000);
        }
    };
    private PermissionRequest pedidoCamera;
    private ValueCallback<Uri[]> retornoArquivo;
    private boolean abrirScannerPendente = false;
    private boolean instaladorAcionadoNestaSessao = false;
    private final AtomicBoolean verificacaoAtualizacaoEmAndamento = new AtomicBoolean(false);
    private final Handler handlerAtualizacao = new Handler(Looper.getMainLooper());
    private android.app.AlertDialog dialogDownload;
    private android.widget.ProgressBar barraDownload;
    private android.widget.TextView textoDownload;
    private Runnable atualizarProgressoDownload;

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
        web.setWebChromeClient(new WebChromeClient() {
            @Override
            public void onPermissionRequest(final PermissionRequest pedido) {
                runOnUiThread(new Runnable() {
                    @Override public void run() {
                        boolean camera = false;
                        for (String recurso : pedido.getResources()) {
                            if (PermissionRequest.RESOURCE_VIDEO_CAPTURE.equals(recurso)) camera = true;
                        }
                        if (!camera) { pedido.deny(); return; }
                        pedidoCamera = pedido;
                        if (checkSelfPermission(Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED) {
                            pedido.grant(new String[]{PermissionRequest.RESOURCE_VIDEO_CAPTURE});
                            pedidoCamera = null;
                        } else {
                            requestPermissions(new String[]{Manifest.permission.CAMERA}, PEDIR_CAMERA);
                        }
                    }
                });
            }

            @Override
            public boolean onShowFileChooser(WebView view, ValueCallback<Uri[]> callback,
                                             FileChooserParams parametros) {
                if (retornoArquivo != null) retornoArquivo.onReceiveValue(null);
                retornoArquivo = callback;
                try {
                    startActivityForResult(parametros.createIntent(), ESCOLHER_IMAGEM_QR);
                    return true;
                } catch (Exception e) {
                    retornoArquivo = null;
                    callback.onReceiveValue(null);
                    return false;
                }
            }
        });
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
                    abrirOffline();
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
        atualizarIdentidadeServidorSalvo();
        retomarDownloadPendente();
        verificarAtualizacaoNoServidor();
    }

    private static final String APK_ASSET = "NutriLab-Mobile.apk";
    private static final String PREF_DOWNLOAD_ID = "update_apk_download_id";
    private static final String PREF_DOWNLOAD_CODE = "update_apk_version_code";
    private static final String PREF_DOWNLOAD_NAME = "update_apk_version_name";
    private static final String PREF_DOWNLOAD_SHA = "update_apk_sha256";
    private static final String PREF_DOWNLOAD_URL = "update_apk_url";
    private static final String PREF_UPDATE_CHECK = "update_apk_last_check";

    /** Consulta a versão do APK no servidor já vinculado ao aparelho, sem usar releases externas. */
    private void verificarAtualizacaoNoServidor() {
        if (prefs == null || !verificacaoAtualizacaoEmAndamento.compareAndSet(false, true)) return;
        final String base = prefs.getString("servidor", "");
        if (base == null || base.isEmpty()) {
            verificacaoAtualizacaoEmAndamento.set(false);
            return;
        }
        long agora = System.currentTimeMillis();
        if (agora - prefs.getLong(PREF_UPDATE_CHECK, 0L) < 60000L) {
            verificacaoAtualizacaoEmAndamento.set(false);
            return;
        }
        new Thread(new Runnable() {
            @Override public void run() {
                HttpURLConnection c = null;
                try {
                    String identidadeSalva = prefs.getString("server_identity", "");
                    String identidadeAtual = obterIdentidade(base);
                    if (!identidadeSalva.isEmpty() && !identidadeSalva.equals(identidadeAtual)) {
                        throw new Exception("O servidor respondeu com uma identidade diferente da vinculada ao aparelho.");
                    }
                    c = (HttpURLConnection) new URL(base + "/api/mobile/update").openConnection();
                    c.setConnectTimeout(5000);
                    c.setReadTimeout(10000);
                    c.setRequestProperty("Accept", "application/json");
                    if (c.getResponseCode() != 200) throw new Exception("Servidor HTTP " + c.getResponseCode());
                    BufferedReader br = new BufferedReader(new InputStreamReader(c.getInputStream(), "UTF-8"));
                    StringBuilder body = new StringBuilder();
                    String line;
                    while ((line = br.readLine()) != null && body.length() < 12000) body.append(line);
                    br.close();
                    JSONObject dados = new JSONObject(body.toString());
                    prefs.edit().putLong(PREF_UPDATE_CHECK, System.currentTimeMillis()).apply();
                    if (!dados.optBoolean("disponivel", false)) return;
                    long codigoRemoto = dados.optLong("version_code", 0L);
                    String nomeRemoto = dados.optString("version_name", "");
                    String sha = dados.optString("sha256", "");
                    String caminho = dados.optString("download_url", "");
                    if (codigoRemoto <= 0 || nomeRemoto.isEmpty() || sha.length() != 64
                            || !caminho.equals("/download/NutriLab-Mobile.apk")) {
                        throw new Exception("O servidor enviou metadados de atualização inválidos.");
                    }
                    long codigoInstalado = getPackageManager().getPackageInfo(getPackageName(), 0).versionCode;
                    if (codigoRemoto > codigoInstalado) {
                        final String url = base + caminho;
                        final String nome = nomeRemoto;
                        final long codigo = codigoRemoto;
                        final String hash = sha;
                        runOnUiThread(new Runnable() {
                            @Override public void run() {
                                iniciarDownloadAutomatico(url, nome, codigo, hash);
                            }
                        });
                    } else {
                        limparDownloadSeJaInstalado(codigoInstalado);
                    }
                } catch (Exception e) {
                    android.util.Log.w("NutriLabUpdate", "Não foi possível consultar atualização no servidor", e);
                } finally {
                    if (c != null) c.disconnect();
                    verificacaoAtualizacaoEmAndamento.set(false);
                }
            }
        }, "nutrilab-server-update-check").start();
    }

    private void iniciarDownloadAutomatico(String url, String versao, long codigo, String sha256) {
        if (android.os.Build.VERSION.SDK_INT >= 33
                && checkSelfPermission("android.permission.POST_NOTIFICATIONS") != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{"android.permission.POST_NOTIFICATIONS"}, PEDIR_NOTIFICACAO);
        }
        long existente = prefs.getLong(PREF_DOWNLOAD_ID, -1L);
        if (existente >= 0) {
            long codigoExistente = prefs.getLong(PREF_DOWNLOAD_CODE, -1L);
            Cursor pendente = consultarDownload(existente);
            if (pendente != null && codigoExistente >= codigo) {
                pendente.close();
                retomarDownloadPendente();
                return;
            }
            if (pendente != null) pendente.close();
            limparRegistroDownload(true);
        }
        try {
            android.app.DownloadManager dm = (android.app.DownloadManager) getSystemService(DOWNLOAD_SERVICE);
            android.app.DownloadManager.Request req = new android.app.DownloadManager.Request(Uri.parse(url));
            req.setTitle("Atualização do NutriLab Mobile " + versao);
            req.setDescription("Baixando automaticamente do servidor vinculado");
            req.setMimeType("application/vnd.android.package-archive");
            req.setNotificationVisibility(android.app.DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED);
            req.setAllowedOverMetered(true);
            req.setAllowedOverRoaming(false);
            req.setDestinationInExternalFilesDir(this, android.os.Environment.DIRECTORY_DOWNLOADS,
                    "NutriLab-Mobile-" + codigo + ".apk");
            long id = dm.enqueue(req);
            boolean registroSalvo = prefs.edit().putLong(PREF_DOWNLOAD_ID, id)
                    .putLong(PREF_DOWNLOAD_CODE, codigo)
                    .putString(PREF_DOWNLOAD_NAME, versao)
                    .putString(PREF_DOWNLOAD_SHA, sha256)
                    .putString(PREF_DOWNLOAD_URL, url).commit();
            if (!registroSalvo) {
                dm.remove(id);
                throw new Exception("Não foi possível persistir o identificador do download para retomada.");
            }
            mostrarProgressoDownload(id);
        } catch (Exception e) {
            android.util.Log.e("NutriLabUpdate", "Falha ao iniciar download", e);
            avisar("Não foi possível iniciar a atualização. O NutriLab continuará funcionando com a versão instalada.");
        }
    }

    /** Retorna o status do DownloadManager; null indica que o registro não existe mais. */
    private android.database.Cursor consultarDownload(long id) {
        try {
            android.app.DownloadManager dm = (android.app.DownloadManager) getSystemService(DOWNLOAD_SERVICE);
            android.database.Cursor c = dm.query(new android.app.DownloadManager.Query().setFilterById(id));
            if (c != null && c.moveToFirst()) return c;
            if (c != null) c.close();
        } catch (Exception e) {
            android.util.Log.w("NutriLabUpdate", "Não foi possível consultar download pendente", e);
        }
        return null;
    }

    /** DownloadManager mantém o trabalho mesmo após o processo do NutriLab ser encerrado. */
    private void retomarDownloadPendente() {
        long id = prefs == null ? -1L : prefs.getLong(PREF_DOWNLOAD_ID, -1L);
        if (id < 0) return;
        Cursor c = consultarDownload(id);
        if (c == null) {
            limparRegistroDownload(false);
            prefs.edit().remove(PREF_UPDATE_CHECK).apply();
            return;
        }
        int status = c.getInt(c.getColumnIndexOrThrow(android.app.DownloadManager.COLUMN_STATUS));
        c.close();
        if (status == android.app.DownloadManager.STATUS_SUCCESSFUL) {
            long codigoBaixado = prefs.getLong(PREF_DOWNLOAD_CODE, -1L);
            try {
                long codigoInstalado = getPackageManager().getPackageInfo(getPackageName(), 0).versionCode;
                if (codigoBaixado > 0 && codigoInstalado >= codigoBaixado) {
                    limparRegistroDownload(true);
                    return;
                }
            } catch (Exception e) {
                android.util.Log.w("NutriLabUpdate", "Não foi possível comparar a versão instalada", e);
            }
            instalarDownloadConcluido(id);
        } else if (status == android.app.DownloadManager.STATUS_FAILED) {
            // Falha de transporte não equivale a bloqueio da instalação; o servidor será consultado novamente.
            limparRegistroDownload(true);
            prefs.edit().remove(PREF_UPDATE_CHECK).apply();
            verificarAtualizacaoNoServidor();
        } else {
            mostrarProgressoDownload(id);
        }
    }

    private void mostrarProgressoDownload(final long id) {
        if (isFinishing() || isDestroyed()) return;
        if (dialogDownload != null && dialogDownload.isShowing()) return;
        android.widget.LinearLayout painel = new android.widget.LinearLayout(this);
        painel.setOrientation(android.widget.LinearLayout.VERTICAL);
        painel.setPadding(48, 28, 48, 12);
        textoDownload = new android.widget.TextView(this);
        textoDownload.setText("Preparando download…");
        painel.addView(textoDownload);
        barraDownload = new android.widget.ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
        barraDownload.setMax(1000);
        android.widget.LinearLayout.LayoutParams lp = new android.widget.LinearLayout.LayoutParams(
                android.widget.LinearLayout.LayoutParams.MATCH_PARENT, android.widget.LinearLayout.LayoutParams.WRAP_CONTENT);
        lp.topMargin = 18;
        painel.addView(barraDownload, lp);
        dialogDownload = new android.app.AlertDialog.Builder(this)
                .setTitle("Atualização do NutriLab Mobile")
                .setMessage("O download continua em segundo plano se você fechar o aplicativo.")
                .setView(painel)
                .setNegativeButton("Continuar em segundo plano", (d, w) -> d.dismiss())
                .create();
        dialogDownload.setOnDismissListener(d -> {
            handlerAtualizacao.removeCallbacks(atualizarProgressoDownload);
            dialogDownload = null;
        });
        dialogDownload.show();
        atualizarProgressoDownload = new Runnable() {
            @Override public void run() {
                Cursor c = consultarDownload(id);
                if (c == null) {
                    if (dialogDownload != null) dialogDownload.dismiss();
                    return;
                }
                int status = c.getInt(c.getColumnIndexOrThrow(android.app.DownloadManager.COLUMN_STATUS));
                long recebido = c.getLong(c.getColumnIndexOrThrow(android.app.DownloadManager.COLUMN_BYTES_DOWNLOADED_SO_FAR));
                long total = c.getLong(c.getColumnIndexOrThrow(android.app.DownloadManager.COLUMN_TOTAL_SIZE_BYTES));
                c.close();
                if (barraDownload != null) {
                    int progresso = total > 0 ? (int) Math.min(1000, recebido * 1000L / total) : 0;
                    barraDownload.setIndeterminate(total <= 0);
                    if (total > 0) barraDownload.setProgress(progresso);
                }
                if (textoDownload != null) {
                    textoDownload.setText(total > 0
                            ? android.text.format.Formatter.formatShortFileSize(MainActivity.this, recebido)
                                + " de " + android.text.format.Formatter.formatShortFileSize(MainActivity.this, total)
                            : "Aguardando dados do servidor…");
                }
                if (status == android.app.DownloadManager.STATUS_SUCCESSFUL) {
                    if (dialogDownload != null) dialogDownload.dismiss();
                    instalarDownloadConcluido(id);
                    return;
                }
                if (status == android.app.DownloadManager.STATUS_FAILED) {
                    if (dialogDownload != null) dialogDownload.dismiss();
                    limparRegistroDownload(true);
                    avisar("O download da atualização falhou. Ao reconectar ao servidor, o NutriLab tentará novamente.");
                    return;
                }
                handlerAtualizacao.postDelayed(this, 500);
            }
        };
        handlerAtualizacao.post(atualizarProgressoDownload);
    }

    private boolean validarHashDownload(long id) {
        String esperado = prefs.getString(PREF_DOWNLOAD_SHA, "");
        if (esperado.length() != 64) return false;
        try {
            android.app.DownloadManager dm = (android.app.DownloadManager) getSystemService(DOWNLOAD_SERVICE);
            android.os.ParcelFileDescriptor descritor = dm.openDownloadedFile(id);
            if (descritor == null) return false;
            InputStream in = new android.os.ParcelFileDescriptor.AutoCloseInputStream(descritor);
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] buffer = new byte[65536];
            int n;
            while ((n = in.read(buffer)) > 0) digest.update(buffer, 0, n);
            in.close();
            StringBuilder hex = new StringBuilder();
            for (byte v : digest.digest()) hex.append(String.format(java.util.Locale.ROOT, "%02x", v & 0xff));
            return esperado.equalsIgnoreCase(hex.toString());
        } catch (Exception e) {
            android.util.Log.e("NutriLabUpdate", "Falha ao validar APK baixado", e);
            return false;
        }
    }

    private void instalarDownloadConcluido(long id) {
        if (instaladorAcionadoNestaSessao) return;
        if (!validarHashDownload(id)) {
            android.util.Log.e("NutriLabUpdate", "Hash do APK baixado não confere; descartando arquivo incompleto.");
            limparRegistroDownload(true);
            prefs.edit().remove(PREF_UPDATE_CHECK).apply();
            verificarAtualizacaoNoServidor();
            return;
        }
        if (android.os.Build.VERSION.SDK_INT >= 26 && !getPackageManager().canRequestPackageInstalls()) {
            new android.app.AlertDialog.Builder(this)
                    .setTitle("Permitir instalação da atualização")
                    .setMessage("O APK foi baixado e validado. Para instalar, permita que o NutriLab solicite a instalação desta atualização nas configurações do Android. O arquivo permanecerá salvo; não será necessário baixá-lo novamente.")
                    .setNegativeButton("Agora não", null)
                    .setPositiveButton("Abrir configuração", (d, w) -> {
                        Intent intent = new Intent(android.provider.Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
                                Uri.parse("package:" + getPackageName()));
                        startActivity(intent);
                    }).show();
            return;
        }
        try {
            android.app.DownloadManager dm = (android.app.DownloadManager) getSystemService(DOWNLOAD_SERVICE);
            Uri uri = dm.getUriForDownloadedFile(id);
            if (uri == null) throw new Exception("O Android não disponibilizou o arquivo baixado.");
            Intent instalar = new Intent(Intent.ACTION_VIEW);
            instalar.setDataAndType(uri, "application/vnd.android.package-archive");
            instalar.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_ACTIVITY_NEW_TASK);
            instaladorAcionadoNestaSessao = true;
            startActivity(instalar);
        } catch (Exception e) {
            instaladorAcionadoNestaSessao = false;
            android.util.Log.e("NutriLabUpdate", "Não foi possível abrir o instalador", e);
            avisar("O APK está salvo no aparelho, mas o Android não abriu o instalador. Abra o NutriLab novamente para tentar instalar sem novo download.");
        }
    }

    private void limparDownloadSeJaInstalado(long codigoInstalado) {
        long codigoBaixado = prefs.getLong(PREF_DOWNLOAD_CODE, -1L);
        if (codigoBaixado > 0 && codigoInstalado >= codigoBaixado) limparRegistroDownload(true);
    }

    private void limparRegistroDownload(boolean removerArquivo) {
        long id = prefs.getLong(PREF_DOWNLOAD_ID, -1L);
        if (removerArquivo && id >= 0) {
            try {
                android.app.DownloadManager dm = (android.app.DownloadManager) getSystemService(DOWNLOAD_SERVICE);
                dm.remove(id);
            } catch (Exception e) {
                android.util.Log.w("NutriLabUpdate", "Falha ao limpar registro do APK", e);
            }
        }
        prefs.edit().remove(PREF_DOWNLOAD_ID).remove(PREF_DOWNLOAD_CODE).remove(PREF_DOWNLOAD_NAME)
                .remove(PREF_DOWNLOAD_SHA).remove(PREF_DOWNLOAD_URL).apply();
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (prefs != null) {
            retomarDownloadPendente();
            verificarAtualizacaoNoServidor();
        }
    }

    private void abrir() {
        offlineMode = false;
        handlerDescoberta.removeCallbacks(tentarRedescobrir);
        String url = prefs.getString("servidor", "");
        web.loadUrl(url.isEmpty() ? "file:///android_asset/config.html" : url);
        if (!url.isEmpty()) {
            handlerAtualizacao.postDelayed(new Runnable() {
                @Override public void run() { verificarAtualizacaoNoServidor(); }
            }, 1200);
        }
    }

    /** Carrega uma cópia local da interface mantendo a origem do servidor para as chamadas /api. */
    private void abrirOffline() {
        String servidor = prefs.getString("servidor", "");
        if (servidor.isEmpty()) {
            offlineMode = false;
            handlerDescoberta.removeCallbacks(tentarRedescobrir);
            web.loadUrl("file:///android_asset/config.html");
            return;
        }
        try {
            InputStream in = getAssets().open("index.html");
            BufferedReader leitor = new BufferedReader(new InputStreamReader(in, "UTF-8"));
            StringBuilder html = new StringBuilder();
            String linha;
            while ((linha = leitor.readLine()) != null) {
                html.append(linha).append("\n");
            }
            leitor.close();
            // O servidor pode estar offline: injeta o decodificador QR local no HTML de contingência.
            InputStream qrIn = getAssets().open("jsQR.js");
            BufferedReader qrLeitor = new BufferedReader(new InputStreamReader(qrIn, "UTF-8"));
            StringBuilder qrCodigo = new StringBuilder();
            while ((linha = qrLeitor.readLine()) != null) qrCodigo.append(linha).append("\n");
            qrLeitor.close();
            String referenciaQr = "<script src=\"/static/jsQR.js\"></script>";
            int posQr = html.indexOf(referenciaQr);
            if (posQr >= 0) {
                html.replace(posQr, posQr + referenciaQr.length(),
                        "<script>" + qrCodigo.toString() + "</script>");
            }
            offlineMode = true;
            web.loadDataWithBaseURL(servidor + "/", html.toString(), "text/html", "UTF-8", null);
            if (!prefs.getString("server_identity", "").isEmpty()) {
                handlerDescoberta.removeCallbacks(tentarRedescobrir);
                handlerDescoberta.postDelayed(tentarRedescobrir, 1200);
            }
        } catch (Exception e) {
            offlineMode = true;
            web.loadUrl("file:///android_asset/erro.html?motivo=conexao");
            if (!prefs.getString("server_identity", "").isEmpty()) {
                handlerDescoberta.removeCallbacks(tentarRedescobrir);
                handlerDescoberta.postDelayed(tentarRedescobrir, 15000);
            }
        }
    }


    @Override
    public void onRequestPermissionsResult(int codigo, String[] permissoes, int[] resultados) {
        super.onRequestPermissionsResult(codigo, permissoes, resultados);
        boolean concedida = resultados.length > 0 && resultados[0] == PackageManager.PERMISSION_GRANTED;
        if (codigo == PEDIR_CAMERA && pedidoCamera != null) {
            if (concedida) pedidoCamera.grant(new String[]{PermissionRequest.RESOURCE_VIDEO_CAPTURE});
            else pedidoCamera.deny();
            pedidoCamera = null;
        }
        if (codigo == PEDIR_CAMERA_SCANNER && abrirScannerPendente) {
            abrirScannerPendente = false;
            if (concedida) {
                startActivityForResult(new Intent(MainActivity.this, QRScannerActivity.class), ESCANEAR_QR);
            } else {
                avisar("A câmera é necessária para escanear o QR code. Você também pode informar o endereço manualmente.");
            }
        }
    }

    private void abrirScannerQR() {
        if (checkSelfPermission(Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED) {
            startActivityForResult(new Intent(this, QRScannerActivity.class), ESCANEAR_QR);
        } else {
            abrirScannerPendente = true;
            requestPermissions(new String[]{Manifest.permission.CAMERA}, PEDIR_CAMERA_SCANNER);
        }
    }

    @Override
    protected void onActivityResult(int codigo, int resultado, Intent dados) {
        super.onActivityResult(codigo, resultado, dados);
        if (codigo == ESCANEAR_QR) {
            if (resultado == RESULT_OK && dados != null && web != null) {
                String texto = dados.getStringExtra("qr_result");
                if (texto != null) {
                    web.evaluateJavascript("if(typeof aplicarConteudoQR==='function')aplicarConteudoQR("
                            + JSONObject.quote(texto) + ")", null);
                }
            }
            return;
        }
        if (codigo == ESCOLHER_IMAGEM_QR && retornoArquivo != null) {
            retornoArquivo.onReceiveValue(WebChromeClient.FileChooserParams.parseResult(resultado, dados));
            retornoArquivo = null;
        }
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

    /** Atualiza a identidade vinculada quando o endereço salvo ainda responde. */
    private void atualizarIdentidadeServidorSalvo() {
        new Thread(new Runnable() {
            @Override public void run() {
                String url = prefs.getString("servidor", "");
                if (url.isEmpty()) return;
                String identidade = obterIdentidade(url);
                // O endereço salvo pode ter sido reutilizado por outro computador.
                // Nunca substitua silenciosamente uma identidade já vinculada:
                // a troca de servidor exige uma nova associação explícita no aparelho.
                if (!identidade.isEmpty() && prefs.getString("server_identity", "").isEmpty()) {
                    prefs.edit().putString("server_identity", identidade).apply();
                }
            }
        }, "nutrilab-server-identity").start();
    }

    /** Consulta o identificador estável do servidor; não é credencial de acesso. */
    private String obterIdentidade(String url) {
        HttpURLConnection c = null;
        try {
            c = (HttpURLConnection) new URL(url + "/api/status").openConnection();
            c.setConnectTimeout(2500);
            c.setReadTimeout(2500);
            if (c.getResponseCode() != 200) return "";
            BufferedReader leitor = new BufferedReader(new InputStreamReader(c.getInputStream(), "UTF-8"));
            StringBuilder corpo = new StringBuilder();
            String linha;
            while ((linha = leitor.readLine()) != null && corpo.length() < 4000) corpo.append(linha);
            leitor.close();
            return new JSONObject(corpo.toString()).optString("server_id", "");
        } catch (Exception e) {
            return "";
        } finally {
            if (c != null) c.disconnect();
        }
    }

    private InetAddress enderecoBroadcast() throws Exception {
        try {
            WifiManager wifi = (WifiManager) getApplicationContext().getSystemService(Context.WIFI_SERVICE);
            DhcpInfo dhcp = wifi == null ? null : wifi.getDhcpInfo();
            if (dhcp != null && dhcp.ipAddress != 0 && dhcp.netmask != 0) {
                int broadcast = (dhcp.ipAddress & dhcp.netmask) | ~dhcp.netmask;
                byte[] bytes = new byte[] {
                    (byte) (broadcast & 0xff), (byte) ((broadcast >> 8) & 0xff),
                    (byte) ((broadcast >> 16) & 0xff), (byte) ((broadcast >> 24) & 0xff)
                };
                return InetAddress.getByAddress(bytes);
            }
        } catch (Exception e) {
            android.util.Log.w("NutriLabDiscovery", "Não foi possível calcular o broadcast Wi-Fi", e);
        }
        return InetAddress.getByName("255.255.255.255");
    }

    /** Localiza o servidor por broadcast, mas só aceita o servidor já vinculado neste aparelho. */
    private void descobrirServidor() {
        descobrirServidor(false);
    }

    /** Tenta localizar o servidor vinculado; no modo offline repete sem interromper o usuário. */
    private void descobrirServidor(final boolean silencioso) {
        if (!descobertaEmAndamento.compareAndSet(false, true)) return;
        new Thread(new Runnable() {
            @Override public void run() {
                DatagramSocket socket = null;
                try {
                    String identidadeSalva = prefs.getString("server_identity", "");
                    if (identidadeSalva.isEmpty()) {
                        if (!silencioso) avisar("Este aparelho ainda não possui vínculo com um servidor. Faça a primeira conexão pelo QR code ou endereço fornecido pelo administrador.");
                        return;
                    }
                    socket = new DatagramSocket();
                    socket.setBroadcast(true);
                    socket.setSoTimeout(900);
                    byte[] pedido = "NUTRILAB_DISCOVER_V1".getBytes("UTF-8");
                    DatagramPacket envio = new DatagramPacket(pedido, pedido.length,
                            enderecoBroadcast(), PORTA_DESCOBERTA);
                    socket.send(envio);
                    byte[] buffer = new byte[512];
                    for (int tentativa = 0; tentativa < 4; tentativa++) {
                        DatagramPacket resposta = new DatagramPacket(buffer, buffer.length);
                        try {
                            socket.receive(resposta);
                        } catch (SocketTimeoutException timeout) {
                            break;
                        }
                        String texto = new String(resposta.getData(), 0, resposta.getLength(), "UTF-8");
                        String[] partes = texto.split("\\|", 3);
                        if (partes.length != 3 || !"NUTRILAB_SERVER_V1".equals(partes[0])
                                || !identidadeSalva.equals(partes[2])) continue;
                        final String url = normalizar(partes[1]);
                        if (url.isEmpty() || testar(url) != null) continue;
                        String identidadeAtual = obterIdentidade(url);
                        if (!identidadeSalva.equals(identidadeAtual)) continue;
                        if (silencioso && !offlineMode) return;
                        runOnUiThread(new Runnable() {
                            @Override public void run() {
                                prefs.edit().putString("servidor", url).apply();
                                offlineMode = false;
                                handlerDescoberta.removeCallbacks(tentarRedescobrir);
                                abrir();
                            }
                        });
                        return;
                    }
                    if (!silencioso) avisar("Não encontrei o servidor vinculado nesta rede. Confira se o computador da clínica está ligado e se o celular está no Wi-Fi correto.");
                } catch (Exception e) {
                    if (!silencioso) avisar("Não foi possível procurar o servidor nesta rede. Confira a conexão Wi-Fi e tente novamente.");
                    android.util.Log.w("NutriLabDiscovery", "Falha na descoberta local", e);
                } finally {
                    if (socket != null) socket.close();
                    descobertaEmAndamento.set(false);
                }
            }
        }, "nutrilab-server-discovery").start();
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
        private static final String CACHE_PREFIX = "cache:";
        private static final String CACHE_ALIAS = "NutriLabOfflineCache";

        private SecretKey chaveCache() throws Exception {
            KeyStore ks = KeyStore.getInstance("AndroidKeyStore");
            ks.load(null);
            if (!ks.containsAlias(CACHE_ALIAS)) {
                KeyGenerator gerador = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore");
                gerador.init(new KeyGenParameterSpec.Builder(CACHE_ALIAS,
                        KeyProperties.PURPOSE_ENCRYPT | KeyProperties.PURPOSE_DECRYPT)
                        .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                        .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                        .setRandomizedEncryptionRequired(true).build());
                gerador.generateKey();
            }
            return (SecretKey) ks.getKey(CACHE_ALIAS, null);
        }

        @JavascriptInterface
        public String cacheGet(String chave) {
            try {
                String valor = prefs.getString(CACHE_PREFIX + chave, "");
                if (valor.isEmpty()) return "";
                String[] partes = valor.split(":", 2);
                if (partes.length != 2) return "";
                byte[] iv = Base64.decode(partes[0], Base64.NO_WRAP);
                byte[] cifrado = Base64.decode(partes[1], Base64.NO_WRAP);
                Cipher cifra = Cipher.getInstance("AES/GCM/NoPadding");
                cifra.init(Cipher.DECRYPT_MODE, chaveCache(), new GCMParameterSpec(128, iv));
                return new String(cifra.doFinal(cifrado), "UTF-8");
            } catch (Exception e) {
                return "";
            }
        }

        @JavascriptInterface
        public boolean cacheSet(String chave, String texto) {
            try {
                Cipher cifra = Cipher.getInstance("AES/GCM/NoPadding");
                cifra.init(Cipher.ENCRYPT_MODE, chaveCache());
                byte[] cifrado = cifra.doFinal(texto.getBytes("UTF-8"));
                String valor = Base64.encodeToString(cifra.getIV(), Base64.NO_WRAP) + ":"
                        + Base64.encodeToString(cifrado, Base64.NO_WRAP);
                prefs.edit().putString(CACHE_PREFIX + chave, valor).apply();
                return true;
            } catch (Exception e) {
                return false;
            }
        }

        @JavascriptInterface
        public void cacheRemove(String chave) {
            prefs.edit().remove(CACHE_PREFIX + chave).apply();
        }

        @JavascriptInterface
        public void cacheClear() {
            SharedPreferences.Editor editor = prefs.edit();
            for (String chave : prefs.getAll().keySet()) {
                if (chave.startsWith(CACHE_PREFIX + "GET:") || chave.equals(CACHE_PREFIX + "queue")) {
                    editor.remove(chave);
                }
            }
            editor.apply();
        }

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
                    final String identidade = problema == null ? obterIdentidade(url) : "";
                    runOnUiThread(new Runnable() {
                        @Override
                        public void run() {
                            if (problema == null) {
                                SharedPreferences.Editor editor = prefs.edit().putString("servidor", url);
                                if (identidade.isEmpty()) editor.remove("server_identity");
                                else editor.putString("server_identity", identidade);
                                editor.apply();
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
        public void escanearQR() {
            runOnUiThread(new Runnable() {
                @Override public void run() { abrirScannerQR(); }
            });
        }

        @JavascriptInterface
        public void descobrirServidor() {
            MainActivity.this.descobrirServidor();
        }

        @JavascriptInterface
        public void descobrirServidorAutomaticamente() {
            offlineMode = true;
            MainActivity.this.descobrirServidor(true);
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

    @Override
    protected void onDestroy() {
        offlineMode = false;
        handlerDescoberta.removeCallbacks(tentarRedescobrir);
        handlerAtualizacao.removeCallbacksAndMessages(null);
        if (dialogDownload != null) {
            dialogDownload.dismiss();
            dialogDownload = null;
        }
        super.onDestroy();
    }
}
