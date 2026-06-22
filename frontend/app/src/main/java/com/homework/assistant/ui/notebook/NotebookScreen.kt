@file:OptIn(ExperimentalMaterial3Api::class)

package com.homework.assistant.ui.notebook

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Card
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.homework.assistant.data.local.SettingsStore
import com.homework.assistant.data.model.QuestionCollection
import com.homework.assistant.data.remote.HomeworkApi
import kotlinx.coroutines.launch

@Composable
fun NotebookScreen(studentId: String) {
    val context = androidx.compose.ui.platform.LocalContext.current
    val settingsStore = remember { SettingsStore(context) }
    val api = remember { HomeworkApi() }
    val scope = rememberCoroutineScope()
    val snackbarHostState = remember { SnackbarHostState() }

    var selectedType by remember { mutableStateOf("wrong") }
    var items by remember { mutableStateOf<List<QuestionCollection>>(emptyList()) }
    var loading by remember { mutableStateOf(false) }
    val token = settingsStore.getAuthToken()
    val studentName = settingsStore.getCurrentStudentName()

    fun load() {
        if (token.isBlank() || studentId.isBlank()) {
            items = emptyList()
            return
        }
        loading = true
        scope.launch {
            api.listCollections(token = token, studentId = studentId, type = selectedType)
                .onSuccess { items = it.items }
                .onFailure { snackbarHostState.showSnackbar(it.message ?: "加载失败") }
            loading = false
        }
    }

    LaunchedEffect(selectedType, studentId) {
        load()
    }

    Scaffold(
        topBar = { TopAppBar(title = { Text("${studentName.ifBlank { "当前孩子" }}的题集") }) },
        snackbarHost = { SnackbarHost(snackbarHostState) }
    ) { padding ->
        Column(
            modifier = Modifier.fillMaxSize().padding(padding),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            Row(
                modifier = Modifier.padding(horizontal = 16.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                FilterChip(
                    selected = selectedType == "wrong",
                    onClick = { selectedType = "wrong" },
                    label = { Text("错题集") }
                )
                FilterChip(
                    selected = selectedType == "watched",
                    onClick = { selectedType = "watched" },
                    label = { Text("关注") }
                )
            }

            when {
                studentId.isBlank() -> EmptyState("请先到设置页添加并选择孩子")
                loading -> EmptyState("加载中...")
                items.isEmpty() -> EmptyState(if (selectedType == "wrong") "暂无错题" else "暂无关注题")
                else -> LazyColumn(
                    modifier = Modifier.fillMaxSize(),
                    contentPadding = PaddingValues(horizontal = 16.dp, vertical = 4.dp),
                    verticalArrangement = Arrangement.spacedBy(10.dp)
                ) {
                    items(items, key = { it.id }) { item ->
                        CollectionCard(item)
                    }
                }
            }
        }
    }
}

@Composable
private fun EmptyState(text: String) {
    Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
        Text(text, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@Composable
private fun CollectionCard(item: QuestionCollection) {
    val block = item.task_block
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(
            modifier = Modifier.padding(14.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxWidth()) {
                Text(
                    block.title.ifBlank { "题目" },
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.SemiBold,
                    modifier = Modifier.weight(1f)
                )
                Text(
                    if (item.collection_type == "wrong") "错题" else "关注",
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.primary
                )
            }
            block.question_text?.takeIf { it.isNotBlank() }?.let {
                Text(it, maxLines = 3, overflow = TextOverflow.Ellipsis)
            }
            block.answer_text?.takeIf { it.isNotBlank() }?.let {
                Text("答案：$it", color = MaterialTheme.colorScheme.error)
            }
            block.solution_text?.takeIf { it.isNotBlank() }?.let {
                Text(
                    "题解：$it",
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }
    }
}
