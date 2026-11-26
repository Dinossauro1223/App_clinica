package br.nutrilab.mobile;

import android.Manifest;
import android.app.Activity;
import android.content.Intent;
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
        verificarAtualizacao();
    }

    private static final String REPO_RELEASES = "https://api.github.com/repos/Dinossauro1223/App_clinica/releases/latest";
    private static final String APK_ASSET = "NutriLab-Mobile.apk";
    private static final String PREF_DOWNLOAD_ID = "update_apk_download_id";

    /** Consulta a release estável sem bloquear a abertura do mapa/interface. */
    private void verificarAtualizacao() {
        new Thread(new Runnable() {
            @Override public void run() {
                HttpURLConnection c = null;
                try {
                    c = (HttpURLConnection) new URL(REPO_RELEASES).openConnection();
                    c.setConnectTimeout(7000);
                    c.setReadTimeout(7000);
                    c.setRequestProperty("Accept", "application/vnd.github+json");
                    c.setRequestProperty("User-Agent", "NutriLab-Android");
                    if (c.getResponseCode() != 200) throw new Exception("GitHub HTTP " + c.getResponseCode());
                    BufferedReader br = new BufferedReader(new InputStreamReader(c.getInputStream(), "UTF-8"));
                    StringBuilder body = new StringBuilder();
                    String line;
                    while ((line = br.readLine()) != null) body.append(line);
                    br.close();
                    JSONObject release = new JSONObject(body.toString());
                    String latest = release.optString("tag_name", "").replaceFirst("^[vV]", "");
                    String installed = getPackageManager().getPackageInfo(getPackageName(), 0).versionName;
                    if (latest.isEmpty()) throw new Exception("Release sem tag de versão.");
                    if (compararVersoes(latest, installed) > 0) {
                        org.json.JSONArray assets = release.optJSONArray("assets");
                        String apkUrl = null;
                        if (assets != null) {
                            for (int i = 0; i < assets.length(); i++) {
                                JSONObject asset = assets.getJSONObject(i);
                                if (APK_ASSET.equals(asset.optString("name"))) {
                                    apkUrl = asset.optString("browser_download_url");
                                    break;
                                }
                            }
                        }
                        if (apkUrl == null || !apkUrl.startsWith("https://")) {
                            throw new Exception("A release " + latest + " ainda não contém o APK.");
                        }
                        final String url = apkUrl;
                        runOnUiThread(new Runnable() {
                            @Override public void run() { oferecerAtualizacao(installed, latest, url); }
                        });
                    } else {
                        limparDownloadsTemporarios();
                    }
                } catch (Exception e) {
                    // Falha de rede/API nunca é interpretada como "já atualizado" e nunca apaga arquivos.
                    android.util.Log.w("NutriLabUpdate", "Não foi possível verificar atualização", e);
                } finally {
                    if (c != null) c.disconnect();
                }
            }
        }, "nutrilab-update-check").start();
    }

    private int compararVersoes(String a, String b) {
        String[] aa = a.split("\\."), bb = (b == null ? "0" : b).split("\\.");
        for (int i = 0; i < Math.max(aa.length, bb.length); i++) {
            int x = i < aa.length ? numeroVersao(aa[i]) : 0;
            int y = i < bb.length ? numeroVersao(bb[i]) : 0;
            if (x != y) return x > y ? 1 : -1;
        }
        return 0;
    }

    private int numeroVersao(String s) {
        try { return Integer.parseInt(s.replaceAll("[^0-9].*$", "")); }
        catch (Exception e) { return 0; }
    }

    private void oferecerAtualizacao(String atual, String nova, final String url) {
        new android.app.AlertDialog.Builder(this)
                .setTitle("Atualização do NutriLab")
                .setMessage("Versão instalada: " + atual + "\\nNova versão: " + nova
                        + "\\n\\nDeseja baixar o APK? A instalação será confirmada pelo Android. "
                        + "Seus dados locais e a fila offline não serão apagados.")
                .setNegativeButton("Depois", null)
                .setPositiveButton("Baixar APK", (dialog, which) -> baixarApk(url, nova))
                .show();
    }

    private void baixarApk(String url, String versao) {
        try {
            android.app.DownloadManager dm = (android.app.DownloadManager) getSystemService(DOWNLOAD_SERVICE);
            android.app.DownloadManager.Request req = new android.app.DownloadManager.Request(Uri.parse(url));
            req.setTitle("NutriLab Mobile " + versao);
            req.setDescription("Baixando atualização oficial");
            req.setMimeType("application/vnd.android.package-archive");
            req.setNotificationVisibility(android.app.DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED);
            req.setDestinationInExternalFilesDir(this, android.os.Environment.DIRECTORY_DOWNLOADS,
                    "NutriLab-Mobile-" + versao + ".apk");
            long id = dm.enqueue(req);
            prefs.edit().putLong(PREF_DOWNLOAD_ID, id).apply();
            new android.app.AlertDialog.Builder(this)
                    .setTitle("Download iniciado")
                    .setMessage("O Android avisará quando o APK estiver pronto. Toque na notificação para iniciar a instalação.")
                    .setPositiveButton("OK", null).show();
        } catch (Exception e) {
            new android.app.AlertDialog.Builder(this).setTitle("Não foi possível baixar")
                    .setMessage(e.getMessage()).setPositiveButton("OK", null).show();
        }
    }

    /** Remove somente o registro/arquivo do DownloadManager criado por esta função. */
    private void limparDownloadsTemporarios() {
        long id = prefs.getLong(PREF_DOWNLOAD_ID, -1L);
        if (id >= 0) {
            try {
                android.app.DownloadManager dm = (android.app.DownloadManager) getSystemService(DOWNLOAD_SERVICE);
                dm.remove(id);
            } catch (Exception e) {
                android.util.Log.w("NutriLabUpdate", "Falha ao limpar APK temporário", e);
            }
            prefs.edit().remove(PREF_DOWNLOAD_ID).apply();
        }
    }

    private void abrir() {
        offlineMode = false;
        handlerDescoberta.removeCallbacks(tentarRedescobrir);
        String url = prefs.getString("servidor", "");
        web.loadUrl(url.isEmpty() ? "file:///android_asset/config.html" : url);
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
                if (!identidade.isEmpty()) prefs.edit().putString("server_identity", identidade).apply();
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
                        String[] partes = texto.split("\\\\|", 3);
                        if (partes.length != 3 || !"NUTRILAB_SERVER_V1".equals(partes[0])
                                || !identidadeSalva.equals(partes[2])) continue;
                        final String url = normalizar(partes[1]);
                        if (url.isEmpty() || testar(url) != null) continue;
                        String identidadeAtual = obterIdentidade(url);
                        if (!identidadeSalva.equals(identidadeAtual)) continue;
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
