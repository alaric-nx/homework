package com.homework.assistant.util

import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.provider.Settings
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import android.util.Log
import android.widget.Toast
import java.util.Locale

/**
 * Android 本地 TTS 管理器
 * 延迟初始化：第一次 speak 时才创建引擎
 */
class TtsManager(private val appContext: Context) {

    private var tts: TextToSpeech? = null
    @Volatile private var isReady = false
    @Volatile private var initStarted = false
    @Volatile private var initFailed = false
    private val handler = Handler(Looper.getMainLooper())
    private var pendingText: String? = null
    @Volatile private var lastRetryAtMs: Long = 0L
    @Volatile private var initStartAtMs: Long = 0L
    @Volatile private var initToken: Long = 0L
    @Volatile private var timeoutRecoveredOnce: Boolean = false
    private val initTimeoutMs = 3000L

    /**
     * 用指定 context 初始化（建议传 Activity context）
     */
    fun ensureInit(activityContext: Context) {
        if (isReady || initStarted) return
        initStarted = true
        doInit(activityContext)
    }

    private fun doInit(ctx: Context, attempt: Int = 1) {
        if (attempt == 1) {
            initFailed = false
            initStartAtMs = System.currentTimeMillis()
            initToken = System.nanoTime()
            timeoutRecoveredOnce = false
            scheduleInitWatchdog(initToken)
        }
        Log.d("TtsManager", "TTS doInit attempt=$attempt")
        val listener = TextToSpeech.OnInitListener { status ->
            Log.d("TtsManager", "TTS onInit status=$status (0=SUCCESS, -1=ERROR)")
            if (status == TextToSpeech.SUCCESS) {
                // 某些机型可能在 tts 字段赋值前回调 onInit，转到主线程再取一次避免竞态
                handler.post { onInitSuccess() }
            } else {
                Log.e("TtsManager", "TTS init FAILED attempt=$attempt")
                if (attempt == 1) {
                    // Android 国内机型不一定有 Google TTS，尝试系统可用引擎
                    val engine = pickAlternativeEngine(ctx)
                    if (!engine.isNullOrBlank()) {
                        handler.postDelayed({
                            doInitWithEngine(ctx, engine, attempt + 1)
                        }, 500L)
                    } else {
                        handler.postDelayed({ doInit(ctx, attempt + 1) }, 800L)
                    }
                } else if (attempt < 4) {
                    handler.postDelayed({ doInit(ctx, attempt + 1) }, attempt * 1500L)
                } else {
                    initFailed = true
                    initStarted = false
                    Log.e("TtsManager", "TTS init failed after retries (default engine)")
                }
            }
        }
        tts?.shutdown()
        val systemDefaultEngine = getSystemDefaultEnginePackage(ctx)
        if (!systemDefaultEngine.isNullOrBlank()) {
            Log.d("TtsManager", "TTS init with system default engine=$systemDefaultEngine")
            tts = TextToSpeech(ctx, listener, systemDefaultEngine)
        } else {
            tts = TextToSpeech(ctx, listener)
        }
    }

    private fun doInitWithEngine(ctx: Context, engine: String, attempt: Int) {
        Log.d("TtsManager", "TTS doInit engine=$engine attempt=$attempt")
        val listener = TextToSpeech.OnInitListener { status ->
            if (status == TextToSpeech.SUCCESS) {
                // 某些机型可能在 tts 字段赋值前回调 onInit，转到主线程再取一次避免竞态
                handler.post { onInitSuccess("engine=$engine") }
            } else {
                if (attempt < 4) {
                    handler.postDelayed({ doInit(ctx, attempt + 1) }, attempt * 1500L)
                } else {
                    initFailed = true
                    initStarted = false
                    Log.e("TtsManager", "TTS init failed after retries (engine=$engine)")
                }
            }
        }
        tts?.shutdown()
        tts = TextToSpeech(ctx, listener, engine)
    }

    fun speak(text: String) {
        if (text.isBlank()) return
        val elapsed = System.currentTimeMillis() - initStartAtMs

        if (isReady && tts != null) {
            val r = speakInternal(tts!!, text.trim(), "tts_${System.nanoTime()}")
            Log.d("TtsManager", "speak result=$r text='${text.take(30)}'")
            if (r == TextToSpeech.ERROR) {
                // 引擎就绪但播放失败：回收状态，允许下一次点击重新初始化
                isReady = false
                initStarted = false
                initFailed = true
                Toast.makeText(appContext, "当前语音引擎播放失败，请重试或切换TTS引擎", Toast.LENGTH_LONG).show()
            }
            return
        }

        // 初始化长时间无结果时，先回收状态，避免一直“语音加载中…”
        val stuck = initStarted && !isReady && elapsed >= initTimeoutMs
        val nullEngineStuck = initStarted && tts == null && elapsed >= 1500L
        if (stuck || nullEngineStuck) {
            val wasEngineNull = tts == null
            Log.e("TtsManager", "TTS init seems stuck, forcing reset (elapsed=${elapsed}ms, engineNull=$wasEngineNull)")
            tts?.shutdown()
            tts = null
            initStarted = false
            initFailed = true
        }

        if (!initFailed) {
            pendingText = text
            Toast.makeText(appContext, "语音加载中…", Toast.LENGTH_SHORT).show()
            // 如果还没开始初始化，用 appContext 兜底
            if (!initStarted) {
                initStarted = true
                doInit(appContext)
            }
            return
        }

        // 失败后允许按点击再次触发重试，避免一次失败后永久不可用
        val now = System.currentTimeMillis()
        if (!initStarted && now - lastRetryAtMs > 2000L) {
            lastRetryAtMs = now
            pendingText = text
            initStarted = true
            initFailed = false
            Toast.makeText(appContext, "正在重试语音引擎…", Toast.LENGTH_SHORT).show()
            doInit(appContext)
            return
        }

        Toast.makeText(appContext, "语音引擎不可用，请安装/启用系统TTS", Toast.LENGTH_LONG).show()
        try {
            appContext.startActivity(
                Intent(TextToSpeech.Engine.ACTION_INSTALL_TTS_DATA).apply {
                    flags = Intent.FLAG_ACTIVITY_NEW_TASK
                }
            )
            return
        } catch (_: Exception) {}
        try {
            appContext.startActivity(
                Intent("com.android.settings.TTS_SETTINGS").apply {
                    flags = Intent.FLAG_ACTIVITY_NEW_TASK
                }
            )
        } catch (_: Exception) {}
    }

