package com.tanue.parus

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.animation.animateContentSize
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Clear
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.tanue.parus.ui.theme.ParusTheme
import com.tanue.parus.ui.theme.AppleBlue
import com.tanue.parus.ui.theme.AppleGray
import com.tanue.parus.data.model.WordWithDetails
import com.tanue.parus.presentation.search.SearchViewModel
import org.koin.androidx.compose.koinViewModel

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            ParusTheme {
                Scaffold(
                    modifier = Modifier.fillMaxSize(),
                    containerColor = MaterialTheme.colorScheme.background
                ) { innerPadding ->
                    // 通过 Koin 依赖注入框架获取 VM
                    val viewModel: SearchViewModel = koinViewModel()
                    SpotlightSearchScreen(
                        viewModel = viewModel,
                        modifier = Modifier
                            .fillMaxSize()
                            .padding(innerPadding)
                    )
                }
            }
        }
    }
}

@Composable
fun SpotlightSearchScreen(
    viewModel: SearchViewModel,
    modifier: Modifier = Modifier
) {
    val searchQuery by viewModel.searchQuery.collectAsState()
    val searchResults by viewModel.searchResults.collectAsState()
    val isLoading by viewModel.isLoading.collectAsState()
    var selectedWordId by remember { mutableStateOf<Int?>(null) }

    Column(
        modifier = modifier
            .fillMaxSize()
            .padding(horizontal = 16.dp, vertical = 8.dp),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Spacer(modifier = Modifier.height(12.dp))
        
        // 苹果 Spotlight 风格的搜索框
        OutlinedTextField(
            value = searchQuery,
            onValueChange = { 
                viewModel.onQueryChanged(it)
                selectedWordId = null // 重新输入时收起当前选中
            },
            placeholder = { 
                Text(
                    text = "搜索俄语单词、变格或中文释义...", 
                    color = AppleGray,
                    fontSize = 15.sp
                ) 
            },
            leadingIcon = { 
                Icon(
                    imageVector = Icons.Default.Search, 
                    contentDescription = "Search",
                    tint = AppleGray
                ) 
            },
            trailingIcon = {
                if (searchQuery.isNotEmpty()) {
                    IconButton(onClick = { viewModel.onQueryChanged("") }) {
                        Icon(
                            imageVector = Icons.Default.Clear,
                            contentDescription = "Clear",
                            tint = AppleGray
                        )
                    }
                }
            },
            singleLine = true,
            colors = OutlinedTextFieldDefaults.colors(
                focusedContainerColor = MaterialTheme.colorScheme.surface,
                unfocusedContainerColor = MaterialTheme.colorScheme.surface.copy(alpha = 0.8f),
                focusedBorderColor = AppleBlue.copy(alpha = 0.8f),
                unfocusedBorderColor = Color.Gray.copy(alpha = 0.2f),
                cursorColor = AppleBlue
            ),
            shape = RoundedCornerShape(24.dp),
            modifier = Modifier
                .fillMaxWidth()
                .height(52.dp)
        )

        Spacer(modifier = Modifier.height(16.dp))

        // 结果渲染区域
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .weight(1f)
        ) {
            if (isLoading) {
                // 正在加载状态
                CircularProgressIndicator(
                    color = AppleBlue,
                    modifier = Modifier.align(Alignment.Center)
                )
            } else if (searchQuery.isBlank()) {
                // 空白欢迎状态
                WelcomeView()
            } else if (searchResults.isEmpty()) {
                // 未找到状态
                NoResultsView(searchQuery)
            } else {
                // 搜索结果列表
                LazyColumn(
                    verticalArrangement = Arrangement.spacedBy(10.dp),
                    modifier = Modifier.fillMaxSize()
                ) {
                    items(searchResults, key = { it.word.id }) { wordWithDetails ->
                        WordItemRow(
                            wordWithDetails = wordWithDetails,
                            isExpanded = selectedWordId == wordWithDetails.word.id,
                            onClick = {
                                selectedWordId = if (selectedWordId == wordWithDetails.word.id) null else wordWithDetails.word.id
                            }
                        )
                    }
                }
            }
        }
    }
}

@Composable
fun WelcomeView() {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(top = 80.dp),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Text(
            text = "Парус",
            fontSize = 36.sp,
            fontWeight = FontWeight.Bold,
            color = MaterialTheme.colorScheme.onBackground
        )
        Spacer(modifier = Modifier.height(8.dp))
        Text(
            text = "极致纯净的俄汉学习词典",
            fontSize = 14.sp,
            color = AppleGray
        )
        Spacer(modifier = Modifier.height(24.dp))
        Text(
            text = "输入上方搜索框开始查词\n例如：вода, молоко 或 \"水\"",
            fontSize = 13.sp,
            color = AppleGray.copy(alpha = 0.8f),
            modifier = Modifier.align(Alignment.CenterHorizontally),
            lineHeight = 20.sp
        )
    }
}

