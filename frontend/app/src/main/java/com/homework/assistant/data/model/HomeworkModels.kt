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
 * 解析结果 JSON v3（异步接口，使用 answer_lines / learning_points / read_units）
 */
data class ParseResult(
    val subject: String = "general",
    val question_meaning_zh: String = "",
    val question_instruction: QuestionInstruction = QuestionInstruction(),
    val question_blocks: List<QuestionBlock> = emptyList(),
    val answer_lines: List<AnswerLine> = emptyList(),
    val solution_steps: List<SolutionStep> = emptyList(),
    val explanation_zh: String = "",
    val learning_points: List<LearningPoint> = emptyList(),
    val read_units: List<ReadUnit> = emptyList(),
    val uncertainty: Uncertainty = Uncertainty()
)

data class QuestionInstruction(
    val text: String = "",
    val meaning_zh: String = "",
    val confidence: Float = 0.0f
)

data class QuestionBlock(
    val block_id: String = "",
    val title: String = "",
    val question_instruction: QuestionInstruction = QuestionInstruction(),
    val question_meaning_zh: String = ""
)

data class AnswerLine(
    val block_id: String = "",
    val number: String? = null,
    val line_type: String = "other",
    val plain_text: String = "",
    val segments: List<AnswerSegment> = emptyList()
)

data class AnswerSegment(
    val text: String = "",
    val role: String = "answer"
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

data class ReadUnit(
    val block_id: String? = null,
    @SerializedName("unit_type")
    val unit_type: String = "text",
    val label: String? = null,
    val text: String = "",
    val meaning_zh: String? = null
)

data class Uncertainty(
    val confidence: Float = 1.0f,
    @SerializedName("reason")
    val warning: String? = null,
    val requires_review: Boolean = false
)
