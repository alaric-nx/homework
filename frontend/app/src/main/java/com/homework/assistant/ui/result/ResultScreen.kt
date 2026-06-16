@file:OptIn(ExperimentalMaterial3Api::class, ExperimentalLayoutApi::class)

package com.homework.assistant.ui.result

import android.graphics.BitmapFactory
import android.os.Handler
import android.os.Looper
import android.view.MotionEvent
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Image
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
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Translate
import androidx.compose.material.icons.filled.VolumeUp
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
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
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.input.pointer.pointerInteropFilter
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.layout.onSizeChanged
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Popup
import androidx.compose.ui.window.PopupProperties
import com.google.gson.Gson
import com.homework.assistant.HomeworkApplication
import com.homework.assistant.R
import com.homework.assistant.data.model.AnswerLine as ResultAnswerLine
import com.homework.assistant.data.model.ParseResult
import com.homework.assistant.data.model.SpeakUnit
import com.homework.assistant.data.model.VocabularyItem
import java.util.Locale

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
private const val WordTipPressDelayMs = 500L

private data class DisplayAnswerLine(
    val id: String,
    val number: String?,
    val lineType: String,
    val text: String,
    val segments: List<DisplayAnswerSegment>
)

private data class DisplayAnswerSegment(
    val text: String,
    val role: String
)

private data class SpeakToken(
    val text: String,
    val speakable: Boolean,
    val role: String = "answer"
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
    var originalImagePath by remember { mutableStateOf<String?>(null) }
    var loading by remember { mutableStateOf(true) }
    var activeTip by remember { mutableStateOf<WordTipTarget?>(null) }
    var activeSentenceTip by remember { mutableStateOf<SentenceTipTarget?>(null) }

    LaunchedEffect(taskId) {
        val task = repo.getById(taskId)
        originalImagePath = task?.imagePath
        if (task != null && task.resultJson != null) {
            result = gson.fromJson(task.resultJson, ParseResult::class.java)
        }
        loading = false
    }

    val answerLines = remember(result) {
        buildDisplayAnswerLines(result?.answer_lines.orEmpty())
    }
    val vocabLookup = remember(result) {
        buildVocabularyLookup(
            items = result?.key_vocabulary.orEmpty(),
            units = result?.speak_units.orEmpty()
        )
    }
    val sentenceTranslationLookup = remember(result) {
        buildSentenceTranslationLookup(result?.speak_units.orEmpty())
    }
    val originalBitmap = remember(originalImagePath) {
        originalImagePath?.let { path ->
            try {
                BitmapFactory.decodeFile(path)?.asImageBitmap()
            } catch (_: Exception) {
                null
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
                    if (originalBitmap != null) {
                        item {
                            OriginalQuestionImageCard(
                                image = originalBitmap,
                                contentDescription = "题目原图"
                            )
                        }
                    } else {
                        item { SectionCard("题目原图", "原图暂不可用") }
                    }
                    if (r.uncertainty.requires_review && !r.uncertainty.warning.isNullOrEmpty()) {
                        item { UncertaintyBanner(r.uncertainty.warning!!) }
                    }
                    item {
                        QuestionRequirementCard(
                            title = stringResource(R.string.question_meaning),
                            content = r.question_meaning_zh,
                            speakText = extractQuestionRequirement(r.question_meaning_zh),
                            onSpeak = {
                                activeTip = null
                                activeSentenceTip = null
                                ttsManager.speak(it)
                            }
                        )
                    }
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
                            SectionCard(stringResource(R.string.reference_answer), "暂无参考答案")
                        }
                    }
                    item { SectionCard(stringResource(R.string.explanation), r.explanation_zh) }
                }
            }
        }
    }
}

