@file:OptIn(ExperimentalMaterial3Api::class)

package com.homework.assistant.ui.notebook

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.BorderStroke
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
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Surface
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
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import coil.compose.AsyncImage
import coil.request.ImageRequest
import com.homework.assistant.data.local.SettingsStore
import com.homework.assistant.data.model.QuestionCollection
import com.homework.assistant.data.model.subjectLabel
import com.homework.assistant.data.remote.HomeworkApi
import kotlinx.coroutines.launch
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

private val NotebookBackground = Color(0xFFF7F8FA)
private val NotebookCardBorder = Color(0xFFE3E8EF)
private val NotebookText = Color(0xFF172033)
private val NotebookMuted = Color(0xFF667085)
private val NotebookPrimary = Color(0xFF1565C0)
private val NotebookShape = RoundedCornerShape(8.dp)

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
                    items = it.items.filter { collection ->
                        collection.status.isBlank() || collection.status == "active"
                    }
                    selectedItem = selectedItem?.let { current ->
                        items.firstOrNull { item -> item.id == current.id }
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
                    items = items.filterNot { current ->
                        current.id == item.id ||
                            (current.task_block.id == item.task_block.id &&
                                current.collection_type == item.collection_type)
                    }
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

    BackHandler(enabled = selectedItem != null) {
        selectedItem = null
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
                title = { Text(if (selectedItem == null) "题集" else "题目详情") },
                navigationIcon = {
                    if (selectedItem != null) {
                        IconButton(onClick = { selectedItem = null }) {
                            Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "返回题集")
                        }
                    }
                }
            )
        },
        snackbarHost = { SnackbarHost(snackbarHostState) },
        containerColor = NotebookBackground
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
            NotebookHeader(
                studentName = studentName.ifBlank { "当前孩子" },
                selectedType = selectedType,
                totalCount = items.size,
                visibleCount = filteredItems.size
            )
            CollectionTypeSwitch(
                selectedType = selectedType,
                onSelect = { selectedType = it },
                modifier = Modifier.padding(horizontal = 16.dp)
            )
            OutlinedTextField(
                value = query,
                onValueChange = { query = it },
                label = { Text("搜索题目、答案或题解") },
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
private fun CollectionTypeSwitch(
    selectedType: String,
    onSelect: (String) -> Unit,
    modifier: Modifier = Modifier
) {
    Row(
        modifier = modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        CollectionTypeSwitchItem(
            text = "错题",
            selected = selectedType == "wrong",
            onClick = { onSelect("wrong") },
            modifier = Modifier.weight(1f)
        )
        CollectionTypeSwitchItem(
            text = "关注",
            selected = selectedType == "watched",
            onClick = { onSelect("watched") },
            modifier = Modifier.weight(1f)
        )
    }
}

@Composable
private fun CollectionTypeSwitchItem(
    text: String,
    selected: Boolean,
    onClick: () -> Unit,
    modifier: Modifier = Modifier
) {
    Surface(
        modifier = modifier
            .height(44.dp)
            .clickable(onClick = onClick),
        shape = NotebookShape,
        color = if (selected) NotebookPrimary else Color.White,
        contentColor = if (selected) Color.White else NotebookText,
        border = BorderStroke(1.dp, if (selected) NotebookPrimary else NotebookCardBorder),
        shadowElevation = if (selected) 1.dp else 0.dp
    ) {
        Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
            Text(
                text = text,
                style = MaterialTheme.typography.titleSmall,
                fontWeight = FontWeight.SemiBold
            )
        }
    }
}

