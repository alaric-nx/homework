package com.homework.assistant.data.remote

import com.google.gson.Gson
import com.homework.assistant.data.model.ParseResponse
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.asRequestBody
import java.io.File
import java.io.IOException
import java.security.SecureRandom
import java.security.cert.X509Certificate
import java.util.concurrent.TimeUnit
import javax.net.ssl.SSLContext
import javax.net.ssl.TrustManager
import javax.net.ssl.X509TrustManager

/**
 * 后端 API 客户端
 * 对接 POST /v1/homework/parse-fill?expected_type=english
 * Content-Type: image/jpeg，body 为图片二进制
 */
class HomeworkApi(
    private val baseUrl: String = "https://hs.for2.top:44443"
) {
    private val client: OkHttpClient

    init {
        val trustAll = object : X509TrustManager {
            override fun checkClientTrusted(chain: Array<X509Certificate>, authType: String) {}
            override fun checkServerTrusted(chain: Array<X509Certificate>, authType: String) {}
            override fun getAcceptedIssuers(): Array<X509Certificate> = arrayOf()
        }
        val sslContext = SSLContext.getInstance("TLS")
        sslContext.init(null, arrayOf<TrustManager>(trustAll), SecureRandom())

        client = OkHttpClient.Builder()
            .sslSocketFactory(sslContext.socketFactory, trustAll)
            .hostnameVerifier { _, _ -> true }
            .connectTimeout(15, TimeUnit.SECONDS)
            .readTimeout(120, TimeUnit.SECONDS)
            .writeTimeout(30, TimeUnit.SECONDS)
            .build()
    }

    private val gson = Gson()

    /**
     * 上传合并后的题图，返回解析结果
     */
    suspend fun parseHomework(imageFile: File): Result<ParseResponse> = withContext(Dispatchers.IO) {
        try {
            val body = imageFile.asRequestBody("image/jpeg".toMediaType())

            val request = Request.Builder()
                .url("$baseUrl/v1/homework/parse-fill?expected_type=english")
                .post(body)
                .build()

            val url = request.url.toString()
            val response = client.newCall(request).execute()
            if (!response.isSuccessful) {
                return@withContext Result.failure(
                    IOException("服务器返回 ${response.code}\n$url")
                )
            }

            val responseBody = response.body?.string()
                ?: return@withContext Result.failure(IOException("响应为空"))

            val parsed = gson.fromJson(responseBody, ParseResponse::class.java)
            Result.success(parsed)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }
}
