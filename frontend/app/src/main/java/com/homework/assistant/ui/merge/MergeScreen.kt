package com.homework.assistant.ui.merge

import android.graphics.Bitmap
import android.net.Uri
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Crop
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.KeyboardArrowDown
import androidx.compose.material.icons.filled.KeyboardArrowUp
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import coil.compose.AsyncImage
import com.homework.assistant.R
import com.homework.assistant.data.remote.HomeworkApi
import com.homework.assistant.util.ImageUtils
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MergeScreen(
    segments: MutableList<Uri>,
    originalUris: MutableList<Uri>,
    onAddMore: () -> Unit,
    onCropItem: (Int) -> Unit,
    onUploadComplete: () -> Unit,
    onBack: () -> Unit
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var isUploading by remember { mutableStateOf(false) }
    var errorMessage by remember { mutableStateOf<String?>(null) }

    // 合并预览状态
    var showPreview by remember { mutableStateOf(false) }
    var previewBitmap by remember { mutableStateOf<Bitmap?>(null) }
    var mergedFile by remember { mutableStateOf<java.io.File?>(null) }

    fun swapItems(from: Int, to: Int) {
        if (to in segments.indices) {
            val temp = segments[from]
            segments[from] = segments[to]
            segments[to] = temp
            // 同步交换原始URI
            val tempOrig = originalUris[from]
            originalUris[from] = originalUris[to]
            originalUris[to] = tempOrig
        }
    }

    // 生成预览
    fun generatePreview() {
        if (segments.isEmpty()) return
        errorMessage = null
        scope.launch {
            val bitmaps = withContext(Dispatchers.IO) {
                segments.mapNotNull { uri -> ImageUtils.loadBitmap(context, uri) }
            }
            if (bitmaps.isEmpty()) {
                errorMessage = "无法加载图片"
                return@launch
            }
            val merged = withContext(Dispatchers.IO) { ImageUtils.mergeVertically(bitmaps) }
            val file = withContext(Dispatchers.IO) {
                ImageUtils.saveToCacheFile(context, merged, "merged_${System.currentTimeMillis()}.jpg")
            }
            previewBitmap = merged
            mergedFile = file
            showPreview = true
        }
    }

    // 确认上传
    fun confirmUpload() {
        val file = mergedFile ?: return
        isUploading = true
        showPreview = false
        errorMessage = null
        scope.launch {
            try {
                val api = HomeworkApi()
                val result = api.parseHomework(file)
                result.fold(
                    onSuccess = {
                        ResultHolder.latestResult = it
                        isUploading = false
                        onUploadComplete()
                    },
                    onFailure = { e ->
                        errorMessage = e.message ?: "上传失败"
                        isUploading = false
                    }
                )
            } catch (e: Exception) {
                errorMessage = e.message ?: "未知错误"
                isUploading = false
            }
        }
    }

    // 合并预览弹窗
    if (showPreview && previewBitmap != null) {
        Dialog(
            onDismissRequest = { showPreview = false },
            properties = DialogProperties(usePlatformDefaultWidth = false)
        ) {
            Surface(
                modifier = Modifier.fillMaxSize().padding(16.dp),
                shape = MaterialTheme.shapes.large,
                tonalElevation = 6.dp
            ) {
                Column(modifier = Modifier.fillMaxSize()) {
                    TopAppBar(
                        title = { Text("合并预览") },
                        navigationIcon = {
                            IconButton(onClick = { showPreview = false }) {
                                Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "返回")
                            }
                        }
                    )
                    // 可滚动的预览图
                    Box(
                        modifier = Modifier.weight(1f).fillMaxWidth()
                            .verticalScroll(rememberScrollState())
                            .padding(8.dp)
                    ) {
                        androidx.compose.foundation.Image(
                            bitmap = previewBitmap!!.asImageBitmap(),
                            contentDescription = "合并预览",
                            contentScale = ContentScale.FillWidth,
                            modifier = Modifier.fillMaxWidth()
                        )
                    }
                    // 底部按钮
                    Row(
                        modifier = Modifier.fillMaxWidth().padding(16.dp),
                        horizontalArrangement = Arrangement.spacedBy(12.dp)
                    ) {
                        OutlinedButton(
                            onClick = { showPreview = false },
                            modifier = Modifier.weight(1f).height(48.dp)
                        ) { Text("返回修改") }
                        Button(
                            onClick = { confirmUpload() },
                            modifier = Modifier.weight(1f).height(48.dp)
                        ) { Text("确认上传") }
                    }
                }
            }
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("排序与合并") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = stringResource(R.string.back))
                    }
                },
                actions = {
                    IconButton(onClick = onAddMore) {
                        Icon(Icons.Default.Add, contentDescription = "继续添加")
                    }
                }
            )
        },
        bottomBar = {
            Column(modifier = Modifier.padding(16.dp)) {
                if (errorMessage != null) {
                    Text(
                        text = errorMessage!!,
                        color = MaterialTheme.colorScheme.error,
                        style = MaterialTheme.typography.bodySmall,
                        modifier = Modifier.padding(bottom = 8.dp)
                    )
                }
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(12.dp)
                ) {
                    OutlinedButton(
                        onClick = onAddMore,
                        modifier = Modifier.weight(1f).height(52.dp)
                    ) {
                        Icon(Icons.Default.Add, contentDescription = null, modifier = Modifier.size(18.dp))
                        Spacer(modifier = Modifier.width(4.dp))
                        Text("继续添加")
                    }
                    Button(
                        onClick = { generatePreview() },
                        modifier = Modifier.weight(1f).height(52.dp),
                        enabled = segments.isNotEmpty() && !isUploading
                    ) {
                        if (isUploading) {
                            CircularProgressIndicator(
                                modifier = Modifier.size(20.dp),
                                color = MaterialTheme.colorScheme.onPrimary,
                                strokeWidth = 2.dp
                            )
                            Spacer(modifier = Modifier.width(8.dp))
                            Text(stringResource(R.string.analyzing))
                        } else {
                            Text(stringResource(R.string.merge_and_upload))
                        }
                    }
                }
            }
        }
    ) { padding ->
        if (segments.isEmpty()) {
            Box(
                modifier = Modifier.fillMaxSize().padding(padding),
                contentAlignment = Alignment.Center
            ) {
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    Text(stringResource(R.string.no_crops_yet))
                    Spacer(modifier = Modifier.height(16.dp))
                    OutlinedButton(onClick = onAddMore) {
                        Icon(Icons.Default.Add, contentDescription = null)
                        Spacer(modifier = Modifier.width(8.dp))
                        Text("添加图片")
                    }
                }
            }
        } else {
            LazyColumn(
                modifier = Modifier.fillMaxSize().padding(padding),
                contentPadding = PaddingValues(16.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                itemsIndexed(segments) { index, uri ->
                    SegmentCard(
                        uri = uri,
                        index = index,
                        isFirst = index == 0,
                        isLast = index == segments.lastIndex,
                        onMoveUp = { swapItems(index, index - 1) },
                        onMoveDown = { swapItems(index, index + 1) },
                        onCrop = { onCropItem(index) },
                        onDelete = {
                            segments.removeAt(index)
                            originalUris.removeAt(index)
                        }
                    )
                }
            }
        }
    }
}

