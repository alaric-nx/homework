#!/bin/bash
set -e

export ANDROID_HOME="$HOME/Library/Android/sdk"

# 关键：JAVA_OPTS 会被 gradlew 传给启动 JVM，包括 wrapper 下载阶段
export JAVA_OPTS="-Dhttp.proxyHost=127.0.0.1 -Dhttp.proxyPort=7890 -Dhttps.proxyHost=127.0.0.1 -Dhttps.proxyPort=7890"
export GRADLE_OPTS="-Dhttp.proxyHost=127.0.0.1 -Dhttp.proxyPort=7890 -Dhttps.proxyHost=127.0.0.1 -Dhttps.proxyPort=7890"

echo "=== Java: $(java -version 2>&1 | head -1) ==="
echo "=== ANDROID_HOME: $ANDROID_HOME ==="

chmod +x gradlew

echo ""
echo "=== 开始编译 ==="
./gradlew assembleDebug --no-daemon

APK_PATH="app/build/outputs/apk/debug/app-debug.apk"

if [ -f "$APK_PATH" ]; then
    echo ""
    echo "=== 编译成功 ==="
    echo "APK: $APK_PATH"
    echo "安装: adb install $APK_PATH"
else
    echo "=== 编译失败 ==="
    exit 1
fi
