package br.nutrilab.mobile;

import android.Manifest;
import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.content.pm.ActivityInfo;
import android.graphics.Color;
import android.hardware.Camera;
import android.os.Bundle;
import android.view.Gravity;
import android.view.SurfaceHolder;
import android.view.SurfaceView;
import android.view.WindowManager;
import android.widget.Button;
import android.widget.FrameLayout;
import android.widget.TextView;

import com.google.zxing.BarcodeFormat;
import com.google.zxing.BinaryBitmap;
import com.google.zxing.DecodeHintType;
import com.google.zxing.MultiFormatReader;
import com.google.zxing.NotFoundException;
import com.google.zxing.PlanarYUVLuminanceSource;
import com.google.zxing.Result;
import com.google.zxing.common.HybridBinarizer;

import java.util.Arrays;
import java.util.EnumMap;
import java.util.Map;

/** Leitor QR nativo: funciona mesmo quando a WebView está conectada por HTTP na rede local. */
@SuppressWarnings("deprecation")
public final class QRScannerActivity extends Activity implements SurfaceHolder.Callback, Camera.PreviewCallback {
    private static final int PEDIR_CAMERA = 5201;
    private SurfaceView superficie;
    private TextView estado;
    private Camera camera;
    private final MultiFormatReader leitor = new MultiFormatReader();
    private volatile boolean finalizado = false;

    @Override
    protected void onCreate(Bundle estadoSalvo) {
        super.onCreate(estadoSalvo);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        setRequestedOrientation(ActivityInfo.SCREEN_ORIENTATION_PORTRAIT);

        FrameLayout raiz = new FrameLayout(this);
        superficie = new SurfaceView(this);
        raiz.addView(superficie, new FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.MATCH_PARENT));

        estado = new TextView(this);
        estado.setText("Aponte a câmera para o QR code de conexão do NutriLab");
        estado.setTextColor(Color.WHITE);
        estado.setTextSize(16);
        estado.setPadding(24, 22, 24, 22);
        estado.setBackgroundColor(0x99000000);
        FrameLayout.LayoutParams topo = new FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.WRAP_CONTENT, Gravity.TOP);
        raiz.addView(estado, topo);

        Button cancelar = new Button(this);
        cancelar.setText("Cancelar");
        cancelar.setOnClickListener(v -> { setResult(RESULT_CANCELED); finish(); });
        FrameLayout.LayoutParams baixo = new FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.WRAP_CONTENT, FrameLayout.LayoutParams.WRAP_CONTENT,
                Gravity.BOTTOM | Gravity.CENTER_HORIZONTAL);
        baixo.bottomMargin = 28;
        raiz.addView(cancelar, baixo);
        setContentView(raiz);

        Map<DecodeHintType, Object> dicas = new EnumMap<>(DecodeHintType.class);
        dicas.put(DecodeHintType.POSSIBLE_FORMATS, Arrays.asList(BarcodeFormat.QR_CODE));
        dicas.put(DecodeHintType.TRY_HARDER, Boolean.TRUE);
        leitor.setHints(dicas);
        superficie.getHolder().addCallback(this);
    }

    @Override
    public void surfaceCreated(SurfaceHolder holder) {
        if (checkSelfPermission(Manifest.permission.CAMERA) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{Manifest.permission.CAMERA}, PEDIR_CAMERA);
            return;
        }
        abrirCamera(holder);
    }

    private void abrirCamera(SurfaceHolder holder) {
        try {
            camera = Camera.open();
            Camera.Parameters parametros = camera.getParameters();
            if (parametros.getSupportedFocusModes() != null
                    && parametros.getSupportedFocusModes().contains(Camera.Parameters.FOCUS_MODE_CONTINUOUS_PICTURE)) {
                parametros.setFocusMode(Camera.Parameters.FOCUS_MODE_CONTINUOUS_PICTURE);
            } else if (parametros.getSupportedFocusModes() != null
                    && parametros.getSupportedFocusModes().contains(Camera.Parameters.FOCUS_MODE_AUTO)) {
                parametros.setFocusMode(Camera.Parameters.FOCUS_MODE_AUTO);
            }
            camera.setParameters(parametros);
            camera.setDisplayOrientation(90);
            camera.setPreviewDisplay(holder);
            camera.setPreviewCallback(this);
            camera.startPreview();
        } catch (Exception e) {
            estado.setText("Não foi possível abrir a câmera. Verifique a permissão e tente novamente.");
            liberarCamera();
        }
    }

    @Override
    public void surfaceChanged(SurfaceHolder holder, int formato, int largura, int altura) {
        if (camera == null) return;
        try {
            camera.stopPreview();
            camera.setPreviewDisplay(holder);
            camera.setPreviewCallback(this);
            camera.startPreview();
        } catch (Exception e) {
            estado.setText("A câmera foi interrompida. Tente novamente.");
        }
    }

    @Override
    public void surfaceDestroyed(SurfaceHolder holder) {
        liberarCamera();
    }

    @Override
    public void onPreviewFrame(byte[] dados, Camera origem) {
        if (finalizado || dados == null || origem == null) return;
        try {
            Camera.Size tamanho = origem.getParameters().getPreviewSize();
            PlanarYUVLuminanceSource fonte = new PlanarYUVLuminanceSource(
                    dados, tamanho.width, tamanho.height, 0, 0, tamanho.width, tamanho.height, false);
            Result resultado = decodificar(fonte);
            if (resultado == null && fonte.isRotateSupported()) {
                resultado = decodificar(fonte.rotateCounterClockwise());
            }
            if (resultado != null && resultado.getText() != null && !resultado.getText().trim().isEmpty()) {
                final String texto = resultado.getText();
                finalizado = true;
                runOnUiThread(() -> {
                    Intent retorno = new Intent();
                    retorno.putExtra("qr_result", texto);
                    setResult(RESULT_OK, retorno);
                    finish();
                });
            }
        } catch (Exception e) {
            // Frames sem QR são esperados; a próxima imagem será analisada.
        } finally {
            leitor.reset();
        }
    }

    private Result decodificar(com.google.zxing.LuminanceSource fonte) {
        try {
            return leitor.decodeWithState(new BinaryBitmap(new HybridBinarizer(fonte)));
        } catch (NotFoundException e) {
            return null;
        } catch (Exception e) {
            return null;
        }
    }

    @Override
    public void onRequestPermissionsResult(int codigo, String[] permissoes, int[] resultados) {
        super.onRequestPermissionsResult(codigo, permissoes, resultados);
        if (codigo == PEDIR_CAMERA) {
            if (resultados.length > 0 && resultados[0] == PackageManager.PERMISSION_GRANTED) {
                abrirCamera(superficie.getHolder());
            } else {
                estado.setText("Permissão de câmera negada. Autorize a câmera para escanear o QR code.");
            }
        }
    }

    private void liberarCamera() {
        if (camera != null) {
            try { camera.setPreviewCallback(null); camera.stopPreview(); } catch (Exception e) { }
            try { camera.release(); } catch (Exception e) { }
            camera = null;
        }
    }

    @Override
    protected void onPause() {
        liberarCamera();
        super.onPause();
    }
}
