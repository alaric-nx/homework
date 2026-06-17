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
import com.homework.assistant.data.model.LearningPoint
import com.homework.assistant.data.model.ParseResult
import com.homework.assistant.data.model.QuestionBlock
import com.homework.assistant.data.model.ReadUnit
import com.homework.assistant.data.model.SolutionStep
import com.homework.assistant.data.model.subjectLabel
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
    val blockId: String,
    val number: String?,
    val lineType: String,
    val text: String,
    val segments: List<DisplayAnswerSegment>
)

private data class DisplayQuestionBlock(
    val blockId: String,
    val title: String,
    val instructionText: String,
    val instructionMeaning: String,
    val questionMeaning: String,
    val lines: List<DisplayAnswerLine>
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

/** 某个交互功能的可见性策略。 */
private enum class FeatureVisibility {
    /** 始终显示 */
    ALWAYS,
    /** 仅当有对应数据时显示（按需） */
    WHEN_AVAILABLE,
    /** 从不显示 */
    NEVER
}

/**
 * 按学科决定结果页各交互/展示的差异。
 * - english：单词释义 tip + 翻译 + 朗读 + 音标，全开。
 * - liberal_arts：无单词 tip；古诗文有今译时显示翻译；可朗读；发音=拼音。
 * - science：答案行不朗读、无 tip、无翻译、不显示发音。
 * - general：按需（有数据才显示对应功能）。
 */
private data class SubjectDisplayPolicy(
    val wordTip: FeatureVisibility,
    val translate: FeatureVisibility,
    val answerLineSpeak: Boolean,
    val showPronunciation: Boolean,
    val pronunciationLabel: String,
    val subject: String
) {
    fun showTranslate(translation: String?): Boolean = when (translate) {
        FeatureVisibility.ALWAYS -> true
        FeatureVisibility.WHEN_AVAILABLE -> !translation.isNullOrBlank()
        FeatureVisibility.NEVER -> false
    }

    companion object {
        fun forSubject(subject: String): SubjectDisplayPolicy = when (subject) {
            "english" -> SubjectDisplayPolicy(
                wordTip = FeatureVisibility.ALWAYS,
                translate = FeatureVisibility.ALWAYS,
                answerLineSpeak = true,
                showPronunciation = true,
                pronunciationLabel = "音标",
                subject = subject
            )
            "liberal_arts" -> SubjectDisplayPolicy(
                wordTip = FeatureVisibility.NEVER,
                translate = FeatureVisibility.WHEN_AVAILABLE,
                answerLineSpeak = true,
                showPronunciation = true,
                pronunciationLabel = "拼音",
                subject = subject
            )
            "science" -> SubjectDisplayPolicy(
                wordTip = FeatureVisibility.NEVER,
                translate = FeatureVisibility.NEVER,
                answerLineSpeak = false,
                showPronunciation = false,
                pronunciationLabel = "",
                subject = subject
            )
            else -> SubjectDisplayPolicy(
                // general：按需
                wordTip = FeatureVisibility.WHEN_AVAILABLE,
                translate = FeatureVisibility.WHEN_AVAILABLE,
                answerLineSpeak = true,
                showPronunciation = true,
                pronunciationLabel = "读音",
                subject = "general"
            )
        }
    }
}

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

    val questionBlocks = remember(result) {
        buildDisplayQuestionBlocks(
            blocks = result?.question_blocks.orEmpty(),
            answerLines = result?.answer_lines.orEmpty()
        )
    }
    val vocabResolver = remember(result) {
        VocabResolver(
            lookup = buildVocabularyLookup(
                items = result?.learning_points.orEmpty(),
                units = result?.read_units.orEmpty()
            ),
            englishStemming = result?.subject == "english"
        )
    }
    val displayPolicy = remember(result) {
        SubjectDisplayPolicy.forSubject(result?.subject ?: "general")
    }
    val sentenceTranslationLookup = remember(result) {
        buildSentenceTranslationLookup(result?.read_units.orEmpty())
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
                            title = stringResource(R.string.question_requirement),
                            subject = r.subject,
                            text = r.question_instruction.text,
                            meaningZh = r.question_instruction.meaning_zh,
                            onSpeak = {
                                activeTip = null
                                activeSentenceTip = null
                                ttsManager.speak(it)
                            }
                        )
                    }
                    item { SectionCard(stringResource(R.string.question_meaning), r.question_meaning_zh) }
                    if (questionBlocks.isNotEmpty()) {
                        questionBlocks.forEach { block ->
                            item {
                                QuestionBlockAnswerCard(
                                    block = block,
                                    vocabResolver = vocabResolver,
                                    displayPolicy = displayPolicy,
                                    sentenceTranslationLookup = sentenceTranslationLookup,
                                    activeTip = activeTip,
                                    activeSentenceTip = activeSentenceTip,
                                    onTipChange = { activeTip = it },
                                    onSentenceTipChange = { activeSentenceTip = it },
                                    onSpeakInstruction = {
                                        activeTip = null
                                        activeSentenceTip = null
                                        ttsManager.speak(it)
                                    },
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
                    } else {
                        item {
                            SectionCard(stringResource(R.string.reference_answer), "暂无参考答案")
                        }
                    }
                    if (r.solution_steps.isNotEmpty()) {
                        item { SolutionStepsCard(r.solution_steps) }
                    }
                    item { SectionCard(stringResource(R.string.explanation), r.explanation_zh) }
                    if (r.learning_points.isNotEmpty()) {
                        item { LearningPointsCard(r.learning_points, displayPolicy) }
                    }
                }
            }
        }
    }
}

