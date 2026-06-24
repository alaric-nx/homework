package com.homework.assistant.data.local

import android.content.Context
import com.google.gson.Gson

/**
 * 应用设置的持久化存储，基于 SharedPreferences。
 *
 * 管理一组模型名称（可增删改），并始终保持其中一个为「选中模型」。
 * 解析请求会携带选中的模型名传给后端。
 *
 * 不变式：
 * - 当模型列表非空时，必有且仅有一个选中模型，且选中模型一定在列表中。
 * - 不允许删除最后一个模型，保证始终存在一个可选中项。
 * - 列表为空（仅首启动的过渡状态）时，[selectedModel] 返回空字符串，
 *   此时后端会使用其默认模型；用户添加第一个模型后会自动选中。
 */
class SettingsStore(context: Context) {

    private val prefs = context.applicationContext
        .getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
    private val gson = Gson()

    init {
        migrateLegacyIfNeeded()
    }

    /** 全部模型名称（顺序即添加顺序）。 */
    fun getModels(): List<String> {
        val raw = prefs.getString(KEY_MODELS, null)
        if (raw.isNullOrBlank()) return emptyList()
        return try {
            gson.fromJson(raw, Array<String>::class.java)?.toList() ?: emptyList()
        } catch (_: Exception) {
            emptyList()
        }
    }

    /**
     * 当前选中的模型名。列表非空时保证返回列表中的某一项；
     * 列表为空时返回空字符串（后端使用默认模型）。
     */
    fun getSelectedModel(): String {
        val models = getModels()
        if (models.isEmpty()) return ""
        val sel = prefs.getString(KEY_SELECTED, null)
        return if (sel != null && sel in models) {
            sel
        } else {
            // 选中项缺失或失效，回退到第一个并落地，维持不变式。
            models.first().also { selectModel(it) }
        }
    }

    /** 选中一个已存在的模型。 */
    fun selectModel(name: String) {
        if (name in getModels()) {
            prefs.edit().putString(KEY_SELECTED, name).apply()
        }
    }

    /**
     * 添加模型名（去空白、去重，区分大小写）。
     * @return true 添加成功；false 名称为空或已存在。
     */
    fun addModel(name: String): Boolean {
        val trimmed = name.trim()
        if (trimmed.isEmpty()) return false
        val models = getModels().toMutableList()
        if (models.contains(trimmed)) return false
        models.add(trimmed)
        saveModels(models)
        // 列表此前为空时，新加项自动成为选中模型。
        if (models.size == 1) selectModel(trimmed)
        return true
    }

    /**
     * 重命名模型名。若重命名的是当前选中项，保持其选中状态。
     * @return true 成功；false 新名为空、原名不存在或与其他项重名。
     */
    fun renameModel(oldName: String, newName: String): Boolean {
        val trimmed = newName.trim()
        if (trimmed.isEmpty()) return false
        val models = getModels().toMutableList()
        val idx = models.indexOf(oldName)
        if (idx < 0) return false
        if (trimmed != oldName && models.contains(trimmed)) return false
        models[idx] = trimmed
        saveModels(models)
        if (prefs.getString(KEY_SELECTED, null) == oldName) selectModel(trimmed)
        return true
    }

    /**
     * 删除模型名。不允许删除最后一个（保证始终有一个可选中项）。
     * 若删除的是选中项，则自动选中剩余列表的第一个。
     * @return true 删除成功；false 仅剩一个或名称不存在。
     */
    fun deleteModel(name: String): Boolean {
        val models = getModels().toMutableList()
        if (models.size <= 1) return false
        if (!models.remove(name)) return false
        saveModels(models)
        if (prefs.getString(KEY_SELECTED, null) == name) {
            selectModel(models.first())
        }
        return true
    }

    /** 兼容旧调用方（如 UploadWorker）：返回当前选中的模型名。 */
    val modelName: String
        get() = getSelectedModel()

