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
import androidx.compose.foundation.border
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Clear
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.activity.compose.BackHandler
import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInHorizontally
import androidx.compose.animation.slideOutHorizontally
import androidx.compose.animation.togetherWith
import com.tanue.parus.ui.theme.ParusTheme
import com.tanue.parus.ui.theme.AppleBlue
import com.tanue.parus.ui.theme.AppleGray
import com.tanue.parus.data.model.WordWithDetails
import com.tanue.parus.data.model.InflectionEntity
import com.tanue.parus.data.model.ExampleEntity
import com.tanue.parus.presentation.search.SearchViewModel
import org.koin.androidx.compose.koinViewModel
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.SpanStyle

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
    var selectedWord by remember { mutableStateOf<WordWithDetails?>(null) }

    AnimatedContent(
        targetState = selectedWord,
        transitionSpec = {
            if (targetState != null) {
                // 进入二级页面：从右侧滑入，主页向左侧滑出
                (slideInHorizontally { width -> width } + fadeIn())
                    .togetherWith(slideOutHorizontally { width -> -width } + fadeOut())
            } else {
                // 返回主页：主页从左侧滑入，二级页面向右侧滑出
                (slideInHorizontally { width -> -width } + fadeIn())
                    .togetherWith(slideOutHorizontally { width -> width } + fadeOut())
            }
        },
        label = "page_transition",
        modifier = modifier.fillMaxSize()
    ) { word ->
        if (word != null) {
            BackHandler {
                selectedWord = null
            }
            WordDetailScreen(
                wordWithDetails = word,
                onBackClick = { selectedWord = null },
                modifier = Modifier.fillMaxSize()
            )
        } else {
            Column(
                modifier = Modifier
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
                                    onClick = {
                                        selectedWord = wordWithDetails
                                    }
                                )
                            }
                        }
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
    onClick: () -> Unit
) {
    val word = wordWithDetails.word
    val definitions = wordWithDetails.definitions

    Card(
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surface
        ),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp),
        modifier = Modifier
            .fillMaxWidth()
            .clickable { onClick() }
    ) {
        Column(
            modifier = Modifier.padding(14.dp)
        ) {
            // 第一行：单词原形与词性
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween,
                modifier = Modifier.fillMaxWidth()
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        text = buildStressedAnnotatedString(word.lemmaStressed),
                        fontSize = 18.sp,
                        fontWeight = FontWeight.Bold,
                        color = MaterialTheme.colorScheme.onSurface
                    )
                    word.pos?.let { pos ->
                        Spacer(modifier = Modifier.width(8.dp))
                        Text(
                            text = pos,
                            fontSize = 10.sp,
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

            // 释义预览
            val briefText = definitions.joinToString("；") { it.definition }
            Text(
                text = if (briefText.isNotEmpty()) briefText else "暂无释义",
                fontSize = 14.sp,
                maxLines = 2,
                color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.7f)
            )
        }
    }
}

