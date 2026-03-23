package com.homework.assistant.service

import android.content.Context
import android.util.Log
import androidx.work.*
import com.google.gson.Gson
import com.homework.assistant.data.local.TaskEntity
import com.homework.assistant.data.remote.HomeworkApi
import com.homework.assistant.data.repository.TaskRepository
import java.io.File
import java.util.concurrent.TimeUnit

/**
 * WorkManager Worker：后台执行题图上传与解析
 * 自动重试 1 次（EXPONENTIAL backoff），之后标记 FAILED 等用户手动重试
 */
class UploadWorker(
    appContext: Context,
    params: WorkerParameters
) : CoroutineWorker(appContext, params) {

    companion object {
        const val KEY_TASK_ID = "task_id"
        private const val TAG = "UploadWorker"

        fun enqueue(context: Context, taskId: String) {
            val request = OneTimeWorkRequestBuilder<UploadWorker>()
                .setInputData(workDataOf(KEY_TASK_ID to taskId))
                .setConstraints(
                    Constraints.Builder()
                        .setRequiredNetworkType(NetworkType.CONNECTED)
                        .build()
                )
                .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 30, TimeUnit.SECONDS)
                .addTag("upload_$taskId")
                .build()

            WorkManager.getInstance(context)
                .enqueueUniqueWork("upload_$taskId", ExistingWorkPolicy.KEEP, request)
        }
    }

    private val repo = TaskRepository(applicationContext)
    private val api = HomeworkApi()
    private val gson = Gson()

    override suspend fun doWork(): Result {
        val taskId = inputData.getString(KEY_TASK_ID)
            ?: return Result.failure()

        val task = repo.getById(taskId)
            ?: return Result.failure()

        // 更新为 RUNNING
        repo.update(task.copy(status = "RUNNING", updatedAt = System.currentTimeMillis()))

        val imageFile = File(task.imagePath)
        if (!imageFile.exists()) {
            repo.update(task.copy(
                status = "FAILED",
                errorMessage = "图片文件不存在",
                updatedAt = System.currentTimeMillis()
            ))
            return Result.failure()
        }

        return try {
            val apiResult = api.parseHomework(imageFile)
            apiResult.fold(
                onSuccess = { apiResp ->
                    val resultJson = gson.toJson(apiResp.result)
                    repo.update(task.copy(
                        status = "SUCCESS",
                        resultJson = resultJson,
                        filledImageBase64 = apiResp.filled_image_base64,
                        errorMessage = null,
                        updatedAt = System.currentTimeMillis()
                    ))
                    Log.d(TAG, "Task $taskId completed")
                    Result.success()
                },
                onFailure = { e ->
                    Log.e(TAG, "Task $taskId failed: ${e.message}")
                    handleFailure(task, e.message ?: "未知错误")
                }
            )
        } catch (e: Exception) {
            Log.e(TAG, "Task $taskId exception: ${e.message}")
            handleFailure(task, e.message ?: "未知错误")
        }
    }

    private suspend fun handleFailure(task: TaskEntity, error: String): Result {
        return if (runAttemptCount < 1) {
            // 还没重试过，返回 retry 让 WorkManager 自动重试 1 次
            repo.update(task.copy(
                status = "PENDING",
                errorMessage = "重试中…",
                updatedAt = System.currentTimeMillis()
            ))
            Result.retry()
        } else {
            // 已重试 1 次，标记失败
            repo.update(task.copy(
                status = "FAILED",
                errorMessage = error,
                updatedAt = System.currentTimeMillis()
            ))
            Result.failure()
        }
    }
}
