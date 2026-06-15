@file:OptIn(ExperimentalMaterial3Api::class, ExperimentalLayoutApi::class)

package com.homework.assistant.ui.result

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.awaitEachGesture
import androidx.compose.foundation.gestures.awaitFirstDown
import androidx.compose.foundation.gestures.waitForUpOrCancellation
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Translate
import androidx.compose.material.icons.filled.VolumeUp
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.google.gson.Gson
import com.homework.assistant.HomeworkApplication
import com.homework.assistant.R
import com.homework.assistant.data.model.ParseResult
import com.homework.assistant.data.model.SpeakUnit
import com.homework.assistant.data.model.VocabularyItem
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import java.util.Locale

private val numberedAnswerPattern = Regex("""(?:^|[\s,;，；、/])(\d{1,2})\s*[\.\)\-:：]?\s*(.+?)(?=(?:[\s,;，；、/]+(?:\d{1,2})\s*[\.\)\-:：]?\s*)|$)""")
private val fallbackAnswerLinePattern = Regex("""^(\d+)[\.)]?\s+(.+)$""")
private val speakTokenPattern = Regex("""[A-Za-z]+(?:'[A-Za-z]+)?|\d+|[^\w\s]""")
private val stripWordPattern = Regex("""^[^a-z0-9']+|[^a-z0-9']+$""")
private val whitespacePattern = Regex("""\s+""")
private val ResultCardShape = RoundedCornerShape(8.dp)
private val TokenShape = RoundedCornerShape(7.dp)
private val PageBackground = Color(0xFFF7F8FA)
private val CardSurface = Color(0xFFFFFEFC)
private val CardBorder = Color(0xFFE4E8EE)
private val SoftPrimarySurface = Color(0xFFEAF3FF)
private val SoftAccentSurface = Color(0xFFEAF7EF)
private val SoftNeutralSurface = Color(0xFFF2F4F7)
private val InkText = Color(0xFF172033)

private data class AnswerLine(
    val id: String,
    val number: Int?,
    val text: String
)

private data class SpeakToken(
    val text: String,
    val speakable: Boolean
)

private data class WordTipTarget(
    val id: String,
    val word: String,
    val ipa: String?,
    val meaning: String
)

