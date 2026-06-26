package com.tanue.parus.presentation.search

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.tanue.parus.data.model.WordWithDetails
import com.tanue.parus.data.repository.DictionaryRepository
import kotlinx.coroutines.FlowPreview
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch

class SearchViewModel(private val repository: DictionaryRepository) : ViewModel() {
    private val _searchQuery = MutableStateFlow("")
    val searchQuery: StateFlow<String> = _searchQuery.asStateFlow()

    private val _searchResults = MutableStateFlow<List<WordWithDetails>>(emptyList())
    val searchResults: StateFlow<List<WordWithDetails>> = _searchResults.asStateFlow()

    private val _isLoading = MutableStateFlow(false)
    val isLoading: StateFlow<Boolean> = _isLoading.asStateFlow()

    init {
        @OptIn(FlowPreview::class)
        viewModelScope.launch {
            _searchQuery
                .debounce(200)
                .distinctUntilChanged()
                .flatMapLatest { query ->
                    if (query.isBlank()) {
                        flowOf(emptyList())
                    } else {
                        flow {
                            _isLoading.value = true
                            try {
                                emit(repository.search(query))
                            } catch (e: Exception) {
                                android.util.Log.e("ParusSearch", "搜索失败: query='$query'", e)
                                emit(emptyList())
                            } finally {
                                _isLoading.value = false
                            }
                        }
                    }
                }
                .collect { results ->
                    _searchResults.value = results
                }
        }
    }

    fun onQueryChanged(newQuery: String) {
        _searchQuery.value = newQuery
    }
}
