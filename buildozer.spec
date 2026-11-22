[app]
title = UNG220Z 光猫工具
package.name = ung220z
package.domain = org.ung220z.tools
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
source.exclude_exts = spec,md,yml,yaml
version = 1.0.0

requirements = python3,kivy==2.2.1

orientation = portrait
fullscreen = 0
android.permissions = INTERNET,ACCESS_WIFI_STATE,ACCESS_NETWORK_STATE
android.api = 35
android.minapi = 21
android.sdk = 35
android.ndk = 25b
android.archs = arm64-v8a
android.accept_sdk_license = True

[buildozer]
log_level = 2
warn_on_root = 1
