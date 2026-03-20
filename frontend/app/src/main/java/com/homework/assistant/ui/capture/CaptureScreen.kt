package com.homework.assistant.ui.capture

import android.Manifest
import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
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
import java.io.File

/**
 * 拍照 / 从相册选择页面
 * 支持相册多选图片
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CaptureScreen(
    onImageSelected: (Uri) -> Unit,
    onMultipleImagesSelected: (List<Uri>) -> Unit
) {
    val context = LocalContext.current
    val ttsManager = (context.applicationContext as HomeworkApplication).ttsManager
    var cameraUri by remember { mutableStateOf<Uri?>(null) }

    LaunchedEffect(Unit) {
        ttsManager.ensureInit(context)
    }

    // 相册多选
    val galleryMultiLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.GetMultipleContents()
    ) { uris: List<Uri> ->
        if (uris.isEmpty()) return@rememberLauncherForActivityResult
        if (uris.size == 1) {
            onImageSelected(uris.first())
        } else {
            onMultipleImagesSelected(uris)
        }
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
            Button(
                onClick = { permissionLauncher.launch(Manifest.permission.CAMERA) },
                modifier = Modifier.fillMaxWidth().height(56.dp)
            ) {
                Text(stringResource(R.string.take_photo))
            }

            Spacer(modifier = Modifier.height(24.dp))

            OutlinedButton(
                onClick = { galleryMultiLauncher.launch("image/*") },
                modifier = Modifier.fillMaxWidth().height(56.dp)
            ) {
                Text("从相册选择（可多选）")
            }
        }
    }
}