@Composable
private fun QuestionBlockAnswerCard(
    block: DisplayQuestionBlock,
    vocabResolver: VocabResolver,
    displayPolicy: SubjectDisplayPolicy,
    sentenceTranslationLookup: Map<String, String>,
    activeTip: WordTipTarget?,
    activeSentenceTip: SentenceTipTarget?,
    onTipChange: (WordTipTarget?) -> Unit,
    onSentenceTipChange: (SentenceTipTarget?) -> Unit,
    onSpeakInstruction: (String) -> Unit,
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
                block.title,
                style = MaterialTheme.typography.titleSmall,
                fontWeight = FontWeight.Bold,
                color = Color(0xFF174A7C)
            )
            if (block.instructionText.isNotBlank() || block.instructionMeaning.isNotBlank()) {
                CompactInstructionRow(
                    text = block.instructionText,
                    meaningZh = block.instructionMeaning,
                    onSpeak = onSpeakInstruction
                )
            }
            if (block.questionMeaning.isNotBlank()) {
                Text(
                    block.questionMeaning,
                    style = MaterialTheme.typography.bodyMedium,
                    color = Color(0xFF475467)
                )
            }
            if (block.lines.isNotEmpty()) {
                HorizontalDivider(color = Color(0xFFE9EDF3))
                AnswerPronunciationContent(
                    lines = block.lines,
                    vocabResolver = vocabResolver,
                    displayPolicy = displayPolicy,
                    sentenceTranslationLookup = sentenceTranslationLookup,
                    activeTip = activeTip,
                    activeSentenceTip = activeSentenceTip,
                    onTipChange = onTipChange,
                    onSentenceTipChange = onSentenceTipChange,
                    onSpeakLine = onSpeakLine,
                    onSpeakWord = onSpeakWord
                )
            } else {
                Text("暂无参考答案", style = MaterialTheme.typography.bodyMedium, color = Color(0xFF667085))
            }
        }
    }
}

