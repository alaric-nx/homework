@file:OptIn(ExperimentalMaterial3Api::class)

package com.homework.assistant.ui.settings

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.selection.selectable
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import com.homework.assistant.data.local.SettingsStore
import kotlinx.coroutines.launch

/**
 * 设置页面：管理解析所用的模型名称列表。
 *
 * 支持新增、重命名、删除模型名，并通过单选保证始终有一个选中的模型。
 * 选中的模型会在解析作业时透传给后端。
 */
@Composable
fun SettingsScreen() {
    val context = LocalContext.current
    val settingsStore = remember { SettingsStore(context) }
    val scope = rememberCoroutineScope()
    val snackbarHostState = remember { SnackbarHostState() }

    val models = remember { mutableStateListOf<String>() }
    var selected by remember { mutableStateOf("") }

    fun reload() {
        models.clear()
        models.addAll(settingsStore.getModels())
        selected = settingsStore.getSelectedModel()
    }

    // 首次组合时加载持久化数据。
    androidx.compose.runtime.LaunchedEffect(Unit) {
        reload()
    }

    var newModel by remember { mutableStateOf("") }
    // 非空时表示正在重命名该模型（弹出重命名对话框）。
    var renameTarget by remember { mutableStateOf<String?>(null) }

    fun toast(msg: String) {
        scope.launch { snackbarHostState.showSnackbar(msg) }
    }

    Scaffold(
        topBar = { TopAppBar(title = { Text("设置") }) },
        snackbarHost = { SnackbarHost(snackbarHostState) }
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            Text(
                text = "模型设置",
                style = MaterialTheme.typography.titleMedium
            )
            Text(
                text = "管理可用的模型名称，选中的模型会在解析作业时使用。",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )

            // 新增模型
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                OutlinedTextField(
                    value = newModel,
                    onValueChange = { newModel = it },
                    label = { Text("模型名称") },
                    singleLine = true,
                    modifier = Modifier.weight(1f)
                )
                Button(
                    onClick = {
                        val name = newModel.trim()
                        when {
                            name.isEmpty() -> toast("请输入模型名称")
                            !settingsStore.addModel(name) -> toast("该模型名已存在")
                            else -> {
                                newModel = ""
                                reload()
                                toast("已添加")
                            }
                        }
                    }
                ) {
                    Text("添加")
                }
            }

            if (models.isEmpty()) {
                Text(
                    text = "尚未添加模型，请先添加一个并选中。",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            } else {
                LazyColumn(
                    modifier = Modifier.fillMaxWidth(),
                    verticalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    items(models, key = { it }) { model ->
                        ModelRow(
                            name = model,
                            selected = model == selected,
                            onSelect = {
                                settingsStore.selectModel(model)
                                reload()
                            },
                            onEdit = { renameTarget = model },
                            onDelete = {
                                if (settingsStore.deleteModel(model)) {
                                    reload()
                                    toast("已删除")
                                } else {
                                    toast("至少保留一个模型")
                                }
                            }
                        )
                    }
                }
            }
        }
    }

    // 重命名对话框
    val target = renameTarget
    if (target != null) {
        var renameText by remember(target) { mutableStateOf(target) }
        AlertDialog(
            onDismissRequest = { renameTarget = null },
            title = { Text("重命名模型") },
            text = {
                OutlinedTextField(
                    value = renameText,
                    onValueChange = { renameText = it },
                    label = { Text("模型名称") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth()
                )
            },
            confirmButton = {
                TextButton(onClick = {
                    val newName = renameText.trim()
                    when {
                        newName.isEmpty() -> toast("请输入模型名称")
                        !settingsStore.renameModel(target, newName) -> toast("名称为空或与已有模型重复")
                        else -> {
                            renameTarget = null
                            reload()
                            toast("已保存")
                        }
                    }
                }) {
                    Text("保存")
                }
            },
            dismissButton = {
                TextButton(onClick = { renameTarget = null }) {
                    Text("取消")
                }
            }
        )
    }
}

@Composable
private fun ModelRow(
    name: String,
    selected: Boolean,
    onSelect: () -> Unit,
    onEdit: () -> Unit,
    onDelete: () -> Unit
) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .selectable(selected = selected, onClick = onSelect)
                .padding(horizontal = 8.dp, vertical = 4.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            RadioButton(selected = selected, onClick = onSelect)
            Text(
                text = name,
                style = MaterialTheme.typography.bodyLarge,
                modifier = Modifier.weight(1f)
            )
            IconButton(onClick = onEdit) {
                Icon(Icons.Default.Edit, contentDescription = "重命名 $name")
            }
            IconButton(onClick = onDelete) {
                Icon(Icons.Default.Delete, contentDescription = "删除 $name")
            }
        }
    }
}
