package de.alexwolf.sparmania;

import android.Manifest;
import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.content.res.Configuration;
import android.net.Uri;
import android.os.Bundle;
import android.view.View;
import android.webkit.CookieManager;
import android.webkit.GeolocationPermissions;
import android.webkit.JavascriptInterface;
import android.webkit.PermissionRequest;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.FrameLayout;

import org.json.JSONObject;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.HashMap;
import java.util.Map;

/**
 * Sparmania Route v3.
 *
 * appView: die eigene Karten-App (assets/karte.html) über den fiktiven
 * Secure-Origin https://appassets.local (GPS braucht Secure Context).
 *
 * officialView: zweiter WebView für sparmania-200.de (Login, QR-Scan,
 * Einsammeln). Session-Cookies bleiben über den CookieManager erhalten,
 * damit syncCollected() den Sammelstand des Profils abrufen kann.
 */
public class MainActivity extends Activity {

    private static final String HOST = "appassets.local";
    private static final String START_URL = "https://" + HOST + "/karte.html";
    private static final String OFFICIAL = "sparmania-200.de";
    private static final int REQ_LOCATION = 1;
    private static final int REQ_CAMERA = 2;

    private FrameLayout root;
    private WebView appView;
    private WebView officialView;
    private Button officialBack;
    private GeolocationPermissions.Callback pendingGeoCallback;
    private String pendingGeoOrigin;
    private PermissionRequest pendingCamRequest;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        root = new FrameLayout(this);
        appView = new WebView(this);
        root.addView(appView);
        setContentView(root);

        CookieManager.getInstance().setAcceptCookie(true);

        WebSettings s = appView.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setGeolocationEnabled(true);

        appView.addJavascriptInterface(new Bridge(), "AndroidApp");