@Composable
private fun CompactInstructionRow(
    text: String,
    meaningZh: String,
    onSpeak: (String) -> Unit
) {
    val instructionText = text.trim()
    Row(
        modifier = Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.Top
    ) {
        Column(modifier = Modifier.weight(1f)) {
            if (instructionText.isNotBlank()) {
                Text(
                    instructionText,
                    style = MaterialTheme.typography.bodyLarge,
                    fontWeight = FontWeight.SemiBold,
                    color = InkText
                )
            }
            val meaning = meaningZh.trim()
            if (meaning.isNotBlank()) {
                Text(
                    meaning,
                    style = MaterialTheme.typography.bodyMedium,
                    color = Color(0xFF475467)
                )
            }
        }
        IconButton(
            onClick = {
                if (instructionText.isNotBlank()) {
                    onSpeak(instructionText)
                }
            },
            enabled = instructionText.isNotBlank()
        ) {
            Icon(
                Icons.Default.VolumeUp,
                contentDescription = stringResource(R.string.pronunciation_voice),
                tint = Color(0xFF1565C0)
            )
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
private fun SubjectPill(subject: String) {
    Surface(
        shape = TokenShape,
        color = SoftPrimarySurface,
        contentColor = Color(0xFF15528C),
        border = BorderStroke(1.dp, Color(0xFFC7DCF5))
    ) {
        Text(
            text = subjectLabel(subject),
            modifier = Modifier.padding(horizontal = 8.dp, vertical = 3.dp),
            style = MaterialTheme.typography.labelSmall,
            fontWeight = FontWeight.SemiBold
        )
    }
}

@Composable
private fun SolutionStepsCard(steps: List<SolutionStep>) {
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
                stringResource(R.string.solution_steps),
                style = MaterialTheme.typography.titleSmall,
                fontWeight = FontWeight.Bold,
                color = Color(0xFF174A7C)
            )
            steps.forEachIndexed { index, step ->
                if (index > 0) {
                    HorizontalDivider(color = Color(0xFFE9EDF3))
                }
                SolutionStepRow(step)
            }
        }
    }
}

@Composable
private fun SolutionStepRow(step: SolutionStep) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.Top,
        horizontalArrangement = Arrangement.spacedBy(10.dp)
    ) {
        Surface(
            shape = TokenShape,
            color = SoftNeutralSurface,
            contentColor = Color(0xFF475467),
            border = BorderStroke(1.dp, Color(0xFFE3E6EA))
        ) {
            Text(
                text = step.number.ifBlank { "•" },
                modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp),
                style = MaterialTheme.typography.labelMedium,
                fontWeight = FontWeight.Bold
            )
        }
        Column(
            modifier = Modifier.weight(1f),
            verticalArrangement = Arrangement.spacedBy(4.dp)
        ) {
            Text(
                step.title,
                style = MaterialTheme.typography.bodyLarge,
                fontWeight = FontWeight.SemiBold,
                color = InkText
            )
            Text(
                step.content_zh,
                style = MaterialTheme.typography.bodyMedium,
                color = Color(0xFF475467)
            )
            step.formula?.trim()?.takeIf { it.isNotBlank() }?.let {
                Text(
                    it,
                    style = MaterialTheme.typography.bodyMedium,
                    fontWeight = FontWeight.SemiBold,
                    color = Color(0xFF15528C)
                )
            }
            step.result?.trim()?.takeIf { it.isNotBlank() }?.let {
                Text(
                    "结果：$it",
                    style = MaterialTheme.typography.bodyMedium,
                    color = Color(0xFFD32F2F)
                )
            }
        }
    }
}

@Composable
private fun LearningPointsCard(points: List<LearningPoint>, displayPolicy: SubjectDisplayPolicy) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = ResultCardShape,
        colors = CardDefaults.cardColors(containerColor = CardSurface),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp),
        border = BorderStroke(1.dp, CardBorder)
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp)
        ) {
            Text(
                stringResource(R.string.learning_points),
                style = MaterialTheme.typography.titleSmall,
                fontWeight = FontWeight.Bold,
                color = Color(0xFF174A7C)
            )
            points.forEachIndexed { index, point ->
                if (index > 0) {
                    HorizontalDivider(color = Color(0xFFE9EDF3))
                }
                LearningPointRow(point, displayPolicy)
            }
        }
    }
}

@Composable
private fun LearningPointRow(point: LearningPoint, displayPolicy: SubjectDisplayPolicy) {
    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        FlowRow(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            verticalArrangement = Arrangement.spacedBy(4.dp)
        ) {
            Text(
                point.term,
                style = MaterialTheme.typography.bodyLarge,
                fontWeight = FontWeight.SemiBold,
                color = InkText
            )
            // 理科无"发音"概念，不展示 pronunciation；其余学科有才展示。
            if (displayPolicy.showPronunciation) {
                point.pronunciation?.trim()?.takeIf { it.isNotBlank() }?.let {
                    Text(
                        it,
                        style = MaterialTheme.typography.bodySmall,
                        color = Color(0xFF667085)
                    )
                }
            }
            LearningPointCategoryPill(point.category, displayPolicy.subject)
        }
        Text(
            point.explanation_zh,
            style = MaterialTheme.typography.bodyMedium,
            color = Color(0xFF475467)
        )
    }
}

