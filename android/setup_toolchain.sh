#!/bin/bash
# Installiert einmalig die minimale Android-Toolchain über Homebrew (~600 MB):
#   - OpenJDK (Formula, braucht kein Admin-Passwort)
#   - Android Command-line Tools (Cask)
#   - build-tools;34.0.0 + platforms;android-34 über sdkmanager
#
# Die Google-SDK-Lizenzen werden automatisch bestätigt (yes |) —
# nur ausführen, wenn du damit einverstanden bist.
set -euo pipefail

brew install openjdk
brew install --cask android-commandlinetools

export JAVA_HOME="$(brew --prefix openjdk)"
export PATH="$JAVA_HOME/bin:$PATH"

SDK="$HOME/Library/Android/sdk"
mkdir -p "$SDK"
CLT="$(brew --prefix)/share/android-commandlinetools/cmdline-tools/latest/bin"

# pipefail kurz aus: 'yes' stirbt planmäßig per SIGPIPE, sobald sdkmanager fertig ist
set +o pipefail
yes | "$CLT/sdkmanager" --sdk_root="$SDK" --licenses > /dev/null
set -o pipefail
"$CLT/sdkmanager" --sdk_root="$SDK" "build-tools;34.0.0" "platforms;android-34"

echo
echo "Toolchain steht. APK bauen mit:  bash android/build_apk.sh"
