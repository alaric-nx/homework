package com.homework.assistant.ui.capture

import android.Manifest
import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
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
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
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
        topBar = { TopAppBar(title = { Text(stringResource(R.string.app_name)) }) }
    ) { padding ->
        Column(
            modifier = Modifier.fillMaxSize().padding(padding).padding(32.dp),
            verticalArrangement = Arrangement.Center,
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            SubjectSelector(
                selectedSubject = normalizeSubject(selectedSubject),
                onSubjectSelected = onSubjectSelected
            )

            Spacer(modifier = Modifier.height(22.dp))

            CaptureActionButton(
                title = "拍照解析",
                subtitle = "单张题图",
                icon = Icons.Default.CameraAlt,
                onClick = { permissionLauncher.launch(Manifest.permission.CAMERA) },
                primary = true
            )

            Spacer(modifier = Modifier.height(14.dp))

            CaptureActionButton(
                title = "多图合并",
                subtitle = "多张拼成一道题",
                icon = Icons.Default.Collections,
                onClick = { mergeGalleryLauncher.launch("image/*") }
            )

            Spacer(modifier = Modifier.height(14.dp))

            CaptureActionButton(
                title = "批量解析",
                subtitle = "多张分别出结果",
                icon = Icons.Default.GridView,
                onClick = { batchGalleryLauncher.launch("image/*") }
            )
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
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    onClick: () -> Unit,
    primary: Boolean = false
) {
    val modifier = Modifier.fillMaxWidth().height(64.dp)
    if (primary) {
        Button(onClick = onClick, modifier = modifier, shape = MaterialTheme.shapes.medium) {
            CaptureActionContent(title = title, subtitle = subtitle, icon = icon)
        }
    } else {
        OutlinedButton(onClick = onClick, modifier = modifier, shape = MaterialTheme.shapes.medium) {
            CaptureActionContent(title = title, subtitle = subtitle, icon = icon)
        }
    }
}

@Composable
private fun CaptureActionContent(
    title: String,
    subtitle: String,
    icon: androidx.compose.ui.graphics.vector.ImageVector
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