@Composable
private fun LearningPointCategoryPill(category: String, subject: String) {
    Surface(
        shape = TokenShape,
        color = SoftAccentSurface,
        contentColor = Color(0xFF22603A)
    ) {
        Text(
            text = learningPointCategoryLabel(category, subject),
            modifier = Modifier.padding(horizontal = 7.dp, vertical = 2.dp),
            style = MaterialTheme.typography.labelSmall
        )
    }
}

@Composable
private fun QuestionRequirementCard(
    title: String,
    subject: String,
    text: String,
    meaningZh: String,
    onSpeak: (String) -> Unit
) {
    val instructionText = text.trim()
    val displayText = instructionText.ifBlank { "未识别到题目要求" }
    val displayMeaning = meaningZh.trim().ifBlank { "暂无中文解释" }
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
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    Text(
                        title,
                        style = MaterialTheme.typography.titleSmall,
                        fontWeight = FontWeight.Bold,
                        color = Color(0xFF174A7C)
                    )
                    SubjectPill(subject)
                }
                IconButton(
                    onClick = {
                        if (instructionText.isNotBlank()) {
                            onSpeak(instructionText)
                        }
                    },
                    enabled = instructionText.isNotBlank()
                ) {
                    Icon(
                        Icons.Default.VolumeUp,
                        contentDescription = stringResource(R.string.pronunciation_voice),
                        tint = Color(0xFF1565C0)
                    )
                }
            }
            Spacer(modifier = Modifier.height(8.dp))
            Text(
                displayText,
                style = MaterialTheme.typography.bodyLarge,
                color = if (instructionText.isBlank()) Color(0xFF667085) else InkText,
                fontWeight = if (instructionText.isBlank()) FontWeight.Normal else FontWeight.SemiBold
            )
            Spacer(modifier = Modifier.height(6.dp))
            Text(
                displayMeaning,
                style = MaterialTheme.typography.bodyMedium,
                color = Color(0xFF475467)
            )
        }
    }
}