    fun stop() { tts?.stop() }

    fun shutdown() {
        tts?.stop()
        tts?.shutdown()
        tts = null
        isReady = false
        initStarted = false
        initFailed = false
        pendingText = null
        lastRetryAtMs = 0L
        initStartAtMs = 0L
        initToken = 0L
        timeoutRecoveredOnce = false
    }

    private fun onInitSuccess(logTag: String = "") {
        val engine = tts
        if (engine == null) {
            // 兜底再试一次，覆盖构造回调早于字段赋值的设备行为
            handler.postDelayed({ onInitSuccess(logTag) }, 50L)
            return
        }

        val lrUs = engine.setLanguage(Locale.US)
        val finalLanguage = if (lrUs == TextToSpeech.LANG_MISSING_DATA || lrUs == TextToSpeech.LANG_NOT_SUPPORTED) {
            val lrEn = engine.setLanguage(Locale.ENGLISH)
            if (lrEn == TextToSpeech.LANG_MISSING_DATA || lrEn == TextToSpeech.LANG_NOT_SUPPORTED) {
                engine.setLanguage(Locale.getDefault())
                "default"
            } else {
                "en"
            }
        } else {
            "us"
        }
        Log.d("TtsManager", "setLanguage final=$finalLanguage $logTag")
        try {
            Log.d("TtsManager", "tts current engine=${engine.defaultEngine}")
        } catch (_: Exception) {}

        engine.setSpeechRate(1.0f)
        engine.setPitch(1.0f)
        engine.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
            override fun onStart(utteranceId: String?) = Unit
            override fun onDone(utteranceId: String?) = Unit
            override fun onError(utteranceId: String?) {
                Log.e("TtsManager", "utterance error id=$utteranceId")
            }
        })

        isReady = true
        initStarted = false
        initFailed = false
        Log.d("TtsManager", "TTS ready! $logTag")
        pendingText?.let { text ->
            pendingText = null
            speakInternal(engine, text.trim(), "tts_pending")
        }
    }

    private fun speakInternal(engine: TextToSpeech, text: String, utteranceId: String): Int {
        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
            engine.speak(text, TextToSpeech.QUEUE_FLUSH, Bundle(), utteranceId)
        } else {
            @Suppress("DEPRECATION")
            engine.speak(text, TextToSpeech.QUEUE_FLUSH, null)
        }
    }

    private fun scheduleInitWatchdog(token: Long) {
        handler.postDelayed({
            // token 不一致表示已开启新一轮初始化，忽略旧 watchdog
            if (token != initToken) return@postDelayed
            if (!isReady && initStarted) {
                if (!timeoutRecoveredOnce) {
                    // 部分 ROM 在 Activity context 绑定失败，超时后改用 Application context 再试一次
                    timeoutRecoveredOnce = true
                    Log.e("TtsManager", "TTS init timeout, retry with app context")
                    tts?.shutdown()
                    tts = null
                    doInit(appContext, 2)
                } else {
                    Log.e("TtsManager", "TTS init timeout after ${initTimeoutMs}ms")
                    tts?.shutdown()
                    tts = null
                    initStarted = false
                    initFailed = true
                }
            }
        }, initTimeoutMs)
    }

    private fun pickAlternativeEngine(ctx: Context): String? {
        return getSystemDefaultEnginePackage(ctx) ?: queryEnginePackages(ctx).firstOrNull()
    }

    private fun getSystemDefaultEnginePackage(ctx: Context): String? {
        return try {
            Settings.Secure.getString(ctx.contentResolver, "tts_default_synth")
                ?.trim()
                ?.takeIf { it.isNotEmpty() }
        } catch (_: Exception) {
            null
        }
    }

    private fun queryEnginePackages(ctx: Context): List<String> {
        return try {
            val flags = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                PackageManager.ResolveInfoFlags.of(0)
            } else {
                null
            }
            val services = if (flags != null) {
                ctx.packageManager.queryIntentServices(
                    Intent(TextToSpeech.Engine.INTENT_ACTION_TTS_SERVICE),
                    flags
                )
            } else {
                @Suppress("DEPRECATION")
                ctx.packageManager.queryIntentServices(
                    Intent(TextToSpeech.Engine.INTENT_ACTION_TTS_SERVICE),
                    0
                )
            }
            services
                .mapNotNull { it.serviceInfo?.packageName }
                .distinct()
        } catch (_: Exception) {
            emptyList()
        }
    }
}