        appView.setWebViewClient(new WebViewClient() {
            @Override
            public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest request) {
                Uri u = request.getUrl();
                if (!HOST.equals(u.getHost())) return null;  // Kacheln, OSRM etc. normal
                String path = u.getPath();
                if (path == null || "/".equals(path)) path = "/karte.html";
                try {
                    InputStream is = getAssets().open(path.substring(1));
                    String mime = path.endsWith(".html") ? "text/html" : "application/octet-stream";
                    Map<String, String> headers = new HashMap<>();
                    headers.put("Access-Control-Allow-Origin", "*");
                    return new WebResourceResponse(mime, "utf-8", 200, "OK", headers, is);
                } catch (IOException e) {
                    return new WebResourceResponse("text/plain", "utf-8", 404, "Not Found",
                            new HashMap<String, String>(), new ByteArrayInputStream(new byte[0]));
                }
            }

            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                Uri u = request.getUrl();
                if (HOST.equals(u.getHost())) return false;
                String h = u.getHost();
                if (h != null && (h.equals(OFFICIAL) || h.endsWith("." + OFFICIAL))) {
                    showOfficial(u.toString());
                    return true;
                }
                // Externe Links nur für unbedenkliche Schemata weiterreichen (z.B. Google Maps).
                // Blockt tel:/sms:/intent:/market:-Deep-Links, die sonst andere Apps ansteuern könnten.
                String sc = u.getScheme();
                if (sc != null && (sc.equals("http") || sc.equals("https") || sc.equals("geo"))) {
                    try {
                        startActivity(new Intent(Intent.ACTION_VIEW, u));
                    } catch (Exception ignored) {
                    }
                }
                return true;
            }
        });

        appView.setWebChromeClient(new WebChromeClient() {
            @Override
            public void onGeolocationPermissionsShowPrompt(String origin,
                    GeolocationPermissions.Callback callback) {
                if (hasLocationPermission()) {
                    callback.invoke(origin, true, true);
                } else {
                    pendingGeoCallback = callback;
                    pendingGeoOrigin = origin;
                    requestPermissions(new String[]{
                            Manifest.permission.ACCESS_FINE_LOCATION,
                            Manifest.permission.ACCESS_COARSE_LOCATION}, REQ_LOCATION);
                }
            }
        });

        if (!hasLocationPermission()) {
            requestPermissions(new String[]{
                    Manifest.permission.ACCESS_FINE_LOCATION,
                    Manifest.permission.ACCESS_COARSE_LOCATION}, REQ_LOCATION);
        }

        // System-Dunkelmodus an die Web-App durchreichen (Theme-Wechsel startet
        // die Activity neu und lädt mit aktualisiertem Parameter)
        boolean night = (getResources().getConfiguration().uiMode
                & Configuration.UI_MODE_NIGHT_MASK) == Configuration.UI_MODE_NIGHT_YES;
        appView.loadUrl(START_URL + (night ? "?dark=1" : ""));
    }

    /** Offizielle Sparmania-Seite als Overlay (Login, QR-Scan, Einsammeln). */
    private void showOfficial(String url) {
        if (officialView == null) {
            officialView = new WebView(this);
            WebSettings os = officialView.getSettings();
            os.setJavaScriptEnabled(true);
            os.setDomStorageEnabled(true);
            os.setMediaPlaybackRequiresUserGesture(false);  // QR-Scanner-Kamera sofort
            CookieManager.getInstance().setAcceptThirdPartyCookies(officialView, true);

            officialView.setWebViewClient(new WebViewClient() {
                @Override
                public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                    Uri u = request.getUrl();
                    String h = u.getHost();
                    if (h != null && (h.equals(OFFICIAL) || h.endsWith("." + OFFICIAL))) return false;
                    try {
                        startActivity(new Intent(Intent.ACTION_VIEW, u));
                    } catch (Exception ignored) {
                    }
                    return true;
                }
            });

            officialView.setWebChromeClient(new WebChromeClient() {
                @Override
                public void onPermissionRequest(PermissionRequest request) {
                    boolean wantsVideo = false;
                    for (String r : request.getResources()) {
                        if (PermissionRequest.RESOURCE_VIDEO_CAPTURE.equals(r)) wantsVideo = true;
                    }
                    if (!wantsVideo) {
                        request.deny();
                        return;
                    }
                    if (checkSelfPermission(Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED) {
                        request.grant(request.getResources());
                    } else {
                        pendingCamRequest = request;
                        requestPermissions(new String[]{Manifest.permission.CAMERA}, REQ_CAMERA);
                    }
                }
            });
            root.addView(officialView);

            // Schneller Rücksprung zur Route (schwebender Button über der offiziellen Seite)
            officialBack = new Button(this);
            officialBack.setText("‹ Zur Route");
            officialBack.setAllCaps(false);
            FrameLayout.LayoutParams lp = new FrameLayout.LayoutParams(
                    FrameLayout.LayoutParams.WRAP_CONTENT, FrameLayout.LayoutParams.WRAP_CONTENT);
            lp.leftMargin = 24;
            lp.topMargin = 72;
            root.addView(officialBack, lp);
            officialBack.setOnClickListener(new View.OnClickListener() {
                @Override
                public void onClick(View v) {
                    hideOfficial();
                }
            });
        }
        officialView.setVisibility(View.VISIBLE);
        officialView.bringToFront();
        officialBack.setVisibility(View.VISIBLE);
        officialBack.bringToFront();
        officialView.loadUrl(url);
    }

    private void hideOfficial() {
        if (officialView != null) officialView.setVisibility(View.GONE);
        if (officialBack != null) officialBack.setVisibility(View.GONE);
    }

    /** Von JS aufrufbar: window.AndroidApp.* */
    private class Bridge {
        @JavascriptInterface
        public void openOfficial(final String url) {
            if (url == null || !url.startsWith("https://" + OFFICIAL)) return;
            runOnUiThread(new Runnable() {
                public void run() {
                    showOfficial(url);
                }
            });
        }

        /** Öffnet eine externe App (z.B. Google Maps für die Routen-Etappen). */
        @JavascriptInterface
        public void openExternal(final String url) {
            if (url == null) return;
            final Uri u = Uri.parse(url);
            String sc = u.getScheme();
            if (sc == null || !(sc.equals("http") || sc.equals("https") || sc.equals("geo"))) return;
            runOnUiThread(new Runnable() {
                public void run() {
                    try {
                        startActivity(new Intent(Intent.ACTION_VIEW, u));
                    } catch (Exception ignored) {
                    }
                }
            });
        }

        @JavascriptInterface
        public void syncCollected() {
            new Thread(new Runnable() {
                public void run() {
                    String result;
                    try {
                        URL url = new URL("https://" + OFFICIAL + "/api/coins/map?includeCollected=1");
                        HttpURLConnection con = (HttpURLConnection) url.openConnection();
                        con.setConnectTimeout(15000);
                        con.setReadTimeout(15000);
                        String cookies = CookieManager.getInstance().getCookie("https://" + OFFICIAL);
                        if (cookies != null) con.setRequestProperty("Cookie", cookies);
                        con.setRequestProperty("Accept", "application/json");
                        InputStream is = con.getResponseCode() < 400
                                ? con.getInputStream() : con.getErrorStream();
                        ByteArrayOutputStream bos = new ByteArrayOutputStream();
                        byte[] buf = new byte[8192];
                        int n;
                        while (is != null && (n = is.read(buf)) > 0) bos.write(buf, 0, n);
                        con.disconnect();
                        result = bos.toString("UTF-8");
                    } catch (Exception e) {
                        result = "{\"error\":\"" + e.getClass().getSimpleName() + "\"}";
                    }
                    final String body = result;
                    runOnUiThread(new Runnable() {
                        public void run() {
                            appView.evaluateJavascript(
                                    "window.onSyncResult(" + JSONObject.quote(body) + ")", null);
                        }
                    });
                }
            }).start();
        }
    }

    private boolean hasLocationPermission() {
        return checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED
                || checkSelfPermission(Manifest.permission.ACCESS_COARSE_LOCATION) == PackageManager.PERMISSION_GRANTED;
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode == REQ_LOCATION && pendingGeoCallback != null) {
            pendingGeoCallback.invoke(pendingGeoOrigin, hasLocationPermission(), true);
            pendingGeoCallback = null;
            pendingGeoOrigin = null;
        }
        if (requestCode == REQ_CAMERA && pendingCamRequest != null) {
            if (checkSelfPermission(Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED) {
                pendingCamRequest.grant(pendingCamRequest.getResources());
            } else {
                pendingCamRequest.deny();
            }
            pendingCamRequest = null;
        }
    }

    @Override
    public void onBackPressed() {
        if (officialView != null && officialView.getVisibility() == View.VISIBLE) {
            if (officialView.canGoBack()) officialView.goBack();
            else hideOfficial();
            return;
        }
        if (appView.canGoBack()) {
            appView.goBack();
        } else {
            super.onBackPressed();
        }
    }
}
