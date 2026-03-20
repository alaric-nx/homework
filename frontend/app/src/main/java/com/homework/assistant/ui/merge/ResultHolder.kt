package com.homework.assistant.ui.merge

import com.homework.assistant.data.model.ParseResponse

/**
 * 简单的结果持有者，用于在导航间传递解析结果
 * 生产环境建议替换为 ViewModel / SavedStateHandle
 */
object ResultHolder {
    var latestResult: ParseResponse? = null
    var filledImageBase64: String? = null
}