private data class SentenceTipTarget(
    val id: String,
    val text: String,
    val translation: String
)

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

    var result by remember { mutableStateOf<ParseResult?>(null) }
    var loading by remember { mutableStateOf(true) }
    var activeTip by remember { mutableStateOf<WordTipTarget?>(null) }
    var activeSentenceTip by remember { mutableStateOf<SentenceTipTarget?>(null) }

    LaunchedEffect(taskId) {
        val task = repo.getById(taskId)
        if (task != null && task.resultJson != null) {
            result = gson.fromJson(task.resultJson, ParseResult::class.java)
        }
        loading = false
    }

    val answerLines = remember(result) {
        parseAnswerLines(result?.reference_answer.orEmpty())
    }
    val vocabLookup = remember(result) {
        buildVocabularyLookup(result?.key_vocabulary.orEmpty())
    }
    val sentenceTranslationLookup = remember(result) {
        buildSentenceTranslationLookup(result?.speak_units.orEmpty())
    }
    val answerWordKeys = remember(answerLines) {
        answerLines.flatMap { line ->
            tokenizeSpeakTokens(line.text)
                .filter { it.speakable }
                .mapNotNull { normalizeWord(it.text) }
        }.toSet()
    }
    val answerSentenceKeys = remember(answerLines) {
        answerLines.map { normalizeSentence(it.text) }.filter { it.isNotEmpty() }.toSet()
    }
    val vocabWordKeys = remember(vocabLookup) { vocabLookup.keys.toSet() }
    val extraSpeakUnits = remember(result, answerWordKeys, answerSentenceKeys, vocabWordKeys) {
        result?.speak_units.orEmpty().filter { unit ->
            when (unit.type) {
                "sentence" -> normalizeSentence(unit.text) !in answerSentenceKeys
                else -> {
                    val key = normalizeWord(unit.text)
                    key.isNotEmpty() && key !in answerWordKeys && key !in vocabWordKeys
                }
            }
        }
    }

    DisposableEffect(Unit) {
        onDispose {
            activeTip = null
            activeSentenceTip = null
            ttsManager.stop()
        }
    }

    Scaffold(
        containerColor = PageBackground,
        topBar = {
            TopAppBar(
                title = {
                    Text(
                        "解析结果",
                        fontWeight = FontWeight.SemiBold,
                        color = InkText
                    )
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = CardSurface,
                    titleContentColor = InkText
                )
            )
        },
        bottomBar = {
            Button(
                onClick = onStartOver,
                colors = ButtonDefaults.buttonColors(
                    containerColor = Color(0xFF1565C0),
                    contentColor = Color.White
                ),
                shape = RoundedCornerShape(8.dp),
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(16.dp)
                    .height(52.dp)
            ) { Text("再来一题") }
        }
    ) { padding ->
        when {
            loading -> {
                Box(
                    Modifier.fillMaxSize().padding(padding),
                    contentAlignment = Alignment.Center
                ) { CircularProgressIndicator() }
            }

            result == null -> {
                Box(
                    Modifier.fillMaxSize().padding(padding),
                    contentAlignment = Alignment.Center
                ) { Text("暂无结果") }
            }

            else -> {
                val r = result!!
                androidx.compose.foundation.lazy.LazyColumn(
                    modifier = Modifier.fillMaxSize().padding(padding),
                    contentPadding = PaddingValues(16.dp),
                    verticalArrangement = Arrangement.spacedBy(16.dp)
                ) {
                    if (r.uncertainty.requires_review && !r.uncertainty.warning.isNullOrEmpty()) {
                        item { UncertaintyBanner(r.uncertainty.warning!!) }
                    }
                    item { SectionCard(stringResource(R.string.question_meaning), r.question_meaning_zh) }
                    item {
                        if (answerLines.isNotEmpty()) {
                            AnswerPronunciationCard(
                                title = stringResource(R.string.reference_answer),
                                lines = answerLines,
                                vocabLookup = vocabLookup,
                                sentenceTranslationLookup = sentenceTranslationLookup,
                                activeTip = activeTip,
                                activeSentenceTip = activeSentenceTip,
                                onTipChange = { activeTip = it },
                                onSentenceTipChange = { activeSentenceTip = it },
                                onSpeakLine = {
                                    activeTip = null
                                    activeSentenceTip = null
                                    ttsManager.speak(it)
                                },
                                onSpeakWord = {
                                    activeTip = null
                                    activeSentenceTip = null
                                    ttsManager.speak(it)
                                }
                            )
                        } else {
                            SectionCard(stringResource(R.string.reference_answer), r.reference_answer)
                        }
                    }
                    item { SectionCard(stringResource(R.string.explanation), r.explanation_zh) }
                    if (r.key_vocabulary.isNotEmpty()) {
                        item {
                            Text(
                                stringResource(R.string.vocabulary),
                                style = MaterialTheme.typography.titleMedium,
                                fontWeight = FontWeight.Bold
                            )
                        }
                        items(r.key_vocabulary) { vocab ->
                            VocabularyCard(vocab, onSpeak = { ttsManager.speak(vocab.word) })
                        }
                    }
                    if (extraSpeakUnits.isNotEmpty()) {
                        item {
                            Text(
                                stringResource(R.string.more_pronunciation),
                                style = MaterialTheme.typography.titleMedium,
                                fontWeight = FontWeight.Bold
                            )
                        }
                        item {
                            ExtraPronunciationCard(
                                units = extraSpeakUnits,
                                vocabLookup = vocabLookup,
                                sentenceTranslationLookup = sentenceTranslationLookup,
                                activeTip = activeTip,
                                activeSentenceTip = activeSentenceTip,
                                onTipChange = { activeTip = it },
                                onSentenceTipChange = { activeSentenceTip = it },
                                onSpeakLine = {
                                    activeTip = null
                                    activeSentenceTip = null
                                    ttsManager.speak(it)
                                },
                                onSpeakWord = {
                                    activeTip = null
                                    activeSentenceTip = null
                                    ttsManager.speak(it)
                                }
                            )
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun UncertaintyBanner(warning: String) {
    Card(
        shape = ResultCardShape,
        colors = CardDefaults.cardColors(containerColor = Color(0xFFFFF0EF)),
        elevation = CardDefaults.cardElevation(defaultElevation = 0.dp),
        border = BorderStroke(1.dp, Color(0xFFFFC9C3))
    ) {
        Text(
            "⚠️ $warning",
            modifier = Modifier.padding(12.dp),
            color = Color(0xFF8A1F16),
            style = MaterialTheme.typography.bodyMedium
        )
    }
}

@Composable
private fun SectionCard(title: String, content: String) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = ResultCardShape,
        colors = CardDefaults.cardColors(containerColor = CardSurface),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp),
        border = BorderStroke(1.dp, CardBorder)
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Text(
                title,
                style = MaterialTheme.typography.titleSmall,
                fontWeight = FontWeight.Bold,
                color = Color(0xFF174A7C)
            )
            Spacer(modifier = Modifier.height(8.dp))
            Text(content, style = MaterialTheme.typography.bodyLarge, color = InkText)
        }
    }
}

@Composable
private fun AnswerPronunciationCard(
    title: String,
    lines: List<AnswerLine>,
    vocabLookup: Map<String, VocabularyItem>,
    sentenceTranslationLookup: Map<String, String>,
    activeTip: WordTipTarget?,
    activeSentenceTip: SentenceTipTarget?,
    onTipChange: (WordTipTarget?) -> Unit,
    onSentenceTipChange: (SentenceTipTarget?) -> Unit,
    onSpeakLine: (String) -> Unit,
    onSpeakWord: (String) -> Unit
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = ResultCardShape,
        colors = CardDefaults.cardColors(containerColor = CardSurface),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp),
        border = BorderStroke(1.dp, CardBorder)
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            Text(
                title,
                style = MaterialTheme.typography.titleSmall,
                fontWeight = FontWeight.Bold,
                color = Color(0xFF174A7C)
            )
            lines.forEachIndexed { index, line ->
                if (index > 0) {
                    HorizontalDivider(color = Color(0xFFE9EDF3))
                }
                SpeakableLineRow(
                    lineId = line.id,
                    number = line.number,
                    text = line.text,
                    vocabLookup = vocabLookup,
                    translation = findSentenceTranslation(line.text, sentenceTranslationLookup),
                    activeTip = activeTip,
                    activeSentenceTip = activeSentenceTip,
                    onTipChange = onTipChange,
                    onSentenceTipChange = onSentenceTipChange,
                    onSpeakLine = onSpeakLine,
                    onSpeakWord = onSpeakWord
                )
            }
        }
    }
}

