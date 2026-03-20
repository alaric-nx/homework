package com.homework.assistant.data.model

import android.net.Uri

/**
 * 裁剪后的图片片段
 */
data class CropSegment(
    val uri: Uri,
    val order: Int
)

/**
 * 后端解析响应
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
    val type: String = "word" // "word" or "sentence"
)

data class Uncertainty(
    val confidence: Float = 1.0f,
    val warning: String = "",
    val requires_review: Boolean = false
)
