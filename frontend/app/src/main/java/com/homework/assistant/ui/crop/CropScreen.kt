package com.homework.assistant.ui.crop

import android.graphics.BitmapFactory
import android.net.Uri
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.awaitEachGesture
import androidx.compose.foundation.gestures.awaitFirstDown
import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Rect
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.PathOperation
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.layout.onSizeChanged
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.IntSize
import androidx.compose.ui.unit.dp
import coil.compose.AsyncImage
import com.homework.assistant.R
import com.homework.assistant.util.ImageUtils
import kotlin.math.abs
import kotlin.math.min

private const val HANDLE_RADIUS = 24f
private const val MIN_CROP_SIZE = 40f

private enum class DragTarget { NONE, MOVE, TOP_LEFT, TOP_RIGHT, BOTTOM_LEFT, BOTTOM_RIGHT, TOP, BOTTOM, LEFT, RIGHT }

/**
 * 裁剪页面
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CropScreen(
    sourceUri: Uri,
    onCropAdded: (Uri) -> Unit,
    onSkip: () -> Unit,
    onDone: () -> Unit,
    onBack: () -> Unit,
    singleMode: Boolean = false,
    onSingleCropDone: ((Uri) -> Unit)? = null
) {
    val context = LocalContext.current
    var cropCount by remember { mutableIntStateOf(0) }
    var containerSize by remember { mutableStateOf(IntSize.Zero) }

    // 源图片原始尺寸
    var srcWidth by remember { mutableIntStateOf(0) }
    var srcHeight by remember { mutableIntStateOf(0) }

    // 加载源图片尺寸
    LaunchedEffect(sourceUri) {
        try {
            val opts = BitmapFactory.Options().apply { inJustDecodeBounds = true }
            context.contentResolver.openInputStream(sourceUri)?.use {
                BitmapFactory.decodeStream(it, null, opts)
            }
            srcWidth = opts.outWidth
            srcHeight = opts.outHeight
        } catch (_: Exception) {}
    }

    // 计算 ContentScale.Fit 下图片在容器内的实际渲染区域
    fun imageRect(): Rect {
        if (containerSize.width == 0 || containerSize.height == 0 || srcWidth == 0 || srcHeight == 0) {
            return Rect(0f, 0f, containerSize.width.toFloat(), containerSize.height.toFloat())
        }
        val cw = containerSize.width.toFloat()
        val ch = containerSize.height.toFloat()
        val scale = min(cw / srcWidth, ch / srcHeight)
        val iw = srcWidth * scale
        val ih = srcHeight * scale
        val ox = (cw - iw) / 2f
        val oy = (ch - ih) / 2f
        return Rect(ox, oy, ox + iw, oy + ih)
    }

    // 裁剪框坐标（像素，相对于容器）
    var cropLeft by remember { mutableFloatStateOf(0f) }
    var cropTop by remember { mutableFloatStateOf(0f) }
    var cropRight by remember { mutableFloatStateOf(0f) }
    var cropBottom by remember { mutableFloatStateOf(0f) }
    var initialized by remember { mutableStateOf(false) }

    // 初始化裁剪框为图片实际区域（留小边距）
    LaunchedEffect(containerSize, srcWidth, srcHeight) {
        if (containerSize.width > 0 && containerSize.height > 0 && srcWidth > 0 && srcHeight > 0 && !initialized) {
            val ir = run {
                val cw = containerSize.width.toFloat()
                val ch = containerSize.height.toFloat()
                val scale = min(cw / srcWidth, ch / srcHeight)
                val iw = srcWidth * scale
                val ih = srcHeight * scale
                val ox = (cw - iw) / 2f
                val oy = (ch - ih) / 2f
                Rect(ox, oy, ox + iw, oy + ih)
            }
            val margin = 8f
            cropLeft = ir.left + margin
            cropTop = ir.top + margin
            cropRight = ir.right - margin
            cropBottom = ir.bottom - margin
            initialized = true
        }
    }

    var dragTarget by remember { mutableStateOf(DragTarget.NONE) }
    var dragStartOffset by remember { mutableStateOf(Offset.Zero) }
    var dragStartRect by remember { mutableStateOf(Rect.Zero) }

    fun hitTest(pos: Offset): DragTarget {
        val r = HANDLE_RADIUS * 2
        val rect = Rect(cropLeft, cropTop, cropRight, cropBottom)
        if (abs(pos.x - rect.left) < r && abs(pos.y - rect.top) < r) return DragTarget.TOP_LEFT
        if (abs(pos.x - rect.right) < r && abs(pos.y - rect.top) < r) return DragTarget.TOP_RIGHT
        if (abs(pos.x - rect.left) < r && abs(pos.y - rect.bottom) < r) return DragTarget.BOTTOM_LEFT
        if (abs(pos.x - rect.right) < r && abs(pos.y - rect.bottom) < r) return DragTarget.BOTTOM_RIGHT
        if (abs(pos.x - rect.left) < r && pos.y in rect.top..rect.bottom) return DragTarget.LEFT
        if (abs(pos.x - rect.right) < r && pos.y in rect.top..rect.bottom) return DragTarget.RIGHT
        if (abs(pos.y - rect.top) < r && pos.x in rect.left..rect.right) return DragTarget.TOP
        if (abs(pos.y - rect.bottom) < r && pos.x in rect.left..rect.right) return DragTarget.BOTTOM
        if (pos.x in rect.left..rect.right && pos.y in rect.top..rect.bottom) return DragTarget.MOVE
        return DragTarget.NONE
    }

    fun clamp(value: Float, min: Float, max: Float) = value.coerceIn(min, max)

    fun performCrop() {
        if (containerSize.width == 0 || containerSize.height == 0) return
        val ir = imageRect()
        if (ir.width < 1f || ir.height < 1f) return

        // 将裁剪框坐标映射到图片归一化坐标
        val leftRatio = ((cropLeft - ir.left) / ir.width).coerceIn(0f, 1f)
        val topRatio = ((cropTop - ir.top) / ir.height).coerceIn(0f, 1f)
        val rightRatio = ((cropRight - ir.left) / ir.width).coerceIn(0f, 1f)
        val bottomRatio = ((cropBottom - ir.top) / ir.height).coerceIn(0f, 1f)
        if (rightRatio - leftRatio < 0.01f || bottomRatio - topRatio < 0.01f) return

        val source = ImageUtils.loadBitmap(context, sourceUri) ?: return
        val cropped = ImageUtils.cropBitmap(source, leftRatio, topRatio, rightRatio, bottomRatio)
        val file = ImageUtils.saveToCacheFile(context, cropped, "crop_${System.currentTimeMillis()}_${cropCount}.jpg")
        cropCount++
        onCropAdded(Uri.fromFile(file))

        if (singleMode) {
            onSingleCropDone?.invoke(Uri.fromFile(file))
            return
        }

        // 重置裁剪框
        val margin = 8f
        cropLeft = ir.left + margin
        cropTop = ir.top + margin
        cropRight = ir.right - margin
        cropBottom = ir.bottom - margin
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(stringResource(R.string.crop)) },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = stringResource(R.string.back))
                    }
                }
            )
        },
        bottomBar = {
            Row(
                modifier = Modifier.fillMaxWidth().padding(16.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                if (singleMode) {
                    OutlinedButton(onClick = onBack, modifier = Modifier.weight(1f)) {
                        Text("取消")
                    }
                    Button(onClick = { performCrop() }, modifier = Modifier.weight(1f)) {
                        Text("确认裁剪")
                    }
                } else {
                    OutlinedButton(onClick = onSkip, modifier = Modifier.weight(1f)) {
                        Text("跳过裁剪")
                    }
                    OutlinedButton(onClick = { performCrop() }, modifier = Modifier.weight(1f)) {
                        Text(stringResource(R.string.add_more))
                    }
                    Button(
                        onClick = { performCrop(); onDone() },
                        modifier = Modifier.weight(1f)
                    ) {
                        Text(stringResource(R.string.done_cropping))
                    }
                }
            }
        }
    ) { padding ->
        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .background(Color.Black)
        ) {
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(24.dp),
                contentAlignment = Alignment.Center
            ) {
                AsyncImage(
                    model = sourceUri,
                    contentDescription = null,
                    contentScale = ContentScale.Fit,
                    modifier = Modifier
                        .fillMaxSize()
                        .onSizeChanged { containerSize = it }
                )

                if (initialized) {
                    Box(
                        modifier = Modifier
                            .fillMaxSize()
                            .pointerInput(Unit) {
                                awaitEachGesture {
                                    val down = awaitFirstDown(requireUnconsumed = false)
                                    down.consume()
                                    dragTarget = hitTest(down.position)
                                    dragStartOffset = down.position
                                    dragStartRect = Rect(cropLeft, cropTop, cropRight, cropBottom)

                                    while (true) {
                                        val event = awaitPointerEvent()
                                        val change = event.changes.firstOrNull() ?: break
                                        if (!change.pressed) {
                                            dragTarget = DragTarget.NONE
                                            break
                                        }
                                        change.consume()
                                        val pos = change.position
                                        val dx = pos.x - dragStartOffset.x
                                        val dy = pos.y - dragStartOffset.y
                                        val maxW = containerSize.width.toFloat()
                                        val maxH = containerSize.height.toFloat()
                                        val sr = dragStartRect

                                        when (dragTarget) {
                                            DragTarget.MOVE -> {
                                                val w = sr.width; val h = sr.height
                                                val newL = clamp(sr.left + dx, 0f, maxW - w)
                                                val newT = clamp(sr.top + dy, 0f, maxH - h)
                                                cropLeft = newL; cropTop = newT
                                                cropRight = newL + w; cropBottom = newT + h
                                            }
                                            DragTarget.TOP_LEFT -> {
                                                cropLeft = clamp(sr.left + dx, 0f, cropRight - MIN_CROP_SIZE)
                                                cropTop = clamp(sr.top + dy, 0f, cropBottom - MIN_CROP_SIZE)
                                            }
                                            DragTarget.TOP_RIGHT -> {
                                                cropRight = clamp(sr.right + dx, cropLeft + MIN_CROP_SIZE, maxW)
                                                cropTop = clamp(sr.top + dy, 0f, cropBottom - MIN_CROP_SIZE)
                                            }
                                            DragTarget.BOTTOM_LEFT -> {
                                                cropLeft = clamp(sr.left + dx, 0f, cropRight - MIN_CROP_SIZE)
                                                cropBottom = clamp(sr.bottom + dy, cropTop + MIN_CROP_SIZE, maxH)
                                            }
                                            DragTarget.BOTTOM_RIGHT -> {
                                                cropRight = clamp(sr.right + dx, cropLeft + MIN_CROP_SIZE, maxW)
                                                cropBottom = clamp(sr.bottom + dy, cropTop + MIN_CROP_SIZE, maxH)
                                            }
                                            DragTarget.LEFT -> cropLeft = clamp(sr.left + dx, 0f, cropRight - MIN_CROP_SIZE)
                                            DragTarget.RIGHT -> cropRight = clamp(sr.right + dx, cropLeft + MIN_CROP_SIZE, maxW)
                                            DragTarget.TOP -> cropTop = clamp(sr.top + dy, 0f, cropBottom - MIN_CROP_SIZE)
                                            DragTarget.BOTTOM -> cropBottom = clamp(sr.bottom + dy, cropTop + MIN_CROP_SIZE, maxH)
                                            DragTarget.NONE -> {}
                                        }
                                    }
                                }
                            }
                    ) {
                        Canvas(modifier = Modifier.fillMaxSize()) {
                            val cRect = Rect(cropLeft, cropTop, cropRight, cropBottom)
                            val outerPath = Path().apply { addRect(Rect(Offset.Zero, size)) }
                            val innerPath = Path().apply { addRect(cRect) }
                            val maskPath = Path().apply { op(outerPath, innerPath, PathOperation.Difference) }
                            drawPath(maskPath, Color.Black.copy(alpha = 0.45f))

                            drawRect(
                                color = Color.White,
                                topLeft = Offset(cRect.left, cRect.top),
                                size = Size(cRect.width, cRect.height),
                                style = Stroke(width = 2.dp.toPx())
                            )

                            val handleR = HANDLE_RADIUS
                            listOf(
                                Offset(cRect.left, cRect.top),
                                Offset(cRect.right, cRect.top),
                                Offset(cRect.left, cRect.bottom),
                                Offset(cRect.right, cRect.bottom)
                            ).forEach { c ->
                                drawCircle(Color.White, radius = handleR, center = c)
                                drawCircle(Color(0xFF4CAF50), radius = handleR - 4f, center = c)
                            }

                            val thirdW = cRect.width / 3f
                            val thirdH = cRect.height / 3f
                            for (i in 1..2) {
                                drawLine(Color.White.copy(alpha = 0.4f),
                                    Offset(cRect.left + thirdW * i, cRect.top),
                                    Offset(cRect.left + thirdW * i, cRect.bottom), strokeWidth = 1f)
                                drawLine(Color.White.copy(alpha = 0.4f),
                                    Offset(cRect.left, cRect.top + thirdH * i),
                                    Offset(cRect.right, cRect.top + thirdH * i), strokeWidth = 1f)
                            }
                        }
                    }
                }
            }

            if (cropCount > 0) {
                Surface(
                    color = MaterialTheme.colorScheme.primaryContainer,
                    shape = MaterialTheme.shapes.small,
                    modifier = Modifier.align(Alignment.TopEnd).padding(8.dp)
                ) {
                    Text(
                        text = "已裁剪 $cropCount 段",
                        modifier = Modifier.padding(horizontal = 12.dp, vertical = 6.dp),
                        style = MaterialTheme.typography.labelMedium
                    )
                }
            }
        }
    }
}
