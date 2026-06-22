package com.homework.assistant.data.repository

import android.content.Context
import com.homework.assistant.data.local.AppDatabase
import com.homework.assistant.data.local.TaskDao
import com.homework.assistant.data.local.TaskEntity
import com.homework.assistant.data.remote.HomeworkApi
import kotlinx.coroutines.flow.Flow
import java.io.File
import java.io.FileInputStream
import java.security.MessageDigest

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
        // 先联动删除后端缓存并清理本地文件
        dao.getAll().forEach { task ->
            val imageFile = File(task.imagePath)
            if (imageFile.exists()) {
                val md5 = getFileMd5(imageFile)
                if (md5.isNotBlank()) {
                    kotlin.runCatching {
                        HomeworkApi().deleteTask("${task.subject}:$md5")
                    }
                }
            }
            listOf(task.thumbnailPath, task.imagePath).forEach { path ->
                try { File(path).delete() } catch (_: Exception) {}
            }
        }
        dao.deleteAll()
    }

    private suspend fun deleteWithFiles(task: TaskEntity) {
        val imageFile = File(task.imagePath)
        if (imageFile.exists()) {
            val md5 = getFileMd5(imageFile)
            if (md5.isNotBlank()) {
                kotlin.runCatching {
                    HomeworkApi().deleteTask("${task.subject}:$md5")
                }
            }
        }
        listOf(task.thumbnailPath, task.imagePath).forEach { path ->
            try { File(path).delete() } catch (_: Exception) {}
        }
        dao.deleteById(task.id)
    }

    private fun getFileMd5(file: File): String {
        if (!file.exists()) return ""
        return try {
            val digest = MessageDigest.getInstance("MD5")
            val buffer = ByteArray(8192)
            FileInputStream(file).use { stream ->
                var read: Int
                while (stream.read(buffer).also { read = it } > 0) {
                    digest.update(buffer, 0, read)
                }
            }
            val bytes = digest.digest()
            bytes.joinToString("") { "%02x".format(it) }
        } catch (e: Exception) {
            ""
        }
    }
}
