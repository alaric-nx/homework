package com.homework.assistant

import android.app.Application
import com.homework.assistant.util.TtsManager

class HomeworkApplication : Application() {

    lateinit var ttsManager: TtsManager
        private set

    override fun onCreate() {
        super.onCreate()
        ttsManager = TtsManager(this)
    }

    override fun onTerminate() {
        ttsManager.shutdown()
        super.onTerminate()
    }
}
