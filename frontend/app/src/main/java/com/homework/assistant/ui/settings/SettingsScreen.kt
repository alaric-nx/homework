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
import androidx.compose.material3.FilterChip
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
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.homework.assistant.data.local.SettingsStore
import com.homework.assistant.data.model.Student
import com.homework.assistant.data.remote.HomeworkApi
import kotlinx.coroutines.launch

@Composable
fun SettingsScreen(onLogout: () -> Unit, onStudentChanged: () -> Unit) {
    val context = LocalContext.current
    val settingsStore = remember { SettingsStore(context) }
    val api = remember { HomeworkApi() }
    val scope = rememberCoroutineScope()
    val snackbarHostState = remember { SnackbarHostState() }

    val students = remember { mutableStateListOf<Student>() }
    val models = remember { mutableStateListOf<String>() }
    var selectedModel by remember { mutableStateOf("") }
    var selectedStudentId by remember { mutableStateOf(settingsStore.getCurrentStudentId()) }
    var newStudentName by remember { mutableStateOf("") }
    var newStudentGrade by remember { mutableStateOf("") }
    var newModel by remember { mutableStateOf("") }
    var renameTarget by remember { mutableStateOf<String?>(null) }
    var editingStudent by remember { mutableStateOf<Student?>(null) }
    var deletingStudent by remember { mutableStateOf<Student?>(null) }

    fun toast(msg: String) {
        scope.launch { snackbarHostState.showSnackbar(msg) }
    }

    fun reloadModels() {
        models.clear()
        models.addAll(settingsStore.getModels())
        selectedModel = settingsStore.getSelectedModel()
    }

    fun reloadStudents() {
        val token = settingsStore.getAuthToken()
        if (token.isBlank()) return
        scope.launch {
            api.listStudents(token)
                .onSuccess { response ->
                    students.clear()
                    students.addAll(response.items)
                    val currentId = settingsStore.getCurrentStudentId()
                    selectedStudentId = currentId
                    if (students.isEmpty()) {
                        settingsStore.clearCurrentStudent()
                        selectedStudentId = ""
                        onStudentChanged()
                    } else if (currentId.isBlank() || students.none { it.id == currentId }) {
                        val first = students.first()
                        settingsStore.saveCurrentStudent(first.id, first.name, first.grade)
                        selectedStudentId = first.id
                        onStudentChanged()
                    }
                }
                .onFailure { toast(it.message ?: "孩子列表加载失败") }
        }
    }

    LaunchedEffect(Unit) {
        reloadModels()
        reloadStudents()
    }

    Scaffold(
        topBar = { TopAppBar(title = { Text("设置") }) },
        snackbarHost = { SnackbarHost(snackbarHostState) }
    ) { padding ->
        LazyColumn(
            modifier = Modifier.fillMaxSize().padding(padding),
            contentPadding = androidx.compose.foundation.layout.PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp)
        ) {
            item {
                AccountCard(
                    userName = settingsStore.getUserName(),
                    tenantName = settingsStore.getTenantName(),
                    onLogout = {
                        settingsStore.clearSession()
                        onLogout()
                    }
                )
            }
            item {
                StudentSection(
                    students = students,
                    selectedStudentId = selectedStudentId,
                    newStudentName = newStudentName,
                    newStudentGrade = newStudentGrade,
                    onNameChange = { newStudentName = it },
                    onGradeChange = { newStudentGrade = it },
                    onSelect = { student ->
                        settingsStore.saveCurrentStudent(student.id, student.name, student.grade)
                        selectedStudentId = student.id
                        onStudentChanged()
                        toast("已切换到 ${student.name}")
                    },
                    onEdit = { student -> editingStudent = student },
                    onDelete = { student -> deletingStudent = student },
                    onAdd = {
                        val name = newStudentName.trim()
                        if (name.isBlank()) {
                            toast("请输入孩子姓名")
                            return@StudentSection
                        }
                        scope.launch {
                            api.createStudent(settingsStore.getAuthToken(), name, newStudentGrade.trim())
                                .onSuccess {
                                    settingsStore.saveCurrentStudent(it.id, it.name, it.grade)
                                    selectedStudentId = it.id
                                    newStudentName = ""
                                    newStudentGrade = ""
                                    reloadStudents()
                                    onStudentChanged()
                                    toast("已添加孩子")
                                }
                                .onFailure { toast(it.message ?: "添加失败") }
                        }
                    }
                )
            }
            item {
                ModelSection(
                    models = models,
                    selected = selectedModel,
                    newModel = newModel,
                    onNewModelChange = { newModel = it },
                    onAdd = {
                        val name = newModel.trim()
                        when {
                            name.isEmpty() -> toast("请输入模型名称")
                            !settingsStore.addModel(name) -> toast("该模型名已存在")
                            else -> {
                                newModel = ""
                                reloadModels()
                                toast("已添加")
                            }
                        }
                    },
                    onSelect = {
                        settingsStore.selectModel(it)
                        reloadModels()
                    },
                    onEdit = { renameTarget = it },
                    onDelete = {
                        if (settingsStore.deleteModel(it)) {
                            reloadModels()
                            toast("已删除")
                        } else {
                            toast("至少保留一个模型")
                        }
                    }
                )
            }
        }
    }

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
                    if (settingsStore.renameModel(target, renameText.trim())) {
                        renameTarget = null
                        reloadModels()
                        toast("已保存")
                    } else {
                        toast("名称为空或重复")
                    }
                }) { Text("保存") }
            },
            dismissButton = {
                TextButton(onClick = { renameTarget = null }) { Text("取消") }
            }
        )
    }

    editingStudent?.let { student ->
        var editName by remember(student.id) { mutableStateOf(student.name) }
        var editGrade by remember(student.id) { mutableStateOf(student.grade.orEmpty()) }
        AlertDialog(
            onDismissRequest = { editingStudent = null },
            title = { Text("编辑孩子") },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    OutlinedTextField(
                        value = editName,
                        onValueChange = { editName = it },
                        label = { Text("孩子姓名") },
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth()
                    )
                    OutlinedTextField(
                        value = editGrade,
                        onValueChange = { editGrade = it },
                        label = { Text("年级") },
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth()
                    )
                }
            },
            confirmButton = {
                TextButton(onClick = {
                    val name = editName.trim()
                    if (name.isBlank()) {
                        toast("请输入孩子姓名")
                        return@TextButton
                    }
                    scope.launch {
                        api.updateStudent(settingsStore.getAuthToken(), student.id, name, editGrade.trim())
                            .onSuccess { updated ->
                                if (selectedStudentId == updated.id) {
                                    settingsStore.saveCurrentStudent(updated.id, updated.name, updated.grade)
                                    onStudentChanged()
                                }
                                editingStudent = null
                                reloadStudents()
                                toast("已保存")
                            }
                            .onFailure { toast(it.message ?: "保存失败") }
                    }
                }) { Text("保存") }
            },
            dismissButton = {
                TextButton(onClick = { editingStudent = null }) { Text("取消") }
            }
        )
    }

    deletingStudent?.let { student ->
        AlertDialog(
            onDismissRequest = { deletingStudent = null },
            title = { Text("删除孩子") },
            text = { Text("删除后，这个孩子不会再出现在设置页和题集筛选中。已有数据仍保留在服务器。") },
            confirmButton = {
                TextButton(onClick = {
                    scope.launch {
                        api.deleteStudent(settingsStore.getAuthToken(), student.id)
                            .onSuccess {
                                if (selectedStudentId == student.id) {
                                    settingsStore.clearCurrentStudent()
                                    selectedStudentId = ""
                                }
                                deletingStudent = null
                                reloadStudents()
                                toast("已删除")
                            }
                            .onFailure { toast(it.message ?: "删除失败") }
                    }
                }) { Text("删除") }
            },
            dismissButton = {
                TextButton(onClick = { deletingStudent = null }) { Text("取消") }
            }
        )
    }
}

