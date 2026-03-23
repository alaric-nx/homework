package com.homework.assistant.service

import android.content.Context
import android.util.Log
import androidx.work.*
import com.google.gson.Gson
import com.homework.assistant.data.remote.HomeworkApi
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
                .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 30, TimeUnit.SECONDS)
                .addTag("upload_$taskId")
                .build()

            WorkManager.getInstance(context).enqueue(request)
        }
    }

    private val app = applicationContext as com.homework.assistant.HomeworkApplication
    private val repo = app.taskRepository
    private val api = HomeworkApi()
    private val gson = Gson()

    override suspend fun doWork(): Result {
        val taskId = inputData.getString(KEY_TASK_ID)
        if (taskId.isNullOrEmpty()) {
            Log.e(TAG, "No task_id in input")
            return Result.failure()
        }
        Log.d(TAG, "doWork start taskId=$taskId attempt=$runAttemptCount")

        val task = repo.getById(taskId)
        if (task == null) {
            Log.e(TAG, "Task $taskId not found in DB")
            return Result.failure()
        }

        // 确保状态为 RUNNING
        repo.update(task.copy(status = "RUNNING", updatedAt = System.currentTimeMillis()))

        val imageFile = File(task.imagePath)
        if (!imageFile.exists()) {
            Log.e(TAG, "Task $taskId image not found: ${task.imagePath}")
            repo.update(task.copy(
                status = "FAILED",
                errorMessage = "图片文件不存在",
                updatedAt = System.currentTimeMillis()
            ))
            return Result.failure()
        }

        return try {
            Log.d(TAG, "Task $taskId calling API...")
            val apiResult = api.parseHomework(imageFile)
            apiResult.fold(
                onSuccess = { apiResp ->
                    val resultJson = gson.toJson(apiResp.result)
                    Log.d(TAG, "Task $taskId API success, updating DB...")
                    // 重新从 DB 读最新状态再更新，避免覆盖
                    val fresh = repo.getById(taskId) ?: task
                    repo.update(fresh.copy(
                        status = "SUCCESS",
                        resultJson = resultJson,
                        filledImageBase64 = apiResp.filled_image_base64,
                        errorMessage = null,
                        updatedAt = System.currentTimeMillis()
                    ))
                    Log.d(TAG, "Task $taskId DB updated to SUCCESS")
                    Result.success()
                },
                onFailure = { e ->
                    Log.e(TAG, "Task $taskId API failed: ${e.message}")
                    handleFailure(taskId, e.message ?: "未知错误")
                }
            )
        } catch (e: Exception) {
            Log.e(TAG, "Task $taskId exception: ${e.message}", e)
            handleFailure(taskId, e.message ?: "未知错误")
        }
    }

    private suspend fun handleFailure(taskId: String, error: String): Result {
        val task = repo.getById(taskId)
        if (task == null) {
            Log.e(TAG, "handleFailure: task $taskId not found")
            return Result.failure()
        }
        return if (runAttemptCount < 1) {
            Log.d(TAG, "Task $taskId will retry")
            repo.update(task.copy(
                status = "RUNNING",
                errorMessage = "重试中…",
                updatedAt = System.currentTimeMillis()
            ))
            Result.retry()
        } else {
            Log.d(TAG, "Task $taskId marked FAILED")
            repo.update(task.copy(
                status = "FAILED",
                errorMessage = error,
                updatedAt = System.currentTimeMillis()
            ))
            Result.failure()
        }
    }
}
