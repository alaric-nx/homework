package com.homework.assistant.util

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Canvas
import android.net.Uri
import java.io.File
import java.io.FileOutputStream
import kotlin.math.max

/**
 * 图片工具：裁剪区域提取、多图纵向合并
 */
object ImageUtils {

    /**
     * 从 Uri 加载 Bitmap
     */
    fun loadBitmap(context: Context, uri: Uri): Bitmap? {
        return try {
            context.contentResolver.openInputStream(uri)?.use { stream ->
                BitmapFactory.decodeStream(stream)
            }
        } catch (e: Exception) {
            null
        }
    }

    /**
     * 裁剪 Bitmap 指定区域（归一化坐标 0..1）
     */
    fun cropBitmap(
        source: Bitmap,
        leftRatio: Float,
        topRatio: Float,
        rightRatio: Float,
        bottomRatio: Float
    ): Bitmap {
        val x = (leftRatio * source.width).toInt().coerceIn(0, source.width)
        val y = (topRatio * source.height).toInt().coerceIn(0, source.height)
        val w = ((rightRatio - leftRatio) * source.width).toInt().coerceIn(1, source.width - x)
        val h = ((bottomRatio - topRatio) * source.height).toInt().coerceIn(1, source.height - y)
        return Bitmap.createBitmap(source, x, y, w, h)
    }

    /**
     * 将多张图片纵向拼接为一张完整题图
     * 宽度统一为最大宽度，各段等比缩放
     */
    fun mergeVertically(bitmaps: List<Bitmap>): Bitmap {
        if (bitmaps.size == 1) return bitmaps.first()

        val maxWidth = bitmaps.maxOf { it.width }
        val scaled = bitmaps.map { bmp ->
            if (bmp.width == maxWidth) bmp
            else {
                val ratio = maxWidth.toFloat() / bmp.width
                Bitmap.createScaledBitmap(bmp, maxWidth, (bmp.height * ratio).toInt(), true)
            }
        }

        val totalHeight = scaled.sumOf { it.height }
        val result = Bitmap.createBitmap(maxWidth, totalHeight, Bitmap.Config.ARGB_8888)
        val canvas = Canvas(result)

        var currentY = 0f
        for (bmp in scaled) {
            canvas.drawBitmap(bmp, 0f, currentY, null)
            currentY += bmp.height
        }
        return result
    }

    /**
     * 压缩图片：长边限制 maxLongSide，JPEG quality，自动修正 EXIF 旋转
     * 返回压缩后的 File
     */
    fun compressForUpload(
        context: Context,
        bitmap: Bitmap,
        maxLongSide: Int = 1920,
        quality: Int = 85,
        name: String = "upload_${System.currentTimeMillis()}.jpg"
    ): File {
        var bmp = bitmap
        // 缩放
        val longSide = max(bmp.width, bmp.height)
        if (longSide > maxLongSide) {
            val scale = maxLongSide.toFloat() / longSide
            bmp = Bitmap.createScaledBitmap(
                bmp,
                (bmp.width * scale).toInt(),
                (bmp.height * scale).toInt(),
                true
            )
        }
        return saveToCacheFile(context, bmp, name, quality)
    }

    /**
     * 保存 Bitmap 到缓存目录，返回 File
     */
    fun saveToCacheFile(
        context: Context,
        bitmap: Bitmap,
        name: String = "merged.jpg",
        quality: Int = 90
    ): File {
        val dir = File(context.cacheDir, "images").apply { mkdirs() }
        val file = File(dir, name)
        FileOutputStream(file).use { out ->
            bitmap.compress(Bitmap.CompressFormat.JPEG, quality, out)
        }
        return file
    }
}