@Composable
fun WordDetailScreen(
    wordWithDetails: WordWithDetails,
    onBackClick: () -> Unit,
    modifier: Modifier = Modifier
) {
    val word = wordWithDetails.word
    val definitions = wordWithDetails.definitions
    val inflections = wordWithDetails.inflections
    val examples = wordWithDetails.examples
    val scrollState = rememberScrollState()

    Box(
        modifier = modifier
            .fillMaxSize()
            .background(MaterialTheme.colorScheme.background)
    ) {
        // 1. 可滚动的主体内容
        Column(
            modifier = Modifier
                .fillMaxSize()
                .verticalScroll(scrollState)
                .padding(horizontal = 16.dp)
        ) {
            // 留出顶部固定返回栏的高度 (56.dp + 状态栏边距)
            Spacer(modifier = Modifier.height(100.dp))

            // 单词头部及词性
            Row(
                verticalAlignment = Alignment.CenterVertically,
                modifier = Modifier.fillMaxWidth()
            ) {
                Text(
                    text = buildStressedAnnotatedString(word.lemmaStressed),
                    fontSize = 28.sp,
                    fontWeight = FontWeight.Bold,
                    color = MaterialTheme.colorScheme.onBackground
                )
                word.pos?.let { pos ->
                    Spacer(modifier = Modifier.width(12.dp))
                    Text(
                        text = pos,
                        fontSize = 12.sp,
                        color = AppleBlue,
                        fontWeight = FontWeight.Bold,
                        modifier = Modifier
                            .background(AppleBlue.copy(alpha = 0.1f), RoundedCornerShape(4.dp))
                            .padding(horizontal = 8.dp, vertical = 4.dp)
                    )
                }
            }

            Spacer(modifier = Modifier.height(20.dp))

            // 详细解释卡片
            Text(
                text = "解释释义",
                fontSize = 13.sp,
                fontWeight = FontWeight.Bold,
                color = AppleGray,
                modifier = Modifier.padding(bottom = 8.dp)
            )
            
            Card(
                shape = RoundedCornerShape(16.dp),
                colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
                elevation = CardDefaults.cardElevation(defaultElevation = 1.dp),
                modifier = Modifier.fillMaxWidth()
            ) {
                Column(modifier = Modifier.padding(16.dp)) {
                    if (definitions.isEmpty()) {
                        Text(
                            text = "暂无释义",
                            fontSize = 14.sp,
                            color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f)
                        )
                    } else {
                        definitions.forEachIndexed { index, df ->
                            if (index > 0) {
                                HorizontalDivider(
                                    color = Color.Gray.copy(alpha = 0.1f),
                                    modifier = Modifier.padding(vertical = 12.dp)
                                )
                            }
                            Column {
                                Row(verticalAlignment = Alignment.CenterVertically) {
                                    Text(
                                        text = df.source,
                                        fontSize = 11.sp,
                                        color = AppleBlue,
                                        fontWeight = FontWeight.Bold,
                                        modifier = Modifier
                                            .background(AppleBlue.copy(alpha = 0.1f), RoundedCornerShape(4.dp))
                                            .padding(horizontal = 6.dp, vertical = 2.dp)
                                    )
                                }
                                Spacer(modifier = Modifier.height(6.dp))
                                // 解析释义文本，• 开头的行作为例句
                                val defLines = df.definition.split("\n")
                                defLines.forEach { defLine ->
                                    val trimmed = defLine.trim()
                                    if (trimmed.startsWith("•") || trimmed.startsWith("→")) {
                                        // 例句行 — 灰色小字
                                        val exampleText = trimmed.removePrefix("•").removePrefix("→").trim()
                                        if (exampleText.isNotEmpty()) {
                                            Spacer(modifier = Modifier.height(4.dp))
                                            Text(
                                                text = exampleText,
                                                fontSize = 13.sp,
                                                color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.5f),
                                                lineHeight = 18.sp
                                            )
                                        }
                                    } else {
                                        if (trimmed.isNotEmpty()) {
                                            Text(
                                                text = trimmed,
                                                fontSize = 15.sp,
                                                color = MaterialTheme.colorScheme.onSurface,
                                                lineHeight = 22.sp
                                            )
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }

            Spacer(modifier = Modifier.height(24.dp))

            // 形态变化格表卡片
            Text(
                text = "形态变化 (变格/变位)",
                fontSize = 13.sp,
                fontWeight = FontWeight.Bold,
                color = AppleGray,
                modifier = Modifier.padding(bottom = 8.dp)
            )

            Card(
                shape = RoundedCornerShape(16.dp),
                colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
                elevation = CardDefaults.cardElevation(defaultElevation = 1.dp),
                modifier = Modifier.fillMaxWidth()
            ) {
                Column(modifier = Modifier.padding(16.dp)) {
                    if (inflections.isEmpty()) {
                        Text(
                            text = "该词无格位变化",
                            fontSize = 14.sp,
                            color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f),
                            modifier = Modifier.fillMaxWidth(),
                            textAlign = TextAlign.Center
                        )
                    } else {
                        val posLower = word.pos?.lowercase() ?: ""
                        when {
                            posLower.contains("noun") || posLower.contains("сущ") -> {
                                NounDeclensionTable(inflections = inflections)
                            }
                            posLower.contains("adj") || posLower.contains("прил") -> {
                                AdjDeclensionTable(inflections = inflections)
                            }
                            posLower.contains("verb") || posLower.contains("глаг") -> {
                                VerbConjugationTable(inflections = inflections)
                            }
                            else -> {
                                GeneralInflectionsList(inflections = inflections)
                            }
                        }
                    }
                }
            }

            Spacer(modifier = Modifier.height(24.dp))

            // 过滤和排序例句：按来源分组，保留新闻引用标签
            val groupedExamples = remember(examples) {
                val (phrases, sentences, news) = examples
                    .filter { ex -> ex.sentenceRu.length >= 8 && ex.sentenceZh.isNotEmpty() }
                    .sortedBy { Math.abs(it.sentenceRu.length - 25) }
                    .partition { ex -> ex.source.equals("BKRS-embedded", ignoreCase = true) }
                val (normal, newsItems) = sentences.partition { ex ->
                    !ex.source.startsWith("News:", ignoreCase = true)
                }
                Triple(phrases.take(5), normal.take(5), newsItems.take(5))
            }

            val (phraseExamples, sentenceExamples, newsExamples) = groupedExamples
            val hasAnyExamples = phraseExamples.isNotEmpty() || sentenceExamples.isNotEmpty() || newsExamples.isNotEmpty()

            if (hasAnyExamples) {
                Text(
                    text = "例句",
                    fontSize = 13.sp,
                    fontWeight = FontWeight.Bold,
                    color = AppleGray,
                    modifier = Modifier.padding(bottom = 8.dp)
                )

                Card(
                    shape = RoundedCornerShape(16.dp),
                    colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
                    elevation = CardDefaults.cardElevation(defaultElevation = 1.dp),
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Column(modifier = Modifier.padding(16.dp)) {
                        // 短语固定搭配
                        if (phraseExamples.isNotEmpty()) {
                            Text(
                                text = "短语固定搭配",
                                fontSize = 11.sp,
                                fontWeight = FontWeight.Medium,
                                color = AppleGray,
                                modifier = Modifier.padding(bottom = 8.dp)
                            )
                            phraseExamples.forEachIndexed { index, ex ->
                                if (index > 0) {
                                    HorizontalDivider(
                                        color = Color.Gray.copy(alpha = 0.05f),
                                        modifier = Modifier.padding(vertical = 6.dp)
                                    )
                                }
                                Column {
                                    Text(
                                        text = ex.sentenceRu,
                                        fontSize = 14.sp,
                                        color = MaterialTheme.colorScheme.onSurface,
                                        lineHeight = 20.sp
                                    )
                                    Spacer(modifier = Modifier.height(3.dp))
                                    Text(
                                        text = ex.sentenceZh,
                                        fontSize = 13.sp,
                                        color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.7f),
                                        lineHeight = 18.sp
                                    )
                                }
                            }
                            Spacer(modifier = Modifier.height(16.dp))
                        }

                        // 日常例句
                        if (sentenceExamples.isNotEmpty()) {
                            Text(
                                text = "日常例句",
                                fontSize = 11.sp,
                                fontWeight = FontWeight.Medium,
                                color = AppleGray,
                                modifier = Modifier.padding(bottom = 8.dp)
                            )
                            sentenceExamples.forEachIndexed { index, ex ->
                                if (index > 0) {
                                    HorizontalDivider(
                                        color = Color.Gray.copy(alpha = 0.05f),
                                        modifier = Modifier.padding(vertical = 6.dp)
                                    )
                                }
                                Column {
                                    Text(
                                        text = ex.sentenceRu,
                                        fontSize = 14.sp,
                                        color = MaterialTheme.colorScheme.onSurface,
                                        lineHeight = 20.sp
                                    )
                                    Spacer(modifier = Modifier.height(3.dp))
                                    Text(
                                        text = ex.sentenceZh,
                                        fontSize = 13.sp,
                                        color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.7f),
                                        lineHeight = 18.sp
                                    )
                                }
                            }
                            Spacer(modifier = Modifier.height(16.dp))
                        }

                        // 新闻例句（保留引用）
                        if (newsExamples.isNotEmpty()) {
                            Text(
                                text = "新闻例句",
                                fontSize = 11.sp,
                                fontWeight = FontWeight.Medium,
                                color = AppleGray,
                                modifier = Modifier.padding(bottom = 8.dp)
                            )
                            newsExamples.forEachIndexed { index, ex ->
                                if (index > 0) {
                                    HorizontalDivider(
                                        color = Color.Gray.copy(alpha = 0.05f),
                                        modifier = Modifier.padding(vertical = 6.dp)
                                    )
                                }
                                Column {
                                    Text(
                                        text = ex.sentenceRu,
                                        fontSize = 14.sp,
                                        color = MaterialTheme.colorScheme.onSurface,
                                        lineHeight = 20.sp
                                    )
                                    Spacer(modifier = Modifier.height(3.dp))
                                    Text(
                                        text = ex.sentenceZh,
                                        fontSize = 13.sp,
                                        color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.7f),
                                        lineHeight = 18.sp
                                    )
                                    Spacer(modifier = Modifier.height(3.dp))
                                    Text(
                                        text = ex.source,
                                        fontSize = 10.sp,
                                        color = AppleGray
                                    )
                                }
                            }
                        }
                    }
                }
            }

            Spacer(modifier = Modifier.height(30.dp))
        }

        // 2. 悬浮液态玻璃拟物风格返回栏 (Sticky Frosted Glass Top Bar)
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .align(Alignment.TopCenter)
                .background(
                    color = MaterialTheme.colorScheme.background.copy(alpha = 0.8f) // 半透明底色
                )
                .border(
                    width = 0.5.dp,
                    color = Color.Gray.copy(alpha = 0.1f) // 底边细边框，模拟玻璃边缘反射
                )
        ) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                modifier = Modifier
                    .statusBarsPadding() // 避开系统状态栏，解决“太靠上”问题
                    .fillMaxWidth()
                    .height(56.dp)
                    .padding(horizontal = 16.dp)
            ) {
                // 液态玻璃拟物胶囊返回按钮
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    modifier = Modifier
                        .background(
                            color = Color.Gray.copy(alpha = 0.08f), // 玻璃磨砂底色
                            shape = RoundedCornerShape(20.dp)
                        )
                        .border(
                            width = 1.dp,
                            color = Color.White.copy(alpha = 0.15f), // 高光描边
                            shape = RoundedCornerShape(20.dp)
                        )
                        .clickable { onBackClick() }
                        .padding(horizontal = 14.dp, vertical = 8.dp)
                ) {
                    Icon(
                        imageVector = Icons.Default.ArrowBack,
                        contentDescription = "Back",
                        tint = AppleBlue,
                        modifier = Modifier.size(18.dp)
                    )
                    Spacer(modifier = Modifier.width(6.dp))
                    Text(
                        text = "返回",
                        fontSize = 14.sp,
                        fontWeight = FontWeight.Medium,
                        color = AppleBlue
                    )
                }
            }
        }
    }
}

