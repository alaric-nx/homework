package com.homework.assistant.data.model

data class HomeworkSubject(
    val code: String,
    val label: String
)

val HomeworkSubjects = listOf(
    HomeworkSubject("general", "通用"),
    HomeworkSubject("english", "英语"),
    HomeworkSubject("liberal_arts", "文科"),
    HomeworkSubject("science", "理科")
)

fun subjectLabel(code: String): String =
    HomeworkSubjects.firstOrNull { it.code == code }?.label ?: "通用"

fun normalizeSubject(code: String): String =
    HomeworkSubjects.firstOrNull { it.code == code }?.code ?: "general"
