package com.homework.assistant.data.remote

import com.google.gson.Gson
import com.homework.assistant.data.model.SubmitResponse
import com.homework.assistant.data.model.TaskStatusResponse
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.asRequestBody
import java.io.File
import java.io.IOException
import java.net.URLEncoder
import java.security.SecureRandom
import java.security.cert.X509Certificate
import java.util.concurrent.TimeUnit
import javax.net.ssl.SSLContext
import javax.net.ssl.TrustManager
import javax.net.ssl.X509TrustManager

/**
 * HTTP 状态异常，携带后端返回的状态码，便于调用方区分 404（任务已过期）等场景。
 */
class HttpStatusException(val code: Int, message: String) : IOException(message)

/**
 * 后端 API 客户端（异步提交 + 轮询模式）
 * - POST /v1/homework/parse?subject=xxx&model=xxx  Content-Type: image/jpeg，body 为图片二进制 → 202 SubmitResponse
 * - GET  /v1/homework/tasks/{task_id}  → 200 TaskStatusResponse / 404 TASK_NOT_FOUND
 */
class HomeworkApi(
    private val baseUrl: String = "https://hs.for2.top:44443"
) {
    private val gson = Gson()

    companion object {
        /**
         * 共享的 OkHttpClient：复用连接池与线程资源。
         * 之前每次 new HomeworkApi() 都会重建 client + SSLContext，浪费连接池且开销大。
         */
        private val sharedClient: OkHttpClient by lazy {
            val trustAll = object : X509TrustManager {
                override fun checkClientTrusted(chain: Array<X509Certificate>, authType: String) {}
                override fun checkServerTrusted(chain: Array<X509Certificate>, authType: String) {}
                override fun getAcceptedIssuers(): Array<X509Certificate> = arrayOf()
            }
            val sslContext = SSLContext.getInstance("TLS")
            sslContext.init(null, arrayOf<TrustManager>(trustAll), SecureRandom())

            OkHttpClient.Builder()
                .sslSocketFactory(sslContext.socketFactory, trustAll)
                .hostnameVerifier { _, _ -> true }
                .connectTimeout(15, TimeUnit.SECONDS)
                .readTimeout(120, TimeUnit.SECONDS)
                .writeTimeout(30, TimeUnit.SECONDS)
                .build()
        }
    }

    private val client: OkHttpClient get() = sharedClient

    /**
     * 异步提交解析请求：上传题图二进制，立即返回 task_id。
     * @param imageFile 合并压缩后的题图（JPEG）
     * @param model     指定模型名称，可为空字符串（为空时省略 model query 参数，由后端使用默认模型）
     * @param subject   学科分类：general / english / liberal_arts / science
     * @param force     是否强制重新解析（跳过缓存直接算）
     */
    suspend fun submitParse(
        imageFile: File,
        model: String,
        subject: String,
        force: Boolean = false
    ): Result<SubmitResponse> =
        withContext(Dispatchers.IO) {
            try {
                val body = imageFile.asRequestBody("image/jpeg".toMediaType())

                val urlBuilder = StringBuilder("$baseUrl/v1/homework/parse")
                val queryParams = mutableListOf(
                    "subject=${URLEncoder.encode(subject, "UTF-8")}"
                )
                if (model.isNotBlank()) {
                    queryParams.add("model=${URLEncoder.encode(model, "UTF-8")}")
                }
                if (force) {
                    queryParams.add("force=true")
                }
                if (queryParams.isNotEmpty()) {
                    urlBuilder.append("?").append(queryParams.joinToString("&"))
                }
                val url = urlBuilder.toString()

                val request = Request.Builder()
                    .url(url)
                    .post(body)
                    .build()

                val response = client.newCall(request).execute()
                if (!response.isSuccessful) {
                    return@withContext Result.failure(
                        HttpStatusException(response.code, "服务器返回 ${response.code}\n$url")
                    )
                }

                val responseBody = response.body?.string()
                    ?: return@withContext Result.failure(IOException("响应为空"))

                val parsed = gson.fromJson(responseBody, SubmitResponse::class.java)
                Result.success(parsed)
            } catch (e: Exception) {
                Result.failure(e)
            }
        }

    /**
     * 轮询任务状态。
     * @param taskId 提交阶段返回的 task_id
     * @return 成功时返回 TaskStatusResponse；任务不存在时 failure 为 HttpStatusException(code = 404)
     */
    suspend fun pollTask(taskId: String): Result<TaskStatusResponse> =
        withContext(Dispatchers.IO) {
            try {
                val url = "$baseUrl/v1/homework/tasks/" +
                    URLEncoder.encode(taskId, "UTF-8")

                val request = Request.Builder()
                    .url(url)
                    .get()
                    .build()

                val response = client.newCall(request).execute()
                if (!response.isSuccessful) {
                    return@withContext Result.failure(
                        HttpStatusException(response.code, "服务器返回 ${response.code}\n$url")
                    )
                }

                val responseBody = response.body?.string()
                    ?: return@withContext Result.failure(IOException("响应为空"))

                val parsed = gson.fromJson(responseBody, TaskStatusResponse::class.java)
                Result.success(parsed)
            } catch (e: Exception) {
                Result.failure(e)
            }
        }

    /**
     * 联动删除后端的任务缓存（内存与本地磁盘文件）。
     * @param taskId 任务 ID（图片的 MD5 哈希值）
     */
    suspend fun deleteTask(taskId: String): Result<Unit> =
        withContext(Dispatchers.IO) {
            try {
                val url = "$baseUrl/v1/homework/tasks/" +
                    URLEncoder.encode(taskId, "UTF-8")

                val request = Request.Builder()
                    .url(url)
                    .delete()
                    .build()

                val response = client.newCall(request).execute()
                if (!response.isSuccessful) {
                    return@withContext Result.failure(
                        HttpStatusException(response.code, "删除失败，服务器返回 ${response.code}\n$url")
                    )
                }
                Result.success(Unit)
            } catch (e: Exception) {
                Result.failure(e)
            }
        }
}
