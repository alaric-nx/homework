package com.homework.assistant.ui.result

import android.graphics.BitmapFactory
import android.util.Base64
import androidx.compose.foundation.Image
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.detectTransformGestures
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.VolumeUp
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clipToBounds
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.layout.onSizeChanged
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.IntSize
import androidx.compose.ui.unit.dp
import com.google.gson.Gson
import com.homework.assistant.HomeworkApplication
import com.homework.assistant.R
import com.homework.assistant.data.model.ParseResponse
import com.homework.assistant.data.model.SpeakUnit
import com.homework.assistant.data.model.VocabularyItem
import com.homework.assistant.data.repository.TaskRepository

/**
 * 结果展示页 — 从 Room 按 taskId 读取数据
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ResultScreen(
    taskId: String,
    onStartOver: () -> Unit
) {
    val context = LocalContext.current
    val app = context.applicationContext as HomeworkApplication
    val ttsManager = app.ttsManager
    val repo = app.taskRepository
    val gson = remember { Gson() }

    LaunchedEffect(Unit) { ttsManager.ensureInit(context) }

    // 从 Room 加载任务
    var result by remember { mutableStateOf<ParseResponse?>(null) }
    var filledImageBase64 by remember { mutableStateOf<String?>(null) }
    var loading by remember { mutableStateOf(true) }

    LaunchedEffect(taskId) {
        val task = repo.getById(taskId)
        if (task != null && task.resultJson != null) {
            result = gson.fromJson(task.resultJson, ParseResponse::class.java)
            filledImageBase64 = task.filledImageBase64
        }
        loading = false
    }

    val filteredSpeakUnits = remember(result) {
        if (result == null) emptyList()
        else {
            val vocabWords = result!!.key_vocabulary
                .map { it.word.trim().lowercase() }
                .filter { it.isNotEmpty() }
                .toSet()
            result!!.speak_units.filter { unit ->
                unit.type != "word" || unit.text.trim().lowercase() !in vocabWords
            }
        }
    }
    val filledBitmap = remember(filledImageBase64) {
        filledImageBase64?.let {
            try {
                val bytes = Base64.decode(it, Base64.DEFAULT)
                BitmapFactory.decodeByteArray(bytes, 0, bytes.size)
            } catch (_: Exception) { null }
        }
    }

    DisposableEffect(Unit) { onDispose { ttsManager.stop() } }

    Scaffold(
        topBar = { TopAppBar(title = { Text("解析结果") }) },
        bottomBar = {
            Button(
                onClick = onStartOver,
                modifier = Modifier.fillMaxWidth().padding(16.dp).height(52.dp)
            ) { Text("再来一题") }
        }
    ) { padding ->
        when {
            loading -> {
                Box(Modifier.fillMaxSize().padding(padding), contentAlignment = Alignment.Center) {
                    CircularProgressIndicator()
                }
            }
            result == null -> {
                Box(Modifier.fillMaxSize().padding(padding), contentAlignment = Alignment.Center) {
                    Text("暂无结果")
                }
            }
            else -> {
                val r = result!!
                LazyColumn(
                    modifier = Modifier.fillMaxSize().padding(padding),
                    contentPadding = PaddingValues(16.dp),
                    verticalArrangement = Arrangement.spacedBy(16.dp)
                ) {
                    if (r.uncertainty.requires_review && !r.uncertainty.warning.isNullOrEmpty()) {
                        item { UncertaintyBanner(r.uncertainty.warning!!) }
                    }
                    if (filledBitmap != null) {
                        item { ZoomableFilledImage(filledBitmap) }
                    }
                    item { SectionCard(stringResource(R.string.question_meaning), r.question_meaning_zh) }
                    item { SectionCard(stringResource(R.string.reference_answer), r.reference_answer) }
                    item { SectionCard(stringResource(R.string.explanation), r.explanation_zh) }
                    if (r.key_vocabulary.isNotEmpty()) {
                        item {
                            Text(stringResource(R.string.vocabulary),
                                style = MaterialTheme.typography.titleMedium,
                                fontWeight = FontWeight.Bold)
                        }
                        items(r.key_vocabulary) { vocab ->
                            VocabularyCard(vocab, onSpeak = { ttsManager.speak(vocab.word) })
                        }
                    }
                    if (filteredSpeakUnits.isNotEmpty()) {
                        item {
                            Text(stringResource(R.string.tap_to_speak),
                                style = MaterialTheme.typography.titleMedium,
                                fontWeight = FontWeight.Bold)
                        }
                        item {
                            SpeakUnitsGrid(filteredSpeakUnits, onSpeak = { ttsManager.speak(it.text) })
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun ZoomableFilledImage(bitmap: android.graphics.Bitmap) {
    var scale by remember { mutableFloatStateOf(1f) }
    var offset by remember { mutableStateOf(Offset.Zero) }
    var containerSize by remember { mutableStateOf(IntSize.Zero) }
    val imgRatio = bitmap.width.toFloat() / bitmap.height.toFloat()

    fun clampOffset(s: Float, o: Offset): Offset {
        if (containerSize.width == 0 || containerSize.height == 0) return o
        val cw = containerSize.width.toFloat()
        val imgH = cw / imgRatio
        val maxX = ((cw * s - cw) / 2f).coerceAtLeast(0f)
        val maxY = ((imgH * s - imgH) / 2f).coerceAtLeast(0f)
        return Offset(o.x.coerceIn(-maxX, maxX), o.y.coerceIn(-maxY, maxY))
    }

    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(16.dp)) {
            Text("填写后题图", style = MaterialTheme.typography.titleSmall,
                fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.primary)
            Spacer(modifier = Modifier.height(8.dp))
            Box(
                modifier = Modifier.fillMaxWidth().clipToBounds()
                    .onSizeChanged { containerSize = it }
                    .pointerInput(Unit) {
                        detectTransformGestures { _, pan, zoom, _ ->
                            val newScale = (scale * zoom).coerceIn(1f, 5f)
                            scale = newScale
                            offset = clampOffset(newScale, offset + pan)
                        }
                    }
            ) {
                Image(
                    bitmap = bitmap.asImageBitmap(),
                    contentDescription = "填写后题图",
                    contentScale = ContentScale.FillWidth,
                    modifier = Modifier.fillMaxWidth().graphicsLayer {
                        scaleX = scale; scaleY = scale
                        translationX = offset.x; translationY = offset.y
                    }
                )
            }
        }
    }
}

@Composable
private fun UncertaintyBanner(warning: String) {
    Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.errorContainer)) {
        Text("⚠️ $warning", modifier = Modifier.padding(12.dp),
            color = MaterialTheme.colorScheme.onErrorContainer,
            style = MaterialTheme.typography.bodyMedium)
    }
}

@Composable
private fun SectionCard(title: String, content: String) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(16.dp)) {
            Text(title, style = MaterialTheme.typography.titleSmall,
                fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.primary)
            Spacer(modifier = Modifier.height(8.dp))
            Text(content, style = MaterialTheme.typography.bodyLarge)
        }
    }
}

@Composable
private fun VocabularyCard(vocab: VocabularyItem, onSpeak: () -> Unit) {
    Card(modifier = Modifier.fillMaxWidth().clickable { onSpeak() }) {
        Row(modifier = Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
            Column(modifier = Modifier.weight(1f)) {
                Text(vocab.word, style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Bold)
                if (vocab.ipa.isNotEmpty()) {
                    Text(vocab.ipa, style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                Text(vocab.meaning_zh, style = MaterialTheme.typography.bodyMedium)
            }
            Icon(Icons.Default.VolumeUp, contentDescription = "发音", tint = MaterialTheme.colorScheme.primary)
        }
    }
}

@Composable
private fun SpeakUnitsGrid(units: List<SpeakUnit>, onSpeak: (SpeakUnit) -> Unit) {
    val sentences = units.filter { it.type == "sentence" }
    val words = units.filter { it.type == "word" }
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        sentences.forEach { unit ->
            SpeakChip(text = unit.text, onClick = { onSpeak(unit) })
        }
        if (words.isNotEmpty()) {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                words.forEach { unit ->
                    SpeakChip(text = unit.text, onClick = { onSpeak(unit) })
                }
            }
        }
    }
}

@Composable
private fun SpeakChip(text: String, onClick: () -> Unit) {
    AssistChip(
        onClick = onClick,
        label = { Text(text) },
        leadingIcon = { Icon(Icons.Default.VolumeUp, contentDescription = null, modifier = Modifier.size(16.dp)) }
    )
}
