#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
aosp="${AOSP_ROOT:?Set AOSP_ROOT to your Android16 AOSP checkout}"
java="$aosp/prebuilts/jdk/jdk21/linux-x86/bin"
sdk="$aosp/prebuilts/sdk/tools/linux/bin"
mkdir -p build/classes assets
ffmpeg -hide_banner -loglevel error -y -f lavfi -i testsrc2=size=320x240:rate=30 -f lavfi -i sine=frequency=1000:sample_rate=48000 -t 2 -c:v libx264 -pix_fmt yuv420p -profile:v baseline -c:a aac assets/sample.mp4
ffmpeg -hide_banner -loglevel error -y -f lavfi -i testsrc2=size=1920x1080:rate=60 -t 3 -c:v libx264 -preset ultrafast -pix_fmt yuv420p -profile:v baseline -an assets/sample-1080p60.mp4
ffmpeg -hide_banner -loglevel error -y -f lavfi -i testsrc2=size=1920x1080:rate=60 -t 3 -c:v libx264 -preset ultrafast -pix_fmt yuv420p -profile:v baseline -level:v 4.2 -b:v 8M -maxrate 16M -bufsize 16M -an assets/sample-1080p60-bounded.mp4
"$java/javac" -source 8 -target 8 -classpath "$aosp/prebuilts/sdk/current/public/android.jar" -d build/classes src/org/kickpi/diagnostics/*.java
"$java/jar" cf build/classes.jar -C build/classes .
"$aosp/out/host/linux-x86/bin/d8" --lib "$aosp/prebuilts/sdk/current/public/android.jar" --min-api 29 --output build build/classes.jar
"$aosp/out/host/linux-x86/bin/aapt2" link -I "$aosp/prebuilts/sdk/current/public/android.jar" --manifest AndroidManifest.xml -A assets -o build/unsigned.apk
cd build
zip -q unsigned.apk classes.dex
"$sdk/zipalign" -f 4 unsigned.apk aligned.apk
if [ ! -f debug.jks ]; then
  "$java/keytool" -genkeypair -keystore debug.jks -storepass android -keypass android -alias debug -dname 'CN=K11C local diagnostics' -keyalg RSA -validity 30
fi
"$java/java" -jar "$aosp/prebuilts/sdk/tools/linux/lib/apksigner.jar" sign --ks debug.jks --ks-key-alias debug --ks-pass pass:android --key-pass pass:android --out diagnostics.apk aligned.apk
sha256sum diagnostics.apk
