package com.homework.assistant.ui.capture

import android.Manifest
import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CameraAlt
import androidx.compose.material.icons.filled.Collections
import androidx.compose.material.icons.filled.GridView
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
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
    onBatchImagesSelected: (List<Uri>) -> Unit
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

    // 相机拍照
    val cameraLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.TakePicture()
    ) { success ->
        if (success) {
            cameraUri?.let { onImageSelected(it) }
        }
    }

    // 相机权限
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
        topBar = { TopAppBar(title = { Text(stringResource(R.string.app_name)) }) },
        containerColor = Color(0xFFF7F8FA)
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(horizontal = 20.dp, vertical = 18.dp),
            verticalArrangement = Arrangement.spacedBy(18.dp)
        ) {
            CaptureHeader()

            CapturePanel(
                selectedSubject = normalizeSubject(selectedSubject),
                onSubjectSelected = onSubjectSelected,
                onTakePhoto = { permissionLauncher.launch(Manifest.permission.CAMERA) },
                onMergeImages = { mergeGalleryLauncher.launch("image/*") },
                onBatchImages = { batchGalleryLauncher.launch("image/*") }
            )
        }
    }
}

@Composable
private fun CaptureHeader() {
    Column(
        modifier = Modifier.fillMaxWidth(),
        verticalArrangement = Arrangement.spacedBy(6.dp)
    ) {
        Text(
            "拍题解析",
            style = MaterialTheme.typography.headlineMedium,
            fontWeight = FontWeight.SemiBold,
            color = Color(0xFF172033)
        )
        Text(
            "选择学科后拍照、合并多图，或批量创建解析任务。",
            style = MaterialTheme.typography.bodyMedium,
            color = Color(0xFF667085)
        )
    }
}

@Composable
private fun CapturePanel(
    selectedSubject: String,
    onSubjectSelected: (String) -> Unit,
    onTakePhoto: () -> Unit,
    onMergeImages: () -> Unit,
    onBatchImages: () -> Unit
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(10.dp),
        colors = CardDefaults.cardColors(containerColor = Color(0xFFFFFEFC)),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp),
        border = BorderStroke(1.dp, Color(0xFFE4E8EE))
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            SubjectSelector(
                selectedSubject = selectedSubject,
                onSubjectSelected = onSubjectSelected
            )

            CaptureActionButton(
                title = "拍照解析",
                subtitle = "适合单页、单张题图",
                icon = Icons.Default.CameraAlt,
                onClick = onTakePhoto,
                primary = true
            )

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                CompactCaptureAction(
                    title = "多图合并",
                    subtitle = "拼成一道题",
                    icon = Icons.Default.Collections,
                    onClick = onMergeImages,
                    modifier = Modifier.weight(1f)
                )
                CompactCaptureAction(
                    title = "批量解析",
                    subtitle = "多张分别解析",
                    icon = Icons.Default.GridView,
                    onClick = onBatchImages,
                    modifier = Modifier.weight(1f)
                )
            }
        }
    }
}

@Composable
private fun SubjectSelector(
    selectedSubject: String,
    onSubjectSelected: (String) -> Unit
) {
    Column(modifier = Modifier.fillMaxWidth()) {
        Text(
            "学科",
            style = MaterialTheme.typography.labelLarge,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
        Spacer(modifier = Modifier.height(8.dp))
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            HomeworkSubjects.forEach { subject ->
                val selected = subject.code == selectedSubject
                FilterChip(
                    selected = selected,
                    onClick = { onSubjectSelected(subject.code) },
                    label = { Text(subject.label) },
                    shape = RoundedCornerShape(8.dp),
                    modifier = Modifier.weight(1f),
                    colors = FilterChipDefaults.filterChipColors(
                        selectedContainerColor = MaterialTheme.colorScheme.primaryContainer,
                        selectedLabelColor = MaterialTheme.colorScheme.onPrimaryContainer
                    )
                )
            }
        }
    }
}

@Composable
private fun CaptureActionButton(
    title: String,
    subtitle: String,
    icon: ImageVector,
    onClick: () -> Unit,
    primary: Boolean = false
) {
    val modifier = Modifier.fillMaxWidth().height(68.dp)
    if (primary) {
        Button(onClick = onClick, modifier = modifier, shape = RoundedCornerShape(8.dp)) {
            CaptureActionContent(title = title, subtitle = subtitle, icon = icon)
        }
    } else {
        OutlinedButton(onClick = onClick, modifier = modifier, shape = RoundedCornerShape(8.dp)) {
            CaptureActionContent(title = title, subtitle = subtitle, icon = icon)
        }
    }
}

@Composable
private fun CaptureActionContent(
    title: String,
    subtitle: String,
    icon: ImageVector
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        Icon(icon, contentDescription = null)
        Column(horizontalAlignment = Alignment.Start) {
            Text(title, style = MaterialTheme.typography.titleSmall)
            Text(subtitle, style = MaterialTheme.typography.bodySmall)
        }
    }
}

@Composable
private fun CompactCaptureAction(
    title: String,
    subtitle: String,
    icon: ImageVector,
    onClick: () -> Unit,
    modifier: Modifier = Modifier
) {
    OutlinedButton(
        onClick = onClick,
        modifier = modifier.height(92.dp),
        shape = RoundedCornerShape(8.dp),
        contentPadding = PaddingValues(12.dp),
        border = BorderStroke(1.dp, Color(0xFFD8DEE8))
    ) {
        Column(
            modifier = Modifier.fillMaxWidth(),
            verticalArrangement = Arrangement.spacedBy(7.dp),
            horizontalAlignment = Alignment.Start
        ) {
            Box(
                modifier = Modifier
                    .size(30.dp)
                    .background(Color(0xFFEAF3FF), RoundedCornerShape(7.dp)),
                contentAlignment = Alignment.Center
            ) {
                Icon(icon, contentDescription = null, tint = Color(0xFF1565C0))
            }
            Text(
                title,
                style = MaterialTheme.typography.titleSmall,
                fontWeight = FontWeight.SemiBold,
                color = Color(0xFF172033)
            )
            Text(
                subtitle,
                style = MaterialTheme.typography.bodySmall,
                color = Color(0xFF667085),
                maxLines = 1
            )
        }
    }
}
