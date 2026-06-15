@file:OptIn(ExperimentalMaterial3Api::class)

package com.homework.assistant.ui.settings

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.homework.assistant.data.local.SettingsStore
import kotlinx.coroutines.launch

/**
 * 设置页面：配置并持久化解析所用的模型名称。
 *
 * 文本输入框用于输入模型名称，点击保存按钮写入 [SettingsStore]。
 * 进入页面时从 [SettingsStore] 读取已保存的值作为初始内容。
 */
@Composable
fun SettingsScreen() {
    val context = LocalContext.current
    val settingsStore = remember { SettingsStore(context) }
    val scope = rememberCoroutineScope()
    val snackbarHostState = remember { SnackbarHostState() }

    var modelName by remember { mutableStateOf(settingsStore.modelName) }

    Scaffold(
        topBar = { TopAppBar(title = { Text("设置") }) },
        snackbarHost = { SnackbarHost(snackbarHostState) }
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            Text(
                text = "模型设置",
                style = MaterialTheme.typography.titleMedium
            )

            OutlinedTextField(
                value = modelName,
                onValueChange = { modelName = it },
                label = { Text("模型名称") },
                placeholder = { Text("留空则使用后端默认模型") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth()
            )

            Text(
                text = "解析作业时会使用此模型名称。留空表示使用后端默认配置的模型。",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                overflow = TextOverflow.Clip
            )

            Spacer(modifier = Modifier.height(8.dp))

            Button(
                onClick = {
                    settingsStore.modelName = modelName.trim()
                    modelName = settingsStore.modelName
                    scope.launch { snackbarHostState.showSnackbar("已保存") }
                },
                modifier = Modifier
                    .fillMaxWidth()
                    .height(52.dp)
            ) {
                Text("保存")
            }
        }
    }
}