@Composable
private fun ExtraPronunciationCard(
    units: List<SpeakUnit>,
    vocabLookup: Map<String, VocabularyItem>,
    sentenceTranslationLookup: Map<String, String>,
    activeTip: WordTipTarget?,
    activeSentenceTip: SentenceTipTarget?,
    onTipChange: (WordTipTarget?) -> Unit,
    onSentenceTipChange: (SentenceTipTarget?) -> Unit,
    onSpeakLine: (String) -> Unit,
    onSpeakWord: (String) -> Unit
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = ResultCardShape,
        colors = CardDefaults.cardColors(containerColor = CardSurface),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp),
        border = BorderStroke(1.dp, CardBorder)
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            val sentenceUnits = units.filter { it.type == "sentence" }
            val wordUnits = units.filter { it.type == "word" }

            sentenceUnits.forEachIndexed { index, unit ->
                if (index > 0) {
                    HorizontalDivider(color = Color(0xFFE9EDF3))
                }
                SpeakableLineRow(
                    lineId = "extra-sentence-$index",
                    number = null,
                    text = unit.text,
                    vocabLookup = vocabLookup,
                    translation = unit.meaning_zh?.takeIf { it.isNotBlank() }
                        ?: findSentenceTranslation(unit.text, sentenceTranslationLookup),
                    activeTip = activeTip,
                    activeSentenceTip = activeSentenceTip,
                    onTipChange = onTipChange,
                    onSentenceTipChange = onSentenceTipChange,
                    onSpeakLine = onSpeakLine,
                    onSpeakWord = onSpeakWord
                )
            }

            if (wordUnits.isNotEmpty()) {
                FlowRow(
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    wordUnits.forEachIndexed { index, unit ->
                        SpeakableWordToken(
                            token = unit.text,
                            tipTarget = buildTipTarget(
                                id = "extra-word-$index",
                                rawWord = unit.text,
                                vocabLookup = vocabLookup
                            ),
                            activeTip = activeTip,
                            onTipChange = onTipChange,
                            onSpeakWord = onSpeakWord
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun SpeakableLineRow(
    lineId: String,
    number: Int?,
    text: String,
    vocabLookup: Map<String, VocabularyItem>,
    translation: String?,
    activeTip: WordTipTarget?,
    activeSentenceTip: SentenceTipTarget?,
    onTipChange: (WordTipTarget?) -> Unit,
    onSentenceTipChange: (SentenceTipTarget?) -> Unit,
    onSpeakLine: (String) -> Unit,
    onSpeakWord: (String) -> Unit
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.Top
    ) {
        if (number != null) {
            Surface(
                shape = TokenShape,
                color = SoftPrimarySurface,
                contentColor = Color(0xFF15528C),
                border = BorderStroke(1.dp, Color(0xFFC7DCF5))
            ) {
                Text(
                    text = number.toString(),
                    modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp),
                    style = MaterialTheme.typography.labelMedium,
                    fontWeight = FontWeight.Bold
                )
            }
            Spacer(modifier = Modifier.width(10.dp))
        }

        FlowRow(
            modifier = Modifier.weight(1f),
            horizontalArrangement = Arrangement.spacedBy(4.dp),
            verticalArrangement = Arrangement.spacedBy(6.dp)
        ) {
            val tokens = tokenizeSpeakTokens(text)
            tokens.forEachIndexed { index, token ->
                if (token.speakable) {
                    SpeakableWordToken(
                        token = token.text,
                        tipTarget = buildTipTarget(
                            id = "$lineId-$index",
                            rawWord = token.text,
                            vocabLookup = vocabLookup
                        ),
                        activeTip = activeTip,
                        onTipChange = onTipChange,
                        onSpeakWord = onSpeakWord
                    )
                } else {
                    Text(
                        text = token.text,
                        style = MaterialTheme.typography.bodyLarge,
                        color = MaterialTheme.colorScheme.onSurface
                    )
                }
            }
        }

        Row(
            horizontalArrangement = Arrangement.spacedBy(2.dp),
            verticalAlignment = Alignment.Top
        ) {
            IconButton(onClick = { onSpeakLine(text) }) {
                Icon(
                    Icons.Default.VolumeUp,
                    contentDescription = stringResource(R.string.pronunciation_voice),
                    tint = Color(0xFF1565C0)
                )
            }
            SentenceTranslationButton(
                lineId = lineId,
                text = text,
                translation = translation,
                activeSentenceTip = activeSentenceTip,
                onTipChange = {
                    onTipChange(null)
                    onSentenceTipChange(it)
                }
            )
        }
    }
}

@Composable
private fun SentenceTranslationButton(
    lineId: String,
    text: String,
    translation: String?,
    activeSentenceTip: SentenceTipTarget?,
    onTipChange: (SentenceTipTarget?) -> Unit
) {
    val target = SentenceTipTarget(
        id = "$lineId-translation",
        text = text,
        translation = translation?.takeIf { it.isNotBlank() }
            ?: stringResource(R.string.pronunciation_translation_unknown)
    )
    val isTipOpen = activeSentenceTip?.id == target.id

    Box {
        IconButton(
            onClick = {
                onTipChange(if (isTipOpen) null else target)
            }
        ) {
            Icon(
                Icons.Default.Translate,
                contentDescription = stringResource(R.string.pronunciation_translate),
                tint = if (isTipOpen) {
                    Color(0xFF2E7D4F)
                } else {
                    Color(0xFF667085)
                }
            )
        }
        DropdownMenu(
            expanded = isTipOpen,
            onDismissRequest = { onTipChange(null) },
            modifier = Modifier.widthIn(min = 180.dp, max = 280.dp)
        ) {
            Surface(
                shape = ResultCardShape,
                color = CardSurface,
                tonalElevation = 3.dp
            ) {
                Column(modifier = Modifier.padding(12.dp)) {
                Text(
                    stringResource(R.string.pronunciation_translate),
                    style = MaterialTheme.typography.labelLarge,
                    fontWeight = FontWeight.Bold,
                    color = Color(0xFF2E7D4F)
                )
                Spacer(modifier = Modifier.height(6.dp))
                Text(
                    target.translation,
                    style = MaterialTheme.typography.bodyMedium,
                    color = InkText
                )
                }
            }
        }
    }
}

@Composable
private fun SpeakableWordToken(
    token: String,
    tipTarget: WordTipTarget?,
    activeTip: WordTipTarget?,
    onTipChange: (WordTipTarget?) -> Unit,
    onSpeakWord: (String) -> Unit
) {
    val isTipOpen = tipTarget != null && activeTip?.id == tipTarget.id
    Box(
        modifier = Modifier
            .pointerInput(token) {
                coroutineScope {
                    awaitEachGesture {
                        awaitFirstDown(requireUnconsumed = false)
                        var longPressTriggered = false
                        val longPressJob = launch {
                            delay(1000L)
                            longPressTriggered = true
                            if (tipTarget != null) {
                                onTipChange(tipTarget)
                            }
                        }
                        val up = waitForUpOrCancellation()
                        longPressJob.cancel()
                        if (up != null && !longPressTriggered) {
                            onTipChange(null)
                            onSpeakWord(token)
                        }
                    }
                }
            }
    ) {
        Surface(
            shape = TokenShape,
            color = if (isTipOpen) {
                SoftAccentSurface
            } else {
                SoftNeutralSurface
            },
            contentColor = if (isTipOpen) {
                Color(0xFF22603A)
            } else {
                Color(0xFF253247)
            },
            border = BorderStroke(
                1.dp,
                if (isTipOpen) Color(0xFFBFE4CC) else Color(0xFFE3E6EA)
            )
        ) {
            Text(
                text = token,
                modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp),
                style = MaterialTheme.typography.bodyMedium,
                fontWeight = FontWeight.Medium
            )
        }

        if (tipTarget != null) {
            DropdownMenu(
                expanded = isTipOpen,
                onDismissRequest = { if (isTipOpen) onTipChange(null) },
                modifier = Modifier.widthIn(min = 160.dp, max = 240.dp)
            ) {
                Surface(
                    shape = ResultCardShape,
                    color = CardSurface,
                    tonalElevation = 3.dp
                ) {
                Column(modifier = Modifier.padding(12.dp)) {
                    Text(
                        tipTarget.word,
                        style = MaterialTheme.typography.labelLarge,
                        fontWeight = FontWeight.Bold,
                        color = Color(0xFF22603A)
                    )
                    if (!tipTarget.ipa.isNullOrBlank()) {
                        Spacer(modifier = Modifier.height(4.dp))
                        Text(
                            tipTarget.ipa,
                            style = MaterialTheme.typography.bodySmall,
                            color = Color(0xFF667085)
                        )
                    }
                    Spacer(modifier = Modifier.height(6.dp))
                    Text(
                        tipTarget.meaning,
                        style = MaterialTheme.typography.bodyMedium,
                        color = InkText
                    )
                }
                }
            }
        }
    }
}

@Composable
private fun VocabularyCard(vocab: VocabularyItem, onSpeak: () -> Unit) {
    Card(
        modifier = Modifier.fillMaxWidth().clickable { onSpeak() },
        shape = ResultCardShape,
        colors = CardDefaults.cardColors(containerColor = CardSurface),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp),
        border = BorderStroke(1.dp, CardBorder)
    ) {
        Row(modifier = Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    vocab.word,
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.Bold,
                    color = InkText
                )
                if (vocab.ipa.isNotEmpty()) {
                    Text(
                        vocab.ipa,
                        style = MaterialTheme.typography.bodySmall,
                        color = Color(0xFF667085)
                    )
                }
                Text(
                    vocab.meaning_zh,
                    style = MaterialTheme.typography.bodyMedium,
                    color = Color(0xFF344054)
                )
            }
            Icon(Icons.Default.VolumeUp, contentDescription = "发音", tint = Color(0xFF1565C0))
        }
    }
}

