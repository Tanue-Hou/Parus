"""
Parus v0.2 — 工具函数
"""

import re
import unicodedata


def clean_stress(text):
    """去除重音符号并小写"""
    if not text:
        return ""
    text = text.replace('\u0301', '')
    normalized = unicodedata.normalize('NFD', text)
    cleaned = "".join(c for c in normalized if unicodedata.category(c) != 'Mn')
    return cleaned.lower().strip()


def clean_dsl_text(text):
    """清洗 DSL 标签，提取纯文本"""
    if not text:
        return ""
    text = text.replace(r'\[', '\u0001').replace(r'\]', '\u0002')
    text = text.replace('[/m]', '\n').replace('[/*]', '\n')
    text = text.replace('[*]', '• ')
    text = re.sub(r'\[.*?\]', '', text)
    text = text.replace('\u0001', '[').replace('\u0002', ']')
    lines = [line.strip() for line in text.split('\n')]
    lines = [line for line in lines if line]
    return '\n'.join(lines)


def normalize_grammar_tag(tags_list):
    """
    将 Kaikki 的 tags 列表规范化为统一格式。
    输入: ['nominative', 'singular']
    输出: 'nom_sg'
    
    如果无法识别，返回原始逗号分隔字符串。
    """
    if not tags_list:
        return None
    
    tags_lower = [t.lower() for t in tags_list]
    tags_set = set(tags_lower)
    
    # 检测词性
    is_noun = 'animate' in tags_set or 'inanimate' in tags_set
    is_verb = 'infinitive' in tags_set or any(t.endswith('person') for t in tags_lower)
    is_adj = any(t in tags_set for t in ['comparative', 'superlative', 'short-form'])
    
    # 检测格
    case_map = {
        'nominative': 'nom', 'nom': 'nom',
        'genitive': 'gen', 'gen': 'gen',
        'dative': 'dat', 'dat': 'dat',
        'accusative': 'acc', 'acc': 'acc',
        'instrumental': 'ins', 'ins': 'ins',
        'prepositional': 'prep', 'prep': 'prep',
        'locative': 'prep',
    }
    case = None
    for k, v in case_map.items():
        if k in tags_set:
            case = v
            break
    
    # 检测数
    if 'plural' in tags_set or 'pl' in tags_set:
        number = 'pl'
    elif 'singular' in tags_set or 'sg' in tags_set:
        number = 'sg'
    else:
        number = None
    
    # 检测性
    gender_map = {'masculine': 'm', 'feminine': 'f', 'neuter': 'n', 'masc': 'm', 'fem': 'f', 'neut': 'n'}
    gender = None
    for k, v in gender_map.items():
        if k in tags_set:
            gender = v
            break
    
    # 检测人称
    person_map = {'first-person': '1', 'second-person': '2', 'third-person': '3'}
    person = None
    for k, v in person_map.items():
        if k in tags_set:
            person = v
            break
    
    # 检测时态
    tense = None
    if 'past' in tags_set:
        tense = 'past'
    elif 'present' in tags_set:
        tense = 'pres'
    elif 'future' in tags_set:
        tense = 'fut'
    
    # 检测命令式
    if 'imperative' in tags_set:
        if number == 'sg':
            return 'imp_sg'
        elif number == 'pl':
            return 'imp_pl'
        else:
            return 'imp'
    
    # 名词变格: case_number
    if case and number:
        return f"{case}_{number}"
    
    # 形容词: case_gender
    if case and gender:
        return f"{case}_{gender}"
    if case and number:
        return f"{case}_{number}"
    
    # 动词变位: tense_person_number
    if person and number:
        if tense:
            return f"{tense}_{person}{number}"
        return f"pres_{person}{number}"
    
    # 过去时: past_gender
    if tense == 'past' and gender:
        return f"past_{gender}"
    if tense == 'past' and number == 'pl':
        return "past_pl"
    
    # 兜底: 返回原始 tags
    return ",".join(tags_lower)


