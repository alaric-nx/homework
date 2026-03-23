package com.homework.assistant

import android.net.Uri
import androidx.compose.runtime.Composable
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.remember
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import com.homework.assistant.ui.capture.CaptureScreen
import com.homework.assistant.ui.crop.CropScreen
import com.homework.assistant.ui.merge.MergeScreen
import com.homework.assistant.ui.merge.ResultHolder
import com.homework.assistant.ui.result.ResultScreen

/**
 * 应用导航：
 * - 选图/拍照 -> 合并页（可裁剪）
 * - 合并页可继续添加、可对单张裁剪
 */
@Composable
fun HomeworkApp() {
    val navController = rememberNavController()
    val selectedImageUri = remember { mutableStateListOf<Uri>() }
    val cropSegments = remember { mutableStateListOf<Uri>() }
    val originalUris = remember { mutableStateListOf<Uri>() }
    val cropTargetIndex = remember { mutableIntStateOf(-1) }

    fun clearAll() {
        cropSegments.clear()
        originalUris.clear()
        selectedImageUri.clear()
        cropTargetIndex.intValue = -1
        ResultHolder.latestResult = null
        ResultHolder.filledImageBase64 = null
    }

    NavHost(navController = navController, startDestination = "capture") {

        composable("capture") {
            CaptureScreen(
                onImageSelected = { uri ->
                    // 单图也直接进合并页，需要裁剪可在合并页操作
                    cropSegments.add(uri)
                    originalUris.add(uri)
                    if (navController.currentDestination?.route == "capture") {
                        navController.navigate("merge") {
                            popUpTo("capture") { inclusive = false }
                        }
                    }
                },
                onMultipleImagesSelected = { uris ->
                    cropSegments.addAll(uris)
                    originalUris.addAll(uris)
                    if (navController.currentDestination?.route == "capture") {
                        navController.navigate("merge") {
                            popUpTo("capture") { inclusive = false }
                        }
                    }
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
                        // 只在还没导航走的时候执行
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

        // 从合并页对单张图片裁剪（单图模式）— 始终使用原图
        composable("cropItem") {
            val idx = cropTargetIndex.intValue
            val imageUri = if (idx in originalUris.indices) originalUris[idx] else null
            if (imageUri != null) {
                CropScreen(
                    sourceUri = imageUri,
                    singleMode = true,
                    onCropAdded = { /* handled by onSingleCropDone */ },
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
                onAddMore = {
                    navController.navigate("capture")
                },
                onCropItem = { index ->
                    cropTargetIndex.intValue = index
                    navController.navigate("cropItem")
                },
                onUploadComplete = {
                    navController.navigate("result") {
                        popUpTo("capture") { inclusive = false }
                    }
                },
                onBack = { navController.popBackStack() }
            )
        }

        composable("result") {
            ResultScreen(
                onStartOver = {
                    clearAll()
                    navController.navigate("capture") {
                        popUpTo("capture") { inclusive = true }
                    }
                }
            )
        }
    }
}
