package com.homework.assistant.ui.result

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.VolumeUp
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.homework.assistant.HomeworkApplication
import com.homework.assistant.R
import com.homework.assistant.data.model.ParseResponse
import com.homework.assistant.data.model.SpeakUnit
import com.homework.assistant.data.model.VocabularyItem
import com.homework.assistant.ui.merge.ResultHolder

/**
 * 结果展示页
 * 展示题意、答案、讲解、词汇、点读单元
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ResultScreen(
    onStartOver: () -> Unit
) {
    val context = LocalContext.current
    val ttsManager = (context.applicationContext as HomeworkApplication).ttsManager
    val result = ResultHolder.latestResult

    DisposableEffect(Unit) {
        onDispose { ttsManager.stop() }
    }

    Scaffold(
        topBar = {
            TopAppBar(title = { Text("解析结果") })
        },
        bottomBar = {
            Button(
                onClick = onStartOver,
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(16.dp)
                    .height(52.dp)
            ) {
                Text("再来一题")
            }
        }
    ) { padding ->
        if (result == null) {
            Box(
                modifier = Modifier.fillMaxSize().padding(padding),
                contentAlignment = Alignment.Center
            ) {
                Text("暂无结果")
            }
        } else {
            LazyColumn(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding),
                contentPadding = PaddingValues(16.dp),
                verticalArrangement = Arrangement.spacedBy(16.dp)
            ) {
                // 不确定性警告
                if (result.uncertainty.requires_review) {
                    item {
                        UncertaintyBanner(result.uncertainty.warning)
                    }
                }

                // 题目理解
                item {
                    SectionCard(
                        title = stringResource(R.string.question_meaning),
                        content = result.question_meaning_zh
                    )
                }

                // 参考答案
                item {
                    SectionCard(
                        title = stringResource(R.string.reference_answer),
                        content = result.reference_answer
                    )
                }

                // 讲解
                item {
                    SectionCard(
                        title = stringResource(R.string.explanation),
                        content = result.explanation_zh
                    )
                }

                // 词汇
                if (result.key_vocabulary.isNotEmpty()) {
                    item {
                        Text(
                            text = stringResource(R.string.vocabulary),
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.Bold
                        )
                    }
                    items(result.key_vocabulary) { vocab ->
                        VocabularyCard(vocab, onSpeak = { ttsManager.speak(vocab.word) })
                    }
                }

                // 点读单元
                if (result.speak_units.isNotEmpty()) {
                    item {
                        Text(
                            text = stringResource(R.string.tap_to_speak),
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.Bold
                        )
                    }
                    item {
                        SpeakUnitsGrid(
                            units = result.speak_units,
                            onSpeak = { ttsManager.speak(it.text) }
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun UncertaintyBanner(warning: String) {
    Card(
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.errorContainer
        )
    ) {
        Text(
            text = "⚠️ $warning",
            modifier = Modifier.padding(12.dp),
            color = MaterialTheme.colorScheme.onErrorContainer,
            style = MaterialTheme.typography.bodyMedium
        )
    }
}

@Composable
private fun SectionCard(title: String, content: String) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(16.dp)) {
            Text(
                text = title,
                style = MaterialTheme.typography.titleSmall,
                fontWeight = FontWeight.Bold,
                color = MaterialTheme.colorScheme.primary
            )
            Spacer(modifier = Modifier.height(8.dp))
            Text(
                text = content,
                style = MaterialTheme.typography.bodyLarge
            )
        }
    }
}

@Composable
private fun VocabularyCard(vocab: VocabularyItem, onSpeak: () -> Unit) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clickable { onSpeak() }
    ) {
        Row(
            modifier = Modifier.padding(12.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = vocab.word,
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.Bold
                )
                if (vocab.ipa.isNotEmpty()) {
                    Text(
                        text = vocab.ipa,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
                Text(
                    text = vocab.meaning_zh,
                    style = MaterialTheme.typography.bodyMedium
                )
            }
            Icon(
                Icons.Default.VolumeUp,
                contentDescription = "发音",
                tint = MaterialTheme.colorScheme.primary
            )
        }
    }
}

@Composable
private fun SpeakUnitsGrid(
    units: List<SpeakUnit>,
    onSpeak: (SpeakUnit) -> Unit
) {
    // 按类型分组：先句子后单词
    val sentences = units.filter { it.type == "sentence" }
    val words = units.filter { it.type == "word" }

    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        // 句子：每个一行
        sentences.forEach { unit ->
            SpeakChip(text = unit.text, onClick = { onSpeak(unit) })
        }

        // 单词：流式布局
        if (words.isNotEmpty()) {
            FlowRow(
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
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
        leadingIcon = {
            Icon(
                Icons.Default.VolumeUp,
                contentDescription = null,
                modifier = Modifier.size(16.dp)
            )
        }
    )
}

@Composable
private fun FlowRow(
    horizontalArrangement: Arrangement.Horizontal = Arrangement.Start,
    verticalArrangement: Arrangement.Vertical = Arrangement.Top,
    content: @Composable () -> Unit
) {
    // Compose 1.5+ 内置 FlowRow，这里用 Column+Row 简单模拟
    // 实际项目中可直接使用 androidx.compose.foundation.layout.FlowRow
    Column(verticalArrangement = verticalArrangement) {
        content()
    }
}
