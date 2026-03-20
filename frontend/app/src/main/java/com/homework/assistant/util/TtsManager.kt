package com.homework.assistant.util

import android.content.Context
import android.speech.tts.TextToSpeech
import java.util.Locale

/**
 * Android 本地 TTS 管理器
 * 支持英文发音（词/句点读）
 */
class TtsManager(context: Context) {

    private var tts: TextToSpeech? = null
    private var isReady = false

    init {
        tts = TextToSpeech(context.applicationContext) { status ->
            if (status == TextToSpeech.SUCCESS) {
                tts?.language = Locale.US
                isReady = true
            }
        }
    }

    fun speak(text: String) {
        if (isReady) {
            tts?.speak(text, TextToSpeech.QUEUE_FLUSH, null, text.hashCode().toString())
        }
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