@Composable
fun RowScope.TableCell(
    text: AnnotatedString,
    weight: Float,
    isHeader: Boolean = false,
    textColor: Color = MaterialTheme.colorScheme.onSurface
) {
    Box(
        modifier = Modifier
            .weight(weight)
            .padding(vertical = 10.dp, horizontal = 6.dp),
        contentAlignment = Alignment.Center
    ) {
        Text(
            text = text,
            fontSize = if (isHeader) 11.sp else 12.sp,
            fontWeight = if (isHeader) FontWeight.Bold else FontWeight.Normal,
            color = if (isHeader) AppleGray else textColor,
            textAlign = TextAlign.Center
        )
    }
}

@Composable
fun RowScope.TableCell(
    text: String,
    weight: Float,
    isHeader: Boolean = false,
    textColor: Color = MaterialTheme.colorScheme.onSurface
) {
    TableCell(
        text = AnnotatedString(text),
        weight = weight,
        isHeader = isHeader,
        textColor = textColor
    )
}

@Composable
fun NounDeclensionTable(inflections: List<InflectionEntity>) {
    val cases = listOf(
        Triple("主格 (Им.)", "nom", "sg"),
        Triple("生格 (Род.)", "gen", "sg"),
        Triple("与格 (Дат.)", "dat", "sg"),
        Triple("宾格 (Вин.)", "acc", "sg"),
        Triple("工格 (Твор.)", "ins", "sg"),
        Triple("前置格 (Предл.)", "prep", "sg")
    )

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .border(0.5.dp, Color.Gray.copy(alpha = 0.15f), RoundedCornerShape(8.dp))
    ) {
        Row(modifier = Modifier.fillMaxWidth().background(Color.Gray.copy(alpha = 0.05f))) {
            TableCell(text = "格 (Case)", weight = 0.3f, isHeader = true)
            TableCell(text = "单数 (Sg.)", weight = 0.35f, isHeader = true)
            TableCell(text = "复数 (Pl.)", weight = 0.35f, isHeader = true)
        }
        HorizontalDivider(color = Color.Gray.copy(alpha = 0.15f))

        cases.forEachIndexed { idx, (caseName, caseTag, _) ->
            val sgForm = cleanAndDeduplicateForms(findNounForm(inflections, caseTag, "sg"))
            val plForm = cleanAndDeduplicateForms(findNounForm(inflections, caseTag, "pl"))
            Row(modifier = Modifier.fillMaxWidth()) {
                TableCell(text = caseName, weight = 0.3f, isHeader = true)
                TableCell(text = buildStressedAnnotatedString(sgForm), weight = 0.35f)
                TableCell(text = buildStressedAnnotatedString(plForm), weight = 0.35f)
            }
            if (idx < cases.size - 1) {
                HorizontalDivider(color = Color.Gray.copy(alpha = 0.08f))
            }
        }
    }
}