    fun saveSession(token: String, displayName: String, tenantName: String) {
        prefs.edit()
            .putString(KEY_AUTH_TOKEN, token)
            .putString(KEY_USER_NAME, displayName)
            .putString(KEY_TENANT_NAME, tenantName)
            .apply()
    }

    fun clearSession() {
        prefs.edit()
            .remove(KEY_AUTH_TOKEN)
            .remove(KEY_USER_NAME)
            .remove(KEY_TENANT_NAME)
            .remove(KEY_CURRENT_STUDENT_ID)
            .remove(KEY_CURRENT_STUDENT_NAME)
            .remove(KEY_CURRENT_STUDENT_GRADE)
            .apply()
    }

    fun getAuthToken(): String = prefs.getString(KEY_AUTH_TOKEN, "") ?: ""

    fun getUserName(): String = prefs.getString(KEY_USER_NAME, "") ?: ""

    fun getTenantName(): String = prefs.getString(KEY_TENANT_NAME, "") ?: ""

    fun saveCurrentStudent(id: String, name: String, grade: String?) {
        prefs.edit()
            .putString(KEY_CURRENT_STUDENT_ID, id)
            .putString(KEY_CURRENT_STUDENT_NAME, name)
            .putString(KEY_CURRENT_STUDENT_GRADE, grade.orEmpty())
            .apply()
    }

    fun clearCurrentStudent() {
        prefs.edit()
            .remove(KEY_CURRENT_STUDENT_ID)
            .remove(KEY_CURRENT_STUDENT_NAME)
            .remove(KEY_CURRENT_STUDENT_GRADE)
            .apply()
    }

    fun getCurrentStudentId(): String = prefs.getString(KEY_CURRENT_STUDENT_ID, "") ?: ""

    fun getCurrentStudentName(): String = prefs.getString(KEY_CURRENT_STUDENT_NAME, "") ?: ""

    fun getCurrentStudentGrade(): String = prefs.getString(KEY_CURRENT_STUDENT_GRADE, "") ?: ""

    fun getSpeechRate(): Float {
        val value = prefs.getFloat(KEY_SPEECH_RATE, DEFAULT_SPEECH_RATE)
        return value.coerceIn(MIN_SPEECH_RATE, MAX_SPEECH_RATE)
    }

    fun saveSpeechRate(rate: Float) {
        prefs.edit()
            .putFloat(KEY_SPEECH_RATE, rate.coerceIn(MIN_SPEECH_RATE, MAX_SPEECH_RATE))
            .apply()
    }

    private fun saveModels(models: List<String>) {
        prefs.edit().putString(KEY_MODELS, gson.toJson(models)).apply()
    }

    /** 将旧版单一 model_name 迁移为模型列表（仅首次执行）。 */
    private fun migrateLegacyIfNeeded() {
        if (prefs.contains(KEY_MODELS)) return
        val legacy = prefs.getString(KEY_MODEL_NAME, "")?.trim().orEmpty()
        if (legacy.isNotEmpty()) {
            saveModels(listOf(legacy))
            prefs.edit().putString(KEY_SELECTED, legacy).apply()
        } else {
            saveModels(emptyList())
        }
    }

    companion object {
        private const val PREFS_NAME = "app_settings"
        private const val KEY_MODEL_NAME = "model_name" // 旧版单值，保留用于迁移
        private const val KEY_MODELS = "model_names"
        private const val KEY_SELECTED = "selected_model"
        private const val KEY_AUTH_TOKEN = "auth_token"
        private const val KEY_USER_NAME = "user_name"
        private const val KEY_TENANT_NAME = "tenant_name"
        private const val KEY_CURRENT_STUDENT_ID = "current_student_id"
        private const val KEY_CURRENT_STUDENT_NAME = "current_student_name"
        private const val KEY_CURRENT_STUDENT_GRADE = "current_student_grade"
        private const val KEY_SPEECH_RATE = "speech_rate"
        private const val DEFAULT_SPEECH_RATE = 0.5f
        private const val MIN_SPEECH_RATE = 0.1f
        private const val MAX_SPEECH_RATE = 1.0f
    }
}
