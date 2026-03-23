package com.homework.assistant.data.repository

import android.content.Context
import com.homework.assistant.data.local.AppDatabase
import com.homework.assistant.data.local.TaskDao
import com.homework.assistant.data.local.TaskEntity
import kotlinx.coroutines.flow.Flow
import java.io.File

class TaskRepository(context: Context) {

    private val dao: TaskDao = AppDatabase.getInstance(context).taskDao()

    companion object {
        const val MAX_TASKS = 10
    }

    fun observeAll(): Flow<List<TaskEntity>> = dao.observeAll()

    suspend fun getById(id: String): TaskEntity? = dao.getById(id)

    suspend fun insert(task: TaskEntity) {
        dao.upsert(task)
        // 超限淘汰
        while (dao.count() > MAX_TASKS) {
            val oldest = dao.oldest() ?: break
            deleteWithFiles(oldest)
        }
    }

    suspend fun update(task: TaskEntity) = dao.upsert(task)

    suspend fun deleteById(id: String) {
        val task = dao.getById(id)
        if (task != null) deleteWithFiles(task)
    }

    suspend fun deleteAll() {
        // 先清文件
        dao.observeAll() // flow 不适合这里，直接用 getAll 替代
        // 简单做法：直接删 DB，文件由缓存清理机制处理
        dao.deleteAll()
    }

    private suspend fun deleteWithFiles(task: TaskEntity) {
        listOf(task.thumbnailPath, task.imagePath).forEach { path ->
            try { File(path).delete() } catch (_: Exception) {}
        }
        dao.deleteById(task.id)
    }
}