@Composable
fun AdjDeclensionTable(inflections: List<InflectionEntity>) {
    val cases = listOf(
        Triple("主格 (Им.)", "nom", "sg"),
        Triple("生格 (Род.)", "gen", "sg"),
        Triple("与格 (Дат.)", "dat", "sg"),
        Triple("宾格 (Вин.)", "acc", "sg"),
        Triple("工格 (Твор.)", "ins", "sg"),
        Triple("前置格 (Предл.)", "prep", "sg")
    )

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .border(0.5.dp, Color.Gray.copy(alpha = 0.15f), RoundedCornerShape(8.dp))
    ) {
        Row(modifier = Modifier.fillMaxWidth().background(Color.Gray.copy(alpha = 0.05f))) {
            TableCell(text = "格", weight = 0.2f, isHeader = true)
            TableCell(text = "阳性 (M.)", weight = 0.2f, isHeader = true)
            TableCell(text = "阴性 (F.)", weight = 0.2f, isHeader = true)
            TableCell(text = "中性 (N.)", weight = 0.2f, isHeader = true)
            TableCell(text = "复数 (Pl.)", weight = 0.2f, isHeader = true)
        }
        HorizontalDivider(color = Color.Gray.copy(alpha = 0.15f))

        cases.forEachIndexed { idx, (caseName, caseTag, _) ->
            val mascForm = cleanAndDeduplicateForms(findAdjForm(inflections, caseTag, "m"))
            val femForm = cleanAndDeduplicateForms(findAdjForm(inflections, caseTag, "f"))
            val neutForm = cleanAndDeduplicateForms(findAdjForm(inflections, caseTag, "n"))
            val plForm = cleanAndDeduplicateForms(findAdjForm(inflections, caseTag, "pl"))
            Row(modifier = Modifier.fillMaxWidth()) {
                TableCell(text = caseName, weight = 0.2f, isHeader = true)
                TableCell(text = buildStressedAnnotatedString(mascForm), weight = 0.2f)
                TableCell(text = buildStressedAnnotatedString(femForm), weight = 0.2f)
                TableCell(text = buildStressedAnnotatedString(neutForm), weight = 0.2f)
                TableCell(text = buildStressedAnnotatedString(plForm), weight = 0.2f)
            }
            if (idx < cases.size - 1) {
                HorizontalDivider(color = Color.Gray.copy(alpha = 0.08f))
            }
        }
    }
}

