package com.homework.assistant.data.local

import android.content.Context

/**
 * 应用设置的持久化存储，基于 SharedPreferences。
 *
 * 目前用于保存用户配置的模型名称（modelName），解析请求会携带该值传给后端。
 * 若未配置，默认返回空字符串（请求时可省略 model 参数）。
 */
class SettingsStore(context: Context) {

    private val prefs = context.applicationContext
        .getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)

    /** 用户配置的模型名称。读写均落地到 SharedPreferences，默认空字符串。 */
    var modelName: String
        get() = prefs.getString(KEY_MODEL_NAME, "") ?: ""
        set(value) {
            prefs.edit().putString(KEY_MODEL_NAME, value).apply()
        }

    companion object {
        private const val PREFS_NAME = "app_settings"
        private const val KEY_MODEL_NAME = "model_name"
    }
}