@Composable
fun NoResultsView(query: String) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(top = 100.dp),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Text(
            text = "未找到 \"$query\"",
            fontSize = 16.sp,
            fontWeight = FontWeight.Medium,
            color = MaterialTheme.colorScheme.onBackground
        )
        Spacer(modifier = Modifier.height(8.dp))
        Text(
            text = "请检查拼写或输入更简短的词条",
            fontSize = 13.sp,
            color = AppleGray
        )
    }
}

@Composable
fun WordItemRow(
    wordWithDetails: WordWithDetails,
    isExpanded: Boolean,
    onClick: () -> Unit
) {
    val word = wordWithDetails.word
    val definitions = wordWithDetails.definitions
    val inflections = wordWithDetails.inflections

    Card(
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surface
        ),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp),
        modifier = Modifier
            .fillMaxWidth()
            .clickable { onClick() }
            .animateContentSize() // 展开折叠的微动画
    ) {
        Column(
            modifier = Modifier.padding(16.dp)
        ) {
            // 第一行：单词原形与词性
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween,
                modifier = Modifier.fillMaxWidth()
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        text = word.lemmaStressed,
                        fontSize = 20.sp,
                        fontWeight = FontWeight.Bold,
                        color = MaterialTheme.colorScheme.onSurface
                    )
                    word.pos?.let { pos ->
                        Spacer(modifier = Modifier.width(8.dp))
                        Text(
                            text = pos,
                            fontSize = 11.sp,
                            color = AppleBlue,
                            fontWeight = FontWeight.Bold,
                            modifier = Modifier
                                .background(AppleBlue.copy(alpha = 0.1f), RoundedCornerShape(4.dp))
                                .padding(horizontal = 6.dp, vertical = 2.dp)
                        )
                    }
                }
                
                // 显示第一个释义来源
                val mainSource = definitions.firstOrNull()?.source ?: "Wiktionary"
                Text(
                    text = mainSource,
                    fontSize = 11.sp,
                    color = AppleGray
                )
            }

            Spacer(modifier = Modifier.height(6.dp))

            // 释义 (合并显示所有释义，即使未展开也显示第一行)
            val briefText = definitions.joinToString("；") { it.definition }
            Text(
                text = if (briefText.isNotEmpty()) briefText else "暂无释义",
                fontSize = 14.sp,
                color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.8f)
            )

            // 展开部分：详细语法变格变位表与例句
            if (isExpanded) {
                HorizontalDivider(
                    color = Color.Gray.copy(alpha = 0.1f),
                    modifier = Modifier.padding(vertical = 12.dp)
                )

                // 变格变位区域
                if (inflections.isNotEmpty()) {
                    Text(
                        text = "词形变化",
                        fontSize = 12.sp,
                        fontWeight = FontWeight.Bold,
                        color = AppleGray
                    )
                    Spacer(modifier = Modifier.height(6.dp))
                    
                    // 用横向流式布局或简单列表行展示词形变化标签
                    Row(
                        horizontalArrangement = Arrangement.spacedBy(6.dp),
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        // 仅限制展示前几个主要变格以防溢出
                        inflections.take(6).forEach { inflection ->
                            Box(
                                modifier = Modifier
                                    .background(Color.Gray.copy(alpha = 0.08f), RoundedCornerShape(6.dp))
                                    .padding(horizontal = 8.dp, vertical = 4.dp)
                            ) {
                                Text(
                                    text = inflection.form,
                                    fontSize = 12.sp,
                                    color = MaterialTheme.colorScheme.onSurface
                                )
                            }
                        }
                    }
                    Spacer(modifier = Modifier.height(14.dp))
                }

                // 词库分层释义展示 (在展开时展示每个数据源的单独释义)
                if (definitions.isNotEmpty()) {
                    Text(
                        text = "详细释义来源",
                        fontSize = 12.sp,
                        fontWeight = FontWeight.Bold,
                        color = AppleGray
                    )
                    Spacer(modifier = Modifier.height(6.dp))
                    definitions.forEach { df ->
                        Row(
                            verticalAlignment = Alignment.CenterVertically,
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(vertical = 2.dp)
                        ) {
                            Text(
                                text = "[${df.source}]",
                                fontSize = 12.sp,
                                color = AppleBlue,
                                fontWeight = FontWeight.Bold,
                                modifier = Modifier.width(70.dp)
                            )
                            Text(
                                text = df.definition,
                                fontSize = 13.sp,
                                color = MaterialTheme.colorScheme.onSurface
                            )
                        }
                    }
                }
            }
        }
    }
}