@Composable
fun VerbConjugationTable(inflections: List<InflectionEntity>) {
    Column(modifier = Modifier.fillMaxWidth()) {
        Text(
            text = "现在时 / 将来时 (Present / Future)",
            fontSize = 12.sp,
            fontWeight = FontWeight.Bold,
            color = AppleGray,
            modifier = Modifier.padding(bottom = 6.dp)
        )
        
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .border(0.5.dp, Color.Gray.copy(alpha = 0.15f), RoundedCornerShape(8.dp))
        ) {
            Row(modifier = Modifier.fillMaxWidth().background(Color.Gray.copy(alpha = 0.05f))) {
                TableCell(text = "人称 (Pers.)", weight = 0.35f, isHeader = true)
                TableCell(text = "单数 (Sg.)", weight = 0.325f, isHeader = true)
                TableCell(text = "复数 (Pl.)", weight = 0.325f, isHeader = true)
            }
            HorizontalDivider(color = Color.Gray.copy(alpha = 0.15f))
            
            val persons = listOf(
                Triple("第一人称 (Я / Мы)", "1", "sg"),
                Triple("第二人称 (Ты / Вы)", "2", "sg"),
                Triple("第三人称 (Он / Они)", "3", "sg")
            )
            
            persons.forEachIndexed { idx, (personName, personTag, _) ->
                val sgForm = cleanAndDeduplicateForms(findVerbPresFutForm(inflections, personTag, "sg"))
                val plForm = cleanAndDeduplicateForms(findVerbPresFutForm(inflections, personTag, "pl"))
                Row(modifier = Modifier.fillMaxWidth()) {
                    TableCell(text = personName, weight = 0.35f, isHeader = true)
                    TableCell(text = buildStressedAnnotatedString(sgForm), weight = 0.325f)
                    TableCell(text = buildStressedAnnotatedString(plForm), weight = 0.325f)
                }
                if (idx < persons.size - 1) {
                    HorizontalDivider(color = Color.Gray.copy(alpha = 0.08f))
                }
            }
        }

        Spacer(modifier = Modifier.height(18.dp))

        Text(
            text = "过去时 (Past Tense)",
            fontSize = 12.sp,
            fontWeight = FontWeight.Bold,
            color = AppleGray,
            modifier = Modifier.padding(bottom = 6.dp)
        )
        
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .border(0.5.dp, Color.Gray.copy(alpha = 0.15f), RoundedCornerShape(8.dp))
        ) {
            Row(modifier = Modifier.fillMaxWidth().background(Color.Gray.copy(alpha = 0.05f))) {
                TableCell(text = "阳性 (Masc.)", weight = 0.25f, isHeader = true)
                TableCell(text = "阴性 (Fem.)", weight = 0.25f, isHeader = true)
                TableCell(text = "中性 (Neut.)", weight = 0.25f, isHeader = true)
                TableCell(text = "复数 (Plur.)", weight = 0.25f, isHeader = true)
            }
            HorizontalDivider(color = Color.Gray.copy(alpha = 0.15f))
            
            val pastMasc = cleanAndDeduplicateForms(findVerbPastForm(inflections, "m"))
            val pastFem = cleanAndDeduplicateForms(findVerbPastForm(inflections, "f"))
            val pastNeut = cleanAndDeduplicateForms(findVerbPastForm(inflections, "n"))
            val pastPl = cleanAndDeduplicateForms(findVerbPastForm(inflections, "pl"))
            Row(modifier = Modifier.fillMaxWidth()) {
                TableCell(text = buildStressedAnnotatedString(pastMasc), weight = 0.25f)
                TableCell(text = buildStressedAnnotatedString(pastFem), weight = 0.25f)
                TableCell(text = buildStressedAnnotatedString(pastNeut), weight = 0.25f)
                TableCell(text = buildStressedAnnotatedString(pastPl), weight = 0.25f)
            }
        }

        Spacer(modifier = Modifier.height(18.dp))

        Text(
            text = "命令式 (Imperative)",
            fontSize = 12.sp,
            fontWeight = FontWeight.Bold,
            color = AppleGray,
            modifier = Modifier.padding(bottom = 6.dp)
        )
        
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .border(0.5.dp, Color.Gray.copy(alpha = 0.15f), RoundedCornerShape(8.dp))
        ) {
            Row(modifier = Modifier.fillMaxWidth().background(Color.Gray.copy(alpha = 0.05f))) {
                TableCell(text = "单数 (ты)", weight = 0.5f, isHeader = true)
                TableCell(text = "复数 (вы)", weight = 0.5f, isHeader = true)
            }
            HorizontalDivider(color = Color.Gray.copy(alpha = 0.15f))
            
            val impSg = cleanAndDeduplicateForms(findVerbImperativeForm(inflections, "sg"))
            val impPl = cleanAndDeduplicateForms(findVerbImperativeForm(inflections, "pl"))
            Row(modifier = Modifier.fillMaxWidth()) {
                TableCell(text = buildStressedAnnotatedString(impSg), weight = 0.5f)
                TableCell(text = buildStressedAnnotatedString(impPl), weight = 0.5f)
            }
        }
    }
}