@Composable
private fun NotebookHeader(
    studentName: String,
    selectedType: String,
    totalCount: Int,
    visibleCount: Int
) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp),
        shape = NotebookShape,
        colors = CardDefaults.cardColors(containerColor = Color.White),
        border = BorderStroke(1.dp, NotebookCardBorder),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp)
    ) {
        Column(
            modifier = Modifier.padding(14.dp),
            verticalArrangement = Arrangement.spacedBy(5.dp)
        ) {
            Text(
                text = "$studentName · ${if (selectedType == "wrong") "错题" else "关注"}",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold,
                color = NotebookText
            )
            Text(
                text = if (totalCount == visibleCount) "共 $totalCount 题" else "显示 $visibleCount / $totalCount 题",
                style = MaterialTheme.typography.bodySmall,
                color = NotebookMuted
            )
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
    Card(
        modifier = Modifier.fillMaxWidth().clickable(onClick = onOpen),
        shape = NotebookShape,
        colors = CardDefaults.cardColors(containerColor = Color.White),
        border = BorderStroke(1.dp, NotebookCardBorder),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp)
    ) {
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
                    color = NotebookPrimary
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
                OutlinedButton(onClick = onOpen, shape = NotebookShape) { Text("查看") }
                TextButton(onClick = onRemove) {
                    Icon(Icons.Default.Delete, contentDescription = null)
                    Text(if (item.collection_type == "wrong") "移出" else "取消关注")
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
        contentPadding = PaddingValues(horizontal = 16.dp, vertical = 14.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        item { DetailHeader(item = item) }
        cropAssetUrl?.takeIf { it.isNotBlank() }?.let { url ->
            item {
                DetailImageCard(
                    title = "题目切图",
                    assetUrl = url,
                    token = token,
                    contentDescription = "题目切图",
                    heightDp = 220
                )
            }
        }
        item {
            DetailSectionCard(
                title = "题目",
                content = block.question_text,
                emptyText = "暂无题目文本"
            )
        }
        item {
            DetailSectionCard(
                title = "答案",
                content = block.answer_text,
                emptyText = "暂无答案",
                highlight = true
            )
        }
        item {
            DetailSectionCard(
                title = "题解",
                content = block.solution_text,
                emptyText = "暂无题解"
            )
        }
        assetUrl?.takeIf { it.isNotBlank() }?.let { url ->
            item {
                DetailImageCard(
                    title = "原图",
                    assetUrl = url,
                    token = token,
                    contentDescription = "题目原图",
                    heightDp = 260
                )
            }
        }
        item {
            OutlinedButton(onClick = onRemove, modifier = Modifier.fillMaxWidth(), shape = NotebookShape) {
                Icon(Icons.Default.Delete, contentDescription = null)
                Spacer(modifier = Modifier.width(6.dp))
                Text(if (item.collection_type == "wrong") "从错题移出" else "取消关注")
            }
        }
    }
}

@Composable
private fun DetailHeader(item: QuestionCollection) {
    val block = item.task_block
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = NotebookShape,
        colors = CardDefaults.cardColors(containerColor = Color.White),
        border = BorderStroke(1.dp, NotebookCardBorder),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp)
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp)
        ) {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxWidth()) {
                Text(
                    block.title.ifBlank { "题目详情" },
                    style = MaterialTheme.typography.titleLarge,
                    fontWeight = FontWeight.SemiBold,
                    color = NotebookText,
                    modifier = Modifier.weight(1f)
                )
                CollectionTypePill(item.collection_type)
            }
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                block.subject?.takeIf { it.isNotBlank() }?.let {
                    DetailMetaPill(subjectLabel(it))
                }
                collectionTimeLabel(item.created_at).takeIf { it.isNotBlank() }?.let {
                    DetailMetaPill(it.removePrefix("加入时间："))
                }
            }
        }
    }
}

private fun collectionTimeLabel(createdAt: Long): String {
    if (createdAt <= 0) return ""
    val format = SimpleDateFormat("yyyy-MM-dd HH:mm", Locale.CHINA)
    return "加入时间：${format.format(Date(createdAt * 1000))}"
}

@Composable
private fun CollectionTypePill(type: String) {
    Surface(
        shape = NotebookShape,
        color = if (type == "wrong") Color(0xFFFFF1F0) else Color(0xFFEAF3FF),
        contentColor = if (type == "wrong") Color(0xFFD32F2F) else NotebookPrimary,
        border = BorderStroke(1.dp, if (type == "wrong") Color(0xFFFFD2CC) else Color(0xFFC7DCF5))
    ) {
        Text(
            text = if (type == "wrong") "错题" else "关注",
            modifier = Modifier.padding(horizontal = 9.dp, vertical = 4.dp),
            style = MaterialTheme.typography.labelMedium,
            fontWeight = FontWeight.SemiBold
        )
    }
}

@Composable
private fun DetailMetaPill(text: String) {
    Surface(
        shape = NotebookShape,
        color = Color(0xFFF2F4F7),
        contentColor = NotebookMuted
    ) {
        Text(
            text = text,
            modifier = Modifier.padding(horizontal = 8.dp, vertical = 3.dp),
            style = MaterialTheme.typography.labelSmall
        )
    }
}

@Composable
private fun DetailSectionCard(
    title: String,
    content: String?,
    emptyText: String,
    highlight: Boolean = false
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = NotebookShape,
        colors = CardDefaults.cardColors(containerColor = Color.White),
        border = BorderStroke(1.dp, NotebookCardBorder),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp)
    ) {
        Column(
            modifier = Modifier.padding(15.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            Text(
                title,
                style = MaterialTheme.typography.titleSmall,
                fontWeight = FontWeight.SemiBold,
                color = NotebookText
            )
            Text(
                content?.takeIf { it.isNotBlank() } ?: emptyText,
                style = MaterialTheme.typography.bodyMedium,
                color = if (highlight) Color(0xFFD32F2F) else NotebookText
            )
        }
    }
}

@Composable
private fun DetailImageCard(
    title: String,
    assetUrl: String,
    token: String,
    contentDescription: String,
    heightDp: Int
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = NotebookShape,
        colors = CardDefaults.cardColors(containerColor = Color.White),
        border = BorderStroke(1.dp, NotebookCardBorder),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp)
    ) {
        Column(
            modifier = Modifier.padding(15.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp)
        ) {
            Text(
                title,
                style = MaterialTheme.typography.titleSmall,
                fontWeight = FontWeight.SemiBold,
                color = NotebookText
            )
            AuthAssetImage(
                assetUrl = assetUrl,
                token = token,
                contentDescription = contentDescription,
                heightDp = heightDp
            )
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
