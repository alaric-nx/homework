@file:OptIn(ExperimentalMaterial3Api::class)

package com.homework.assistant.ui.notebook

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
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
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import coil.compose.AsyncImage
import coil.request.ImageRequest
import com.homework.assistant.data.local.SettingsStore
import com.homework.assistant.data.model.QuestionCollection
import com.homework.assistant.data.model.TaskBlock
import com.homework.assistant.data.model.subjectLabel
import com.homework.assistant.data.remote.HomeworkApi
import kotlinx.coroutines.launch
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

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
    var query by remember { mutableStateOf("") }
    var selectedSubject by remember { mutableStateOf("all") }
    var selectedTimeRange by remember { mutableStateOf("all") }
    var selectedItem by remember { mutableStateOf<QuestionCollection?>(null) }
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
                .onSuccess {
                    items = it.items
                    selectedItem = selectedItem?.let { current ->
                        it.items.firstOrNull { item -> item.id == current.id }
                    }
                }
                .onFailure { snackbarHostState.showSnackbar(it.message ?: "加载失败") }
            loading = false
        }
    }

    fun removeFromCurrentCollection(item: QuestionCollection) {
        if (token.isBlank() || studentId.isBlank()) return
        scope.launch {
            api.unsetCollection(
                token = token,
                studentId = studentId,
                blockId = item.task_block.id,
                type = item.collection_type
            )
                .onSuccess {
                    snackbarHostState.showSnackbar(if (item.collection_type == "wrong") "已移出错题集" else "已取消关注")
                    selectedItem = null
                    load()
                }
                .onFailure { snackbarHostState.showSnackbar(it.message ?: "操作失败") }
        }
    }

    LaunchedEffect(selectedType, studentId) {
        selectedItem = null
        selectedSubject = "all"
        selectedTimeRange = "all"
        load()
    }

    val subjectOptions = remember(items) {
        items.mapNotNull { it.task_block.subject?.takeIf { subject -> subject.isNotBlank() } }
            .distinct()
            .sorted()
    }
    val filteredItems = remember(items, query, selectedSubject, selectedTimeRange) {
        val keyword = query.trim()
        val nowSec = System.currentTimeMillis() / 1000
        items.filter { item ->
            val block = item.task_block
            val matchesSubject = selectedSubject == "all" || block.subject == selectedSubject
            val matchesTime = when (selectedTimeRange) {
                "7d" -> item.created_at > 0 && item.created_at >= nowSec - 7L * 24 * 3600
                "30d" -> item.created_at > 0 && item.created_at >= nowSec - 30L * 24 * 3600
                else -> true
            }
            val searchable = listOf(
                block.title,
                block.question_text.orEmpty(),
                block.answer_text.orEmpty(),
                block.solution_text.orEmpty()
            ).joinToString("\n")
            val matchesKeyword = keyword.isBlank() || searchable.contains(keyword, ignoreCase = true)
            matchesSubject && matchesTime && matchesKeyword
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("${studentName.ifBlank { "当前孩子" }}的题集") },
                navigationIcon = {
                    if (selectedItem != null) {
                        IconButton(onClick = { selectedItem = null }) {
                            Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "返回题集")
                        }
                    }
                }
            )
        },
        snackbarHost = { SnackbarHost(snackbarHostState) }
    ) { padding ->
        val detail = selectedItem
        if (detail != null) {
            NotebookDetail(
                item = detail,
                token = token,
                assetUrl = detail.task_block.original_asset_id?.let { api.assetContentUrl(it) },
                cropAssetUrl = detail.task_block.crop_asset_id?.let { api.assetContentUrl(it) },
                onRemove = { removeFromCurrentCollection(detail) },
                modifier = Modifier.fillMaxSize().padding(padding)
            )
            return@Scaffold
        }

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
            OutlinedTextField(
                value = query,
                onValueChange = { query = it },
                label = { Text("搜索题目、答案、题解") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp)
            )
            if (subjectOptions.isNotEmpty()) {
                Row(
                    modifier = Modifier.padding(horizontal = 16.dp),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    FilterChip(
                        selected = selectedSubject == "all",
                        onClick = { selectedSubject = "all" },
                        label = { Text("全部学科") }
                    )
                    subjectOptions.forEach { subject ->
                        FilterChip(
                            selected = selectedSubject == subject,
                            onClick = { selectedSubject = subject },
                            label = { Text(subjectLabel(subject)) }
                        )
                    }
                }
            }
            Row(
                modifier = Modifier.padding(horizontal = 16.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                FilterChip(
                    selected = selectedTimeRange == "all",
                    onClick = { selectedTimeRange = "all" },
                    label = { Text("全部时间") }
                )
                FilterChip(
                    selected = selectedTimeRange == "7d",
                    onClick = { selectedTimeRange = "7d" },
                    label = { Text("近7天") }
                )
                FilterChip(
                    selected = selectedTimeRange == "30d",
                    onClick = { selectedTimeRange = "30d" },
                    label = { Text("近30天") }
                )
            }

            when {
                studentId.isBlank() -> EmptyState("请先到设置页添加并选择孩子")
                loading -> EmptyState("加载中...")
                items.isEmpty() -> EmptyState(if (selectedType == "wrong") "暂无错题" else "暂无关注题")
                filteredItems.isEmpty() -> EmptyState("没有匹配的题目")
                else -> LazyColumn(
                    modifier = Modifier.fillMaxSize(),
                    contentPadding = PaddingValues(horizontal = 16.dp, vertical = 4.dp),
                    verticalArrangement = Arrangement.spacedBy(10.dp)
                ) {
                    items(filteredItems, key = { it.id }) { item ->
                        CollectionCard(
                            item = item,
                            onOpen = { selectedItem = item },
                            onRemove = { removeFromCurrentCollection(item) }
                        )
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
private fun CollectionCard(
    item: QuestionCollection,
    onOpen: () -> Unit,
    onRemove: () -> Unit
) {
    val block = item.task_block
    Card(modifier = Modifier.fillMaxWidth().clickable(onClick = onOpen)) {
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
            block.subject?.takeIf { it.isNotBlank() }?.let {
                Text(
                    subjectLabel(it),
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
            collectionTimeLabel(item.created_at).takeIf { it.isNotBlank() }?.let {
                Text(
                    it,
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
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
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(onClick = onOpen) { Text("查看详情") }
                TextButton(onClick = onRemove) {
                    Icon(Icons.Default.Delete, contentDescription = null)
                    Text(if (item.collection_type == "wrong") "移出错题" else "取消关注")
                }
            }
        }
    }
}

@Composable
private fun NotebookDetail(
    item: QuestionCollection,
    token: String,
    assetUrl: String?,
    cropAssetUrl: String?,
    onRemove: () -> Unit,
    modifier: Modifier = Modifier
) {
    val block = item.task_block
    LazyColumn(
        modifier = modifier,
        contentPadding = PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        item {
            Card(modifier = Modifier.fillMaxWidth()) {
                Column(
                    modifier = Modifier.padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp)
                ) {
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxWidth()) {
                        Text(
                            block.title.ifBlank { "题目详情" },
                            style = MaterialTheme.typography.titleLarge,
                            fontWeight = FontWeight.SemiBold,
                            modifier = Modifier.weight(1f)
                        )
                        Text(
                            if (item.collection_type == "wrong") "错题" else "关注",
                            color = MaterialTheme.colorScheme.primary,
                            style = MaterialTheme.typography.labelLarge
                        )
                    }
                    block.subject?.takeIf { it.isNotBlank() }?.let {
                        Text(subjectLabel(it), color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                    collectionTimeLabel(item.created_at).takeIf { it.isNotBlank() }?.let {
                        Text(it, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                    DetailSection(title = "题目", content = block.question_text)
                    DetailSection(title = "答案", content = block.answer_text, highlight = true)
                    DetailSection(title = "题解", content = block.solution_text)
                    OriginalImageSection(assetUrl = assetUrl, token = token)
                    CropImageSection(block = block, assetUrl = cropAssetUrl, token = token)
                    Spacer(modifier = Modifier.height(4.dp))
                    Button(onClick = onRemove, modifier = Modifier.fillMaxWidth()) {
                        Text(if (item.collection_type == "wrong") "移出错题集" else "取消关注")
                    }
                }
            }
        }
    }
}

@Composable
private fun OriginalImageSection(assetUrl: String?, token: String) {
    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
        HorizontalDivider()
        Text("题目原图", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold)
        if (assetUrl.isNullOrBlank()) {
            Text("暂无原图资产", color = MaterialTheme.colorScheme.onSurfaceVariant)
        } else {
            AuthAssetImage(assetUrl = assetUrl, token = token, contentDescription = "题目原图", heightDp = 260)
        }
    }
}

private fun collectionTimeLabel(createdAt: Long): String {
    if (createdAt <= 0) return ""
    val format = SimpleDateFormat("yyyy-MM-dd HH:mm", Locale.CHINA)
    return "加入时间：${format.format(Date(createdAt * 1000))}"
}

@Composable
private fun DetailSection(title: String, content: String?, highlight: Boolean = false) {
    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
        HorizontalDivider()
        Text(title, style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold)
        Text(
            content?.takeIf { it.isNotBlank() } ?: "暂无",
            color = if (highlight) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurface
        )
    }
}

@Composable
private fun CropImageSection(block: TaskBlock, assetUrl: String?, token: String) {
    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
        HorizontalDivider()
        Text("题目切图", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold)
        if (assetUrl.isNullOrBlank()) {
            Text("暂未生成独立题目切图", color = MaterialTheme.colorScheme.onSurfaceVariant)
        } else {
            AuthAssetImage(assetUrl = assetUrl, token = token, contentDescription = "题目切图", heightDp = 220)
        }
    }
}

@Composable
private fun AuthAssetImage(
    assetUrl: String,
    token: String,
    contentDescription: String,
    heightDp: Int
) {
    val context = LocalContext.current
    AsyncImage(
        model = ImageRequest.Builder(context)
            .data(assetUrl)
            .addHeader("Authorization", "Bearer $token")
            .crossfade(true)
            .build(),
        contentDescription = contentDescription,
        contentScale = ContentScale.Fit,
        modifier = Modifier
            .fillMaxWidth()
            .height(heightDp.dp)
    )
}
