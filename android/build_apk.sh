#!/bin/bash
# Baut die signierte Sparmania-APK ohne Gradle, direkt mit den SDK-Werkzeugen.
#
# Voraussetzungen (einmalig, siehe setup_toolchain.sh):
#   - JDK (temurin)
#   - Android SDK mit build-tools;34.0.0 und platforms;android-34
#
# Aufruf:  bash android/build_apk.sh
set -euo pipefail
cd "$(dirname "$0")"

# Homebrew-OpenJDK in den PATH holen, falls kein System-Java existiert
if ! command -v javac >/dev/null 2>&1 || ! javac -version >/dev/null 2>&1; then
  export JAVA_HOME="$(brew --prefix openjdk 2>/dev/null)"
  export PATH="$JAVA_HOME/bin:$PATH"
fi

SDK="${ANDROID_HOME:-$HOME/Library/Android/sdk}"
# neueste installierte build-tools nehmen (altes d8 verträgt kein aktuelles javac-Output)
BT="$(ls -d "$SDK"/build-tools/*/ 2>/dev/null | sort -V | tail -1)"
BT="${BT%/}"
PLATFORM="$SDK/platforms/android-34/android.jar"
KEYSTORE="sparmania-release.keystore"
# Passwort NICHT im Repo: per Umgebungsvariable setzen -> export SPARMANIA_KEYSTORE_PASS=...
STOREPASS="${SPARMANIA_KEYSTORE_PASS:-}"
if [ -z "$STOREPASS" ]; then
  echo "FEHLT: Umgebungsvariable SPARMANIA_KEYSTORE_PASS (Keystore-Passwort) nicht gesetzt."
  echo "  export SPARMANIA_KEYSTORE_PASS=<dein-passwort>   und erneut ausführen."
  exit 1
fi

for tool in "$BT/aapt2" "$BT/d8" "$BT/apksigner" "$BT/zipalign"; do
  [ -x "$tool" ] || { echo "FEHLT: $tool — erst setup_toolchain.sh ausführen"; exit 1; }
done
[ -f "$PLATFORM" ] || { echo "FEHLT: $PLATFORM — erst setup_toolchain.sh ausführen"; exit 1; }

# Frische Karte als App-Asset übernehmen
mkdir -p assets
cp ../sparmania-karte.html assets/karte.html

rm -rf build && mkdir -p build/classes build/dex

echo "[1/6] Ressourcen kompilieren"
"$BT/aapt2" compile --dir res -o build/res.zip

echo "[2/6] APK-Grundgerüst linken"
"$BT/aapt2" link -o build/base.apk \
  --manifest AndroidManifest.xml \
  -I "$PLATFORM" \
  -A assets \
  build/res.zip

echo "[3/6] Java kompilieren"
javac -source 8 -target 8 -nowarn \
  -classpath "$PLATFORM" \
  -d build/classes \
  src/de/alexwolf/sparmania/MainActivity.java

echo "[4/6] Dex erzeugen"
"$BT/d8" --release --lib "$PLATFORM" --output build/dex \
  $(find build/classes -name '*.class')
(cd build/dex && zip -q ../base.apk classes.dex)

echo "[5/6] Ausrichten"
"$BT/zipalign" -f 4 build/base.apk build/aligned.apk

echo "[6/6] Signieren"
if [ ! -f "$KEYSTORE" ]; then
  keytool -genkeypair -keystore "$KEYSTORE" -alias sparmania \
    -keyalg RSA -keysize 2048 -validity 3650 \
    -storepass "$STOREPASS" -keypass "$STOREPASS" \
    -dname "CN=Sparmania Route"
  echo "Neuer Keystore erzeugt: $KEYSTORE (Passwort: $STOREPASS)"
fi
"$BT/apksigner" sign --ks "$KEYSTORE" --ks-pass "pass:$STOREPASS" \
  --out ../sparmania.apk build/aligned.apk
"$BT/apksigner" verify ../sparmania.apk

echo
echo "Fertig: sparmania.apk ($(du -h ../sparmania.apk | cut -f1 | tr -d ' '))"