private fun parseAnswerLines(referenceAnswer: String): List<AnswerLine> {
    val rawText = referenceAnswer.trim()
    if (rawText.isBlank()) return emptyList()

    val compact = rawText.replace('\n', ' ')
    val compactMatches = numberedAnswerPattern.findAll(compact).toList()
    if (compactMatches.isNotEmpty()) {
        return compactMatches.mapIndexed { index, match ->
            AnswerLine(
                id = "answer-$index",
                number = match.groupValues[1].toIntOrNull(),
                text = match.groupValues[2].trim().trimEnd(';', '；', '，', ',', '、', '/')
            )
        }.filter { it.text.isNotBlank() }
    }

    return rawText.lines().mapIndexedNotNull { index, line ->
        val trimmed = line.trim()
        if (trimmed.isBlank()) return@mapIndexedNotNull null
        val match = fallbackAnswerLinePattern.matchEntire(trimmed)
        if (match != null) {
            AnswerLine(
                id = "answer-$index",
                number = match.groupValues[1].toIntOrNull(),
                text = match.groupValues[2].trim()
            )
        } else {
            AnswerLine(
                id = "answer-$index",
                number = null,
                text = trimmed
            )
        }
    }
}

private fun tokenizeSpeakTokens(text: String): List<SpeakToken> {
    val raw = text.trim()
    if (raw.isBlank()) return emptyList()
    return speakTokenPattern.findAll(raw).map { match ->
        val token = match.value
        val speakable = token.matches(Regex("""[A-Za-z]+(?:'[A-Za-z]+)?|\d+"""))
        SpeakToken(text = token, speakable = speakable)
    }.toList()
}

