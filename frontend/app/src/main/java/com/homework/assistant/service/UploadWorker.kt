package com.homework.assistant.service

import android.content.Context
import android.util.Log
import androidx.work.*
import com.google.gson.Gson
import com.homework.assistant.data.local.SettingsStore
import com.homework.assistant.data.model.normalizeSubject
import com.homework.assistant.data.remote.HomeworkApi
import com.homework.assistant.data.remote.HttpStatusException
import kotlinx.coroutines.delay
import java.io.File
import java.util.concurrent.TimeUnit

/**
 * WorkManager Worker：后台执行题图上传与解析（异步提交 + 轮询模式）
 *
 * 流程：
 *  1. submitParse(imageFile, model, subject) → 获得后端 task_id
 *  2. 轮询 pollTask(backendTaskId)，间隔 2s，最多 35 次（≈70s）
 *  3. 根据 status 判断 completed / failed / timeout
 *
 * 注意：本地 Room 行以 [KEY_TASK_ID]（本地 UUID）为主键，与后端返回的 task_id 不同。
 * 提交后用后端 task_id 轮询，最终用本地 taskId 回写 DB。
 *
 * 重试语义：仅“提交阶段的网络错误”交给 WorkManager 重试 1 次；
 * 轮询超时、404（任务已过期）、后端 failed 均直接置 FAILED，不再重试。
 */