@Composable
fun GeneralInflectionsList(inflections: List<InflectionEntity>) {
    Text(
        text = "所有变形词表：",
        fontSize = 12.sp,
        fontWeight = FontWeight.Bold,
        color = AppleGray,
        modifier = Modifier.padding(bottom = 6.dp)
    )
    
    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
        inflections.distinctBy { it.form }.forEach { inflection ->
            Row(
                verticalAlignment = Alignment.CenterVertically,
                modifier = Modifier
                    .fillMaxWidth()
                    .background(Color.Gray.copy(alpha = 0.04f), RoundedCornerShape(8.dp))
                    .padding(horizontal = 12.dp, vertical = 6.dp)
            ) {
                Text(
                    text = buildStressedAnnotatedString(inflection.form),
                    fontSize = 13.sp,
                    fontWeight = FontWeight.Bold,
                    color = MaterialTheme.colorScheme.onSurface,
                    modifier = Modifier.weight(0.4f)
                )
                Text(
                    text = inflection.grammarTag ?: "无详细说明",
                    fontSize = 11.sp,
                    color = AppleGray,
                    modifier = Modifier.weight(0.6f)
                )
            }
        }
    }
}

// 辅助方法：重音加粗与颜色高亮引擎 (自动清除所有单引号、反引号、Combining Accent 并对发重音的元音换色高亮，同时高亮ё/Ё)
fun buildStressedAnnotatedString(
    text: String,
    highlightColor: Color = Color(0xFFD32F2F) // 高端深红色
): AnnotatedString {
    if (text == "-" || text.isEmpty()) return AnnotatedString(text)
    
    val vowels = "аеиоуыэюяёАЕИОУЫЭЮЯЁ"
    val stressMarkers = "'\u0301`’"
    
    val builder = AnnotatedString.Builder()
    val cleanText = java.lang.StringBuilder()
    val stressedIndices = mutableListOf<Int>()
    
    var i = 0
    while (i < text.length) {
        val c = text[i]
        if (stressMarkers.contains(c)) {
            // 如果前一个字符是元音，则将该元音在cleanText中的当前位置记为重音
            if (cleanText.isNotEmpty()) {
                val lastChar = cleanText.last()
                if (vowels.contains(lastChar)) {
                    val lastIdx = cleanText.length - 1
                    if (!stressedIndices.contains(lastIdx)) {
                        stressedIndices.add(lastIdx)
                    }
                }
            }
            // 跳过，不把重音符号追加到 cleanText 中
        } else {
            cleanText.append(c)
        }
        i++
    }
    
    val finalStr = cleanText.toString()
    builder.append(finalStr)
    
    val hasExplicitStress = stressedIndices.isNotEmpty()
    
    // 应用重音换色及加粗样式
    for (idx in stressedIndices) {
        builder.addStyle(
            style = SpanStyle(
                color = highlightColor,
                fontWeight = FontWeight.Bold
            ),
            start = idx,
            end = idx + 1
        )
    }
    
    // 若没有显式标音，自动高亮任何 ё / Ё
    if (!hasExplicitStress) {
        for (idx in finalStr.indices) {
            val c = finalStr[idx]
            if (c == 'ё' || c == 'Ё') {
                builder.addStyle(
                    style = SpanStyle(
                        color = highlightColor,
                        fontWeight = FontWeight.Bold
                    ),
                    start = idx,
                    end = idx + 1
                )
            }
        }
    }
    
    return builder.toAnnotatedString()
}