@Composable
private fun SegmentCard(
    uri: Uri,
    index: Int,
    isFirst: Boolean,
    isLast: Boolean,
    onMoveUp: () -> Unit,
    onMoveDown: () -> Unit,
    onCrop: () -> Unit,
    onDelete: () -> Unit
) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Row(
            modifier = Modifier.padding(8.dp),
            verticalAlignment = Alignment.Top
        ) {
            AsyncImage(
                model = uri,
                contentDescription = "片段 ${index + 1}",
                contentScale = ContentScale.FillWidth,
                modifier = Modifier.weight(1f)
            )
            Column(
                modifier = Modifier.padding(start = 8.dp),
                horizontalAlignment = Alignment.CenterHorizontally
            ) {
                IconButton(onClick = onMoveUp, enabled = !isFirst) {
                    Icon(Icons.Default.KeyboardArrowUp, contentDescription = "上移")
                }
                IconButton(onClick = onMoveDown, enabled = !isLast) {
                    Icon(Icons.Default.KeyboardArrowDown, contentDescription = "下移")
                }
                IconButton(onClick = onCrop) {
                    Icon(Icons.Default.Crop, contentDescription = "裁剪", tint = MaterialTheme.colorScheme.primary)
                }
                IconButton(onClick = onDelete) {
                    Icon(Icons.Default.Delete, contentDescription = "删除", tint = MaterialTheme.colorScheme.error)
                }
            }
        }
    }
}
