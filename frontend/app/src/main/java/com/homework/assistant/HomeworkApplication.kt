package com.homework.assistant

import android.app.Application
import com.homework.assistant.data.local.AppDatabase
import com.homework.assistant.data.repository.TaskRepository
import com.homework.assistant.util.TtsManager

class HomeworkApplication : Application() {

    lateinit var ttsManager: TtsManager
        private set
    lateinit var database: AppDatabase
        private set
    lateinit var taskRepository: TaskRepository
        private set

    override fun onCreate() {
        super.onCreate()
        ttsManager = TtsManager(this)
        database = AppDatabase.getInstance(this)
        taskRepository = TaskRepository(this)
    }

    override fun onTerminate() {
        ttsManager.shutdown()
        super.onTerminate()
    }
}
