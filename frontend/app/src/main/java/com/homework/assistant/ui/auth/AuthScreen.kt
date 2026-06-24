@file:OptIn(ExperimentalMaterial3Api::class)

package com.homework.assistant.ui.auth

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import com.homework.assistant.data.local.SettingsStore
import com.homework.assistant.data.remote.HomeworkApi
import kotlinx.coroutines.launch

private val AuthBackground = Color(0xFFF7F8FA)
private val AuthCardBorder = Color(0xFFE3E8EF)
private val AuthText = Color(0xFF172033)
private val AuthMuted = Color(0xFF667085)
private val AuthPrimary = Color(0xFF1565C0)

@Composable
fun AuthScreen(onAuthed: () -> Unit) {
    val scope = rememberCoroutineScope()
    val snackbarHostState = remember { SnackbarHostState() }
    var isRegister by remember { mutableStateOf(false) }
    var username by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    var loading by remember { mutableStateOf(false) }

    val context = androidx.compose.ui.platform.LocalContext.current
    val settingsStore = remember { SettingsStore(context) }
    val api = remember { HomeworkApi() }

    fun show(message: String) {
        scope.launch { snackbarHostState.showSnackbar(message) }
    }

    Scaffold(
        snackbarHost = { SnackbarHost(snackbarHostState) },
        containerColor = AuthBackground
    ) { padding ->
        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(horizontal = 22.dp, vertical = 28.dp),
            contentAlignment = Alignment.Center
        ) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .heightIn(max = 560.dp),
                verticalArrangement = Arrangement.spacedBy(18.dp)
            ) {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text(
                        text = "作业助手",
                        style = MaterialTheme.typography.headlineLarge,
                        fontWeight = FontWeight.Bold,
                        color = AuthText
                    )
                    Text(
                        text = if (isRegister) "创建账号后，按孩子管理错题与关注题。"
                        else "登录后继续查看题集、任务和孩子资料。",
                        style = MaterialTheme.typography.bodyLarge,
                        color = AuthMuted
                    )
                }

                Card(
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(8.dp),
                    colors = CardDefaults.cardColors(containerColor = Color.White),
                    border = BorderStroke(1.dp, AuthCardBorder),
                    elevation = CardDefaults.cardElevation(defaultElevation = 1.dp)
                ) {
                    Column(
                        modifier = Modifier.padding(18.dp),
                        verticalArrangement = Arrangement.spacedBy(14.dp)
                    ) {
                        Text(
                            text = if (isRegister) "注册账号" else "账号登录",
                            style = MaterialTheme.typography.titleLarge,
                            fontWeight = FontWeight.SemiBold,
                            color = AuthText
                        )
                        OutlinedTextField(
                            value = username,
                            onValueChange = { username = it },
                            label = { Text("用户名") },
                            singleLine = true,
                            shape = RoundedCornerShape(8.dp),
                            modifier = Modifier.fillMaxWidth()
                        )
                        OutlinedTextField(
                            value = password,
                            onValueChange = { password = it },
                            label = { Text("密码") },
                            singleLine = true,
                            visualTransformation = PasswordVisualTransformation(),
                            shape = RoundedCornerShape(8.dp),
                            modifier = Modifier.fillMaxWidth()
                        )
                        Button(
                            onClick = {
                                val account = username.trim()
                                val pass = password.trim()
                                if (account.isBlank() || pass.length < 6) {
                                    show("请输入用户名和至少 6 位密码")
                                    return@Button
                                }
                                loading = true
                                scope.launch {
                                    val result = if (isRegister) {
                                        api.register(username = account, password = pass)
                                    } else {
                                        api.login(account = account, password = pass)
                                    }
                                    loading = false
                                    result
                                        .onSuccess {
                                            settingsStore.saveSession(
                                                token = it.token,
                                                displayName = it.user.display_name,
                                                tenantName = it.tenant.name
                                            )
                                            onAuthed()
                                        }
                                        .onFailure { show(it.message ?: "请求失败") }
                                }
                            },
                            enabled = !loading,
                            shape = RoundedCornerShape(8.dp),
                            modifier = Modifier
                                .fillMaxWidth()
                                .height(48.dp)
                        ) {
                            Text(if (loading) "请稍候..." else if (isRegister) "创建账号" else "进入应用")
                        }
                        Row(horizontalArrangement = Arrangement.Center, modifier = Modifier.fillMaxWidth()) {
                            TextButton(onClick = { isRegister = !isRegister }) {
                                Text(
                                    text = if (isRegister) "已有账号，去登录" else "没有账号，注册",
                                    color = AuthPrimary
                                )
                            }
                        }
                    }
                }
                Spacer(modifier = Modifier.height(1.dp))
            }
        }
    }
}
