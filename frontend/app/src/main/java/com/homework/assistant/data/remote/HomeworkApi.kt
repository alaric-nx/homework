package com.homework.assistant.data.remote

import com.google.gson.Gson
import com.homework.assistant.data.model.ParseResponse
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.asRequestBody
import java.io.File
import java.io.IOException
import java.util.concurrent.TimeUnit

/**
 * 后端 API 客户端
 * 对接 POST /v1/homework/parse
 */
class HomeworkApi(
    private val baseUrl: String = "http://10.0.2.2:8000" // 模拟器默认指向宿主机
) {
    private val client = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .writeTimeout(30, TimeUnit.SECONDS)
        .build()

    private val gson = Gson()

    /**
     * 上传合并后的题图，返回解析结果
     */
    suspend fun parseHomework(imageFile: File): Result<ParseResponse> = withContext(Dispatchers.IO) {
        try {
            val requestBody = MultipartBody.Builder()
                .setType(MultipartBody.FORM)
                .addFormDataPart(
                    "image",
                    imageFile.name,
                    imageFile.asRequestBody("image/jpeg".toMediaType())
                )
                .build()

            val request = Request.Builder()
                .url("$baseUrl/v1/homework/parse")
                .post(requestBody)
                .build()

            val response = client.newCall(request).execute()
            if (!response.isSuccessful) {
                return@withContext Result.failure(
                    IOException("服务器返回错误: ${response.code}")
                )
            }

            val body = response.body?.string()
                ?: return@withContext Result.failure(IOException("响应为空"))

            val parsed = gson.fromJson(body, ParseResponse::class.java)
            Result.success(parsed)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }
}
