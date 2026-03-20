package com.homework.assistant.util

import android.content.Context
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import android.util.Log
import android.widget.Toast
import java.util.Locale

/**
 * Android 本地 TTS 管理器
 * 支持英文发音（词/句点读）
 */
class TtsManager(private val appContext: Context) {

    private var tts: TextToSpeech? = null
    private var isReady = false
    private var langOk = false

    init {
        tts = TextToSpeech(appContext.applicationContext) { status ->
            if (status == TextToSpeech.SUCCESS) {
                val engine = tts
                if (engine != null) {
                    val result = engine.setLanguage(Locale.US)
                    langOk = result != TextToSpeech.LANG_MISSING_DATA
                            && result != TextToSpeech.LANG_NOT_SUPPORTED
                    if (!langOk) {
                        val fb = engine.setLanguage(Locale.ENGLISH)
                        langOk = fb != TextToSpeech.LANG_MISSING_DATA
                                && fb != TextToSpeech.LANG_NOT_SUPPORTED
                    }
                    engine.setSpeechRate(1.0f)
                    engine.setPitch(1.0f)
                }
                isReady = true
                Log.d("TtsManager", "TTS init ok, langOk=$langOk")
            } else {
                Log.e("TtsManager", "TTS init failed, status=$status")
            }
        }
    }

    fun speak(text: String) {
        if (text.isBlank()) return
        if (!isReady) {
            Toast.makeText(appContext, "语音引擎未就绪", Toast.LENGTH_SHORT).show()
            return
        }
        if (!langOk) {
            Toast.makeText(appContext, "设备缺少英文语音数据，请在系统设置中下载", Toast.LENGTH_LONG).show()
        }
        // 即使 langOk=false 也尝试播放，部分设备仍可发声
        tts?.speak(text.trim(), TextToSpeech.QUEUE_FLUSH, null, "tts_${System.nanoTime()}")
    }

    fun stop() {
        tts?.stop()
    }

    fun shutdown() {
        tts?.stop()
        tts?.shutdown()
        tts = null
        isReady = false
    }
}