private fun normalizeWord(raw: String): String {
    val lower = raw.trim().lowercase(Locale.US)
    return stripWordPattern.replace(lower, "")
}

private fun normalizeSentence(raw: String): String {
    return whitespacePattern.replace(raw.trim().lowercase(Locale.US), " ")
}

private fun buildVocabularyLookup(items: List<VocabularyItem>): Map<String, VocabularyItem> {
    val lookup = linkedMapOf<String, VocabularyItem>()
    items.forEach { item ->
        val key = normalizeWord(item.word)
        if (key.isNotEmpty()) {
            lookup[key] = item
        }
    }
    return lookup
}

private fun buildSentenceTranslationLookup(units: List<SpeakUnit>): Map<String, String> {
    val lookup = linkedMapOf<String, String>()
    units.filter { it.type == "sentence" }.forEach { unit ->
        val translation = unit.meaning_zh?.trim()
        if (translation.isNullOrBlank()) return@forEach
        val key = normalizeSentence(unit.text)
        if (key.isNotEmpty()) {
            lookup[key] = translation
        }
    }
    return lookup
}

private fun findSentenceTranslation(
    text: String,
    sentenceTranslationLookup: Map<String, String>
): String? {
    val key = normalizeSentence(text)
    if (key.isNotEmpty()) {
        sentenceTranslationLookup[key]?.let { return it }
    }
    val withoutNumber = fallbackAnswerLinePattern.matchEntire(text.trim())
        ?.groupValues
        ?.getOrNull(2)
        ?.trim()
    if (!withoutNumber.isNullOrBlank()) {
        sentenceTranslationLookup[normalizeSentence(withoutNumber)]?.let { return it }
    }
    return null
}

