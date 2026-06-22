package com.homework.assistant.ui.capture

import android.Manifest
import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CameraAlt
import androidx.compose.material.icons.filled.Collections
import androidx.compose.material.icons.filled.GridView
import androidx.compose.material.icons.filled.List
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.core.content.FileProvider
import com.homework.assistant.HomeworkApplication
import com.homework.assistant.R
import com.homework.assistant.data.model.HomeworkSubjects
import com.homework.assistant.data.model.normalizeSubject
import java.io.File

/**
 * 拍照 / 从相册选择页面
 * 支持相册多选图片
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CaptureScreen(
    selectedSubject: String,
    onSubjectSelected: (String) -> Unit,
    onImageSelected: (Uri) -> Unit,
    onMultipleImagesSelected: (List<Uri>) -> Unit,
    onBatchImagesSelected: (List<Uri>) -> Unit,
    onOpenTasks: () -> Unit
) {
    val context = LocalContext.current
    val ttsManager = (context.applicationContext as HomeworkApplication).ttsManager
    var cameraUri by remember { mutableStateOf<Uri?>(null) }

    LaunchedEffect(Unit) {
        ttsManager.ensureInit(context)
    }

    val mergeGalleryLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.GetMultipleContents()
    ) { uris: List<Uri> ->
        if (uris.isEmpty()) return@rememberLauncherForActivityResult
        if (uris.size == 1) {
            onImageSelected(uris.first())
        } else {
            onMultipleImagesSelected(uris)
        }
    }

    val batchGalleryLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.GetMultipleContents()
    ) { uris: List<Uri> ->
        if (uris.isEmpty()) return@rememberLauncherForActivityResult
        onBatchImagesSelected(uris)
    }

    val cameraLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.TakePicture()
    ) { success ->
        if (success) {
            cameraUri?.let { onImageSelected(it) }
        }
    }

    val permissionLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.RequestPermission()
    ) { granted ->
        if (granted) {
            val file = File(context.cacheDir, "images").apply { mkdirs() }
                .let { File(it, "capture_${System.currentTimeMillis()}.jpg") }
            val uri = FileProvider.getUriForFile(
                context, "${context.packageName}.fileprovider", file
            )
            cameraUri = uri
            cameraLauncher.launch(uri)
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(stringResource(R.string.app_name)) },
                navigationIcon = {
                    IconButton(onClick = onOpenTasks) {
                        Icon(Icons.Default.List, contentDescription = "任务列表")
                    }
                }
            )
        },
        containerColor = Color(0xFFF6F8FB)
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(horizontal = 20.dp, vertical = 20.dp),
            verticalArrangement = Arrangement.spacedBy(18.dp)
        ) {
            CaptureHeader()
            SubjectSection(
                selectedSubject = normalizeSubject(selectedSubject),
                onSubjectSelected = onSubjectSelected
            )
            CaptureActions(
                onTakePhoto = { permissionLauncher.launch(Manifest.permission.CAMERA) },
                onMergeImages = { mergeGalleryLauncher.launch("image/*") },
                onBatchImages = { batchGalleryLauncher.launch("image/*") }
            )
            Spacer(modifier = Modifier.weight(1f))
        }
    }
}

@Composable
private fun CaptureHeader() {
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text(
            text = "拍题解析",
            style = MaterialTheme.typography.headlineMedium,
            fontWeight = FontWeight.SemiBold,
            color = Color(0xFF172033)
        )
        Text(
            text = "选择学科后拍照解析，也可以多图合并或批量创建任务。",
            style = MaterialTheme.typography.bodyLarge,
            color = Color(0xFF667085)
        )
    }
}

@Composable
private fun SubjectSection(
    selectedSubject: String,
    onSubjectSelected: (String) -> Unit
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(8.dp),
        colors = CardDefaults.cardColors(containerColor = Color.White),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp),
        border = BorderStroke(1.dp, Color(0xFFE3E8EF))
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            Text(
                text = "选择学科",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold,
                color = Color(0xFF172033)
            )
            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                HomeworkSubjects.chunked(2).forEach { rowSubjects ->
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(10.dp)
                    ) {
                        rowSubjects.forEach { subject ->
                            SubjectChoice(
                                label = subject.label,
                                selected = subject.code == selectedSubject,
                                onClick = { onSubjectSelected(subject.code) },
                                modifier = Modifier.weight(1f)
                            )
                        }
                        if (rowSubjects.size == 1) {
                            Spacer(modifier = Modifier.weight(1f))
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun SubjectChoice(
    label: String,
    selected: Boolean,
    onClick: () -> Unit,
    modifier: Modifier = Modifier
) {
    val background = if (selected) Color(0xFFEAF3FF) else Color(0xFFF8FAFC)
    val border = if (selected) Color(0xFF2F80ED) else Color(0xFFE0E7EF)
    val textColor = if (selected) Color(0xFF145DB8) else Color(0xFF344054)

    Surface(
        modifier = modifier
            .height(50.dp)
            .clickable(onClick = onClick),
        shape = RoundedCornerShape(8.dp),
        color = background,
        border = BorderStroke(1.dp, border)
    ) {
        Box(contentAlignment = Alignment.Center) {
            Text(
                text = label,
                style = MaterialTheme.typography.titleSmall,
                fontWeight = if (selected) FontWeight.SemiBold else FontWeight.Medium,
                color = textColor,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis
            )
        }
    }
}

@Composable
private fun CaptureActions(
    onTakePhoto: () -> Unit,
    onMergeImages: () -> Unit,
    onBatchImages: () -> Unit
) {
    Column(verticalArrangement = Arrangement.spacedBy(14.dp)) {
        CaptureActionCard(
            title = "拍照解析",
            subtitle = "拍一张题图，裁剪后开始解析",
            icon = Icons.Default.CameraAlt,
            onClick = onTakePhoto,
            primary = true,
            modifier = Modifier.fillMaxWidth()
        )
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            CaptureActionCard(
                title = "多图合并",
                subtitle = "多张拼成一道题",
                icon = Icons.Default.Collections,
                onClick = onMergeImages,
                modifier = Modifier.weight(1f)
            )
            CaptureActionCard(
                title = "批量解析",
                subtitle = "多张分别建任务",
                icon = Icons.Default.GridView,
                onClick = onBatchImages,
                modifier = Modifier.weight(1f)
            )
        }
    }
}

@Composable
private fun CaptureActionCard(
    title: String,
    subtitle: String,
    icon: ImageVector,
    onClick: () -> Unit,
    primary: Boolean = false,
    modifier: Modifier = Modifier
) {
    val background = if (primary) Color(0xFF1769E0) else Color.White
    val border = if (primary) Color(0xFF1769E0) else Color(0xFFD8DEE8)
    val iconBackground = if (primary) Color.White.copy(alpha = 0.18f) else Color(0xFFEAF3FF)
    val iconColor = if (primary) Color.White else Color(0xFF1565C0)
    val titleColor = if (primary) Color.White else Color(0xFF172033)
    val subtitleColor = if (primary) Color.White.copy(alpha = 0.86f) else Color(0xFF667085)
    val height = if (primary) 104.dp else 112.dp

    Surface(
        modifier = modifier
            .height(height)
            .clickable(onClick = onClick),
        shape = RoundedCornerShape(8.dp),
        color = background,
        border = BorderStroke(1.dp, border)
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(16.dp),
            verticalArrangement = if (primary) Arrangement.Center else Arrangement.Top
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Box(
                    modifier = Modifier
                        .size(if (primary) 46.dp else 38.dp)
                        .background(iconBackground, RoundedCornerShape(8.dp)),
                    contentAlignment = Alignment.Center
                ) {
                    Icon(icon, contentDescription = null, tint = iconColor)
                }
                Spacer(modifier = Modifier.width(12.dp))
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        text = title,
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.SemiBold,
                        color = titleColor,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis
                    )
                    Text(
                        text = subtitle,
                        style = MaterialTheme.typography.bodyMedium,
                        color = subtitleColor,
                        maxLines = if (primary) 1 else 2,
                        overflow = TextOverflow.Ellipsis
                    )
                }
            }
        }
    }
}