@Composable
private fun OriginalQuestionImageCard(
    image: ImageBitmap,
    contentDescription: String
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = ResultCardShape,
        colors = CardDefaults.cardColors(containerColor = CardSurface),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp),
        border = BorderStroke(1.dp, CardBorder)
    ) {
        Column(modifier = Modifier.padding(12.dp)) {
            Text(
                "题目原图",
                style = MaterialTheme.typography.titleSmall,
                fontWeight = FontWeight.Bold,
                color = Color(0xFF174A7C)
            )
            Spacer(modifier = Modifier.height(10.dp))
            Image(
                bitmap = image,
                contentDescription = contentDescription,
                contentScale = ContentScale.Fit,
                modifier = Modifier
                    .fillMaxWidth()
                    .heightIn(min = 120.dp, max = 320.dp)
            )
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
private fun QuestionRequirementCard(
    title: String,
    content: String,
    speakText: String,
    onSpeak: (String) -> Unit
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = ResultCardShape,
        colors = CardDefaults.cardColors(containerColor = CardSurface),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp),
        border = BorderStroke(1.dp, CardBorder)
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.Top
            ) {
                Text(
                    title,
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.Bold,
                    color = Color(0xFF174A7C)
                )
                IconButton(onClick = { onSpeak(speakText) }) {
                    Icon(
                        Icons.Default.VolumeUp,
                        contentDescription = stringResource(R.string.pronunciation_voice),
                        tint = Color(0xFF1565C0)
                    )
                }
            }
            Spacer(modifier = Modifier.height(8.dp))
            Text(content, style = MaterialTheme.typography.bodyLarge, color = InkText)
        }
    }
}

