package com.homework.assistant.data.local

import androidx.room.*
import kotlinx.coroutines.flow.Flow

@Dao
interface TaskDao {

    @Query("SELECT * FROM tasks ORDER BY createdAt DESC")
    fun observeAll(): Flow<List<TaskEntity>>

    @Query("SELECT * FROM tasks WHERE id = :id")
    suspend fun getById(id: String): TaskEntity?

    @Upsert
    suspend fun upsert(task: TaskEntity)

    @Query("DELETE FROM tasks WHERE id = :id")
    suspend fun deleteById(id: String)

    @Query("DELETE FROM tasks")
    suspend fun deleteAll()

    @Query("SELECT COUNT(*) FROM tasks")
    suspend fun count(): Int

    /** 获取最早的任务（用于超限淘汰） */
    @Query("SELECT * FROM tasks ORDER BY createdAt ASC LIMIT 1")
    suspend fun oldest(): TaskEntity?
}
