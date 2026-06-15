package com.homework.assistant.data.model

import android.net.Uri
import com.google.gson.annotations.SerializedName

/**
 * 裁剪后的图片片段
 */
data class CropSegment(
    val uri: Uri,
    val order: Int
)

/**
 * POST /v1/homework/parse 异步提交响应（202 Accepted）
 */
data class SubmitResponse(
    @SerializedName("task_id")
    val taskId: String = "",
    val status: String = "",
    @SerializedName("image_hash")
    val imageHash: String = ""
)

/**
 * GET /v1/homework/tasks/{task_id} 轮询响应
 * status ∈ pending / processing / completed / failed
 * completed 时 result 非空；failed 时 errorCode / errorMessage 非空
 */
data class TaskStatusResponse(
    @SerializedName("task_id")
    val taskId: String = "",
    val status: String = "",
    @SerializedName("image_hash")
    val imageHash: String = "",
    val model: String = "default",
    val result: ParseResult? = null,
    @SerializedName("error_code")
    val errorCode: String? = null,
    @SerializedName("error_message")
    val errorMessage: String? = null
)

/**
 * 解析结果（异步接口，移除 answer_placements / filled_image 相关字段）
 */
data class ParseResult(
    val question_meaning_zh: String = "",
    val reference_answer: String = "",
    val explanation_zh: String = "",
    val key_vocabulary: List<VocabularyItem> = emptyList(),
    val speak_units: List<SpeakUnit> = emptyList(),
    val uncertainty: Uncertainty = Uncertainty()
)

data class VocabularyItem(
    val word: String = "",
    val ipa: String = "",
    val meaning_zh: String = ""
)

data class SpeakUnit(
    val text: String = "",
    val meaning_zh: String? = null,
    @SerializedName("unit_type")
    val type: String = "word" // "word" or "sentence"
)

data class Uncertainty(
    val confidence: Float = 1.0f,
    @SerializedName("reason")
    val warning: String? = null,
    val requires_review: Boolean = false
)