@Composable
private fun AnswerPronunciationCard(
    title: String,
    lines: List<DisplayAnswerLine>,
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
                    lineType = line.lineType,
                    text = line.text,
                    segments = line.segments,
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
private fun SpeakableLineRow(
    lineId: String,
    number: String?,
    lineType: String,
    text: String,
    segments: List<DisplayAnswerSegment>,
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
                    text = number,
                    modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp),
                    style = MaterialTheme.typography.labelMedium,
                    fontWeight = FontWeight.Bold
                )
            }
            Spacer(modifier = Modifier.width(10.dp))
        }

        if (shouldRenderAsAtomicLine(lineType, text, segments)) {
            AtomicAnswerLine(
                lineId = lineId,
                text = text,
                segments = segments,
                vocabLookup = vocabLookup,
                activeTip = activeTip,
                onTipChange = onTipChange,
                onSpeakWord = onSpeakWord,
                modifier = Modifier.weight(1f)
            )
        } else {
            FlowRow(
                modifier = Modifier.weight(1f),
                horizontalArrangement = Arrangement.spacedBy(4.dp),
                verticalArrangement = Arrangement.spacedBy(6.dp)
            ) {
                val tokens = tokenizeDisplayTokens(segments)
                tokens.forEachIndexed { index, token ->
                    if (token.speakable) {
                        SpeakableWordToken(
                            token = token.text,
                            role = token.role,
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
                            color = answerSegmentColor(token.role)
                        )
                    }
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
private fun AtomicAnswerLine(
    lineId: String,
    text: String,
    segments: List<DisplayAnswerSegment>,
    vocabLookup: Map<String, VocabularyItem>,
    activeTip: WordTipTarget?,
    onTipChange: (WordTipTarget?) -> Unit,
    onSpeakWord: (String) -> Unit,
    modifier: Modifier = Modifier
) {
    val tipTarget = buildTipTarget(
        id = "$lineId-atomic",
        rawWord = text,
        vocabLookup = vocabLookup
    )
    val isTipOpen = tipTarget != null && activeTip?.id == tipTarget.id
    val mainHandler = remember { Handler(Looper.getMainLooper()) }
    var tipRunnable by remember { mutableStateOf<Runnable?>(null) }
    var tipShownForCurrentPress by remember { mutableStateOf(false) }

    DisposableEffect(Unit) {
        onDispose {
            tipRunnable?.let { mainHandler.removeCallbacks(it) }
            tipRunnable = null
        }
    }

    Box(
        modifier = modifier.pointerInteropFilter { event ->
            when (event.actionMasked) {
                MotionEvent.ACTION_DOWN -> {
                    tipRunnable?.let { mainHandler.removeCallbacks(it) }
                    tipShownForCurrentPress = false
                    val pendingTip = Runnable {
                        if (tipTarget != null) {
                            tipShownForCurrentPress = true
                            onTipChange(tipTarget)
                        }
                    }
                    tipRunnable = pendingTip
                    mainHandler.postDelayed(pendingTip, WordTipPressDelayMs)
                    true
                }

                MotionEvent.ACTION_UP -> {
                    tipRunnable?.let { mainHandler.removeCallbacks(it) }
                    tipRunnable = null
                    if (!tipShownForCurrentPress) {
                        onTipChange(null)
                        onSpeakWord(text)
                    }
                    tipShownForCurrentPress = false
                    true
                }

                MotionEvent.ACTION_CANCEL -> {
                    tipRunnable?.let { mainHandler.removeCallbacks(it) }
                    tipRunnable = null
                    tipShownForCurrentPress = false
                    true
                }

                else -> true
            }
        }
    ) {
        FlowRow(
            horizontalArrangement = Arrangement.spacedBy(2.dp),
            verticalArrangement = Arrangement.spacedBy(6.dp)
        ) {
            segments.forEach { segment ->
                Text(
                    text = segment.text,
                    style = MaterialTheme.typography.bodyLarge,
                    color = answerSegmentColor(segment.role)
                )
            }
        }

        if (tipTarget != null) {
            var popupHeightPx by remember { mutableStateOf(0) }
            if (isTipOpen) {
                Popup(
                    alignment = Alignment.TopCenter,
                    offset = IntOffset(0, -popupHeightPx - 10),
                    onDismissRequest = { onTipChange(null) },
                    properties = PopupProperties(focusable = true)
                ) {
                    Surface(
                        modifier = Modifier
                            .widthIn(min = 160.dp, max = 240.dp)
                            .onSizeChanged { popupHeightPx = it.height },
                        shape = ResultCardShape,
                        color = CardSurface,
                        tonalElevation = 6.dp,
                        shadowElevation = 8.dp,
                        border = BorderStroke(1.dp, CardBorder)
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
        var popupHeightPx by remember { mutableStateOf(0) }
        if (isTipOpen) {
            Popup(
                alignment = Alignment.TopCenter,
                offset = IntOffset(0, -popupHeightPx - 10),
                onDismissRequest = { onTipChange(null) },
                properties = PopupProperties(focusable = true)
            ) {
            Surface(
                modifier = Modifier
                    .widthIn(min = 180.dp, max = 280.dp)
                    .onSizeChanged { popupHeightPx = it.height },
                shape = ResultCardShape,
                color = CardSurface,
                tonalElevation = 6.dp,
                shadowElevation = 8.dp,
                border = BorderStroke(1.dp, CardBorder)
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
}

@Composable
private fun SpeakableWordToken(
    token: String,
    role: String,
    tipTarget: WordTipTarget?,
    activeTip: WordTipTarget?,
    onTipChange: (WordTipTarget?) -> Unit,
    onSpeakWord: (String) -> Unit
) {
    val isTipOpen = tipTarget != null && activeTip?.id == tipTarget.id
    val mainHandler = remember { Handler(Looper.getMainLooper()) }
    var tipRunnable by remember { mutableStateOf<Runnable?>(null) }
    var tipShownForCurrentPress by remember { mutableStateOf(false) }

    DisposableEffect(Unit) {
        onDispose {
            tipRunnable?.let { mainHandler.removeCallbacks(it) }
            tipRunnable = null
        }
    }

    Box(
        modifier = Modifier
            .pointerInteropFilter { event ->
                when (event.actionMasked) {
                    MotionEvent.ACTION_DOWN -> {
                        tipRunnable?.let { mainHandler.removeCallbacks(it) }
                        tipShownForCurrentPress = false
                        val pendingTip = Runnable {
                            if (tipTarget != null) {
                                tipShownForCurrentPress = true
                                onTipChange(tipTarget)
                            }
                        }
                        tipRunnable = pendingTip
                        mainHandler.postDelayed(pendingTip, WordTipPressDelayMs)
                        true
                    }

                    MotionEvent.ACTION_UP -> {
                        tipRunnable?.let { mainHandler.removeCallbacks(it) }
                        tipRunnable = null
                        if (!tipShownForCurrentPress) {
                            onTipChange(null)
                            onSpeakWord(token)
                        }
                        tipShownForCurrentPress = false
                        true
                    }

                    MotionEvent.ACTION_CANCEL -> {
                        tipRunnable?.let { mainHandler.removeCallbacks(it) }
                        tipRunnable = null
                        tipShownForCurrentPress = false
                        true
                    }

                    else -> true
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
                answerSegmentColor(role)
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
            var popupHeightPx by remember { mutableStateOf(0) }
            if (isTipOpen) {
                Popup(
                    alignment = Alignment.TopCenter,
                    offset = IntOffset(0, -popupHeightPx - 10),
                    onDismissRequest = { onTipChange(null) },
                    properties = PopupProperties(focusable = true)
                ) {
                Surface(
                    modifier = Modifier
                        .widthIn(min = 160.dp, max = 240.dp)
                        .onSizeChanged { popupHeightPx = it.height },
                    shape = ResultCardShape,
                    color = CardSurface,
                    tonalElevation = 6.dp,
                    shadowElevation = 8.dp,
                    border = BorderStroke(1.dp, CardBorder)
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
}

private fun buildDisplayAnswerLines(answerLines: List<ResultAnswerLine>): List<DisplayAnswerLine> {
    return answerLines.mapIndexedNotNull { index, line ->
        val plainText = line.plain_text.trim()
        val rawSegments = line.segments
            .mapNotNull { segment ->
                val text = segment.text
                if (text.isBlank()) {
                    null
                } else {
                    DisplayAnswerSegment(text = text, role = segment.role)
                }
            }
        val segments = rawSegments.ifEmpty {
            plainText.takeIf { it.isNotBlank() }?.let {
                listOf(DisplayAnswerSegment(text = it, role = "answer"))
            }.orEmpty()
        }
        val text = plainText.ifBlank {
            segments.joinToString(separator = "") { it.text }.trim()
        }
        if (text.isBlank()) return@mapIndexedNotNull null

        DisplayAnswerLine(
            id = "answer-$index",
            number = line.number?.trim()?.takeIf { it.isNotBlank() },
            lineType = line.line_type.trim().lowercase(Locale.US),
            text = text,
            segments = segments
        )
    }
}

private fun extractQuestionRequirement(questionMeaning: String): String {
    val lines = questionMeaning.lines()
        .map { it.trim() }
        .filter { it.isNotBlank() }
    return lines.getOrNull(1) ?: lines.firstOrNull().orEmpty()
}

private fun shouldRenderAsAtomicLine(
    lineType: String,
    text: String,
    segments: List<DisplayAnswerSegment>
): Boolean {
    val normalizedType = lineType.trim().lowercase(Locale.US)
    val cleanText = text.trim()
    if (cleanText.isBlank() || whitespacePattern.containsMatchIn(cleanText)) {
        return false
    }

    val nonBlankSegments = segments.mapNotNull { segment ->
        segment.text.trim().takeIf { it.isNotBlank() }
    }
    if (nonBlankSegments.size < 2) {
        return false
    }

    val allLetters = nonBlankSegments.all { part ->
        part.all { ch -> ch.isLetter() || ch == '\'' }
    }
    val mostlyShortPieces = nonBlankSegments.count { it.length <= 2 } >= 2
    return allLetters && mostlyShortPieces &&
        normalizedType in setOf("fill_blank", "picture_word", "other")
}

private fun tokenizeDisplayTokens(segments: List<DisplayAnswerSegment>): List<SpeakToken> {
    return segments.flatMap { segment ->
        tokenizeSpeakTokens(segment.text, segment.role)
    }
}

private fun tokenizeSpeakTokens(text: String, role: String = "answer"): List<SpeakToken> {
    val raw = text.trim()
    if (raw.isBlank()) return emptyList()
    return speakTokenPattern.findAll(raw).map { match ->
        val token = match.value
        val speakable = token.matches(Regex("""[A-Za-z]+(?:'[A-Za-z]+)?|\d+"""))
        SpeakToken(text = token, speakable = speakable, role = role)
    }.toList()
}

private fun answerSegmentColor(role: String): Color {
    return when (role.lowercase(Locale.US)) {
        "given" -> InkText
        "answer" -> Color(0xFFD32F2F)
        "connector" -> Color(0xFF667085)
        "correction" -> Color(0xFFE65100)
        else -> Color(0xFFD32F2F)
    }
}

private fun normalizeWord(raw: String): String {
    val lower = raw.trim().lowercase(Locale.US)
    return stripWordPattern.replace(lower, "")
}

private fun normalizeSentence(raw: String): String {
    return whitespacePattern.replace(raw.trim().lowercase(Locale.US), " ")
}

private fun buildVocabularyLookup(
    items: List<VocabularyItem>,
    units: List<SpeakUnit>
): Map<String, VocabularyItem> {
    val lookup = linkedMapOf<String, VocabularyItem>()
    items.forEach { item ->
        val key = normalizeWord(item.word)
        if (key.isNotEmpty()) {
            lookup[key] = item
        }
    }
    units.filter { it.type == "word" }.forEach { unit ->
        val meaning = unit.meaning_zh?.trim()
        if (meaning.isNullOrBlank()) return@forEach
        val key = normalizeWord(unit.text)
        if (key.isNotEmpty() && lookup[key] == null) {
            lookup[key] = VocabularyItem(
                word = unit.text,
                meaning_zh = meaning,
                ipa = ""
            )
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
        ?: "暂无释义，点击可发音"
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