@Composable
private fun AccountCard(userName: String, tenantName: String, onLogout: () -> Unit) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("账号信息", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
            Text(userName.ifBlank { "未命名账号" })
            Text(
                tenantName.ifBlank { "家庭" },
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
            TextButton(onClick = onLogout) { Text("退出登录") }
        }
    }
}

@Composable
private fun StudentSection(
    students: List<Student>,
    selectedStudentId: String,
    newStudentName: String,
    newStudentGrade: String,
    onNameChange: (String) -> Unit,
    onGradeChange: (String) -> Unit,
    onSelect: (Student) -> Unit,
    onEdit: (Student) -> Unit,
    onDelete: (Student) -> Unit,
    onAdd: () -> Unit
) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text("当前孩子", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
            if (students.isEmpty()) {
                Text("还没有孩子，请先添加。", color = MaterialTheme.colorScheme.onSurfaceVariant)
            } else {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxWidth()) {
                    students.forEach { student ->
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.spacedBy(8.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                        FilterChip(
                            selected = student.id == selectedStudentId,
                            onClick = { onSelect(student) },
                                label = {
                                    Text(
                                        listOfNotNull(student.name, student.grade?.takeIf { it.isNotBlank() })
                                            .joinToString(" · ")
                                    )
                                },
                                modifier = Modifier.weight(1f)
                        )
                            IconButton(onClick = { onEdit(student) }) {
                                Icon(Icons.Default.Edit, contentDescription = "编辑 ${student.name}")
                            }
                            IconButton(onClick = { onDelete(student) }) {
                                Icon(Icons.Default.Delete, contentDescription = "删除 ${student.name}")
                            }
                        }
                    }
                }
            }
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                OutlinedTextField(
                    value = newStudentName,
                    onValueChange = onNameChange,
                    label = { Text("孩子姓名") },
                    singleLine = true,
                    modifier = Modifier.weight(1f)
                )
                OutlinedTextField(
                    value = newStudentGrade,
                    onValueChange = onGradeChange,
                    label = { Text("年级") },
                    singleLine = true,
                    modifier = Modifier.weight(1f)
                )
            }
            Button(onClick = onAdd, modifier = Modifier.fillMaxWidth()) { Text("添加孩子") }
        }
    }
}

@Composable
private fun ModelSection(
    models: List<String>,
    selected: String,
    newModel: String,
    onNewModelChange: (String) -> Unit,
    onAdd: () -> Unit,
    onSelect: (String) -> Unit,
    onEdit: (String) -> Unit,
    onDelete: (String) -> Unit
) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text("模型设置", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                OutlinedTextField(
                    value = newModel,
                    onValueChange = onNewModelChange,
                    label = { Text("模型名称") },
                    singleLine = true,
                    modifier = Modifier.weight(1f)
                )
                Button(onClick = onAdd) { Text("添加") }
            }
            models.forEach { model ->
                ModelRow(
                    name = model,
                    selected = model == selected,
                    onSelect = { onSelect(model) },
                    onEdit = { onEdit(model) },
                    onDelete = { onDelete(model) }
                )
            }
        }
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
            Text(text = name, modifier = Modifier.weight(1f))
            IconButton(onClick = onEdit) {
                Icon(Icons.Default.Edit, contentDescription = "重命名 $name")
            }
            IconButton(onClick = onDelete) {
                Icon(Icons.Default.Delete, contentDescription = "删除 $name")
            }
        }
    }
}