@Composable
private fun AnswerPronunciationContent(
    lines: List<DisplayAnswerLine>,
    vocabResolver: VocabResolver,
    displayPolicy: SubjectDisplayPolicy,
    sentenceTranslationLookup: Map<String, String>,
    activeTip: WordTipTarget?,
    activeSentenceTip: SentenceTipTarget?,
    onTipChange: (WordTipTarget?) -> Unit,
    onSentenceTipChange: (SentenceTipTarget?) -> Unit,
    onSpeakLine: (String) -> Unit,
    onSpeakWord: (String) -> Unit
) {
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
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
                vocabResolver = vocabResolver,
                displayPolicy = displayPolicy,
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

@Composable
private fun SpeakableLineRow(
    lineId: String,
    number: String?,
    lineType: String,
    text: String,
    segments: List<DisplayAnswerSegment>,
    vocabResolver: VocabResolver,
    displayPolicy: SubjectDisplayPolicy,
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

        if (!displayPolicy.answerLineSpeak) {
            // 理科：答案行纯展示，不朗读、不弹词义。
            PlainAnswerLine(segments = segments, modifier = Modifier.weight(1f))
        } else if (shouldRenderAsAtomicLine(lineType, text, segments)) {
            AtomicAnswerLine(
                lineId = lineId,
                text = text,
                segments = segments,
                vocabResolver = vocabResolver,
                displayPolicy = displayPolicy,
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
                                vocabResolver = vocabResolver,
                                wordTip = displayPolicy.wordTip
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

        val showTranslate = displayPolicy.showTranslate(translation)
        if (displayPolicy.answerLineSpeak || showTranslate) {
            Row(
                horizontalArrangement = Arrangement.spacedBy(2.dp),
                verticalAlignment = Alignment.Top
            ) {
                if (displayPolicy.answerLineSpeak) {
                    IconButton(onClick = { onSpeakLine(text) }) {
                        Icon(
                            Icons.Default.VolumeUp,
                            contentDescription = stringResource(R.string.pronunciation_voice),
                            tint = Color(0xFF1565C0)
                        )
                    }
                }
                if (showTranslate) {
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
    }
}

@Composable
private fun PlainAnswerLine(
    segments: List<DisplayAnswerSegment>,
    modifier: Modifier = Modifier
) {
    FlowRow(
        modifier = modifier,
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
}

@Composable
private fun AtomicAnswerLine(
    lineId: String,
    text: String,
    segments: List<DisplayAnswerSegment>,
    vocabResolver: VocabResolver,
    displayPolicy: SubjectDisplayPolicy,
    activeTip: WordTipTarget?,
    onTipChange: (WordTipTarget?) -> Unit,
    onSpeakWord: (String) -> Unit,
    modifier: Modifier = Modifier
) {
    val tipTarget = buildTipTarget(
        id = "$lineId-atomic",
        rawWord = text,
        vocabResolver = vocabResolver,
        wordTip = displayPolicy.wordTip
    )
    val isTipOpen = tipTarget != null && activeTip?.id == tipTarget.id

    Box(
        modifier = modifier.longPressToReadModifier(
            tipTarget = tipTarget,
            onShowTip = onTipChange,
            onClearTip = { onTipChange(null) },
            onSpeak = { onSpeakWord(text) }
        )
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

    Box(
        modifier = Modifier.longPressToReadModifier(
            tipTarget = tipTarget,
            onShowTip = onTipChange,
            onClearTip = { onTipChange(null) },
            onSpeak = { onSpeakWord(token) }
        )
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

@Composable
private fun Modifier.longPressToReadModifier(
    tipTarget: WordTipTarget?,
    onShowTip: (WordTipTarget) -> Unit,
    onClearTip: () -> Unit,
    onSpeak: () -> Unit
): Modifier {
    // 长按延迟弹出词义 tip；短按（未触发 tip）则朗读。
    // 抽出复用，避免在 AtomicAnswerLine 与 SpeakableWordToken 中重复同一段手势代码。
    val mainHandler = remember { Handler(Looper.getMainLooper()) }
    var tipRunnable by remember { mutableStateOf<Runnable?>(null) }
    var tipShownForCurrentPress by remember { mutableStateOf(false) }

    DisposableEffect(Unit) {
        onDispose {
            tipRunnable?.let { mainHandler.removeCallbacks(it) }
            tipRunnable = null
        }
    }

    return this.pointerInteropFilter { event ->
        when (event.actionMasked) {
            MotionEvent.ACTION_DOWN -> {
                tipRunnable?.let { mainHandler.removeCallbacks(it) }
                tipShownForCurrentPress = false
                val pendingTip = Runnable {
                    if (tipTarget != null) {
                        tipShownForCurrentPress = true
                        onShowTip(tipTarget)
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
                    onClearTip()
                    onSpeak()
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
}

private fun buildDisplayQuestionBlocks(
    blocks: List<QuestionBlock>,
    answerLines: List<ResultAnswerLine>
): List<DisplayQuestionBlock> {
    val displayLines = buildDisplayAnswerLines(answerLines)
    val linesByBlock = displayLines.groupBy { it.blockId }
    val knownBlockIds = blocks.mapNotNull { it.block_id.trim().takeIf { id -> id.isNotBlank() } }.toSet()
    val result = blocks.mapIndexedNotNull { index, block ->
        val blockId = block.block_id.trim()
        if (blockId.isBlank()) return@mapIndexedNotNull null
        val title = block.title.trim().ifBlank { "第${index + 1}题" }
        DisplayQuestionBlock(
            blockId = blockId,
            title = title,
            instructionText = block.question_instruction.text.trim(),
            instructionMeaning = block.question_instruction.meaning_zh.trim(),
            questionMeaning = block.question_meaning_zh.trim(),
            lines = linesByBlock[blockId].orEmpty()
        )
    }.toMutableList()

    // 兜底：block_id 无法对应任何题目块的答案行不应被静默丢弃，
    // 统一归入一个"其他"分组展示，避免用户看不到答案。
    val orphanLines = displayLines.filter { it.blockId.isBlank() || it.blockId !in knownBlockIds }
    if (orphanLines.isNotEmpty()) {
        result.add(
            DisplayQuestionBlock(
                blockId = "__orphan__",
                title = "其他",
                instructionText = "",
                instructionMeaning = "",
                questionMeaning = "",
                lines = orphanLines
            )
        )
    }
    return result
}

private fun buildDisplayAnswerLines(answerLines: List<ResultAnswerLine>): List<DisplayAnswerLine> {
    return answerLines.mapIndexedNotNull { index, line ->
        val plainText = line.plain_text.trim()
        val blockId = line.block_id.trim()
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
            blockId = blockId,
            number = line.number?.trim()?.takeIf { it.isNotBlank() },
            lineType = line.line_type.trim().lowercase(Locale.US),
            text = text,
            segments = segments
        )
    }
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

private fun learningPointCategoryLabel(category: String, subject: String): String {
    return when (category.lowercase(Locale.US)) {
        "word" -> if (subject == "liberal_arts") "字词" else "单词"
        "concept" -> "概念"
        "formula" -> "公式"
        "unit" -> "单位"
        "method" -> "方法"
        else -> "知识点"
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
    items: List<LearningPoint>,
    units: List<ReadUnit>
): Map<String, LearningPoint> {
    val lookup = linkedMapOf<String, LearningPoint>()
    items.forEach { item ->
        val key = normalizeWord(item.term)
        if (key.isNotEmpty()) {
            lookup[key] = item
        }
    }
    units.filter { it.unit_type == "word" }.forEach { unit ->
        val meaning = unit.meaning_zh?.trim()
        if (meaning.isNullOrBlank()) return@forEach
        val key = normalizeWord(unit.text)
        if (key.isNotEmpty() && lookup[key] == null) {
            lookup[key] = LearningPoint(
                term = unit.text,
                explanation_zh = meaning,
                category = "word"
            )
        }
    }
    return lookup
}

private fun buildSentenceTranslationLookup(units: List<ReadUnit>): Map<String, String> {
    val lookup = linkedMapOf<String, String>()
    units.filter { it.unit_type == "text" }.forEach { unit ->
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

private class VocabResolver(
    private val lookup: Map<String, LearningPoint>,
    private val englishStemming: Boolean
) {
    fun resolve(rawWord: String): LearningPoint? {
        val normalized = normalizeWord(rawWord)
        if (normalized.isEmpty()) return null
        lookup[normalized]?.let { return it }
        // 英语词形还原（ies/es/s）只对英语学科启用，避免文科/理科术语被误匹配。
        if (!englishStemming) return null
        val candidates = buildList {
            if (normalized.length > 3 && normalized.endsWith("ies")) {
                add(normalized.dropLast(3) + "y")
            }
            if (normalized.length > 2 && normalized.endsWith("es")) {
                add(normalized.dropLast(2))
            }
            if (normalized.length > 1 && normalized.endsWith("s")) {
                add(normalized.dropLast(1))
            }
        }.distinct()
        for (candidate in candidates) {
            lookup[candidate]?.let { return it }
        }
        return null
    }
}

private fun buildTipTarget(
    id: String,
    rawWord: String,
    vocabResolver: VocabResolver,
    wordTip: FeatureVisibility
): WordTipTarget? {
    if (wordTip == FeatureVisibility.NEVER) return null
    val normalized = normalizeWord(rawWord)
    if (normalized.isEmpty()) return null

    val vocab = vocabResolver.resolve(rawWord)
    // 按需模式下，没有真实词义就不弹 tip（避免噪音）。
    if (wordTip == FeatureVisibility.WHEN_AVAILABLE && vocab == null) return null

    val meaning = vocab?.explanation_zh?.takeIf { it.isNotBlank() }
        ?: "暂无解释，点击可朗读"
    return WordTipTarget(
        id = id,
        word = rawWord,
        ipa = vocab?.pronunciation?.takeIf { it.isNotBlank() },
        meaning = meaning
    )
}
