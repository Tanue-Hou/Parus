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
import com.tanue.parus.ui.theme.ParusTheme
import com.tanue.parus.ui.theme.AppleBlue
import com.tanue.parus.ui.theme.AppleGray
import com.tanue.parus.data.model.WordWithDetails
import com.tanue.parus.data.model.InflectionEntity
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
    var selectedWord by remember { mutableStateOf<WordWithDetails?>(null) }

    if (selectedWord != null) {
        BackHandler {
            selectedWord = null
        }
        WordDetailScreen(
            wordWithDetails = selectedWord!!,
            onBackClick = { selectedWord = null },
            modifier = Modifier.fillMaxSize()
        )
    } else {
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
                        text = word.lemmaStressed,
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
    val scrollState = rememberScrollState()

    Column(
        modifier = modifier
            .fillMaxSize()
            .verticalScroll(scrollState)
            .padding(16.dp)
    ) {
        // 返回导航栏
        Row(
            verticalAlignment = Alignment.CenterVertically,
            modifier = Modifier
                .fillMaxWidth()
                .padding(vertical = 4.dp)
                .clickable { onBackClick() }
        ) {
            Icon(
                imageVector = Icons.Default.ArrowBack,
                contentDescription = "Back",
                tint = AppleBlue,
                modifier = Modifier.size(24.dp)
            )
            Spacer(modifier = Modifier.width(4.dp))
            Text(
                text = "返回词典",
                fontSize = 16.sp,
                fontWeight = FontWeight.Medium,
                color = AppleBlue
            )
        }

        Spacer(modifier = Modifier.height(16.dp))

        // 单词头部及词性
        Row(
            verticalAlignment = Alignment.CenterVertically,
            modifier = Modifier.fillMaxWidth()
        ) {
            Text(
                text = word.lemmaStressed,
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
                            Text(
                                text = df.definition,
                                fontSize = 15.sp,
                                color = MaterialTheme.colorScheme.onSurface,
                                lineHeight = 22.sp
                            )
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
        
        Spacer(modifier = Modifier.height(30.dp))
    }
}

@Composable
fun RowScope.TableCell(
    text: String,
    weight: Float,
    isHeader: Boolean = false,
    textColor: Color = MaterialTheme.colorScheme.onSurface
) {
    Box(
        modifier = Modifier
            .weight(weight)
            .border(0.5.dp, Color.Gray.copy(alpha = 0.15f))
            .padding(8.dp),
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
fun NounDeclensionTable(inflections: List<InflectionEntity>) {
    val cases = listOf(
        Triple("主格 (Им.)", "nominative", "nom"),
        Triple("生格 (Род.)", "genitive", "gen"),
        Triple("与格 (Дат.)", "dative", "dat"),
        Triple("宾格 (Вин.)", "accusative", "acc"),
        Triple("工格 (Твор.)", "instrumental", "ins"),
        Triple("前置格 (Предл.)", "prepositional", "pre")
    )

    Column(modifier = Modifier.fillMaxWidth()) {
        Row(modifier = Modifier.fillMaxWidth().background(Color.Gray.copy(alpha = 0.05f))) {
            TableCell(text = "格 (Case)", weight = 0.3f, isHeader = true)
            TableCell(text = "单数 (Sg.)", weight = 0.35f, isHeader = true)
            TableCell(text = "复数 (Pl.)", weight = 0.35f, isHeader = true)
        }

        cases.forEach { (caseName, caseTag, _) ->
            val sgForm = findNounForm(inflections, caseTag, "singular")
            val plForm = findNounForm(inflections, caseTag, "plural")
            Row(modifier = Modifier.fillMaxWidth()) {
                TableCell(text = caseName, weight = 0.3f, isHeader = true)
                TableCell(text = sgForm, weight = 0.35f)
                TableCell(text = plForm, weight = 0.35f)
            }
        }
    }
}

@Composable
fun AdjDeclensionTable(inflections: List<InflectionEntity>) {
    val cases = listOf(
        Triple("主格 (Им.)", "nominative", "nom"),
        Triple("生格 (Род.)", "genitive", "gen"),
        Triple("与格 (Дат.)", "dative", "dat"),
        Triple("宾格 (Вин.)", "accusative", "acc"),
        Triple("工格 (Твор.)", "instrumental", "ins"),
        Triple("前置格 (Предл.)", "prepositional", "pre")
    )

    Column(modifier = Modifier.fillMaxWidth()) {
        Row(modifier = Modifier.fillMaxWidth().background(Color.Gray.copy(alpha = 0.05f))) {
            TableCell(text = "格", weight = 0.2f, isHeader = true)
            TableCell(text = "阳性 (M.)", weight = 0.2f, isHeader = true)
            TableCell(text = "阴性 (F.)", weight = 0.2f, isHeader = true)
            TableCell(text = "中性 (N.)", weight = 0.2f, isHeader = true)
            TableCell(text = "复数 (Pl.)", weight = 0.2f, isHeader = true)
        }

        cases.forEach { (caseName, caseTag, _) ->
            val mascForm = findAdjForm(inflections, caseTag, "masculine")
            val femForm = findAdjForm(inflections, caseTag, "feminine")
            val neutForm = findAdjForm(inflections, caseTag, "neuter")
            val plForm = findAdjForm(inflections, caseTag, "plural")
            Row(modifier = Modifier.fillMaxWidth()) {
                TableCell(text = caseName, weight = 0.2f, isHeader = true)
                TableCell(text = mascForm, weight = 0.2f)
                TableCell(text = femForm, weight = 0.2f)
                TableCell(text = neutForm, weight = 0.2f)
                TableCell(text = plForm, weight = 0.2f)
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
        
        Row(modifier = Modifier.fillMaxWidth().background(Color.Gray.copy(alpha = 0.05f))) {
            TableCell(text = "人称 (Pers.)", weight = 0.35f, isHeader = true)
            TableCell(text = "单数 (Sg.)", weight = 0.325f, isHeader = true)
            TableCell(text = "复数 (Pl.)", weight = 0.325f, isHeader = true)
        }
        
        val persons = listOf(
            Triple("第一人称 (Я / Мы)", "first-person", "1st"),
            Triple("第二人称 (Ты / Вы)", "second-person", "2nd"),
            Triple("第三人称 (Он / Они)", "third-person", "3rd")
        )
        
        persons.forEach { (personName, personTag, _) ->
            val sgForm = findVerbPresFutForm(inflections, personTag, "singular")
            val plForm = findVerbPresFutForm(inflections, personTag, "plural")
            Row(modifier = Modifier.fillMaxWidth()) {
                TableCell(text = personName, weight = 0.35f, isHeader = true)
                TableCell(text = sgForm, weight = 0.325f)
                TableCell(text = plForm, weight = 0.325f)
            }
        }

        Spacer(modifier = Modifier.height(14.dp))

        Text(
            text = "过去时 (Past Tense)",
            fontSize = 12.sp,
            fontWeight = FontWeight.Bold,
            color = AppleGray,
            modifier = Modifier.padding(bottom = 6.dp)
        )
        
        Row(modifier = Modifier.fillMaxWidth().background(Color.Gray.copy(alpha = 0.05f))) {
            TableCell(text = "阳性 (Masc.)", weight = 0.25f, isHeader = true)
            TableCell(text = "阴性 (Fem.)", weight = 0.25f, isHeader = true)
            TableCell(text = "中性 (Neut.)", weight = 0.25f, isHeader = true)
            TableCell(text = "复数 (Plur.)", weight = 0.25f, isHeader = true)
        }
        
        val pastMasc = findVerbPastForm(inflections, "masculine")
        val pastFem = findVerbPastForm(inflections, "feminine")
        val pastNeut = findVerbPastForm(inflections, "neuter")
        val pastPl = findVerbPastForm(inflections, "plural")
        Row(modifier = Modifier.fillMaxWidth()) {
            TableCell(text = pastMasc, weight = 0.25f)
            TableCell(text = pastFem, weight = 0.25f)
            TableCell(text = pastNeut, weight = 0.25f)
            TableCell(text = pastPl, weight = 0.25f)
        }

        Spacer(modifier = Modifier.height(14.dp))

        Text(
            text = "命令式 (Imperative)",
            fontSize = 12.sp,
            fontWeight = FontWeight.Bold,
            color = AppleGray,
            modifier = Modifier.padding(bottom = 6.dp)
        )
        
        Row(modifier = Modifier.fillMaxWidth().background(Color.Gray.copy(alpha = 0.05f))) {
            TableCell(text = "单数 (ты)", weight = 0.5f, isHeader = true)
            TableCell(text = "复数 (вы)", weight = 0.5f, isHeader = true)
        }
        
        val impSg = findVerbImperativeForm(inflections, "singular")
        val impPl = findVerbImperativeForm(inflections, "plural")
        Row(modifier = Modifier.fillMaxWidth()) {
            TableCell(text = impSg, weight = 0.5f)
            TableCell(text = impPl, weight = 0.5f)
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
                    text = inflection.form,
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

private fun findNounForm(inflections: List<InflectionEntity>, case: String, number: String): String {
    val matches = inflections.filter {
        val tag = it.grammarTag?.lowercase() ?: ""
        tag.contains(case) && tag.contains(number)
    }
    if (matches.isNotEmpty()) {
        return matches.map { it.form }.distinct().joinToString(", ")
    }
    
    if (number == "singular") {
        val singularMatches = inflections.filter {
            val tag = it.grammarTag?.lowercase() ?: ""
            tag.contains(case) && !tag.contains("plural")
        }
        if (singularMatches.isNotEmpty()) {
            return singularMatches.map { it.form }.distinct().joinToString(", ")
        }
    }
    
    return "-"
}

private fun findAdjForm(inflections: List<InflectionEntity>, case: String, genderOrPlural: String): String {
    val matches = inflections.filter {
        val tag = it.grammarTag?.lowercase() ?: ""
        tag.contains(case) && tag.contains(genderOrPlural)
    }
    if (matches.isNotEmpty()) {
        return matches.map { it.form }.distinct().joinToString(", ")
    }
    
    if (genderOrPlural == "masculine") {
        val mascMatches = inflections.filter {
            val tag = it.grammarTag?.lowercase() ?: ""
            tag.contains(case) && !tag.contains("feminine") && !tag.contains("neuter") && !tag.contains("plural")
        }
        if (mascMatches.isNotEmpty()) {
            return mascMatches.map { it.form }.distinct().joinToString(", ")
        }
    }
    return "-"
}

private fun findVerbPresFutForm(inflections: List<InflectionEntity>, person: String, number: String): String {
    val matches = inflections.filter {
        val tag = it.grammarTag?.lowercase() ?: ""
        tag.contains(person) && tag.contains(number) && !tag.contains("past") && !tag.contains("imperative")
    }
    return if (matches.isNotEmpty()) {
        matches.map { it.form }.distinct().joinToString(", ")
    } else {
        "-"
    }
}

private fun findVerbPastForm(inflections: List<InflectionEntity>, genderOrPlural: String): String {
    val matches = inflections.filter {
        val tag = it.grammarTag?.lowercase() ?: ""
        tag.contains("past") && tag.contains(genderOrPlural)
    }
    return if (matches.isNotEmpty()) {
        matches.map { it.form }.distinct().joinToString(", ")
    } else {
        "-"
    }
}

private fun findVerbImperativeForm(inflections: List<InflectionEntity>, number: String): String {
    val matches = inflections.filter {
        val tag = it.grammarTag?.lowercase() ?: ""
        tag.contains("imperative") && tag.contains(number)
    }
    return if (matches.isNotEmpty()) {
        matches.map { it.form }.distinct().joinToString(", ")
    } else {
        "-"
    }
}