private fun buildTipTarget(
    id: String,
    rawWord: String,
    vocabLookup: Map<String, VocabularyItem>
): WordTipTarget? {
    val normalized = normalizeWord(rawWord)
    if (normalized.isEmpty()) return null

    val vocab = lookupVocabulary(normalized, vocabLookup)
    val meaning = vocab?.meaning_zh?.takeIf { it.isNotBlank() }
        ?: "暂无释义"
    return WordTipTarget(
        id = id,
        word = rawWord,
        ipa = vocab?.ipa?.takeIf { it.isNotBlank() },
        meaning = meaning
    )
}

private fun lookupVocabulary(
    normalizedWord: String,
    vocabLookup: Map<String, VocabularyItem>
): VocabularyItem? {
    if (normalizedWord.isBlank()) return null
    val candidates = buildList {
        add(normalizedWord)
        if (normalizedWord.length > 3 && normalizedWord.endsWith("ies")) {
            add(normalizedWord.dropLast(3) + "y")
        }
        if (normalizedWord.length > 2 && normalizedWord.endsWith("es")) {
            add(normalizedWord.dropLast(2))
        }
        if (normalizedWord.length > 1 && normalizedWord.endsWith("s")) {
            add(normalizedWord.dropLast(1))
        }
    }.distinct()
    for (candidate in candidates) {
        vocabLookup[candidate]?.let { return it }
    }
    return null
}
