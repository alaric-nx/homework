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
import com.homework.assistant.ui.result.ResultScreen

/**
 * 应用导航：
 * - 单图拍照/选图 -> 裁剪(可跳过) -> 合并页
 * - 多图选图 -> 合并页（每张可单独裁剪）
 * - 合并页可继续添加、可对单张裁剪
 */
@Composable
fun HomeworkApp() {
    val navController = rememberNavController()
    val selectedImageUri = remember { mutableStateListOf<Uri>() }
    val cropSegments = remember { mutableStateListOf<Uri>() }
    // 保存原始图片URI，重新裁剪时始终使用原图
    val originalUris = remember { mutableStateListOf<Uri>() }
    // 记录从合并页裁剪哪张图片的索引
    val cropTargetIndex = remember { mutableIntStateOf(-1) }

    NavHost(navController = navController, startDestination = "capture") {

        composable("capture") {
            CaptureScreen(
                onImageSelected = { uri ->
                    selectedImageUri.clear()
                    selectedImageUri.add(uri)
                    navController.navigate("crop")
                },
                onMultipleImagesSelected = { uris ->
                    cropSegments.addAll(uris)
                    originalUris.addAll(uris)
                    navController.navigate("merge") {
                        popUpTo("capture") { inclusive = false }
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
                        cropSegments.add(imageUri)
                        originalUris.add(imageUri)
                        navController.navigate("merge") {
                            popUpTo("capture") { inclusive = false }
                        }
                    },
                    onDone = {
                        navController.navigate("merge") {
                            popUpTo("capture") { inclusive = false }
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
                    cropSegments.clear()
                    originalUris.clear()
                    selectedImageUri.clear()
                    cropTargetIndex.intValue = -1
                    navController.navigate("capture") {
                        popUpTo("capture") { inclusive = true }
                    }
                }
            )
        }
    }
}