// 辅助方法：过滤并去重变格变位词形 (去除 old spelling、将来时多词复合、保留重音剔除无重音重复项)
private fun cleanAndDeduplicateForms(rawFormsString: String): String {
    if (rawFormsString == "-" || rawFormsString.isEmpty()) return "-"
    
    fun stripStress(str: String): String {
        return str.replace("'", "").replace("\u0301", "").lowercase()
    }
    
    fun hasStress(str: String): Boolean {
        return str.contains("'") || str.contains("\u0301") || str.contains("ё") || str.contains("Ё")
    }

    val forms = rawFormsString.split(",").map { it.trim() }
    val filtered = mutableListOf<String>()
    
    for (f in forms) {
        if (f.isEmpty()) continue
        // 过滤以 ъ/Ъ 结尾的旧俄语拼写
        if (f.endsWith("ъ", ignoreCase = true)) continue
        // 过滤包含空格的复合形式 (例如 "буду работать")
        if (f.contains(" ")) continue
        filtered.add(f)
    }
    
    // 按是否有重音标志降序排序，使 stressed 形式排在前面以进行去重保留
    val sorted = filtered.sortedWith(compareByDescending { hasStress(it) })
    val deduped = mutableListOf<String>()
    val seenNorm = mutableSetOf<String>()
    
    for (f in sorted) {
        val norm = stripStress(f)
        if (norm !in seenNorm) {
            seenNorm.add(norm)
            deduped.add(f)
        }
    }
    
    return if (deduped.isNotEmpty()) deduped.joinToString(", ") else "-"
}

