package com.homework.assistant

import android.graphics.Bitmap
import android.net.Uri
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CameraAlt
import androidx.compose.material.icons.filled.List
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import com.homework.assistant.data.local.TaskEntity
import com.homework.assistant.data.model.normalizeSubject
import com.homework.assistant.service.UploadWorker
import com.homework.assistant.ui.capture.CaptureScreen
import com.homework.assistant.ui.crop.CropScreen
import com.homework.assistant.ui.merge.MergeScreen
import com.homework.assistant.ui.merge.ResultHolder
import com.homework.assistant.ui.result.ResultScreen
import com.homework.assistant.ui.settings.SettingsScreen
import com.homework.assistant.ui.tasklist.TaskListScreen
import com.homework.assistant.util.ImageUtils
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.util.UUID

private data class BottomTab(val route: String, val label: String, val icon: androidx.compose.ui.graphics.vector.ImageVector)

private val TABS = listOf(
    BottomTab("capture", "拍题", Icons.Default.CameraAlt),
    BottomTab("taskList", "任务", Icons.Default.List),
    BottomTab("settings", "设置", Icons.Default.Settings)
)

@Composable
fun HomeworkApp() {
    val navController = rememberNavController()
    val context = LocalContext.current
    val app = context.applicationContext as HomeworkApplication
    val scope = rememberCoroutineScope()

    val selectedImageUri = remember { mutableStateListOf<Uri>() }
    val cropSegments = remember { mutableStateListOf<Uri>() }
    val originalUris = remember { mutableStateListOf<Uri>() }
    val cropTargetIndex = remember { mutableIntStateOf(-1) }
    var selectedSubject by remember { mutableStateOf("general") }

    suspend fun createTaskFromBitmap(bitmap: Bitmap, subject: String): String {
        val (imagePath, thumbPath) = withContext(Dispatchers.IO) {
            val now = System.currentTimeMillis()
            val imgFile = ImageUtils.compressForUpload(
                context = context,
                bitmap = bitmap,
                name = "upload_$now.jpg"
            )
            val thumbFile = ImageUtils.saveToCacheFile(
                context, bitmap, "thumb_$now.jpg", 60
            )
            imgFile.absolutePath to thumbFile.absolutePath
        }
        val taskId = UUID.randomUUID().toString()
        val task = TaskEntity(
            id = taskId,
            subject = normalizeSubject(subject),
            status = "PENDING",
            thumbnailPath = thumbPath,
            imagePath = imagePath
        )
        app.taskRepository.insert(task)
        UploadWorker.enqueue(context, taskId)
        return taskId
    }

    fun clearAll() {
        cropSegments.clear()
        originalUris.clear()
        selectedImageUri.clear()
        cropTargetIndex.intValue = -1
        ResultHolder.latestResult = null
    }

    /** 统一的 tab 切换：清栈到 capture，再跳目标 */
    fun navigateToTab(route: String) {
        navController.navigate(route) {
            popUpTo("capture") { inclusive = false }
            launchSingleTop = true
        }
    }

    fun submitBatchImages(uris: List<Uri>, subject: String) {
        if (uris.isEmpty()) return
        scope.launch {
            val bitmaps = withContext(Dispatchers.IO) {
                uris.mapNotNull { uri -> ImageUtils.loadBitmap(context, uri) }
            }
            bitmaps.forEach { bitmap ->
                createTaskFromBitmap(bitmap, subject)
            }
            clearAll()
            navigateToTab("taskList")
        }
    }

    val navBackStackEntry by navController.currentBackStackEntryAsState()
    val currentRoute = navBackStackEntry?.destination?.route
    val showBottomBar = currentRoute in listOf("capture", "taskList", "settings")

    Scaffold(
        bottomBar = {
            if (showBottomBar) {
                NavigationBar {
                    TABS.forEach { tab ->
                        NavigationBarItem(
                            selected = currentRoute == tab.route,
                            onClick = {
                                if (currentRoute != tab.route) {
                                    navigateToTab(tab.route)
                                }
                            },
                            icon = { Icon(tab.icon, contentDescription = tab.label) },
                            label = { Text(tab.label) }
                        )
                    }
                }
            }
        }
    ) { scaffoldPadding ->
        NavHost(
            navController = navController,
            startDestination = "capture",
            modifier = if (showBottomBar) Modifier.padding(bottom = scaffoldPadding.calculateBottomPadding())
                       else Modifier
        ) {
            composable("capture") {
                CaptureScreen(
                    selectedSubject = selectedSubject,
                    onSubjectSelected = { selectedSubject = normalizeSubject(it) },
                    onImageSelected = { uri ->
                        cropSegments.add(uri)
                        originalUris.add(uri)
                        if (navController.currentDestination?.route == "capture") {
                            navController.navigate("merge")
                        }
                    },
                    onMultipleImagesSelected = { uris ->
                        cropSegments.addAll(uris)
                        originalUris.addAll(uris)
                        if (navController.currentDestination?.route == "capture") {
                            navController.navigate("merge")
                        }
                    },
                    onBatchImagesSelected = { uris ->
                        submitBatchImages(uris, selectedSubject)
                    }
                )
            }

            composable("crop") {
                val imageUri = selectedImageUri.firstOrNull()
                if (imageUri != null) {
                    CropScreen(
                        sourceUri = imageUri,
                        onCropAdded = { croppedUri ->
                            cropSegments.add(croppedUri)
                            originalUris.add(imageUri)
                        },
                        onSkip = {
                            if (navController.currentDestination?.route == "crop") {
                                cropSegments.add(imageUri)
                                originalUris.add(imageUri)
                                navController.navigate("merge") {
                                    popUpTo("capture") { inclusive = false }
                                }
                            }
                        },
                        onDone = {
                            if (navController.currentDestination?.route == "crop") {
                                navController.navigate("merge") {
                                    popUpTo("capture") { inclusive = false }
                                }
                            }
                        },
                        onBack = { navController.popBackStack() }
                    )
                }
            }

            composable("cropItem") {
                val idx = cropTargetIndex.intValue
                val imageUri = if (idx in originalUris.indices) originalUris[idx] else null
                if (imageUri != null) {
                    CropScreen(
                        sourceUri = imageUri,
                        singleMode = true,
                        onCropAdded = {},
                        onSingleCropDone = { croppedUri ->
                            cropSegments[idx] = croppedUri
                            navController.popBackStack()
                        },
                        onSkip = { navController.popBackStack() },
                        onDone = { navController.popBackStack() },
                        onBack = { navController.popBackStack() }
                    )
                }
            }

            composable("merge") {
                MergeScreen(
                    segments = cropSegments,
                    originalUris = originalUris,
                    onAddMore = { navController.navigate("capture") },
                    onCropItem = { index ->
                        cropTargetIndex.intValue = index
                        navController.navigate("cropItem")
                    },
                    onSubmitTask = { bitmap ->
                        scope.launch {
                            createTaskFromBitmap(bitmap, selectedSubject)
                            clearAll()
                            navigateToTab("taskList")
                        }
                    },
                    onBack = { navController.popBackStack() }
                )
            }

            composable("taskList") {
                TaskListScreen(
                    onTaskClick = { taskId ->
                        navController.navigate("result/$taskId")
                    }
                )
            }

            composable("settings") {
                SettingsScreen()
            }

            composable("result/{taskId}") { backStackEntry ->
                val taskId = backStackEntry.arguments?.getString("taskId") ?: ""
                ResultScreen(
                    taskId = taskId,
                    onStartOver = {
                        clearAll()
                        navigateToTab("capture")
                    }
                )
            }
        }
    }
}
