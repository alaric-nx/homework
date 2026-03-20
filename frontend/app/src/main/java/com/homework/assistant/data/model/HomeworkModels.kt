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
 * /v1/homework/parse-fill 外层响应
 */
data class ApiResponse(
    val result: ParseResponse = ParseResponse(),
    val filled_image_base64: String? = null,
    val filled_image_path: String? = null
)

/**
 * 后端解析响应（内层 result）
 */
data class ParseResponse(
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
    @SerializedName("unit_type")
    val type: String = "word" // "word" or "sentence"
)

data class Uncertainty(
    val confidence: Float = 1.0f,
    @SerializedName("reason")
    val warning: String? = null,
    val requires_review: Boolean = false
)
