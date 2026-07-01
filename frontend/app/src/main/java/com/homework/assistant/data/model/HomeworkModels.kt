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
    val meaning_zh: String? = null,
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

data class RegisterRequest(
    val username: String,
    val password: String
)

data class LoginRequest(
    val account: String,
    val password: String
)

data class AuthResponse(
    val token: String = "",
    val user: NotebookUser = NotebookUser(),
    val tenant: NotebookTenant = NotebookTenant()
)

data class MeResponse(
    val user: NotebookUser = NotebookUser(),
    val tenant: NotebookTenant = NotebookTenant()
)

data class NotebookUser(
    val id: String = "",
    val username: String = "",
    val display_name: String = "",
    val status: String = "active"
)

data class NotebookTenant(
    val id: String = "",
    val name: String = "",
    val tenant_type: String = "family",
    val status: String = "active"
)

data class Student(
    val id: String = "",
    val tenant_id: String = "",
    val name: String = "",
    val nickname: String? = null,
    val grade: String? = null,
    val school: String? = null,
    val status: String = "active"
)

data class StudentsResponse(
    val items: List<Student> = emptyList()
)

data class CreateStudentRequest(
    val name: String,
    val nickname: String? = null,
    val grade: String? = null,
    val school: String? = null
)

data class UpdateStudentRequest(
    val name: String,
    val nickname: String? = null,
    val grade: String? = null,
    val school: String? = null
)

data class CreateNotebookTaskRequest(
    val task_id: String? = null,
    val student_id: String,
    val subject: String = "general",
    val status: String = "completed",
    val original_asset_id: String? = null,
    val result: Map<String, String> = emptyMap()
)

data class AssetResponse(
    val id: String = "",
    val tenant_id: String = "",
    val owner_type: String = "",
    val owner_id: String = "",
    val asset_type: String = "",
    val storage_provider: String = "local",
    val storage_key: String = "",
    val content_type: String? = null,
    val size_bytes: Long = 0,
    val sha256: String? = null
)

data class CreateTaskBlockRequest(
    val student_id: String,
    val task_id: String,
    val source_block_id: String,
    val title: String,
    val question_text: String? = null,
    val answer_text: String? = null,
    val solution_text: String? = null,
    val bbox: Map<String, Float>? = null,
    val crop_asset_id: String? = null
)

data class SetCollectionRequest(
    val student_id: String,
    val reason: String = "manual",
    val note: String? = null
)

data class UpdateTaskBlockCropRequest(
    val student_id: String,
    val crop_asset_id: String,
    val bbox: Map<String, Float>? = null
)

data class CollectionListResponse(
    val items: List<QuestionCollection> = emptyList()
)

data class QuestionCollection(
    val id: String = "",
    val tenant_id: String = "",
    val student_id: String = "",
    val collection_type: String = "",
    val status: String = "",
    val reason: String = "",
    val note: String? = null,
    val created_at: Long = 0,
    val updated_at: Long = 0,
    val task_block: TaskBlock = TaskBlock()
)

data class TaskBlock(
    val id: String = "",
    val task_id: String = "",
    val source_block_id: String = "",
    val subject: String? = null,
    val original_asset_id: String? = null,
    val title: String = "",
    val question_text: String? = null,
    val answer_text: String? = null,
    val solution_text: String? = null,
    val crop_asset_id: String? = null,
    val is_wrong_collected: Boolean = false,
    val is_watched: Boolean = false
)