def extract_bkrs_examples(definition_text):
    """
    从 BKRS 释义文本中提取内嵌例句。
    格式: • xxx - yyy
    返回: [(ru_sentence, zh_sentence), ...]
    """
    pattern = re.compile(r'•\s*([^-\n]+?)\s*-\s*([^\n•]+)')
    matches = pattern.findall(definition_text)
    return [(ru.strip(), zh.strip()) for ru, zh in matches]


def get_difficulty_level(rank):
    """词频排名 → 难度等级"""
    if not rank:
        return None
    if rank <= 2000:
        return "A1"
    elif rank <= 5000:
        return "A2"
    elif rank <= 10000:
        return "B1"
    elif rank <= 20000:
        return "B2"
    elif rank <= 50000:
        return "C1"
    else:
        return "C2"


def is_noise_tag(tags_list):
    """判断 tags 是否为噪声（模板标记、罗马化等）"""
    if not tags_list:
        return True
    tags_lower = [t.lower() for t in tags_list]
    noise = {'romanization', 'ru-conj', 'ru-noun-table', 'inflection-template',
             'hard-stem', 'accent-d', 'class', 'noun-from-verb', 'table-tags',
             'no-table-tags', 'no-short-form', 'velar-stem', 'accent-a',
             'accent-b', 'accent-c', 'accent-d', 'accent-e', 'accent-f'}
    return bool(noise & set(tags_lower))


def pymorphy_pos_to_en(pymorphy_pos):
    """pymorphy3 的俄语 POS 映射到英文"""
    pos_map = {
        'NOUN': 'noun', 'ADJF': 'adj', 'ADJS': 'adj', 'COMP': 'adj',
        'VERB': 'verb', 'INFN': 'verb', 'PRTF': 'verb', 'PRTS': 'verb',
        'GRND': 'verb', 'ADVB': 'adv', 'PREP': 'prep', 'CONJ': 'conj',
        'PRCL': 'part', 'INTJ': 'intj', 'NUMR': 'num', 'NPRO': 'pron',
    }
    return pos_map.get(pymorphy_pos)


def guess_pos_from_suffix(lemma):
    """后缀启发式判断词性

    注意：-ние/-ие 既可能是名词(существование)也可能是形容词复数(синие)，
    但词典中形容词 lemma 通常是 -ый/-ий/-ой 形式，所以 -ние/-ие 视为名词。
    同理 -ство/-ость/-ота 是典型名词后缀，需在 -о/-е 的 adv 判断之前检查。
    """
    # 动词
    if lemma.endswith('ть') or lemma.endswith('ти') or lemma.endswith('чь'):
        return 'verb'
    if lemma.endswith('ся') or lemma.endswith('сь'):
        return 'verb'

    # 名词后缀（必须在 adj/adv 之前检查，避免 -ство 被误判为 adv）
    noun_suffixes = [
        'ство', 'ость', 'ота',     # 抽象名词
        'ение', 'ание', 'ние', 'тие',  # 动名词
        'ость', 'изация', 'ация', 'яция', 'ификация',  # 名词化后缀
        'изм', 'ист',              # 主义/人
        'ник', 'тель', 'чик', 'щик',  # 人/器物
        'ик', 'ек', 'ок',          # 指小
        'ина',                     # 集合/大
        'ка', 'ня',                # 女性/场所
        'ло',                      # 工具
    ]
    for suf in noun_suffixes:
        if lemma.endswith(suf):
            return 'noun'

    # 形容词
    if any(lemma.endswith(x) for x in ['ый', 'ой', 'ий', 'ая', 'яя', 'ое', 'ее', 'ые', 'ие']):
        return 'adj'

    # 副词
    if lemma.endswith('о') or lemma.endswith('е') or lemma.endswith('ски'):
        return 'adv'

    return 'noun'