class UploadWorker(
    appContext: Context,
    params: WorkerParameters
) : CoroutineWorker(appContext, params) {

    companion object {
        const val KEY_TASK_ID = "task_id"
        const val KEY_FORCE = "force"
        private const val TAG = "UploadWorker"

        /** 轮询间隔（毫秒） */
        private const val POLL_INTERVAL_MS = 3000L
        /** 最大轮询次数（35 × 2s ≈ 70s） */
        private const val MAX_POLL_ATTEMPTS = 200

        fun enqueue(context: Context, taskId: String, force: Boolean = false) {
            val request = OneTimeWorkRequestBuilder<UploadWorker>()
                .setInputData(
                    workDataOf(
                        KEY_TASK_ID to taskId,
                        KEY_FORCE to force
                    )
                )
                .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 30, TimeUnit.SECONDS)
                .addTag("upload_$taskId")
                .build()

            // 以本地 taskId 作为唯一任务名，避免同一任务（重试 / 重新解题）并发跑多个 Worker。
            // REPLACE：新的请求会取消并替换仍在排队/运行的旧 Worker。
            WorkManager.getInstance(context).enqueueUniqueWork(
                "upload_$taskId",
                ExistingWorkPolicy.REPLACE,
                request
            )
        }
    }

    private val app = applicationContext as com.homework.assistant.HomeworkApplication
    private val repo = app.taskRepository
    private val api = HomeworkApi()
    private val settings = SettingsStore(applicationContext)
    private val gson = Gson()

    override suspend fun doWork(): Result {
        val taskId = inputData.getString(KEY_TASK_ID)
        val force = inputData.getBoolean(KEY_FORCE, false)
        if (taskId.isNullOrEmpty()) {
            Log.e(TAG, "No task_id in input")
            return Result.failure()
        }
        Log.d(TAG, "doWork start taskId=$taskId attempt=$runAttemptCount force=$force")

        val task = repo.getById(taskId)
        if (task == null) {
            Log.e(TAG, "Task $taskId not found in DB")
            return Result.failure()
        }

        val model = settings.modelName.trim()
        val displayModel = model.ifBlank { "default" }

        // 确保状态为 RUNNING，并记录本次任务实际使用的模型。
        repo.update(
            task.copy(
                status = "RUNNING",
                modelName = displayModel,
                updatedAt = System.currentTimeMillis()
            )
        )

        val imageFile = File(task.imagePath)
        if (!imageFile.exists()) {
            Log.e(TAG, "Task $taskId image not found: ${task.imagePath}")
            markFailed(taskId, "图片文件不存在")
            return Result.failure()
        }

        // 1) 提交解析请求，获得后端 task_id
        val subject = normalizeSubject(task.subject)
        val submitResult = api.submitParse(imageFile, model, subject = subject, force = force)
        val backendTaskId = submitResult.fold(
            onSuccess = { it.taskId },
            onFailure = { e ->
                Log.e(TAG, "Task $taskId submit failed: ${e.message}")
                // 提交阶段失败：网络错误允许 WorkManager 重试 1 次
                return handleSubmitFailure(taskId, e.message ?: "提交失败")
            }
        )

        if (backendTaskId.isBlank()) {
            Log.e(TAG, "Task $taskId submit returned blank backend task_id")
            return handleSubmitFailure(taskId, "提交返回的任务 ID 为空")
        }
        Log.d(TAG, "Task $taskId submitted, backendTaskId=$backendTaskId subject=$subject")

        // 2) 轮询后端任务状态
        return pollLoop(taskId, backendTaskId)
    }

    /**
     * 轮询循环：间隔 2s，最多 35 次。
     * - completed → 回写 SUCCESS（存入 ParseResult JSON）
     * - failed    → 直接 FAILED（展示 error_message）
     * - 404       → 直接 FAILED「任务已过期」
     * - 超时       → FAILED「解析超时」
     */
    private suspend fun pollLoop(localTaskId: String, backendTaskId: String): Result {
        repeat(MAX_POLL_ATTEMPTS) { attempt ->
            delay(POLL_INTERVAL_MS)

            val pollResult = api.pollTask(backendTaskId)
            val resolved = pollResult.fold(
                onSuccess = { status ->
                    when (status.status.lowercase()) {
                        "completed" -> {
                            val parseResult = status.result
                            // answer_items 是参考答案区正式契约；solution_steps 只表示过程，不能替代答案项。
                            if (
                                parseResult == null ||
                                parseResult.subject.isBlank() ||
                                parseResult.question_blocks.isEmpty() ||
                                parseResult.answer_items.isEmpty()
                            ) {
                                val msg = "后端返回缺少 subject、question_blocks 或 answer_items，请检查后端是否已部署当前 JSON v4 契约。"
                                Log.e(TAG, "Task $localTaskId invalid result: $msg")
                                markFailed(localTaskId, msg)
                                return Result.failure()
                            }
                            val resultJson = gson.toJson(parseResult)
                            Log.d(TAG, "Task $localTaskId completed, updating DB...")
                            val fresh = repo.getById(localTaskId)
                                ?: return Result.failure()
                            repo.update(
                                fresh.copy(
                                    status = "SUCCESS",
                                    resultJson = resultJson,
                                    errorMessage = null,
                                    updatedAt = System.currentTimeMillis()
                                )
                            )
                            Result.success()
                        }
                        "failed" -> {
                            val msg = status.errorMessage
                                ?: status.errorCode
                                ?: "解析失败"
                            Log.e(TAG, "Task $localTaskId failed: $msg")
                            markFailed(localTaskId, msg)
                            Result.failure()
                        }
                        // pending / processing → 继续轮询
                        else -> null
                    }
                },
                onFailure = { e ->
                    if (e is HttpStatusException && e.code == 404) {
                        Log.e(TAG, "Task $localTaskId expired (404)")
                        markFailed(localTaskId, "任务已过期")
                        Result.failure()
                    } else {
                        // 轮询期间的瞬时网络错误：记录并继续下一轮（计入轮询次数）
                        Log.w(TAG, "Task $localTaskId poll attempt ${attempt + 1} error: ${e.message}")
                        null
                    }
                }
            )

            if (resolved != null) {
                return resolved
            }
        }

        // 轮询次数耗尽仍无终态 → 本地标记超时失败
        Log.e(TAG, "Task $localTaskId polling timed out after ${MAX_POLL_ATTEMPTS * POLL_INTERVAL_MS / 1000}s")
        markFailed(localTaskId, "解析超时")
        return Result.failure()
    }

    /**
     * 提交阶段失败处理：网络错误允许重试 1 次；404 视为不可恢复直接失败。
     */
    private suspend fun handleSubmitFailure(localTaskId: String, error: String): Result {
        val task = repo.getById(localTaskId) ?: return Result.failure()
        return if (runAttemptCount < 1) {
            Log.d(TAG, "Task $localTaskId submit will retry")
            repo.update(
                task.copy(
                    status = "RUNNING",
                    errorMessage = "重试中…",
                    updatedAt = System.currentTimeMillis()
                )
            )
            Result.retry()
        } else {
            Log.d(TAG, "Task $localTaskId submit marked FAILED")
            repo.update(
                task.copy(
                    status = "FAILED",
                    errorMessage = error,
                    updatedAt = System.currentTimeMillis()
                )
            )
            Result.failure()
        }
    }

    /** 直接将本地任务标记为 FAILED（不触发重试）。 */
    private suspend fun markFailed(localTaskId: String, error: String) {
        val task = repo.getById(localTaskId) ?: return
        repo.update(
            task.copy(
                status = "FAILED",
                errorMessage = error,
                updatedAt = System.currentTimeMillis()
            )
        )
    }
}