// 名词变格：搜 nom_sg, gen_sg, dat_sg, acc_sg, ins_sg, prep_sg, nom_pl, gen_pl, dat_pl, acc_pl, ins_pl, prep_pl
private fun findNounForm(inflections: List<InflectionEntity>, caseTag: String, number: String): String {
    val fullTag = "${caseTag}_${number}"  // e.g. "nom_sg"
    val matches = inflections.filter {
        val tag = it.grammarTag?.lowercase() ?: ""
        tag == fullTag || tag.startsWith("$fullTag,") || tag.contains(",$fullTag") || tag.contains(",$fullTag,")
    }
    return if (matches.isNotEmpty()) {
        matches.map { it.form }.distinct().joinToString(", ")
    } else "-"
}

// 形容词变格：搜 nom_m, gen_f, dat_n, acc_pl, ins_m, prep_f 等
private fun findAdjForm(inflections: List<InflectionEntity>, caseTag: String, gender: String): String {
    val fullTag = "${caseTag}_${gender}"  // e.g. "nom_m"
    val matches = inflections.filter {
        val tag = it.grammarTag?.lowercase() ?: ""
        tag == fullTag || tag.startsWith("$fullTag,") || tag.contains(",$fullTag") || tag.contains(",$fullTag,")
    }
    return if (matches.isNotEmpty()) {
        matches.map { it.form }.distinct().joinToString(", ")
    } else "-"
}

// 动词现在时/将来时：搜 pres_1sg, pres_2sg, pres_3sg, pres_1pl, pres_2pl, pres_3pl 和 fut_ 前缀
private fun findVerbPresFutForm(inflections: List<InflectionEntity>, personTag: String, number: String): String {
    val presTag = "pres_${personTag}${number}"  // e.g. "pres_1sg"
    val futTag = "fut_${personTag}${number}"    // e.g. "fut_1sg"
    val matches = inflections.filter {
        val tag = it.grammarTag?.lowercase() ?: ""
        tag == presTag || tag == futTag ||
        tag.startsWith("$presTag,") || tag.startsWith("$futTag,") ||
        tag.contains(",$presTag") || tag.contains(",$futTag") ||
        tag.contains(",$presTag,") || tag.contains(",$futTag,")
    }
    return if (matches.isNotEmpty()) {
        matches.map { it.form }.distinct().joinToString(", ")
    } else "-"
}

// 动词过去时：搜 past_m, past_f, past_n, past_pl
private fun findVerbPastForm(inflections: List<InflectionEntity>, genderOrPlural: String): String {
    val fullTag = "past_${genderOrPlural}"  // e.g. "past_m"
    val matches = inflections.filter {
        val tag = it.grammarTag?.lowercase() ?: ""
        tag == fullTag || tag.startsWith("$fullTag,") || tag.contains(",$fullTag") || tag.contains(",$fullTag,")
    }
    return if (matches.isNotEmpty()) {
        matches.map { it.form }.distinct().joinToString(", ")
    } else "-"
}

// 动词命令式：搜 imp_sg, imp_pl
private fun findVerbImperativeForm(inflections: List<InflectionEntity>, number: String): String {
    val fullTag = "imp_${number}"  // e.g. "imp_sg"
    val matches = inflections.filter {
        val tag = it.grammarTag?.lowercase() ?: ""
        tag == fullTag || tag.startsWith("$fullTag,") || tag.contains(",$fullTag") || tag.contains(",$fullTag,")
    }
    return if (matches.isNotEmpty()) {
        matches.map { it.form }.distinct().joinToString(", ")
    } else "-"
}