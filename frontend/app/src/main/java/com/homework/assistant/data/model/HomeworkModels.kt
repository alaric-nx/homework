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
    val imageHash: String = "",
    val subject: String = "general"
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
    val subject: String = "general",
    val result: ParseResult? = null,
    @SerializedName("error_code")
    val errorCode: String? = null,
    @SerializedName("error_message")
    val errorMessage: String? = null
)

/**
 * 解析结果 JSON v4（题面内容、答案项、学生答案批改分层展示）
 */
data class ParseResult(
    val schema_version: String = "4.0",
    val subject: String = "general",
    val question_meaning_zh: String = "",
    val question_blocks: List<QuestionBlock> = emptyList(),
    val answer_items: List<AnswerItem> = emptyList(),
    val student_answer_reviews: List<StudentAnswerReview> = emptyList(),
    val solution_steps: List<SolutionStep> = emptyList(),
    val explanation_zh: String = "",
    val learning_points: List<LearningPoint> = emptyList(),
    val uncertainty: Uncertainty = Uncertainty()
)

data class QuestionBlock(
    val block_id: String = "",
    val order: Int = 0,
    val title: String = "",
    val question_meaning_zh: String = "",
    val content_items: List<ContentItem> = emptyList()
)

data class ContentItem(
    val item_id: String = "",
    val order: Int = 0,
    val group_id: String? = null,
    val type: String = "other",
    val text: String = "",
    val meaning_zh: String? = null,
    val language: String = "unknown",
    val speak_text: String? = null,
    val speakable: Boolean = true
)

data class AnswerItem(
    val answer_id: String = "",
    val block_id: String = "",
    val order: Int = 0,
    val number: String? = null,
    val answer_type: String = "other",
    val plain_text: String = "",
    val speak_text: String? = null,
    val display: AnswerDisplay = AnswerDisplay()
)

data class AnswerDisplay(
    val mode: String = "inline_segments",
    val format: String = "plain_text",
    val latex: String? = null,
    val preserve_newlines: Boolean = false,
    val runs: List<DisplayRun> = emptyList()
)

data class DisplayRun(
    val text: String = "",
    val role: String = "answer"
)

data class StudentAnswerReview(
    val review_id: String = "",
    val block_id: String = "",
    val answer_id: String? = null,
    val order: Int = 0,
    val number: String? = null,
    val student_answer: String? = null,
    val correct_answer: String? = null,
    val status: String = "unclear",
    val feedback_zh: String = "",
    val confidence: Float = 0.0f
)

data class SolutionStep(
    val block_id: String = "",
    val number: String = "",
    val title: String = "",
    val content_zh: String = "",
    val formula: String? = null,
    val result: String? = null
)

data class LearningPoint(
    val block_id: String? = null,
    val term: String = "",
    val explanation_zh: String = "",
    val pronunciation: String? = null,
    val category: String = "other",
    val label: String? = null
)

data class Uncertainty(
    val confidence: Float = 1.0f,
    @SerializedName("reason")
    val warning: String? = null,
    val requires_review: Boolean = false
)
