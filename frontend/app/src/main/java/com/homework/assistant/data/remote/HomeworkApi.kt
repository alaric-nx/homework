package com.homework.assistant.data.remote

import com.google.gson.Gson
import com.homework.assistant.data.model.AssetResponse
import com.homework.assistant.data.model.AuthResponse
import com.homework.assistant.data.model.CollectionListResponse
import com.homework.assistant.data.model.CreateNotebookTaskRequest
import com.homework.assistant.data.model.CreateStudentRequest
import com.homework.assistant.data.model.CreateTaskBlockRequest
import com.homework.assistant.data.model.LoginRequest
import com.homework.assistant.data.model.MeResponse
import com.homework.assistant.data.model.RegisterRequest
import com.homework.assistant.data.model.SetCollectionRequest
import com.homework.assistant.data.model.Student
import com.homework.assistant.data.model.StudentsResponse
import com.homework.assistant.data.model.TaskBlock
import com.homework.assistant.data.model.SubmitResponse
import com.homework.assistant.data.model.TaskStatusResponse
import com.homework.assistant.data.model.UpdateStudentRequest
import com.homework.assistant.data.model.UpdateTaskBlockCropRequest
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
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
    private val jsonMediaType = "application/json; charset=utf-8".toMediaType()

    suspend fun register(
        username: String,
        password: String
    ): Result<AuthResponse> =
        postJson(
            path = "/v1/auth/register",
            body = RegisterRequest(
                username = username,
                password = password
            ),
            responseClass = AuthResponse::class.java
        )

    suspend fun login(account: String, password: String): Result<AuthResponse> =
        postJson(
            path = "/v1/auth/login",
            body = LoginRequest(account = account, password = password),
            responseClass = AuthResponse::class.java
        )

    suspend fun me(token: String): Result<MeResponse> =
        getJson(
            path = "/v1/auth/me",
            token = token,
            responseClass = MeResponse::class.java
        )

    suspend fun listStudents(token: String): Result<StudentsResponse> =
        getJson(
            path = "/v1/students",
            token = token,
            responseClass = StudentsResponse::class.java
        )

    suspend fun createStudent(
        token: String,
        name: String,
        grade: String
    ): Result<Student> =
        postJson(
            path = "/v1/students",
            token = token,
            body = CreateStudentRequest(name = name, grade = grade.ifBlank { null }),
            responseClass = Student::class.java
        )

    suspend fun uploadAsset(
        token: String,
        ownerType: String,
        ownerId: String,
        assetType: String,
        file: File,
        contentType: String = "image/jpeg"
    ): Result<AssetResponse> =
        withContext(Dispatchers.IO) {
            try {
                val url = "$baseUrl/v1/assets" +
                    "?owner_type=${URLEncoder.encode(ownerType, "UTF-8")}" +
                    "&owner_id=${URLEncoder.encode(ownerId, "UTF-8")}" +
                    "&asset_type=${URLEncoder.encode(assetType, "UTF-8")}"
                val request = Request.Builder()
                    .url(url)
                    .addAuth(token)
                    .post(file.asRequestBody(contentType.toMediaType()))
                    .build()
                val response = client.newCall(request).execute()
                if (!response.isSuccessful) {
                    return@withContext Result.failure(
                        HttpStatusException(response.code, "服务器返回 ${response.code}\n$url")
                    )
                }
                val responseBody = response.body?.string()
                    ?: return@withContext Result.failure(IOException("响应为空"))
                Result.success(gson.fromJson(responseBody, AssetResponse::class.java))
            } catch (e: Exception) {
                Result.failure(e)
            }
        }

    fun assetContentUrl(assetId: String): String =
        "$baseUrl/v1/assets/${URLEncoder.encode(assetId, "UTF-8")}/content"

    suspend fun updateStudent(
        token: String,
        studentId: String,
        name: String,
        grade: String
    ): Result<Student> =
        patchJson(
            path = "/v1/students/${URLEncoder.encode(studentId, "UTF-8")}",
            token = token,
            body = UpdateStudentRequest(name = name, grade = grade.ifBlank { null }),
            responseClass = Student::class.java
        )

    suspend fun deleteStudent(token: String, studentId: String): Result<Unit> =
        withContext(Dispatchers.IO) {
            try {
                val url = "$baseUrl/v1/students/${URLEncoder.encode(studentId, "UTF-8")}"
                val request = Request.Builder()
                    .url(url)
                    .addAuth(token)
                    .delete()
                    .build()
                val response = client.newCall(request).execute()
                if (!response.isSuccessful) {
                    return@withContext Result.failure(
                        HttpStatusException(response.code, "服务器返回 ${response.code}\n$url")
                    )
                }
                Result.success(Unit)
            } catch (e: Exception) {
                Result.failure(e)
            }
        }

    suspend fun listCollections(
        token: String,
        studentId: String,
        type: String
    ): Result<CollectionListResponse> =
        getJson(
            path = "/v1/question-collections?type=${URLEncoder.encode(type, "UTF-8")}" +
                "&student_id=${URLEncoder.encode(studentId, "UTF-8")}",
            token = token,
            responseClass = CollectionListResponse::class.java
        )

    suspend fun createNotebookTask(
        token: String,
        studentId: String,
        taskId: String,
        subject: String,
        originalAssetId: String? = null
    ): Result<Map<*, *>> =
        postJson(
            path = "/v1/notebook/tasks",
            token = token,
            body = CreateNotebookTaskRequest(
                task_id = taskId,
                student_id = studentId,
                subject = subject,
                original_asset_id = originalAssetId?.takeIf { it.isNotBlank() },
                result = emptyMap()
            ),
            responseClass = Map::class.java
        )

    suspend fun createTaskBlock(
        token: String,
        studentId: String,
        taskId: String,
        sourceBlockId: String,
        title: String,
        questionText: String?,
        answerText: String?,
        solutionText: String?
    ): Result<TaskBlock> =
        postJson(
            path = "/v1/task-blocks",
            token = token,
            body = CreateTaskBlockRequest(
                student_id = studentId,
                task_id = taskId,
                source_block_id = sourceBlockId,
                title = title,
                question_text = questionText,
                answer_text = answerText,
                solution_text = solutionText
            ),
            responseClass = TaskBlock::class.java
        )

    suspend fun getTaskBlock(
        token: String,
        studentId: String,
        blockId: String
    ): Result<TaskBlock> =
        getJson(
            path = "/v1/task-blocks/${URLEncoder.encode(blockId, "UTF-8")}" +
                "?student_id=${URLEncoder.encode(studentId, "UTF-8")}",
            token = token,
            responseClass = TaskBlock::class.java
        )

    suspend fun updateTaskBlockCrop(
        token: String,
        studentId: String,
        blockId: String,
        cropAssetId: String,
        bbox: Map<String, Float>? = null
    ): Result<TaskBlock> =
        patchJson(
            path = "/v1/task-blocks/${URLEncoder.encode(blockId, "UTF-8")}/crop",
            token = token,
            body = UpdateTaskBlockCropRequest(
                student_id = studentId,
                crop_asset_id = cropAssetId,
                bbox = bbox
            ),
            responseClass = TaskBlock::class.java
        )

    suspend fun setCollection(
        token: String,
        studentId: String,
        blockId: String,
        type: String
    ): Result<Unit> =
        postJson(
            path = "/v1/task-blocks/${URLEncoder.encode(blockId, "UTF-8")}/collections/" +
                URLEncoder.encode(type, "UTF-8"),
            token = token,
            body = SetCollectionRequest(student_id = studentId),
            responseClass = UnitResponse::class.java
        ).map { Unit }

    suspend fun unsetCollection(
        token: String,
        studentId: String,
        blockId: String,
        type: String
    ): Result<Unit> =
        withContext(Dispatchers.IO) {
            try {
                val url = "$baseUrl/v1/task-blocks/${URLEncoder.encode(blockId, "UTF-8")}/collections/" +
                    "${URLEncoder.encode(type, "UTF-8")}?student_id=${URLEncoder.encode(studentId, "UTF-8")}"
                val request = Request.Builder()
                    .url(url)
                    .addAuth(token)
                    .delete()
                    .build()
                val response = client.newCall(request).execute()
                if (!response.isSuccessful) {
                    return@withContext Result.failure(
                        HttpStatusException(response.code, "服务器返回 ${response.code}\n$url")
                    )
                }
                Result.success(Unit)
            } catch (e: Exception) {
                Result.failure(e)
            }
        }

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

    private suspend fun <T : Any> postJson(
        path: String,
        body: Any,
        responseClass: Class<T>,
        token: String = ""
    ): Result<T> =
        withContext(Dispatchers.IO) {
            try {
                val url = "$baseUrl$path"
                val request = Request.Builder()
                    .url(url)
                    .addAuth(token)
                    .post(gson.toJson(body).toRequestBody(jsonMediaType))
                    .build()
                val response = client.newCall(request).execute()
                if (!response.isSuccessful) {
                    return@withContext Result.failure(
                        HttpStatusException(response.code, "服务器返回 ${response.code}\n$url")
                    )
                }
                val responseBody = response.body?.string()
                    ?: return@withContext Result.failure(IOException("响应为空"))
                Result.success(gson.fromJson(responseBody, responseClass))
            } catch (e: Exception) {
                Result.failure(e)
            }
        }

    private suspend fun <T : Any> patchJson(
        path: String,
        body: Any,
        responseClass: Class<T>,
        token: String = ""
    ): Result<T> =
        withContext(Dispatchers.IO) {
            try {
                val url = "$baseUrl$path"
                val request = Request.Builder()
                    .url(url)
                    .addAuth(token)
                    .patch(gson.toJson(body).toRequestBody(jsonMediaType))
                    .build()
                val response = client.newCall(request).execute()
                if (!response.isSuccessful) {
                    return@withContext Result.failure(
                        HttpStatusException(response.code, "服务器返回 ${response.code}\n$url")
                    )
                }
                val responseBody = response.body?.string()
                    ?: return@withContext Result.failure(IOException("响应为空"))
                Result.success(gson.fromJson(responseBody, responseClass))
            } catch (e: Exception) {
                Result.failure(e)
            }
        }

    private suspend fun <T : Any> getJson(
        path: String,
        responseClass: Class<T>,
        token: String = ""
    ): Result<T> =
        withContext(Dispatchers.IO) {
            try {
                val url = "$baseUrl$path"
                val request = Request.Builder()
                    .url(url)
                    .addAuth(token)
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
                Result.success(gson.fromJson(responseBody, responseClass))
            } catch (e: Exception) {
                Result.failure(e)
            }
        }

    private fun Request.Builder.addAuth(token: String): Request.Builder {
        if (token.isNotBlank()) {
            header("Authorization", "Bearer $token")
        }
        return this
    }

    private data class UnitResponse(val status: String = "")
}
