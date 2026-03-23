package com.homework.assistant.data.local

import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "tasks")
data class TaskEntity(
    @PrimaryKey val id: String,
    val status: String,          // PENDING, RUNNING, SUCCESS, FAILED
    val thumbnailPath: String,   // 缩略图路径（合并后小图）
    val imagePath: String,       // 上传用的压缩图路径
    val resultJson: String? = null,
    val filledImageBase64: String? = null,
    val errorMessage: String? = null,
    val createdAt: Long = System.currentTimeMillis(),
    val updatedAt: Long = System.currentTimeMillis()
)
